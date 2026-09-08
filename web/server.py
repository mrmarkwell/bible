"""Built-in HTTP Server and REST API Engine for Bible Engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003).
Provides:
  - High-performance multi-threaded HTTP server using http.server.ThreadingHTTPServer.
  - Comprehensive REST API endpoints for scripture lookup, search, tags, cross-references,
    topic density aggregations, and system health.
  - Secure static web asset serving (preventing directory traversal attacks) with MIME type resolution.
  - CORS headers for local API integration and development.
"""

from contextlib import contextmanager
from dataclasses import asdict
import http.server
import json
import mimetypes
from pathlib import Path
import re
import socketserver
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple, Union
import urllib.parse
import webbrowser

from core.arcs import ArcTheme, build_arc_network
from core.crossref import CrossReferenceService
from core.db import DEFAULT_DB_PATH, Database, PericopeRecord
from core.pericopes import PericopeService
from core.reference import (
    ALL_BOOKS,
    Book,
    Reference,
    get_book,
    parse_reference,
    verse_canonical_id,
)
from core.tags import ChapterTopicDensity, TaggingService

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_STATIC_DIR = Path(__file__).resolve().parent / "static"


class BibleRequestHandler(http.server.BaseHTTPRequestHandler):
    """HTTP Request Handler for Bible Engine REST API and static web assets."""

    db: Database
    static_dir: Path
    verbose: bool = False

    def log_message(self, format_str: str, *args: Any) -> None:
        """Custom logger to avoid terminal clutter unless verbose is enabled."""
        if getattr(self, "verbose", False):
            sys.stderr.write(
                f"[BibleServer] {self.address_string()} - {format_str % args}\n"
            )

    # -------------------------------------------------------------------------
    # Response Helpers
    # -------------------------------------------------------------------------

    def send_json(self, data: Any, status: int = 200) -> None:
        """Serialize data to JSON and send HTTP response with CORS headers."""
        try:
            payload = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        except Exception as exc:
            self.send_json_error(f"Serialization error: {exc}", status=500)
            return

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(payload)

    def send_json_error(self, message: str, status: int = 400) -> None:
        """Send a standardized JSON error response."""
        payload = json.dumps({"error": message, "status": status}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def send_svg(self, svg_content: str, status: int = 200) -> None:
        """Send a standalone pure vector SVG image response."""
        payload = svg_content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        """Handle CORS pre-flight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # -------------------------------------------------------------------------
    # Request Routing
    # -------------------------------------------------------------------------

    def do_GET(self) -> None:
        """Route GET requests to REST API handlers or static file dispatcher."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path.startswith("/api/"):
            self.route_api(path, query)
        else:
            self.serve_static(path)

    def route_api(self, path: str, query: Dict[str, List[str]]) -> None:
        """Dispatch REST API endpoint paths."""
        clean_path = path.rstrip("/")
        if clean_path == "/api/health":
            self.handle_health()
        elif clean_path == "/api/books":
            self.handle_books(query)
        elif clean_path == "/api/passage":
            self.handle_passage(query)
        elif clean_path == "/api/verses":
            self.handle_verses(query)
        elif clean_path == "/api/search":
            self.handle_search(query)
        elif clean_path == "/api/translations":
            self.handle_translations()
        elif clean_path == "/api/pericopes":
            self.handle_pericopes(query)
        elif clean_path == "/api/tags":
            self.handle_tags(query)
        elif clean_path == "/api/tags/density":
            self.handle_tags_density(query)
        elif clean_path == "/api/tags/chapters":
            self.handle_tags_chapters(query)
        elif clean_path in ("/api/tags/co-occurrence", "/api/tags/matrix"):
            self.handle_tags_co_occurrence(query)
        elif clean_path in ("/api/tags/relevance", "/api/tags/rank"):
            self.handle_tags_relevance(query)
        elif clean_path == "/api/crossref":
            self.handle_crossref(query)
        elif clean_path == "/api/crossref/stats":
            self.handle_crossref_stats()
        elif clean_path in ("/api/crossref/arcs", "/api/arcs"):
            self.handle_arcs(query)
        elif clean_path in ("/api/crossref/arcs.svg", "/api/arcs.svg"):
            self.handle_arcs_svg(query)
        elif clean_path in ("/api/slide", "/api/slide.svg"):
            self.handle_slide(query)
        elif clean_path == "/api/stats":
            self.handle_stats()
        else:
            self.send_json_error(f"Unknown API endpoint: '{path}'", status=404)

    # -------------------------------------------------------------------------
    # REST API Handlers
    # -------------------------------------------------------------------------

    def handle_health(self) -> None:
        """GET /api/health — System diagnostics, version, and database statistics."""
        try:
            verse_count = self.db.count_verses()
            translations = self.db.get_available_translation_ids()
            data = {
                "status": "ok",
                "engine": "Bible Engine",
                "version": "1.0.0",
                "database": str(self.db.db_path),
                "total_verses": verse_count,
                "translations": translations,
            }
            self.send_json(data)
        except Exception as exc:
            self.send_json_error(f"Database error during health check: {exc}", status=500)

    def handle_books(self, query: Dict[str, List[str]]) -> None:
        """GET /api/books — Canonical 66 books catalog with filtering."""
        testament_filter = query.get("testament", [None])[0]
        if testament_filter:
            testament_filter = testament_filter.strip().upper()

        books_data = []
        for b in ALL_BOOKS:
            if testament_filter and b.testament != testament_filter:
                continue
            books_data.append({
                "number": b.number,
                "name": b.name,
                "osis": b.osis,
                "testament": b.testament,
                "total_chapters": b.total_chapters,
                "is_single_chapter": b.is_single_chapter,
            })

        self.send_json({
            "total": len(books_data),
            "testament_filter": testament_filter,
            "books": books_data,
        })

    def handle_passage(self, query: Dict[str, List[str]]) -> None:
        """GET /api/passage — Fetch scripture passage by canonical reference string."""
        ref_str = query.get("ref", [None])[0]
        if not ref_str:
            self.send_json_error("Missing required query parameter: 'ref'", status=400)
            return

        version = query.get("version", ["WEB"])[0].strip().upper()

        try:
            parsed_ref = parse_reference(ref_str)
        except (ValueError, TypeError) as exc:
            self.send_json_error(f"Invalid scripture reference '{ref_str}': {exc}", status=400)
            return

        try:
            verses, used_id, is_fallback = self.db.get_verses_with_fallback(parsed_ref, translation_id=version)
            fallback_for = version if is_fallback else None
            tagging_svc = TaggingService(self.db)
            tags = tagging_svc.get_tags_for_passage(parsed_ref)

            crossref_svc = CrossReferenceService(self.db)
            crossrefs = crossref_svc.get_cross_references(reference=parsed_ref, bidirectional=True)
            pericope_svc = PericopeService(self.db)
            pericopes = pericope_svc.get_pericopes_for_passage(parsed_ref)

            verse_items = []
            for v in verses:
                cid = v.canonical_verse_id or 0
                matching_tags = [
                    t.tag_name
                    for t in tags
                    if t.start_canonical_id <= cid <= t.end_canonical_id
                ]
                verse_items.append({
                    "canonical_verse_id": cid,
                    "book": v.book_name,
                    "book_id": v.book_id,
                    "osis_ref": v.osis_ref,
                    "chapter": v.chapter,
                    "verse": v.verse,
                    "text": v.text,
                    "translation_id": v.translation_id,
                    "tags": matching_tags,
                })

            tag_items = [
                {
                    "id": t.id,
                    "tag_id": t.tag_id,
                    "name": t.tag_name,
                    "confidence": t.confidence,
                    "starred": bool(t.starred),
                    "source": t.source,
                }
                for t in tags
            ]

            pericope_items = [
                {
                    "id": p.id,
                    "book_id": p.book_id,
                    "book_name": p.book_name,
                    "osis": p.osis,
                    "start_canonical_id": p.start_canonical_id,
                    "end_canonical_id": p.end_canonical_id,
                    "human_ref": p.human_ref,
                    "title": p.title,
                    "redemptive_summary": p.redemptive_summary,
                }
                for p in pericopes
            ]

            crossref_items = [
                {
                    "id": x.id,
                    "source_ref": x.source_human_ref,
                    "target_ref": x.target_human_ref,
                    "relationship_type": x.relationship_type,
                    "weight": x.weight,
                }
                for x in crossrefs
            ]

            self.send_json({
                "reference": parsed_ref.format(),
                "translation_id": used_id,
                "fallback_for": fallback_for,
                "total_verses": len(verse_items),
                "total_pericopes": len(pericope_items),
                "verses": verse_items,
                "pericopes": pericope_items,
                "tags": tag_items,
                "cross_references": crossref_items,
            })
        except Exception as exc:
            self.send_json_error(f"Failed to fetch passage: {exc}", status=500)

    def handle_verses(self, query: Dict[str, List[str]]) -> None:
        """GET /api/verses — Direct chapter/verse range retrieval."""
        book_param = query.get("book", [None])[0]
        if not book_param:
            self.send_json_error("Missing required query parameter: 'book'", status=400)
            return

        try:
            book = get_book(book_param)
        except ValueError as exc:
            self.send_json_error(f"Unrecognized book '{book_param}': {exc}", status=400)
            return

        chapter_str = query.get("chapter", ["1"])[0]
        try:
            chapter = int(chapter_str)
        except ValueError:
            self.send_json_error(f"Invalid chapter '{chapter_str}', expected integer", status=400)
            return

        if chapter < 1 or chapter > book.total_chapters:
            self.send_json_error(
                f"Chapter {chapter} out of range for {book.name} (1-{book.total_chapters})",
                status=400,
            )
            return

        version = query.get("version", ["WEB"])[0].strip().upper()
        ref = parse_reference(f"{book.name} {chapter}")

        try:
            verses, used_id, is_fallback = self.db.get_verses_with_fallback(ref, translation_id=version)
            fallback_for = version if is_fallback else None
            verse_items = [
                {
                    "canonical_verse_id": v.canonical_verse_id,
                    "book": v.book_name,
                    "book_id": v.book_id,
                    "osis_ref": v.osis_ref,
                    "chapter": v.chapter,
                    "verse": v.verse,
                    "text": v.text,
                    "translation_id": v.translation_id,
                }
                for v in verses
            ]
            self.send_json({
                "book": book.name,
                "osis": book.osis,
                "chapter": chapter,
                "translation_id": used_id,
                "fallback_for": fallback_for,
                "total_verses": len(verse_items),
                "verses": verse_items,
            })
        except Exception as exc:
            self.send_json_error(f"Failed to retrieve chapter verses: {exc}", status=500)

    def handle_search(self, query: Dict[str, List[str]]) -> None:
        """GET /api/search — High-performance SQLite FTS5 full-text scripture search."""
        q = query.get("q", [None])[0]
        if not q or not q.strip():
            self.send_json_error("Missing required query parameter: 'q'", status=400)
            return

        version = query.get("version", ["WEB"])[0].strip().upper()

        try:
            limit = max(1, min(int(query.get("limit", ["50"])[0]), 200))
            offset = max(0, int(query.get("offset", ["0"])[0]))
        except ValueError:
            self.send_json_error("Query parameters 'limit' and 'offset' must be integers", status=400)
            return

        book_id: Optional[int] = None
        book_param = query.get("book", [None])[0]
        if book_param:
            try:
                b = get_book(book_param)
                book_id = b.number
            except ValueError:
                self.send_json_error(f"Unrecognized book filter '{book_param}'", status=400)
                return

        testament_param = query.get("testament", [None])[0]
        if testament_param:
            testament_param = testament_param.strip().upper()
            if testament_param not in ("OT", "NT"):
                self.send_json_error("Testament filter must be 'OT' or 'NT'", status=400)
                return

        try:
            results = self.db.search_text(
                query=q,
                translation_id=version,
                book=book_param,
                testament=testament_param,
                limit=limit,
                offset=offset,
            )
            total_matches = self.db.count_search_matches(
                query=q,
                translation_id=version,
                book=book_param,
                testament=testament_param,
            )

            result_items = [
                {
                    "verse_id": r.verse_id,
                    "canonical_verse_id": verse_canonical_id(
                        get_book(r.book_name).number, r.chapter, r.verse
                    ) if r.book_name else None,
                    "book": r.book_name,
                    "chapter": r.chapter,
                    "verse": r.verse,
                    "osis_ref": r.osis_ref,
                    "text": r.text,
                    "snippet": r.snippet,
                    "rank": r.rank,
                }
                for r in results
            ]

            self.send_json({
                "query": q,
                "translation_id": version,
                "total_matches": total_matches,
                "limit": limit,
                "offset": offset,
                "results": result_items,
            })
        except Exception as exc:
            self.send_json_error(f"Search query error: {exc}", status=500)

    def handle_translations(self) -> None:
        """GET /api/translations — List available installed scripture translations."""
        try:
            records = self.db.list_translations()
            items = [
                {
                    "id": t.id,
                    "name": t.name,
                    "language": t.language,
                    "is_public_domain": bool(t.is_public_domain),
                    "license_notes": t.license_notes,
                    "is_encrypted": bool(t.is_encrypted),
                }
                for t in records
            ]
            self.send_json({"total": len(items), "translations": items})
        except Exception as exc:
            self.send_json_error(f"Failed to retrieve translations: {exc}", status=500)

    def handle_pericopes(self, query: Dict[str, List[str]]) -> None:
        """GET /api/pericopes — Retrieve canonical pericope section headings and summaries."""
        ref_str = query.get("ref", [None])[0]
        book_str = query.get("book", [None])[0]
        chapter_str = query.get("chapter", [None])[0]

        pericope_svc = PericopeService(self.db)
        try:
            if ref_str:
                parsed_ref = parse_reference(ref_str)
                records = pericope_svc.get_pericopes_for_passage(parsed_ref)
                query_label = parsed_ref.format()
            elif book_str:
                book = get_book(book_str)
                chapter = int(chapter_str) if chapter_str else None
                records = pericope_svc.get_pericopes_for_book(book, chapter=chapter)
                query_label = f"{book.name} {chapter}" if chapter else book.name
            else:
                cur = self.db.conn.cursor()
                cur.execute(
                    "SELECT id, book_id, start_canonical_id, end_canonical_id, human_ref, title, redemptive_summary, created_at "
                    "FROM pericopes ORDER BY start_canonical_id ASC"
                )
                rows = cur.fetchall()
                cur.close()
                records = [
                    PericopeRecord(
                        id=r["id"],
                        book_id=r["book_id"],
                        start_canonical_id=r["start_canonical_id"],
                        end_canonical_id=r["end_canonical_id"],
                        human_ref=r["human_ref"],
                        title=r["title"],
                        redemptive_summary=r["redemptive_summary"],
                        created_at=r["created_at"],
                    )
                    for r in rows
                ]
                query_label = "All Canon"

            items = [p.to_dict() for p in records]
            self.send_json({
                "query": query_label,
                "total_pericopes": len(items),
                "pericopes": items,
            })
        except Exception as exc:
            self.send_json_error(f"Failed to fetch pericopes: {exc}", status=500)

    def handle_tags(self, query: Dict[str, List[str]]) -> None:
        """GET /api/tags — List semantic tags with optional category or text filter."""
        category = query.get("category", [None])[0]
        q = query.get("q", [None])[0]

        tagging_svc = TaggingService(self.db)
        try:
            if q:
                tags = tagging_svc.search_tags(q)
            else:
                tags = tagging_svc.list_tags(category=category)

            tag_items = [
                {
                    "id": t.id,
                    "name": t.name,
                    "category": t.category,
                    "description": t.description,
                    "passage_count": t.passage_count,
                }
                for t in tags
            ]
            self.send_json({
                "total": len(tag_items),
                "category_filter": category,
                "search_query": q,
                "tags": tag_items,
            })
        except Exception as exc:
            self.send_json_error(f"Failed to retrieve tags: {exc}", status=500)

    def handle_tags_density(self, query: Dict[str, List[str]]) -> None:
        """GET /api/tags/density — Thematic topic distribution across the 66 canonical books."""
        tag = query.get("tag", [None])[0]
        category = query.get("category", [None])[0]
        testament = query.get("testament", [None])[0]
        min_passages_str = query.get("min_passages", ["0"])[0]

        try:
            min_passages = max(0, int(min_passages_str))
        except ValueError:
            min_passages = 0

        tagging_svc = TaggingService(self.db)
        try:
            densities = tagging_svc.get_topic_density_per_book(
                tag_name=tag,
                category=category,
                testament=testament,
                min_passages=min_passages,
            )
            items = [
                {
                    "book_id": d.book_id,
                    "book_name": d.book_name,
                    "osis": d.osis,
                    "testament": d.testament,
                    "total_chapters": d.total_chapters,
                    "passage_count": d.passage_count,
                    "starred_count": d.starred_count,
                    "distinct_tags": d.distinct_tags,
                    "tag_counts": d.tag_counts,
                }
                for d in densities
            ]
            self.send_json({
                "tag": tag,
                "category": category,
                "testament": testament,
                "min_passages": min_passages,
                "total_books": len(items),
                "densities": items,
            })
        except Exception as exc:
            self.send_json_error(f"Failed to calculate topic density: {exc}", status=500)

    def handle_tags_chapters(self, query: Dict[str, List[str]]) -> None:
        """GET /api/tags/chapters — Thematic topic distribution across chapters of a book."""
        book_param = query.get("book", [None])[0]
        if not book_param:
            self.send_json_error("Missing required query parameter: 'book'", status=400)
            return

        try:
            book = get_book(book_param)
        except ValueError as exc:
            self.send_json_error(f"Unrecognized book '{book_param}': {exc}", status=400)
            return

        tag = query.get("tag", [None])[0]
        category = query.get("category", [None])[0]

        tagging_svc = TaggingService(self.db)
        try:
            densities = tagging_svc.get_topic_density_per_chapter(
                book=book,
                tag_name=tag,
                category=category,
            )
            items = [d.to_dict() for d in densities]
            self.send_json({
                "book_id": book.number,
                "book_name": book.name,
                "osis": book.osis,
                "total_chapters": book.total_chapters,
                "tag_filter": tag,
                "category_filter": category,
                "chapters": items,
            })
        except Exception as exc:
            self.send_json_error(f"Failed to calculate chapter topic density: {exc}", status=500)

    def handle_tags_co_occurrence(self, query: Dict[str, List[str]]) -> None:
        """GET /api/tags/co-occurrence — Tag co-occurrence matrix and similarity indices."""
        tags_raw = query.get("tags", [None])[0]
        tag_list: Optional[List[str]] = None
        if tags_raw:
            tag_list = [t.strip() for t in tags_raw.split(",") if t.strip()]

        category = query.get("category", [None])[0]
        min_shared_str = query.get("min_shared", ["1"])[0]
        try:
            min_shared = max(1, int(min_shared_str))
        except ValueError:
            min_shared = 1

        tagging_svc = TaggingService(self.db)
        try:
            matrix = tagging_svc.get_tag_co_occurrences(
                tags=tag_list,
                category=category,
                min_co_occurrences=min_shared,
            )
            pair_items = [
                {
                    "tag_a": p.tag_a,
                    "tag_b": p.tag_b,
                    "shared_passages": p.shared_passages,
                    "jaccard_similarity": round(p.jaccard_similarity, 4),
                    "dice_coefficient": round(p.dice_coefficient, 4),
                    "category_a": p.category_a,
                    "category_b": p.category_b,
                }
                for p in matrix.pair_metrics
            ]
            self.send_json({
                "tags": matrix.tags,
                "total_pairs": len(pair_items),
                "min_shared": min_shared,
                "pairs": pair_items,
            })
        except Exception as exc:
            self.send_json_error(f"Failed to compute co-occurrence matrix: {exc}", status=500)

    def handle_tags_relevance(self, query: Dict[str, List[str]]) -> None:
        """GET /api/tags/relevance — Scored multi-tag scripture passage ranking."""
        tags_raw = query.get("tags", [None])[0]
        if not tags_raw:
            self.send_json_error("Missing required query parameter: 'tags'", status=400)
            return

        tag_list = [t.strip() for t in tags_raw.split(",") if t.strip()]
        if not tag_list:
            self.send_json_error("Query parameter 'tags' must contain at least one tag", status=400)
            return

        version = query.get("version", ["WEB"])[0].strip().upper()
        starred_only = query.get("starred_only", ["0"])[0].lower() in ("1", "true", "yes")

        try:
            min_score = float(query.get("min_score", ["0.1"])[0])
            limit = max(1, min(int(query.get("limit", ["20"])[0]), 100))
        except ValueError:
            self.send_json_error("Parameters 'min_score' (float) and 'limit' (int) must be numeric", status=400)
            return

        hydrate = query.get("hydrate", ["1"])[0].lower() not in ("0", "false", "no")

        tagging_svc = TaggingService(self.db)
        try:
            ranked = tagging_svc.score_verse_relevance(
                tags=tag_list,
                translation_id=version,
                starred_only=starred_only,
                min_score=min_score,
                limit=limit,
                hydrate_verses=hydrate,
            )
            items = [
                {
                    "citation": r.human_ref,
                    "osis": r.osis,
                    "score": round(r.score, 4),
                    "matched_tags": r.matched_tags,
                    "match_ratio": round(r.match_ratio, 4),
                    "starred": r.starred,
                    "highest_confidence": round(r.highest_confidence, 4),
                    "text": r.text,
                }
                for r in ranked
            ]
            self.send_json({
                "tags": tag_list,
                "total_results": len(items),
                "translation_id": version,
                "results": items,
            })
        except Exception as exc:
            self.send_json_error(f"Failed to score verse relevance: {exc}", status=500)

    def handle_crossref(self, query: Dict[str, List[str]]) -> None:
        """GET /api/crossref — Retrieve cross-reference relationship edges for a passage."""
        ref_str = query.get("ref", [None])[0]
        if not ref_str:
            self.send_json_error("Missing required query parameter: 'ref'", status=400)
            return

        version = query.get("version", ["WEB"])[0].strip().upper()

        try:
            parsed_ref = parse_reference(ref_str)
        except (ValueError, TypeError) as exc:
            self.send_json_error(f"Invalid scripture reference '{ref_str}': {exc}", status=400)
            return

        crossref_svc = CrossReferenceService(self.db)
        try:
            hydrated = crossref_svc.get_hydrated_cross_references(
                reference=parsed_ref,
                translation_id=version,
            )
            items = [
                {
                    "id": h.id,
                    "source_ref": h.source_ref,
                    "target_ref": h.target_ref,
                    "relationship_type": h.relationship_type,
                    "votes": h.votes,
                    "target_text": h.target_text,
                }
                for h in hydrated
            ]
            self.send_json({
                "reference": parsed_ref.format(),
                "translation_id": version,
                "total_cross_references": len(items),
                "cross_references": items,
            })
        except Exception as exc:
            self.send_json_error(f"Failed to retrieve cross-references: {exc}", status=500)

    def handle_crossref_stats(self) -> None:
        """GET /api/crossref/stats — Global cross-reference relationship statistics."""
        crossref_svc = CrossReferenceService(self.db)
        try:
            stats = crossref_svc.get_summary_statistics()
            self.send_json({
                "total_edges": stats.total_edges,
                "by_relationship_type": stats.by_relationship_type,
                "testament_connections": stats.testament_connections,
                "distinct_sources": stats.distinct_sources,
                "distinct_targets": stats.distinct_targets,
            })
        except Exception as exc:
            self.send_json_error(f"Failed to retrieve cross-reference statistics: {exc}", status=500)

    def handle_arcs(self, query: Dict[str, List[str]]) -> None:
        """GET /api/crossref/arcs — Retrieve graph nodes, edges, and Bézier arc coordinates in JSON."""
        rel_type = query.get("type", query.get("rel_type", [None]))[0]
        book = query.get("book", [None])[0]
        testament = query.get("testament", [None])[0]
        theme = query.get("theme", ["obsidian"])[0]
        try:
            width = int(query.get("width", [1200])[0])
            height = int(query.get("height", [520])[0])
        except (ValueError, TypeError):
            width, height = 1200, 520

        try:
            net = build_arc_network(
                self.db,
                relationship_type=rel_type,
                book_filter=book,
                testament_filter=testament,
                theme=theme,
                width=width,
                height=height,
            )
            self.send_json(net.to_dict())
        except Exception as exc:
            self.send_json_error(f"Failed to generate arc network: {exc}", status=500)

    def handle_arcs_svg(self, query: Dict[str, List[str]]) -> None:
        """GET /api/crossref/arcs.svg — Pure vector SVG rendering of typological arc network."""
        rel_type = query.get("type", query.get("rel_type", [None]))[0]
        book = query.get("book", [None])[0]
        testament = query.get("testament", [None])[0]
        theme = query.get("theme", ["obsidian"])[0]
        try:
            width = int(query.get("width", [1200])[0])
            height = int(query.get("height", [520])[0])
        except (ValueError, TypeError):
            width, height = 1200, 520

        try:
            net = build_arc_network(
                self.db,
                relationship_type=rel_type,
                book_filter=book,
                testament_filter=testament,
                theme=theme,
                width=width,
                height=height,
            )
            self.send_svg(net.render_svg(standalone=True, interactive=True))
        except Exception as exc:
            self.send_json_error(f"Failed to render arc SVG: {exc}", status=500)

    def handle_slide(self, query: Dict[str, List[str]]) -> None:
        """GET /api/slide or /api/slide.svg — Render high-resolution visual scripture slide."""
        ref_str = query.get("ref", query.get("passage", [None]))[0]
        if not ref_str:
            self.send_json_error("Missing required query parameter: 'ref'", status=400)
            return

        try:
            parsed_ref = parse_reference(ref_str)
        except Exception as exc:
            self.send_json_error(f"Invalid scripture reference '{ref_str}': {exc}", status=400)
            return

        version = query.get("version", ["WEB"])[0].strip().upper()
        verses, used_id, _ = self.db.get_verses_with_fallback(parsed_ref, translation_id=version)
        if not verses:
            self.send_json_error(f"No verses found for '{ref_str}' in translation '{version}'", status=404)
            return

        verse_text = " ".join(v.text.strip() for v in verses)
        citation = parsed_ref.format()

        pericope_svc = PericopeService(self.db)
        pericopes = pericope_svc.get_pericopes_for_passage(parsed_ref)
        pericope_title = pericopes[0].title if pericopes else None

        from core.render import (
            PaginationConfig,
            RenderConfig,
            SlideContent,
            get_default_engine,
            get_theme,
            normalize_color,
            paginate_verses,
            parse_resolution,
        )

        res_param = query.get("res", query.get("resolution", ["1080p"]))[0]
        theme_param = query.get("theme", ["oled_black"])[0]
        fmt_param = query.get("format", ["svg"])[0].lower()
        backend_param = query.get("backend", ["svg"])[0].lower()
        font_param = query.get("font", [None])[0]
        font_size_raw = query.get("font_size", [None])[0]
        line_spacing_raw = query.get("line_spacing", ["1.5"])[0]
        align_param = query.get("align", ["center"])[0].lower()
        citation_style_param = query.get("citation_style", ["below"])[0].lower()
        citation_color_param = query.get("citation_color", [None])[0]
        accent_color_param = query.get("accent_color", [None])[0]
        tags_param = query.get("tags", ["false"])[0].lower() in ("true", "1", "yes")
        safe_area_raw = query.get("safe_area", ["0.15"])[0]
        optical_center_raw = query.get("optical_center", ["0.45"])[0]
        balance_param = query.get("balance", ["true"])[0].lower()

        # Pagination query parameters
        paginate_param = query.get("paginate", ["auto"])[0].lower()
        page_param = query.get("page", ["1"])[0]
        max_verses_raw = query.get("max_verses", [None])[0]
        max_lines_raw = query.get("max_lines", [None])[0]
        max_chars_raw = query.get("max_chars", [None])[0]
        page_format_param = query.get("page_format", ["{page} / {total}"])[0]
        keep_cit_param = query.get("keep_citation", ["false"])[0].lower() in ("true", "1", "yes")

        w, h = parse_resolution(res_param)
        theme_obj = get_theme(theme_param)

        font_size = None
        if font_size_raw:
            try:
                font_size = float(font_size_raw)
            except ValueError:
                font_size = None

        line_spacing = 1.5
        try:
            line_spacing = float(line_spacing_raw)
        except ValueError:
            line_spacing = 1.5

        optical_center = 0.45
        try:
            optical_center = float(optical_center_raw)
        except ValueError:
            optical_center = 0.45

        safe_area = 0.15
        try:
            sa_val = float(safe_area_raw.rstrip("%"))
            safe_area = sa_val / 100.0 if sa_val > 1.0 else sa_val
        except ValueError:
            safe_area = 0.15

        balance_lines = balance_param not in ("false", "0", "no")

        slide_tags: List[str] = []
        if tags_param:
            tagging_svc = TaggingService(self.db)
            passages = tagging_svc.get_tags_for_passage(parsed_ref)
            slide_tags = [p.tag_name for p in passages if p.tag_name]

        config = RenderConfig(
            width=w,
            height=h,
            theme=theme_obj,
            safe_area_pct=safe_area,
            font_family=font_param,
            font_size=font_size,
            line_spacing=line_spacing,
            text_align=align_param if align_param in ("center", "left", "right") else "center",
            citation_style=citation_style_param if citation_style_param in ("below", "smallcaps", "none") else "below",
            citation_color=normalize_color(citation_color_param),
            accent_color=normalize_color(accent_color_param),
            optical_center_pct=optical_center,
            balance_lines=balance_lines,
            show_tags=tags_param,
            backend=backend_param,
            output_format="svg" if fmt_param == "svg" else fmt_param,
        )

        max_verses_val = None
        if max_verses_raw:
            try:
                max_verses_val = int(max_verses_raw)
            except ValueError:
                max_verses_val = None

        max_lines_val = None
        if max_lines_raw:
            try:
                max_lines_val = int(max_lines_raw)
            except ValueError:
                max_lines_val = None

        max_chars_val = None
        if max_chars_raw:
            try:
                max_chars_val = int(max_chars_raw)
            except ValueError:
                max_chars_val = None

        if paginate_param in ("false", "0", "no"):
            pagination = PaginationConfig(enabled=False)
        else:
            pagination = PaginationConfig(
                enabled=True,
                mode="always" if paginate_param in ("true", "1", "always") else "auto",
                max_verses_per_slide=max_verses_val,
                max_lines_per_slide=max_lines_val,
                max_chars_per_slide=max_chars_val,
                indicator_format=page_format_param,
                sub_citations=not keep_cit_param,
                keep_parent_citation=keep_cit_param,
            )

        pages = paginate_verses(
            verses=verses,
            parent_ref=parsed_ref,
            config=config,
            pagination=pagination,
            pericope_title=pericope_title,
            tags=slide_tags,
        )

        if not pages:
            pages = [
                SlideContent(
                    text=verse_text,
                    citation=citation,
                    translation=used_id,
                    pericope_title=pericope_title,
                    tags=slide_tags,
                )
            ]

        # JSON manifest response
        if fmt_param == "json":
            from urllib.parse import quote
            pages_data = []
            for i, p in enumerate(pages, start=1):
                pages_data.append({
                    "page": i,
                    "total": len(pages),
                    "citation": p.citation,
                    "page_indicator": p.page_indicator,
                    "text": p.text,
                    "tags": p.tags,
                    "svg_url": f"/api/slide?ref={quote(citation)}&page={i}&format=svg",
                })
            self.send_json({
                "reference": citation,
                "translation": used_id,
                "total_pages": len(pages),
                "pages": pages_data,
            })
            return

        try:
            page_idx = int(page_param) - 1
            if page_idx < 0 or page_idx >= len(pages):
                page_idx = 0
        except ValueError:
            page_idx = 0

        content = pages[page_idx]

        try:
            engine = get_default_engine()
            res = engine.render(content, config)
            if res.format == "svg":
                svg_data = res.data.decode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Content-Length", str(len(res.data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("X-Bible-Slide-Page", str(page_idx + 1))
                self.send_header("X-Bible-Slide-Total-Pages", str(len(pages)))
                self.send_header("X-Bible-Slide-Citation", content.citation)
                if content.page_indicator:
                    self.send_header("X-Bible-Slide-Indicator", content.page_indicator)
                self.end_headers()
                self.wfile.write(res.data)
            else:
                self.send_response(200)
                self.send_header("Content-Type", res.mime_type)
                self.send_header("Content-Length", str(len(res.data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("X-Bible-Slide-Page", str(page_idx + 1))
                self.send_header("X-Bible-Slide-Total-Pages", str(len(pages)))
                self.send_header("X-Bible-Slide-Citation", content.citation)
                if content.page_indicator:
                    self.send_header("X-Bible-Slide-Indicator", content.page_indicator)
                self.end_headers()
                self.wfile.write(res.data)
        except Exception as exc:
            self.send_json_error(f"Slide rendering error: {exc}", status=500)

    def handle_stats(self) -> None:
        """GET /api/stats — Global database aggregate statistics."""
        try:
            crossref_svc = CrossReferenceService(self.db)
            xref_stats = crossref_svc.get_summary_statistics()
            self.send_json({
                "total_verses": self.db.count_verses(),
                "total_books": len(ALL_BOOKS),
                "translations_count": len(self.db.list_translations()),
                "tags_count": len(self.db.list_tags()),
                "cross_reference_edges": xref_stats.total_edges,
            })
        except Exception as exc:
            self.send_json_error(f"Failed to retrieve database stats: {exc}", status=500)

    # -------------------------------------------------------------------------
    # Static File Serving
    # -------------------------------------------------------------------------

    def serve_static(self, path: str) -> None:
        """Serve static web assets safely, preventing directory traversal."""
        static_dir = getattr(self, "static_dir", DEFAULT_STATIC_DIR)

        # Normalize requested path
        clean_path = path.strip()
        if clean_path in ("", "/", "/index.html"):
            rel_path = "index.html"
        elif clean_path.startswith("/static/"):
            rel_path = clean_path[len("/static/"):]
        else:
            rel_path = clean_path.lstrip("/")

        # Security check: resolve file path and verify it stays inside static_dir
        base_dir = static_dir.resolve()
        target_path = (base_dir / rel_path).resolve()

        if not target_path.is_relative_to(base_dir):
            self.send_error(403, "Forbidden: Path traversal is not permitted")
            return

        if not target_path.is_file():
            self.send_error(404, f"File not found: '{rel_path}'")
            return

        # Determine MIME type
        content_type, _ = mimetypes.guess_type(str(target_path))
        if not content_type:
            content_type = "application/octet-stream"
        if content_type.startswith("text/") or content_type in (
            "application/javascript",
            "application/json",
            "image/svg+xml",
        ):
            content_type += "; charset=utf-8"

        try:
            content = target_path.read_bytes()
        except OSError as exc:
            self.send_error(500, f"Error reading file: {exc}")
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(content)


class BibleWebServer:
    """Encapsulates the multi-threaded HTTP server lifecycle and database access."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        db_path: Optional[Union[str, Path]] = None,
        database: Optional[Database] = None,
        static_dir: Optional[Union[str, Path]] = None,
        verbose: bool = False,
    ) -> None:
        """Initialize web server.

        Args:
            host: Bind host IP or hostname (default: 127.0.0.1).
            port: Bind port (default: 8080, use 0 for ephemeral test allocation).
            db_path: Path to SQLite database file if database is not directly supplied.
            database: Optional pre-configured Database instance.
            static_dir: Directory containing static assets (defaults to web/static).
            verbose: If True, log HTTP request lines to stderr.
        """
        self.host = host
        self.requested_port = port
        self.verbose = verbose

        if database is not None:
            self.database = database
            self._owns_database = False
        else:
            resolved_db = Path(db_path) if db_path else DEFAULT_DB_PATH
            self.database = Database(db_path=resolved_db, check_same_thread=False)
            self._owns_database = True

        self.static_dir = Path(static_dir) if static_dir else DEFAULT_STATIC_DIR

        # Create localized request handler subclass bound to this server instance
        db_ref = self.database
        static_ref = self.static_dir
        verbose_flag = self.verbose

        class BoundHandler(BibleRequestHandler):
            db = db_ref
            static_dir = static_ref
            verbose = verbose_flag

        self.handler_class = BoundHandler
        self.httpd = http.server.ThreadingHTTPServer((self.host, self.requested_port), self.handler_class)
        self.bound_host, self.port = self.httpd.server_address[:2]
        self._is_running = False

    @property
    def url(self) -> str:
        """Return base HTTP URL for the running server."""
        return f"http://{self.bound_host}:{self.port}"

    def start(self, open_browser: bool = False) -> None:
        """Start serving HTTP requests indefinitely.

        Args:
            open_browser: If True, spawn a background timer to open browser at server URL.
        """
        self._is_running = True
        if open_browser:
            timer = threading.Timer(0.3, lambda: webbrowser.open(self.url))
            timer.daemon = True
            timer.start()

        try:
            self.httpd.serve_forever()
        finally:
            self._is_running = False

    def shutdown(self) -> None:
        """Gracefully stop server and close database connection."""
        self.httpd.shutdown()
        self.httpd.server_close()
        self._is_running = False
        if self._owns_database:
            self.database.close()

    def is_running(self) -> bool:
        """Check if server is currently active."""
        return self._is_running


def create_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    db_path: Optional[Union[str, Path]] = None,
    database: Optional[Database] = None,
    static_dir: Optional[Union[str, Path]] = None,
    verbose: bool = False,
) -> BibleWebServer:
    """Factory function to instantiate a BibleWebServer instance."""
    return BibleWebServer(
        host=host,
        port=port,
        db_path=db_path,
        database=database,
        static_dir=static_dir,
        verbose=verbose,
    )
