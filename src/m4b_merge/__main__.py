#!/usr/bin/env python3
"""
CLI entry point for m4b-merge.

Parses arguments, builds RuntimeConfig, and orchestrates the merge pipeline.
"""

import argparse
from pathlib import Path

import m4b_merge.runtime_config as runtime_config
import m4b_merge.helpers as helpers
import m4b_merge.merger as merger


def parse_args():
	"""Parse command-line arguments."""
	parser = argparse.ArgumentParser(
		description="Convert a folder of MP3s into a single M4B audiobook"
	)

	parser.add_argument(
		"-i", "--input",
		dest="input_path",
		type=Path,
		required=True,
		help="Input directory (MP3s + optional sidecar/cover) or single audio file"
	)

	parser.add_argument(
		"-o", "--output",
		dest="output_path",
		type=Path,
		required=True,
		help="Output directory (creates <dir>/<title>.m4b) or path to .m4b file"
	)

	parser.add_argument(
		"-n", "--no-asin",
		dest="no_asin",
		action="store_true",
		help="Skip Audnex metadata lookup; use sidecar and cover only"
	)

	parser.add_argument(
		"-u", "--api-url",
		dest="api_url",
		default="https://api.audnex.us",
		help="Audnex API base URL (default: %(default)s)"
	)

	parser.add_argument(
		"-d", "--dry-run",
		dest="dry_run",
		action="store_true",
		help="Plan execution without writing files"
	)

	parser.add_argument(
		"-k", "--keep-temp",
		dest="keep_temp",
		action="store_true",
		help="Preserve temporary directory after merge completes"
	)

	parser.add_argument(
		"-f", "--force",
		dest="force",
		action="store_true",
		help="Overwrite existing output file if it exists"
	)

	return parser.parse_args()


def _validate_output_path(output_path: Path) -> None:
	"""
	Validate that output_path is either:
	  - An existing directory, or
	  - A path ending in .m4b

	Raises:
		ValueError: if path is invalid.
	"""
	if output_path.exists():
		if not output_path.is_dir():
			raise ValueError(
				f"Output path exists but is not a directory: {output_path}"
			)
	else:
		# Path does not exist; it must end in .m4b
		if not str(output_path).endswith(".m4b"):
			raise ValueError(
				f"Output path must be an existing directory or a path ending in .m4b: {output_path}"
			)


def _prompt_for_asin(api_url: str) -> str | None:
	"""
	Prompt user for audiobook ASIN and validate it.

	Args:
		api_url: Audnex API base URL for validation.

	Returns:
		Validated ASIN, or None if user skips.
	"""
	max_attempts = 3
	for attempt in range(max_attempts):
		user_input = input("Audiobook ASIN (or press Enter to skip): ").strip()

		if not user_input:
			return None

		try:
			helpers.validate_asin(api_url, user_input)
			return user_input
		except ValueError as e:
			remaining = max_attempts - attempt - 1
			if remaining > 0:
				print(f"Invalid ASIN: {e}. Try again ({remaining} attempts left).")
			else:
				print(f"Invalid ASIN: {e}. Skipping Audnex lookup.")
				return None

	return None


def main():
	"""Main entry point."""
	args = parse_args()

	# Validate output path
	_validate_output_path(args.output_path)

	# Build RuntimeConfig
	config = runtime_config.discover(
		audnex_url=args.api_url,
		keep_temp=args.keep_temp,
		dry_run=args.dry_run,
	)

	# Prompt for ASIN if not --no-asin
	asin = None
	if not args.no_asin:
		asin = _prompt_for_asin(args.api_url)

	# Create and run Merger
	m = merger.Merger(
		input_path=args.input_path,
		output_path=args.output_path,
		runtime_config=config,
		no_asin=args.no_asin,
		asin=asin,
		force=args.force,
	)

	m.run()


if __name__ == "__main__":
	main()
