# Changelog

All notable changes to this project are documented in this file.
Newer entries follow the `## YYYY-MM-DD` format from
[docs/REPO_STYLE.md](REPO_STYLE.md). Older entries below were generated
by `standard-version` against the upstream `djdembeck/m4b-merge` repo.

## 2026-04-27

### Behavior or Interface Changes

- `__main__.py`: removed `-u/--api-url` flag (argparse minimalism). Audnex
  base URL is now a module-level `AUDNEX_URL` constant. Boolean flags
  `--dry-run`, `--keep-temp`, `--force` now have paired `--no-*` variants
  with `set_defaults`.
- `_prompt_for_asin` no longer silently returns `None` after three invalid
  ASINs; it now raises `ValueError` so failures are visible. Pressing
  Enter to skip is still respected.
- `runtime_config._detect_aac_encoder`: removed `try/except` that silently
  demoted `libfdk_aac` to native AAC on any failure. ffmpeg is verified
  earlier in `discover()`, so a real failure here now raises.
- `merger.run`: silence-detection failures now propagate instead of being
  swallowed and replaced with `[]` (silent wrong-chapter splits).
- `merger._resolve_output_path`: gained `check_collision` parameter; the
  dry-run report now skips the `FileExistsError` collision check so
  `--dry-run` works on re-runs without `--force`.
- `tagger.write`: dropped dead `genres` branch (key never produced by any
  metadata source). Required keys (`title`, `authors`, `narrators`,
  `description`) now use direct dict access instead of `.get(key)`.
- `silence_detect`: amplitude and duration parsers now raise on parse
  failure instead of leaving `max_amplitude=None` and reporting "no
  silence." Cache hash is computed once per call and threaded through
  `load_cache` / `save_cache` (avoids a second full-file SHA1 read on hit).

### Fixes and Maintenance

- `ffmpeg_runner.probe`: `audio_track["Format"]` (direct access). The old
  `.get("Format", "unknown")` let two un-probeable files compare equal in
  the homogeneity preflight and bypass the guard.
- `audible_helper.fetch_api_data` and `helpers.validate_asin`: added
  `time.sleep(random.random())` before each Audnex `requests.get`, per
  repo style.
- `helpers.find_extension`: `logging.warn` (deprecated) -> `logging.warning`.
- `helpers.get_directory`: replaced fragile `Path(...).stem.split('.')[1]`
  (would `IndexError` for a bare suffix) with `Path(...).suffix.lstrip('.')`.
  Renamed `extension_to_use_PRE` to follow snake_case. Added module
  docstring.
- `silence_detect.save_cache`: collapsed the nested temp-file cleanup
  `try/except` into a plain `os.replace`; a failed atomic rename leaves a
  `.tmp` file (acceptable, surfaces the real error).

### Removals and Deprecations

- Removed `tests/test_tagger.py::test_tagger_with_genres` (asserted on the
  now-deleted `genres` tagger branch).

### Developer Tests and Notes

- `tests/test_merger.py::test_runtime_config`: replaced bare
  `except Exception: pytest.skip(...)` with a `shutil.which` precheck and
  let unrelated exceptions propagate.
- `tests/test_chapter_builder.py::test_derek_fixture_no_split`: replaced
  brittle `assert len(chapters) == 21` with the invariant
  `len(chapters) == len(filenames)`.
- `tests/test_sidecar_parser.py`: replaced fixture-dependent test (relied
  on the untracked `Derek_Cheung-Conquering_the_Electron/` directory and
  asserted on hardcoded publisher / description / language fields) with
  an inline-fixture round-trip test of the parser on Derek-style sidecar
  text. `test_missing_file` now uses `pytest.raises`.
- `tests/test_silence_detect.py::rt_config`: replaced
  `shutil.which("sox") or "sox"` (and friends) with a precheck that
  skips when binaries are missing.
- `tests/test_ffmpeg_runner.py::runtime_config_fixture`: replaced
  hardcoded `/usr/bin/sox` with `shutil.which("sox")`; skips when sox is
  absent (Apple Silicon Homebrew installs to `/opt/homebrew/bin`).
