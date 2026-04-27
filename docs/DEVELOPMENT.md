# Development

How to set up a dev environment for `m4b-merge` and run the test suite.

## Set up

1. Install Python 3.12 and the required external binaries listed in
   [docs/INSTALL.md](docs/INSTALL.md) (`ffmpeg`, `sox`).
2. Clone the repo and install in editable mode:

   ```
   source source_me.sh
   pip install -r pip_requirements.txt
   pip install -r pip_requirements-dev.txt
   pip install -e .
   ```

3. Verify the install:

   ```
   m4b-merge -h
   ```

## Run tests

The test suite is plain `pytest`. From the repo root:

```
source source_me.sh
python -m pytest tests/
```

To run a single test module:

```
python -m pytest tests/test_ascii_compliance.py -v
```

To filter by test name:

```
python -m pytest tests/test_pyflakes_code_lint.py -k helpers
```

## Repo style

Follow the conventions in:

- [docs/REPO_STYLE.md](docs/REPO_STYLE.md) - repo-wide conventions
- [docs/PYTHON_STYLE.md](docs/PYTHON_STYLE.md) - Python style
- [docs/MARKDOWN_STYLE.md](docs/MARKDOWN_STYLE.md) - Markdown style

When you change behavior, add an entry to [docs/CHANGELOG.md](docs/CHANGELOG.md)
under today's date heading.

## Reporting bugs

Open an issue on the project tracker with:

- Command line you ran
- Full traceback or `ffmpeg`/`sox` error output
- OS and Python version (`python3 --version`)
- A minimal input that reproduces the problem when possible
