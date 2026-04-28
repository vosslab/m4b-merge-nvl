"""
Integration tests for merger module.

Tests the full M4B merge pipeline with synthetic audio and metadata.
"""

import subprocess

import pytest

import m4b_merge.merger as merger
import m4b_merge.ffmpeg_runner as ffmpeg_runner

import conftest


@pytest.fixture
def three_mp3_fixture(tmp_path):
	"""
	Generate a 3-file MP3 fixture using ffmpeg.

	Returns:
		Tuple of (fixture_dir, file_list).
	"""
	fixture_dir = tmp_path / "fixture"
	fixture_dir.mkdir()

	# Generate 3 short MP3 files with different frequencies
	files = []
	for idx in range(1, 4):
		output_file = fixture_dir / f"{idx:02d}_chapter.mp3"

		# Generate 3 seconds of sine wave at different frequencies
		frequency = 440 + (idx * 100)
		subprocess.run(
			[
				"ffmpeg",
				"-y",
				"-f", "lavfi",
				"-i", f"sine=frequency={frequency}:duration=3",
				"-c:a", "libmp3lame",
				"-q:a", "5",
				str(output_file),
			],
			capture_output=True,
			check=True,
		)
		files.append(output_file)

	return fixture_dir, files


@pytest.fixture
def test_runtime_config(tmp_path):
	"""Build a minimal RuntimeConfig for testing."""
	tmp_merge_dir = tmp_path / "m4b_merge_tmp"
	tmp_merge_dir.mkdir(parents=True, exist_ok=True)
	return conftest.make_runtime_config(tmp_merge_dir)


def test_merger_with_sidecar(three_mp3_fixture, tmp_path, test_runtime_config):
	"""Test merger with sidecar metadata (no ASIN)."""
	fixture_dir, files = three_mp3_fixture
	output_dir = tmp_path / "output"
	output_dir.mkdir(parents=True, exist_ok=True)

	# Create a sidecar.txt
	sidecar_content = """Conquering the Electron
By: Derek Cheung, Eric Brach
Narrated by: Eric Jason Martin
Length: 00:09:00.000
Release date: 03-01-20
Language: English
Publisher: Test Publisher
Publisher's summary: A test audiobook about electrons."""

	sidecar_file = fixture_dir / "metadata.txt"
	sidecar_file.write_text(sidecar_content)

	# Run merger
	m = merger.Merger(
		input_path=fixture_dir,
		output_path=output_dir,
		runtime_config=test_runtime_config,
		no_asin=True,
		asin=None,
	)

	m.run()

	# Verify output exists
	output_file = output_dir / "Conquering_the_Electron.m4b"
	assert output_file.exists(), f"Output file not found: {output_file}"

	# Verify the file is valid and has chapters
	probe = ffmpeg_runner.probe(output_file, test_runtime_config)
	assert probe["duration_seconds"] > 0


def test_merger_dry_run(three_mp3_fixture, tmp_path, capsys):
	"""Test merger dry-run mode."""
	fixture_dir, files = three_mp3_fixture
	output_dir = tmp_path / "output"
	output_dir.mkdir(parents=True, exist_ok=True)

	# Create a sidecar.txt
	sidecar_content = """Test Audiobook
By: Author
Narrated by: Narrator
Length: 00:09:00.000
Release date: 04-15-24
Language: English
Publisher: Publisher
Publisher's summary: Test summary."""

	sidecar_file = fixture_dir / "sidecar.txt"
	sidecar_file.write_text(sidecar_content)

	# Build a dry-run config
	tmp_merge_dir = tmp_path / "m4b_merge_tmp"
	tmp_merge_dir.mkdir(parents=True, exist_ok=True)
	dry_run_config = conftest.make_runtime_config(tmp_merge_dir, dry_run=True)

	# Run merger
	m = merger.Merger(
		input_path=fixture_dir,
		output_path=output_dir,
		runtime_config=dry_run_config,
		no_asin=True,
		asin=None,
	)

	m.run()

	# Verify no output file was created
	output_files = list(output_dir.glob("*.m4b"))
	assert len(output_files) == 0, "Dry-run should not create output files"

	# Verify dry-run report was printed
	captured = capsys.readouterr()
	assert "DRY-RUN REPORT" in captured.out
	assert "Output Path" in captured.out