- Full suite: 281 passed.

## 2026-04-25

### Additions and New Features

- New `Brewfile` at repo root listing required external binaries
  (`ffmpeg`, `mediainfo`, `sox`).
- New `VERSION` file at repo root mirroring `pyproject.toml` version
  `26.04.0` (CalVer).
- New `m4b-merge.py` executable launcher at repo root for running
  without installation: `source source_me.sh && ./m4b-merge.py -h`.
- New Python orchestrator modules: `runtime_config`, `sidecar_parser`,
  `cover_finder`, `ffmpeg_runner`, `silence_detect`, `chapter_builder`,
  `tagger`, `merger`. Together they replace the old `m4b_helper.py`
  subprocess-to-`m4b-tool` flow.
- New CLI flags: `-d/--dry-run`, `-k/--keep-temp`, `-n/--no-asin`,
  `-u/--api-url`, `-f/--force`. Removed legacy `--num_cpus`,
  `--path_format`, `--completed_directory`, `--log_level`, `--inputs`.
- M2 docs refresh (Patch 3): created
  [docs/INSTALL.md](INSTALL.md),
  [docs/USAGE.md](USAGE.md),
  [docs/CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md),
  [docs/FILE_STRUCTURE.md](FILE_STRUCTURE.md), and
  [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md). Rewrote
  [README.md](../README.md) as an ASCII-only short intro with
  quick-start and doc links. Rewrote
  [docs/DEVELOPMENT.md](DEVELOPMENT.md) to drop emoji and the
  obsolete release-please / conventional-commits content.
- M7 silence detection (Patch 8): new `silence_detect.py` (sox-driven,
  on-disk cache by sha1+mtime under platformdirs cache dir);
  `chapter_builder.build()` now accepts an optional
  `silences_per_file` argument and splits filename-derived chapters
  longer than `MAX_CHAPTER_SECONDS` (default 5400) at silence
  midpoints, never producing chapters shorter than
  `MIN_CHAPTER_SECONDS` (default 60).
- M8 e2e validation (Patch 9): real run on
  `Derek_Cheung-Conquering_the_Electron/` (21 MP3s, 14h 9m of audio)
  produced a 1014 MB `.m4b` in 6m39s wall time (~128x realtime),
  with 21 chapters, embedded 300x300 JPEG cover, AAC 44.1 kHz stereo
  at 165 kbps average, and full sidecar-sourced metadata (title,
  authors, narrator/composer, release date, description).

### Behavior or Interface Changes

- New end-to-end engine: ffmpeg + sox + mediainfo + mutagen replaces
  `m4b-tool` (PHP) + `mp4chaps` (mp4v2). `Merger.run()` orchestrates
  source-homogeneity preflight -> per-file AAC encode (libfdk_aac
  preferred, native AAC at `-b:a 160k` fallback) -> concat with
  preflight -> remux with cover + ffmetadata chapters -> mutagen MP4
  atom pass.
- `--dry-run` honored end to end: writes nothing to disk and creates
  no temp directories (verified against fixture).
- Output-path semantics: `-o` is either an existing directory
  (output goes to `<dir>/<sanitized_title>.m4b`) or a path ending in
  `.m4b`. Existing output files require `-f/--force` to overwrite.

### Behavior or Interface Changes

- Swapped `ffprobe` for `mediainfo` in `ffmpeg_runner.probe()` (Patch 5b).
  mediainfo provides richer JSON output with more stable field names,
  improving audio codec, sample rate, and channel detection reliability.
  mediainfo is now a required external binary alongside ffmpeg and sox.
  Added `mediainfo_path` field to `RuntimeConfig`; updated
  `runtime_config.discover()` to locate mediainfo with `shutil.which()`.
  All probe callers (concat preflight, merger pipeline, dry-run) kept
  unchanged due to stable return shape. Updated [docs/INSTALL.md](INSTALL.md),
  [docs/CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md), and Brewfile.
