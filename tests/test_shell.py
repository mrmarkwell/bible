"""Hermetic unit tests for the interactive Scripture REPL Shell and direct citation routing.

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cli.main import preprocess_cli_argv
from cli.shell import BibleShell
from core.db import Database, VerseRecord


class TestShell(unittest.TestCase):
    """Hermetic unit tests for BibleShell."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.temp_dir.name) / "test_shell.db"
        cls.db = Database(cls.db_path, auto_init=True)
        cls.db.add_translation("WEB", "World English Bible")
        cls.db.add_translation("KJV", "King James Version")
        cls.db.insert_verses(
            [
                VerseRecord(
                    translation_id="WEB",
                    book_id=1,
                    chapter=1,
                    verse=1,
                    text="In the beginning, God created the heavens and the earth.",
                ),
                VerseRecord(
                    translation_id="WEB",
                    book_id=43,
                    chapter=3,
                    verse=16,
                    text="For God so loved the world, that he gave his one and only Son.",
                ),
                VerseRecord(
                    translation_id="KJV",
                    book_id=43,
                    chapter=3,
                    verse=16,
                    text="For God so loved the world, that he gave his only begotten Son.",
                ),
            ]
        )

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.temp_dir.cleanup()

    def setUp(self):
        self.shells = []

    def tearDown(self):
        for s in self.shells:
            s.close()

    def _create_shell(self, theme="plain", margin=0, box=False, color=False):
        stdout = io.StringIO()
        shell = BibleShell(
            db_path=self.db_path,
            translation_id="WEB",
            theme=theme,
            margin=margin,
            box=box,
            color=color,
            stdout=stdout,
        )
        self.shells.append(shell)
        return shell, stdout

    def test_shell_direct_reference(self):
        shell, stdout = self._create_shell()
        shell.default("John 3:16")
        out = stdout.getvalue()
        self.assertIn("John 3:16 (WEB)", out)
        self.assertIn("one and only Son", out)

    def test_shell_slash_get(self):
        shell, stdout = self._create_shell()
        shell.onecmd("/get Genesis 1:1")
        out = stdout.getvalue()
        self.assertIn("Genesis 1:1 (WEB)", out)
        self.assertIn("created the heavens and the earth", out)

    def test_shell_slash_search(self):
        shell, stdout = self._create_shell()
        shell.onecmd("/search world")
        out = stdout.getvalue()
        self.assertIn('Scripture Search: "world" (WEB)', out)
        self.assertIn("John 3:16 (WEB)", out)

    def test_shell_slash_compare(self):
        shell, stdout = self._create_shell()
        shell.onecmd("/compare 'John 3:16' WEB,KJV")
        out = stdout.getvalue()
        self.assertIn("Compare: John 3:16", out)
        self.assertIn("[WEB]", out)
        self.assertIn("[KJV]", out)

    def test_shell_version_management(self):
        shell, stdout = self._create_shell()
        # List versions
        shell.onecmd("/versions")
        out = stdout.getvalue()
        self.assertIn("WEB", out)
        self.assertIn("KJV", out)

        # Switch version to KJV
        shell.onecmd("/version KJV")
        self.assertEqual(shell.translation_id, "KJV")
        self.assertIn("Switched session translation to KJV", stdout.getvalue())

        # Switch version to ESV
        shell.onecmd("/version ESV")
        self.assertEqual(shell.translation_id, "ESV")
        self.assertIn("Switched session translation to ESV", stdout.getvalue())
        self.assertNotIn("Warning: Translation 'ESV' has 0 verses installed", stdout.getvalue())

        # Verify ESV is listed in /versions
        shell.onecmd("/versions")
        self.assertIn("ESV", stdout.getvalue())
        self.assertIn("English Standard Version", stdout.getvalue())

    def test_shell_theme_switching(self):
        shell, stdout = self._create_shell()
        shell.onecmd("/theme amber")
        self.assertEqual(shell.theme, "amber")
        self.assertIn("Switched theme to 'amber'", stdout.getvalue())

        shell.onecmd("/theme invalid_theme")
        self.assertIn("Unknown theme", stdout.getvalue())

    def test_shell_margin_and_flow_and_box(self):
        shell, stdout = self._create_shell()
        shell.onecmd("/margin 4")
        self.assertEqual(shell.margin, 4)

        shell.onecmd("/flow on")
        self.assertTrue(shell.flow)
        shell.onecmd("/flow off")
        self.assertFalse(shell.flow)

        shell.onecmd("/box on")
        self.assertTrue(shell.box)
        shell.onecmd("/box off")
        self.assertFalse(shell.box)

    def test_shell_help_and_exit(self):
        shell, stdout = self._create_shell()
        shell.onecmd("/help")
        self.assertIn("Command Reference", stdout.getvalue())

        res = shell.onecmd("exit")
        self.assertTrue(res)
        self.assertIn("Grace and peace", stdout.getvalue())

    def test_shell_autocompletion(self):
        shell, _ = self._create_shell()
        themes = shell.complete_theme("sa", "theme sa", 0, 0)
        self.assertIn("sacred", themes)

        versions = shell.complete_version("W", "version W", 0, 0)
        self.assertIn("WEB", versions)

        names = shell.completenames("sea")
        self.assertIn("search", names)
        self.assertIn("/search", names)

        # Book autocompletion
        gen = shell.completenames("Gen")
        self.assertIn("Genesis", gen)

        # Doctor autocompletion
        doc = shell.complete_doctor("fas", "doctor fas", 0, 0)
        self.assertIn("fast", doc)

    def test_shell_doctor_commands(self):
        shell, stdout = self._create_shell()
        shell.onecmd("/doctor hooks")
        self.assertIn("Git Hook Safeguards", stdout.getvalue())

        stdout.truncate(0)
        stdout.seek(0)
        shell.onecmd("/doctor fast")
        self.assertIn("Fast Pre-Commit Mode", stdout.getvalue())
        self.assertIn("EXCELLENT", stdout.getvalue())

    def test_shell_db_and_init_commands(self):
        shell, stdout = self._create_shell()
        shell.onecmd("/db stats")
        self.assertIn("Database Storage Diagnostics", stdout.getvalue())
        self.assertIn("Total Verses:", stdout.getvalue())

        stdout.truncate(0)
        stdout.seek(0)
        shell.onecmd("/db optimize")
        self.assertIn("Successfully ran PRAGMA optimize", stdout.getvalue())

        stdout.truncate(0)
        stdout.seek(0)
        shell.onecmd("/db vacuum")
        self.assertIn("Successfully vacuumed", stdout.getvalue())

        stdout.truncate(0)
        stdout.seek(0)
        shell.onecmd("/help")
        self.assertIn("/db", stdout.getvalue())
        self.assertIn("/init", stdout.getvalue())

        # Autocompletion test
        db_opts = shell.complete_db("op", "db op", 0, 0)
        self.assertIn("optimize", db_opts)
        init_opts = shell.complete_init("--fo", "init --fo", 0, 0)
        self.assertIn("--force", init_opts)

    def test_shell_lint_command(self):
        stdout = io.StringIO()
        with BibleShell(db_path=self.db_path, stdout=stdout) as shell:
            shell.onecmd("/lint -p tools/linter.py")
            out = stdout.getvalue()
            self.assertIn("Static Analysis & Linter Engine", out)
            self.assertIn("CODE QUALITY: CLEAN", out)

    def test_shell_slide_batch_command(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            out_path = Path(temp_dir) / "shell_slides"
            with BibleShell(db_path=self.db_path, stdout=stdout) as shell:
                # Test list-plans
                shell.onecmd("/slide-batch --list-plans")
                out = stdout.getvalue()
                self.assertIn("Curated Scripture Reading Plans", out)
                self.assertIn("psalms_of_ascent", out)

                stdout.truncate(0)
                stdout.seek(0)

                # Test batch generation to svg
                shell.onecmd(f"/slide-batch 'John 3:16' 'Genesis 1:1' -f svg -d {out_path} --sequential")
                out2 = stdout.getvalue()
                self.assertIn("Generated 2 slides", out2)
                self.assertTrue((out_path / "manifest.json").exists())
                self.assertTrue((out_path / "index.html").exists())

                # Autocompletion test
                opts = shell.complete_slide_batch("--p", "/slide-batch --p", 0, 0)
                self.assertIn("--plan", opts)
                plan_opts = shell.complete_slide_batch("psalms", "/slide-batch --plan psalms", 0, 0)
    def test_shell_gemini_command(self):
        stdout = io.StringIO()
        with BibleShell(db_path=self.db_path, stdout=stdout) as shell:
            shell.onecmd("/gemini status")
            out = stdout.getvalue()
            self.assertIn("Google Gemini LLM Client", out)
            self.assertIn("gemini-2.5-pro", out)
            self.assertIn("gemini-2.0-flash", out)

            # Test context action
            stdout.truncate(0)
            stdout.seek(0)
            shell.onecmd("/gemini context John 3:16")
            out2 = stdout.getvalue()
            self.assertIn("Passage Context: John 3:16", out2)

            # Test autocompletion
            opts = shell.complete_gemini("con", "/gemini con", 0, 0)
            self.assertIn("context", opts)

    def test_shell_vector_command(self):
        stdout = io.StringIO()
        with BibleShell(db_path=self.db_path, stdout=stdout) as shell:
            shell.onecmd("/vector status")
            out = stdout.getvalue()
            self.assertIn("Zero-Dependency Vector Similarity Engine", out)
            self.assertIn("Verse Embeddings:", out)

            # Test autocompletion
            opts = shell.complete_vector("stat", "/vector stat", 0, 0)
            self.assertIn("status", opts)

    def test_shell_audit_semantic_command(self):
        stdout = io.StringIO()
        with BibleShell(db_path=self.db_path, stdout=stdout) as shell:
            shell.onecmd("/audit-semantic --json")
            out = stdout.getvalue()
            self.assertIn('"status": "PASSED"', out)
            self.assertIn('"audit_report"', out)

            # Test autocompletion
            opts = shell.complete_audit_semantic("--j", "/audit-semantic --j", 0, 0)
            self.assertIn("--json", opts)
            book_opts = shell.complete_audit_semantic("Rom", "/audit-semantic Rom", 0, 0)
            self.assertIn("Romans", book_opts)

    def test_shell_doctor_bench_completion(self):
        stdout = io.StringIO()
        with BibleShell(db_path=self.db_path, stdout=stdout) as shell:
            opts = shell.complete_doctor("ben", "/doctor ben", 0, 0)
            self.assertIn("bench", opts)
            self.assertIn("benchmark", opts)

    @patch("tools.github_issues.list_issues")
    def test_shell_issues_command(self, mock_list):
        mock_list.return_value = (True, [], "")
        stdout = io.StringIO()
        with BibleShell(db_path=self.db_path, stdout=stdout) as shell:
            with patch("sys.stdout", stdout):
                shell.onecmd("/issues")
            opts = shell.complete_issues("vi", "/issues vi", 0, 0)
            self.assertIn("view", opts)

    def test_shell_ask_context_only(self):
        out = io.StringIO()
        with BibleShell(db_path=self.db_path, database=self.db, stdout=out) as sh:
            sh.do_ask("--context-only God")
        val = out.getvalue()
        self.assertIn("Scripture RAG Retrieved Context", val)
        self.assertIn("Inquiry: God", val)

    def test_shell_ask_missing_api_key(self):
        out = io.StringIO()
        with patch.dict("os.environ", {}, clear=True):
            with BibleShell(db_path=self.db_path, database=self.db, stdout=out) as sh:
                sh.do_ask("God")
        val = out.getvalue()
        self.assertIn("GEMINI_API_KEY is not configured", val)
        self.assertIn("Retrieved Scripture Context", val)

    @patch("core.llm.GeminiClient.generate_stream")
    @patch("core.llm.get_gemini_api_key")
    def test_shell_ask_streaming(self, mock_key, mock_stream):
        from core.llm import StreamChunk
        mock_key.return_value = "AIzaSyFakeKeyTest12345"
        mock_stream.return_value = iter([
            StreamChunk(text="In the beginning, ", finish_reason=None),
            StreamChunk(text="God created.", finish_reason="STOP"),
        ])
        out = io.StringIO()
        with BibleShell(db_path=self.db_path, database=self.db, stdout=out) as sh:
            sh.do_ask("God")
        val = out.getvalue()
        self.assertIn("In the beginning, God created.", val)

    def test_shell_characters_list(self):
        out = io.StringIO()
        with BibleShell(db_path=self.db_path, database=self.db, stdout=out) as sh:
            sh.do_characters("")
        val = out.getvalue()
        self.assertIn("Canonical Biblical Character Studio", val)
        self.assertIn("paul", val)
        self.assertIn("moses", val)
        self.assertIn("david", val)

    def test_shell_chat_unknown_persona(self):
        out = io.StringIO()
        with BibleShell(db_path=self.db_path, database=self.db, stdout=out) as sh:
            sh.do_chat("unknown_hero")
        val = out.getvalue()
        self.assertIn("Unknown biblical character persona 'unknown_hero'", val)

    def test_shell_chat_profile_and_passages(self):
        out = io.StringIO()
        with BibleShell(db_path=self.db_path, database=self.db, stdout=out) as sh:
            sh.do_persona("paul --profile")
        val = out.getvalue()
        self.assertIn("Biblical Character Profile: Paul", val)
        self.assertIn("Theological Role:", val)
        self.assertIn("Speaking Style:", val)

        out_pass = io.StringIO()
        with BibleShell(db_path=self.db_path, database=self.db, stdout=out_pass) as sh:
            sh.do_chat("paul --passages")
        val_pass = out_pass.getvalue()
        self.assertIn("Grounded Scripture Passages: Paul", val_pass)

    @patch("core.llm.get_gemini_api_key")
    def test_shell_chat_offline_fallback(self, mock_key):
        mock_key.return_value = ""
        out = io.StringIO()
        with BibleShell(db_path=self.db_path, database=self.db, stdout=out) as sh:
            sh.do_chat("paul Why do you boast in weakness?")
        val = out.getvalue()
        self.assertIn("GEMINI_API_KEY is not configured", val)
        self.assertIn("Canonical Persona Offline Card: Paul", val)

    def test_shell_chat_set_active_and_exit(self):
        out = io.StringIO()
        with BibleShell(db_path=self.db_path, database=self.db, stdout=out) as sh:
            sh.do_chat("paul")
            self.assertEqual(sh._active_persona_id, "paul")
            self.assertIn("paul", sh.prompt)
            sh.do_chat("reset")
            val = out.getvalue()
            self.assertIn("Active character set to: Paul", val)
            self.assertIn("Reset dialogue history", val)
            sh.do_chat("exit")
            self.assertIsNone(sh._active_persona_id)
            self.assertNotIn(":paul", sh.prompt)

    def test_shell_complete_chat(self):
        with BibleShell(db_path=self.db_path, database=self.db, stdout=io.StringIO()) as sh:
            completions = sh.complete_chat("pau", "pau", 0, 3)
            self.assertIn("paul", completions)
            flags = sh.complete_chat("--pro", "--pro", 0, 5)
            self.assertIn("--profile", flags)
            resets = sh.complete_chat("res", "res", 0, 3)
            self.assertIn("reset", resets)

    @patch("core.llm.get_gemini_api_key")
    def test_shell_chat_streaming(self, mock_key):
        mock_key.return_value = "AIzaSyFakeKeyTest12345"
        out = io.StringIO()
        with BibleShell(db_path=self.db_path, database=self.db, stdout=out) as sh:
            session = sh._get_persona_session("paul")
            with patch.object(session, "say_stream", return_value=iter(["I boast ", "in Christ alone."])):
                sh.do_chat("paul What is your boast?")
        val = out.getvalue()
        self.assertIn("Paul (Apostle): I boast in Christ alone.", val)

    @patch("tools.ci.get_runs")
    def test_shell_ci(self, mock_get_runs):
        mock_get_runs.return_value = {
            "workflow_runs": [
                {
                    "id": 888,
                    "head_sha": "fff9999",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": "https://github.com/mrmarkwell/bible/actions/runs/888",
                    "head_commit": {"message": "ci test"},
                }
            ]
        }
        out = io.StringIO()
        with BibleShell(db_path=self.db_path, database=self.db) as sh:
            with patch("sys.stdout", out):
                sh.do_ci("--limit 1")
        val = out.getvalue()
        self.assertIn("GitHub Actions CI Status", val)
        self.assertIn("Run #888", val)

    @patch("tools.ci.get_runs")
    def test_shell_ci_aliases(self, mock_get_runs):
        mock_get_runs.return_value = {"workflow_runs": []}
        out = io.StringIO()
        with BibleShell(db_path=self.db_path, database=self.db) as sh:
            with patch("sys.stdout", out):
                sh.do_actions("")
                sh.do_workflow("")
        val = out.getvalue()
        self.assertIn("No workflow runs found", val)

    def test_shell_ci_completion(self):
        with BibleShell(db_path=self.db_path, database=self.db) as sh:
            comp = sh.complete_ci("--det", "--det", 0, 5)
            self.assertIn("--details", comp)
            comp_w = sh.complete_ci("--wat", "--wat", 0, 5)
            self.assertIn("--watch", comp_w)

    def test_shell_keys(self):
        with BibleShell(db_path=self.db_path, database=self.db, stdout=io.StringIO()) as sh:
            with patch("tools.onboarding.main") as mock_main:
                sh.do_keys("status --json")
                mock_main.assert_called_once_with(["status", "--json"])

            with patch("tools.onboarding.main") as mock_main:
                sh.do_key("probe")
                mock_main.assert_called_once_with(["probe"])

            completions = sh.complete_keys("sta", "sta", 0, 3)
            self.assertIn("status", completions)

    def test_shell_map_and_vector_project(self):
        out = io.StringIO()
        with BibleShell(db_path=self.db_path, database=self.db, stdout=out) as sh:
            sh.do_map("--status")
            val = out.getvalue()
            self.assertIn("Pericope 2D Coordinate Coverage", val)

            # Test autocompletion
            comp_map = sh.complete_map("O", "O", 0, 1)
            self.assertIn("OT", comp_map)
            comp_vec = sh.complete_vector("pro", "pro", 0, 3)
            self.assertIn("project", comp_vec)

            # Test /scatter and /scatter_map aliases
            sh.do_scatter("--status")
            sh.do_scatter_map("--status")

    def test_shell_summary_options_and_completion(self):
        out = io.StringIO()
        with BibleShell(db_path=self.db_path, database=self.db, stdout=out) as sh:
            sh.do_summary("5")
            val = out.getvalue()
            self.assertIn("Executive Summary", val)

            # Test JSON output
            out_json = io.StringIO()
            sh.stdout = out_json
            sh.do_summary("--window 3 --json")
            json_val = out_json.getvalue().strip()
            data = json.loads(json_val)
            self.assertIn("roadmap", data)
            self.assertIn("velocity", data)

            # Test autocompletion
            comp_sum = sh.complete_summary("--w", "--w", 0, 3)
            self.assertIn("--window", comp_sum)
            comp_doc = sh.complete_summary("--d", "--d", 0, 3)
            self.assertIn("--doctor", comp_doc)

    def test_shell_similar_and_recommend_commands(self):
        """Verify /similar and /recommend commands in interactive BibleShell."""
        shell, stdout = self._create_shell()
        shell.onecmd("/similar")
        self.assertIn("Usage: /similar <reference>", stdout.getvalue())

        stdout.seek(0)
        stdout.truncate(0)
        shell.onecmd("/similar John 3:16")
        self.assertTrue(len(stdout.getvalue()) > 0)


class TestCliCitationPreprocessing(unittest.TestCase):
    """Hermetic tests for direct citation CLI preprocessing."""

    def test_preprocess_direct_citation_simple(self):
        res = preprocess_cli_argv(["John 3:16"])
        self.assertEqual(res, ["get", "John 3:16"])

    def test_preprocess_direct_citation_with_flags(self):
        res = preprocess_cli_argv(["Romans 8:28-30", "--flow", "--margin=4"])
        self.assertEqual(res, ["get", "Romans 8:28-30", "--flow", "--margin=4"])

    def test_preprocess_with_db_flag_first(self):
        res = preprocess_cli_argv(["--db", "data/bible.db", "Psalm 23", "--box"])
        self.assertEqual(res, ["--db", "data/bible.db", "get", "Psalm 23", "--box"])

    def test_preprocess_preserves_subcommands(self):
        self.assertEqual(preprocess_cli_argv(["get", "John 3:16"]), ["get", "John 3:16"])
        self.assertEqual(preprocess_cli_argv(["search", "light"]), ["search", "light"])
        self.assertEqual(preprocess_cli_argv(["compare", "John 1:1"]), ["compare", "John 1:1"])
        self.assertEqual(preprocess_cli_argv(["doctor"]), ["doctor"])
        self.assertEqual(preprocess_cli_argv(["summary"]), ["summary"])
        self.assertEqual(preprocess_cli_argv(["shell"]), ["shell"])
        self.assertEqual(preprocess_cli_argv(["init"]), ["init"])
        self.assertEqual(preprocess_cli_argv(["db", "stats"]), ["db", "stats"])
        self.assertEqual(preprocess_cli_argv(["lint"]), ["lint"])
        self.assertEqual(preprocess_cli_argv(["esv", "status"]), ["esv", "status"])
        self.assertEqual(preprocess_cli_argv(["gemini", "status"]), ["gemini", "status"])
        self.assertEqual(preprocess_cli_argv(["vector", "status"]), ["vector", "status"])
        self.assertEqual(preprocess_cli_argv(["map"]), ["map"])
        self.assertEqual(preprocess_cli_argv(["scatter"]), ["scatter"])
        self.assertEqual(preprocess_cli_argv(["scatter-map"]), ["scatter-map"])
        self.assertEqual(preprocess_cli_argv(["issues"]), ["issues"])
        self.assertEqual(preprocess_cli_argv(["bug"]), ["bug"])
        self.assertEqual(preprocess_cli_argv(["ask", "temple"]), ["ask", "temple"])
        self.assertEqual(preprocess_cli_argv(["rag", "temple"]), ["rag", "temple"])
        self.assertEqual(preprocess_cli_argv(["ci"]), ["ci"])
        self.assertEqual(preprocess_cli_argv(["workflow"]), ["workflow"])
        self.assertEqual(preprocess_cli_argv(["actions"]), ["actions"])
        self.assertEqual(preprocess_cli_argv(["keys"]), ["keys"])
        self.assertEqual(preprocess_cli_argv(["key"]), ["key"])
        self.assertEqual(preprocess_cli_argv(["onboarding"]), ["onboarding"])
        self.assertEqual(preprocess_cli_argv(["similar", "Genesis 1:1"]), ["similar", "Genesis 1:1"])
        self.assertEqual(preprocess_cli_argv(["recommend", "Genesis 1:1"]), ["recommend", "Genesis 1:1"])
        self.assertEqual(preprocess_cli_argv(["build-vectors", "--status"]), ["build-vectors", "--status"])
        self.assertEqual(preprocess_cli_argv(["compile-vectors", "--status"]), ["compile-vectors", "--status"])

    def test_preprocess_preserves_empty_and_unknown(self):
        self.assertEqual(preprocess_cli_argv([]), [])
        self.assertEqual(preprocess_cli_argv(["nonexistent_subcommand"]), ["nonexistent_subcommand"])

    def test_shell_build_vectors_commands(self):
        """Verify /build-vectors and /compile-vectors commands and tab-completion."""
        out = io.StringIO()
        shell = BibleShell(stdout=out)
        with patch("sys.stdout", out):
            shell.do_build_vectors("status")
        val = out.getvalue()
        self.assertIn("Vector Compilation Ledger Status", val)

        # Autocompletion
        completions = shell.complete_build_vectors("st", "/build-vectors st", 15, 17)
        self.assertIn("status", completions)
        comp_alias = shell.complete_compile_vectors("dr", "/compile-vectors dr", 17, 19)
        self.assertIn("dry-run", comp_alias)


if __name__ == "__main__":
    unittest.main()
