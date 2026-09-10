"""Hermetic unit tests for core/corpora.py.

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

from __future__ import annotations

import unittest

from core.corpora import (
    CANONICAL_CORPORA,
    get_corpus,
    get_corpus_for_book,
    list_corpora,
)
from core.reference import get_book


class TestCanonicalCorpora(unittest.TestCase):
    """Test suite for Canonical Corpora Architecture & Whole-Bible Partitioning."""

    def test_canonical_corpora_count_and_keys(self):
        """Verify exactly 7 canonical corpora exist with keys 1 through 7."""
        self.assertEqual(len(CANONICAL_CORPORA), 7)
        self.assertEqual(sorted(CANONICAL_CORPORA.keys()), list(range(1, 8)))

    def test_complete_66_book_coverage_no_duplicates(self):
        """Verify all 66 Protestant canonical books are partitioned with zero overlap."""
        all_book_ids = []
        for corpus_id, corpus in CANONICAL_CORPORA.items():
            self.assertEqual(corpus.corpus_id, corpus_id)
            all_book_ids.extend(corpus.book_ids)

        self.assertEqual(len(all_book_ids), 66)
        self.assertEqual(len(set(all_book_ids)), 66)
        self.assertEqual(sorted(all_book_ids), list(range(1, 67)))

    def test_book_names_match_canonical_reference(self):
        """Verify all book names inside each corpus correspond to valid Book instances."""
        for corpus in CANONICAL_CORPORA.values():
            self.assertEqual(len(corpus.book_names), len(corpus.book_ids))
            for bname, bid in zip(corpus.book_names, corpus.book_ids):
                b = get_book(bid)
                self.assertIsNotNone(b)
                self.assertEqual(b.name, bname)

    def test_corpus_1_composition(self):
        """Verify Corpus 1 includes the Foundational Pauline Epistles & Hebrews."""
        c1 = CANONICAL_CORPORA[1]
        self.assertEqual(c1.corpus_id, 1)
        self.assertEqual(c1.name, "pauline_foundations_hebrews")
        self.assertEqual(
            c1.book_names,
            (
                "Romans",
                "1 Corinthians",
                "2 Corinthians",
                "Galatians",
                "Ephesians",
                "Philippians",
                "Colossians",
                "Hebrews",
            ),
        )
        self.assertEqual(c1.book_ids, (45, 46, 47, 48, 49, 50, 51, 58))
        self.assertEqual(len(c1.books), 8)
        self.assertGreater(c1.total_chapters, 0)
        # 16 + 16 + 13 + 6 + 6 + 4 + 4 + 13 = 78 chapters
        self.assertEqual(c1.total_chapters, 78)

    def test_corpus_2_composition(self):
        """Verify Corpus 2 includes The Four Gospels & Acts."""
        c2 = CANONICAL_CORPORA[2]
        self.assertEqual(c2.corpus_id, 2)
        self.assertEqual(c2.name, "gospels_acts")
        self.assertEqual(
            c2.book_names,
            ("Matthew", "Mark", "Luke", "John", "Acts"),
        )
        self.assertEqual(c2.book_ids, (40, 41, 42, 43, 44))
        self.assertEqual(len(c2.books), 5)
        # 28 + 16 + 24 + 21 + 28 = 117 chapters
        self.assertEqual(c2.total_chapters, 117)

    def test_corpus_3_composition(self):
        """Verify Corpus 3 includes the Pentateuch & Covenant Foundations."""
        c3 = CANONICAL_CORPORA[3]
        self.assertEqual(c3.corpus_id, 3)
        self.assertEqual(c3.name, "pentateuch_covenant")
        self.assertEqual(
            c3.book_names,
            ("Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy"),
        )
        self.assertEqual(c3.book_ids, (1, 2, 3, 4, 5))
        self.assertEqual(len(c3.books), 5)
        # 50 + 40 + 27 + 36 + 34 = 187 chapters
        self.assertEqual(c3.total_chapters, 187)

    def test_corpus_4_composition(self):
        """Verify Corpus 4 includes the Pastoral & General Epistles."""
        c4 = CANONICAL_CORPORA[4]
        self.assertEqual(c4.corpus_id, 4)
        self.assertEqual(c4.name, "pastoral_general_epistles")
        self.assertEqual(
            c4.book_names,
            (
                "1 Thessalonians",
                "2 Thessalonians",
                "1 Timothy",
                "2 Timothy",
                "Titus",
                "Philemon",
                "James",
                "1 Peter",
                "2 Peter",
                "1 John",
                "2 John",
                "3 John",
                "Jude",
            ),
        )
        self.assertEqual(
            c4.book_ids,
            (52, 53, 54, 55, 56, 57, 59, 60, 61, 62, 63, 64, 65),
        )
        self.assertEqual(len(c4.books), 13)
        # 5 + 3 + 6 + 4 + 3 + 1 + 5 + 5 + 3 + 5 + 1 + 1 + 1 = 43 chapters
        self.assertEqual(c4.total_chapters, 43)

    def test_corpus_5_composition(self):
        """Verify Corpus 5 includes Wisdom Literature & Poetry."""
        c5 = CANONICAL_CORPORA[5]
        self.assertEqual(c5.corpus_id, 5)
        self.assertEqual(c5.name, "wisdom_poetry")
        self.assertEqual(
            c5.book_names,
            ("Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon"),
        )
        self.assertEqual(c5.book_ids, (18, 19, 20, 21, 22))
        self.assertEqual(len(c5.books), 5)
        # 42 + 150 + 31 + 12 + 8 = 243 chapters
        self.assertEqual(c5.total_chapters, 243)

    def test_get_corpus_by_id_and_string(self):
        """Verify get_corpus resolves by integer, numeric string, and textual name."""
        c1 = get_corpus(1)
        self.assertIsNotNone(c1)
        self.assertEqual(c1.corpus_id, 1)

        self.assertEqual(get_corpus("1"), c1)
        self.assertEqual(get_corpus("corpus 1"), c1)
        self.assertEqual(get_corpus("corpus-1"), c1)
        self.assertEqual(get_corpus("pauline_foundations_hebrews"), c1)
        self.assertEqual(get_corpus("Pauline"), c1)

        # Non-existent
        self.assertIsNone(get_corpus(0))
        self.assertIsNone(get_corpus(8))
        self.assertIsNone(get_corpus("nonexistent"))
        self.assertIsNone(get_corpus(""))

    def test_get_corpus_for_book(self):
        """Verify get_corpus_for_book identifies the correct corpus for various books."""
        # By ID
        self.assertEqual(get_corpus_for_book(45).corpus_id, 1)  # Romans -> Corpus 1
        self.assertEqual(get_corpus_for_book(58).corpus_id, 1)  # Hebrews -> Corpus 1
        self.assertEqual(get_corpus_for_book(40).corpus_id, 2)  # Matthew -> Corpus 2
        self.assertEqual(get_corpus_for_book(1).corpus_id, 3)   # Genesis -> Corpus 3
        self.assertEqual(get_corpus_for_book(54).corpus_id, 4)  # 1 Tim -> Corpus 4
        self.assertEqual(get_corpus_for_book(19).corpus_id, 5)  # Psalms -> Corpus 5
        self.assertEqual(get_corpus_for_book(23).corpus_id, 6)  # Isaiah -> Corpus 6
        self.assertEqual(get_corpus_for_book(66).corpus_id, 7)  # Revelation -> Corpus 7

        # By Name
        self.assertEqual(get_corpus_for_book("Romans").corpus_id, 1)
        self.assertEqual(get_corpus_for_book("Genesis").corpus_id, 3)
        self.assertEqual(get_corpus_for_book("Revelation").corpus_id, 7)

        # By Book object
        romans_book = get_book("Romans")
        self.assertEqual(get_corpus_for_book(romans_book).corpus_id, 1)

        # Invalid
        self.assertIsNone(get_corpus_for_book(999))
        self.assertIsNone(get_corpus_for_book("NotABook"))

    def test_contains_book(self):
        """Verify contains_book method on CanonicalCorpus."""
        c1 = CANONICAL_CORPORA[1]
        self.assertTrue(c1.contains_book(45))
        self.assertTrue(c1.contains_book("Romans"))
        self.assertTrue(c1.contains_book(get_book("Hebrews")))
        self.assertFalse(c1.contains_book(1))
        self.assertFalse(c1.contains_book("Genesis"))
        self.assertFalse(c1.contains_book("InvalidBook"))

    def test_to_dict_serialization(self):
        """Verify to_dict produces valid metadata structure."""
        c1 = CANONICAL_CORPORA[1]
        d = c1.to_dict()
        self.assertEqual(d["corpus_id"], 1)
        self.assertEqual(d["name"], "pauline_foundations_hebrews")
        self.assertEqual(d["total_books"], 8)
        self.assertEqual(d["total_chapters"], 78)
        self.assertEqual(d["estimated_pericopes"], 110)
        self.assertIn("Romans", d["book_names"])
        self.assertIn(45, d["book_ids"])

    def test_list_corpora(self):
        """Verify list_corpora returns all 7 corpora in order."""
        corpora = list_corpora()
        self.assertEqual(len(corpora), 7)
        self.assertEqual([c.corpus_id for c in corpora], list(range(1, 8)))


if __name__ == "__main__":
    unittest.main()
