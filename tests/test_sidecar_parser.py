"""
Unit tests for sidecar_parser.

Tests parsing of Audible-style .txt sidecar files.
"""

from pathlib import Path

import pytest

import m4b_merge.sidecar_parser as sidecar_parser


# Inline sidecar text used for the Derek-Cheung style parser test below.
# Lifted verbatim from the original fixture so the test does not depend on
# an untracked .m4b directory shipping with the repo.
DEREK_SIDECAR_TEXT = (
	"Conquering the Electron: The Geniuses, Visionaries, Egomaniacs, "
	"and Scoundrels Who Built Our Electronic Age\n"
	"By: Derek Cheung, Eric Brach\n"
	"Narrated by: Eric Jason Martin\n"
	"Length: 14 hrs and 9 mins\n"
	"Release date: 03-01-20\n"
	"Language: English\n"
	"Publisher: Tantor Audio\n"
	"Publisher's summary:\n"
	"A history of electricity and electronics, from the discovery of "
	"magnetism to the modern semiconductor age. This book covers more than "
	"two centuries of scientific progress and the personalities behind the "
	"breakthroughs.\n"
)


def test_derek_cheung_fixture(tmp_path):
	"""
	Round-trip parser check on a Derek-Cheung style sidecar.

	Uses an inline copy of the sidecar text so the test runs without the
	untracked .m4b directory present.
	"""
	sidecar_file = tmp_path / "derek.txt"
	sidecar_file.write_text(DEREK_SIDECAR_TEXT)

	result = sidecar_parser.parse(sidecar_file)

	# Required keys present
	for key in ("title", "authors", "narrators", "chapters", "release_date"):
		assert key in result

	# Title round-trip
	assert "Conquering the Electron" in result["title"]

	# Authors and narrators round-trip from the "By:" / "Narrated by:" lines
	assert result["authors"] == ["Derek Cheung", "Eric Brach"]
	assert result["narrators"] == ["Eric Jason Martin"]

	# ISO normalization: "MM-DD-YY" -> "YYYY-MM-DD"
	assert result["release_date"] == "2020-03-01"

	# Description survives parsing
	assert result["description"] is not None
	assert "history" in result["description"].lower()


def test_missing_file():
	"""Missing file raises FileNotFoundError."""
	missing_path = Path("/nonexistent/file.txt")
	with pytest.raises(FileNotFoundError):
		sidecar_parser.parse(missing_path)


def test_minimal_sidecar(tmp_path):
	"""Test parsing a minimal sidecar with only title."""
	minimal_txt = tmp_path / "minimal.txt"
	minimal_txt.write_text("Test Title\n")

	result = sidecar_parser.parse(minimal_txt)

	assert result["title"] == "Test Title"
	assert result["authors"] is None
	assert result["narrators"] is None
	assert result["description"] is None
	assert result["chapters"] == []


def test_author_parsing(tmp_path):
	"""Test various author and narrator formats."""
	test_txt = tmp_path / "test.txt"
	test_txt.write_text(
		"My Book\n"
		"By: Alice and Bob\n"
		"Narrated by: Charlie, David, and Eve\n"
	)

	result = sidecar_parser.parse(test_txt)

	assert result["authors"] == ["Alice", "Bob"]
	assert result["narrators"] == ["Charlie", "David", "Eve"]


def test_sidecar_parser_crlf_line_endings(tmp_path):
	"""Test that CRLF line endings are handled correctly (Windows format)."""
	crlf_txt = tmp_path / "crlf.txt"
	content = "My Book\r\nBy: Alice, Bob\r\nNarrated by: Carol, Dave\r\nLength: 12 hours\r\n"
	crlf_txt.write_bytes(content.encode("utf-8"))

	result = sidecar_parser.parse(crlf_txt)

	# Should parse identically to LF version
	assert result["title"] == "My Book"
	assert result["authors"] == ["Alice", "Bob"]
	assert result["narrators"] == ["Carol", "Dave"]
	assert result["length"] == "12 hours"
