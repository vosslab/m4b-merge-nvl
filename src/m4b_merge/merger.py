"""
Orchestrator for the M4B merge pipeline.

Coordinates the full pipeline: input classification, metadata resolution,
cover discovery, source preflight, encoding, concatenation, chapter building,
remuxing, tagging, and cleanup.
"""

import time
import pathlib
import shutil
import logging
import subprocess

import requests

import m4b_merge.audible_helper as audible_helper
import m4b_merge.sidecar_parser as sidecar_parser
import m4b_merge.cover_finder as cover_finder
import m4b_merge.ffmpeg_runner as ffmpeg_runner
import m4b_merge.chapter_builder as chapter_builder
import m4b_merge.silence_detect as silence_detect
import m4b_merge.tagger as tagger


class SourcePreflightError(RuntimeError):
	"""
	Raised when source files have heterogeneous properties.

	Attributes:
		message: Detailed error description with per-file diff.
	"""
	pass


def _sanitize_title(title: str) -> str:
	"""
	Sanitize title for use as filename.

	Replaces problematic characters with hyphens.

	Args:
		title: Original title string.

	Returns:
		Sanitized filename-safe string.
	"""
	if not title:
		return "audiobook"

	# Replace problematic characters with hyphen, then collapse whitespace
	# runs into single underscores so the resulting filename is shell-safe
	# and free of spaces.
	problematic_chars = set(":/\\?*\"<>|")
	result = ""
	for char in title:
		if char in problematic_chars:
			result += "-"
		else:
			result += char

	# Clean up consecutive hyphens
	while "--" in result:
		result = result.replace("--", "-")

	# Convert any whitespace runs to single underscores
	result = "_".join(result.split())

	# Strip leading/trailing hyphens or underscores
	result = result.strip("-_")

	return result if result else "audiobook"


def _select_quality_args(runtime_config, probe_results: list[dict]) -> list[str] | None:
	"""
	Pick AAC encoder quality args based on RuntimeConfig and source probes.

	Priority:
	1. If runtime_config.target_bitrate_kbps is set (user-supplied), use it
	   directly: ["-b:a", "<N>k"].
	2. Otherwise auto-scale: take the maximum bitrate across source files,
	   round to the nearest 16 kbps, clamp to [32, 320] kbps.
	3. If no probe reports a bitrate, return None so the caller falls back
	   to runtime_config.quality_args (the static default).

	Args:
		runtime_config: RuntimeConfig.
		probe_results: List of probe dicts (from ffmpeg_runner.probe).

	Returns:
		List of ffmpeg quality flags, or None to use the default.
	"""
	if runtime_config.target_bitrate_kbps is not None:
		return ["-b:a", f"{runtime_config.target_bitrate_kbps}k"]

	bitrates_kbps = []
	for probe in probe_results:
		bps = probe.get("bitrate_bps")
		if bps:
			bitrates_kbps.append(bps / 1000.0)

	if not bitrates_kbps:
		return None

	# Round max bitrate to nearest 16 kbps step, clamp to [32, 320]
	target_kbps = round(max(bitrates_kbps) / 16) * 16
	target_kbps = max(32, min(320, target_kbps))
	return ["-b:a", f"{target_kbps}k"]


