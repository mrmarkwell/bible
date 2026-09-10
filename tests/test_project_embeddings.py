#!/usr/bin/env python3
"""Hermetic Unit Tests for Batch Embedding Projection CLI Tool.

Zero external dependencies (ADR-003):
- Tests tools.project_embeddings CLI actions, status checks, coordinate persistence,
  and SVG/JSON exports against temporary hermetic SQLite databases.
"""

import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from core.db import Database
from tools.project_embeddings import main, run_projection


class TestProjectEmbeddingsTool(unittest.TestCase):
    """Test suite for tools.project_embeddings CLI operations."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_bible.db"
        self.db = Database(self.db_path)

        # Seed sample pericopes
        p1 = self.db.insert_pericope(
            reference="Genesis 1:1-2:3",
            title="The Creation of the World",
            genre="Creation Narrative",
            redemptive_summary="God speaks cosmos into being, resting on 7th day.",
        )
        p2 = self.db.insert_pericope(
            reference="Romans 8:28-39",
            title="Everlasting Love and Election",
            genre="Epistle",
            redemptive_summary="Nothing can separate believers from God's love in Christ.",
        )
        p3 = self.db.insert_pericope(
            reference="Revelation 21:1-22:5",
            title="New Heavens and New Earth",
            genre="Apocalyptic",
            redemptive_summary="Consummation of all redemptive history in the New Jerusalem.",
        )

        # Save synthetic int8 embeddings (dim=8)
        dim = 8
        emb1 = struct.pack(f"{dim}b", 100, 50, -30, 20, 10, -40, 60, 80)
        emb2 = struct.pack(f"{dim}b", -80, 120, -50, 10, 30, 40, -20, -10)
        emb3 = struct.pack(f"{dim}b", 20, -100, 80, -60, 40, -10, 30, 50)

        self.db.save_pericope_embedding(p1.id, "Genesis 1:1-2:3", "test-model", dim, emb1)
        self.db.save_pericope_embedding(p2.id, "Romans 8:28-39", "test-model", dim, emb2)
        self.db.save_pericope_embedding(p3.id, "Revelation 21:1-22:5", "test-model", dim, emb3)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_status_check(self) -> None:
        """Verify --status inspects total vs projected coordinate counts."""
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            ret = run_projection(self.db_path, status_only=True, json_output=True)
        self.assertEqual(ret, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["total_pericope_embeddings"], 3)
        self.assertEqual(data["projected_2d_count"], 0)
        self.assertEqual(data["coverage_percent"], 0.0)

    def test_run_projection_and_persistence(self) -> None:
        """Verify run_projection computes and writes map_x, map_y to database."""
        ret = run_projection(self.db_path, method="fastmap", save=True, force=True)
        self.assertEqual(ret, 0)

        # Verify database coordinates updated
        points = self.db.get_pericope_map_points()
        self.assertEqual(len(points), 3)
        for pt in points:
            self.assertIsNotNone(pt["x"])
            self.assertIsNotNone(pt["y"])
            self.assertIn("human_ref", pt)
            self.assertIn("genre", pt)

    def test_export_svg_and_json(self) -> None:
        """Verify exporting standalone SVG and JSON files."""
        svg_out = Path(self.temp_dir.name) / "map.svg"
        json_out = Path(self.temp_dir.name) / "map.json"

        ret = run_projection(
            self.db_path,
            method="pca",
            save=True,
            force=True,
            export_svg=svg_out,
            export_json=json_out,
        )
        self.assertEqual(ret, 0)
        self.assertTrue(svg_out.exists())
        self.assertTrue(json_out.exists())

        svg_content = svg_out.read_text(encoding="utf-8")
        self.assertTrue(svg_content.startswith("<svg"))
        self.assertIn("Genesis 1:1-2:3", svg_content)

        json_content = json.loads(json_out.read_text(encoding="utf-8"))
        self.assertEqual(json_content["count"], 3)
        self.assertEqual(len(json_content["points"]), 3)

    def test_missing_database_error(self) -> None:
        """Verify non-existent database file returns error code 1."""
        missing = Path(self.temp_dir.name) / "missing.db"
        ret = run_projection(missing)
        self.assertEqual(ret, 1)

    def test_main_cli_dispatch(self) -> None:
        """Verify main() parses sys.argv and executes correctly."""
        test_args = ["tools/project_embeddings.py", "--db", str(self.db_path), "--status", "--json"]
        buf = io.StringIO()
        with patch("sys.argv", test_args), patch("sys.stdout", buf):
            ret = main()
        self.assertEqual(ret, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("total_pericope_embeddings", data)


if __name__ == "__main__":
    unittest.main()
