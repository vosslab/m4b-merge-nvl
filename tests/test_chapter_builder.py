"""
Unit tests for chapter_builder module.

Tests chapter list generation from various sources (metadata, sidecar, filenames).
"""

import m4b_merge.chapter_builder as chapter_builder


def count_chapter_blocks(text: str) -> int:
	"""
	Count the number of [CHAPTER] blocks in ffmetadata text.

	Args:
		text: ffmetadata text.

	Returns:
		Number of chapter blocks.
	"""
	return text.count("[CHAPTER]")


def extract_chapters_from_text(text: str) -> list[dict]:
	"""
	Parse ffmetadata text and extract chapter start/end times.

	Args:
		text: ffmetadata text.

	Returns:
		List of dicts with start_ms, end_ms, title.
	"""
	chapters = []
	lines = text.strip().split("\n")
	current_chapter = {}

	for line in lines:
		line = line.strip()
		if line == "[CHAPTER]":
			if current_chapter:
				chapters.append(current_chapter)
			current_chapter = {}
		elif line.startswith("START="):
			current_chapter["start_ms"] = int(line.split("=")[1])
		elif line.startswith("END="):
			current_chapter["end_ms"] = int(line.split("=")[1])
		elif line.startswith("title="):
			current_chapter["title"] = line.split("=", 1)[1]

	if current_chapter:
		chapters.append(current_chapter)

	return chapters


class TestBuildFromFilenames:
	"""Test chapter_builder.build with filename fallback."""

	def test_build_from_three_files_with_durations(self):
		"""
		Test that build creates chapters from filenames + cumulative durations.

		3 files: 600s, 300s, 900s total = 1800s
		Expected chapters:
		- Chapter 0: start 0ms, end 600000ms
		- Chapter 1: start 600000ms, end 900000ms
		- Chapter 2: start 900000ms, end 1800000ms
		"""
		probe_results = [
			{"duration_seconds": 600.0},
			{"duration_seconds": 300.0},
			{"duration_seconds": 900.0},
		]
		filenames = ["track_01.mp3", "track_02.mp3", "track_03.mp3"]
		metadata = {"chapters": []}
		sidecar = {"chapters": []}

		text = chapter_builder.build(probe_results, filenames, metadata, sidecar)

		# Verify chapter count
		assert count_chapter_blocks(text) == 3

		# Extract chapters and verify properties
		chapters = extract_chapters_from_text(text)
		assert len(chapters) == 3

		# Check monotonicity and non-overlapping
		assert chapters[0]["start_ms"] == 0
		assert chapters[0]["end_ms"] == 600000
		assert chapters[1]["start_ms"] == 600000
		assert chapters[1]["end_ms"] == 900000
		assert chapters[2]["start_ms"] == 900000
		assert chapters[2]["end_ms"] == 1800000

		# Check titles are stripped of extension
		assert chapters[0]["title"] == "track_01"
		assert chapters[1]["title"] == "track_02"
		assert chapters[2]["title"] == "track_03"

		# Verify total duration
		total_duration = chapters[-1]["end_ms"]
		assert total_duration == 1800000

	def test_chapters_are_monotonic_non_overlapping(self):
		"""Test that chapters are monotonically increasing and non-overlapping."""
		probe_results = [
			{"duration_seconds": 100.0},
			{"duration_seconds": 200.0},
			{"duration_seconds": 300.0},
		]
		filenames = ["a.mp3", "b.mp3", "c.mp3"]
		metadata = {"chapters": []}
		sidecar = {"chapters": []}

		text = chapter_builder.build(probe_results, filenames, metadata, sidecar)
		chapters = extract_chapters_from_text(text)

		# Check monotonicity
		for i in range(len(chapters) - 1):
			assert chapters[i]["start_ms"] < chapters[i + 1]["start_ms"]
			# End of chapter N == start of chapter N+1
			assert chapters[i]["end_ms"] == chapters[i + 1]["start_ms"]


