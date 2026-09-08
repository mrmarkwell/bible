"""Hermetic unit tests for canonical scripture reference model and parser."""

import csv
import os
import unittest

from core.reference import (
    ALL_BOOKS,
    Reference,
    get_book,
    parse_reference,
    parse_references,
)


class TestBookModel(unittest.TestCase):
    """Test canonical book catalogue, metadata, and alias lookups."""

    def test_canon_counts(self):
        self.assertEqual(len(ALL_BOOKS), 66)
        ot_books = [b for b in ALL_BOOKS if b.testament == "OT"]
        nt_books = [b for b in ALL_BOOKS if b.testament == "NT"]
        self.assertEqual(len(ot_books), 39)
        self.assertEqual(len(nt_books), 27)

    def test_canon_ordering_and_chapters(self):
        self.assertEqual(ALL_BOOKS[0].name, "Genesis")
        self.assertEqual(ALL_BOOKS[0].number, 1)
        self.assertEqual(ALL_BOOKS[0].total_chapters, 50)

        self.assertEqual(ALL_BOOKS[38].name, "Malachi")
        self.assertEqual(ALL_BOOKS[38].number, 39)

        self.assertEqual(ALL_BOOKS[39].name, "Matthew")
        self.assertEqual(ALL_BOOKS[39].number, 40)

        self.assertEqual(ALL_BOOKS[65].name, "Revelation")
        self.assertEqual(ALL_BOOKS[65].number, 66)
        self.assertEqual(ALL_BOOKS[65].total_chapters, 22)

        total_chapters = sum(b.total_chapters for b in ALL_BOOKS)
        self.assertEqual(total_chapters, 1189)

    def test_single_chapter_books(self):
        single_chapter_names = {b.name for b in ALL_BOOKS if b.is_single_chapter}
        expected = {"Obadiah", "Philemon", "2 John", "3 John", "Jude"}
        self.assertEqual(single_chapter_names, expected)

    def test_get_book_lookups(self):
        # By number
        self.assertEqual(get_book(1).name, "Genesis")
        self.assertEqual(get_book(66).name, "Revelation")
        self.assertIsNone(get_book(0))
        self.assertIsNone(get_book(67))

        # By exact name
        self.assertEqual(get_book("Genesis").number, 1)
        self.assertEqual(get_book("Romans").number, 45)

        # By OSIS code
        self.assertEqual(get_book("Gen").number, 1)
        self.assertEqual(get_book("Rev").number, 66)
        self.assertEqual(get_book("1Cor").number, 46)

        # By abbreviations and variants
        self.assertEqual(get_book("1 Cor").name, "1 Corinthians")
        self.assertEqual(get_book("1st Corinthians").name, "1 Corinthians")
        self.assertEqual(get_book("First Corinthians").name, "1 Corinthians")
        self.assertEqual(get_book("I Corinthians").name, "1 Corinthians")
        self.assertEqual(get_book("1Corinthians").name, "1 Corinthians")
        self.assertEqual(get_book("Ps").name, "Psalms")
        self.assertEqual(get_book("Psalm").name, "Psalms")
        self.assertEqual(get_book("Song of Songs").name, "Song of Solomon")
        self.assertEqual(get_book("Canticles").name, "Song of Solomon")
        self.assertEqual(get_book("Revelations").name, "Revelation")

        # Typo tolerance from user CSV
        self.assertEqual(get_book("Galations").name, "Galatians")


