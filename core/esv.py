"""Zero-Dependency ESV API Client & Crossway Legal Compliance Module.

Implementation per ADR-003 (Zero External Dependencies) and ADR-041:
- Zero-dependency HTTP client targeting https://api.esv.org/v3/passage/text/ via standard library `urllib.request`.
- Environment & config file discovery for `ESV_API_KEY`.
- Crossway Terms of Service compliance:
  * Ephemeral 500-verse LRU cache management.
  * Mandatory legal attribution notices and links ((ESV) - www.esv.org).
- Resilient response parsing converting ESV API JSON payloads into canonical `VerseRecord` objects.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import OpenerDirector, Request, build_opener
from typing import Any, Dict, List, Optional, Sequence, Union

from core.reference import (
    BOOKS,
    Reference,
    canonical_id_to_triple,
    parse_reference,
    verse_canonical_id,
)

# Base repository root directory
REPO_ROOT = Path(__file__).resolve().parent.parent

# Crossway ESV API Endpoints & Configuration
ESV_API_BASE_URL = "https://api.esv.org/v3/passage/text/"

DEFAULT_TRANSLATION = "ESV"
FALLBACK_TRANSLATION = "WEB"
ESV_MAX_CACHE_VERSES = 500  # Strict Crossway legal compliance limit

# Crossway Legal Attribution & Copyright Notices
ESV_SHORT_ATTRIBUTION = "(ESV) - www.esv.org"
ESV_ATTRIBUTION_URL = "https://www.esv.org"
ESV_FULL_COPYRIGHT = (
    "Scripture quotations are from the ESV® Bible "
    "(The Holy Bible, English Standard Version®), copyright © 2001 by Crossway, "
    "a publishing ministry of Good News Publishers. Used by permission. "
    "All rights reserved. The Holy Bible, English Standard Version, is available on "
    "the Internet at esv.org."
)
ESV_COPYRIGHT_NOTICE = (
    "Scripture quotations marked (ESV) are from the ESV® Bible, "
    "copyright © 2001 by Crossway."
)


def _utc_now_iso() -> str:
    """Return current UTC ISO-8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


# --- Exception Hierarchy ---


class ESVError(Exception):
    """Base exception for all ESV API and caching operations."""


class ESVAuthError(ESVError):
    """Raised when ESV API key is missing, unauthorized, or rejected."""


class ESVRateLimitError(ESVError):
    """Raised when ESV API rate limit (HTTP 429) is exceeded."""


class ESVNetworkError(ESVError):
    """Raised on network failures, connection drops, or timeouts."""


class ESVParseError(ESVError):
    """Raised when the API returns an unexpected or malformed payload."""


# --- API Key Discovery ---


def get_esv_api_key(explicit_key: Optional[str] = None) -> Optional[str]:
    """Resolve ESV API key from explicit argument, environment, or configuration files.

    Search order:
    1. explicit_key parameter (if non-empty)
    2. ESV_API_KEY environment variable
    3. .env file in repository root or current working directory
    4. config/esv_api_key.txt in repository root
    5. ~/.config/bible/esv_api_key

    Returns:
        Cleaned API key string if found, else None.
    """
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()

    env_val = os.environ.get("ESV_API_KEY")
    if env_val and env_val.strip():
        return env_val.strip()

    # In hermetic test mode, do not read local developer secrets from disk unless explicitly passed
    if os.environ.get("BIBLE_TEST_MODE") == "1":
        return None

    # Search potential file paths

    candidate_paths: List[Path] = [
        Path.cwd() / ".env",
        REPO_ROOT / ".env",
        REPO_ROOT / "config" / "esv_api_key.txt",
        Path.home() / ".config" / "bible" / "esv_api_key",
    ]


    for p in candidate_paths:
        try:
            if p.is_file():
                content = p.read_text(encoding="utf-8")
                if p.name == ".env":
                    for line in content.splitlines():
                        line = line.strip()
                        if line.startswith("ESV_API_KEY="):
                            val = line.split("=", 1)[1].strip().strip("'\"")
                            if val:
                                return val
                else:
                    val = content.strip()
                    if val:
                        return val
        except Exception:
            continue

    return None


def format_esv_attribution(style: str = "short") -> str:
    """Return formatted Crossway legal attribution string.

    Args:
        style: 'short' (default: '(ESV) - www.esv.org'),
               'notice' (single-sentence Crossway permission notice),
               'full' (complete official copyright statement).
    """
    s = style.lower().strip()
    if s == "short":
        return ESV_SHORT_ATTRIBUTION
    elif s == "notice":
        return ESV_COPYRIGHT_NOTICE
    elif s == "full":
        return ESV_FULL_COPYRIGHT
    return ESV_SHORT_ATTRIBUTION


