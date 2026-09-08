"""Hermetic unit tests for core/bootstrap.py lifecycle and compilation engine.

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

from pathlib import Path
import tempfile
import unittest

from core.bootstrap import (
    bootstrap_database,
    format_size,
    get_db_stats,
    is_database_healthy,
)
from core.db import DEFAULT_DB_PATH, Database
from core.reference import BOOKS


class TestBootstrapModule(unittest.TestCase):
    """Hermetic unit tests for database bootstrap and inspection functions."""

    def test_format_size(self):
        """Verify human-readable byte formatting across scales."""
        self.assertEqual(format_size(500), "500 B")
        self.assertEqual(format_size(1500), "1.5 KB")
        self.assertEqual(format_size(26_400_000), "25.2 MB")

    def test_get_db_stats_nonexistent(self):
        """Verify stats behavior on non-existent database file."""
        nonexistent = Path("/tmp/definitely_does_not_exist_bible_12345.db")
        stats = get_db_stats(nonexistent)
        self.assertFalse(stats["exists"])
        self.assertEqual(stats["total_verses"], 0)
        self.assertEqual(stats["size_bytes"], 0)
        self.assertEqual(stats["fts5_status"], "inactive")

    def test_get_db_stats_existing_bundled(self):
        """Verify stats retrieval on bundled canonical scripture database."""
        stats = get_db_stats(DEFAULT_DB_PATH)
        self.assertTrue(stats["exists"])
        self.assertGreaterEqual(stats["total_verses"], 31100)
        self.assertEqual(stats["fts5_status"], "active")
        self.assertEqual(stats["integrity_check"], "ok")
        self.assertGreaterEqual(stats["total_tags"], 20)
        self.assertGreaterEqual(stats["total_cross_references"], 40)
        self.assertTrue(any(tr["id"] == "WEB" for tr in stats["translations"]))

    def test_is_database_healthy(self):
        """Verify health determination logic."""
        self.assertTrue(is_database_healthy(DEFAULT_DB_PATH))
        self.assertFalse(is_database_healthy(Path("/tmp/nonexistent_123.db")))

        with tempfile.TemporaryDirectory() as tmpdir:
            empty_db = Path(tmpdir) / "empty.db"
            empty_db.touch()
            self.assertFalse(is_database_healthy(empty_db))

    def test_bootstrap_idempotent_existing(self):
        """Verify fast idempotent no-op execution on existing healthy database."""
        rep = bootstrap_database(db_path=DEFAULT_DB_PATH, force=False, install_git_hooks=False)
        self.assertTrue(rep.is_clean)
        self.assertIn("idempotent", rep.details)
        self.assertGreaterEqual(rep.verses_count, 31100)
        self.assertLess(rep.duration_sec, 2.0)

    def test_bootstrap_quick_into_temp(self):
        """Verify complete compilation into an isolated temporary database in quick mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "test_quick.db"
            notified_steps = []

            def callback(step: str, pct: float) -> None:
                notified_steps.append((step, pct))

            rep = bootstrap_database(
                db_path=tmp_db,
                books=[BOOKS[57], BOOKS[63], BOOKS[64]],  # Philemon, 2 John, 3 John (52 verses)
                install_git_hooks=False,
                verbose=False,
                progress_callback=callback,
            )

            self.assertTrue(rep.is_clean)
            self.assertTrue(tmp_db.exists())
            self.assertEqual(rep.verses_count, 52)
            self.assertEqual(rep.translations_count, 1)
            self.assertGreaterEqual(rep.tags_count, 20)
            self.assertGreaterEqual(rep.cross_references_count, 40)
            self.assertTrue(len(notified_steps) >= 5)

            # Verify summary lines format
            lines = rep.summary_lines()
            self.assertTrue(any("Verses Ingested" in l for l in lines))
            self.assertTrue(any("Canonical Tags" in l for l in lines))

            # Verify Database query against compiled temp file
            with Database(tmp_db) as db:
                verse = db.get_verse("2 John", 1, 1, translation_id="WEB")
                self.assertIsNotNone(verse)
                self.assertIn("elder", verse.text.lower())

    def test_bootstrap_force_rebuild(self):
        """Verify --force flag recompiles database from scratch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "test_force.db"
            # First pass: 2 John (13 verses)
            rep1 = bootstrap_database(
                db_path=tmp_db,
                books=[BOOKS[63]],
                install_git_hooks=False,
            )
            self.assertEqual(rep1.verses_count, 13)

            # Second pass: 2 John and 3 John with force=True (27 verses)
            rep2 = bootstrap_database(
                db_path=tmp_db,
                books=[BOOKS[63], BOOKS[64]],
                force=True,
                install_git_hooks=False,
            )
            self.assertEqual(rep2.verses_count, 27)

    def test_bootstrap_with_onboarding_keys(self):
        """Verify bootstrap_database passes explicit API keys and onboarding wizard flag."""
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "test_onboard.db"
            with patch("tools.onboarding.run_onboarding_wizard") as mock_wizard:
                rep = bootstrap_database(
                    db_path=tmp_db,
                    books=[BOOKS[63]],
                    install_git_hooks=False,
                    onboarding_wizard=True,
                    esv_key="test_esv_boot",
                    gemini_key="test_gem_boot",
                    probe_keys=False,
                )
                self.assertEqual(rep.verses_count, 13)
                mock_wizard.assert_called_once()
                kwargs = mock_wizard.call_args[1]
                self.assertTrue(kwargs["interactive"])
                self.assertEqual(kwargs["esv_key"], "test_esv_boot")
                self.assertEqual(kwargs["gemini_key"], "test_gem_boot")
                self.assertFalse(kwargs["probe"])


if __name__ == "__main__":
    unittest.main()