class TestReferenceModel(unittest.TestCase):
    """Test Reference dataclass behavior, formatting, and operations."""

    def setUp(self):
        self.gen = get_book("Genesis")
        self.rom = get_book("Romans")
        self.mark = get_book("Mark")

    def test_single_verse(self):
        ref = Reference(self.gen, 1, 27)
        self.assertTrue(ref.is_single_verse)
        self.assertFalse(ref.is_whole_chapter)
        self.assertFalse(ref.is_verse_range)
        self.assertEqual(ref.start_chapter, 1)
        self.assertEqual(ref.start_verse, 27)
        self.assertEqual(ref.end_chapter, 1)
        self.assertEqual(ref.end_verse, 27)
        self.assertEqual(str(ref), "Genesis 1:27")
        self.assertEqual(ref.to_osis(), "Gen.1.27")

    def test_single_verse_with_part(self):
        ref = Reference(self.mark, 4, 41, start_part="b")
        self.assertTrue(ref.is_single_verse)
        self.assertEqual(str(ref), "Mark 4:41b")
        self.assertEqual(ref.to_osis(), "Mark.4.41b")

    def test_verse_range_same_chapter(self):
        ref = Reference(self.rom, 8, 28, end_verse=30)
        self.assertFalse(ref.is_single_verse)
        self.assertTrue(ref.is_verse_range)
        self.assertEqual(str(ref), "Romans 8:28-30")
        self.assertEqual(ref.to_osis(), "Rom.8.28-Rom.8.30")

    def test_verse_range_multi_chapter(self):
        ref = Reference(self.gen, 1, 1, end_chapter=2, end_verse=3)
        self.assertTrue(ref.is_verse_range)
        self.assertEqual(str(ref), "Genesis 1:1-2:3")
        self.assertEqual(ref.to_osis(), "Gen.1.1-Gen.2.3")

    def test_whole_chapter(self):
        ref = Reference(self.gen, 1)
        self.assertTrue(ref.is_whole_chapter)
        self.assertFalse(ref.is_single_verse)
        self.assertEqual(str(ref), "Genesis 1")
        self.assertEqual(ref.to_osis(), "Gen.1")

    def test_chapter_range(self):
        ref = Reference(self.gen, 1, end_chapter=3)
        self.assertTrue(ref.is_chapter_range)
        self.assertEqual(str(ref), "Genesis 1-3")
        self.assertEqual(ref.to_osis(), "Gen.1-Gen.3")

    def test_canonical_ordering(self):
        r1 = Reference(self.gen, 1, 1)
        r2 = Reference(self.gen, 1, 27)
        r3 = Reference(self.gen, 2, 1)
        r4 = Reference(self.rom, 8, 28)
        self.assertTrue(r1 < r2 < r3 < r4)
        sorted_refs = sorted([r4, r2, r1, r3])
        self.assertEqual(sorted_refs, [r1, r2, r3, r4])

    def test_contains(self):
        whole_ch = Reference(self.rom, 8)
        v28 = Reference(self.rom, 8, 28)
        span = Reference(self.rom, 8, 28, end_verse=30)
        other_ch = Reference(self.rom, 9, 1)

        self.assertTrue(whole_ch.contains(v28))
        self.assertTrue(whole_ch.contains(span))
        self.assertFalse(whole_ch.contains(other_ch))
        self.assertTrue(span.contains(v28))
        self.assertFalse(v28.contains(span))

    def test_overlaps(self):
        r1 = Reference(self.rom, 8, 28, end_verse=30)
        r2 = Reference(self.rom, 8, 30, end_verse=32)
        r3 = Reference(self.rom, 8, 31, end_verse=35)
        whole_ch = Reference(self.rom, 8)
        other_ch = Reference(self.rom, 9)
        other_book = Reference(self.gen, 1)

        self.assertTrue(r1.overlaps(r2))
        self.assertFalse(r1.overlaps(r3))
        self.assertTrue(whole_ch.overlaps(r1))
        self.assertFalse(whole_ch.overlaps(other_ch))
        self.assertFalse(r1.overlaps(other_book))

    def test_validation(self):
        valid_ref = Reference(self.gen, 1, 1)
        self.assertTrue(valid_ref.is_valid)
        valid_ref.validate()

        invalid_ch = Reference(self.gen, 51)
        self.assertFalse(invalid_ch.is_valid)
        with self.assertRaises(ValueError):
            invalid_ch.validate()

        invalid_span = Reference(self.gen, 1, 10, end_verse=5)
        self.assertFalse(invalid_span.is_valid)
        with self.assertRaises(ValueError):
            invalid_span.validate()

        invalid_ch_span = Reference(self.gen, 5, end_chapter=2)
        self.assertFalse(invalid_ch_span.is_valid)
        with self.assertRaises(ValueError):
            invalid_ch_span.validate()


