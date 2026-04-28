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


# Audnex API base URL. Edit here, not via a CLI flag, since it almost never
# changes between runs.
AUDNEX_URL = "https://api.audnex.us"


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

	dry_run_group = parser.add_mutually_exclusive_group()
	dry_run_group.add_argument(
		"-d", "--dry-run",
		dest="dry_run", action="store_true",
		help="Plan execution without writing files"
	)
	dry_run_group.add_argument(
		"--no-dry-run",
		dest="dry_run", action="store_false",
		help="Disable dry-run (default)"
	)
	parser.set_defaults(dry_run=False)

	keep_temp_group = parser.add_mutually_exclusive_group()
	keep_temp_group.add_argument(
		"-k", "--keep-temp",
		dest="keep_temp", action="store_true",
		help="Preserve temporary directory after merge completes"
	)
	keep_temp_group.add_argument(
		"--no-keep-temp",
		dest="keep_temp", action="store_false",
		help="Remove temporary directory after merge completes (default)"
	)
	parser.set_defaults(keep_temp=False)

	force_group = parser.add_mutually_exclusive_group()
	force_group.add_argument(
		"-f", "--force",
		dest="force", action="store_true",
		help="Overwrite existing output file if it exists"
	)
	force_group.add_argument(
		"--no-force",
		dest="force", action="store_false",
		help="Refuse to overwrite existing output (default)"
	)
	parser.set_defaults(force=False)

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
	Prompt user for an audiobook ASIN and validate it.

	The user may press Enter to skip Audnex lookup entirely. Otherwise the
	last validation error is raised so the user sees why their ASIN was
	rejected instead of the program silently continuing without metadata.

	Args:
		api_url: Audnex API base URL for validation.

	Returns:
		Validated ASIN, or None if the user pressed Enter to skip.

	Raises:
		ValueError: if the user supplied an invalid ASIN three times.
	"""
	max_attempts = 3
	last_error = None
	for attempt in range(max_attempts):
		user_input = input("Audiobook ASIN (or press Enter to skip): ").strip()

		if not user_input:
			return None

		# validate_asin raises ValueError on bad ASIN or HTTP error
		last_error = None
		try:
			helpers.validate_asin(api_url, user_input)
			return user_input
		except ValueError as e:
			last_error = e
			remaining = max_attempts - attempt - 1
			if remaining > 0:
				print(f"Invalid ASIN: {e}. Try again ({remaining} attempts left).")

	# All attempts exhausted with invalid input. Surface the last error.
	raise ValueError(f"Invalid ASIN after {max_attempts} attempts: {last_error}")


def main():
	"""Main entry point."""
	args = parse_args()

	# Validate output path
	_validate_output_path(args.output_path)

	# Build RuntimeConfig
	config = runtime_config.discover(
		audnex_url=AUDNEX_URL,
		keep_temp=args.keep_temp,
		dry_run=args.dry_run,
	)

	# Prompt for ASIN if not --no-asin
	asin = None
	if not args.no_asin:
		asin = _prompt_for_asin(AUDNEX_URL)

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
