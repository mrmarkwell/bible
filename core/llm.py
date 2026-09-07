"""Zero-Dependency Google Gemini LLM Client & Passage Context Engine.

Implementation per ADR-003 (Zero External Dependencies), ADR-006, and ADR-041:
- Zero-dependency HTTP REST client targeting Google Gemini API endpoints via standard library `urllib.request`.
- Environment and configuration file discovery for `GEMINI_API_KEY` (and `GOOGLE_API_KEY`).
- Primary model `gemini-2.5-pro` with automatic, seamless fallback to `gemini-2.0-flash` on 404/429/transient failure.
- Configurable retry loop with exponential backoff for transient errors (HTTP 500/503/timeouts).
- Streaming response generation parsing Server-Sent Events (SSE) chunks.
- Structured JSON generation mode (`response_mime_type="application/json"`).
- Embeddings generation (`embed_content`, `batch_embed_contents`) targeting `text-embedding-004`.
- Passage context builder defaulting to ESV via `core.esv` / `core.db` with Crossway legal compliance (ADR-041)
  and graceful offline fallback to WEB.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from urllib import request as _urllib_request
from urllib.error import HTTPError, URLError
from urllib.request import OpenerDirector, Request
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple, Union

from core.db import DEFAULT_DB_PATH, Database, VerseRecord
from core.esv import (
    DEFAULT_TRANSLATION,
    FALLBACK_TRANSLATION,
    format_esv_attribution,
)
from core.pericopes import PericopeService
from core.reference import Reference, parse_reference

# Default Models & API Endpoints
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"
FALLBACK_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_EMBEDDING_MODEL = "text-embedding-004"
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

SUPPORTED_MODELS = (
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
)


def _utc_now_iso() -> str:
    """Return current UTC ISO-8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


# ==============================================================================
# Exception Hierarchy
# ==============================================================================


class LLMError(Exception):
    """Base exception for all LLM and Gemini API operations."""


class LLMAuthError(LLMError):
    """Raised when the Gemini API key is missing, unauthorized, or invalid."""


class LLMRateLimitError(LLMError):
    """Raised when Gemini API rate limit or quota is exceeded (HTTP 429)."""


class LLMNetworkError(LLMError):
    """Raised on network connection drop, timeout, or DNS resolution failure."""


class LLMResponseError(LLMError):
    """Raised when Gemini API returns an error response, blocked content, or invalid schema."""


class LLMModelNotFoundError(LLMError):
    """Raised when the requested model endpoint is not found (HTTP 404)."""


# ==============================================================================
# API Key Discovery
# ==============================================================================


def get_gemini_api_key(explicit_key: Optional[str] = None) -> Optional[str]:
    """Resolve Google Gemini API key from parameters, environment, or configuration files.

    Search order:
    1. explicit_key parameter (if non-empty)
    2. GEMINI_API_KEY environment variable
    3. GOOGLE_API_KEY environment variable
    4. .env file in repository root or current working directory
    5. config/gemini_api_key.txt in repository root
    6. ~/.config/bible/gemini_api_key

    Returns:
        Cleaned API key string if found, else None.
    """
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()

    for env_var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(env_var)
        if val and val.strip():
            return val.strip()

    # Search potential configuration file paths
    candidate_paths: List[Path] = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent / "config" / "gemini_api_key.txt",
        Path(__file__).resolve().parent.parent / "config" / "google_api_key.txt",
        Path.home() / ".config" / "bible" / "gemini_api_key",
        Path.home() / ".config" / "bible" / "google_api_key",
    ]

    for p in candidate_paths:
        try:
            if p.is_file():
                content = p.read_text(encoding="utf-8")
                if p.name == ".env":
                    for line in content.splitlines():
                        line = line.strip()
                        for prefix in ("GEMINI_API_KEY=", "GOOGLE_API_KEY="):
                            if line.startswith(prefix):
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


# ==============================================================================
# Data Structures & Context DTOs
# ==============================================================================