# --- ESV Response Parser ---


def parse_esv_passage_text(
    passages: Sequence[str],
    requested_ref: Optional[Reference] = None,
    parsed_ranges: Optional[Sequence[Sequence[int]]] = None,
) -> List[Dict[str, Any]]:
    """Parse text array returned by ESV API into structured verse dictionaries.

    Handles bracketed verse markers (e.g. '[16] For God so loved... [17] For God did not...'),
    cross-chapter passages, single verses, poetry lines, and unbracketed text.

    Args:
        passages: List of passage text strings returned by the ESV API.
        requested_ref: Optional canonical Reference object for context.
        parsed_ranges: Optional [[start_canonical_id, end_canonical_id], ...] from ESV API.

    Returns:
        List of dictionaries with keys:
            book_id, chapter, verse, text, canonical_verse_id
    """
    if not passages:
        return []

    combined_text = "\n\n".join(p for p in passages if p)
    if not combined_text.strip():
        return []

    # Determine default initial book and chapter
    initial_book_id = 1
    initial_chapter = 1
    initial_verse = 1

    if requested_ref:
        initial_book_id = requested_ref.book.number
        initial_chapter = requested_ref.start_chapter
        initial_verse = requested_ref.start_verse or 1
    elif parsed_ranges and len(parsed_ranges) > 0 and len(parsed_ranges[0]) > 0:
        start_cid = parsed_ranges[0][0]
        initial_book_id, initial_chapter, initial_verse = canonical_id_to_triple(start_cid)

    # Search for bracketed verse markers: '[16]', '[1]', etc.
    bracket_matches = list(re.finditer(r"\[(\d+)\]", combined_text))

    results: List[Dict[str, Any]] = []

    if not bracket_matches:
        # No bracket markers found; entire text represents the requested passage / single verse
        clean_text = re.sub(r"\s+", " ", combined_text).strip()
        cid = verse_canonical_id(initial_book_id, initial_chapter, initial_verse)
        results.append({
            "book_id": initial_book_id,
            "chapter": initial_chapter,
            "verse": initial_verse,
            "text": clean_text,
            "canonical_verse_id": cid,
        })
        return results

    current_book_id = initial_book_id
    current_chapter = initial_chapter
    prev_verse_num = 0

    for idx, match in enumerate(bracket_matches):
        verse_num = int(match.group(1))
        content_start = match.end()
        content_end = (
            bracket_matches[idx + 1].start()
            if idx + 1 < len(bracket_matches)
            else len(combined_text)
        )

        raw_verse_text = combined_text[content_start:content_end]
        clean_verse_text = re.sub(r"\s+", " ", raw_verse_text).strip()

        # Handle chapter boundary crossing: if verse number dropped or equal to previous,
        # we have crossed into the next chapter
        if prev_verse_num > 0 and verse_num <= prev_verse_num:
            current_chapter += 1

        prev_verse_num = verse_num
        cid = verse_canonical_id(current_book_id, current_chapter, verse_num)

        results.append({
            "book_id": current_book_id,
            "chapter": current_chapter,
            "verse": verse_num,
            "text": clean_verse_text,
            "canonical_verse_id": cid,
        })

    return results


# --- Zero-Dependency ESV API Client ---


