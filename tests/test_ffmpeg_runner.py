"""
Unit tests for ffmpeg_runner module.

Tests probe, encode_to_m4a, concat with preflight, and remux_with_metadata.
"""

import pathlib
import shutil
import subprocess
import pytest
import m4b_merge.ffmpeg_runner as ffmpeg_runner
from m4b_merge.runtime_config import RuntimeConfig


@pytest.fixture
def runtime_config_fixture(tmp_path):
	"""
	Create a minimal RuntimeConfig for testing.

	Skips tests if ffmpeg or mediainfo is not available.
	"""
	ffmpeg_path = shutil.which("ffmpeg")
	mediainfo_path = shutil.which("mediainfo")
	if not ffmpeg_path or not mediainfo_path:
		pytest.skip("ffmpeg or mediainfo not installed")

	return RuntimeConfig(
		ffmpeg_path=ffmpeg_path,
		mediainfo_path=mediainfo_path,
		sox_path="/usr/bin/sox",
		aac_encoder="aac",
		quality_args=["-b:a", "160k"],
		audnex_url="https://example.com",
		keep_temp=False,
		dry_run=False,
		tmp_dir=tmp_path,
	)


def _generate_test_audio(path: pathlib.Path, duration_sec: float, sample_rate: int = 44100) -> None:
	"""
	Generate a test audio file using ffmpeg.

	Args:
		path: Output file path.
		duration_sec: Duration in seconds.
		sample_rate: Sample rate in Hz.
	"""
	ffmpeg_path = shutil.which("ffmpeg")
	if not ffmpeg_path:
		raise RuntimeError("ffmpeg not found")

	subprocess.run(
		[
			ffmpeg_path,
			"-f", "lavfi",
			"-i", f"sine=frequency=440:duration={duration_sec}:sample_rate={sample_rate}",
			"-ac", "2",
			"-y",
			str(path),
		],
		capture_output=True,
		check=True,
	)


class TestProbe:
	"""Test ffmpeg_runner.probe function."""

	def test_probe_returns_normalized_dict(self, tmp_path, runtime_config_fixture):
		"""Test that probe returns expected normalized keys."""
		# Generate a test audio file
		test_mp3 = tmp_path / "test.mp3"
		_generate_test_audio(test_mp3, 2.0)

		# Probe the file
		result = ffmpeg_runner.probe(test_mp3, runtime_config_fixture)

		# Check that result has expected keys (specific assertions)
		assert "codec" in result
		assert "sample_rate" in result
		assert "channels" in result
		assert "channel_layout" in result
		assert "duration_seconds" in result

		# Verify types and reasonable values
		assert isinstance(result["codec"], str)
		assert result["sample_rate"] == 44100
		assert result["channels"] == 2
		assert result["channel_layout"] in ["stereo", "mono", "unknown_2ch"]
		assert isinstance(result["duration_seconds"], float)
		assert result["duration_seconds"] >= 1.9  # Rough range

	def test_probe_mp3_codec_normalization(self, tmp_path, runtime_config_fixture):
		"""Test that MP3 codec is normalized to lowercase."""
		# Generate a test MP3
		test_mp3 = tmp_path / "test.mp3"
		_generate_test_audio(test_mp3, 1.0)

		# Probe the file
		result = ffmpeg_runner.probe(test_mp3, runtime_config_fixture)

		# Verify codec is normalized to lowercase and contains expected string
		assert result["codec"] == result["codec"].lower()
		assert "mpeg" in result["codec"] or "mp3" in result["codec"]


class TestLayoutFromChannels:
	"""Test _layout_from_channels helper."""

	def test_mono_layout(self):
		"""Test that 1 channel maps to mono."""
		assert ffmpeg_runner._layout_from_channels(1) == "mono"

	def test_stereo_layout(self):
		"""Test that 2 channels maps to stereo."""
		assert ffmpeg_runner._layout_from_channels(2) == "stereo"

	def test_unknown_layout(self):
		"""Test that other channel counts use unknown_Nch format."""
		assert ffmpeg_runner._layout_from_channels(6) == "unknown_6ch"
		assert ffmpeg_runner._layout_from_channels(5) == "unknown_5ch"


