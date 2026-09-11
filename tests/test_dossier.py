"""Hermetic unit tests for Sovereign Omnichannel Exegetical Study Dossier Engine.

Zero external dependencies (Python stdlib unittest only per ADR-003).
Covers:
- ExegeticalDossier dataclass and child record types
- ExegeticalDossierService dossier generation across scripture, pericopes, tags,
  theology, cross-references, typological arcs, vector similarity, and personas
- Multi-format exporters: to_dict(), to_json(), to_markdown(), to_html(), to_ansi(), to_text()
- CLI subcommands (bible dossier / study / research / packet) and --export flag
- Interactive REPL shell commands (/dossier, /study, /research, /read)
- REST API endpoint (/api/dossier, /api/study)
"""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from core.crossref import CrossReferenceService, RelationshipType
from core.db import (
    Database,
    VerseRecord,
)
from core.tags import TaggingService
from core.dossier import (
    DossierCrossRef,
    DossierPericope,
    DossierPersonaPerspective,
    DossierTag,
    DossierTheology,
    DossierTypologicalArc,
    DossierVectorNeighbor,
    ExegeticalDossier,
    ExegeticalDossierService,
)
from core.reference import parse_reference
from cli.main import main
from cli.shell import BibleShell


def create_test_db(db_path: str = ":memory:") -> Database:
    """Create and seed a test SQLite database with sample verses, pericopes, tags, and arcs."""
    db = Database(db_path)
    with db.conn:
        db.conn.execute(
            """
            INSERT OR REPLACE INTO translations (id, name, language, is_public_domain)
            VALUES ('BSB', 'Berean Standard Bible', 'en', 1),
                   ('KJV', 'King James Version', 'en', 1)
            """
        )

    # Romans 8:28-30
    verses = [
        VerseRecord(
            translation_id="BSB",
            book_id=45,  # Romans
            chapter=8,
            verse=28,
            text="And we know that God works all things together for the good of those who love Him, who are called according to His purpose.",
        ),
        VerseRecord(
            translation_id="BSB",
            book_id=45,
            chapter=8,
            verse=29,
            text="For those God foreknew, He also predestined to be conformed to the image of His Son, so that He might be the firstborn among many brothers.",
        ),
        VerseRecord(
            translation_id="BSB",
            book_id=45,
            chapter=8,
            verse=30,
            text="And those He predestined, He also called; those He called, He also justified; those He justified, He also glorified.",
        ),
        VerseRecord(
            translation_id="KJV",
            book_id=45,
            chapter=8,
            verse=28,
            text="And we know that all things work together for good to them that love God, to them who are the called according to his purpose.",
        ),
        # Ephesians 1:4-5 (for crossref and vector simulation)
        VerseRecord(
            translation_id="BSB",
            book_id=49,  # Ephesians
            chapter=1,
            verse=4,
            text="For He chose us in Him before the foundation of the world to be holy and blameless in His presence.",
        ),
        VerseRecord(
            translation_id="BSB",
            book_id=49,
            chapter=1,
            verse=5,
            text="He predestined us for adoption as His sons through Jesus Christ, according to the good pleasure of His will.",
        ),
    ]
    db.insert_verses(verses)

    # Pericope
    db.insert_pericope(
        reference="Romans 8:28-30",
        title="More Than Conquerors / The Golden Chain of Redemption",
        redemptive_summary="Paul articulates God's eternal sovereign purpose from foreknowledge to glorification.",
        genre="Epistle",
        literary_structure="Chiasm / Logical Chain",
        central_proposition="God works all things together for the good of those who love Him.",
    )

    # Tags via TaggingService
    tag_svc = TaggingService(db=db)
    tag_svc.add_tag("providence", "theological", "Universal providential care")
    tag_svc.add_tag("election", "theological", "Foreknown and predestined")
    tag_svc.add_tag("justification", "theological", "Golden chain of salvation")
    tag_svc.tag_passage("Romans 8:28", "providence", category="theological", confidence=1.0, starred=True)
    tag_svc.tag_passage("Romans 8:29", "election", category="theological", confidence=1.0, starred=True)
    tag_svc.tag_passage("Romans 8:30", "justification", category="theological", confidence=1.0, starred=False)

    # Theology
    db.insert_verse_theology(
        reference="Romans 8:28-30",
        storyline_epoch="Apostolic / Church Age",
        theological_locus="Soteriology / Providence",
        primary_doctrine="God's Sovereign Purpose for Believers",
        thematic_ribbon="Redemption / Security",
    )

    # Cross References
    xref_svc = CrossReferenceService(db=db)
    xref_svc.link_passages(
        source="Romans 8:29",
        target="Ephesians 1:4",
        relationship_type=RelationshipType.THEMATIC,
        weight=0.95,
        notes="Eternal election before the foundation of the world",
    )

    # Typological Arc
    db.insert_typological_arc(
        type_reference="Genesis 1:26",
        antitype_reference="Romans 8:29",
        theological_correspondence="Adam the firstborn of creation; Christ the firstborn among many brothers",
        warrant="EXPLICIT_APOSTOLIC",
        confidence=0.98,
    )

    return db


