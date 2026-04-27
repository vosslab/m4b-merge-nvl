# Install

`m4b-merge` is a Python 3.12 tool that wraps three external binaries:
`ffmpeg`, `mediainfo`, and `sox`. It also depends on the pure-Python `mutagen` and
`requests` libraries.

The legacy dependencies on `m4b-tool` (PHP) and `mp4chaps` (mp4v2) were
removed in version 26.04.0. You no longer need PHP or mp4v2 installed.

## External binaries

| Binary | Purpose |
| --- | --- |
| ffmpeg | Encode, concat, remux, embed cover and chapters |
| mediainfo | Probe audio files for codec, sample rate, channels, duration |
| sox | Silence detection for chapter splitting (M7+) |

### macOS (Homebrew)

The repo ships a [Brewfile](../Brewfile) listing both binaries. From the
repo root:

```
brew bundle
```

Or install them individually:

```
brew install ffmpeg mediainfo sox
```

For best AAC quality, install an `ffmpeg` build that includes `libfdk_aac`
(see [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md)). The default Homebrew
build uses the native `aac` encoder; the orchestrator falls back to it
automatically.

### Debian and Ubuntu

```
sudo apt update
sudo apt install ffmpeg mediainfo sox
```

The Debian `ffmpeg` package does not ship `libfdk_aac` for license
reasons. The orchestrator detects this and falls back to the native AAC
encoder.

### Other systems

Install `ffmpeg`, `mediainfo`, and `sox` from your package manager or from source.
All three must be on `PATH` so that `which ffmpeg`, `which mediainfo`, and `which sox` succeed.

## Python dependencies

```
source source_me.sh
pip install -r pip_requirements.txt
```

For development tools (pytest, pyflakes, etc.):

```
pip install -r pip_requirements-dev.txt
```

## Install the package

Editable install from the repo root:

```
pip install -e .
```

## Verify

```
m4b-merge -h
```

You should see the CLI usage. If `ffmpeg`, `mediainfo`, or `sox` is missing, the tool
fails fast with an install message at first run.
