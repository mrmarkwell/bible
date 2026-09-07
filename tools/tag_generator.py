#!/usr/bin/env python3
"""Batch Scripture Semantic Tagging Generator & LLM Pipeline.

Zero-dependency implementation (Python 3 standard library only per ADR-003):
- Generates TGC-aligned tagging prompts for single passages, batch lists,
  user favorites, and full books.
- Offline-first: Generates inspection prompts, JSON/JSONL batch files, and applies
  offline LLM response payloads to SQLite without requiring active network connectivity.
- Online capability: Integrates directly with Google Gemini REST API
  (gemini-2.5-pro / gemini-2.0-flash) using standard library `urllib.request`.
- Persists validated tags into SQLite via `core.tags.TaggingService`.
"""

import argparse
import csv
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union
import urllib.error
import urllib.request

# Ensure repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.db import DEFAULT_DB_PATH, Database
from core.reference import Book, Reference, get_book, parse_reference
from core.tag_prompts import (
    GeneratedTag,
    TaggingResult,
    format_prompt_for_gemini_api,
    format_taxonomy_for_prompt,
    generate_batch_tagging_prompts,
    generate_tagging_prompt,
    get_tgc_hermeneutical_system_prompt,
    parse_tagging_response,
)
from core.tags import CANONICAL_TAXONOMY, TagCategory, TaggingService


DEFAULT_MODEL = "gemini-2.5-pro"
FALLBACK_MODEL = "gemini-2.0-flash"
GEMINI_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


# ==============================================================================
# Scripture Text Retrieval Helper
# ==============================================================================


def fetch_passage_text(
    db: Database,
    reference: Union[Reference, str],
    translation_id: str = "WEB",
) -> Tuple[Reference, str]:
    """Retrieve formatted verse text for a given reference from the database.

    Args:
        db: Database instance.
        reference: Reference string or object.
        translation_id: Translation identifier (e.g. 'WEB').

    Returns:
        Tuple of `(canonical_reference, text)`.
    """
    ref_obj = parse_reference(reference) if isinstance(reference, str) else reference
    verses, _, _ = db.get_verses_with_fallback(ref_obj, translation_id=translation_id)

    if not verses:
        raise ValueError(
            f"No verses found for reference '{ref_obj.format()}' in translation '{translation_id}'."
        )

    text_parts = [f"[{v.verse}] {v.text.strip()}" for v in verses]
    joined_text = " ".join(text_parts)
    return ref_obj, joined_text


# ==============================================================================
# Pure Python Stdlib Gemini REST Client
# ==============================================================================