class TestEncodeToM4a:
	"""Test ffmpeg_runner.encode_to_m4a function."""

	def test_encode_to_m4a_creates_file(self, tmp_path, runtime_config_fixture):
		"""Test that encode_to_m4a creates a valid M4A file."""
		# Generate test audio
		test_mp3 = tmp_path / "test.mp3"
		_generate_test_audio(test_mp3, 1.0)

		# Encode to M4A
		output_m4a = tmp_path / "output.m4a"
		ffmpeg_runner.encode_to_m4a(test_mp3, output_m4a, runtime_config_fixture)

		# Check file was created
		assert output_m4a.exists()

		# Probe to verify it's valid audio
		result = ffmpeg_runner.probe(output_m4a, runtime_config_fixture)
		assert result["codec"] == "aac"


class TestConcatPreflightError:
	"""Test ConcatPreflightError exception."""

	def test_concat_preflight_error_is_runtime_error(self):
		"""Test that ConcatPreflightError is a RuntimeError."""
		exc = ffmpeg_runner.ConcatPreflightError("test message")
		assert isinstance(exc, RuntimeError)


class TestConcat:
	"""Test ffmpeg_runner.concat function."""

	def test_concat_with_homogeneous_files(self, tmp_path, runtime_config_fixture):
		"""Test concat succeeds on homogeneous M4A files."""
		# Generate three test MP3s
		test_files_mp3 = []
		for i in range(3):
			mp3_path = tmp_path / f"test_{i}.mp3"
			_generate_test_audio(mp3_path, 0.5)
			test_files_mp3.append(mp3_path)

		# Encode all to M4A with same parameters
		test_files_m4a = []
		for mp3_path in test_files_mp3:
			m4a_path = tmp_path / f"{mp3_path.stem}.m4a"
			ffmpeg_runner.encode_to_m4a(mp3_path, m4a_path, runtime_config_fixture)
			test_files_m4a.append(m4a_path)

		# Concatenate
		output_m4a = tmp_path / "concatenated.m4a"
		ffmpeg_runner.concat(
			test_files_m4a,
			output_m4a,
			runtime_config_fixture,
			preflight=True,
		)

		# Verify output exists and probes correctly
		assert output_m4a.exists()
		result = ffmpeg_runner.probe(output_m4a, runtime_config_fixture)

		# Duration should be roughly 1.5 seconds (3 * 0.5)
		assert result["duration_seconds"] >= 1.4
		assert result["duration_seconds"] <= 1.6

	def test_concat_preflight_raises_on_different_sample_rates(
		self, tmp_path, runtime_config_fixture
	):
		"""Test concat preflight raises ConcatPreflightError on sample rate mismatch."""
		# Generate files at different sample rates
		file_44k = tmp_path / "test_44k.mp3"
		_generate_test_audio(file_44k, 0.5, sample_rate=44100)

		file_48k = tmp_path / "test_48k.mp3"
		_generate_test_audio(file_48k, 0.5, sample_rate=48000)

		# Encode to M4A
		m4a_44k = tmp_path / "test_44k.m4a"
		m4a_48k = tmp_path / "test_48k.m4a"
		ffmpeg_runner.encode_to_m4a(file_44k, m4a_44k, runtime_config_fixture)
		ffmpeg_runner.encode_to_m4a(file_48k, m4a_48k, runtime_config_fixture)

		# Try to concatenate with preflight
		output_m4a = tmp_path / "concatenated.m4a"
		with pytest.raises(ffmpeg_runner.ConcatPreflightError):
			ffmpeg_runner.concat(
				[m4a_44k, m4a_48k],
				output_m4a,
				runtime_config_fixture,
				preflight=True,
			)


