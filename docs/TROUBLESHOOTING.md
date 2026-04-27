# Troubleshooting

Common failure modes and how to fix them.

## ffmpeg not found

Symptom: startup error from `runtime_config.discover()` saying
`ffmpeg` is not on `PATH`.

Fix: install `ffmpeg` and re-run `which ffmpeg` to confirm. See
[docs/INSTALL.md](INSTALL.md).

## sox not found

Symptom: startup error from `runtime_config.discover()` saying `sox`
is not on `PATH`. Affects M7+ where silence-driven chapter splitting
is used.

Fix: install `sox` (`brew install sox` on macOS, `apt install sox` on
Debian and Ubuntu).

## libfdk_aac not available

Symptom: log line says `aac_encoder=aac` instead of `libfdk_aac`. The
output still works but at slightly lower quality per bit.

Fix: install an `ffmpeg` build that includes `libfdk_aac`. On macOS:

```
brew tap homebrew-ffmpeg/ffmpeg
brew install homebrew-ffmpeg/ffmpeg/ffmpeg --with-fdk-aac
```

Debian and Ubuntu do not ship `libfdk_aac` for license reasons; build
`ffmpeg` from source if you need it.

## Cover not found

Symptom: log line says `cover=none` and the output `.m4b` has no
attached picture stream.

Fix: ensure the input directory contains one of:

- `cover.jpg` or `cover.jpeg`
- `folder.jpg` or `folder.jpeg`
- `cover.png` or `folder.png`
- Exactly one image file

If multiple unrelated images are present, the finder refuses to guess.
Rename the intended cover to `cover.jpg`.

## Sidecar parse miss

Symptom: metadata fields show as `None` even though the sidecar `.txt`
contains them.

Fix: confirm the sidecar uses the Audible-style `Key: value` format
(one field per line). Run with `--dry-run` to see which fields the
parser found. The parser always returns a fixed key set; missing
fields are explicitly `None`.

## Audnex 404

Symptom: `audible_helper` raises after a 404 from the Audnex API.

Fix: verify the ASIN is correct. If the book is not in the Audnex
database, run with `--no-asin` to fall back to the sidecar and
filenames.

## Bad ASIN

Symptom: ASIN extracted from the directory name fails the format
check or returns a 404.

Fix: rename the directory so the ASIN is the trailing `B0XXXXXXXX`
token, or run with `--no-asin`.

## Mutagen cannot write atom

Symptom: `tagger.write` raises a `mutagen.MP4MetadataError`.

Fix: confirm the file is a real MP4/M4B (run `ffprobe` on it). If
ffmpeg produced a malformed file, re-run the merge with `--keep-temp`
and inspect the intermediate `.m4a` files.

## Concat preflight failure

Symptom: `ConcatPreflightError` with a per-file diff showing
mismatched `codec`, `sample_rate`, `channels`, `channel_layout`, or
`time_base`.

Fix: this means the encoded `.m4a` files diverged. Check that the
source MP3s were not altered mid-run and that `runtime_config` is
threading the same `quality_args` to every encode. The earlier
source-homogeneity preflight should normally catch this before any
encoding happens.

## Source homogeneity preflight failure

Symptom: `SourcePreflightError` raised before any encoding starts,
showing a per-file diff of `sample_rate` and `channel_layout`.

Fix: the input MP3s are not uniform. Re-encode the odd files to match
the rest (same sample rate and channel layout) and rerun. MVP does
not auto-normalize; that is a planned enhancement.
