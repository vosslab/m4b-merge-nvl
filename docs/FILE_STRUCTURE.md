# File structure

Top-level layout of the `m4b-merge` repository.

```
m4b-merge/
+-- README.md                      Project intro and quick start
+-- LICENSE                        GPLv3 license text
+-- VERSION                        Single-line version string (CalVer)
+-- pyproject.toml                 Package metadata; reads pip_requirements.txt
+-- pip_requirements.txt           Runtime Python deps (source of truth)
+-- pip_requirements-dev.txt       Developer-only Python deps (pytest, etc.)
+-- Brewfile                       macOS Homebrew packages (ffmpeg, sox)
+-- source_me.sh                   Bash env bootstrap for AI agents
+-- m4b-merge.py                   Convenience entry point script
+-- AGENTS.md                      Agent instructions
+-- CLAUDE.md                      Claude-specific instructions
+-- src/m4b_merge/                 Python package source
+-- tests/                         Pytest test suite and lint helpers
+-- docs/                          Project documentation (this folder)
+-- devel/                         Maintainer scripts (release, changelog)
+-- Derek_Cheung-Conquering_the_Electron/
                                   Test fixture, do not modify
```

## src/m4b_merge

```
src/m4b_merge/
+-- __init__.py                    One-line package docstring only
+-- __main__.py                    cli entry point (argparse, build config)
+-- runtime_config.py              RuntimeConfig dataclass and discover()
+-- helpers.py                     Path, extension, ASIN utilities
+-- audible_helper.py              Audnex API client; boundary normalization
+-- conftest.py                    Pytest configuration for in-package tests
```

Modules added in later milestones (per the active implementation plan):

```
+-- sidecar_parser.py              Audible-style .txt parser (M4)
+-- cover_finder.py                Cover image discovery (M4)
+-- ffmpeg_runner.py               probe, encode, concat, remux (M5)
+-- chapter_builder.py             ffmetadata chapter emitter (M5)
+-- tagger.py                      mutagen MP4 tag pass (M6)
+-- merger.py                      End-to-end orchestrator (M6)
+-- silence_detect.py              sox-based silence detection (M7)
```

## docs

```
docs/
+-- CHANGELOG.md                   Dated change log per REPO_STYLE.md
+-- INSTALL.md                     External binaries and Python setup
+-- USAGE.md                       CLI flags and examples
+-- DEVELOPMENT.md                 Dev environment and running tests
+-- CODE_ARCHITECTURE.md           Pipeline diagram and module roles
+-- FILE_STRUCTURE.md              This file
+-- TROUBLESHOOTING.md             Common failures and fixes
+-- AUTHORS.md                     Maintainers (centrally maintained)
+-- REPO_STYLE.md                  Centrally maintained
+-- PYTHON_STYLE.md                Centrally maintained
+-- MARKDOWN_STYLE.md              Centrally maintained
+-- CLAUDE_HOOK_USAGE_GUIDE.md     Centrally maintained
```

## tests

```
tests/
+-- conftest.py                    Shared pytest fixtures
+-- git_file_utils.py              get_repo_root() helper
+-- check_ascii_compliance.py      Single-file ASCII checker
+-- fix_ascii_compliance.py        Single-file ASCII fixer
+-- fix_whitespace.py              Tab/whitespace normalizer
+-- test_ascii_compliance.py       Repo-wide ASCII gate
+-- test_bandit_security.py        Security lint gate
+-- test_import_dot.py             No relative imports gate
+-- test_import_requirements.py    Declared-deps gate
+-- test_import_star.py            No `import *` gate
+-- test_indentation.py            Tabs-only gate
+-- test_init_files.py             Minimal __init__.py gate
+-- test_pyflakes_code_lint.py     pyflakes gate
+-- test_shebangs.py               Shebang/executable bit gate
+-- test_whitespace.py             Trailing-whitespace gate
```

## Outputs and temp

- Smoke output goes to `output_smoke/` (gitignored). Reuse this folder
  rather than creating one-off output directories.
- Per-run temp work happens under the system temp dir; pass
  `--keep-temp` to preserve it.