- M3 style cleanup (Patch 4): renamed
  `src/m4b_merge/config.py` -> `src/m4b_merge/runtime_config.py`
  (final `RuntimeConfig` dataclass shape lands in Patch 5);
  replaced relative `from . import` with absolute imports in all
  kept modules; converted space indentation to tabs throughout
  `src/m4b_merge/`; narrowed broad `Exception` handler in
  `__main__.py` to specific `ValueError` from `validate_asin`.
- Repo surgery (Patch 1, M1 of plan
  `~/.claude/plans/stateful-herding-zebra.md`): root `__main__.py`
  removed (use `python -m m4b_merge` instead); root `CHANGELOG.md`
  moved to `docs/CHANGELOG.md`; root `CONTRIBUTING.md` moved to
  `docs/DEVELOPMENT.md`; `requirements.txt` renamed to
  `pip_requirements.txt`.

### Fixes and Maintenance

- Packaging consolidated: `setup.py` removed entirely;
  `pyproject.toml` now carries name, version, classifiers, and
  console-script entry; dependencies declared dynamically from
  `pip_requirements.txt` so the requirements file remains the single
  source of truth.
- `pip_requirements.txt` now declares `mutagen`, `platformdirs`, and
  `requests` as the target dependencies; `appdirs`, `pathvalidate`, and
  `pydub` are kept temporarily and marked for removal in their
  respective patches.
- `tests/conftest.py` now puts `src/` on `sys.path` so the test suite
  collects without requiring `pip install -e .`.
- `src/m4b_merge/config.py` no longer raises `SystemExit` at import
  time when `m4b-tool` or `mp4chaps` is missing; checks are deferred
  to consumers (Patch 5 replaces this with `runtime_config.discover()`
  that fails fast).

### Removals and Deprecations

- Removed five slow functional tests (`test_audible.py`,
  `test_single_mp3_merge.py`, `test_single_m4b_merge.py`,
  `test_multiple_mp3_merge.py`, `test_multiple_m4b_merge.py`). Reasons:
  (1) targeted obsolete code (`m4b_helper.py`) scheduled for deletion
  in M6, (2) violated `docs/PYTHON_STYLE.md` pytest rules (network
  calls to live Audnex API, 8-hour silent audio generated via ffmpeg,
  shelled out to real `m4b-tool` binary, asserted on hardcoded byte
  sizes). Replacement: M8 introduces a single skip-on-missing-deps
  end-to-end smoke test.
- Removed `.github/workflows/` (build, docker-publish, pypi-publish,
  release-please).
- Removed `renovate.json` (GitHub-only, not useful without workflows).
- Removed `docker/` (Dockerfile + entrypoint.sh).
- Removed `MANIFEST.in`; LICENSE inclusion now declared via PEP 639
  `license-files = ["LICENSE"]` in `pyproject.toml`.

### Decisions and Failures

- Reviewed two reference silence-detection implementations:
  - Current: `sox ... stat` per 1-second chunk (poor scaling).
  - Reference: `emwy_tools/silence_annotator/sa_detection.py`
    (single ffmpeg WAV extract + numpy frame RMS in dBFS, smoothing,
    auto-threshold).
  Decided to keep the current implementation for the MVP because the
  silence-driven chapter splitter is only invoked when no chapter
  source is available AND a single file exceeds 90 minutes - a
  corner case the Derek fixture and most multi-MP3 audiobooks do not
  trigger. Documented the perf gap and the planned port in
  [docs/TODO.md](TODO.md).


- Plan acknowledged a contradiction between "drop pydub/appdirs/
  pathvalidate now" and "pytest must collect cleanly". Chose the
  pragmatic interpretation: keep transitional deps in
  `pip_requirements.txt` with comments noting their removal patch.

### Developer Tests and Notes

- `pytest tests/ --collect-only` reports 209 tests collected, no
  errors.
- `pip install -e .` in the project venv succeeds.



