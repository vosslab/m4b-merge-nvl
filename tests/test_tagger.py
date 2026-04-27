"""
Unit tests for tagger module.

Tests metadata tagging and cover art embedding in M4B files.
"""

import subprocess

import pytest
import mutagen.mp4

import m4b_merge.tagger as tagger


@pytest.fixture
def tiny_m4b(tmp_path):
	"""
	Generate a tiny valid M4B file using ffmpeg.

	Returns:
		Path to the M4B file.
	"""
	output_file = tmp_path / "test.m4b"

	# Generate a 2-second silence via ffmpeg and save as M4A (which we'll rename)
	m4a_file = tmp_path / "test.m4a"
	subprocess.run(
		[
			"ffmpeg",
			"-y",
			"-f", "lavfi",
			"-i", "anullsrc=r=44100:cl=stereo",
			"-t", "2",
			"-c:a", "aac",
			str(m4a_file),
		],
		capture_output=True,
		check=True,
	)

	# Rename to .m4b
	m4a_file.rename(output_file)
	return output_file


@pytest.fixture
def tiny_jpeg(tmp_path):
	"""
	Generate a tiny valid JPEG cover image.

	Returns:
		Path to the JPEG file.
	"""
	output_file = tmp_path / "cover.jpg"

	# Generate a 16x16 red JPEG
	subprocess.run(
		[
			"ffmpeg",
			"-y",
			"-f", "lavfi",
			"-i", "color=red:size=16x16",
			"-frames:v", "1",
			str(output_file),
		],
		capture_output=True,
		check=True,
	)

	return output_file


def test_tagger_write_basic(tiny_m4b, tiny_jpeg):
	"""Test basic metadata tagging."""
	metadata = {
		"title": "Test Audiobook",
		"subtitle": None,
		"authors": ["Author One", "Author Two"],
		"narrators": ["Narrator One"],
		"length": "01:30:45.000",
		"release_date": "2024-01-15",
		"publisher": "Test Publisher",
		"language": "English",
		"description": "A test audiobook description.",
		"cover_url": None,
		"chapters": [],
	}

	# Write tags
	tagger.write(tiny_m4b, metadata, tiny_jpeg)

	# Read back and verify
	mp4_file = mutagen.mp4.MP4(str(tiny_m4b))

	# Check title
	assert "\xa9nam" in mp4_file
	assert mp4_file["\xa9nam"][0] == "Test Audiobook"

	# Check artists
	assert "\xa9ART" in mp4_file
	assert mp4_file["\xa9ART"][0] == "Author One, Author Two"

	# Check album (should be title)
	assert "\xa9alb" in mp4_file
	assert mp4_file["\xa9alb"][0] == "Test Audiobook"

	# Check release date
	assert "\xa9day" in mp4_file
	assert mp4_file["\xa9day"][0] == "2024-01-15"

	# Check narrators as composer
	assert "\xa9wrt" in mp4_file
	assert mp4_file["\xa9wrt"][0] == "Narrator One"

	# Check description
	assert "desc" in mp4_file
	assert mp4_file["desc"][0] == "A test audiobook description."

	# Check cover was embedded
	assert "covr" in mp4_file
	assert len(mp4_file["covr"]) > 0


def test_tagger_idempotent(tiny_m4b, tiny_jpeg):
	"""Test that writing twice produces idempotent results."""
	metadata = {
		"title": "Idempotent Test",
		"subtitle": None,
		"authors": ["Author"],
		"narrators": ["Narrator"],
		"length": "02:00:00.000",
		"release_date": "2024-02-01",
		"publisher": "Publisher",
		"language": "English",
		"description": "Description",
		"cover_url": None,
		"chapters": [],
	}

	# Write first time
	tagger.write(tiny_m4b, metadata, tiny_jpeg)
	mp4_file_1 = mutagen.mp4.MP4(str(tiny_m4b))
	title_1 = mp4_file_1["\xa9nam"][0]
	artist_1 = mp4_file_1["\xa9ART"][0]

	# Write second time
	tagger.write(tiny_m4b, metadata, tiny_jpeg)
	mp4_file_2 = mutagen.mp4.MP4(str(tiny_m4b))
	title_2 = mp4_file_2["\xa9nam"][0]
	artist_2 = mp4_file_2["\xa9ART"][0]

	# Verify results are identical
	assert title_1 == title_2
	assert artist_1 == artist_2


def test_tagger_skip_none_values(tiny_m4b):
	"""Test that None values are skipped."""
	metadata = {
		"title": "Minimal",
		"subtitle": None,
		"authors": None,
		"narrators": None,
		"length": None,
		"release_date": None,
		"publisher": None,
		"language": None,
		"description": None,
		"cover_url": None,
		"chapters": [],
	}

	# Write tags (should skip most)
	tagger.write(tiny_m4b, metadata, None)

	# Read back
	mp4_file = mutagen.mp4.MP4(str(tiny_m4b))

	# Title should be present
	assert "\xa9nam" in mp4_file
	assert mp4_file["\xa9nam"][0] == "Minimal"

	# Artists should not be present (empty list)
	if "\xa9ART" in mp4_file:
		# If present, should be empty or N/A
		assert len(mp4_file["\xa9ART"]) == 0 or mp4_file["\xa9ART"][0] == ""


def test_tagger_with_genres(tiny_m4b, tiny_jpeg):
	"""Test genre tagging."""
	metadata = {
		"title": "Genre Test",
		"subtitle": None,
		"authors": ["Author"],
		"narrators": ["Narrator"],
		"length": None,
		"release_date": None,
		"publisher": None,
		"language": None,
		"description": None,
		"cover_url": None,
		"genres": ["Fiction", "Science Fiction"],
		"chapters": [],
	}

	# Write tags
	tagger.write(tiny_m4b, metadata, tiny_jpeg)

	# Read back
	mp4_file = mutagen.mp4.MP4(str(tiny_m4b))

	# Check genre (should be first one)
	assert "\xa9gen" in mp4_file
	assert mp4_file["\xa9gen"][0] == "Fiction"


def test_tagger_no_cover(tiny_m4b):
	"""Test writing metadata without cover."""
	metadata = {
		"title": "No Cover",
		"subtitle": None,
		"authors": ["Author"],
		"narrators": ["Narrator"],
		"length": None,
		"release_date": None,
		"publisher": None,
		"language": None,
		"description": None,
		"cover_url": None,
		"chapters": [],
	}

	# Write tags without cover
	tagger.write(tiny_m4b, metadata, None)

	# Read back
	mp4_file = mutagen.mp4.MP4(str(tiny_m4b))

	# Title should be present
	assert "\xa9nam" in mp4_file
	assert mp4_file["\xa9nam"][0] == "No Cover"

	# Cover should not be present (or empty)
	if "covr" in mp4_file:
		assert len(mp4_file["covr"]) == 0
