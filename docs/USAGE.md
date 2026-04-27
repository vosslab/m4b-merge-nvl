# Usage

`m4b-merge` takes a directory of audio files (or a single file) and
produces one tagged `.m4b` audiobook with embedded chapters and cover
art.

## Synopsis

```
m4b-merge -i INPUT -o OUTPUT [--no-asin] [--api-url URL] [--dry-run] [--keep-temp]
```

## Flags

| Flag | Description |
| --- | --- |
| `-i`, `--input` | Input directory or single audio file (required) |
| `-o`, `--output` | Output directory or `.m4b` filename (required) |
| `-n`, `--no-asin` | Skip Audnex lookup; use sidecar and filenames only |
| `-u`, `--api-url` | Audnex mirror to query (default is the public API) |
| `-d`, `--dry-run` | Print the planned ffmpeg invocations and exit |
| `-k`, `--keep-temp` | Keep the working temp directory after a run |

The legacy flags `--num_cpus` and `--path_format` were removed in
version 26.04.0. See [docs/CHANGELOG.md](CHANGELOG.md).

## Output path semantics

- If `-o` is an existing directory, the output file is written to
  `<dir>/<sanitized_title>.m4b`.
- If `-o` ends in `.m4b`, that path is the final filename and the parent
  directory must exist.
- Any other value raises a clear error.

## Examples

Convert a folder of MP3s using only the sidecar `.txt` and filenames:

```
m4b-merge -i Derek_Cheung-Conquering_the_Electron/ -o output_smoke/ --no-asin
```

Convert with Audnex metadata when the input directory name contains an
ASIN:

```
m4b-merge -i Some_Book_B0XXXXXXXX/ -o output_smoke/
```

Dry run to see the planned ffmpeg calls without writing any files:

```
m4b-merge -i Derek_Cheung-Conquering_the_Electron/ -o output_smoke/ --no-asin --dry-run
```

## Input layout

The orchestrator expects an input directory to contain:

- One or more `.mp3` (or `.m4a`, `.m4b`) audio files in playback order.
  Files are sorted lexicographically; numeric prefixes such as
  `01_intro.mp3` are recommended.
- Optional cover art. Search order:
  1. `cover.jpg` or `cover.jpeg`
  2. `folder.jpg` or `folder.jpeg`
  3. `cover.png` or `folder.png` (converted to JPEG before embed)
  4. Exactly one `.jpg`, `.jpeg`, or `.png` in the directory
- Optional sidecar `.txt` with Audible-style metadata (title, authors,
  narrators, release date, publisher, language, description).

If multiple unrelated images are present and none match the priority
names, no cover is embedded; the tool will not silently pick one.

## Metadata sources

In priority order:

1. Audnex API lookup (when an ASIN is detected and `--no-asin` is not set)
2. Sidecar `.txt` parser
3. Filename heuristics

The composite is normalized into one internal metadata dict before any
ffmpeg work starts.

## Related docs

- [docs/INSTALL.md](INSTALL.md) - install steps
- [docs/CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md) - pipeline internals
- [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) - common failures