### Bug Fixes

  * If junk_dir is not set, do not perform post-process move ([4286a1c](https://github.com/djdembeck/m4b-merge/commit/4286a1ce7c50d56d5d9e22136cbdc292cd3d52e3))
  * Add --tmp-dir with os.pid to each m4b-tool invocation ([36689e8](https://github.com/djdembeck/m4b-merge/commit/36689e8f52ed7af7e3c70660501529d852dc482e))


### [0.5.2](https://github.com/djdembeck/m4b-merge/compare/v0.5.1...v0.5.2) (2023-04-27)


### Bug Fixes

* file_title not found, replaced with title ([3ec4d66](https://github.com/djdembeck/m4b-merge/commit/3ec4d661fd032836b374e277d2b947a170d16716))

### [0.5.1](https://github.com/djdembeck/m4b-merge/compare/v0.5.0...v0.5.1) (2023-02-24)


### Bug Fixes

* **merge:** :bug: incorrect dict key ([54d4a8b](https://github.com/djdembeck/m4b-merge/commit/54d4a8b259a0486ace02f69264aeacd7e224f26f))

## [0.5.0](https://github.com/djdembeck/m4b-merge/compare/v0.4.11...v0.5.0) (2023-02-24)


### Features

* **merge:** :sparkles: add support for `asin` as output path term ([87a3623](https://github.com/djdembeck/m4b-merge/commit/87a3623fd9799d5c7f30da34015b84b17eadb12d))

### [0.4.11](https://github.com/djdembeck/m4b-merge/compare/v0.4.10...v0.4.11) (2023-01-23)


### Bug Fixes

* write temporary covers to `input_path` ([#104](https://github.com/djdembeck/m4b-merge/issues/104)) ([7cfca92](https://github.com/djdembeck/m4b-merge/commit/7cfca92b61ad8f47a656418fb8385acc6625b0d9)), closes [#103](https://github.com/djdembeck/m4b-merge/issues/103)

### [0.4.10](https://github.com/djdembeck/m4b-merge/compare/v0.4.8...v0.4.10) (2022-09-21)


### Bug Fixes

* **merge:** :bug: properly fix moving completed input files ([f0f4ae9](https://github.com/djdembeck/m4b-merge/commit/f0f4ae9468796f13d6738cb4ba9592df9e858d74))

### [0.4.8](https://github.com/djdembeck/m4b-merge/compare/v0.4.7...v0.4.8) (2022-09-12)


### Features

* **merge:** :sparkles: use LOG_LEVEL from environment variable if available ([6779104](https://github.com/djdembeck/m4b-merge/commit/677910471c1ea88f272df29d1b5f0faf34e6b073))


### Bug Fixes

* **merge:** :ambulance: fix crash on single file in a folder ([a895b4d](https://github.com/djdembeck/m4b-merge/commit/a895b4de44f549068c4b010a3b4fb1a82d1750ad))
* **merge:** :bug: handle case where input has no `bit_rate` and/or `sample_rate` ([9e17fbd](https://github.com/djdembeck/m4b-merge/commit/9e17fbd7b58145461ca1cee422ab881e76415483))

### [0.4.7](https://github.com/djdembeck/m4b-merge/compare/v0.4.6...v0.4.7) (2022-02-28)


### Bug Fixes

* **docker:** :ambulance: also chown /config ([8e99393](https://github.com/djdembeck/m4b-merge/commit/8e993935e92cd2e49a10cd2abbec4cf394bbee83))
* **docker:** :bug: better startup permissions management ([3c4cef5](https://github.com/djdembeck/m4b-merge/commit/3c4cef567f185e2c690c043b2316c1e4439ed441))
* **merge:** :bug: cleanup find_extension process ([a37bfbe](https://github.com/djdembeck/m4b-merge/commit/a37bfbe96870774d35e3255813932f7ce2e7c518))
* **merge:** :bug: separate these into own functions so multi disc and single file both can pick up unknown extensions ([a8da6b5](https://github.com/djdembeck/m4b-merge/commit/a8da6b5ab3fe726057d4c9b18a7d486f5947990a))

### [0.4.6](https://github.com/djdembeck/m4b-merge/compare/v0.4.5...v0.4.6) (2022-02-07)

### [0.4.2](https://github.com/djdembeck/m4b-merge/compare/v0.4.1...v0.4.2) (2021-11-04)

### [0.4.5](https://github.com/djdembeck/m4b-merge/compare/v0.4.4...v0.4.5) (2021-12-06)


### Bug Fixes

* **merge:** :bug: handle api having no author or narrators ([3adac9b](https://github.com/djdembeck/m4b-merge/commit/3adac9bd66480e1b373f9a17946dbd6c355f1e9e))

### [0.4.4](https://github.com/djdembeck/m4b-merge/compare/v0.4.3...v0.4.4) (2021-11-26)


### Features

* **merge:** :sparkles: Allow specifying output naming convention ([8980308](https://github.com/djdembeck/m4b-merge/commit/89803080db9816b8a71b8ff2d1f5135c2199c4dc))


### Bug Fixes

* **merge:** :bug: don't create empty directory of file name ([cbd2297](https://github.com/djdembeck/m4b-merge/commit/cbd22973d137875a317d68dd444897f44ecb0830))
* **merge:** :bug: fix replace_tag replacing partial terms instead of full term ([7abea6f](https://github.com/djdembeck/m4b-merge/commit/7abea6fd5c08252e4413f42b83ca1ecff5a28479))

### [0.4.3](https://github.com/djdembeck/m4b-merge/compare/v0.4.1...v0.4.3) (2021-11-18)


### Features

* **merge:** :construction: better config 1: move user configurable options to arguments ([c2cd229](https://github.com/djdembeck/m4b-merge/commit/c2cd2292fc8d3b3d50511deaf404e3df487cfb86))


### Bug Fixes

* **audible:** :bug: fix double import config issue with api_url ([0e657fb](https://github.com/djdembeck/m4b-merge/commit/0e657fb0ae2a0a7d58dd53d72110d66e75dfef3b))
* **audible:** :bug: fix validate url ([36a357b](https://github.com/djdembeck/m4b-merge/commit/36a357bbfd030165c09a45e33baae17ee8c20d94))
* **audible:** :bug: pass url directly instead of importing config ([27f796f](https://github.com/djdembeck/m4b-merge/commit/27f796fb01f4d20bf9a12eafe7eb7fc5ff8430d6))
* **merge:** :ambulance: fix  inconsistent variable name ([51b9b94](https://github.com/djdembeck/m4b-merge/commit/51b9b94d1b96d073587a2cf760565cff479ab049))
* **merge:** :bug: fix asin validation before merge ([0d00c09](https://github.com/djdembeck/m4b-merge/commit/0d00c09d07322a34bd18d560e15bac333090bc67))
* **merge:** :bug: fix error when no cover exists ([b42b081](https://github.com/djdembeck/m4b-merge/commit/b42b081bdf28f4c526fedd8bd71870d8252481ea))
* **merge:** :bug: fix path comparison for junk dir ([a98c828](https://github.com/djdembeck/m4b-merge/commit/a98c8287069fbf90a075826848e2433225046992))

### [0.4.2](https://github.com/djdembeck/m4b-merge/compare/v0.4.1...v0.4.2) (2021-11-03)


### Bug Fixes

* **merge:** :bug: fix error when no cover exists ([b42b081](https://github.com/djdembeck/m4b-merge/commit/b42b081bdf28f4c526fedd8bd71870d8252481ea))

### [0.4.1](https://github.com/djdembeck/m4b-merge/compare/v0.3.5...v0.4.1) (2021-10-06)


### Bug Fixes

* **audible:** :bug: verify isAccurate exists before using it ([6f21eae](https://github.com/djdembeck/m4b-merge/commit/6f21eae6c343e14aafb1a4521444b1ad687c8184))
* **merge:** :bug: don't expect series position to exist ([cf41203](https://github.com/djdembeck/m4b-merge/commit/cf412030db3b9d2c67632f6ea1737c478bb3ad20))
* **merge:** :bug: set series_position to none if it doesn't exist ([3aaed08](https://github.com/djdembeck/m4b-merge/commit/3aaed08889f9585ad6b96a4a2f3434f7f0144f00))