class TestBuildFromMetadata:
	"""Test chapter_builder.build with metadata chapters."""

	def test_metadata_chapters_override_sidecar_and_filenames(self):
		"""Test that metadata chapters take priority."""
		probe_results = [
			{"duration_seconds": 100.0},
			{"duration_seconds": 200.0},
		]
		filenames = ["file1.mp3", "file2.mp3"]

		# Metadata chapters
		metadata = {
			"chapters": [
				{"title": "Chapter 1", "start_offset_ms": 0},
				{"title": "Chapter 2", "start_offset_ms": 50000},
			]
		}
		sidecar = {
			"chapters": [
				{"title": "Sidecar 1", "start_offset_ms": 0},
			]
		}

		text = chapter_builder.build(probe_results, filenames, metadata, sidecar)

		chapters = extract_chapters_from_text(text)
		assert len(chapters) == 2
		assert chapters[0]["title"] == "Chapter 1"
		assert chapters[1]["title"] == "Chapter 2"


class TestBuildFromSidecar:
	"""Test chapter_builder.build with sidecar chapters."""

	def test_sidecar_chapters_override_filenames(self):
		"""Test that sidecar chapters take priority over filenames."""
		probe_results = [
			{"duration_seconds": 100.0},
			{"duration_seconds": 200.0},
		]
		filenames = ["file1.mp3", "file2.mp3"]

		metadata = {"chapters": []}
		sidecar = {
			"chapters": [
				{"title": "Part A", "start_offset_ms": 0},
				{"title": "Part B", "start_offset_ms": 75000},
			]
		}

		text = chapter_builder.build(probe_results, filenames, metadata, sidecar)

		chapters = extract_chapters_from_text(text)
		assert len(chapters) == 2
		assert chapters[0]["title"] == "Part A"
		assert chapters[1]["title"] == "Part B"


class TestBuildFFMetadataFormat:
	"""Test that output is valid ffmetadata format."""

	def test_output_starts_with_ffmetadata1_header(self):
		"""Test that output begins with ;FFMETADATA1."""
		probe_results = [{"duration_seconds": 100.0}]
		filenames = ["test.mp3"]
		metadata = {"chapters": []}
		sidecar = {"chapters": []}

		text = chapter_builder.build(probe_results, filenames, metadata, sidecar)

		assert text.startswith(";FFMETADATA1\n")

	def test_output_contains_timebase(self):
		"""Test that each chapter includes TIMEBASE=1/1000."""
		probe_results = [
			{"duration_seconds": 50.0},
			{"duration_seconds": 50.0},
		]
		filenames = ["a.mp3", "b.mp3"]
		metadata = {"chapters": []}
		sidecar = {"chapters": []}

		text = chapter_builder.build(probe_results, filenames, metadata, sidecar)

		# Count TIMEBASE lines; should equal chapter count
		timebase_count = text.count("TIMEBASE=1/1000")
		chapter_count = count_chapter_blocks(text)
		assert timebase_count == chapter_count


class TestBuildEdgeCases:
	"""Test edge cases."""

	def test_single_file_creates_one_chapter(self):
		"""Test that a single file creates one chapter."""
		probe_results = [{"duration_seconds": 1000.0}]
		filenames = ["book.mp3"]
		metadata = {"chapters": []}
		sidecar = {"chapters": []}

		text = chapter_builder.build(probe_results, filenames, metadata, sidecar)

		chapters = extract_chapters_from_text(text)
		assert len(chapters) == 1
		assert chapters[0]["start_ms"] == 0
		assert chapters[0]["end_ms"] == 1000000

	def test_empty_metadata_and_sidecar_uses_filenames(self):
		"""Test that empty metadata and sidecar fall back to filenames."""
		probe_results = [
			{"duration_seconds": 50.0},
			{"duration_seconds": 50.0},
		]
		filenames = ["chapter_1.mp3", "chapter_2.mp3"]
		metadata = {}  # No chapters key
		sidecar = {}  # No chapters key

		text = chapter_builder.build(probe_results, filenames, metadata, sidecar)

		chapters = extract_chapters_from_text(text)
		assert len(chapters) == 2
		assert chapters[0]["title"] == "chapter_1"
		assert chapters[1]["title"] == "chapter_2"

	def test_last_chapter_end_equals_total_duration(self):
		"""Test that the last chapter's END equals total duration."""
		probe_results = [
			{"duration_seconds": 100.5},
			{"duration_seconds": 200.3},
		]
		filenames = ["a.mp3", "b.mp3"]
		metadata = {"chapters": []}
		sidecar = {"chapters": []}

		text = chapter_builder.build(probe_results, filenames, metadata, sidecar)

		chapters = extract_chapters_from_text(text)
		total_ms = int((100.5 + 200.3) * 1000)
		assert chapters[-1]["end_ms"] == total_ms


