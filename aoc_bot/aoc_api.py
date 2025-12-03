"""Advent of Code API client."""

import logging
import time
from typing import Any, Dict, Optional

import requests


logger = logging.getLogger(__name__)


class AoCAPIError(Exception):
    """Base exception for AoC API errors."""

    pass


class AoCAPIClient:
    """Client for interacting with Advent of Code private leaderboard API."""

    def __init__(self, session_cookie: str, year: int, leaderboard_id: str):
        """Initialize the AoC API client.

        Args:
            session_cookie: AoC session cookie (e.g., 'session=abc123...')
            year: Advent of Code event year
            leaderboard_id: Private leaderboard ID
        """
        self.session_cookie = session_cookie
        self.year = year
        self.leaderboard_id = leaderboard_id
        self.base_url = (
            f"https://adventofcode.com/{year}/leaderboard/private/view/{leaderboard_id}.json"
        )
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with proper headers.

        Returns:
            Configured requests.Session.
        """
        session = requests.Session()
        session.headers.update({
            "User-Agent": "AoC-Telegram-Bot (https://github.com/yourusername/AoC_Telegram_Bot)",
            "Cookie": self.session_cookie,
        })
        return session

    def fetch_leaderboard(self) -> Dict[str, Any]:
        """Fetch current leaderboard data from AoC API.

        Returns:
            Parsed JSON response with leaderboard data.

        Raises:
            AoCAPIError: If the request fails.
        """
        return self._make_request()

    def _make_request(self) -> Dict[str, Any]:
        """Make HTTP request to AoC API with retry logic.

        Returns:
            Parsed JSON response.

        Raises:
            AoCAPIError: If request fails after retries.
        """
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                logger.debug(f"Fetching leaderboard (attempt {attempt + 1}/{max_retries})...")
                response = self.session.get(self.base_url, timeout=10)

                # Handle specific HTTP errors
                if response.status_code == 401:
                    raise AoCAPIError(
                        "Authentication failed. Check your session cookie."
                    )
                elif response.status_code == 404:
                    raise AoCAPIError(
                        f"Leaderboard {self.leaderboard_id} not found. Check the ID."
                    )
                elif response.status_code == 429:
                    # Rate limited - wait longer before retrying
                    retry_delay = min(60, retry_delay * 2)
                    logger.warning(
                        f"Rate limited by AoC API. Waiting {retry_delay}s before retry..."
                    )
                    time.sleep(retry_delay)
                    continue
                elif response.status_code >= 500:
                    # Server error - retry
                    logger.warning(
                        f"AoC server error ({response.status_code}). Retrying..."
                    )
                    time.sleep(retry_delay)
                    continue
                elif response.status_code >= 400:
                    # Other client error
                    raise AoCAPIError(
                        f"HTTP {response.status_code}: {response.text}"
                    )

                # Success
                response.raise_for_status()
                data = response.json()
                logger.debug("Successfully fetched leaderboard")
                return data

            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                raise AoCAPIError("Request timeout after retries")

            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                raise AoCAPIError(f"Request failed after {max_retries} attempts: {e}")

            except ValueError as e:
                # JSON parsing error
                raise AoCAPIError(f"Failed to parse JSON response: {e}")

        raise AoCAPIError("Failed to fetch leaderboard after all retries")
