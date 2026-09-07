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
from pathlib import Path
import threading
import time
import unittest
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
        self.assertIn("Unknown API endpoint", data["error"])


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

