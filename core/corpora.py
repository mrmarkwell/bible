"""Canonical Corpora Architecture & Whole-Bible Partitioning Engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003, ADR-082, ADR-083).
Partitions all 66 Protestant canonical books into 7 sequential, cohesive theological corpora:
- Corpus 1: Foundational Pauline Epistles & Hebrews (Romans, 1-2 Cor, Gal, Eph, Phil, Col, Heb)
- Corpus 2: The Four Gospels & Acts (Matthew, Mark, Luke, John, Acts)
- Corpus 3: Pentateuch & Covenant Foundations (Genesis to Deuteronomy)
- Corpus 4: Pastoral & General Epistles (1-2 Thess, 1-2 Tim, Titus, Phlm, James, 1-2 Pet, 1-3 John, Jude)
- Corpus 5: Wisdom Literature & Poetry (Job, Psalms, Proverbs, Ecclesiastes, Song of Solomon)
- Corpus 6: Major & Minor Prophets (Isaiah to Malachi)
- Corpus 7: Historical Books & Apocalyptic Consummation (Joshua to Esther, Revelation)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from core.reference import Book, get_book


@dataclass(frozen=True)
class CanonicalCorpus:
    """Represents a bounded, cohesive canonical corpus for semantic and vector campaigns."""

    corpus_id: int
    name: str
    title: str
    description: str
    book_names: Tuple[str, ...]
    book_ids: Tuple[int, ...]
    estimated_pericopes: int

    @property
    def books(self) -> List[Book]:
        """Resolve all Book objects in this corpus in canonical order."""
        result: List[Book] = []
        for bid in self.book_ids:
            b = get_book(bid)
            if b:
                result.append(b)
        return result

    @property
    def total_chapters(self) -> int:
        """Total number of biblical chapters contained in this corpus."""
        return sum(b.total_chapters for b in self.books)

    def contains_book(self, book: Union[Book, int, str]) -> bool:
        """Check whether a book belongs to this corpus."""
        b = get_book(book)
        if not b:
            return False
        return b.number in self.book_ids

    def to_dict(self) -> Dict[str, Any]:
        """Serialize canonical corpus metadata to dictionary."""
        return {
            "corpus_id": self.corpus_id,
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "book_names": list(self.book_names),
            "book_ids": list(self.book_ids),
            "total_books": len(self.book_ids),
            "total_chapters": self.total_chapters,
            "estimated_pericopes": self.estimated_pericopes,
        }


# Authoritative catalog of the 7 Canonical Corpora covering all 66 books
CANONICAL_CORPORA: Dict[int, CanonicalCorpus] = {
    1: CanonicalCorpus(
        corpus_id=1,
        name="pauline_foundations_hebrews",
        title="Foundational Pauline Epistles & Hebrews",
        description="Theological bedrock of justification by grace through faith, union with Christ, cross-centered ecclesiology, and the supreme priesthood of Christ.",
        book_names=(
            "Romans",
            "1 Corinthians",
            "2 Corinthians",
            "Galatians",
            "Ephesians",
            "Philippians",
            "Colossians",
            "Hebrews",
        ),
        book_ids=(45, 46, 47, 48, 49, 50, 51, 58),
        estimated_pericopes=110,
    ),
    2: CanonicalCorpus(
        corpus_id=2,
        name="gospels_acts",
        title="The Four Gospels & Acts",
        description="The incarnation, life, teaching, cross, resurrection, and ascension of Jesus Christ, and the Holy Spirit-empowered birth of the apostolic Church.",
        book_names=("Matthew", "Mark", "Luke", "John", "Acts"),
        book_ids=(40, 41, 42, 43, 44),
        estimated_pericopes=375,
    ),
    3: CanonicalCorpus(
        corpus_id=3,
        name="pentateuch_covenant",
        title="Pentateuch & Covenant Foundations",
        description="Creation, cosmic Fall, patriarchal promises, exodus deliverance, tabernacle dwelling, sacrificial atonement, and covenant faithfulness.",
        book_names=("Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy"),
        book_ids=(1, 2, 3, 4, 5),
        estimated_pericopes=250,
    ),
    4: CanonicalCorpus(
        corpus_id=4,
        name="pastoral_general_epistles",
        title="Pastoral & General Epistles",
        description="Apostolic instructions for pastoral oversight, godly suffering, living faith, sound doctrine, love, and persevering hope in Christ.",
        book_names=(
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
        book_ids=(52, 53, 54, 55, 56, 57, 59, 60, 61, 62, 63, 64, 65),
        estimated_pericopes=80,
    ),
    5: CanonicalCorpus(
        corpus_id=5,
        name="wisdom_poetry",
        title="Wisdom Literature & Poetry",
        description="Covenantal praise, lament, righteous suffering, fear of the Lord, vanity under the sun, and marital devotion pointing to Christ.",
        book_names=("Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon"),
        book_ids=(18, 19, 20, 21, 22),
        estimated_pericopes=240,
    ),
    6: CanonicalCorpus(
        corpus_id=6,
        name="prophets",
        title="Major & Minor Prophets",
        description="Covenant lawsuit against idolatry, warnings of exile, divine justice, the Suffering Servant, the New Covenant, and the Day of the Lord.",
        book_names=(
            "Isaiah",
            "Jeremiah",
            "Lamentations",
            "Ezekiel",
            "Daniel",
            "Hosea",
            "Joel",
            "Amos",
            "Obadiah",
            "Jonah",
            "Micah",
            "Nahum",
            "Habakkuk",
            "Zephaniah",
            "Haggai",
            "Zechariah",
            "Malachi",
        ),
        book_ids=(23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39),
        estimated_pericopes=215,
    ),
    7: CanonicalCorpus(
        corpus_id=7,
        name="historical_apocalypse",
        title="Historical Books & Apocalyptic Consummation",
        description="Israel's historical trajectory from conquest, kingdom, and exile to post-exilic return, culminating in the apocalyptic victory of the Lamb in Revelation.",
        book_names=(
            "Joshua",
            "Judges",
            "Ruth",
            "1 Samuel",
            "2 Samuel",
            "1 Kings",
            "2 Kings",
            "1 Chronicles",
            "2 Chronicles",
            "Ezra",
            "Nehemiah",
            "Esther",
            "Revelation",
        ),
        book_ids=(6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 66),
        estimated_pericopes=150,
    ),
}


def get_corpus(identifier: Union[int, str]) -> Optional[CanonicalCorpus]:
    """Retrieve a canonical corpus by integer ID (1-7), name, or alias string."""
    if isinstance(identifier, int):
        return CANONICAL_CORPORA.get(identifier)

    id_str = str(identifier).strip().lower()
    if not id_str:
        return None

    # Try numeric string (e.g. "1", "corpus 1", "corpus-1")
    digits = "".join(c for c in id_str if c.isdigit())
    if digits:
        val = int(digits)
        if val in CANONICAL_CORPORA:
            return CANONICAL_CORPORA[val]

    # Try exact name or title match
    for corpus in CANONICAL_CORPORA.values():
        if corpus.name.lower() == id_str:
            return corpus
        if corpus.title.lower() == id_str:
            return corpus

    # Substring search
    for corpus in CANONICAL_CORPORA.values():
        if id_str in corpus.name.lower() or id_str in corpus.title.lower():
            return corpus

    return None


def get_corpus_for_book(book: Union[Book, int, str]) -> Optional[CanonicalCorpus]:
    """Identify which of the 7 canonical corpora contains the specified book."""
    b = get_book(book)
    if not b:
        return None
    for corpus in CANONICAL_CORPORA.values():
        if b.number in corpus.book_ids:
            return corpus
    return None


def list_corpora() -> List[CanonicalCorpus]:
    """Return all 7 canonical corpora in sequential numerical order."""
    return [CANONICAL_CORPORA[k] for k in sorted(CANONICAL_CORPORA.keys())]
