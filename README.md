# m4b-merge

Convert a folder of MP3 audiobook files into a single tagged `.m4b` with
embedded chapters and cover art. A small Python orchestrator around
`ffmpeg` and `mutagen`.

## Status

Active rewrite. The runtime no longer depends on the PHP `m4b-tool` or
`mp4chaps`. It now drives `ffmpeg`, `sox`, and `mutagen` directly. See
[docs/CHANGELOG.md](docs/CHANGELOG.md) for milestone progress.

## Prerequisites

- Python 3.12
- `ffmpeg` and `sox` on `PATH`
- Python packages from [pip_requirements.txt](pip_requirements.txt)

Full setup steps live in [docs/INSTALL.md](docs/INSTALL.md).

## Quick start

```
source source_me.sh
pip install -r pip_requirements.txt
./m4b-merge.py -i Derek_Cheung-Conquering_the_Electron/ -o output_smoke/ --no-asin
```

The tool writes `<sanitized_title>.m4b` into the output directory, with
chapters built from filenames and metadata read from the sidecar `.txt`.

## Documentation

- [docs/INSTALL.md](docs/INSTALL.md) - install steps and external binaries
- [docs/USAGE.md](docs/USAGE.md) - CLI flags and examples
- [docs/CODE_ARCHITECTURE.md](docs/CODE_ARCHITECTURE.md) - pipeline and modules
- [docs/FILE_STRUCTURE.md](docs/FILE_STRUCTURE.md) - directory map
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - common failures
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) - dev environment and tests
- [docs/CHANGELOG.md](docs/CHANGELOG.md) - history of changes

## License

GPLv3. See [LICENSE](LICENSE).

## Author

Originally created by [@djdembeck](https://github.com/djdembeck). Current
maintenance by Neil Voss
([bsky](https://bsky.app/profile/neilvosslab.bsky.social)).
