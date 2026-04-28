"""Shared pytest setup: put src/ on sys.path so tests run without install."""
import os
import sys
import dataclasses

import git_file_utils

REPO_ROOT = git_file_utils.get_repo_root()
SRC_DIR = os.path.join(REPO_ROOT, 'src')
if SRC_DIR not in sys.path:
	sys.path.insert(0, SRC_DIR)

import pytest

import m4b_merge.runtime_config as _runtime_config


def make_runtime_config(tmp_dir, dry_run=False):
	"""
	Build a RuntimeConfig for tests, reusing discover()'s binary search so
	test fixtures don't duplicate the field list. Skips the test if any
	required external binary is missing.
	"""
	import shutil
	for binary in ("ffmpeg", "mediainfo", "sox"):
		if not shutil.which(binary):
			pytest.skip(f"{binary} not installed")
	config = _runtime_config.discover(
		audnex_url="https://api.audnex.us",
		dry_run=dry_run,
	)
	return dataclasses.replace(config, tmp_dir=tmp_dir)