class TestReferenceParser(unittest.TestCase):
    """Test parse_reference and parse_references against common biblical strings."""

    def test_standard_verse_references(self):
        ref = parse_reference("John 3:16")
        self.assertEqual(ref.book.name, "John")
        self.assertEqual(ref.start_chapter, 3)
        self.assertEqual(ref.start_verse, 16)
        self.assertTrue(ref.is_single_verse)

        ref_span = parse_reference("Romans 8:28-30")
        self.assertEqual(ref_span.book.name, "Romans")
        self.assertEqual(ref_span.start_chapter, 8)
        self.assertEqual(ref_span.start_verse, 28)
        self.assertEqual(ref_span.end_chapter, 8)
        self.assertEqual(ref_span.end_verse, 30)

        ref_cross = parse_reference("Genesis 1:1 - 2:3")
        self.assertEqual(ref_cross.start_chapter, 1)
        self.assertEqual(ref_cross.start_verse, 1)
        self.assertEqual(ref_cross.end_chapter, 2)
        self.assertEqual(ref_cross.end_verse, 3)

    def test_whole_chapter_and_chapter_spans(self):
        ref = parse_reference("Genesis 1")
        self.assertEqual(ref.book.name, "Genesis")
        self.assertEqual(ref.start_chapter, 1)
        self.assertTrue(ref.is_whole_chapter)

        ref_span = parse_reference("1 Corinthians 12-14")
        self.assertEqual(ref_span.book.name, "1 Corinthians")
        self.assertEqual(ref_span.start_chapter, 12)
        self.assertEqual(ref_span.end_chapter, 14)
        self.assertTrue(ref_span.is_chapter_range)

    def test_single_chapter_books(self):
        # Single chapter books can omit chapter number
        ref1 = parse_reference("Jude 24")
        self.assertEqual(ref1.book.name, "Jude")
        self.assertEqual(ref1.start_chapter, 1)
        self.assertEqual(ref1.start_verse, 24)

        ref2 = parse_reference("Jude 1:24")
        self.assertEqual(ref2.book.name, "Jude")
        self.assertEqual(ref2.start_chapter, 1)
        self.assertEqual(ref2.start_verse, 24)

        ref3 = parse_reference("Philemon 4-7")
        self.assertEqual(ref3.book.name, "Philemon")
        self.assertEqual(ref3.start_chapter, 1)
        self.assertEqual(ref3.start_verse, 4)
        self.assertEqual(ref3.end_verse, 7)

    def test_verse_parts(self):
        ref = parse_reference("Mark 4:41b")
        self.assertEqual(ref.book.name, "Mark")
        self.assertEqual(ref.start_chapter, 4)
        self.assertEqual(ref.start_verse, 41)
        self.assertEqual(ref.start_part, "b")

        ref2 = parse_reference("2 Corinthians 12:9a")
        self.assertEqual(ref2.book.name, "2 Corinthians")
        self.assertEqual(ref2.start_chapter, 12)
        self.assertEqual(ref2.start_verse, 9)
        self.assertEqual(ref2.start_part, "a")

    def test_dash_and_separator_variations(self):
        # En-dash and em-dash
        r1 = parse_reference("Romans 8:28–30")
        r2 = parse_reference("Romans 8:28—30")
        self.assertEqual(r1.end_verse, 30)
        self.assertEqual(r2.end_verse, 30)

        # Dot separator
        r3 = parse_reference("John 3.16")
        self.assertEqual(r3.start_chapter, 3)
        self.assertEqual(r3.start_verse, 16)

    def test_parse_references_multiple(self):
        refs = parse_references("John 3:16; Romans 8:28; Gen 1:1")
        self.assertEqual(len(refs), 3)
        self.assertEqual([r.book.name for r in refs], ["John", "Romans", "Genesis"])

    def test_whole_book_parsing(self):
        ref = parse_reference("Genesis")
        self.assertEqual(ref.book.name, "Genesis")
        self.assertEqual(ref.start_chapter, 1)
        self.assertEqual(ref.end_chapter, 50)
        self.assertTrue(ref.is_chapter_range)

    def test_invalid_and_empty_inputs(self):
        with self.assertRaises(ValueError):
            parse_reference("")
        with self.assertRaises(ValueError):
            parse_reference("   ")
        with self.assertRaises(ValueError):
            parse_reference("NonexistentBook 1:1")
        with self.assertRaises(ValueError):
            parse_reference("Romans abc:xyz")

        self.assertEqual(parse_references(""), [])
        self.assertEqual(parse_references("   "), [])


class TestFavoriteBibleVersesCSVCompatibility(unittest.TestCase):
    """Ensure every single row in favorite_bible_verses.csv parses cleanly."""

    def test_all_rows_parse(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csv_path = os.path.join(repo_root, "favorite_bible_verses.csv")
        self.assertTrue(os.path.isfile(csv_path), "favorite_bible_verses.csv missing")

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                count += 1
                ref = Reference.from_csv_row(row)
                self.assertIsNotNone(ref.book, f"Failed on book for row {count}: {row}")
                self.assertGreaterEqual(ref.start_chapter, 1)
                # Ensure str representation doesn't crash
                formatted = str(ref)
                self.assertTrue(len(formatted) > 0)
            self.assertEqual(count, 829)


if __name__ == "__main__":
    unittest.main()
