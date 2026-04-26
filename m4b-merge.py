#!/usr/bin/env python3
"""Repo-root launcher for m4b_merge.

Lets you invoke the tool without installing the package:
    source source_me.sh && ./m4b-merge.py -i some_dir -o out_dir
"""
import os
import sys

# Make src/ importable when running from a fresh checkout.
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
if SRC_DIR not in sys.path:
	sys.path.insert(0, SRC_DIR)

import m4b_merge.__main__

if __name__ == '__main__':
	m4b_merge.__main__.main()