@dataclass(frozen=True)
class ChatMessage:
    """Single turn in a conversational dialogue."""

    role: str  # 'user', 'model', or 'system'
    content: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize message to dictionary."""
        return {"role": self.role, "content": self.content}

    def to_gemini_part(self) -> Dict[str, Any]:
        """Convert to Gemini API content payload object."""
        # In Gemini REST API, system instructions are passed separately,
        # while user/model turns are role 'user' and 'model'.
        gemini_role = "user" if self.role in ("user", "system") else "model"
        return {
            "role": gemini_role,
            "parts": [{"text": self.content}],
        }


@dataclass
class GenerationConfig:
    """Hyperparameters and formatting options for Gemini generation."""

    temperature: float = 0.7
    top_p: Optional[float] = 0.95
    top_k: Optional[int] = 40
    max_output_tokens: Optional[int] = 8192
    stop_sequences: Optional[List[str]] = None
    response_mime_type: Optional[str] = None
    response_schema: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize configuration to Gemini REST payload dictionary."""
        d: Dict[str, Any] = {"temperature": self.temperature}
        if self.top_p is not None:
            d["topP"] = self.top_p
        if self.top_k is not None:
            d["topK"] = self.top_k
        if self.max_output_tokens is not None:
            d["maxOutputTokens"] = self.max_output_tokens
        if self.stop_sequences:
            d["stopSequences"] = list(self.stop_sequences)
        if self.response_mime_type:
            d["responseMimeType"] = self.response_mime_type
        if self.response_schema:
            d["responseSchema"] = self.response_schema
        return d


@dataclass
class LLMResponse:
    """Standardized response from Gemini content generation."""

    text: str
    model: str
    finish_reason: Optional[str] = None
    usage: Dict[str, int] = field(default_factory=dict)
    raw_response: Dict[str, Any] = field(default_factory=dict)
    latency_seconds: float = 0.0
    fallback_used: bool = False
    attempts: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize response to dictionary."""
        return {
            "text": self.text,
            "model": self.model,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
            "latency_seconds": round(self.latency_seconds, 3),
            "fallback_used": self.fallback_used,
            "attempts": self.attempts,
        }


@dataclass
class StreamChunk:
    """Incremental chunk emitted during streaming response generation."""

    text: str
    finish_reason: Optional[str] = None
    raw_chunk: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PassageContext:
    """Structured scripture passage context formatted for LLM prompts."""

    reference: str
    translation: str
    verses: List[VerseRecord]
    text: str
    attribution: str
    fallback_used: bool = False
    fallback_translation: Optional[str] = None
    pericope: Optional[str] = None

    def format_prompt_block(self, include_attribution: bool = True) -> str:
        """Format scripture into a clean, hermeneutically focused markdown block."""
        lines: List[str] = []
        if self.pericope:
            lines.append(f"### {self.pericope}")
        lines.append(f"**Passage**: {self.reference} ({self.translation})")
        if self.fallback_used and self.fallback_translation:
            lines.append(f"*(Note: Translated from fallback {self.fallback_translation})*")
        lines.append("")
        for v in self.verses:
            lines.append(f"[{v.verse}] {v.text}")
        if include_attribution and self.attribution:
            lines.append("")
            lines.append(f"*{self.attribution}*")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize passage context to dictionary."""
        return {
            "reference": self.reference,
            "translation": self.translation,
            "text": self.text,
            "attribution": self.attribution,
            "fallback_used": self.fallback_used,
            "fallback_translation": self.fallback_translation,
            "pericope": self.pericope,
            "verse_count": len(self.verses),
            "verses": [
                {
                    "chapter": v.chapter,
                    "verse": v.verse,
                    "text": v.text,
                    "canonical_id": v.canonical_verse_id,
                }
                for v in self.verses
            ],
        }


# ==============================================================================
# Passage Context Builder
# ==============================================================================


