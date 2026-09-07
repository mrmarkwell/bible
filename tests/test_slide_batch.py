"""Hermetic unit tests for batch slide exporter and album generation engine."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from core.db import Database
from core.plans import get_plan
from core.render import PaginationConfig, RenderConfig, export_slide_batch
from core.slide_batch import (
    BatchExportConfig,
    BatchExportResult,
    BatchSlideItem,
    SlideBatchExporter,
    generate_html_gallery,
)


class TestSlideBatchExporter(unittest.TestCase):
    """Test suite for SlideBatchExporter and album packaging."""

    @classmethod
    def setUpClass(cls) -> None:
        """Initialize shared database instance for test reads."""
        cls.db = Database()

    def setUp(self) -> None:
        """Set up per-test exporter instance and temporary directory."""
        self.exporter = SlideBatchExporter(self.db)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dest_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def test_resolve_passages_explicit_references(self) -> None:
        """Verify resolving passages from an explicit list of reference strings."""
        refs = ["John 3:16", "Romans 8:28"]
        items = self.exporter.resolve_passages(references=refs)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].citation, "John 3:16")
        self.assertIn("God so loved the world", items[0].text)
        self.assertEqual(items[1].citation, "Romans 8:28")
        self.assertIn("all things work together for good", items[1].text)

    def test_resolve_passages_from_plan(self) -> None:
        """Verify resolving passages from a curated reading plan."""
        items = self.exporter.resolve_passages(plan="romans_road")
        plan = get_plan("romans_road")
        self.assertIsNotNone(plan)
        self.assertEqual(len(items), plan.passage_count)
        self.assertEqual(items[0].citation, "Romans 3:23")

    def test_resolve_passages_from_favorites_and_starred(self) -> None:
        """Verify resolving favorites and starred-only filtering."""
        all_favs = self.exporter.resolve_passages(favorites=True, limit=10)
        self.assertGreaterEqual(len(all_favs), 1)

        starred_favs = self.exporter.resolve_passages(
            favorites=True, starred_only=True, limit=10
        )
        self.assertGreaterEqual(len(starred_favs), 1)
        for item in starred_favs:
            self.assertTrue(item.starred)

    def test_resolve_passages_from_tag(self) -> None:
        """Verify resolving passages by semantic tag name."""
        items = self.exporter.resolve_passages(tag="favorites", limit=5)
        self.assertGreaterEqual(len(items), 1)
        self.assertEqual(len(items), 5)

    def test_resolve_passages_from_book(self) -> None:
        """Verify resolving all pericopes/chapters for a canonical book."""
        items = self.exporter.resolve_passages(book="Jude")
        self.assertGreaterEqual(len(items), 1)
        self.assertEqual(items[0].reference.book.name, "Jude")

    def test_resolve_passages_from_file(self) -> None:
        """Verify resolving passages from a text file with reference citations."""
        file_path = self.dest_dir / "refs.txt"
        file_path.write_text(
            "# Scripture list\nJohn 1:1\nGenesis 1:1\nPsalm 23:1\n",
            encoding="utf-8",
        )
        items = self.exporter.resolve_passages(file_path=file_path)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].citation, "John 1:1")
        self.assertEqual(items[1].citation, "Genesis 1:1")
        self.assertEqual(items[2].citation, "Psalms 23:1")

    def test_resolve_limit_offset_and_deterministic_shuffle(self) -> None:
        """Verify limit, offset, and seeded shuffling."""
        refs = [f"Psalm {i}" for i in range(120, 135)]  # 15 Psalms of Ascent
        items_all = self.exporter.resolve_passages(references=refs)
        self.assertEqual(len(items_all), 15)

        items_sliced = self.exporter.resolve_passages(
            references=refs, offset=5, limit=3
        )
        self.assertEqual(len(items_sliced), 3)
        self.assertEqual(items_sliced[0].citation, "Psalms 125")

        shuffled1 = self.exporter.resolve_passages(
            references=refs, shuffle=True, seed=42
        )
        shuffled2 = self.exporter.resolve_passages(
            references=refs, shuffle=True, seed=42
        )
        self.assertEqual(
            [it.citation for it in shuffled1],
            [it.citation for it in shuffled2],
        )
        # Verify it actually shuffled away from identity
        self.assertNotEqual(
            [it.citation for it in shuffled1],
            [it.citation for it in items_all],
        )

    def test_batch_export_svg_sequential(self) -> None:
        """Verify sequential batch export generating SVGs, manifest, and gallery."""
        cfg = BatchExportConfig(
            destination_dir=self.dest_dir / "album_svg",
            render_config=RenderConfig(
                width=1920,
                height=1080,
                theme="oled_black",
                output_format="svg",
                backend="svg",
            ),
            album_title="Test SVG Album",
            sequential=True,
            quiet=True,
        )
        passages = self.exporter.resolve_passages(
            references=["John 3:16", "Romans 8:28"]
        )
        res = self.exporter.export_batch(cfg, passages=passages)

        self.assertIsInstance(res, BatchExportResult)
        self.assertEqual(res.total_passages, 2)
        self.assertEqual(res.total_slides, 2)
        self.assertGreater(res.total_bytes, 0)
        self.assertIsNotNone(res.manifest_path)
        self.assertIsNotNone(res.gallery_path)
        self.assertIsNotNone(res.index_txt_path)

        self.assertTrue(res.manifest_path.exists())
        self.assertTrue(res.gallery_path.exists())
        self.assertTrue(res.index_txt_path.exists())

        # Verify slide filenames on disk
        files = sorted([f.name for f in res.destination_dir.glob("*.svg")])
        self.assertEqual(len(files), 2)
        self.assertTrue(files[0].startswith("001_"))
        self.assertTrue(files[1].startswith("002_"))

        # Verify manifest JSON contents
        with open(res.manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        self.assertEqual(manifest_data["album_title"], "Test SVG Album")
        self.assertEqual(manifest_data["total_slides"], 2)
        self.assertEqual(len(manifest_data["slides"]), 2)
        self.assertEqual(manifest_data["slides"][0]["citation"], "John 3:16")

        # Verify index.txt contents
        txt_content = res.index_txt_path.read_text(encoding="utf-8")
        self.assertIn("John 3:16", txt_content)
        self.assertIn("Romans 8:28", txt_content)

    def test_batch_export_multiprocessing(self) -> None:
        """Verify parallel rendering with ProcessPoolExecutor."""
        cfg = BatchExportConfig(
            destination_dir=self.dest_dir / "album_parallel",
            render_config=RenderConfig(
                width=1920,
                height=1080,
                theme="charcoal",
                output_format="svg",
                backend="svg",
            ),
            album_title="Parallel Album",
            max_workers=2,
            sequential=False,
            quiet=True,
        )
        passages = self.exporter.resolve_passages(
            references=["Psalm 23:1", "Psalm 23:2", "Psalm 23:3"]
        )
        res = self.exporter.export_batch(cfg, passages=passages)
        self.assertEqual(res.total_slides, 3)
        files = list(res.destination_dir.glob("*.svg"))
        self.assertEqual(len(files), 3)

    def test_batch_export_with_pagination(self) -> None:
        """Verify multi-slide pagination handling within a batch export."""
        cfg = BatchExportConfig(
            destination_dir=self.dest_dir / "album_paginated",
            render_config=RenderConfig(
                width=1920,
                height=1080,
                theme="obsidian",
                output_format="svg",
                backend="svg",
            ),
            pagination_config=PaginationConfig(
                enabled=True,
                mode="always",
                max_verses_per_slide=2,
            ),
            album_title="Paginated Album",
            sequential=True,
            quiet=True,
        )
        # Psalm 23:1-6 has 6 verses, with max 2 per slide it must paginate into 3 slides
        passages = self.exporter.resolve_passages(references=["Psalm 23:1-6"])
        res = self.exporter.export_batch(cfg, passages=passages)

        self.assertEqual(res.total_passages, 1)
        self.assertEqual(res.total_slides, 3)

        files = sorted([f.name for f in res.destination_dir.glob("*.svg")])
        self.assertEqual(len(files), 3)
        self.assertIn("_p1.svg", files[0])
        self.assertIn("_p2.svg", files[1])
        self.assertIn("_p3.svg", files[2])

    def test_generate_html_gallery_structure(self) -> None:
        """Verify Sacred-Modern HTML gallery contains all requisite UI components."""
        items = [
            BatchSlideItem(
                index=1,
                passage_index=1,
                reference_str="John 3:16",
                citation="John 3:16",
                text_excerpt="For God so loved the world...",
                page_num=1,
                total_pages=1,
                filename="001_john_3_16.svg",
                file_path=Path("001_john_3_16.svg"),
                file_size_bytes=1024,
                width=3840,
                height=2160,
                format="svg",
                backend="svg",
                theme_name="oled_black",
                pericope_title="The Love of God",
                tags=["Gospel", "Love"],
                starred=True,
            )
        ]
        html_text = generate_html_gallery(
            title="Screensaver Gallery",
            description="Sacred gallery description",
            slides=items,
            render_cfg=RenderConfig(),
            theme_name="oled_black",
        )
        self.assertIn("Screensaver Gallery", html_text)
        self.assertIn("001_john_3_16.svg", html_text)
        self.assertIn("John 3:16", html_text)
        self.assertIn("The Love of God", html_text)
        self.assertIn("Gospel", html_text)
        self.assertIn("★ Starred", html_text)
        self.assertIn("Google TV &amp; Chromecast", html_text)
        self.assertIn("openLightbox", html_text)
        self.assertIn("lightbox", html_text)

    def test_export_slide_batch_convenience_function(self) -> None:
        """Verify export_slide_batch convenience functional interface in core/render.py."""
        target_dir = self.dest_dir / "convenience_album"
        res = export_slide_batch(
            destination_dir=target_dir,
            references=["Romans 8:31", "Romans 8:38-39"],
            album_title="Romans Highlights",
            theme="monastery",
            resolution="1080p",
            output_format="svg",
            backend="svg",
            sequential=True,
            quiet=True,
        )
        self.assertEqual(res.total_slides, 2)
        self.assertTrue((target_dir / "manifest.json").exists())
        self.assertTrue((target_dir / "index.html").exists())


if __name__ == "__main__":
    unittest.main()
