"""Hermetic unit tests for core/bootstrap.py lifecycle and compilation engine.

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

from pathlib import Path
import tempfile
import unittest

from core.bootstrap import (
    REPO_ROOT,
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
        self.assertFalse(stats["fts_synchronized"])
        self.assertIn("fts_health", stats)

    def test_get_db_stats_existing_bundled(self):
        """Verify stats retrieval on bundled canonical scripture database."""
        stats = get_db_stats(DEFAULT_DB_PATH)
        self.assertTrue(stats["exists"])
        self.assertGreaterEqual(stats["total_verses"], 31100)
        self.assertEqual(stats["fts5_status"], "active")
        self.assertTrue(stats["fts_synchronized"])
        self.assertEqual(stats["fts_bloat_ratio"], 1.0)
        self.assertEqual(stats["fts_health"]["orphaned_count"], 0)
        self.assertEqual(stats["integrity_check"], "ok")
        self.assertGreaterEqual(stats["total_tags"], 1)
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
        self.assertLess(rep.duration_sec, 5.0)

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
            # 52 verses in WEB + 52 verses in KJV = 104 total verses
            self.assertEqual(rep.verses_count, 104)
            self.assertEqual(rep.translations_count, 2)
            self.assertGreaterEqual(rep.tags_count, 0)
            self.assertGreaterEqual(rep.cross_references_count, 40)
            self.assertTrue(len(notified_steps) >= 5)

            # Verify summary lines format
            lines = rep.summary_lines()
            self.assertTrue(any("Verses Ingested" in l for l in lines))
            self.assertTrue(any("Canonical Tags" in l for l in lines))

            # Verify Database query against compiled temp file
            with Database(tmp_db) as db:
                verse_web = db.get_verse("2 John", 1, 1, translation_id="WEB")
                self.assertIsNotNone(verse_web)
                self.assertIn("elder", verse_web.text.lower())
                verse_kjv = db.get_verse("2 John", 1, 1, translation_id="KJV")
                self.assertIsNotNone(verse_kjv)
                self.assertIn("elder", verse_kjv.text.lower())

    def test_bootstrap_force_rebuild(self):
        """Verify --force flag recompiles database from scratch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "test_force.db"
            # First pass: 2 John (13 verses WEB + 13 verses KJV = 26 verses)
            rep1 = bootstrap_database(
                db_path=tmp_db,
                books=[BOOKS[63]],
                install_git_hooks=False,
            )
            self.assertEqual(rep1.verses_count, 26)

            # Second pass: 2 John and 3 John with force=True (27 verses WEB + 27 verses KJV = 54 verses)
            rep2 = bootstrap_database(
                db_path=tmp_db,
                books=[BOOKS[63], BOOKS[64]],
                force=True,
                install_git_hooks=False,
            )
            self.assertEqual(rep2.verses_count, 54)

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
                self.assertEqual(rep.verses_count, 26)
                mock_wizard.assert_called_once()
                kwargs = mock_wizard.call_args[1]
                self.assertTrue(kwargs["interactive"])
                self.assertEqual(kwargs["esv_key"], "test_esv_boot")
                self.assertEqual(kwargs["gemini_key"], "test_gem_boot")
                self.assertFalse(kwargs["probe"])


    def test_bootstrap_idempotent_backfills_missing_verse_embeddings(self):
        """Verify that idempotent bootstrap backfills verse embeddings if pericopes exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "test_backfill.db"
            with Database(tmp_db) as db:
                from core.db import VerseRecord
                db.add_translation("WEB", "World English Bible")
                p = db.insert_pericope("Romans 1:1-7", "Greeting", "Epistle", "Gospel of God")
                db.insert_verses([
                    VerseRecord("WEB", 45, 1, v, f"Romans 1:{v} text") for v in range(1, 8)
                ])
                import struct
                dim = 8
                emb = struct.pack(f"{dim}b", *([10] * dim))
                db.save_pericope_embedding(p.id, "Romans 1:1-7", "test-model", dim, emb)
                db.conn.execute("INSERT INTO tags (name) VALUES ('theology')")
                for i in range(45):
                    db.conn.execute(
                        "INSERT INTO cross_references (source_start_id, source_end_id, source_human_ref, target_start_id, target_end_id, target_human_ref) "
                        "VALUES (?, ?, 'Rom 1:1', ?, ?, 'Rom 1:2')",
                        (1001001, 1001001, 1001002 + i, 1001002 + i),
                    )
                db.conn.commit()

            from unittest.mock import patch
            with patch("core.bootstrap.is_database_healthy", return_value=True):
                rep = bootstrap_database(db_path=tmp_db, force=False, install_git_hooks=False)
                self.assertTrue(rep.is_clean)

            with Database(tmp_db) as db:
                cur = db.conn.cursor()
                cur.execute("SELECT count(*) FROM verse_embeddings")
                ve_count = cur.fetchone()[0]
                self.assertGreater(ve_count, 0)

    def test_bootstrap_report_summary_lines_includes_keys(self):
        """Verify BootstrapReport summary_lines includes Crossway ESV API and Google Gemini AI."""
        from core.bootstrap import BootstrapReport
        rep = BootstrapReport(
            db_path=Path("/tmp/fake.db"),
            duration_sec=0.1,
            verses_count=100,
            translations_count=1,
            favorites_count=10,
            starred_count=5,
            tags_count=20,
            cross_references_count=30,
            hooks_installed=True,
            pragmas_optimized=True,
            is_clean=True,
            details="Test report",
            esv_configured=True,
            gemini_configured=False,
        )
        lines = rep.summary_lines()
        self.assertTrue(any("Crossway ESV API:" in l and "Configured" in l for l in lines))
        self.assertTrue(any("Google Gemini AI:" in l and "Not Configured" in l for l in lines))

    def test_bootstrap_updates_system_when_new_content_pulled(self):
        """Regression test for Issue #6: running bootstrap on an existing DB updates newly pulled translations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "test_existing.db"
            tmp_kjv_dir = Path(tmpdir) / "kjv"
            tmp_kjv_dir.mkdir(parents=True, exist_ok=True)

            # Step 1: Initial state - DB initialized with only 2 John in WEB, no KJV
            rep1 = bootstrap_database(
                db_path=tmp_db,
                raw_kjv_dir=tmp_kjv_dir,  # Empty KJV dir initially
                books=[BOOKS[63]],        # 2 John (13 verses)
                force=False,
                install_git_hooks=False,
            )
            self.assertTrue(rep1.is_clean)
            self.assertEqual(rep1.verses_count, 13)
            self.assertEqual(rep1.translations_count, 1)

            with Database(tmp_db) as db:
                self.assertIsNotNone(db.get_verse("2 John", 1, 1, translation_id="WEB"))
                self.assertIsNone(db.get_verse("2 John", 1, 1, translation_id="KJV"))

            # Step 2: Simulate "git pull" pulling new KJV content by populating tmp_kjv_dir
            source_kjv_file = REPO_ROOT / "data" / "raw" / "kjv" / "2John.json"
            if source_kjv_file.exists():
                (tmp_kjv_dir / "2John.json").write_text(
                    source_kjv_file.read_text(encoding="utf-8"), encoding="utf-8"
                )
            else:
                import json
                (tmp_kjv_dir / "2John.json").write_text(
                    json.dumps({
                        "chapters": [{
                            "chapter": "1",
                            "verses": [{"verse": str(i), "text": f"KJV verse {i}"} for i in range(1, 14)]
                        }]
                    }),
                    encoding="utf-8",
                )

            # Step 3: Run ./bible init (bootstrap_database) WITHOUT --force
            rep2 = bootstrap_database(
                db_path=tmp_db,
                raw_kjv_dir=tmp_kjv_dir,
                books=[BOOKS[63]],
                force=False,
                install_git_hooks=False,
            )
            self.assertTrue(rep2.is_clean)
            # The database MUST now have both WEB and KJV (26 verses across 2 translations)
            self.assertEqual(rep2.translations_count, 2)
            self.assertEqual(rep2.verses_count, 26)

            with Database(tmp_db) as db:
                verse_web = db.get_verse("2 John", 1, 1, translation_id="WEB")
                verse_kjv = db.get_verse("2 John", 1, 1, translation_id="KJV")
                self.assertIsNotNone(verse_web)
                self.assertIsNotNone(verse_kjv)

    def test_bootstrap_updates_curated_favorites_on_existing_db(self):
        """Regression test for Issue #6: running bootstrap on existing DB synchronizes updated favorites."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "test_fav_update.db"
            tmp_csv = Path(tmpdir) / "favorites.csv"

            # Initial CSV with 1 entry
            tmp_csv.write_text(
                "book,chapter,start_verse,end_verse,starred\n"
                "Romans,8,28,28,1\n",
                encoding="utf-8",
            )

            rep1 = bootstrap_database(
                db_path=tmp_db,
                favorites_csv=tmp_csv,
                books=[BOOKS[63]],
                force=False,
                install_git_hooks=False,
            )
            self.assertEqual(rep1.favorites_count, 1)
            self.assertEqual(rep1.starred_count, 1)

            # Simulate pulling new favorites in CSV
            tmp_csv.write_text(
                "book,chapter,start_verse,end_verse,starred\n"
                "Romans,8,28,28,1\n"
                "Romans,8,38,39,1\n"
                "John,3,16,16,0\n",
                encoding="utf-8",
            )

            # Re-run bootstrap without force
            rep2 = bootstrap_database(
                db_path=tmp_db,
                favorites_csv=tmp_csv,
                books=[BOOKS[63]],
                force=False,
                install_git_hooks=False,
            )
            self.assertTrue(rep2.is_clean)
            self.assertEqual(rep2.favorites_count, 3)
            self.assertEqual(rep2.starred_count, 2)

    def test_cli_init_update_and_sync_flags(self):
        """Regression test for Issue #6: verify CLI init --update and --sync flags execute successfully."""
        from unittest.mock import patch
        from cli.main import main

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_db = Path(tmpdir) / "cli_init_test.db"
            with patch("core.bootstrap.bootstrap_database") as mock_boot:
                from core.bootstrap import BootstrapReport
                mock_rep = BootstrapReport(
                    db_path=fake_db,
                    duration_sec=0.2,
                    verses_count=62205,
                    translations_count=2,
                    favorites_count=829,
                    starred_count=50,
                    tags_count=318,
                    cross_references_count=343603,
                    hooks_installed=True,
                    pragmas_optimized=True,
                    is_clean=True,
                    details="Database updated and synchronized",
                )
                mock_boot.return_value = mock_rep

                # Test --update flag
                ret1 = main(["--db", str(fake_db), "init", "--update", "--quiet", "--no-wizard"])
                self.assertEqual(ret1, 0)
                mock_boot.assert_called()

                # Test --sync flag
                mock_boot.reset_mock()
                ret2 = main(["--db", str(fake_db), "init", "--sync", "--quiet", "--no-wizard"])
                self.assertEqual(ret2, 0)
                mock_boot.assert_called()


if __name__ == "__main__":
    unittest.main()