def call_gemini_api(
    prompt: str,
    api_key: str,
    system_prompt: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    timeout: int = 45,
) -> str:
    """Call Google Gemini REST API using Python standard library `urllib.request`.

    Zero external dependencies (ADR-003, ADR-006).

    Args:
        prompt: User prompt content.
        api_key: Google Gemini API key.
        system_prompt: Optional system prompt.
        model: Target Gemini model identifier.
        timeout: Request timeout in seconds.

    Returns:
        Raw string response from Gemini.
    """
    clean_key = api_key.strip()
    if not clean_key:
        raise ValueError("GEMINI_API_KEY is empty or missing.")

    payload = format_prompt_for_gemini_api(prompt, system_prompt=system_prompt)
    payload_bytes = json.dumps(payload).encode("utf-8")

    models_to_try = [model]
    if model != FALLBACK_MODEL:
        models_to_try.append(FALLBACK_MODEL)

    last_error: Optional[Exception] = None

    for candidate_model in models_to_try:
        url = f"{GEMINI_API_ENDPOINT.format(model=candidate_model)}?key={clean_key}"
        req = urllib.request.Request(
            url,
            data=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "BibleEngine/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                res_bytes = response.read()
                res_data = json.loads(res_bytes.decode("utf-8"))

                # Extract text from Gemini response structure
                candidates = res_data.get("candidates", [])
                if not candidates:
                    raise ValueError(f"Gemini API returned no candidates: {res_data}")

                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if not parts:
                    raise ValueError(f"Gemini API returned empty parts in content: {content}")

                return str(parts[0].get("text", "")).strip()

        except urllib.error.HTTPError as http_err:
            last_error = http_err
            error_body = ""
            try:
                error_body = http_err.read().decode("utf-8")
            except Exception:
                pass

            # If 404 / model not found, try fallback model
            if http_err.code == 404 and candidate_model != models_to_try[-1]:
                continue

            raise RuntimeError(
                f"Gemini API HTTP {http_err.code} Error for model '{candidate_model}': {error_body or http_err.reason}"
            ) from http_err

        except Exception as exc:
            last_error = exc
            if candidate_model != models_to_try[-1]:
                continue
            raise RuntimeError(f"Gemini API network error: {exc}") from exc

    raise last_error or RuntimeError("Gemini API call failed.")


# ==============================================================================
# Subcommand Handlers
# ==============================================================================


def cmd_prompt(args: argparse.Namespace) -> int:
    """Handle 'prompt' subcommand: generate and display LLM tagging prompt."""
    raw_ref = args.reference
    try:
        ref = parse_reference(raw_ref)
    except Exception as exc:
        sys.stderr.write(f"Error: Invalid reference '{raw_ref}': {exc}\n")
        return 1

    db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
    if not db_path.exists():
        sys.stderr.write(
            f"Error: Database file not found at '{db_path}'.\n"
            f"Run 'python3 tools/ingest_web.py' to compile offline scripture database.\n"
        )
        return 1

    version = getattr(args, "version", "WEB") or "WEB"
    try:
        with Database(db_path, auto_init=False) as db:
            ref_obj, text = fetch_passage_text(db, ref, translation_id=version)
    except Exception as exc:
        sys.stderr.write(f"Error fetching text for '{raw_ref}': {exc}\n")
        return 1

    cats = [c.strip() for c in args.category.split(",") if c.strip()] if getattr(args, "category", None) else None
    custom = [c.strip() for c in args.custom_tags.split(",") if c.strip()] if getattr(args, "custom_tags", None) else None
    allow_new = not getattr(args, "no_new_tags", False)
    max_tags = getattr(args, "max_tags", 6)

    prompt = generate_tagging_prompt(
        reference=ref_obj,
        passage_text=text,
        categories=cats,
        custom_tags=custom,
        allow_new_tags=allow_new,
        max_tags=max_tags,
        translation_id=version,
    )

    fmt = getattr(args, "format", "text")
    if fmt == "gemini":
        payload = format_prompt_for_gemini_api(prompt)
        output_str = json.dumps(payload, indent=2)
    elif fmt == "json":
        payload = {
            "reference": ref_obj.format(),
            "translation": version,
            "system_prompt": get_tgc_hermeneutical_system_prompt(),
            "prompt": prompt,
        }
        output_str = json.dumps(payload, indent=2)
    else:
        output_str = prompt

    if getattr(args, "output", None):
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_str, encoding="utf-8")
        print(f"Wrote prompt for {ref_obj.format()} to '{out_path}'.")
    else:
        print(output_str)

    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    """Handle 'batch' subcommand: generate batch prompt requests for multiple passages."""
    db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
    if not db_path.exists():
        sys.stderr.write(f"Error: Database file not found at '{db_path}'.\n")
        return 1

    version = getattr(args, "version", "WEB") or "WEB"
    targets: List[Reference] = []

    # Source 1: Direct --refs
    if getattr(args, "refs", None):
        parts = [p.strip() for p in args.refs.split(",") if p.strip()]
        for p in parts:
            try:
                targets.append(parse_reference(p))
            except Exception as exc:
                sys.stderr.write(f"Warning: Skipping invalid citation '{p}': {exc}\n")

    # Source 2: --favorites (favorite_bible_verses.csv)
    if getattr(args, "favorites", False):
        fav_path = _REPO_ROOT / "favorite_bible_verses.csv"
        if not fav_path.exists():
            sys.stderr.write(f"Error: Favorites file not found at '{fav_path}'.\n")
            return 1
        starred_only = getattr(args, "starred_only", False)
        with open(fav_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                is_starred = row.get("starred", "").strip().upper() == "TRUE"
                if starred_only and not is_starred:
                    continue
                try:
                    targets.append(Reference.from_csv_row(row))
                except Exception:
                    pass

    # Source 3: --book
    if getattr(args, "book", None):
        b = get_book(args.book)
        if not b:
            sys.stderr.write(f"Error: Unknown book '{args.book}'.\n")
            return 1
        for ch in range(1, b.total_chapters + 1):
            targets.append(Reference(book=b, chapter=ch))

    # Source 4: --input-file
    if getattr(args, "input_file", None):
        in_path = Path(args.input_file).resolve()
        if not in_path.exists():
            sys.stderr.write(f"Error: Input file not found at '{in_path}'.\n")
            return 1
        for line in in_path.read_text(encoding="utf-8").splitlines():
            line_clean = line.strip()
            if line_clean and not line_clean.startswith("#"):
                try:
                    targets.append(parse_reference(line_clean))
                except Exception as exc:
                    sys.stderr.write(f"Warning: Skipping '{line_clean}': {exc}\n")

    if not targets:
        sys.stderr.write("Error: No passages specified. Use --refs, --favorites, --book, or --input-file.\n")
        return 1

    limit = getattr(args, "limit", None)
    if limit and limit > 0:
        targets = targets[:limit]

    # Fetch texts from database
    passages: List[Tuple[Reference, str]] = []
    with Database(db_path, auto_init=False) as db:
        for ref in targets:
            try:
                ref_obj, text = fetch_passage_text(db, ref, translation_id=version)
                passages.append((ref_obj, text))
            except Exception as exc:
                sys.stderr.write(f"Warning: Could not fetch text for {ref.format()}: {exc}\n")

    if not passages:
        sys.stderr.write("Error: Failed to retrieve scripture text for specified targets.\n")
        return 1

    cats = [c.strip() for c in args.category.split(",") if c.strip()] if getattr(args, "category", None) else None
    allow_new = not getattr(args, "no_new_tags", False)
    max_tags = getattr(args, "max_tags", 6)

    batch_items = generate_batch_tagging_prompts(
        passages=passages,
        categories=cats,
        allow_new_tags=allow_new,
        max_tags=max_tags,
        translation_id=version,
    )

    fmt = getattr(args, "format", "jsonl")
    if fmt == "json":
        output_data = json.dumps(batch_items, indent=2)
    else:  # jsonl
        output_data = "\n".join(json.dumps(item) for item in batch_items)

    if getattr(args, "output", None):
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_data + "\n", encoding="utf-8")
        print(f"Generated {len(batch_items)} batch tagging prompt(s) in '{out_path}'.")
    else:
        print(output_data)

    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    """Handle 'apply' subcommand: parse and apply LLM tagging response payload to SQLite."""
    input_source = args.file
    raw_content = ""

    if input_source == "-":
        raw_content = sys.stdin.read()
    else:
        in_path = Path(input_source).resolve()
        if not in_path.exists():
            sys.stderr.write(f"Error: Input file not found at '{in_path}'.\n")
            return 1
        raw_content = in_path.read_text(encoding="utf-8")

    db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
    if not db_path.exists():
        sys.stderr.write(f"Error: Database file not found at '{db_path}'.\n")
        return 1

    # Detect if content is single JSON or JSONL
    results: List[TaggingResult] = []
    single_res = parse_tagging_response(raw_content)
    if single_res.is_success:
        results.append(single_res)
    else:
        # Attempt to parse as JSONL (one JSON object per line)
        lines = [line.strip() for line in raw_content.splitlines() if line.strip()]
        for line_num, line in enumerate(lines, start=1):
            try:
                item = json.loads(line)
                res_text = item.get("response", item.get("text", line))
                ref_fallback = item.get("reference")
                res = parse_tagging_response(res_text, default_reference=ref_fallback)
                if res.is_success:
                    results.append(res)
                else:
                    sys.stderr.write(f"Warning: Line {line_num} had no valid tags: {res.error}\n")
            except Exception as exc:
                sys.stderr.write(f"Warning: Skipping line {line_num}: {exc}\n")

    if not results:
        sys.stderr.write("Error: No valid tagging results extracted from input.\n")
        return 1

    dry_run = getattr(args, "dry_run", False)
    min_conf = getattr(args, "min_confidence", 0.5)
    source_name = getattr(args, "source", "llm-gemini")

    total_applied = 0
    total_skipped = 0

    with Database(db_path, auto_init=False) as db:
        svc = TaggingService(db)

        for res in results:
            print(f"\nPassage: {res.reference}")
            for tag in res.tags:
                if tag.confidence < min_conf:
                    print(f"  [SKIP] {tag.name} (confidence {tag.confidence:.2f} < {min_conf})")
                    total_skipped += 1
                    continue

                star_icon = " ★" if tag.starred else ""
                sub_str = f" ({tag.sub_span})" if tag.sub_span else ""
                print(f"  • {tag.name} [{tag.category}]{star_icon}{sub_str} (conf: {tag.confidence:.2f})")
                if tag.notes:
                    print(f"    Rationale: {tag.notes}")

                if not dry_run:
                    try:
                        target_ref = tag.sub_span if tag.sub_span else res.reference
                        svc.tag_passage(
                            reference=target_ref,
                            tags=tag.name,
                            category=tag.category,
                            confidence=tag.confidence,
                            source=source_name,
                            starred=tag.starred,
                            notes=tag.notes,
                        )
                        total_applied += 1
                    except Exception as exc:
                        sys.stderr.write(f"    Error writing tag '{tag.name}': {exc}\n")
                else:
                    total_applied += 1

    action_label = "Would apply" if dry_run else "Successfully applied"
    print(f"\n{action_label} {total_applied} tag(s) across {len(results)} passage(s) ({total_skipped} skipped).")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    """Handle 'generate' subcommand: direct end-to-end LLM tagging via Gemini API."""
    raw_ref = args.reference
    try:
        ref = parse_reference(raw_ref)
    except Exception as exc:
        sys.stderr.write(f"Error: Invalid reference '{raw_ref}': {exc}\n")
        return 1

    # API Key retrieval
    api_key = getattr(args, "api_key", None) or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.stderr.write(
            "Error: GEMINI_API_KEY environment variable or --api-key argument is required for online generation.\n"
            "To set: export GEMINI_API_KEY='your-key-here'\n"
            "Alternatively, use offline prompt generation:\n"
            f"  ./bible tag prompt \"{raw_ref}\"\n"
        )
        return 1

    db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
    if not db_path.exists():
        sys.stderr.write(f"Error: Database file not found at '{db_path}'.\n")
        return 1

    version = getattr(args, "version", "WEB") or "WEB"
    try:
        with Database(db_path, auto_init=False) as db:
            ref_obj, text = fetch_passage_text(db, ref, translation_id=version)
    except Exception as exc:
        sys.stderr.write(f"Error fetching text for '{raw_ref}': {exc}\n")
        return 1

    cats = [c.strip() for c in args.category.split(",") if c.strip()] if getattr(args, "category", None) else None
    custom = [c.strip() for c in args.custom_tags.split(",") if c.strip()] if getattr(args, "custom_tags", None) else None
    allow_new = not getattr(args, "no_new_tags", False)
    max_tags = getattr(args, "max_tags", 6)
    model = getattr(args, "model", DEFAULT_MODEL) or DEFAULT_MODEL

    user_prompt = generate_tagging_prompt(
        reference=ref_obj,
        passage_text=text,
        categories=cats,
        custom_tags=custom,
        allow_new_tags=allow_new,
        max_tags=max_tags,
        translation_id=version,
    )

    sys_prompt = get_tgc_hermeneutical_system_prompt()

    print(f"Requesting semantic tags for {ref_obj.format()} using model '{model}'...")
    try:
        t0 = time.time()
        raw_response = call_gemini_api(
            prompt=user_prompt,
            api_key=api_key,
            system_prompt=sys_prompt,
            model=model,
        )
        duration = time.time() - t0
    except Exception as exc:
        sys.stderr.write(f"Error during Gemini API call: {exc}\n")
        return 1

    res = parse_tagging_response(raw_response, default_reference=ref_obj, model=model)
    if not res.is_success:
        sys.stderr.write(f"Error: Failed to parse LLM response into semantic tags: {res.error}\n")
        sys.stderr.write(f"Raw response was:\n{raw_response}\n")
        return 1

    print(f"Received {len(res.tags)} tag(s) in {duration:.2f}s:")
    dry_run = getattr(args, "dry_run", False)
    source_name = getattr(args, "source", "llm-gemini")

    with Database(db_path, auto_init=False) as db:
        svc = TaggingService(db)
        for tag in res.tags:
            star_icon = " ★" if tag.starred else ""
            sub_str = f" ({tag.sub_span})" if tag.sub_span else ""
            print(f"  • {tag.name} [{tag.category}]{star_icon}{sub_str} (conf: {tag.confidence:.2f})")
            if tag.notes:
                print(f"    {tag.notes}")

            if not dry_run:
                target_ref = tag.sub_span if tag.sub_span else res.reference
                svc.tag_passage(
                    reference=target_ref,
                    tags=tag.name,
                    category=tag.category,
                    confidence=tag.confidence,
                    source=source_name,
                    starred=tag.starred,
                    notes=tag.notes,
                )

    if dry_run:
        print("\n[Dry Run] No tags were written to the database. Remove --dry-run to persist.")
    else:
        print(f"\nSuccessfully stored tags for {ref_obj.format()} in SQLite database.")

    return 0