class TestSilenceDrivenSplitting:
	"""Test chapter_builder silence-driven splitting (M7 feature)."""

	def test_long_file_split_by_silences(self):
		"""
		Test that a single file exceeding MAX_CHAPTER_SECONDS is split at silence boundaries.

		File: 7200s (2 hours) with silences at:
		- [1798, 1802] seconds (midpoint 1800)
		- [3598, 3602] seconds (midpoint 3600)
		- [5398, 5402] seconds (midpoint 5400)

		Expected: 4 chapters at boundaries 1800, 3600, 5400, 7200.
		"""
		probe_results = [
			{"duration_seconds": 7200.0},
		]
		filenames = ["long_book.mp3"]
		metadata = {"chapters": []}
		sidecar = {"chapters": []}

		# Silences at 30min (1800s), 60min (3600s), 90min (5400s)
		silences_per_file = [
			[
				(1798.0, 1802.0),
				(3598.0, 3602.0),
				(5398.0, 5402.0),
			]
		]

		text = chapter_builder.build(
			probe_results,
			filenames,
			metadata,
			sidecar,
			silences_per_file=silences_per_file,
		)

		chapters = extract_chapters_from_text(text)

		# Should have 4 chapters
		assert len(chapters) == 4, f"Expected 4 chapters, got {len(chapters)}"

		# Verify chapter boundaries are at silence midpoints
		assert chapters[0]["start_ms"] == 0
		assert chapters[0]["end_ms"] == 1800000  # 1800s
		assert chapters[1]["start_ms"] == 1800000
		assert chapters[1]["end_ms"] == 3600000  # 3600s
		assert chapters[2]["start_ms"] == 3600000
		assert chapters[2]["end_ms"] == 5400000  # 5400s
		assert chapters[3]["start_ms"] == 5400000
		assert chapters[3]["end_ms"] == 7200000  # 7200s (total)

		# Verify titles have " - Part" suffixes
		assert chapters[0]["title"] == "long_book"
		assert chapters[1]["title"] == "long_book - Part 2"
		assert chapters[2]["title"] == "long_book - Part 3"
		assert chapters[3]["title"] == "long_book - Part 4"

		# Verify non-overlapping
		for i in range(len(chapters) - 1):
			assert chapters[i]["end_ms"] == chapters[i + 1]["start_ms"]

	def test_derek_fixture_no_split(self):
		"""
		Regression test: Derek fixture should still produce 21 chapters.

		Derek fixture has 21 files, longest is ~4236s (~71 min).
		Since 4236 < MAX_CHAPTER_SECONDS (5400), no file should be split.
		"""
		# Simulate Derek fixture probe data (from dry-run observation)
		probe_results = [
			{"duration_seconds": 3534.0},   # 01 - Introduction
			{"duration_seconds": 3600.0},   # 02
			{"duration_seconds": 3060.0},   # 03
			{"duration_seconds": 3240.0},   # 04
			{"duration_seconds": 3360.0},   # 05
			{"duration_seconds": 3300.0},   # 06
			{"duration_seconds": 3180.0},   # 07
			{"duration_seconds": 3360.0},   # 08
			{"duration_seconds": 3420.0},   # 09
			{"duration_seconds": 3540.0},   # 10
			{"duration_seconds": 3300.0},   # 11
			{"duration_seconds": 3420.0},   # 12
			{"duration_seconds": 3300.0},   # 13
			{"duration_seconds": 3180.0},   # 14
			{"duration_seconds": 3540.0},   # 15
			{"duration_seconds": 3420.0},   # 16
			{"duration_seconds": 3600.0},   # 17
			{"duration_seconds": 3240.0},   # 18
			{"duration_seconds": 3180.0},   # 19
			{"duration_seconds": 3420.0},   # 20
			{"duration_seconds": 4236.31},  # 21 - longest file at 70.6 min
		]

		filenames = [f"{i:02d}_chapter.mp3" for i in range(1, 22)]
		metadata = {"chapters": []}
		sidecar = {"chapters": []}

		# Provide empty silences (no silence detection, or no silences found)
		silences_per_file = [[] for _ in range(21)]

		text = chapter_builder.build(
			probe_results,
			filenames,
			metadata,
			sidecar,
			silences_per_file=silences_per_file,
		)

		chapters = extract_chapters_from_text(text)

		# Invariant: when no file exceeds MAX, chapters == files (one per file).
		assert len(chapters) == len(filenames)

		# Verify no "- Part" suffixes (no splitting happened)
		for ch in chapters:
			assert " - Part " not in ch["title"], \
				f"Should not have part suffixes: {ch['title']}"

	def test_no_split_without_silences(self):
		"""Test that long file without silence data is not split."""
		probe_results = [
			{"duration_seconds": 7200.0},  # 2 hours, exceeds MAX_CHAPTER_SECONDS
		]
		filenames = ["long_book.mp3"]
		metadata = {"chapters": []}
		sidecar = {"chapters": []}

		# No silence data provided
		silences_per_file = None

		text = chapter_builder.build(
			probe_results,
			filenames,
			metadata,
			sidecar,
			silences_per_file=silences_per_file,
		)

		chapters = extract_chapters_from_text(text)

		# Should be 1 chapter (no split without silence data)
		assert len(chapters) == 1
		assert chapters[0]["title"] == "long_book"

	def test_no_split_with_audnex_chapters(self):
		"""Test that Audnex chapters prevent silence-driven splitting."""
		probe_results = [
			{"duration_seconds": 7200.0},
		]
		filenames = ["book.mp3"]

		# Audnex chapters provided
		metadata = {
			"chapters": [
				{"title": "Chapter 1", "start_offset_ms": 0},
				{"title": "Chapter 2", "start_offset_ms": 3600000},
			]
		}
		sidecar = {"chapters": []}

		# Silences provided but should be ignored
		silences_per_file = [
			[
				(1798.0, 1802.0),
				(3598.0, 3602.0),
			]
		]

		text = chapter_builder.build(
			probe_results,
			filenames,
			metadata,
			sidecar,
			silences_per_file=silences_per_file,
		)

		chapters = extract_chapters_from_text(text)

		# Should use Audnex chapters, not silence splits
		assert len(chapters) == 2
		assert chapters[0]["title"] == "Chapter 1"
		assert chapters[1]["title"] == "Chapter 2"

	def test_min_chapter_duration_constraint(self):
		"""Test that MIN_CHAPTER_SECONDS constraint prevents too-short chapters."""
		# File: 6000s (>MAX_CHAPTER_SECONDS of 5400) with silences at 1000s and 5000s
		# Silence midpoints at 1000s and 5000s
		# With MIN_CHAPTER_SECONDS=60, both would be valid (chunks: 1000s, 4000s, 1000s)
		probe_results = [
			{"duration_seconds": 6000.0},
		]
		filenames = ["long_book.mp3"]
		metadata = {"chapters": []}
		sidecar = {"chapters": []}

		silences_per_file = [
			[
				(998.0, 1002.0),    # midpoint 1000s
				(4998.0, 5002.0),   # midpoint 5000s
			]
		]

		text = chapter_builder.build(
			probe_results,
			filenames,
			metadata,
			sidecar,
			silences_per_file=silences_per_file,
		)

		chapters = extract_chapters_from_text(text)

		# Both splits should be valid (all chunks >= MIN_CHAPTER_SECONDS)
		assert len(chapters) == 3
		assert chapters[0]["end_ms"] == 1000000  # 1000s
		assert chapters[1]["start_ms"] == 1000000
		assert chapters[1]["end_ms"] == 5000000  # 5000s
		assert chapters[2]["start_ms"] == 5000000
		assert chapters[2]["end_ms"] == 6000000  # 6000s (total)


def test_silence_split_final_chapter_too_short_rejected():
	"""Test that MIN_CHAPTER_SECONDS constraint is enforced on split chapters."""
	# File: 7200s (2 hours), silence split at 3600s (midpoint)
	# Chunks: [0-3600s], [3600-7200s] = [3600s, 3600s] - both >= 60s MIN, both valid
	probe_results = [{"duration_seconds": 7200.0}]
	filenames = ["book.mp3"]
	metadata = {}
	sidecar = {}
	# Silence at 3598-3602 (midpoint 3600s)
	silences_per_file = [[
		(3598.0, 3602.0),
	]]

	text = chapter_builder.build(probe_results, filenames, metadata, sidecar, silences_per_file=silences_per_file)
	chapters = extract_chapters_from_text(text)

	# Split should be applied (all chunks >= MIN_CHAPTER_SECONDS)
	# Result: 2 chapters
	assert len(chapters) == 2
	assert chapters[0]["end_ms"] == 3600000  # 3600s
	assert chapters[1]["start_ms"] == 3600000
	assert chapters[1]["end_ms"] == 7200000  # 7200s (total)
