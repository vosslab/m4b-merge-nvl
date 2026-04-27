# Code architecture

`m4b-merge` is a sequential Python orchestrator around `ffmpeg`, `mediainfo`,
`sox`, and `mutagen`. One book at a time, no parallel job pool.

## Pipeline

```
+--------+     +-------+     +----------+     +-----------+
| input  | --> | probe | --> | metadata | --> | encode    |
| dir    |     |       |     | resolve  |     | each MP3  |
+--------+     +-------+     +----------+     +-----------+
                                                    |
                                                    v
+----------+     +------------+     +----------+    +--------+
| concat   | --> | remux with | --> | mutagen  | -> | clean  |
| with     |     | chapters + |     | tag pass |    | up tmp |
| preflight|     | cover      |     |          |    |        |
+----------+     +------------+     +----------+    +--------+
```

Each stage is a pure function or a thin subprocess wrapper. The merger
holds the only mutable state (a temp directory and the resolved metadata
dict) and threads it between stages.

## Modules

The components below are introduced across milestones M3 through M7.
Some files do not exist yet at the moment this doc was written; they
land in later patches per the implementation plan.

| Module | Role |
| --- | --- |
| `cli` (`__main__.py`) | argparse, build `RuntimeConfig`, call `Merger.run` |
| `runtime_config` | discover binaries (ffmpeg, mediainfo, sox), choose AAC encoder, hold paths and quality args |
| `helpers` | path, extension, and ASIN utilities |
| `audible_helper` | Audnex API client; normalizes external JSON at the boundary |
| `sidecar_parser` (M4) | parse Audible-style `.txt`; always return a fixed-key dict |
| `cover_finder` (M4) | locate cover by priority order; flag PNG for JPEG conversion |
| `ffmpeg_runner` (M5) | probe (mediainfo-based), encode_to_m4a, concat (preflight), remux_with_metadata |
| `silence_detect` (M7) | sox-based silence interval detection with on-disk cache |
| `chapter_builder` (M5) | pure function; emit ffmetadata chapters from probe and metadata |
| `tagger` (M6) | mutagen MP4 tag pass; idempotent cover fallback |
| `merger` (M6) | end-to-end orchestrator that wires the pipeline |

## Runtime config flow

`runtime_config.discover()` runs once at startup. It locates `ffmpeg`,
`mediainfo`, and `sox` with `shutil.which`, picks the best available AAC encoder
(`libfdk_aac` if present, else native `aac`), and returns a frozen
config object with:

- `ffmpeg_path`, `mediainfo_path`, `sox_path`
- `aac_encoder` (`"libfdk_aac"` or `"aac"`)
- `quality_args` (a list, e.g. `["-vbr", "5"]` or `["-b:a", "160k"]`)
- `audnex_url`
- `keep_temp`

The object is built in `cli` and passed into `Merger`. Modules never
read the environment or call `which` again on their own.

## Source homogeneity preflight

Before any encoding, `Merger.run` probes every input MP3 and asserts a
homogeneous `(sample_rate, channels, channel_layout)` set. A mismatch
raises `SourcePreflightError` with a per-file diff. This is the first
line of defense against concat failures; `ffmpeg_runner.concat`
re-checks as a second line.

## Chapter sources

In priority order:

1. Audnex chapter list, when `metadata["chapters"]` is non-empty
2. Sidecar `chapters` field, when present (the test fixture has none)
3. Filenames plus cumulative file durations from probe

M7 adds a silence-driven splitter: when a single input exceeds
`MAX_CHAPTER_SECONDS` (default 1800) and silence intervals are present,
the chapter is split at the deepest silences such that no resulting
chapter is shorter than `MIN_CHAPTER_SECONDS` (default 60).

## Tagging

The `tagger` writes standard MP4 atoms with `mutagen`:

- `\xa9nam` title
- `\xa9ART` artist
- `\xa9alb` album
- `\xa9day` release date
- `\xa9gen` genre
- `\xa9wrt` composer (used for narrator)
- `desc` description
- `covr` cover art (only if not already present, idempotent)

Chapter atoms are NOT written by `mutagen` in the MVP. ffmpeg's
ffmetadata path is the sole chapter writer. A mutagen-based chapter-atom
fallback is deferred to M10 and only added if a real player is shown to
ignore ffmpeg-written chapters.

## Cleanup

Unless `--keep-temp` is set, the temp directory is removed after a
successful run. On failure it is preserved so the user can inspect
intermediate `.m4a` files and the generated `ffmetadata.txt`.
