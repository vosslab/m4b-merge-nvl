"""
Silence detection via sox amplitude analysis.
Detects silence intervals in audio files using sox stat on chunks.
Results are cached on disk keyed by file sha1 and mtime.
"""

import os
import json
import logging
import hashlib
import subprocess
import tempfile
import platformdirs
from pathlib import Path

def get_cache_dir() -> Path:
	"""Get the cache directory for silence detection."""
	cache_root = platformdirs.user_cache_dir("m4b-merge")
	cache_dir = Path(cache_root) / "silence"
	cache_dir.mkdir(parents=True, exist_ok=True)
	return cache_dir

def compute_file_hash_and_mtime(path: str) -> tuple[str, float]:
	"""Compute SHA1 hash of file and get mtime."""
	sha1 = hashlib.sha1(usedforsecurity=False)
	with open(path, "rb") as f:
		for chunk in iter(lambda: f.read(65536), b""):
			sha1.update(chunk)

	stat = os.stat(path)
	return sha1.hexdigest(), stat.st_mtime

def load_cache(path: str) -> list[tuple[float, float]] | None:
	"""Load cached silence intervals if valid."""
	file_sha1, file_mtime = compute_file_hash_and_mtime(path)

	cache_dir = get_cache_dir()
	cache_file = cache_dir / f"{file_sha1}.json"

	if not cache_file.exists():
		return None

	try:
		with open(cache_file, "r") as f:
			data = json.load(f)

		# Validate cache entry
		if data.get("sha1") != file_sha1 or data.get("mtime") != file_mtime:
			return None

		intervals = data.get("intervals", [])
		# Convert back to tuples
		return [(start, end) for start, end in intervals]
	except (json.JSONDecodeError, KeyError, ValueError):
		# Parse or structure errors: cache is corrupt
		return None
	except OSError as e:
		# Permission or I/O error reading cache file
		logging.warning(f"Error reading cache for {path}: {e}")
		return None

def save_cache(path: str, intervals: list[tuple[float, float]]) -> None:
	"""Save silence intervals to cache."""
	file_sha1, file_mtime = compute_file_hash_and_mtime(path)

	cache_dir = get_cache_dir()
	cache_file = cache_dir / f"{file_sha1}.json"

	data = {
		"sha1": file_sha1,
		"mtime": file_mtime,
		"intervals": [[start, end] for start, end in intervals],
	}

	# Write atomically via temp file
	with tempfile.NamedTemporaryFile(
		mode="w",
		dir=cache_dir,
		delete=False,
		suffix=".tmp"
	) as tmp:
		json.dump(data, tmp)
		tmp_path = tmp.name

	try:
		os.replace(tmp_path, cache_file)
	except (OSError,):
		# If atomic rename fails, clean up temp file
		try:
			os.unlink(tmp_path)
		except OSError as unlink_err:
			logging.warning(f"Failed to clean up temp cache file {tmp_path}: {unlink_err}")
		raise

def detect(path: str, runtime_config, chunk_size: float = 1.0, amplitude_threshold: float = 0.001) -> list[tuple[float, float]]:
	"""
	Detect silence intervals in an audio file via sox amplitude analysis.

	Args:
		path: Path to audio file
		runtime_config: RuntimeConfig with sox_path
		chunk_size: Duration (seconds) of each chunk to probe
		amplitude_threshold: Max amplitude below which a chunk is considered silent

	Returns:
		Sorted list of (start_seconds, end_seconds) tuples for silence intervals.
		Raises subprocess.CalledProcessError if sox fails.
	"""
	# Check cache first
	cached = load_cache(path)
	if cached is not None:
		return cached

	# Get total duration via sox stat
	stat_result = subprocess.run(
		[runtime_config.sox_path, path, "-n", "stat"],
		check=True,
		capture_output=True,
		text=True
	)

	# Parse duration from "Length (seconds):" line
	total_duration = None
	for line in stat_result.stderr.split("\n"):
		if "Length" in line and "seconds" in line:
			try:
				# Extract value after the colon: "Length (seconds):     60.000000"
				total_duration = float(line.split(":")[-1].strip())
				break
			except (ValueError, IndexError):
				pass

	if total_duration is None:
		raise ValueError(f"Could not determine duration of {path}")

	# Probe chunks and detect silences
	silences = []
	current_silence_start = None
	pos = 0

	while pos < total_duration:
		chunk_end = min(pos + chunk_size, total_duration)
		duration = chunk_end - pos

		# Probe this chunk with sox stat
		stat_result = subprocess.run(
			[runtime_config.sox_path, path, "-n", "trim", str(pos), str(duration), "stat"],
			check=True,
			capture_output=True,
			text=True
		)

		# Parse max amplitude from "Maximum amplitude:" line
		max_amplitude = None
		for line in stat_result.stderr.split("\n"):
			if "Maximum amplitude" in line:
				parts = line.split()
				for i, part in enumerate(parts):
					if part.startswith("Maximum"):
						# Next token should be the value
						if i + 2 < len(parts):
							try:
								max_amplitude = float(parts[i + 2])
								break
							except ValueError:
								pass

		is_silent = max_amplitude is not None and max_amplitude < amplitude_threshold

		if is_silent:
			if current_silence_start is None:
				current_silence_start = pos
		else:
			if current_silence_start is not None:
				silences.append((current_silence_start, pos))
				current_silence_start = None

		pos = chunk_end

	# Handle final silence
	if current_silence_start is not None:
		silences.append((current_silence_start, total_duration))

	# Cache the result
	save_cache(path, silences)

	return silences