class TestRemuxWithMetadata:
	"""Test ffmpeg_runner.remux_with_metadata function."""

	def test_remux_with_metadata_creates_m4b(self, tmp_path, runtime_config_fixture):
		"""Test that remux_with_metadata creates a valid M4B file."""
		# Generate test audio
		test_mp3 = tmp_path / "test.mp3"
		_generate_test_audio(test_mp3, 1.0)

		# Encode to M4A
		audio_m4a = tmp_path / "audio.m4a"
		ffmpeg_runner.encode_to_m4a(test_mp3, audio_m4a, runtime_config_fixture)

		# Create a simple cover image (red square)
		cover_jpg = tmp_path / "cover.jpg"
		subprocess.run(
			[
				runtime_config_fixture.ffmpeg_path,
				"-f", "lavfi",
				"-i", "color=c=red:s=100x100:d=1",
				"-frames:v", "1",
				str(cover_jpg),
			],
			capture_output=True,
			check=True,
		)

		# Create ffmetadata
		ffmetadata = tmp_path / "ffmetadata.txt"
		ffmetadata.write_text(
			";FFMETADATA1\n"
			"[CHAPTER]\n"
			"TIMEBASE=1/1000\n"
			"START=0\n"
			"END=1000\n"
			"title=Test Chapter\n"
		)

		# Remux with metadata
		output_m4b = tmp_path / "output.m4b"
		ffmpeg_runner.remux_with_metadata(
			audio_m4a,
			cover_jpg,
			False,
			ffmetadata,
			output_m4b,
			runtime_config_fixture,
		)

		# Verify output exists and is valid
		assert output_m4b.exists()
		result = ffmpeg_runner.probe(output_m4b, runtime_config_fixture)
		assert result["codec"] == "aac"


class TestConcatPreflightConstraints:
	"""Test concat preflight validation of each constraint independently."""

	def test_concat_preflight_codec_mismatch(self, tmp_path, runtime_config_fixture):
		"""Test that concat preflight detects codec mismatch."""
		# Generate first file and encode to M4A (AAC codec)
		file_1_mp3 = tmp_path / "test_1.mp3"
		_generate_test_audio(file_1_mp3, 0.5, sample_rate=44100)

		file_1_m4a = tmp_path / "test_1.m4a"
		ffmpeg_runner.encode_to_m4a(file_1_mp3, file_1_m4a, runtime_config_fixture)

		# Generate second file as MP3 (different codec)
		file_2_mp3 = tmp_path / "test_2.mp3"
		_generate_test_audio(file_2_mp3, 0.5, sample_rate=44100)

		# Concat with preflight should raise ConcatPreflightError on codec mismatch
		output = tmp_path / "out.m4a"
		with pytest.raises(ffmpeg_runner.ConcatPreflightError, match="codec"):
			ffmpeg_runner.concat([file_1_m4a, file_2_mp3], output, runtime_config_fixture, preflight=True)

	def test_concat_preflight_channels_mismatch(self, tmp_path, runtime_config_fixture):
		"""Test that concat preflight detects channels mismatch."""
		# Generate mono file
		mono_mp3 = tmp_path / "mono.mp3"
		ffmpeg_path = shutil.which("ffmpeg")
		subprocess.run(
			[ffmpeg_path, "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1", "-ac", "1", str(mono_mp3)],
			capture_output=True,
			check=True,
		)
		mono_m4a = tmp_path / "mono.m4a"
		ffmpeg_runner.encode_to_m4a(mono_mp3, mono_m4a, runtime_config_fixture)

		# Generate stereo file
		stereo_mp3 = tmp_path / "stereo.mp3"
		_generate_test_audio(stereo_mp3, 0.5, sample_rate=44100)
		stereo_m4a = tmp_path / "stereo.m4a"
		ffmpeg_runner.encode_to_m4a(stereo_mp3, stereo_m4a, runtime_config_fixture)

		# Concat with preflight should raise ConcatPreflightError on channels mismatch
		output = tmp_path / "out.m4a"
		with pytest.raises(ffmpeg_runner.ConcatPreflightError, match="channels"):
			ffmpeg_runner.concat([mono_m4a, stereo_m4a], output, runtime_config_fixture, preflight=True)
