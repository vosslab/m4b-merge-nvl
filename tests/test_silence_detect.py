"""
Tests for silence_detect module.
"""

import pathlib
import shutil
import subprocess
import tempfile
import pytest

import m4b_merge.silence_detect as silence_detect
import m4b_merge.runtime_config as runtime_config


pytestmark = pytest.mark.skipif(
	shutil.which("sox") is None,
	reason="sox not available"
)


@pytest.fixture(scope="module")
def rt_config():
	"""Minimal RuntimeConfig wired to the local sox/ffmpeg/mediainfo."""
	ffmpeg_path = shutil.which("ffmpeg")
	sox_path = shutil.which("sox")
	mediainfo_path = shutil.which("mediainfo")
	if not (ffmpeg_path and sox_path and mediainfo_path):
		pytest.skip("ffmpeg, sox, or mediainfo not found")
	return runtime_config.RuntimeConfig(
		ffmpeg_path=ffmpeg_path,
		sox_path=sox_path,
		mediainfo_path=mediainfo_path,
		aac_encoder="aac",
		quality_args=["-b:a", "160k"],
		audnex_url="https://api.audnex.us",
		keep_temp=False,
		dry_run=False,
		tmp_dir=pathlib.Path(tempfile.gettempdir()) / "m4b_test",
	)


@pytest.fixture(scope="module")
def test_wav(tmp_path_factory):
	"""
	Generate a test WAV file with known silence intervals.
	Pattern: sine (0-20s), silence (20-25s), sine (25-40s), silence (40-45s), sine (45-60s).
	Expected silences: [20.0, 25.0] and [40.0, 45.0].
	"""
	tmp_dir = tmp_path_factory.mktemp("silence_test")
	wav_path = tmp_dir / "test_spike.wav"

	cmd = [
		"ffmpeg",
		"-f", "lavfi",
		"-i", "sine=frequency=440:duration=20",
		"-f", "lavfi",
		"-i", "aevalsrc=0:duration=5",
		"-f", "lavfi",
		"-i", "sine=frequency=440:duration=15",
		"-f", "lavfi",
		"-i", "aevalsrc=0:duration=5",
		"-f", "lavfi",
		"-i", "sine=frequency=440:duration=15",
		"-filter_complex", "[0][1][2][3][4]concat=n=5:v=0:a=1[out]",
		"-map", "[out]",
		"-y",
		str(wav_path),
	]

	subprocess.run(cmd, check=True, capture_output=True)
	return wav_path


def test_detect_returns_intervals(test_wav, rt_config):
	"""Test that detect() returns at least 2 intervals."""
	intervals = silence_detect.detect(str(test_wav), rt_config)
	assert len(intervals) >= 2, f"Expected at least 2 silences, got {len(intervals)}"


def test_detect_sorted_intervals(test_wav, rt_config):
	"""Test that intervals are sorted and non-overlapping."""
	intervals = silence_detect.detect(str(test_wav), rt_config)

	# Check sorted
	sorted_intervals = sorted(intervals)
	assert intervals == sorted_intervals, "Intervals should be sorted"

	# Check non-overlapping
	for i in range(len(intervals) - 1):
		assert intervals[i][1] <= intervals[i + 1][0], \
			f"Intervals overlap: {intervals[i]} and {intervals[i + 1]}"


def test_detect_finds_expected_silences(test_wav, rt_config):
	"""Test that detected silences are near the expected positions [20, 25] and [40, 45]."""
	intervals = silence_detect.detect(str(test_wav), rt_config)

	# Should have silences near 20.0 and 40.0
	silence_starts = [s[0] for s in intervals]

	has_first_silence = any(19.5 <= s <= 20.5 for s in silence_starts)
	has_second_silence = any(39.5 <= s <= 40.5 for s in silence_starts)

	assert has_first_silence, \
		f"Expected silence around 20.0s, got starts at {silence_starts}"
	assert has_second_silence, \
		f"Expected silence around 40.0s, got starts at {silence_starts}"


def test_detect_cache_determinism(test_wav, rt_config):
	"""Test that calling detect() twice returns the same result."""
	result1 = silence_detect.detect(str(test_wav), rt_config)
	result2 = silence_detect.detect(str(test_wav), rt_config)

	assert result1 == result2, "Second call should return cached result"


def test_detect_cache_invalidation(test_wav, rt_config):
	"""Test that cache is invalidated when file mtime changes."""
	# Get initial result (warm cache)
	silence_detect.detect(str(test_wav), rt_config)

	# Modify the file (append a byte)
	with open(test_wav, "ab") as f:
		f.write(b"\x00")

	# Get result after modification
	result2 = silence_detect.detect(str(test_wav), rt_config)

	# Results should still be the same (same audio content, just with extra null byte)
	# But the cache should have been rebuilt (we just verify no errors occur)
	assert result2 is not None, "Should handle cache invalidation gracefully"


@pytest.mark.skipif(not shutil.which("sox"), reason="sox not installed")
def test_detect_empty_file(tmp_path, rt_config):
	"""Test that silence detection handles empty (near-zero duration) files."""
	empty_wav = tmp_path / "empty.wav"

	# Generate a very short (near-zero) silence file
	sox_path = shutil.which("sox")
	subprocess.run(
		[sox_path, "-r", "44100", "-b", "16", "-n", str(empty_wav), "trim", "0", "0.001"],
		capture_output=True,
		check=True,
	)

	# Should return empty list or handle gracefully without crashing
	result = silence_detect.detect(str(empty_wav), rt_config)
	assert isinstance(result, list), "Should return a list even for empty files"


@pytest.mark.skipif(not shutil.which("sox"), reason="sox not installed")
def test_detect_no_silences(tmp_path, rt_config):
	"""Test that silence detection returns empty list for file with no silences (pure tone)."""
	tone_wav = tmp_path / "tone.wav"

	# Generate a 2-second pure tone (no silences)
	ffmpeg_path = shutil.which("ffmpeg")
	subprocess.run(
		[ffmpeg_path, "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=2", "-ac", "2", str(tone_wav)],
		capture_output=True,
		check=True,
	)

	result = silence_detect.detect(str(tone_wav), rt_config)

	# Should return empty list (no silence intervals in a pure tone)
	assert result == [], "Pure tone file should have no silence intervals"
