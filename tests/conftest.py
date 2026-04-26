"""Shared pytest setup: put src/ on sys.path so tests run without install."""
import os
import sys

import git_file_utils

REPO_ROOT = git_file_utils.get_repo_root()
SRC_DIR = os.path.join(REPO_ROOT, 'src')
if SRC_DIR not in sys.path:
	sys.path.insert(0, SRC_DIR)
