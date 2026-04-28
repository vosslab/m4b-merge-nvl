"""
Runtime configuration for m4b-merge pipeline.

Defines a frozen RuntimeConfig dataclass and a discover() function that
locates external binaries and selects the best AAC encoder.
"""

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class RuntimeConfig:
	"""
	Immutable runtime configuration built once at startup.

	Holds paths to required external binaries, encoder choice, and
	runtime options.
	"""
	ffmpeg_path: str
	mediainfo_path: str
	sox_path: str
	aac_encoder: str
	quality_args: list[str]
	audnex_url: str
	keep_temp: bool
	dry_run: bool
	tmp_dir: Path


def discover(audnex_url: str, keep_temp: bool, dry_run: bool) -> RuntimeConfig:
	"""
	Discover external binaries and build RuntimeConfig.

	Args:
		audnex_url: Audnex API base URL.
		keep_temp: If True, preserve temp directory after pipeline runs.
		dry_run: If True, plan execution without writing files.

	Returns:
		RuntimeConfig with all required paths and encoder settings.

	Raises:
		RuntimeError: if ffmpeg, mediainfo, or sox not found, with install message.
	"""
	# Find ffmpeg
	ffmpeg_path = shutil.which("ffmpeg")
	if not ffmpeg_path:
		raise RuntimeError(
			"ffmpeg not found. Install via: brew bundle install (Brewfile at repo root)"
		)

	# Find mediainfo
	mediainfo_path = shutil.which("mediainfo")
	if not mediainfo_path:
		raise RuntimeError(
			"mediainfo not found. Install via: brew bundle install (Brewfile at repo root)"
		)

	# Find sox
	sox_path = shutil.which("sox")
	if not sox_path:
		raise RuntimeError(
			"sox not found. Install via: brew bundle install (Brewfile at repo root)"
		)

	# Detect AAC encoder
	aac_encoder, quality_args = _detect_aac_encoder(ffmpeg_path)

	# Prepare temp directory path (do NOT mkdir here - defer to Merger.run after dry-run check)
	tmp_dir = Path(tempfile.gettempdir()) / "m4b-merge" / f"{os.getpid()}"

	return RuntimeConfig(
		ffmpeg_path=ffmpeg_path,
		mediainfo_path=mediainfo_path,
		sox_path=sox_path,
		aac_encoder=aac_encoder,
		quality_args=quality_args,
		audnex_url=audnex_url,
		keep_temp=keep_temp,
		dry_run=dry_run,
		tmp_dir=tmp_dir,
	)


def _detect_aac_encoder(ffmpeg_path: str) -> tuple[str, list[str]]:
	"""
	Detect best available AAC encoder and return (encoder_name, quality_args).

	If libfdk_aac is available, use it with VBR quality 5.
	Otherwise, fall back to native aac at 160k bitrate.

	Args:
		ffmpeg_path: Path to ffmpeg binary.

	Returns:
		Tuple of (encoder_name, quality_args_list).
	"""
	# Run with check=True so any failure raises rather than silently
	# demoting the encoder. ffmpeg is verified earlier in discover().
	result = subprocess.run(
		[ffmpeg_path, "-hide_banner", "-encoders"],
		capture_output=True,
		text=True,
		timeout=10,
		check=True,
	)

	# Prefer libfdk_aac (higher quality at lower bitrates) when present
	if "libfdk_aac" in result.stdout:
		return "libfdk_aac", ["-vbr", "5"]

	# Fall back to native aac
	return "aac", ["-b:a", "160k"]
