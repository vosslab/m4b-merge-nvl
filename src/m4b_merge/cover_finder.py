"""
Locate cover art in a directory.

Searches for cover images in priority order, returning a CoverHit with
the path and a flag indicating if JPEG conversion is needed.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CoverHit:
	"""Located cover image with optional conversion flag."""
	path: Path
	needs_jpeg_conversion: bool


def find(directory: Path) -> CoverHit | None:
	"""
	Find a cover image in the directory.

	Priority order:
	  1. cover.jpg / cover.jpeg (case-insensitive)
	  2. folder.jpg / folder.jpeg (case-insensitive)
	  3. cover.png / folder.png (case-insensitive, needs_jpeg_conversion=True)
	  4. exactly one .jpg/.jpeg/.png in directory (no other image files)
	  5. None

	Args:
		directory: Path to search.

	Returns:
		CoverHit with path and conversion flag, or None if not found.
	"""
	if not directory.exists() or not directory.is_dir():
		return None

	# Get all files in directory (case-insensitive comparison)
	# Note: On case-sensitive filesystems (Linux), if both COVER.JPG and cover.jpg exist,
	# the dict comprehension performs last-one-wins. This is acceptable behavior - the
	# pipeline will find whichever one is returned.
	files = {f.name.lower(): f for f in directory.iterdir() if f.is_file()}

	# 1. cover.jpg / cover.jpeg
	for name in ["cover.jpg", "cover.jpeg"]:
		for fname in files:
			if fname == name:
				return CoverHit(path=files[fname], needs_jpeg_conversion=False)

	# 2. folder.jpg / folder.jpeg
	for name in ["folder.jpg", "folder.jpeg"]:
		for fname in files:
			if fname == name:
				return CoverHit(path=files[fname], needs_jpeg_conversion=False)

	# 3. cover.png / folder.png
	for name in ["cover.png", "folder.png"]:
		for fname in files:
			if fname == name:
				return CoverHit(path=files[fname], needs_jpeg_conversion=True)

	# 4. exactly one image file (any .jpg/.jpeg/.png)
	image_extensions = {".jpg", ".jpeg", ".png"}
	image_files = [
		f for f in files.values()
		if f.suffix.lower() in image_extensions
	]

	if len(image_files) == 1:
		image_file = image_files[0]
		needs_conversion = image_file.suffix.lower() == ".png"
		return CoverHit(path=image_file, needs_jpeg_conversion=needs_conversion)

	# 5. None
	return None
