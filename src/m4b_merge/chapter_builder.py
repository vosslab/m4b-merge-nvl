"""
Chapter metadata builder for audiobook files.

Constructs ffmetadata-format chapter list from probe data, filenames,
and optional metadata/sidecar chapters.
"""

import pathlib

# Maximum duration (seconds) for a single chapter before silence-driven splitting
# is considered. Default is 5400 (90 minutes). This is set high enough to avoid
# splitting intentional long chapters (e.g., Derek Cheung fixture has chapters up
# to ~71 minutes that should remain single chapters), while still capturing
# genuinely multi-hour files that may benefit from silence-based splits.
MAX_CHAPTER_SECONDS = 5400

# Minimum duration (seconds) for a split chapter. If a silence-driven split would
# create a chapter shorter than this, the split is not applied. Default is 60.
MIN_CHAPTER_SECONDS = 60


def build(
	probe_results: list[dict],
	filenames: list[str],
	metadata: dict,
	sidecar: dict,
	silences_per_file: list[list[tuple[float, float]]] | None = None,
) -> str:
	"""
	Build ffmetadata text with chapter definitions.

	Pure function that generates ffmetadata-format chapter blocks.
	Chapters are sourced in priority order:
	1. metadata["chapters"] if non-empty
	2. sidecar["chapters"] if non-empty
	3. filenames + cumulative durations from probe_results (with optional
	   silence-driven splitting for files exceeding MAX_CHAPTER_SECONDS)

	Args:
		probe_results: List of dicts (one per source file) with
			"duration_seconds" key (float).
		filenames: List of source filenames (basenames).
		metadata: Normalized metadata dict with optional "chapters" key
			(list of dicts with "title" and "start_offset_ms").
		sidecar: Normalized sidecar dict with optional "chapters" key.
		silences_per_file: Optional list of silence interval lists, one per
			source file. Each element is a list of (start_seconds, end_seconds)
			tuples. Only used when falling back to filename-based chapters.
			If None, no silence-driven splitting is performed.

	Returns:
		ffmetadata text with ;FFMETADATA1 header and [CHAPTER] blocks.
	"""
	chapters = _resolve_chapters(
		probe_results,
		filenames,
		metadata,
		sidecar,
		silences_per_file
	)

	# Build ffmetadata text
	lines = [";FFMETADATA1"]

	for chapter in chapters:
		lines.append("[CHAPTER]")
		lines.append("TIMEBASE=1/1000")
		lines.append(f"START={chapter['start_ms']}")
		lines.append(f"END={chapter['end_ms']}")
		lines.append(f"title={chapter['title']}")

	return "\n".join(lines) + "\n"


def _resolve_chapters(
	probe_results: list[dict],
	filenames: list[str],
	metadata: dict,
	sidecar: dict,
	silences_per_file: list[list[tuple[float, float]]] | None = None,
) -> list[dict]:
	"""
	Resolve chapter list from priority sources.

	Returns list of dicts with keys: start_ms, end_ms, title.

	Args:
		probe_results: List of probe dicts with "duration_seconds".
		filenames: List of source filenames.
		metadata: Normalized metadata dict.
		sidecar: Normalized sidecar dict.
		silences_per_file: Optional list of silence intervals per file.

	Returns:
		List of chapter dicts in chronological order.
	"""
	# Priority 1: Audnex chapters (metadata)
	if metadata.get("chapters"):
		return _chapters_from_audnex(metadata["chapters"], probe_results)

	# Priority 2: Sidecar chapters
	if sidecar.get("chapters"):
		return _chapters_from_sidecar(sidecar["chapters"], probe_results)

	# Priority 3: Filenames + cumulative durations (with optional silence splits)
	return _chapters_from_filenames(filenames, probe_results, silences_per_file)


def _chapters_from_audnex(
	audnex_chapters: list[dict],
	probe_results: list[dict],
) -> list[dict]:
	"""
	Convert Audnex chapter list to internal format.

	Args:
		audnex_chapters: List of dicts with "title" and "start_offset_ms".
		probe_results: List of probe dicts (used to compute total duration).

	Returns:
		List of chapter dicts with start_ms, end_ms, title.
	"""
	total_duration_ms = int(
		sum(p["duration_seconds"] for p in probe_results) * 1000
	)

	chapters = []
	for idx, ch in enumerate(audnex_chapters):
		start_ms = int(ch["start_offset_ms"])
		# End is the start of the next chapter, or total duration if last
		end_ms = (
			int(audnex_chapters[idx + 1]["start_offset_ms"])
			if idx + 1 < len(audnex_chapters)
			else total_duration_ms
		)

		chapters.append({
			"start_ms": start_ms,
			"end_ms": end_ms,
			"title": ch["title"],
		})

	return chapters


def _chapters_from_sidecar(
	sidecar_chapters: list[dict],
	probe_results: list[dict],
) -> list[dict]:
	"""
	Convert sidecar chapter list to internal format.

	Args:
		sidecar_chapters: List of dicts with "title" and "start_offset_ms".
		probe_results: List of probe dicts (used to compute total duration).

	Returns:
		List of chapter dicts with start_ms, end_ms, title.
	"""
	total_duration_ms = int(
		sum(p["duration_seconds"] for p in probe_results) * 1000
	)

	chapters = []
	for idx, ch in enumerate(sidecar_chapters):
		start_ms = int(ch["start_offset_ms"])
		end_ms = (
			int(sidecar_chapters[idx + 1]["start_offset_ms"])
			if idx + 1 < len(sidecar_chapters)
			else total_duration_ms
		)

		chapters.append({
			"start_ms": start_ms,
			"end_ms": end_ms,
			"title": ch["title"],
		})

	return chapters