def build_passage_context(
    reference: Union[str, Reference],
    db: Optional[Database] = None,
    translation: str = DEFAULT_TRANSLATION,
    fallback_translation: str = FALLBACK_TRANSLATION,
    include_attribution: bool = True,
    include_pericope: bool = True,
    allow_network: bool = True,
) -> PassageContext:
    """Build structured scripture passage context defaulting to ESV with Crossway compliance.

    Fulfills Task 6.1 and ADR-041:
    - Default translation is ESV.
    - Resolves from SQLite database (which transparently checks the 500-verse LRU cache,
      fetches from ESV API if needed and authorized, or cascades gracefully to WEB).
    - Injects Crossway legal attribution ('(ESV) - www.esv.org') for ESV verses.
    - Injects pericope headings when available.

    Args:
        reference: Scripture citation string (e.g. 'John 3:16-17') or Reference object.
        db: Optional active Database instance. If None, opens default database.
        translation: Preferred translation (defaults to 'ESV').
        fallback_translation: Fallback translation if preferred is unavailable (defaults to 'WEB').
        include_attribution: Whether to include attribution string.
        include_pericope: Whether to query pericope heading.
        allow_network: Whether to allow ESV API network fetch if not cached.

    Returns:
        Populated PassageContext ready for LLM prompt assembly.
    """
    ref_obj = parse_reference(reference) if isinstance(reference, str) else reference

    def _query_db(database: Database) -> PassageContext:
        verses, eff_trans, fallback_used = database.get_verses_with_fallback(
            ref_obj,
            translation_id=translation,
            fallback_id=fallback_translation,
            allow_network=allow_network,
        )

        pericope_heading: Optional[str] = None
        if include_pericope:
            try:
                pericope_svc = PericopeService(database)
                pericopes = pericope_svc.get_pericopes_for_reference(ref_obj)
                if pericopes:
                    pericope_heading = pericopes[0].title
            except Exception:
                pass

        # Determine attribution
        attribution_str = ""
        if eff_trans.upper() == "ESV":
            attribution_str = format_esv_attribution("short")
        elif eff_trans.upper() == "WEB":
            attribution_str = "World English Bible (Public Domain)"
        elif eff_trans.upper() == "KJV":
            attribution_str = "King James Version (Public Domain)"
        else:
            attribution_str = f"Translation: {eff_trans}"

        combined_text = " ".join(v.text for v in verses).strip()

        return PassageContext(
            reference=ref_obj.format(),
            translation=eff_trans,
            verses=verses,
            text=combined_text,
            attribution=attribution_str,
            fallback_used=fallback_used,
            fallback_translation=fallback_translation if fallback_used else None,
            pericope=pericope_heading,
        )

    if db is not None:
        return _query_db(db)

    # Use default database connection
    with Database(DEFAULT_DB_PATH, auto_init=False) as default_db:
        return _query_db(default_db)


# ==============================================================================
# Google Gemini REST Client
# ==============================================================================


