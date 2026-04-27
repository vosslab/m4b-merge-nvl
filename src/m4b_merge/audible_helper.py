"""
Audible API client via Audnex.

Fetches metadata and chapter data from the Audnex API and normalizes
the response into the internal metadata dict format.
"""

import logging
import requests
from datetime import timedelta


class BookData:
	"""Fetch and normalize Audible audiobook data from Audnex API."""

	def __init__(self, asin):
		"""
		Initialize BookData with an ASIN.

		Args:
			asin: Audible Standard Identification Number (10-character code).
		"""
		self.asin = asin
		self.metadata_dict = None

	def ms_to_timestamp(self, input_duration: int) -> str:
		"""
		Convert milliseconds to timestamp format hh:mm:ss.ms.

		Args:
			input_duration: Duration in milliseconds.

		Returns:
			Timestamp string in hh:mm:ss.ms format.
		"""
		conversion = timedelta(milliseconds=input_duration)
		# Handle timedelta showing days past 24hr
		if "day" in str(conversion):
			hour = int(str(conversion).split(", ")[1].split(":")[0])
			day = int(str(conversion).split(" ")[0])
			real_hours = hour + (day * 24)
			remainder = str(conversion).split(", ")[1].split(":", 1)[1]
			timestamp = f"{real_hours}:{remainder}"
		else:
			timestamp = str(conversion)

		# Remove trailing 000 if it makes ms 6 places long
		if "." in timestamp:
			split_timestamp = timestamp.split(".")
			prefix = split_timestamp[0]
			suffix = split_timestamp[1]
			if len(suffix) > 3:
				suffix = suffix.rstrip("000")
			return prefix + '.' + suffix

		return timestamp + '.' + '000'

	def get_chapters(self):
		"""
		Extract chapter list from metadata_dict.

		Returns:
			List of chapter strings, or None if not available or not accurate.
		"""
		chapter_info = self.metadata_dict['chapter_info']

		# Only use Audible chapters if tagged as accurate
		if 'isAccurate' in chapter_info and chapter_info['isAccurate'] is True:
			chapter_output = []
			# Append total runtime to the top of file
			total_len = self.ms_to_timestamp(chapter_info['runtimeLengthMs'])
			chapter_output.append(
				f"# total-length {total_len}"
			)

			# Append each chapter to array
			for chapter in chapter_info['chapters']:
				chap_start = self.ms_to_timestamp(chapter['startOffsetMs'])
				chapter_title = chapter['title']
				chapter_output.append(
					f"{chap_start} {chapter_title}"
				)
			return chapter_output
		else:
			logging.warning(
				"Not using Audible chapters as they aren't tagged as accurate"
			)
			return None

	def fetch_api_data(self, api_url: str) -> dict:
		"""
		Fetch metadata and chapters from Audnex API.

		Args:
			api_url: Audnex API base URL.

		Returns:
			Metadata dict with book data and chapter_info.

		Raises:
			requests.RequestException: if API calls fail.
		"""
		book_api_call = requests.get(
			f"{api_url}/books/{self.asin}"
		)
		book_api_call.raise_for_status()

		chapter_api_call = requests.get(
			f"{api_url}/books/{self.asin}/chapters"
		)
		chapter_api_call.raise_for_status()

		self.metadata_dict = book_api_call.json()
		self.metadata_dict['chapter_info'] = chapter_api_call.json()
		return self.metadata_dict

	def normalize(self) -> dict:
		"""
		Normalize raw Audnex JSON into internal metadata dict format.

		Converts the API response into the fixed-key dict shape used by
		sidecar_parser and merger. Keys: title, subtitle, authors, narrators,
		length, release_date, publisher, language, description, cover_url,
		chapters.

		Returns:
			Dict with all known keys, values set to None or [] when absent.

		Raises:
			RuntimeError: if metadata_dict is None (fetch_api_data not called).
		"""
		if self.metadata_dict is None:
			raise RuntimeError(
				"normalize() called before fetch_api_data(). "
				"Call fetch_api_data(api_url) first."
			)

		result = {
			"title": None,
			"subtitle": None,
			"authors": None,
			"narrators": None,
			"length": None,
			"release_date": None,
			"publisher": None,
			"language": None,
			"description": None,
			"cover_url": None,
			"chapters": [],
		}

		# Extract title
		if "title" in self.metadata_dict:
			result["title"] = self.metadata_dict["title"]

		# Extract subtitle
		if "subtitle" in self.metadata_dict and self.metadata_dict["subtitle"]:
			result["subtitle"] = self.metadata_dict["subtitle"]

		# Extract authors (array of {name: ...})
		if "authors" in self.metadata_dict:
			authors_list = self.metadata_dict["authors"]
			if isinstance(authors_list, list) and authors_list:
				result["authors"] = [a.get("name") for a in authors_list if "name" in a]
				if not result["authors"]:
					result["authors"] = None

		# Extract narrators (array of {name: ...})
		if "narrators" in self.metadata_dict:
			narrators_list = self.metadata_dict["narrators"]
			if isinstance(narrators_list, list) and narrators_list:
				result["narrators"] = [n.get("name") for n in narrators_list if "name" in n]
				if not result["narrators"]:
					result["narrators"] = None

		# Extract length (duration string)
		if "runtimeLengthMs" in self.metadata_dict:
			result["length"] = self.ms_to_timestamp(
				self.metadata_dict["runtimeLengthMs"]
			)

		# Extract release date
		if "releaseDate" in self.metadata_dict:
			result["release_date"] = self.metadata_dict["releaseDate"]

		# Extract publisher
		if "publisher" in self.metadata_dict:
			result["publisher"] = self.metadata_dict["publisher"]

		# Extract language
		if "language" in self.metadata_dict:
			result["language"] = self.metadata_dict["language"]

		# Extract description
		if "description" in self.metadata_dict:
			result["description"] = self.metadata_dict["description"]

		# Extract cover URL (image -> cover_url)
		if "image" in self.metadata_dict:
			result["cover_url"] = self.metadata_dict["image"]

		# Extract chapters if accurate
		chapter_info = self.metadata_dict.get("chapter_info", {})
		if (chapter_info.get("isAccurate") is True and
			"chapters" in chapter_info):
			chapters_list = chapter_info["chapters"]
			result["chapters"] = [
				{
					"title": ch.get("title"),
					"start_offset_ms": ch.get("startOffsetMs"),
				}
				for ch in chapters_list
				if "title" in ch and "startOffsetMs" in ch
			]

		return result
