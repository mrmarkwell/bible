"""Hermetic unit tests for the built-in HTTP server and REST API engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003).
Verifies:
  - HTTP Server lifecycle and ephemeral port binding.
  - Safe static web asset dispatch and MIME type resolution.
  - Path traversal protection (HTTP 403 Forbidden).
  - CORS header propagation and OPTIONS pre-flight handling.
  - Complete REST API suite (/api/health, /api/books, /api/passage, /api/verses,
    /api/search, /api/translations, /api/tags, /api/tags/density,
    /api/tags/co-occurrence, /api/tags/relevance, /api/crossref, /api/stats).
  - Validation error handling (HTTP 400 Bad Request, HTTP 404 Not Found).
  - CLI parser and REPL /serve command integration.
"""

import io
import json
import threading
import time
from typing import Any, Optional
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from cli.main import build_parser, preprocess_cli_argv
from cli.shell import BibleShell
from core.db import DEFAULT_DB_PATH, Database
from web.server import BibleWebServer, create_server


class TestWebServerEndpoints(unittest.TestCase):
    """Hermetic tests against an ephemeral local HTTP server instance."""

    server: BibleWebServer
    server_thread: threading.Thread

    @classmethod
    def setUpClass(cls) -> None:
        # Use existing bundled SQLite database with check_same_thread=False
        cls.db = Database(DEFAULT_DB_PATH, check_same_thread=False)
        # Bind to port 0 for ephemeral port allocation
        cls.server = create_server(
            host="127.0.0.1",
            port=0,
            database=cls.db,
            verbose=False,
        )
        cls.server_thread = threading.Thread(target=cls.server.start, daemon=True)
        cls.server_thread.start()
        # Wait until server is listening
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server_thread.join(timeout=2.0)
        cls.db.close()

    def _get(self, path: str) -> tuple[int, dict, bytes]:
        """Perform HTTP GET request and return (status_code, headers_dict, body_bytes)."""
        url = f"{self.server.url}{path}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                headers = dict(resp.headers)
                body = resp.read()
                return status, headers, body
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()

    def _get_json(self, path: str) -> tuple[int, dict]:
        """Perform HTTP GET request expecting JSON response."""
        status, _, body = self._get(path)
        data = json.loads(body.decode("utf-8"))
        return status, data

    def _post(self, path: str, payload: Optional[Any] = None) -> tuple[int, dict, bytes]:
        """Perform HTTP POST request with JSON payload."""
        url = f"{self.server.url}{path}"
        data_bytes = json.dumps(payload).encode("utf-8") if payload is not None else b""
        req = urllib.request.Request(
            url,
            data=data_bytes,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                headers = dict(resp.headers)
                body = resp.read()
                return status, headers, body
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()

    def _post_json(self, path: str, payload: Optional[Any] = None) -> tuple[int, dict]:
        """Perform HTTP POST request expecting JSON response."""
        status, _, body = self._post(path, payload)
        data = json.loads(body.decode("utf-8"))
        return status, data

    # -------------------------------------------------------------------------
    # Static Assets & Security Tests
    # -------------------------------------------------------------------------

    def test_serve_root_index_html(self) -> None:
        status, headers, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        self.assertIn(b"BIBLE ENGINE", body)

    def test_serve_static_style_css(self) -> None:
        status, headers, body = self._get("/style.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", headers.get("Content-Type", ""))
        self.assertIn(b":root", body)

    def test_serve_static_app_js(self) -> None:
        status, headers, body = self._get("/app.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers.get("Content-Type", "").lower())
        self.assertIn(b"DOMContentLoaded", body)

    def test_sacred_modern_design_system_tokens_in_css(self) -> None:
        status, _, body = self._get("/style.css")
        self.assertEqual(status, 200)
        css_text = body.decode("utf-8")
        self.assertIn("--bg-obsidian: #0D0E11", css_text)
        self.assertIn("--gold-primary: #D4AF37", css_text)
        self.assertIn('[data-theme="obsidian"]', css_text)
        self.assertIn('[data-theme="scriptorium"]', css_text)
        self.assertIn('[data-theme="monastery"]', css_text)
        self.assertIn(".flow-mode", css_text)
        self.assertIn(".chapter-nav-bar", css_text)
        self.assertIn(".shortcuts-table", css_text)
        self.assertIn(".ribbon-legend-bar", css_text)
        self.assertIn('.canon-book-btn[data-heat="4"]', css_text)

    def test_sacred_modern_html_elements(self) -> None:
        status, _, body = self._get("/")
        self.assertEqual(status, 200)
        html_text = body.decode("utf-8")
        self.assertIn('data-theme="obsidian"', html_text)
        self.assertIn('id="select-theme"', html_text)
        self.assertIn('id="btn-toggle-flow"', html_text)
        self.assertIn('id="btn-copy-passage"', html_text)
        self.assertIn('id="chapter-breadcrumbs"', html_text)
        self.assertIn('id="shortcuts-modal"', html_text)
        self.assertIn('id="select-ribbon-tag"', html_text)
        self.assertIn('id="ribbon-legend-bar"', html_text)
        self.assertIn('id="ot-book-grid"', html_text)
        self.assertIn('id="nt-book-grid"', html_text)

    def test_sacred_modern_js_capabilities(self) -> None:
        status, _, body = self._get("/app.js")
        self.assertEqual(status, 200)
        js_text = body.decode("utf-8")
        self.assertIn("setTheme", js_text)
        self.assertIn("cycleTheme", js_text)
        self.assertIn("copyCurrentPassage", js_text)
        self.assertIn("toggleFlowMode", js_text)
        self.assertIn("renderCanonicalRibbon", js_text)
        self.assertIn("loadRibbonDensity", js_text)
        self.assertIn("populateRibbonTagSelector", js_text)
        self.assertIn("shortcutsModal", js_text)

    def test_app_js_syntax_integrity(self) -> None:
        """Verify web/static/app.js has zero unclosed brackets, braces, or quotes."""
        status, _, body = self._get("/app.js")
        self.assertEqual(status, 200)
        code = body.decode("utf-8")

        stack: list[tuple[str, int, int]] = []
        i = 0
        n = len(code)
        line = 1
        col = 0
        state = "NORMAL"
        escape = False

        while i < n:
            c = code[i]
            col += 1
            if c == "\n":
                line += 1
                col = 0
                if state == "LINE_COMMENT":
                    state = "NORMAL"
                i += 1
                escape = False
                continue

            if state == "LINE_COMMENT":
                i += 1
                continue

            if state == "BLOCK_COMMENT":
                if c == "*" and i + 1 < n and code[i + 1] == "/":
                    state = "NORMAL"
                    i += 2
                    col += 1
                    continue
                i += 1
                continue

            if state == "SINGLE_QUOTE":
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == "'":
                    state = "NORMAL"
                i += 1
                continue

            if state == "DOUBLE_QUOTE":
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == '"':
                    state = "NORMAL"
                i += 1
                continue

            if state == "TEMPLATE":
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == "`":
                    if stack and stack[-1][0] == "`":
                        stack.pop()
                    state = "NORMAL"
                elif c == "$" and i + 1 < n and code[i + 1] == "{":
                    stack.append(("${", line, col))
                    state = "NORMAL"
                    i += 2
                    col += 1
                    continue
                i += 1
                continue

            if state == "REGEX":
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == "/":
                    state = "NORMAL"
                i += 1
                continue

            if c == "/" and i + 1 < n:
                if code[i + 1] == "/":
                    state = "LINE_COMMENT"
                    i += 2
                    col += 1
                    continue
                elif code[i + 1] == "*":
                    state = "BLOCK_COMMENT"
                    i += 2
                    col += 1
                    continue

            if c == "'":
                state = "SINGLE_QUOTE"
                i += 1
                continue
            if c == '"':
                state = "DOUBLE_QUOTE"
                i += 1
                continue
            if c == "`":
                state = "TEMPLATE"
                stack.append(("`", line, col))
                i += 1
                continue

            if c == "/":
                prev = code[:i].rstrip()
                if prev and prev[-1] in "=([" + ",:;!&|?{}+-*%^~":
                    state = "REGEX"
                    i += 1
                    continue
                for kw in ["return", "case", "delete", "throw", "void", "typeof"]:
                    if prev.endswith(kw):
                        state = "REGEX"
                        break
                if state == "REGEX":
                    i += 1
                    continue

            if c in "({[":
                stack.append((c, line, col))
            elif c in ")}]":
                self.assertTrue(bool(stack), f"Unexpected closing '{c}' at line {line}:{col}")
                top, top_line, top_col = stack[-1]
                matched = (
                    (top == "(" and c == ")")
                    or (top == "{" and c == "}")
                    or (top == "[" and c == "]")
                    or (top == "${" and c == "}")
                )
                self.assertTrue(
                    matched,
                    f"Delimiter mismatch: opened '{top}' at {top_line}:{top_col} but closed with '{c}' at {line}:{col}",
                )
                stack.pop()
                if top == "${":
                    state = "TEMPLATE"

            i += 1

        self.assertEqual(state, "NORMAL", f"Unfinished token state at EOF: {state}")
        self.assertEqual(len(stack), 0, f"Unclosed delimiters in app.js: {stack}")

    def test_global_hidden_utility_css_and_arc_stage_regression(self) -> None:
        """Regression test for Issue #1: Ensure .hidden utility hides elements and arc stage mounts SVG safely."""
        # 1. Verify /style.css contains universal .hidden rule
        status, _, body = self._get("/style.css")
        self.assertEqual(status, 200)
        css_text = body.decode("utf-8")
        self.assertIn(".hidden", css_text)
        self.assertIn("display: none !important", css_text)

        # 2. Verify index.html defines arc-visualizer-stage with hidden class
        status, _, body = self._get("/")
        self.assertEqual(status, 200)
        html_text = body.decode("utf-8")
        self.assertIn('class="arc-visualizer-stage hidden"', html_text)
        self.assertIn('id="arc-svg-viewport"', html_text)
        self.assertIn('app.js?v=', html_text)

        # 3. Verify app.js cleans XML prolog and implements race-condition request tracking
        status, _, body = self._get("/app.js")
        self.assertEqual(status, 200)
        js_text = body.decode("utf-8")
        self.assertIn("arcNetworkRequestId", js_text)
        self.assertIn("replace(/<\\?xml[^>]*\\?>/i", js_text)
        self.assertIn("switchView", js_text)
        self.assertIn("hashchange", js_text)

    def test_issue_2_passage_tags_no_duplicate_favorites_regression(self) -> None:
        """Regression test for Issue #2: Ensure #favorites tag is never duplicated in web UI or API."""
        # 1. Test passage with multiple favorites records (Genesis 15:1-21 has 15:6 and 15:18-21)
        status, data = self._get_json("/api/passage?ref=Genesis+15:1-21")
        self.assertEqual(status, 200)
        fav_tags = [t for t in data["tags"] if t["name"] == "favorites"]
        self.assertEqual(len(fav_tags), 1, f"Expected 1 favorites tag, got {len(fav_tags)}: {fav_tags}")
        self.assertEqual(fav_tags[0]["category"], "curation")

        # 2. Test Romans 8:28-39 (contains 4 separate favorite spans: 8:28, 8:29-30, 8:31, 8:38-39)
        status, data = self._get_json("/api/passage?ref=Romans+8:28-39")
        self.assertEqual(status, 200)
        fav_tags = [t for t in data["tags"] if t["name"] == "favorites"]
        self.assertEqual(len(fav_tags), 1, f"Expected 1 favorites tag, got {len(fav_tags)}: {fav_tags}")
        self.assertEqual(fav_tags[0]["category"], "curation")

        # 3. Test entire chapter (Romans 8 contains 6 separate favorite passages)
        status, data = self._get_json("/api/passage?ref=Romans+8")
        self.assertEqual(status, 200)
        fav_tags = [t for t in data["tags"] if t["name"] == "favorites"]
        self.assertEqual(len(fav_tags), 1, f"Expected 1 favorites tag, got {len(fav_tags)}: {fav_tags}")

        # 4. Verify verse-level tags deduplication
        for v in data["verses"]:
            self.assertEqual(
                len(v["tags"]),
                len(set(v["tags"])),
                f"Duplicate tags in verse {v['verse']}: {v['tags']}",
            )

        # 5. Verify app.js deduplicates tags defensively in UI rendering
        status, _, body = self._get("/app.js")
        self.assertEqual(status, 200)
        js_text = body.decode("utf-8")
        self.assertIn("seenTagNames", js_text)

    def test_serve_missing_file_returns_404(self) -> None:
        status, _, _ = self._get("/nonexistent_asset_404.txt")
        self.assertEqual(status, 404)

    def test_path_traversal_protection(self) -> None:
        status, _, _ = self._get("/../server.py")
        self.assertIn(status, (403, 404))

    def test_cors_options_preflight(self) -> None:
        url = f"{self.server.url}/api/health"
        req = urllib.request.Request(url, method="OPTIONS")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 204)
            self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")
            self.assertIn("GET", resp.headers.get("Access-Control-Allow-Methods", ""))

    # -------------------------------------------------------------------------
    # REST API Tests
    # -------------------------------------------------------------------------

    def test_api_health(self) -> None:
        status, data = self._get_json("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["engine"], "Bible Engine")
        self.assertGreater(data["total_verses"], 30000)
        self.assertIn("WEB", data["translations"])

    def test_api_books_catalog(self) -> None:
        status, data = self._get_json("/api/books")
        self.assertEqual(status, 200)
        self.assertEqual(data["total"], 66)
        self.assertEqual(len(data["books"]), 66)
        self.assertEqual(data["books"][0]["name"], "Genesis")

        # Testament filter OT
        status, ot_data = self._get_json("/api/books?testament=OT")
        self.assertEqual(status, 200)
        self.assertEqual(ot_data["total"], 39)

        # Testament filter NT
        status, nt_data = self._get_json("/api/books?testament=NT")
        self.assertEqual(status, 200)
        self.assertEqual(nt_data["total"], 27)

    def test_api_passage_lookup(self) -> None:
        status, data = self._get_json("/api/passage?ref=John+3:16")
        self.assertEqual(status, 200)
        self.assertEqual(data["reference"], "John 3:16")
        self.assertEqual(data["total_verses"], 1)
        self.assertEqual(len(data["verses"]), 1)
        self.assertIn("God so loved the world", data["verses"][0]["text"])

    def test_api_passage_multi_verse_range(self) -> None:
        status, data = self._get_json("/api/passage?ref=Romans+8:28-30")
        self.assertEqual(status, 200)
        self.assertEqual(data["reference"], "Romans 8:28-30")
        self.assertEqual(data["total_verses"], 3)
        self.assertEqual(data["verses"][0]["verse"], 28)
        self.assertEqual(data["verses"][2]["verse"], 30)

    def test_api_passage_missing_ref_error(self) -> None:
        status, data = self._get_json("/api/passage")
        self.assertEqual(status, 400)
        self.assertIn("Missing required query parameter", data["error"])

    def test_api_passage_invalid_ref_error(self) -> None:
        status, data = self._get_json("/api/passage?ref=ImaginaryBook+99:99")
        self.assertEqual(status, 400)
        self.assertIn("Invalid scripture reference", data["error"])

    def test_api_verses_by_chapter(self) -> None:
        status, data = self._get_json("/api/verses?book=GEN&chapter=1")
        self.assertEqual(status, 200)
        self.assertEqual(data["book"], "Genesis")
        self.assertEqual(data["chapter"], 1)
        self.assertEqual(data["total_verses"], 31)
        self.assertIn("In the beginning", data["verses"][0]["text"])

    def test_api_verses_invalid_chapter(self) -> None:
        status, data = self._get_json("/api/verses?book=GEN&chapter=999")
        self.assertEqual(status, 400)
        self.assertIn("out of range", data["error"])

    def test_api_search_fts5(self) -> None:
        status, data = self._get_json("/api/search?q=light+of+the+world")
        self.assertEqual(status, 200)
        self.assertEqual(data["query"], "light of the world")
        self.assertGreater(data["total_matches"], 0)
        self.assertGreater(len(data["results"]), 0)
        first_hit = data["results"][0]
        self.assertIn("snippet", first_hit)
        self.assertIn("light", first_hit["text"].lower())

    def test_api_search_with_testament_filter(self) -> None:
        status, data = self._get_json("/api/search?q=faith&testament=NT&limit=5")
        self.assertEqual(status, 200)
        self.assertLessEqual(len(data["results"]), 5)

    def test_api_search_missing_q_error(self) -> None:
        status, data = self._get_json("/api/search")
        self.assertEqual(status, 400)
        self.assertIn("Missing required query parameter: 'q'", data["error"])

    def test_api_translations_list(self) -> None:
        status, data = self._get_json("/api/translations")
        self.assertEqual(status, 200)
        self.assertGreater(data["total"], 0)
        translation_ids = [t["id"] for t in data["translations"]]
        self.assertIn("WEB", translation_ids)

    def test_api_tags_list(self) -> None:
        status, data = self._get_json("/api/tags")
        self.assertEqual(status, 200)
        self.assertGreater(data["total"], 0)
        tag_names = [t["name"] for t in data["tags"]]
        self.assertIn("favorites", tag_names)

    def test_api_tags_density(self) -> None:
        status, data = self._get_json("/api/tags/density?min_passages=1")
        self.assertEqual(status, 200)
        self.assertGreater(data["total_books"], 0)
        self.assertIn("densities", data)
        first = data["densities"][0]
        self.assertIn("book_name", first)
        self.assertIn("passage_count", first)

    def test_api_tags_co_occurrence(self) -> None:
        status, data = self._get_json("/api/tags/co-occurrence")
        self.assertEqual(status, 200)
        self.assertIn("tags", data)
        self.assertIn("pairs", data)

    def test_api_tags_relevance(self) -> None:
        status, data = self._get_json("/api/tags/relevance?tags=favorites&limit=5")
        self.assertEqual(status, 200)
        self.assertEqual(data["tags"], ["favorites"])
        self.assertGreater(data["total_results"], 0)
        first = data["results"][0]
        self.assertIn("citation", first)
        self.assertIn("score", first)
        self.assertIn("text", first)

    def test_api_tags_relevance_missing_tags(self) -> None:
        status, data = self._get_json("/api/tags/relevance")
        self.assertEqual(status, 400)
        self.assertIn("Missing required query parameter: 'tags'", data["error"])

    def test_api_crossref_lookup(self) -> None:
        status, data = self._get_json("/api/crossref?ref=Genesis+1:1")
        self.assertEqual(status, 200)
        self.assertEqual(data["reference"], "Genesis 1:1")
        self.assertIn("cross_references", data)

    def test_api_crossref_missing_ref(self) -> None:
        status, data = self._get_json("/api/crossref")
        self.assertEqual(status, 400)
        self.assertIn("Missing required query parameter: 'ref'", data["error"])

    def test_api_crossref_stats(self) -> None:
        status, data = self._get_json("/api/crossref/stats")
        self.assertEqual(status, 200)
        self.assertGreater(data["total_edges"], 0)
        self.assertIn("by_relationship_type", data)

    def test_api_global_stats(self) -> None:
        status, data = self._get_json("/api/stats")
        self.assertEqual(status, 200)
        self.assertGreater(data["total_verses"], 30000)
        self.assertEqual(data["total_books"], 66)
        self.assertGreaterEqual(data["translations_count"], 1)

    def test_api_unknown_endpoint_404(self) -> None:
        status, data = self._get_json("/api/nonexistent_endpoint")
        self.assertEqual(status, 404)
    def test_api_pericopes_endpoint(self) -> None:
        status, data = self._get_json("/api/pericopes?ref=John+3:16")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(data["total_pericopes"], 1)
        self.assertTrue(any("Born Again" in p["title"] for p in data["pericopes"]))

        # Filter by book
        status, gen_data = self._get_json("/api/pericopes?book=Genesis")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(gen_data["total_pericopes"], 5)

    def test_api_tags_chapters_endpoint(self) -> None:
        status, data = self._get_json("/api/tags/chapters?book=Genesis")
        self.assertEqual(status, 200)
        self.assertEqual(data["book_name"], "Genesis")
        self.assertEqual(data["total_chapters"], 50)
        self.assertEqual(len(data["chapters"]), 50)
        self.assertEqual(data["chapters"][0]["chapter"], 1)

    def test_api_slide_svg_endpoint(self) -> None:
        status, headers, body = self._get("/api/slide?ref=John+3:16&theme=oled_black&res=1080p")
        self.assertEqual(status, 200)
        self.assertIn("image/svg+xml", headers.get("Content-Type", ""))
        self.assertIn(b"<svg", body)
        self.assertIn(b"John 3:16", body)

    def test_api_slide_rich_options(self) -> None:
        status, headers, body = self._get("/api/slide?ref=John+3:16&citation_color=%23E74C3C&accent_color=%232ECC71&safe_area=10%25&tags=true")
        self.assertEqual(status, 200)
        self.assertIn("image/svg+xml", headers.get("Content-Type", ""))
        body_text = body.decode("utf-8")
        self.assertIn("fill: #E74C3C", body_text)
        self.assertIn("stroke: #2ECC71", body_text)
        self.assertIn("John 3:16", body_text)

    def test_api_slide_missing_ref_error(self) -> None:
        status, data = self._get_json("/api/slide")
        self.assertEqual(status, 400)
        self.assertIn("Missing required query parameter: 'ref'", data["error"])

    def test_api_slide_json_manifest(self) -> None:
        status, data = self._get_json("/api/slide?ref=Romans+8:28-39&format=json")
        self.assertEqual(status, 200)
        self.assertIn("total_pages", data)
        self.assertGreater(data["total_pages"], 1)
        self.assertEqual(len(data["pages"]), data["total_pages"])
        self.assertEqual(data["pages"][0]["page"], 1)
        self.assertIn("Romans 8:", data["pages"][0]["citation"])
        self.assertIn("svg_url", data["pages"][0])

    def test_api_slide_pagination_headers_and_page_selection(self) -> None:
        status, headers, body = self._get("/api/slide?ref=Romans+8:28-39&page=2")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Bible-Slide-Page"), "2")
        total_pages = int(headers.get("X-Bible-Slide-Total-Pages", "1"))
        self.assertGreater(total_pages, 1)
        self.assertTrue(headers.get("X-Bible-Slide-Citation", "").startswith("Romans 8:"))
        self.assertEqual(headers.get("X-Bible-Slide-Indicator"), f"2 / {total_pages}")

    # -------------------------------------------------------------------------
    # Phase 8: Character Persona & Scripture RAG Endpoints (Task 8.5)
    # -------------------------------------------------------------------------

    def test_api_health_includes_gemini_and_characters(self) -> None:
        status, data = self._get_json("/api/health")
        self.assertEqual(status, 200)
        self.assertIn("gemini_api_available", data)
        self.assertIn("canonical_characters", data)
        self.assertGreaterEqual(data["canonical_characters"], 19)

    def test_api_characters_list(self) -> None:
        status, data = self._get_json("/api/characters")
        self.assertEqual(status, 200)
        self.assertIn("total", data)
        self.assertGreaterEqual(data["total"], 19)
        self.assertIn("api_available", data)
        self.assertIn("characters", data)
        self.assertTrue(any(c["id"] == "paul" for c in data["characters"]))
        self.assertTrue(any(c["id"] == "moses" for c in data["characters"]))

    def test_api_characters_testament_filter(self) -> None:
        status, data = self._get_json("/api/characters?testament=NT")
        self.assertEqual(status, 200)
        self.assertTrue(all(c["testament"] in ("NT", "BOTH") for c in data["characters"]))
        self.assertTrue(any(c["id"] == "paul" for c in data["characters"]))
        self.assertFalse(any(c["id"] == "abraham" for c in data["characters"]))

    def test_api_characters_search_filter(self) -> None:
        status, data = self._get_json("/api/characters?q=exile")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(data["total"], 1)

    def test_api_characters_single_by_path(self) -> None:
        status, data = self._get_json("/api/characters/paul")
        self.assertEqual(status, 200)
        self.assertEqual(data["character"]["id"], "paul")
        self.assertEqual(data["character"]["canonical_name"], "Paul (Apostle)")
        self.assertIn("grounded_passages", data)
        self.assertGreaterEqual(len(data["grounded_passages"]), 1)
        self.assertTrue(any("Romans" in p["reference"] for p in data["grounded_passages"]))

    def test_api_characters_single_by_query(self) -> None:
        status, data = self._get_json("/api/characters?id=moses")
        self.assertEqual(status, 200)
        self.assertEqual(data["character"]["id"], "moses")
        self.assertIn("grounded_passages", data)
        self.assertTrue(any("Exodus" in p["reference"] for p in data["grounded_passages"]))

    def test_api_characters_single_by_post(self) -> None:
        status, data = self._post_json("/api/characters", {"id": "david"})
        self.assertEqual(status, 200)
        self.assertEqual(data["character"]["id"], "david")
        self.assertIn("grounded_passages", data)

    def test_api_characters_not_found(self) -> None:
        status, data = self._get_json("/api/characters/nonexistent_character")
        self.assertEqual(status, 404)
        self.assertIn("error", data)
        self.assertIn("Available", data["error"])

    def test_api_rag_missing_query_error(self) -> None:
        status, data = self._get_json("/api/rag")
        self.assertEqual(status, 400)
        self.assertIn("Missing required parameter: 'query'", data["error"])

    def test_api_rag_get_retrieval(self) -> None:
        status, data = self._get_json("/api/rag?q=temple+dwelling+presence&max_passages=3")
        self.assertEqual(status, 200)
        self.assertEqual(data["query"], "temple dwelling presence")
        self.assertIn("context", data)
        self.assertFalse(data["synthesized"])
        self.assertIn("thematic_ribbons", data)
        self.assertLessEqual(data["total_passages"], 3)
        self.assertGreaterEqual(data["total_passages"], 1)

    def test_api_rag_post_retrieval(self) -> None:
        status, data = self._post_json(
            "/api/rag",
            {"query": "Garden of Eden to New Jerusalem", "max_passages": 2},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["query"], "Garden of Eden to New Jerusalem")
        self.assertLessEqual(data["total_passages"], 2)
        self.assertIn("passages", data["context"])

    def test_api_rag_offline_synthesis(self) -> None:
        # In unkeyed environment, requesting synthesis must produce graceful offline status without 500 error
        status, data = self._get_json("/api/rag?q=justification+by+faith&synthesize=true")
        self.assertEqual(status, 200)
        self.assertIsNone(data["answer"])
        self.assertTrue(data["offline_fallback"])
        self.assertFalse(data["api_available"])
        self.assertIn("offline_message", data)
        self.assertIn("context", data)

    def test_api_rag_mock_online_synthesis(self) -> None:
        from core.rag import RAGContextWindow, RAGResponse

        with patch("core.llm.GeminiClient.is_available", return_value=True):
            with patch("core.rag.ScriptureRAGEngine.answer") as mock_answer:
                mock_answer.return_value = RAGResponse(
                    query="temple theme",
                    answer="From Eden to New Jerusalem, God dwells with man.",
                    context=RAGContextWindow(query="temple theme", passages=[]),
                    model="gemini-2.5-pro",
                    token_usage={"total_tokens": 150},
                )
                status, data = self._post_json(
                    "/api/rag",
                    {"query": "temple theme", "synthesize": True},
                )
                self.assertEqual(status, 200)
                self.assertTrue(data["synthesized"])
                self.assertTrue(data["api_available"])
                self.assertFalse(data["offline_fallback"])
                self.assertEqual(data["answer"], "From Eden to New Jerusalem, God dwells with man.")
                self.assertEqual(data["model"], "gemini-2.5-pro")

    def test_api_chat_persona_missing_params(self) -> None:
        status, data = self._post_json("/api/chat/persona", {"message": "Hello"})
        self.assertEqual(status, 400)
        self.assertIn("Missing required parameter: 'character'", data["error"])

        status, data = self._post_json("/api/chat/persona", {"character": "paul"})
        self.assertEqual(status, 400)
        self.assertIn("Missing required parameter: 'message'", data["error"])

    def test_api_chat_persona_unknown_character(self) -> None:
        status, data = self._post_json("/api/chat/persona", {"character": "nobody", "message": "Hi"})
        self.assertEqual(status, 404)
        self.assertIn("Unknown biblical persona", data["error"])

    def test_api_chat_persona_offline_get(self) -> None:
        status, data = self._get_json(
            "/api/chat/persona?character=paul&message=Why+do+you+boast+in+weakness?"
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["character"]["id"], "paul")
        self.assertEqual(data["user_message"], "Why do you boast in weakness?")
        self.assertTrue(data["offline_fallback"])
        self.assertIn("OFFLINE PERSONA PROFILE", data["response"])
        self.assertGreaterEqual(len(data["grounded_passages"]), 1)
        self.assertEqual(len(data["history"]), 2)
        self.assertEqual(data["history"][0]["role"], "user")
        self.assertEqual(data["history"][1]["role"], "model")

    def test_api_chat_persona_offline_post(self) -> None:
        status, data = self._post_json(
            "/api/chat/persona",
            {"character": "moses", "message": "Why did you strike the rock?"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["character"]["id"], "moses")
        self.assertTrue(data["offline_fallback"])
        self.assertIn("OFFLINE PERSONA PROFILE", data["response"])
        self.assertEqual(len(data["history"]), 2)

    def test_api_chat_persona_with_multi_turn_history(self) -> None:
        history = [
            {"role": "user", "content": "Who called you to journey?"},
            {"role": "model", "content": "The Lord called me out of Ur of the Chaldees."},
        ]
        status, data = self._post_json(
            "/api/chat/persona",
            {
                "character": "abraham",
                "message": "What was God's covenant promise?",
                "history": history,
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(data["history"]), 4)
        self.assertEqual(data["history"][0]["content"], "Who called you to journey?")
        self.assertEqual(data["history"][1]["content"], "The Lord called me out of Ur of the Chaldees.")
        self.assertEqual(data["history"][2]["content"], "What was God's covenant promise?")
        self.assertIn("OFFLINE PERSONA PROFILE", data["history"][3]["content"])

    def test_api_chat_persona_mock_online_generation(self) -> None:
        from core.llm import LLMResponse

        mock_llm_resp = LLMResponse(
            text="Grace to you and peace from God our Father and the Lord Jesus Christ.",
            model="gemini-2.5-pro",
        )
        with patch("core.llm.GeminiClient.is_available", return_value=True):
            with patch("core.llm.GeminiClient.generate_content", return_value=mock_llm_resp):
                status, data = self._post_json(
                    "/api/chat/persona",
                    {"character": "paul", "message": "Greetings, Apostle Paul!"},
                )
                self.assertEqual(status, 200)
                self.assertFalse(data["offline_fallback"])
                self.assertTrue(data["api_available"])
                self.assertEqual(
                    data["response"],
                    "Grace to you and peace from God our Father and the Lord Jesus Christ.",
                )
                self.assertEqual(len(data["history"]), 2)

    def test_api_chat_stream_offline(self) -> None:
        """Verify /api/chat/stream SSE endpoint streams offline fallback event."""
        status, headers, body = self._get(
            "/api/chat/stream?character=paul&message=Greetings"
        )
        self.assertEqual(status, 200)
        self.assertIn("text/event-stream", headers.get("Content-Type", ""))
        text = body.decode("utf-8")
        self.assertIn("event: start", text)
        self.assertIn("event: token", text)
        self.assertIn("event: done", text)
        self.assertIn("OFFLINE PERSONA PROFILE", text)

    def test_api_chat_stream_missing_params(self) -> None:
        """Verify /api/chat/stream returns error for missing parameters."""
        status, data = self._get_json("/api/chat/stream")
        self.assertEqual(status, 400)
        self.assertIn("Missing required parameter", data["error"])

    def test_api_rag_stream_offline(self) -> None:
        """Verify /api/rag/stream SSE endpoint streams context and offline event when unkeyed."""
        status, headers, body = self._get(
            "/api/rag/stream?q=justification+by+faith"
        )
        self.assertEqual(status, 200)
        self.assertIn("text/event-stream", headers.get("Content-Type", ""))
        text = body.decode("utf-8")
        self.assertIn("event: context", text)
        self.assertIn("event: offline", text)
        self.assertIn("event: done", text)

    def test_api_rag_stream_missing_query(self) -> None:
        """Verify /api/rag/stream returns 400 for missing query."""
        status, data = self._get_json("/api/rag/stream")
        self.assertEqual(status, 400)
        self.assertIn("Missing required parameter: 'query'", data["error"])

    def test_api_cors_options_post_allowed(self) -> None:
        req = urllib.request.Request(
            f"{self.server.url}/api/chat/persona",
            method="OPTIONS",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 204)
            methods = resp.headers.get("Access-Control-Allow-Methods", "")
            self.assertIn("POST", methods)
            self.assertIn("GET", methods)
            headers_allowed = resp.headers.get("Access-Control-Allow-Headers", "")
            self.assertIn("Content-Type", headers_allowed)


    def test_web_ui_rag_study_and_character_studio_integration(self) -> None:
        """Verify Web UI HTML and JavaScript provide complete RAG Study and Character Dialogue panels."""
        # 1. Verify index.html contains all RAG and Persona elements
        status, _, body = self._get("/")
        self.assertEqual(status, 200)
        html_text = body.decode("utf-8")
        self.assertIn('data-view="rag"', html_text)
        self.assertIn('data-view="persona"', html_text)
        self.assertIn('id="panel-rag"', html_text)
        self.assertIn('id="panel-persona"', html_text)
        self.assertIn('id="rag-study-stage"', html_text)
        self.assertIn('id="persona-studio-stage"', html_text)
        self.assertIn('id="input-rag-query"', html_text)
        self.assertIn('id="btn-run-rag"', html_text)
        self.assertIn('id="select-persona-character"', html_text)
        self.assertIn('id="persona-message-input"', html_text)
        self.assertIn('id="btn-persona-send"', html_text)

        # 2. Verify style.css defines split-screen and studio styles
        status, _, body = self._get("/style.css")
        self.assertEqual(status, 200)
        css_text = body.decode("utf-8")
        self.assertIn(".rag-split-container", css_text)
        self.assertIn(".rag-scripture-column", css_text)
        self.assertIn(".rag-notes-column", css_text)
        self.assertIn(".persona-studio-split", css_text)
        self.assertIn(".persona-chat-column", css_text)
        self.assertIn(".persona-reference-column", css_text)
        self.assertIn(".chat-bubble", css_text)

        # 3. Verify app.js defines RAG and Character Dialogue functions
        status, _, body = self._get("/app.js")
        self.assertEqual(status, 200)
        js_text = body.decode("utf-8")
        self.assertIn("executeRAGStudy", js_text)
        self.assertIn("loadCharacters", js_text)
        self.assertIn("populateCharacterSelector", js_text)
        self.assertIn("renderActivePersona", js_text)
        self.assertIn("sendPersonaMessage", js_text)
        self.assertIn("renderChatHistory", js_text)
        self.assertIn("appendChatBubble", js_text)


class TestWebCliAndShellIntegration(unittest.TestCase):
    """Test CLI argument parsing and REPL shell integration for the web server."""

    def test_cli_parser_serve_subcommand(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve", "--port", "9090", "--host", "0.0.0.0", "--open", "--verbose"])
        self.assertEqual(args.port, 9090)
        self.assertEqual(args.host, "0.0.0.0")
        self.assertTrue(args.open)
        self.assertTrue(args.verbose)

    def test_cli_preprocess_argv_preserves_serve(self) -> None:
        processed = preprocess_cli_argv(["serve", "--port", "8080"])
        self.assertEqual(processed, ["serve", "--port", "8080"])

    def test_shell_serve_command_status_and_lifecycle(self) -> None:
        out = io.StringIO()
        with BibleShell(stdout=out, color=False) as shell:
            # Check status when stopped
            shell.do_serve("status")
            self.assertIn("Web server is stopped", out.getvalue())

            # Stop when not running
            out.seek(0)
            out.truncate(0)
            shell.do_serve("stop")
            self.assertIn("Web server is not running", out.getvalue())

            # Start on ephemeral port
            out.seek(0)
            out.truncate(0)
            shell.do_serve("start -p 0")
            self.assertIn("web server started", out.getvalue())

            # Status when running
            out.seek(0)
            out.truncate(0)
            shell.do_serve("status")
            self.assertIn("active at http://", out.getvalue())

            # Stop when running
            out.seek(0)
            out.truncate(0)
            shell.do_serve("stop")
            self.assertIn("web server stopped", out.getvalue())

    def test_web_package_exports(self) -> None:
        import web
        for symbol in [
            "DEFAULT_HOST",
            "DEFAULT_PORT",
            "DEFAULT_STATIC_DIR",
            "BibleRequestHandler",
            "BibleWebServer",
            "create_server",
        ]:
            self.assertTrue(hasattr(web, symbol), f"web package missing export: {symbol}")
            self.assertIn(symbol, web.__all__)


if __name__ == "__main__":
    unittest.main()

