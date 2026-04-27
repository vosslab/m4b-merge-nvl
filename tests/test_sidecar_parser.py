"""
Unit tests for sidecar_parser.

Tests parsing of Audible-style .txt sidecar files.
"""

from pathlib import Path
import m4b_merge.sidecar_parser as sidecar_parser
import git_file_utils


def test_derek_cheung_fixture():
	"""Test parsing the Derek Cheung fixture."""
	repo_root = Path(git_file_utils.get_repo_root())
	fixture_path = (
		repo_root / "Derek_Cheung-Conquering_the_Electron"
		/ "Derek_Cheung_and_Eric_Brach-Conquering_the_Electron.txt"
	)

	result = sidecar_parser.parse(fixture_path)

	# Check that result has expected keys (specific assertions)
	assert "title" in result
	assert "authors" in result
	assert "narrators" in result
	assert "chapters" in result

	# Verify title
	assert result["title"] is not None
	assert "Conquering the Electron" in result["title"]

	# Verify authors
	assert result["authors"] == ["Derek Cheung", "Eric Brach"]

	# Verify narrators
	assert result["narrators"] == ["Eric Jason Martin"]

	# Verify release_date (converted to ISO format)
	assert result["release_date"] == "2020-03-01"

	# Verify language
	assert result["language"] == "English"

	# Verify publisher
	assert result["publisher"] == "Tantor Audio"

	# Verify chapters (should be empty list for this fixture)
	assert result["chapters"] == []

	# Verify cover_url (should be None)
	assert result["cover_url"] is None

	# Verify description (should contain summary content)
	assert result["description"] is not None
	assert "history" in result["description"].lower()
	assert len(result["description"]) > 50


def test_missing_file():
	"""Test that missing file raises FileNotFoundError."""
	missing_path = Path("/nonexistent/file.txt")
	try:
		sidecar_parser.parse(missing_path)
		assert False, "Should have raised FileNotFoundError"
	except FileNotFoundError:
		pass


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