class ESVClient:
    """Zero-dependency HTTP Client for the official Crossway ESV API.

    Targets https://api.esv.org/v3/passage/text/ using standard library `urllib.request`.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = ESV_API_BASE_URL,
        timeout: float = 5.0,
        user_agent: str = "BibleEngine/1.0 (+https://github.com/mrmarkwell/bible)",
        opener: Optional[OpenerDirector] = None,
    ) -> None:
        """Initialize ESV API Client.

        Args:
            api_key: Optional explicit API key. If omitted, resolved via `get_esv_api_key`.
            base_url: API endpoint URL (default: https://api.esv.org/v3/passage/text/).
            timeout: HTTP request timeout in seconds (default: 5.0s).
            user_agent: User-Agent header string.
            opener: Optional custom OpenerDirector for hermetic test mocking.
        """
        self.api_key = get_esv_api_key(api_key)
        self.base_url = base_url
        self.timeout = timeout
        self.user_agent = user_agent
        self._opener = opener or build_opener()

    def is_available(self) -> bool:
        """Return True if an API key is configured."""
        return bool(self.api_key and self.api_key.strip())

    def fetch_passage_raw(
        self,
        query: str,
        include_verse_numbers: bool = True,
        include_first_verse_numbers: bool = True,
        include_headings: bool = False,
        include_footnotes: bool = False,
    ) -> Dict[str, Any]:
        """Execute HTTP request against ESV API and return parsed JSON payload.

        Args:
            query: Canonical scripture citation (e.g. 'John 3:16', 'Romans 8:28-30').
            include_verse_numbers: Include bracketed verse markers.
            include_first_verse_numbers: Include marker for verse 1.
            include_headings: Include pericope section headings.
            include_footnotes: Include footnote markers and bodies.

        Returns:
            Dictionary matching the ESV API JSON schema.

        Raises:
            ESVAuthError: If API key is missing or invalid (HTTP 401/403).
            ESVRateLimitError: If rate limit exceeded (HTTP 429).
            ESVNetworkError: On timeout, DNS failure, or connection drop.
            ESVParseError: If response body is not valid JSON.
        """
        if not self.is_available():
            raise ESVAuthError(
                "ESV API key is not configured. Set the ESV_API_KEY environment variable "
                "or create a .env / config/esv_api_key.txt file with your Crossway API key."
            )

        params = {
            "q": query.strip(),
            "include-passage-references": "false",
            "include-verse-numbers": "true" if include_verse_numbers else "false",
            "include-first-verse-numbers": "true" if include_first_verse_numbers else "false",
            "include-footnotes": "true" if include_footnotes else "false",
            "include-footnote-body": "false",
            "include-headings": "true" if include_headings else "false",
            "include-short-copyright": "false",
            "include-passage-horizontal-lines": "false",
            "include-heading-horizontal-lines": "false",
            "horizontal-line-length": "0",
            "indent-paragraphs": "0",
            "indent-poetry": "true",
            "indent-poetry-lines": "1",
            "line-length": "0",
        }

        query_string = urlencode(params)
        url = f"{self.base_url}?{query_string}"

        req = Request(
            url,
            headers={
                "Authorization": f"Token {self.api_key}",
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
            method="GET",
        )

        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                status_code = resp.status if hasattr(resp, "status") else resp.getcode()
                raw_bytes = resp.read()
                charset = resp.headers.get_content_charset("utf-8") if resp.headers else "utf-8"
                text = raw_bytes.decode(charset or "utf-8")
        except HTTPError as err:
            if err.code in (401, 403):
                raise ESVAuthError(
                    f"ESV API authentication failed (HTTP {err.code}): invalid or unauthorized API key."
                ) from err
            elif err.code == 429:
                raise ESVRateLimitError(
                    "ESV API rate limit exceeded (HTTP 429). Crossway enforces 60 req/min and 5,000 req/day."
                ) from err
            else:
                raise ESVNetworkError(
                    f"ESV API returned HTTP {err.code}: {err.reason}"
                ) from err
        except URLError as err:
            raise ESVNetworkError(f"ESV API network connection error: {err.reason}") from err
        except (TimeoutError, OSError) as err:
            raise ESVNetworkError(f"ESV API connection timed out after {self.timeout}s: {err}") from err
        except Exception as err:
            raise ESVNetworkError(f"Unexpected error communicating with ESV API: {err}") from err

        try:
            data = json.loads(text)
            if not isinstance(data, dict):
                raise ESVParseError(f"Expected JSON dictionary from ESV API, got {type(data).__name__}")
            return data
        except json.JSONDecodeError as err:
            raise ESVParseError(f"Failed to parse ESV API JSON response: {err}") from err

    def fetch_verses(
        self,
        reference: Union[Reference, str],
        include_headings: bool = False,
    ) -> List[Any]:
        """Fetch and return canonical VerseRecord objects for a given scripture reference.

        Args:
            reference: Reference object or canonical citation string.
            include_headings: Whether to preserve headings.

        Returns:
            List of VerseRecord objects with translation_id='ESV'.
        """
        from core.db import VerseRecord

        if isinstance(reference, str):
            ref = parse_reference(reference)
        else:
            ref = reference

        data = self.fetch_passage_raw(
            ref.format(),
            include_verse_numbers=True,
            include_first_verse_numbers=True,
            include_headings=include_headings,
        )

        passages = data.get("passages", [])
        parsed_ranges = data.get("parsed", [])

        parsed_items = parse_esv_passage_text(
            passages,
            requested_ref=ref,
            parsed_ranges=parsed_ranges,
        )

        records: List[VerseRecord] = []
        for item in parsed_items:
            b = BOOKS.get(item["book_id"])
            b_name = b.name if b else f"Book_{item['book_id']}"
            osis = f"{b.osis}.{item['chapter']}.{item['verse']}" if b else ""

            records.append(
                VerseRecord(
                    id=None,
                    translation_id="ESV",
                    book_id=item["book_id"],
                    book_name=b_name,
                    chapter=item["chapter"],
                    verse=item["verse"],
                    subverse="",
                    text=item["text"],
                    osis_ref=osis,
                    canonical_verse_id=item["canonical_verse_id"],
                )
            )

        return records