class TestExegeticalDossierService(unittest.TestCase):
    """Hermetic unit tests for ExegeticalDossierService."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_dossier.db"
        self.db = create_test_db(str(self.db_path))
        self.service = ExegeticalDossierService(db=self.db)

    def tearDown(self) -> None:
        self.db.close()
        self.temp_dir.cleanup()

    def test_generate_dossier_basic(self) -> None:
        """Verify dossier compilation retrieves all facets of Romans 8:28-30."""
        dossier = self.service.generate_dossier(
            reference="Romans 8:28-30",
            translations=["BSB", "KJV"],
            top_crossrefs=5,
            top_vectors=0,
            include_personas=True,
        )
        self.assertEqual(dossier.human_ref, "Romans 8:28-30")
        self.assertEqual(dossier.book_name, "Romans")
        self.assertEqual(dossier.testament, "NT")
        self.assertEqual(dossier.total_verses, 3)

        # Scripture texts
        self.assertIn("BSB", dossier.verses_by_translation)
        self.assertIn("KJV", dossier.verses_by_translation)
        self.assertEqual(len(dossier.verses_by_translation["BSB"]), 3)
        self.assertIn("works all things together", dossier.verses_by_translation["BSB"][0].text)

        # Pericopes
        self.assertTrue(len(dossier.pericopes) >= 1)
        self.assertIn("Golden Chain", dossier.pericopes[0].title)

        # Theology
        self.assertIsNotNone(dossier.theology)
        self.assertEqual(dossier.theology.primary_doctrine, "God's Sovereign Purpose for Believers")

        # Tags
        self.assertTrue(len(dossier.tags) >= 2)
        tag_names = [t.name for t in dossier.tags]
        self.assertIn("providence", tag_names)
        self.assertIn("election", tag_names)

        # Cross References
        self.assertTrue(len(dossier.cross_references) >= 1)
        self.assertIn("Ephesians", dossier.cross_references[0].target_ref)

        # Typological Arcs
        self.assertTrue(len(dossier.typological_arcs) >= 1)
        self.assertIn("Genesis 1:26", dossier.typological_arcs[0].type_ref)

        # Persona Perspectives
        self.assertTrue(len(dossier.persona_perspectives) >= 1)
        persona_names = [p.name for p in dossier.persona_perspectives]
        self.assertTrue(any("Paul" in name for name in persona_names))

    def test_generate_dossier_specific_persona(self) -> None:
        """Verify dossier filters to a specifically requested persona."""
        dossier = self.service.generate_dossier(
            reference="Romans 8:28-30",
            persona_id="paul",
            top_vectors=0,
            include_personas=True,
        )
        self.assertEqual(len(dossier.persona_perspectives), 1)
        self.assertIn("Paul", dossier.persona_perspectives[0].name)
        self.assertTrue(dossier.persona_perspectives[0].is_author)

    def test_generate_dossier_invalid_reference(self) -> None:
        """Verify that invalid references raise ValueError."""
        with self.assertRaises(ValueError):
            self.service.generate_dossier("InvalidBook 99:99")

    def test_generate_dossier_without_personas_or_vectors(self) -> None:
        """Verify flags for skipping vectors and personas work."""
        dossier = self.service.generate_dossier(
            reference="Romans 8:28",
            top_vectors=0,
            include_personas=False,
        )
        self.assertEqual(len(dossier.vector_neighbors), 0)
        self.assertEqual(len(dossier.persona_perspectives), 0)


class TestExegeticalDossierExporters(unittest.TestCase):
    """Hermetic unit tests for ExegeticalDossier export formats."""

    def setUp(self) -> None:
        ref_obj = parse_reference("Romans 8:28-30")
        self.dossier = ExegeticalDossier(
            reference=ref_obj,
            human_ref="Romans 8:28-30",
            book_name="Romans",
            testament="NT",
            canon_order=45,
            verses_by_translation={
                "BSB": [
                    VerseRecord(
                        translation_id="BSB",
                        book_id=45,
                        chapter=8,
                        verse=28,
                        text="And we know that God works all things together for good.",
                    )
                ]
            },
            pericopes=[
                DossierPericope(
                    id=1,
                    title="The Golden Chain of Redemption",
                    human_ref="Romans 8:28-30",
                    genre="Epistle",
                    literary_structure="Chiasm / Logical Chain",
                    central_proposition="God's eternal purpose",
                    redemptive_summary="Paul articulates God's eternal sovereign purpose.",
                )
            ],
            theology=DossierTheology(
                storyline_epoch="Church Age",
                theological_locus="Soteriology",
                primary_doctrine="Divine Purpose",
                thematic_ribbon="Redemption",
            ),
            tags=[
                DossierTag(
                    name="election",
                    category="theological",
                    confidence=1.0,
                    starred=True,
                    notes="Foreknown and predestined",
                )
            ],
            cross_references=[
                DossierCrossRef(
                    target_ref="Ephesians 1:4",
                    direction="forward",
                    relationship_type="THEMATIC_PARALLEL",
                    icon="🔗",
                    confidence=0.95,
                    notes="Eternal election",
                )
            ],
            typological_arcs=[
                DossierTypologicalArc(
                    id=1,
                    title="Adam / Christ firstborn",
                    type_ref="Genesis 1:26",
                    antitype_ref="Romans 8:29",
                    theological_correspondence="Adam / Christ firstborn",
                    warrant="EXPLICIT_APOSTOLIC",
                )
            ],
            vector_neighbors=[
                DossierVectorNeighbor(
                    rank=1,
                    score=0.885,
                    match_pct=88.5,
                    title="Spiritual Blessings in Christ",
                    human_ref="Ephesians 1:3-6",
                    book_name="Ephesians",
                    genre="Epistle",
                    redemptive_summary="Election and divine decree",
                )
            ],
            persona_perspectives=[
                DossierPersonaPerspective(
                    persona_id="paul",
                    name="Paul",
                    title="Apostle to the Gentiles",
                    canonical_era="Apostolic / Church Age",
                    is_author=True,
                    pastoral_reflection="Justification by grace through faith in Christ",
                )
            ],
            generated_at="2026-09-11 04:30:00Z",
        )

    def test_to_dict_and_to_json(self) -> None:
        """Verify to_dict and to_json serialize correctly."""
        d_dict = self.dossier.to_dict()
        self.assertEqual(d_dict["metadata"]["reference"], "Romans 8:28-30")
        self.assertEqual(d_dict["metadata"]["human_ref"], "Romans 8:28-30")
        self.assertEqual(len(d_dict["pericopes"]), 1)
        self.assertEqual(len(d_dict["tags"]), 1)

        raw_json = self.dossier.to_json()
        parsed = json.loads(raw_json)
        self.assertEqual(parsed["metadata"]["human_ref"], "Romans 8:28-30")
        self.assertIn("scripture", parsed)

    def test_to_markdown(self) -> None:
        """Verify to_markdown generates complete Markdown research document."""
        md = self.dossier.to_markdown()
        self.assertIn("Exegetical Study Dossier: Romans 8:28-30", md)
        self.assertIn("## 1. Scripture Text", md)
        self.assertIn("The Golden Chain of Redemption", md)
        self.assertIn("Ephesians 1:4", md)
        self.assertIn("Genesis 1:26", md)
        self.assertIn("Paul", md)

    def test_to_html(self) -> None:
        """Verify to_html generates standalone HTML."""
        html_out = self.dossier.to_html()
        self.assertIn("<!DOCTYPE html>", html_out)
        self.assertIn('<html lang="en">', html_out)
        self.assertIn("Exegetical Study Dossier: Romans 8:28-30", html_out)
        self.assertIn("card", html_out)

    def test_to_ansi(self) -> None:
        """Verify to_ansi generates rich colored and uncolored console output."""
        ansi_colored = self.dossier.to_ansi(color=True)
        self.assertIn("\033[", ansi_colored)
        self.assertIn("Romans 8:28-30", ansi_colored)

        ansi_plain = self.dossier.to_ansi(color=False)
        self.assertNotIn("\033[", ansi_plain)
        self.assertIn("Romans 8:28-30", ansi_plain)

    def test_to_text(self) -> None:
        """Verify to_text generates clean plain text without ANSI escape sequences."""
        txt = self.dossier.to_text()
        self.assertNotIn("\033[", txt)
        self.assertIn("Exegetical Study Dossier: Romans 8:28-30", txt)
        self.assertIn("SCRIPTURE TEXT", txt)


class TestExegeticalDossierCLI(unittest.TestCase):
    """Hermetic unit tests for CLI dossier subcommands."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_cli.db"
        self.db = create_test_db(str(self.db_path))

    def tearDown(self) -> None:
        self.db.close()
        self.temp_dir.cleanup()

    def test_cli_dossier_default_ansi(self) -> None:
        """Verify running `bible dossier 'Romans 8:28-30'` defaults to console output."""
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            ret = main(["dossier", "Romans 8:28-30", "--db", str(self.db_path), "--no-color"])
        self.assertEqual(ret, 0)
        output = buf.getvalue()
        self.assertIn("Exegetical Study Dossier: Romans 8:28-30", output)

    def test_cli_study_alias_markdown(self) -> None:
        """Verify `bible study` alias with `--format=markdown`."""
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            ret = main(["study", "Romans 8:28-30", "--format", "markdown", "--db", str(self.db_path)])
        self.assertEqual(ret, 0)
        output = buf.getvalue()
        self.assertIn("Exegetical Study Dossier: Romans 8:28-30", output)

    def test_cli_research_alias_json(self) -> None:
        """Verify `bible research` alias with `--format=json`."""
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            ret = main(["research", "Romans 8:28-30", "--format", "json", "--db", str(self.db_path)])
        self.assertEqual(ret, 0)
        output = buf.getvalue()
        parsed = json.loads(output)
        self.assertEqual(parsed["metadata"]["human_ref"], "Romans 8:28-30")

    def test_cli_packet_export_file(self) -> None:
        """Verify `bible packet` with `--export` writes to a disk file."""
        export_file = Path(self.temp_dir.name) / "dossier.html"
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            ret = main([
                "packet",
                "Romans 8:28-30",
                "--format", "html",
                "--export", str(export_file),
                "--db", str(self.db_path),
            ])
        self.assertEqual(ret, 0)
        self.assertTrue(export_file.exists())
        content = export_file.read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("Romans 8:28-30", content)