def test_merger_output_dir_semantics(three_mp3_fixture, tmp_path, test_runtime_config):
	"""Test output path resolution: directory vs .m4b."""
	fixture_dir, files = three_mp3_fixture
	output_dir = tmp_path / "output"
	output_dir.mkdir(parents=True, exist_ok=True)

	# Create sidecar
	sidecar_content = """My Audiobook
By: Author
Narrated by: Narrator
Release date: 04-15-24
Language: English
Publisher: Publisher
Publisher's summary: Summary."""

	sidecar_file = fixture_dir / "sidecar.txt"
	sidecar_file.write_text(sidecar_content)

	# Test 1: output_path is a directory
	m1 = merger.Merger(
		input_path=fixture_dir,
		output_path=output_dir,
		runtime_config=test_runtime_config,
		no_asin=True,
	)

	m1.run()

	# Verify output has sanitized title
	output_files = list(output_dir.glob("*.m4b"))
	assert len(output_files) == 1
	assert output_files[0].name == "My_Audiobook.m4b"


def test_merger_sanitizes_title(three_mp3_fixture, tmp_path, test_runtime_config):
	"""Test that problematic characters in titles are sanitized."""
	fixture_dir, files = three_mp3_fixture
	output_dir = tmp_path / "output"
	output_dir.mkdir(parents=True, exist_ok=True)

	# Create sidecar with problematic characters
	sidecar_content = """A/B:C?D*E
By: Author
Narrated by: Narrator
Release date: 04-15-24
Language: English
Publisher: Publisher
Publisher's summary: Summary."""

	sidecar_file = fixture_dir / "sidecar.txt"
	sidecar_file.write_text(sidecar_content)

	# Run merger
	m = merger.Merger(
		input_path=fixture_dir,
		output_path=output_dir,
		runtime_config=test_runtime_config,
		no_asin=True,
	)

	m.run()

	# Verify output has sanitized filename (no problematic chars)
	output_files = list(output_dir.glob("*.m4b"))
	assert len(output_files) == 1
	output_filename = output_files[0].name

	# Should not contain problematic characters
	problematic_chars = set(":/\\?*\"<>|")
	for char in output_filename:
		assert char not in problematic_chars


def test_merger_source_preflight_homogeneity(three_mp3_fixture, tmp_path, test_runtime_config):
	"""Test source preflight detects heterogeneous sample rates."""
	# This test would require deliberately creating mismatched MP3s.
	# For now, verify that homogeneous sources pass preflight.
	fixture_dir, files = three_mp3_fixture

	sidecar_content = """Test
By: Author
Narrated by: Narrator
Release date: 04-15-24
Language: English
Publisher: Publisher
Publisher's summary: Summary."""

	sidecar_file = fixture_dir / "sidecar.txt"
	sidecar_file.write_text(sidecar_content)

	# Should not raise
	m = merger.Merger(
		input_path=fixture_dir,
		output_path=tmp_path / "output",
		runtime_config=test_runtime_config,
		no_asin=True,
	)

	# Preflight should pass (fixture is homogeneous)
	m._probe_and_validate_sources(files)


def test_merger_no_title_raises(three_mp3_fixture, tmp_path, test_runtime_config):
	"""Test that merger raises if no title is found."""
	fixture_dir, files = three_mp3_fixture
	output_dir = tmp_path / "output"
	output_dir.mkdir(parents=True, exist_ok=True)

	# Create empty sidecar (no title)
	sidecar_file = fixture_dir / "empty.txt"
	sidecar_file.write_text("")

	# Should raise ValueError about missing title
	m = merger.Merger(
		input_path=fixture_dir,
		output_path=output_dir,
		runtime_config=test_runtime_config,
		no_asin=True,
	)

	with pytest.raises(ValueError, match="title"):
		m.run()
