# TODO

Backlog of small to medium tasks not blocking the current release.

## silence_detect performance and accuracy

`src/m4b_merge/silence_detect.py` currently spawns one `sox ... stat`
subprocess per 1-second chunk of audio. For long inputs (e.g. a single
14-hour audiobook file with no chapter signal) this is roughly 50,000
subprocess calls and is impractical.

A reference implementation lives in
`/Users/vosslab/nsh/emwy-video-editor/emwy_tools/silence_annotator/sa_detection.py`
and is much better:

- Extracts audio to WAV with one `ffmpeg` call.
- Reads samples with `wave` + `numpy.frombuffer`.
- Slides a frame window in numpy and computes per-frame RMS in dBFS.
- Optional smoothing window.
- Auto-raises threshold until silences appear (handles loud-baseline
  audio).
- Returns structured `(start, end, duration)` plus stats.

Port that approach when the silence-driven chapter splitter is
actually exercised in production. Add `numpy` to `pip_requirements.txt`
at that time. The `sox` dependency may then drop entirely.

Note: silence detection is only invoked when (1) Audnex provided no
chapters, (2) sidecar provided no chapters, and (3) a single source
file exceeds `chapter_builder.MAX_CHAPTER_SECONDS` (default 5400 s).
The Derek fixture and most multi-MP3 audiobooks never trigger it.

## Other pending items

- M9 (deferred from plan `~/.claude/plans/stateful-herding-zebra.md`):
  `batch.py` walker + JSON resume file for processing a directory of
  book directories.
- M10 (deferred from same plan): mutagen QuickTime/iTunes chapter atom
  fallback in `tagger.py` for players that ignore ffmpeg ffmetadata
  chapters. Only add if a real player is shown to fail.
- Speed levers: pass `-threads 0` to ffmpeg encode_to_m4a; verify
  libfdk_aac install path; explore stream-copy mode when source is
  already AAC.