class GeminiClient:
    """Zero-dependency Google Gemini REST API client.

    Strictly complies with ADR-003:
    - Pure Python 3 standard library (`urllib.request`, `json`, `os`, `time`).
    - Defaults to `gemini-2.5-pro` with automatic fallback to `gemini-2.0-flash`.
    - Implements retry loop with exponential backoff on transient errors.
    - Supports unary generation, streaming generation, JSON output mode, and embeddings.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_GEMINI_MODEL,
        fallback_model: Optional[str] = FALLBACK_GEMINI_MODEL,
        timeout: float = 45.0,
        max_retries: int = 2,
        backoff_factor: float = 1.5,
        base_url: str = GEMINI_API_BASE_URL,
        opener: Optional[OpenerDirector] = None,
    ) -> None:
        """Initialize the Gemini client.

        Args:
            api_key: Optional explicit Gemini API key. If omitted, resolved automatically.
            model: Default primary model identifier (defaults to 'gemini-2.5-pro').
            fallback_model: Fallback model identifier on 404/429/failure (defaults to 'gemini-2.0-flash').
            timeout: HTTP request timeout in seconds.
            max_retries: Maximum number of retry attempts for transient errors.
            backoff_factor: Multiplier for exponential backoff between retries.
            base_url: Base URL for Gemini models API.
            opener: Optional custom urllib OpenerDirector (useful for testing and hermetic mocks).
        """
        self.api_key = get_gemini_api_key(api_key)
        self.model = model.strip() if model else DEFAULT_GEMINI_MODEL
        self.fallback_model = fallback_model.strip() if fallback_model else None
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.backoff_factor = backoff_factor
        self.base_url = base_url.rstrip("/")
        self._opener = opener

    def _open(self, req: Request, timeout: float):
        """Execute request using custom opener if supplied, otherwise standard urlopen."""
        if self._opener is not None:
            return self._opener.open(req, timeout=timeout)
        return _urllib_request.urlopen(req, timeout=timeout)

    def is_available(self) -> bool:
        """Return True if a valid Gemini API key is configured."""
        return bool(self.api_key and self.api_key.strip())

    # --- Payload Construction Helpers ---

    def _prepare_request_body(
        self,
        prompt: Union[str, Sequence[ChatMessage]],
        system_instruction: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> Dict[str, Any]:
        """Construct JSON dictionary payload matching the Gemini REST API contract."""
        contents: List[Dict[str, Any]] = []

        if isinstance(prompt, str):
            contents.append({
                "role": "user",
                "parts": [{"text": prompt}],
            })
        else:
            for msg in prompt:
                if msg.role == "system" and not system_instruction:
                    system_instruction = msg.content
                else:
                    contents.append(msg.to_gemini_part())

        payload: Dict[str, Any] = {"contents": contents}

        if system_instruction and system_instruction.strip():
            payload["system_instruction"] = {
                "parts": [{"text": system_instruction.strip()}]
            }

        if config is not None:
            payload["generationConfig"] = config.to_dict()

        return payload

    def _build_http_request(
        self,
        endpoint_url: str,
        data: Optional[bytes] = None,
        method: str = "POST",
    ) -> Request:
        """Create urllib Request with required Gemini authentication headers."""
        if not self.is_available():
            raise LLMAuthError(
                "Gemini API key is not configured. Set the GEMINI_API_KEY (or GOOGLE_API_KEY) "
                "environment variable or provide a key in .env or config/gemini_api_key.txt."
            )

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "BibleEngine/1.0 (Zero-Dependency Python stdlib)",
            "x-goog-api-key": self.api_key,  # Standard Google API header
        }

        return Request(
            endpoint_url,
            data=data,
            headers=headers,
            method=method,
        )

    # --- HTTP Execution with Retries ---

    def _post_json_with_retries(
        self,
        endpoint_url: str,
        payload_dict: Dict[str, Any],
        model_name: str,
    ) -> Tuple[Dict[str, Any], int]:
        """Execute HTTP POST with JSON payload, exponential backoff retries, and error mapping.

        Returns:
            Tuple of (parsed_json_dict, total_attempts_made).
        """
        payload_bytes = json.dumps(payload_dict).encode("utf-8")
        attempts = 0
        current_delay = 0.05  # Short initial delay for fast hermetic tests

        while attempts <= self.max_retries:
            attempts += 1
            req = self._build_http_request(endpoint_url, data=payload_bytes, method="POST")

            try:
                with self._open(req, timeout=self.timeout) as resp:
                    raw_bytes = resp.read()
                    charset = "utf-8"
                    if hasattr(resp, "headers") and resp.headers and hasattr(resp.headers, "get_content_charset"):
                        cs = resp.headers.get_content_charset()
                        if isinstance(cs, str) and cs.strip():
                            charset = cs.strip()
                    text = raw_bytes.decode(charset)
                    return json.loads(text), attempts

            except HTTPError as err:
                error_body = ""
                try:
                    error_body = err.read().decode("utf-8")
                except Exception:
                    pass

                # Specific HTTP status handling
                if err.code in (401, 403):
                    raise LLMAuthError(
                        f"Gemini API authentication failed (HTTP {err.code}): {error_body or err.reason}"
                    ) from err

                if err.code == 404:
                    raise LLMModelNotFoundError(
                        f"Gemini model '{model_name}' not found (HTTP 404): {error_body or err.reason}"
                    ) from err

                if err.code == 429:
                    if attempts <= self.max_retries:
                        time.sleep(current_delay)
                        current_delay *= self.backoff_factor
                        continue
                    raise LLMRateLimitError(
                        f"Gemini API rate limit exceeded (HTTP 429): {error_body or err.reason}"
                    ) from err

                # Server errors: 500, 502, 503, 504 are retryable
                if err.code in (500, 502, 503, 504) and attempts <= self.max_retries:
                    time.sleep(current_delay)
                    current_delay *= self.backoff_factor
                    continue

                raise LLMResponseError(
                    f"Gemini API returned HTTP {err.code} for model '{model_name}': {error_body or err.reason}"
                ) from err

            except (URLError, TimeoutError, OSError) as err:
                if attempts <= self.max_retries:
                    time.sleep(current_delay)
                    current_delay *= self.backoff_factor
                    continue
                raise LLMNetworkError(
                    f"Network error communicating with Gemini API: {err}"
                ) from err

            except json.JSONDecodeError as err:
                raise LLMResponseError(
                    f"Invalid JSON received from Gemini API: {err}"
                ) from err

        raise LLMNetworkError(f"Exceeded max retries ({self.max_retries}) connecting to Gemini API.")

    # --- Public Generation Methods ---

    def generate(
        self,
        prompt: Union[str, Sequence[ChatMessage]],
        system_instruction: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Generate content from Gemini, automatically falling back to secondary model if needed.

        Args:
            prompt: Text prompt string or sequence of ChatMessage objects.
            system_instruction: Optional high-level system instruction/prompt.
            config: GenerationConfig parameters (temperature, max tokens, etc.).
            model: Target model identifier. Defaults to client's primary model.

        Returns:
            LLMResponse containing generated text, token usage, and latency.
        """
        primary_model = model.strip() if model else self.model
        payload = self._prepare_request_body(prompt, system_instruction, config)

        models_to_try = [primary_model]
        if self.fallback_model and self.fallback_model != primary_model:
            models_to_try.append(self.fallback_model)

        last_error: Optional[Exception] = None
        total_attempts = 0
        start_time = time.time()

        for idx, candidate_model in enumerate(models_to_try):
            endpoint = f"{self.base_url}/{candidate_model}:generateContent"
            is_fallback = idx > 0

            try:
                res_data, attempts = self._post_json_with_retries(endpoint, payload, candidate_model)
                total_attempts += attempts
                latency = time.time() - start_time

                # Parse response candidates
                candidates = res_data.get("candidates", [])
                if not candidates:
                    # Check for prompt feedback block
                    prompt_feedback = res_data.get("promptFeedback", {})
                    block_reason = prompt_feedback.get("blockReason")
                    if block_reason:
                        raise LLMResponseError(f"Prompt blocked by Gemini safety filters: {block_reason}")
                    raise LLMResponseError("Gemini API returned 0 candidates in response.")

                first_candidate = candidates[0]
                content = first_candidate.get("content", {})
                parts = content.get("parts", [])
                finish_reason = first_candidate.get("finishReason")

                if not parts:
                    if finish_reason:
                        raise LLMResponseError(
                            f"Gemini generation stopped with reason '{finish_reason}' without text output."
                        )
                    raise LLMResponseError("Gemini candidate contains empty content parts.")

                # Extract text from parts
                text = "".join(part.get("text", "") for part in parts).strip()

                # Extract usage metadata
                usage_raw = res_data.get("usageMetadata", {})
                usage = {
                    "prompt_tokens": usage_raw.get("promptTokenCount", 0),
                    "candidate_tokens": usage_raw.get("candidatesTokenCount", 0),
                    "total_tokens": usage_raw.get("totalTokenCount", 0),
                }

                return LLMResponse(
                    text=text,
                    model=candidate_model,
                    finish_reason=finish_reason,
                    usage=usage,
                    raw_response=res_data,
                    latency_seconds=latency,
                    fallback_used=is_fallback,
                    attempts=total_attempts,
                )

            except (LLMModelNotFoundError, LLMRateLimitError, LLMNetworkError, LLMResponseError) as exc:
                last_error = exc
                # If we have a fallback model left to try, proceed to next iteration
                if idx + 1 < len(models_to_try):
                    continue
                raise

        raise last_error or LLMError("Gemini content generation failed.")

    def generate_stream(
        self,
        prompt: Union[str, Sequence[ChatMessage]],
        system_instruction: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
        model: Optional[str] = None,
    ) -> Iterator[StreamChunk]:
        """Stream content incrementally from Gemini using Server-Sent Events (SSE).

        Args:
            prompt: Text prompt string or sequence of ChatMessage objects.
            system_instruction: Optional system instruction.
            config: GenerationConfig parameters.
            model: Target model identifier.

        Yields:
            StreamChunk objects with incremental text pieces.
        """
        active_model = model.strip() if model else self.model
        payload = self._prepare_request_body(prompt, system_instruction, config)
        payload_bytes = json.dumps(payload).encode("utf-8")

        endpoint = f"{self.base_url}/{active_model}:streamGenerateContent?alt=sse"
        req = self._build_http_request(endpoint, data=payload_bytes, method="POST")

        try:
            with self._open(req, timeout=self.timeout) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                    line_clean = line.strip()

                    if not line_clean:
                        continue

                    if line_clean.startswith("data:"):
                        data_content = line_clean[5:].strip()
                        if data_content == "[DONE]":
                            break

                        try:
                            chunk_json = json.loads(data_content)
                        except json.JSONDecodeError:
                            continue

                        candidates = chunk_json.get("candidates", [])
                        if candidates:
                            cand = candidates[0]
                            content = cand.get("content", {})
                            parts = content.get("parts", [])
                            finish_reason = cand.get("finishReason")
                            text_piece = "".join(part.get("text", "") for part in parts)

                            if text_piece or finish_reason:
                                yield StreamChunk(
                                    text=text_piece,
                                    finish_reason=finish_reason,
                                    raw_chunk=chunk_json,
                                )

        except HTTPError as err:
            error_body = ""
            try:
                error_body = err.read().decode("utf-8")
            except Exception:
                pass
            if err.code in (401, 403):
                raise LLMAuthError(f"Gemini stream auth error (HTTP {err.code}): {error_body}") from err
            if err.code == 429:
                raise LLMRateLimitError(f"Gemini stream rate limit (HTTP 429): {error_body}") from err
            raise LLMResponseError(f"Gemini stream HTTP {err.code} error: {error_body}") from err
        except (URLError, TimeoutError, OSError) as err:
            raise LLMNetworkError(f"Gemini stream connection failed: {err}") from err

    def generate_json(
        self,
        prompt: Union[str, Sequence[ChatMessage]],
        schema: Optional[Dict[str, Any]] = None,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
    ) -> Tuple[Dict[str, Any], LLMResponse]:
        """Generate structured JSON adhering to an optional schema.

        Args:
            prompt: User prompt or ChatMessage sequence.
            schema: Optional JSON schema dictionary for output validation.
            system_instruction: Optional system instruction.
            model: Optional model override.
            temperature: Sampling temperature (defaults to 0.2 for deterministic formatting).

        Returns:
            Tuple of (parsed_json_dict, full_LLMResponse).
        """
        cfg = GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
        )

        resp = self.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            config=cfg,
            model=model,
        )

        try:
            clean_text = resp.text.strip()
            # Clean markdown JSON wrapping if present
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()

            parsed = json.loads(clean_text)
            return parsed, resp
        except json.JSONDecodeError as err:
            raise LLMResponseError(
                f"Failed to parse structured JSON from Gemini response: {err}\nResponse was:\n{resp.text}"
            ) from err

    # --- Embeddings Support (Phase 7 Preparation) ---

    def embed_content(
        self,
        text: str,
        model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> List[float]:
        """Compute semantic vector embedding for a text string using Gemini Embeddings API.

        Args:
            text: Text content to embed.
            model: Target embedding model (defaults to 'text-embedding-004').

        Returns:
            List of floating point numbers representing the semantic embedding vector.
        """
        endpoint = f"{self.base_url}/{model}:embedContent"
        payload = {
            "model": f"models/{model}",
            "content": {
                "parts": [{"text": text}]
            },
        }

        res_data, _ = self._post_json_with_retries(endpoint, payload, model)
        embedding_obj = res_data.get("embedding", {})
        values = embedding_obj.get("values", [])
        if not values:
            raise LLMResponseError(f"Gemini embeddings API returned empty values: {res_data}")
        return values

    def batch_embed_contents(
        self,
        texts: Sequence[str],
        model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> List[List[float]]:
        """Compute batch vector embeddings for multiple text snippets in a single HTTP request.

        Args:
            texts: Sequence of text snippets.
            model: Target embedding model (defaults to 'text-embedding-004').

        Returns:
            List of embedding vectors corresponding to the input texts.
        """
        if not texts:
            return []

        endpoint = f"{self.base_url}/{model}:batchEmbedContents"
        requests_list = [
            {
                "model": f"models/{model}",
                "content": {"parts": [{"text": t}]},
            }
            for t in texts
        ]
        payload = {"requests": requests_list}

        res_data, _ = self._post_json_with_retries(endpoint, payload, model)
        embeddings = res_data.get("embeddings", [])
        if len(embeddings) != len(texts):
            raise LLMResponseError(
                f"Batch embeddings count mismatch: expected {len(texts)}, got {len(embeddings)}"
            )

        return [emb.get("values", []) for emb in embeddings]
