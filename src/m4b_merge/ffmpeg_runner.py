"""
FFmpeg subprocess wrappers for audio encoding and metadata operations.

Provides functions to probe audio files, encode to M4A, concatenate with
preflight checks, and remux with metadata and cover art.
"""

import json
import os
import pathlib
import subprocess
import tempfile


class ConcatPreflightError(RuntimeError):
	"""
	Raised when concat preflight validation detects heterogeneous sources.

	Attributes:
		message: Detailed error description with per-file diff.
	"""
	pass


def probe(path: pathlib.Path, runtime_config) -> dict:
	"""
	Probe audio file with mediainfo to extract normalized metadata.

	Uses mediainfo for richer, more stable JSON output. Maps mediainfo
	Audio track fields to normalized return shape.

	Args:
		path: Path to audio file.
		runtime_config: RuntimeConfig with mediainfo_path.

	Returns:
		Dict with normalized keys: codec, sample_rate, channels,
		channel_layout, duration_seconds, time_base.

	Raises:
		subprocess.CalledProcessError: if mediainfo fails.
		RuntimeError: if no audio track found.
	"""
	result = subprocess.run(
		[
			runtime_config.mediainfo_path,
			"--Output=JSON",
			str(path),
		],
		capture_output=True,
		text=True,
		check=True,
	)

	data = json.loads(result.stdout)

	# Extract track list (sometimes a single dict, sometimes a list)
	media = data["media"]
	track_list = media["track"]
	if isinstance(track_list, dict):
		track_list = [track_list]

	# Find General and Audio tracks
	general_track = None
	audio_track = None
	for track in track_list:
		if track.get("@type") == "General":
			general_track = track
		elif track.get("@type") == "Audio":
			audio_track = track
			break

	if not audio_track:
		raise RuntimeError(f"No audio track found in {path}")

	# Extract codec from Audio track Format field (lowercased)
	codec_format = audio_track.get("Format", "unknown")
	codec = codec_format.lower()

	# Extract sample rate
	sample_rate = int(audio_track["SamplingRate"])

	# Extract channels
	channels = int(audio_track["Channels"])

	# Extract or derive channel layout
	channel_layout = audio_track.get("ChannelLayout")
	if not channel_layout:
		channel_layout = _layout_from_channels(channels)

	# Extract duration (prefer General track, fallback to Audio track)
	duration_seconds = None
	if general_track and "Duration" in general_track:
		duration_seconds = float(general_track["Duration"])
	elif "Duration" in audio_track:
		duration_seconds = float(audio_track["Duration"])
	else:
		raise RuntimeError(f"No duration found in {path}")

	return {
		"codec": codec,
		"sample_rate": sample_rate,
		"channels": channels,
		"channel_layout": channel_layout,
		"duration_seconds": duration_seconds,
		"time_base": "1/1000",
	}


def _layout_from_channels(channels: int) -> str:
	"""
	Derive channel layout name from channel count.

	Args:
		channels: Number of audio channels.

	Returns:
		Channel layout string: "mono", "stereo", or f"unknown_{n}ch".
	"""
	if channels == 1:
		return "mono"
	elif channels == 2:
		return "stereo"
	else:
		return f"unknown_{channels}ch"


def encode_to_m4a(src: pathlib.Path, dst: pathlib.Path, runtime_config) -> None:
	"""
	Encode audio to AAC M4A format.

	Preserves source sample rate and channel layout. Uses the encoder and
	quality settings selected in runtime_config.

	Args:
		src: Source audio file.
		dst: Destination M4A file.
		runtime_config: RuntimeConfig with ffmpeg_path, aac_encoder,
			quality_args.

	Raises:
		subprocess.CalledProcessError: if ffmpeg encoding fails.
	"""
	subprocess.run(
		[
			runtime_config.ffmpeg_path,
			"-y",
			"-i", str(src),
			"-vn",
			"-c:a", runtime_config.aac_encoder,
			*runtime_config.quality_args,
			str(dst),
		],
		capture_output=True,
		check=True,
	)