def _chapters_from_filenames(
	filenames: list[str],
	probe_results: list[dict],
	silences_per_file: list[list[tuple[float, float]]] | None = None,
) -> list[dict]:
	"""
	Build chapters from filenames and cumulative durations.

	Each file becomes one chapter; start offset is the cumulative duration
	of all preceding files. Title is the filename minus extension.

	If a file's duration exceeds MAX_CHAPTER_SECONDS and silence intervals
	are provided, the file is split at silence boundaries such that no
	resulting chapter is shorter than MIN_CHAPTER_SECONDS. Split chapters
	are titled with " - Part 2", " - Part 3", etc appended.

	Args:
		filenames: List of source filenames.
		probe_results: List of probe dicts with "duration_seconds".
		silences_per_file: Optional list of silence interval lists, one per file.
			Each element is a list of (start_seconds, end_seconds) tuples.

	Returns:
		List of chapter dicts with start_ms, end_ms, title.
	"""
	chapters = []
	cumulative_ms = 0
	total_duration_ms = int(
		sum(p["duration_seconds"] for p in probe_results) * 1000
	)

	for idx, (filename, probe) in enumerate(zip(filenames, probe_results)):
		duration_seconds = probe["duration_seconds"]
		base_title = pathlib.Path(filename).stem

		# Check if this file should be split based on duration and silences
		should_split = (
			duration_seconds > MAX_CHAPTER_SECONDS
			and silences_per_file is not None
			and idx < len(silences_per_file)
			and silences_per_file[idx]
		)

		if should_split:
			# Split this file at silence boundaries
			silences = silences_per_file[idx]
			file_chapters = _split_file_by_silences(
				base_title,
				duration_seconds,
				silences,
				cumulative_ms
			)
			chapters.extend(file_chapters)
			cumulative_ms += int(duration_seconds * 1000)
		else:
			# Single chapter for this file
			start_ms = cumulative_ms
			duration_ms = int(duration_seconds * 1000)
			cumulative_ms += duration_ms

			chapters.append({
				"start_ms": start_ms,
				"end_ms": cumulative_ms,
				"title": base_title,
			})

	# Ensure the last chapter's end equals total duration
	if chapters:
		chapters[-1]["end_ms"] = total_duration_ms

	return chapters


def _split_file_by_silences(
	base_title: str,
	duration_seconds: float,
	silences: list[tuple[float, float]],
	global_start_ms: int,
) -> list[dict]:
	"""
	Split a file at silence boundaries.

	Args:
		base_title: Original filename-derived title.
		duration_seconds: Total duration of the file in seconds.
		silences: List of (start_seconds, end_seconds) silence intervals.
		global_start_ms: Start time of this file in the global timeline (ms).

	Returns:
		List of chapter dicts. If splits would violate MIN_CHAPTER_SECONDS
		constraint, returns a single unsplit chapter instead.
	"""
	if not silences:
		# No silences to split on
		return [{
			"start_ms": global_start_ms,
			"end_ms": global_start_ms + int(duration_seconds * 1000),
			"title": base_title,
		}]

	# Find split points at silence midpoints
	# Only split if the resulting segments are at least MIN_CHAPTER_SECONDS long
	split_points = []
	for silence_start, silence_end in silences:
		midpoint = (silence_start + silence_end) / 2.0
		split_points.append(midpoint)

	# Validate splits: ensure no chapter would be shorter than MIN_CHAPTER_SECONDS
	split_points.sort()
	valid_splits = []
	prev_boundary = 0.0

	for split_point in split_points:
		potential_chapter_duration = split_point - prev_boundary
		if potential_chapter_duration >= MIN_CHAPTER_SECONDS:
			valid_splits.append(split_point)
			prev_boundary = split_point

	# Check final chapter
	final_duration = duration_seconds - prev_boundary
	if final_duration < MIN_CHAPTER_SECONDS:
		# Last split would create a chapter that's too short; discard it
		if valid_splits:
			valid_splits.pop()

	if not valid_splits:
		# No valid splits; return single unsplit chapter
		return [{
			"start_ms": global_start_ms,
			"end_ms": global_start_ms + int(duration_seconds * 1000),
			"title": base_title,
		}]

	# Build split chapters
	chapters = []
	prev_boundary = 0.0

	for part_num, split_point in enumerate(valid_splits, start=1):
		start_ms = global_start_ms + int(prev_boundary * 1000)
		end_ms = global_start_ms + int(split_point * 1000)

		if part_num == 1:
			title = base_title
		else:
			title = f"{base_title} - Part {part_num}"

		chapters.append({
			"start_ms": start_ms,
			"end_ms": end_ms,
			"title": title,
		})

		prev_boundary = split_point

	# Final chapter
	start_ms = global_start_ms + int(prev_boundary * 1000)
	end_ms = global_start_ms + int(duration_seconds * 1000)
	final_part_num = len(valid_splits) + 1

	# valid_splits is non-empty when this code is reached, so final_part_num >= 2
	title = f"{base_title} - Part {final_part_num}"

	chapters.append({
		"start_ms": start_ms,
		"end_ms": end_ms,
		"title": title,
	})

	return chapters