# ==============================================================================
# CLI Argument Parser Construction
# ==============================================================================


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for `tools/tag_generator.py`."""
    parser = argparse.ArgumentParser(
        prog="tag_generator.py",
        description="Batch Scripture Semantic Tagging Generator & LLM Pipeline (Zero Dependencies).",
    )
    subparsers = parser.add_subparsers(dest="command", help="Tag generator command")

    # Subcommand: prompt
    p_prompt = subparsers.add_parser("prompt", help="Generate and display prompt for a passage")
    p_prompt.add_argument("reference", help="Scripture passage citation (e.g. 'Romans 8:1-11')")
    p_prompt.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to SQLite database")
    p_prompt.add_argument("--version", default="WEB", help="Bible translation ID (default: WEB)")
    p_prompt.add_argument("--category", help="Comma-separated category filter (e.g. 'theological,historical')")
    p_prompt.add_argument("--custom-tags", help="Comma-separated custom candidate tags")
    p_prompt.add_argument("--no-new-tags", action="store_true", help="Disallow novel tags outside taxonomy")
    p_prompt.add_argument("--max-tags", type=int, default=6, help="Maximum tags to request (default: 6)")
    p_prompt.add_argument("--format", choices=["text", "gemini", "json"], default="text", help="Output format")
    p_prompt.add_argument("--output", "-o", help="Write output to file instead of stdout")

    # Subcommand: batch
    p_batch = subparsers.add_parser("batch", help="Generate batch prompt requests (JSONL/JSON) for multiple passages")
    p_batch.add_argument("--refs", help="Comma-separated citations (e.g. 'John 3:16, Romans 8:1')")
    p_batch.add_argument("--favorites", action="store_true", help="Extract passages from favorite_bible_verses.csv")
    p_batch.add_argument("--starred-only", action="store_true", help="With --favorites, filter to starred passages")
    p_batch.add_argument("--book", help="Generate prompts for all chapters of a book (e.g. 'Romans')")
    p_batch.add_argument("--input-file", help="Path to text file containing references (one per line)")
    p_batch.add_argument("--limit", type=int, help="Maximum passages to process")
    p_batch.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to SQLite database")
    p_batch.add_argument("--version", default="WEB", help="Bible translation ID (default: WEB)")
    p_batch.add_argument("--category", help="Comma-separated category filter")
    p_batch.add_argument("--no-new-tags", action="store_true", help="Disallow novel tags")
    p_batch.add_argument("--max-tags", type=int, default=6, help="Maximum tags per passage")
    p_batch.add_argument("--format", choices=["jsonl", "json"], default="jsonl", help="Batch output format")
    p_batch.add_argument("--output", "-o", help="Write batch output to file")

    # Subcommand: apply
    p_apply = subparsers.add_parser("apply", help="Parse and apply LLM tagging response payload to SQLite")
    p_apply.add_argument("file", help="Path to response JSON/JSONL file (or '-' for stdin)")
    p_apply.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to SQLite database")
    p_apply.add_argument("--dry-run", action="store_true", help="Preview tags without writing to database")
    p_apply.add_argument("--min-confidence", type=float, default=0.5, help="Minimum confidence threshold (0.0-1.0)")
    p_apply.add_argument("--source", default="llm-gemini", help="Provenance source identifier (default: llm-gemini)")

    # Subcommand: generate
    p_gen = subparsers.add_parser("generate", help="Direct online LLM tagging via Gemini API")
    p_gen.add_argument("reference", help="Scripture passage citation")
    p_gen.add_argument("--api-key", help="Google Gemini API key (defaults to $GEMINI_API_KEY)")
    p_gen.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model ID (default: {DEFAULT_MODEL})")
    p_gen.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to SQLite database")
    p_gen.add_argument("--version", default="WEB", help="Bible translation ID (default: WEB)")
    p_gen.add_argument("--category", help="Comma-separated category filter")
    p_gen.add_argument("--custom-tags", help="Comma-separated custom candidate tags")
    p_gen.add_argument("--no-new-tags", action="store_true", help="Disallow novel tags")
    p_gen.add_argument("--max-tags", type=int, default=6, help="Maximum tags to produce")
    p_gen.add_argument("--dry-run", action="store_true", help="Print tags without saving to database")
    p_gen.add_argument("--source", default="llm-gemini", help="Provenance source identifier (default: llm-gemini)")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main CLI entry point for `tools/tag_generator.py`."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "prompt":
        return cmd_prompt(args)
    elif args.command == "batch":
        return cmd_batch(args)
    elif args.command == "apply":
        return cmd_apply(args)
    elif args.command == "generate":
        return cmd_generate(args)
    else:
        sys.stderr.write(f"Unknown command: {args.command}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