def concat(
	file_list: list[pathlib.Path],
	dst: pathlib.Path,
	runtime_config,
	preflight: bool = True,
) -> None:
	"""
	Concatenate audio files with optional preflight validation.

	When preflight=True (default), probes all files to ensure homogeneous
	codec, sample_rate, channels, channel_layout, and time_base. Raises
	ConcatPreflightError if any mismatch is detected.

	Args:
		file_list: List of audio files to concatenate.
		dst: Destination concatenated audio file.
		runtime_config: RuntimeConfig with ffmpeg_path.
		preflight: If True, validate homogeneity before concatenating.

	Raises:
		ConcatPreflightError: if preflight=True and files are heterogeneous.
		subprocess.CalledProcessError: if ffmpeg concat fails.
	"""
	if preflight and len(file_list) > 1:
		_validate_concat_homogeneity(file_list, runtime_config)

	# Write concat demuxer listing file
	with tempfile.NamedTemporaryFile(
		mode="w",
		delete=False,
		suffix=".txt",
	) as listing_file:
		listing_path = listing_file.name
		for fpath in file_list:
			# Escape single quotes per ffmpeg concat demuxer spec
			escaped = str(fpath.resolve()).replace("'", "'\\''")
			listing_file.write(f"file '{escaped}'\n")

	try:
		subprocess.run(
			[
				runtime_config.ffmpeg_path,
				"-y",
				"-f", "concat",
				"-safe", "0",
				"-i", listing_path,
				"-c", "copy",
				str(dst),
			],
			capture_output=True,
			check=True,
		)
	finally:
		# Always clean up the temporary listing file
		os.unlink(listing_path)


def _validate_concat_homogeneity(
	file_list: list[pathlib.Path],
	runtime_config,
) -> None:
	"""
	Validate that all files have matching audio properties.

	Args:
		file_list: List of audio files.
		runtime_config: RuntimeConfig with ffmpeg_path.

	Raises:
		ConcatPreflightError: if any file differs from the first.
	"""
	probes = [probe(fpath, runtime_config) for fpath in file_list]
	first_probe = probes[0]

	# Keys to check for homogeneity
	homogeneity_keys = [
		"codec",
		"sample_rate",
		"channels",
		"channel_layout",
		"time_base",
	]

	mismatches = []
	for idx, p in enumerate(probes[1:], start=1):
		for key in homogeneity_keys:
			if p[key] != first_probe[key]:
				mismatches.append(
					f"File {idx} ({file_list[idx].name}): {key} "
					f"mismatch: {p[key]} != {first_probe[key]}"
				)

	if mismatches:
		error_msg = "Concat preflight failed: heterogeneous sources\n" + "\n".join(
			mismatches
		)
		raise ConcatPreflightError(error_msg)


def remux_with_metadata(
	audio_src: pathlib.Path,
	cover_path: pathlib.Path,
	needs_jpeg_conversion: bool,
	ffmetadata_path: pathlib.Path,
	dst: pathlib.Path,
	runtime_config,
) -> None:
	"""
	Remux audio with metadata and cover art.

	Combines audio, cover image, and ffmetadata into a final M4B container.
	If cover is PNG or flagged for conversion, first transcodes it to JPEG.

	Args:
		audio_src: Source audio file.
		cover_path: Path to cover image file.
		needs_jpeg_conversion: If True, convert cover to JPEG first.
		ffmetadata_path: Path to ffmetadata text file.
		dst: Destination M4B file.
		runtime_config: RuntimeConfig with ffmpeg_path.

	Raises:
		subprocess.CalledProcessError: if ffmpeg remux fails.
	"""
	# If cover is PNG or flagged, transcode to temp JPEG (cleaned up after remux).
	cover_for_embed = cover_path
	temp_jpg_path = None
	if needs_jpeg_conversion or cover_path.suffix.lower() == ".png":
		with tempfile.NamedTemporaryFile(
			suffix=".jpg",
			delete=False,
		) as temp_jpg:
			temp_jpg_path = pathlib.Path(temp_jpg.name)

		try:
			subprocess.run(
				[
					runtime_config.ffmpeg_path,
					"-y",
					"-i", str(cover_path),
					"-frames:v", "1",
					str(temp_jpg_path),
				],
				capture_output=True,
				check=True,
			)
			cover_for_embed = temp_jpg_path
		except subprocess.CalledProcessError:
			os.unlink(temp_jpg_path)
			raise

	try:
		subprocess.run(
			[
				runtime_config.ffmpeg_path,
				"-y",
				"-i", str(audio_src),
				"-i", str(cover_for_embed),
				"-i", str(ffmetadata_path),
				"-map", "0:a",
				"-map", "1:v",
				"-map_metadata", "2",
				"-c", "copy",
				"-disposition:v:0", "attached_pic",
				str(dst),
			],
			capture_output=True,
			check=True,
		)
	finally:
		if temp_jpg_path is not None and temp_jpg_path.exists():
			os.unlink(temp_jpg_path)