class TestExegeticalDossierShell(unittest.TestCase):
    """Hermetic unit tests for BibleShell dossier commands."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_shell.db"
        self.db = create_test_db(str(self.db_path))
        self.shell = BibleShell(database=self.db)

    def tearDown(self) -> None:
        self.db.close()
        self.temp_dir.cleanup()

    def test_shell_dossier_command(self) -> None:
        """Verify `do_dossier` in BibleShell."""
        buf = io.StringIO()
        self.shell.stdout = buf
        self.shell.do_dossier("Romans 8:28-30")
        output = buf.getvalue()
        self.assertIn("Exegetical Study Dossier: Romans 8:28-30", output)

    def test_shell_study_and_read_commands(self) -> None:
        """Verify `do_study` and `do_read` in BibleShell."""
        buf = io.StringIO()
        self.shell.stdout = buf
        self.shell.do_study("Romans 8:28-30")
        output = buf.getvalue()
        self.assertIn("Exegetical Study Dossier: Romans 8:28-30", output)

        buf2 = io.StringIO()
        self.shell.stdout = buf2
        self.shell.do_read("Romans 8:28")
        output2 = buf2.getvalue()
        self.assertIn("Romans 8:28", output2)


class TestExegeticalDossierRestAPI(unittest.TestCase):
    """Hermetic unit tests for /api/dossier REST API endpoint."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_api.db"
        self.db = create_test_db(str(self.db_path))

    def tearDown(self) -> None:
        self.db.close()
        self.temp_dir.cleanup()

    def test_api_dossier_handler_json(self) -> None:
        """Verify handle_dossier with format=json sends expected JSON payload."""
        from web.server import BibleRequestHandler

        handler = BibleRequestHandler.__new__(BibleRequestHandler)
        handler.db = self.db
        handler.send_json = MagicMock()
        handler.send_json_error = MagicMock()

        query = {
            "ref": ["Romans 8:28-30"],
            "format": ["json"],
        }
        handler.handle_dossier(query=query, body_data=None)

        handler.send_json.assert_called_once()
        args, _ = handler.send_json.call_args
        data = args[0]
        self.assertEqual(data["metadata"]["human_ref"], "Romans 8:28-30")
        self.assertIn("scripture", data)
        handler.send_json_error.assert_not_called()

    def test_api_dossier_handler_html(self) -> None:
        """Verify handle_dossier with format=html calls send_html."""
        from web.server import BibleRequestHandler

        handler = BibleRequestHandler.__new__(BibleRequestHandler)
        handler.db = self.db
        handler.send_html = MagicMock()
        handler.send_json_error = MagicMock()

        query = {
            "ref": ["Romans 8:28-30"],
            "format": ["html"],
        }
        handler.handle_dossier(query=query, body_data=None)

        handler.send_html.assert_called_once()
        args, _ = handler.send_html.call_args
        html_str = args[0]
        self.assertIn("<!DOCTYPE html>", html_str)
        self.assertIn("Exegetical Study Dossier: Romans 8:28-30", html_str)
        handler.send_json_error.assert_not_called()

    def test_api_dossier_missing_ref(self) -> None:
        """Verify handle_dossier without ref returns 400."""
        from web.server import BibleRequestHandler

        handler = BibleRequestHandler.__new__(BibleRequestHandler)
        handler.db = self.db
        handler.send_json_error = MagicMock()

        handler.handle_dossier(query={}, body_data=None)
        handler.send_json_error.assert_called_once()
        args, kwargs = handler.send_json_error.call_args
        self.assertIn("Missing required parameter", args[0])
        self.assertEqual(kwargs.get("status"), 400)


if __name__ == "__main__":
    unittest.main()
