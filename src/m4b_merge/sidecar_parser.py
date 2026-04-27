"""
Parse Audible-style sidecar .txt files.

Returns a normalized dict with all known keys, with values set to None (or []
for chapters) when not present.
"""

from pathlib import Path


def parse(path: Path) -> dict:
	"""
	Parse an Audible-style .txt sidecar file.

	Expected format:
	  - Title (first non-empty line)
	  - By: <authors>
	  - Narrated by: <narrators>
	  - Length: <duration>
	  - Release date: MM-DD-YY
	  - Language: <language>
	  - Publisher: <publisher>
	  - Publisher's summary: <description follows>

	Args:
		path: Path to the .txt file.

	Returns:
		Dict with fixed keys:
		{
			"title": str|None,
			"subtitle": None,
			"authors": list[str]|None,
			"narrators": list[str]|None,
			"length": str|None,
			"release_date": str|None (ISO YYYY-MM-DD),
			"publisher": str|None,
			"language": str|None,
			"description": str|None,
			"cover_url": None,
			"chapters": [],
		}

	Raises:
		FileNotFoundError: if path does not exist.
	"""
	if not path.exists():
		raise FileNotFoundError(f"Sidecar file not found: {path}")

	content = path.read_text(encoding="utf-8")
	lines = content.splitlines()

	# Initialize result dict with defaults
	result = {
		"title": None,
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

	# Track state
	in_summary = False
	summary_lines = []
	title_set = False

	for line in lines:
		stripped = line.strip()

		# Skip empty lines unless we're in summary
		if not stripped:
			if in_summary:
				summary_lines.append("")
			continue

		# Title: first non-empty line
		if not title_set:
			result["title"] = stripped
			title_set = True
			continue

		# By: authors
		if stripped.startswith("By:"):
			authors_str = stripped[3:].strip()
			# Split on comma and "and"
			authors = _split_authors(authors_str)
			result["authors"] = authors
			continue

		# Narrated by: narrators
		if stripped.startswith("Narrated by:"):
			narrators_str = stripped[12:].strip()
			narrators = _split_narrators(narrators_str)
			result["narrators"] = narrators
			continue

		# Length: duration
		if stripped.startswith("Length:"):
			length_str = stripped[7:].strip()
			result["length"] = length_str
			continue

		# Release date: MM-DD-YY format -> YYYY-MM-DD
		if stripped.startswith("Release date:"):
			date_str = stripped[13:].strip()
			result["release_date"] = _parse_date(date_str)
			continue

		# Language: language
		if stripped.startswith("Language:"):
			language_str = stripped[9:].strip()
			result["language"] = language_str
			continue

		# Publisher: publisher
		if stripped.startswith("Publisher:"):
			publisher_str = stripped[10:].strip()
			result["publisher"] = publisher_str
			continue

		# Publisher's summary: start of description
		if stripped.startswith("Publisher's summary"):
			in_summary = True
			continue

		# After summary marker, accumulate lines
		if in_summary:
			summary_lines.append(stripped)

	# Join description
	if summary_lines:
		description = "\n".join(summary_lines).strip()
		if description:
			result["description"] = description

	return result


def _split_authors(authors_str: str) -> list[str]:
	"""
	Split author string on comma and 'and'.

	Examples:
	  "Derek Cheung, Eric Brach" -> ["Derek Cheung", "Eric Brach"]
	  "Alice and Bob" -> ["Alice", "Bob"]
	  "Alice, Bob, and Charlie" -> ["Alice", "Bob", "Charlie"]
	"""
	# Replace " and " with ", "
	normalized = authors_str.replace(" and ", ", ")
	# Split on ", "
	parts = [p.strip() for p in normalized.split(",")]
	return [p for p in parts if p]


def _split_narrators(narrators_str: str) -> list[str]:
	"""
	Split narrator string on comma and 'and'.

	(Same logic as authors.)
	"""
	normalized = narrators_str.replace(" and ", ", ")
	parts = [p.strip() for p in normalized.split(",")]
	return [p for p in parts if p]


def _parse_date(date_str: str) -> str | None:
	"""
	Parse date in MM-DD-YY format and return ISO YYYY-MM-DD.

	Examples:
	  "03-01-20" -> "2020-03-01"
	  "12-25-19" -> "2019-12-25"
	"""
	parts = date_str.split("-")
	if len(parts) != 3:
		return None

	month, day, year = parts
	# Convert YY to YYYY (assume 20YY)
	full_year = f"20{year}"
	return f"{full_year}-{month}-{day}"