class Merger:
	"""Orchestrate the M4B merge pipeline."""

	def __init__(
		self,
		input_path: pathlib.Path,
		output_path: pathlib.Path,
		runtime_config,
		no_asin: bool,
		asin: str | None = None,
	):
		"""
		Initialize Merger.

		Args:
			input_path: Input directory or file.
			output_path: Output directory or .m4b file path.
			runtime_config: RuntimeConfig with binaries and options.
			no_asin: If True, skip Audnex lookup.
			asin: Audible ASIN, or None to skip.
		"""
		self.input_path = pathlib.Path(input_path)
		self.output_path = pathlib.Path(output_path)
		self.runtime_config = runtime_config
		self.no_asin = no_asin
		self.asin = asin

	def run(self) -> None:
		"""
		Execute the merge pipeline.

		Steps:
		1. Classify input (directory or file).
		2. Resolve metadata (Audnex -> sidecar -> filenames).
		3. Resolve cover (finder -> Audnex URL -> none).
		4. Source homogeneity preflight.
		5. [Dry-run branch: print report, return].
		6. Encode each MP3 to M4A.
		7. Concatenate with preflight.
		8. Build chapters.
		9. Remux with metadata.
		10. Tagger pass.
		11. Cleanup.

		Raises:
			ValueError: if metadata resolution fails.
			SourcePreflightError: if sources are heterogeneous.
			subprocess.CalledProcessError: if ffmpeg operations fail.
		"""
		run_start = time.monotonic()

		# Step 1: Classify input
		input_dir = self.input_path
		if not input_dir.is_dir():
			raise ValueError(f"Input must be a directory (for now): {self.input_path}")

		# Collect MP3 files in input directory, sorted by filename
		source_files = sorted([
			f for f in input_dir.iterdir()
			if f.is_file() and f.suffix.lower() == ".mp3"
		])

		if not source_files:
			raise ValueError(f"No MP3 files found in {input_dir}")

		print(f"[1/8] Scanning input: found {len(source_files)} MP3 file(s) in {input_dir.name}")

		# Step 2: Resolve metadata
		print("[2/8] Resolving metadata (Audnex/sidecar/filenames)...")
		metadata = self._resolve_metadata(input_dir)
		if not metadata["title"]:
			raise ValueError(
				"No title found in metadata. "
				"Provide via sidecar.txt or Audnex ASIN."
			)
		print(f"      Title: {metadata['title']}")
		if metadata.get("authors"):
			print(f"      Authors: {', '.join(metadata['authors'])}")
		if metadata.get("narrators"):
			print(f"      Narrators: {', '.join(metadata['narrators'])}")

		# Step 3: Resolve cover
		print("[3/8] Locating cover image...")
		cover_hit = None
		cover_path = None
		cover_hit = cover_finder.find(input_dir)

		if cover_hit:
			cover_path = cover_hit.path
			print(f"      Cover: {cover_path.name}")
		elif metadata.get("cover_url"):
			# TODO: Download cover from metadata["cover_url"] in future
			logging.warning("Cover URL present but downloading not yet implemented")
			print("      Cover: (none found, placeholder will be used)")
		else:
			print("      Cover: (none found, placeholder will be used)")

		# Step 4: Source homogeneity preflight
		print("[4/8] Probing source files and verifying homogeneity...")
		probe_results_src = self._probe_and_validate_sources(source_files)
		total_dur = sum(p["duration_seconds"] for p in probe_results_src)
		print(f"      Total source duration: {total_dur:.1f}s ({total_dur/3600:.2f}h)")

		# Cache sidecar result to avoid re-parsing (HIGH-06)
		sidecar = self._get_sidecar(input_dir)

		# Step 4b: Detect silences for potential chapter splitting
		# Only if: no Audnex chapters AND no sidecar chapters AND some file > MAX_CHAPTER_SECONDS
		silences_per_file = None
		files_needing_silence_detection = []
		if (
			not metadata.get("chapters")
			and not sidecar.get("chapters")
		):
			for idx, probe in enumerate(probe_results_src):
				if probe["duration_seconds"] > chapter_builder.MAX_CHAPTER_SECONDS:
					files_needing_silence_detection.append(idx)

		if files_needing_silence_detection:
			if not self.runtime_config.dry_run:
				# Run silence detection on long files
				silences_per_file = [None] * len(source_files)
				for idx in files_needing_silence_detection:
					src_file = source_files[idx]
					silences_per_file[idx] = silence_detect.detect(
						str(src_file), self.runtime_config
					)

		# Choose target encoder quality args (auto-scaled from sources or
		# user-supplied via --bitrate). None means "use runtime defaults".
		selected_quality_args = _select_quality_args(
			self.runtime_config, probe_results_src
		)

		# Step 5: Dry-run branch
		if self.runtime_config.dry_run:
			self._print_dry_run_report(
				source_files, metadata, cover_path, cover_hit,
				files_needing_silence_detection,
				selected_quality_args=selected_quality_args,
				probe_results=probe_results_src,
			)
			return

		# Create temp directory only after dry-run check (CRIT-01: dry-run must not create files)
		self.runtime_config.tmp_dir.mkdir(parents=True, exist_ok=True)

		# Step 6: Encode each MP3 to M4A
		effective_quality_args = (
			selected_quality_args
			if selected_quality_args is not None
			else self.runtime_config.quality_args
		)
		print(f"[5/8] Encoding {len(source_files)} file(s) to AAC ({self.runtime_config.aac_encoder} {' '.join(effective_quality_args)})...")
		encoded_dir = self.runtime_config.tmp_dir / "encoded"
		encoded_dir.mkdir(parents=True, exist_ok=True)

		encoded_files = []
		encode_start = time.monotonic()
		for idx, src_file in enumerate(source_files):
			step_start = time.monotonic()
			dst_file = encoded_dir / f"{idx:03d}.m4a"
			src_dur = probe_results_src[idx]["duration_seconds"]
			print(f"      [{idx+1:>2}/{len(source_files)}] {src_file.name} ({src_dur:.1f}s)", end="", flush=True)
			ffmpeg_runner.encode_to_m4a(
				src_file, dst_file, self.runtime_config,
				quality_args=selected_quality_args,
			)
			encoded_files.append(dst_file)
			elapsed = time.monotonic() - step_start
			print(f" -> {elapsed:.1f}s ({src_dur/elapsed:.0f}x realtime)")
		encode_total = time.monotonic() - encode_start
		print(f"      Encoded in {encode_total:.1f}s total ({total_dur/encode_total:.0f}x realtime)")

		# Step 7: Concatenate with preflight
		print("[6/8] Concatenating encoded files...")
		concat_start = time.monotonic()
		merged_file = self.runtime_config.tmp_dir / "merged.tmp.m4a"
		ffmpeg_runner.concat(
			encoded_files,
			merged_file,
			self.runtime_config,
			preflight=True,
		)
		print(f"      Concatenated in {time.monotonic() - concat_start:.1f}s")

		# Step 8: Build chapters
		print("[7/8] Building chapters and remuxing with cover + metadata...")
		probe_results = [
			ffmpeg_runner.probe(f, self.runtime_config) for f in encoded_files
		]
		filenames = [f.name for f in source_files]

		ffmetadata_text = chapter_builder.build(
			probe_results,
			filenames,
			metadata,
			sidecar,
			silences_per_file=silences_per_file,
		)

		ffmetadata_file = self.runtime_config.tmp_dir / "ffmetadata.txt"
		ffmetadata_file.write_text(ffmetadata_text)

		# Step 9: Remux with metadata
		final_m4b = self._resolve_output_path(metadata["title"])
		final_m4b.parent.mkdir(parents=True, exist_ok=True)

		if cover_path:
			ffmpeg_runner.remux_with_metadata(
				merged_file,
				cover_path,
				cover_hit.needs_jpeg_conversion if cover_hit else False,
				ffmetadata_file,
				final_m4b,
				self.runtime_config,
			)
		else:
			# Remux without cover: create a silent 1-pixel image as placeholder
			temp_cover = self._create_silent_cover()
			ffmpeg_runner.remux_with_metadata(
				merged_file,
				temp_cover,
				False,
				ffmetadata_file,
				final_m4b,
				self.runtime_config,
			)

		# Step 10: Tagger pass
		print("[8/8] Writing MP4 tags...")
		tagger.write(final_m4b, metadata, cover_path)

		# Step 11: Cleanup
		shutil.rmtree(self.runtime_config.tmp_dir, ignore_errors=True)

		size_mb = final_m4b.stat().st_size / (1024 * 1024)
		total_elapsed = time.monotonic() - run_start
		print()
		print(f"Done: {final_m4b}")
		print(f"      {size_mb:.1f} MB, {total_dur/3600:.2f}h audio, encoded in {total_elapsed:.1f}s ({total_dur/total_elapsed:.0f}x realtime)")

	def _get_sidecar(self, input_dir: pathlib.Path) -> dict:
		"""
		Get sidecar metadata from the input directory.

		Args:
			input_dir: Input directory.

		Returns:
			Normalized sidecar dict, or empty dict if no sidecar found.
		"""
		sidecar_files = sorted([
			f for f in input_dir.iterdir()
			if f.is_file() and f.suffix.lower() == ".txt"
		])

		if not sidecar_files:
			return {
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

		# Prefer file with "audible" in name or matching directory name
		preferred = None
		for sf in sidecar_files:
			if "audible" in sf.name.lower():
				preferred = sf
				break
			if input_dir.name in sf.name:
				preferred = sf
				break

		sidecar_file = preferred if preferred else sidecar_files[0]
		try:
			return sidecar_parser.parse(sidecar_file)
		except (FileNotFoundError, UnicodeDecodeError, ValueError) as e:
			logging.warning(f"Sidecar parse failed: {e}")
			return {
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

	def _resolve_metadata(self, input_dir: pathlib.Path) -> dict:
		"""
		Resolve metadata from Audnex, sidecar, or filenames.

		Priority:
		1. Audnex (if asin and not no_asin)
		2. Sidecar .txt file
		3. Filenames (minimal fallback)

		Args:
			input_dir: Input directory.

		Returns:
			Normalized metadata dict.

		Raises:
			ValueError: if no metadata source is available.
		"""
		# Priority 1: Audnex
		if self.asin and not self.no_asin:
			try:
				book_data = audible_helper.BookData(self.asin)
				book_data.fetch_api_data(self.runtime_config.audnex_url)
				return book_data.normalize()
			except (requests.RequestException, ValueError, KeyError) as e:
				logging.warning(f"Audnex lookup failed: {e}")
				# Fall through to sidecar

		# Priority 2: Sidecar .txt
		sidecar_files = sorted([
			f for f in input_dir.iterdir()
			if f.is_file() and f.suffix.lower() == ".txt"
		])

		if sidecar_files:
			# Prefer file with "audible" in name or matching directory name
			preferred = None
			for sf in sidecar_files:
				if "audible" in sf.name.lower():
					preferred = sf
					break
				if input_dir.name in sf.name:
					preferred = sf
					break

			sidecar_file = preferred if preferred else sidecar_files[0]
			try:
				return sidecar_parser.parse(sidecar_file)
			except (FileNotFoundError, UnicodeDecodeError, ValueError) as e:
				logging.warning(f"Sidecar parse failed: {e}")
				# Fall through to filenames

		# Priority 3: Minimal fallback from directory name
		return {
			"title": input_dir.name,
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

	def _probe_and_validate_sources(
		self,
		source_files: list[pathlib.Path],
	) -> list[dict]:
		"""
		Probe source files and validate homogeneous properties.

		Checks sample_rate and channel_layout for consistency.

		Args:
			source_files: List of MP3 files.

		Returns:
			List of probe result dicts (one per source file).

		Raises:
			SourcePreflightError: if sources differ in key properties.
		"""
		if not source_files:
			return []

		probes = [
			ffmpeg_runner.probe(f, self.runtime_config)
			for f in source_files
		]

		first_probe = probes[0]
		homogeneity_keys = ["codec", "sample_rate", "channels", "channel_layout"]
		# Note: time_base is not checked because it's always "1/1000" in normalized probes

		mismatches = []
		for idx, p in enumerate(probes[1:], start=1):
			for key in homogeneity_keys:
				if p[key] != first_probe[key]:
					mismatches.append(
						f"File {idx} ({source_files[idx].name}): {key} "
						f"mismatch: {p[key]} != {first_probe[key]}"
					)

		if mismatches:
			error_msg = "Source preflight failed: heterogeneous sources\n" + "\n".join(
				mismatches
			)
			raise SourcePreflightError(error_msg)

		return probes

	def _resolve_output_path(self, title: str, check_collision: bool = True) -> pathlib.Path:
		"""
		Resolve final output path from title and output_path.

		If output_path is a directory, use output_path / sanitized_title.m4b.
		If output_path ends in .m4b, use it directly.

		Args:
			title: Audiobook title (for sanitization).

		Returns:
			Final .m4b file path.

		Raises:
			ValueError: if output_path is invalid.
			FileExistsError: if output file already exists and force is False.
		"""
		if self.output_path.is_dir():
			sanitized = _sanitize_title(title)
			resolved = self.output_path / f"{sanitized}.m4b"
		elif str(self.output_path).endswith(".m4b"):
			resolved = self.output_path
		else:
			raise ValueError(
				f"Output path must be a directory or end in .m4b: {self.output_path}"
			)

		# Check for output file collision. Prompt the user interactively so
		# accidental clobbers don't happen silently, but a y/Y reply is
		# enough to overwrite without re-running with a flag.
		if check_collision and resolved.exists():
			reply = input(
				f"Output file already exists: {resolved}\nOverwrite? [y/N]: "
			).strip().lower()
			if reply not in ("y", "yes"):
				raise FileExistsError(
					f"Refusing to overwrite existing output: {resolved}"
				)

		return resolved

	def _print_dry_run_report(
		self,
		source_files: list[pathlib.Path],
		metadata: dict,
		cover_path: pathlib.Path | None,
		cover_hit,
		files_needing_silence_detection: list[int] | None = None,
		selected_quality_args: list[str] | None = None,
		probe_results: list[dict] | None = None,
	) -> None:
		"""
		Print a dry-run report to stdout.

		Args:
			source_files: List of source MP3 files.
			metadata: Resolved metadata dict.
			cover_path: Cover file path, or None.
			cover_hit: CoverHit object, or None.
			files_needing_silence_detection: Optional list of file indices that
				would have silence detection run.
		"""
		output_path = self._resolve_output_path(metadata["title"], check_collision=False)

		print("=" * 70)
		print("M4B-MERGE DRY-RUN REPORT")
		print("=" * 70)
		print()
		# Display the args that would actually be used: caller-supplied
		# selection (auto or --bitrate) wins; otherwise the runtime default.
		effective_args = (
			selected_quality_args
			if selected_quality_args is not None
			else self.runtime_config.quality_args
		)
		print(f"Output Path:     {output_path}")
		print(f"Encoder:         {self.runtime_config.aac_encoder}")
		print(f"Quality Args:    {effective_args}")
		print()

		print("Source Files (in processing order):")
		# Prefer the probes the caller already ran to avoid a second pass.
		probes = probe_results if probe_results is not None else [
			ffmpeg_runner.probe(src_file, self.runtime_config) for src_file in source_files
		]
		for idx, (src_file, probe) in enumerate(zip(source_files, probes), 1):
			duration = probe["duration_seconds"]
			bps = probe.get("bitrate_bps")
			bitrate_note = f" @ {bps // 1000} kbps" if bps else ""
			note = ""
			if files_needing_silence_detection and (idx - 1) in files_needing_silence_detection:
				note = " [silence detection will be run]"
			print(f"  {idx:2d}. {src_file.name:<40} {duration:8.2f}s{bitrate_note}{note}")
		print()

		total_duration = sum(p["duration_seconds"] for p in probes)
		print(f"Total Duration:  {total_duration:.2f} seconds")
		print()

		print(f"Title:           {metadata.get('title', '(none)')}")
		if metadata.get("authors"):
			print(f"Authors:         {', '.join(metadata['authors'])}")
		if metadata.get("narrators"):
			print(f"Narrators:       {', '.join(metadata['narrators'])}")
		print()

		chapter_source = "filenames"
		if metadata.get("chapters"):
			chapter_source = "Audnex"
		print(f"Chapter Source:  {chapter_source} ({len(source_files)} chapters)")
		print()

		cover_source = "none"
		if cover_path:
			conversion_note = ""
			if cover_hit and cover_hit.needs_jpeg_conversion:
				conversion_note = " (will convert to JPEG)"
			cover_source = f"{cover_path.name}{conversion_note}"
		print(f"Cover Source:    {cover_source}")
		print()

		print("FFmpeg Invocations (planned):")
		print("  1. encode_to_m4a: ffmpeg -i <source>.mp3 -c:a aac ...")
		print("  2. concat: ffmpeg -f concat -i <concat_list> -c copy merged.m4a")
		print("  3. remux_with_metadata: ffmpeg -i merged.m4a -i cover -i ffmeta ...")
		print()
		print("=" * 70)

	def _create_silent_cover(self) -> pathlib.Path:
		"""
		Create a minimal 1x1 JPEG as placeholder cover when none provided.

		Returns:
			Path to temporary JPEG file.
		"""
		# Generate a 1x1 red JPEG via ffmpeg
		temp_cover = self.runtime_config.tmp_dir / "_placeholder_cover.jpg"

		# Use ffmpeg to generate minimal JPEG
		subprocess.run(
			[
				self.runtime_config.ffmpeg_path,
				"-y",
				"-f", "lavfi",
				"-i", "color=red:size=1x1",
				"-frames:v", "1",
				str(temp_cover),
			],
			capture_output=True,
			check=True,
		)
		return temp_cover
