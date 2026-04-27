"""
Unit tests for cover_finder.

Tests locating cover images in priority order.
"""

import m4b_merge.cover_finder as cover_finder


def test_priority_1_cover_jpg(tmp_path):
	"""Priority 1: cover.jpg exists."""
	cover_jpg = tmp_path / "cover.jpg"
	cover_jpg.write_text("fake jpeg")

	result = cover_finder.find(tmp_path)

	assert result is not None
	assert result.path == cover_jpg
	assert result.needs_jpeg_conversion is False


def test_priority_1_cover_jpeg(tmp_path):
	"""Priority 1: cover.jpeg exists."""
	cover_jpeg = tmp_path / "cover.jpeg"
	cover_jpeg.write_text("fake jpeg")

	result = cover_finder.find(tmp_path)

	assert result is not None
	assert result.path == cover_jpeg
	assert result.needs_jpeg_conversion is False


def test_priority_2_folder_jpg(tmp_path):
	"""Priority 2: folder.jpg when no cover.jpg."""
	folder_jpg = tmp_path / "folder.jpg"
	folder_jpg.write_text("fake jpeg")

	result = cover_finder.find(tmp_path)

	assert result is not None
	assert result.path == folder_jpg
	assert result.needs_jpeg_conversion is False


def test_priority_1_over_priority_2(tmp_path):
	"""cover.jpg wins over folder.jpg."""
	cover_jpg = tmp_path / "cover.jpg"
	folder_jpg = tmp_path / "folder.jpg"
	cover_jpg.write_text("fake cover")
	folder_jpg.write_text("fake folder")

	result = cover_finder.find(tmp_path)

	assert result is not None
	assert result.path == cover_jpg


def test_priority_3_cover_png(tmp_path):
	"""Priority 3: cover.png when no .jpg present."""
	cover_png = tmp_path / "cover.png"
	cover_png.write_text("fake png")

	result = cover_finder.find(tmp_path)

	assert result is not None
	assert result.path == cover_png
	assert result.needs_jpeg_conversion is True


def test_priority_3_folder_png(tmp_path):
	"""Priority 3: folder.png when no .jpg present."""
	folder_png = tmp_path / "folder.png"
	folder_png.write_text("fake png")

	result = cover_finder.find(tmp_path)

	assert result is not None
	assert result.path == folder_png
	assert result.needs_jpeg_conversion is True


def test_priority_2_over_priority_3(tmp_path):
	"""folder.jpg wins over cover.png."""
	folder_jpg = tmp_path / "folder.jpg"
	cover_png = tmp_path / "cover.png"
	folder_jpg.write_text("fake folder")
	cover_png.write_text("fake png")

	result = cover_finder.find(tmp_path)

	assert result is not None
	assert result.path == folder_jpg
	assert result.needs_jpeg_conversion is False


def test_priority_4_single_ambiguous_jpg(tmp_path):
	"""Priority 4: single unrecognized .jpg is found."""
	ambiguous_jpg = tmp_path / "cover_art.jpg"
	ambiguous_jpg.write_text("fake jpeg")

	result = cover_finder.find(tmp_path)

	assert result is not None
	assert result.path == ambiguous_jpg
	assert result.needs_jpeg_conversion is False


def test_priority_4_single_ambiguous_png(tmp_path):
	"""Priority 4: single unrecognized .png is found with conversion flag."""
	ambiguous_png = tmp_path / "artwork.png"
	ambiguous_png.write_text("fake png")

	result = cover_finder.find(tmp_path)

	assert result is not None
	assert result.path == ambiguous_png
	assert result.needs_jpeg_conversion is True


def test_priority_4_rejected_multiple_images(tmp_path):
	"""Priority 4 rejects when multiple ambiguous images exist."""
	(tmp_path / "image1.jpg").write_text("fake1")
	(tmp_path / "image2.jpg").write_text("fake2")

	result = cover_finder.find(tmp_path)

	assert result is None


def test_priority_4_rejected_mixed_image_types(tmp_path):
	"""Multiple image files (jpg + png) with no well-known names -> None."""
	(tmp_path / "photo.jpg").write_text("fake jpg")
	(tmp_path / "artwork.png").write_text("fake png")

	result = cover_finder.find(tmp_path)

	assert result is None


def test_empty_directory(tmp_path):
	"""Empty directory returns None."""
	result = cover_finder.find(tmp_path)

	assert result is None


def test_directory_no_images(tmp_path):
	"""Directory with non-image files returns None."""
	(tmp_path / "file.txt").write_text("not an image")
	(tmp_path / "audio.mp3").write_text("not an image")

	result = cover_finder.find(tmp_path)

	assert result is None


def test_nonexistent_directory(tmp_path):
	"""Nonexistent directory returns None."""
	nonexistent = tmp_path / "does_not_exist"

	result = cover_finder.find(nonexistent)

	assert result is None


def test_case_insensitive_matching(tmp_path):
	"""Case-insensitive matching for well-known names."""
	# Create cover.JPG (uppercase)
	cover_upper = tmp_path / "cover.JPG"
	cover_upper.write_text("fake jpeg")

	result = cover_finder.find(tmp_path)

	assert result is not None
	assert result.path == cover_upper
	assert result.needs_jpeg_conversion is False


def test_case_insensitive_folder(tmp_path):
	"""Case-insensitive matching for folder.Jpeg."""
	folder_mixed = tmp_path / "Folder.Jpeg"
	folder_mixed.write_text("fake jpeg")

	result = cover_finder.find(tmp_path)

	assert result is not None
	assert result.path == folder_mixed
	assert result.needs_jpeg_conversion is False
