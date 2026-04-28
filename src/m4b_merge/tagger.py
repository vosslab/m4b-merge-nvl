"""
Mutagen MP4 tagging for audiobook metadata and cover art.

Writes ID3-style tags to M4B files: title, artist, album, date, genre,
description, composer (narrator). Embeds cover art via MP4Cover.
"""

import pathlib
import mutagen.mp4


def write(m4b_path: pathlib.Path, metadata: dict, cover_path: pathlib.Path | None) -> None:
	"""
	Write metadata tags and optional cover art to M4B file.

	Idempotent: calling twice produces the same result (skips if value
	already matches). Uses direct dict access for required metadata keys;
	falls back to None/empty list for optional fields.

	Args:
		m4b_path: Path to the M4B file.
		metadata: Normalized metadata dict with keys:
			title, subtitle, authors, narrators, length, release_date,
			publisher, language, description, cover_url, chapters.
		cover_path: Path to cover image (JPEG assumed), or None.

	Raises:
		FileNotFoundError: if m4b_path does not exist.
		mutagen.mp4.MP4Error: if file cannot be parsed or written.
	"""
	if not m4b_path.exists():
		raise FileNotFoundError(f"M4B file not found: {m4b_path}")

	# Load the M4B
	mp4_file = mutagen.mp4.MP4(str(m4b_path))

	# Title: \xa9nam. Required key; direct access exposes missing data.
	title = metadata["title"]
	_set_atom(mp4_file, "\xa9nam", title)

	# Album: \xa9alb - set to title for audiobooks
	_set_atom(mp4_file, "\xa9alb", title)

	# Artist: \xa9ART - join authors list (may be None for filename-only metadata)
	authors = metadata["authors"]
	if authors:
		_set_atom(mp4_file, "\xa9ART", ", ".join(authors))

	# Release date: \xa9day (optional)
	if metadata["release_date"]:
		_set_atom(mp4_file, "\xa9day", metadata["release_date"])

	# Composer (narrator): \xa9wrt - join narrators list (optional)
	narrators = metadata["narrators"]
	if narrators:
		_set_atom(mp4_file, "\xa9wrt", ", ".join(narrators))

	# Description: desc (optional)
	if metadata["description"]:
		_set_atom(mp4_file, "desc", metadata["description"])

	# Cover art: covr - embed if cover_path provided and not already present
	if cover_path and cover_path.exists():
		_embed_cover(mp4_file, cover_path)

	# Write the file
	mp4_file.save()


def _set_atom(mp4_file: mutagen.mp4.MP4, atom_key: str, value: str) -> None:
	"""
	Set an atom value, skipping if already present and matches.

	Args:
		mp4_file: mutagen.mp4.MP4 instance.
		atom_key: Atom key (e.g., \xa9nam, desc).
		value: String value to set.
	"""
	if not value:
		return

	# Check if atom already exists and matches
	if atom_key in mp4_file:
		current_value = mp4_file[atom_key]
		# Extract string from mutagen's atom value format
		if isinstance(current_value, list) and current_value:
			current_str = str(current_value[0])
		else:
			current_str = str(current_value)

		if current_str == value:
			return  # Already set, skip

	# Set the atom
	mp4_file[atom_key] = [value]


def _embed_cover(mp4_file: mutagen.mp4.MP4, cover_path: pathlib.Path) -> None:
	"""
	Embed cover image as MP4Cover, only if not already present.

	Args:
		mp4_file: mutagen.mp4.MP4 instance.
		cover_path: Path to cover image.

	Raises:
		FileNotFoundError: if cover_path does not exist.
	"""
	if not cover_path.exists():
		raise FileNotFoundError(f"Cover file not found: {cover_path}")

	# Check if cover already embedded
	if "covr" in mp4_file and mp4_file["covr"]:
		return  # Already has cover, skip

	# Detect image format from file extension
	suffix = cover_path.suffix.lower()
	if suffix == ".png":
		image_format = mutagen.mp4.MP4Cover.FORMAT_PNG
	else:
		# Default to JPEG for .jpg, .jpeg, or unknown extensions
		image_format = mutagen.mp4.MP4Cover.FORMAT_JPEG

	# Read cover bytes and embed
	cover_bytes = cover_path.read_bytes()
	mp4_cover = mutagen.mp4.MP4Cover(
		cover_bytes,
		imageformat=image_format,
	)
	mp4_file["covr"] = [mp4_cover]
