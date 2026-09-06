"""Canonical Scripture Reference Model & Parser.

Zero-dependency implementation providing:
- Protestant 66-book canon definitions with ordering, OSIS codes, and chapter counts.
- Flexible book lookup with alias and typo tolerance.
- Comprehensive Reference data model for single verses, verse ranges, cross-chapter spans,
  and whole chapters.
- High-fidelity human-readable and OSIS string formatting.
- Robust reference parser supporting standard and edge-case citation syntaxes.
"""

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


@dataclass(frozen=True)
class Book:
    """Represents one canonical book of the Bible."""

    number: int  # 1 to 66
    name: str  # e.g., "Genesis", "1 Corinthians"
    osis: str  # e.g., "Gen", "1Cor"
    testament: str  # "OT" or "NT"
    total_chapters: int

    @property
    def is_single_chapter(self) -> bool:
        """True if the book has exactly one chapter (e.g. Jude, Philemon)."""
        return self.total_chapters == 1

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"Book({self.number}, '{self.name}', osis='{self.osis}', testament='{self.testament}')"

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Book):
            return NotImplemented
        return self.number < other.number

    def __hash__(self) -> int:
        return hash(self.number)


# Canonical 66 Books of the Protestant Canon
_RAW_BOOKS_DATA: List[Tuple[int, str, str, str, int]] = [
    # Old Testament (1-39)
    (1, "Genesis", "Gen", "OT", 50),
    (2, "Exodus", "Exod", "OT", 40),
    (3, "Leviticus", "Lev", "OT", 27),
    (4, "Numbers", "Num", "OT", 36),
    (5, "Deuteronomy", "Deut", "OT", 34),
    (6, "Joshua", "Josh", "OT", 24),
    (7, "Judges", "Judg", "OT", 21),
    (8, "Ruth", "Ruth", "OT", 4),
    (9, "1 Samuel", "1Sam", "OT", 31),
    (10, "2 Samuel", "2Sam", "OT", 24),
    (11, "1 Kings", "1Kgs", "OT", 22),
    (12, "2 Kings", "2Kgs", "OT", 25),
    (13, "1 Chronicles", "1Chr", "OT", 29),
    (14, "2 Chronicles", "2Chr", "OT", 36),
    (15, "Ezra", "Ezra", "OT", 10),
    (16, "Nehemiah", "Neh", "OT", 13),
    (17, "Esther", "Esth", "OT", 10),
    (18, "Job", "Job", "OT", 42),
    (19, "Psalms", "Ps", "OT", 150),
    (20, "Proverbs", "Prov", "OT", 31),
    (21, "Ecclesiastes", "Eccl", "OT", 12),
    (22, "Song of Solomon", "Song", "OT", 8),
    (23, "Isaiah", "Isa", "OT", 66),
    (24, "Jeremiah", "Jer", "OT", 52),
    (25, "Lamentations", "Lam", "OT", 5),
    (26, "Ezekiel", "Ezek", "OT", 48),
    (27, "Daniel", "Dan", "OT", 12),
    (28, "Hosea", "Hos", "OT", 14),
    (29, "Joel", "Joel", "OT", 3),
    (30, "Amos", "Amos", "OT", 9),
    (31, "Obadiah", "Obad", "OT", 1),
    (32, "Jonah", "Jonah", "OT", 4),
    (33, "Micah", "Mic", "OT", 7),
    (34, "Nahum", "Nah", "OT", 3),
    (35, "Habakkuk", "Hab", "OT", 3),
    (36, "Zephaniah", "Zeph", "OT", 3),
    (37, "Haggai", "Hag", "OT", 2),
    (38, "Zechariah", "Zech", "OT", 14),
    (39, "Malachi", "Mal", "OT", 4),
    # New Testament (40-66)
    (40, "Matthew", "Matt", "NT", 28),
    (41, "Mark", "Mark", "NT", 16),
    (42, "Luke", "Luke", "NT", 24),
    (43, "John", "John", "NT", 21),
    (44, "Acts", "Acts", "NT", 28),
    (45, "Romans", "Rom", "NT", 16),
    (46, "1 Corinthians", "1Cor", "NT", 16),
    (47, "2 Corinthians", "2Cor", "NT", 13),
    (48, "Galatians", "Gal", "NT", 6),
    (49, "Ephesians", "Eph", "NT", 6),
    (50, "Philippians", "Phil", "NT", 4),
    (51, "Colossians", "Col", "NT", 4),
    (52, "1 Thessalonians", "1Thess", "NT", 5),
    (53, "2 Thessalonians", "2Thess", "NT", 3),
    (54, "1 Timothy", "1Tim", "NT", 6),
    (55, "2 Timothy", "2Tim", "NT", 4),
    (56, "Titus", "Titus", "NT", 3),
    (57, "Philemon", "Phlm", "NT", 1),
    (58, "Hebrews", "Heb", "NT", 13),
    (59, "James", "Jas", "NT", 5),
    (60, "1 Peter", "1Pet", "NT", 5),
    (61, "2 Peter", "2Pet", "NT", 3),
    (62, "1 John", "1John", "NT", 5),
    (63, "2 John", "2John", "NT", 1),
    (64, "3 John", "3John", "NT", 1),
    (65, "Jude", "Jude", "NT", 1),
    (66, "Revelation", "Rev", "NT", 22),
]

ALL_BOOKS: Tuple[Book, ...] = tuple(
    Book(num, name, osis, test, ch) for num, name, osis, test, ch in _RAW_BOOKS_DATA
)

BOOKS: Dict[int, Book] = {b.number: b for b in ALL_BOOKS}


def _normalize_key(text: str) -> str:
    """Normalize book name or alias for case- and format-insensitive lookup."""
    s = text.lower().strip()
    # Normalize Roman numerals and ordinal prefixes at the start
    s = re.sub(r"^(1st|first|i)\b\s*", "1 ", s)
    s = re.sub(r"^(2nd|second|ii)\b\s*", "2 ", s)
    s = re.sub(r"^(3rd|third|iii)\b\s*", "3 ", s)
    # Remove punctuation except alphanumeric characters and spaces
    s = re.sub(r"[^\w\s]", "", s)
    # Collapse multiple whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Build alias lookup dictionary
_ALIASES: Dict[str, Book] = {}

# Common book abbreviations mapping (key: alias, value: book name)
_COMMON_ALIASES: Dict[str, str] = {
    # OT
    "gen": "Genesis", "ge": "Genesis", "gn": "Genesis",
    "ex": "Exodus", "exod": "Exodus", "exo": "Exodus",
    "lev": "Leviticus", "le": "Leviticus", "lv": "Leviticus",
    "num": "Numbers", "nu": "Numbers", "nm": "Numbers", "nb": "Numbers",
    "deut": "Deuteronomy", "dt": "Deuteronomy", "de": "Deuteronomy",
    "josh": "Joshua", "jos": "Joshua", "jsh": "Joshua",
    "judg": "Judges", "jdg": "Judges", "jdgs": "Judges", "jud": "Judges", "jg": "Judges",
    "ruth": "Ruth", "rth": "Ruth", "ru": "Ruth",
    "1 sam": "1 Samuel", "1sam": "1 Samuel", "1 sa": "1 Samuel", "1sa": "1 Samuel", "1 s": "1 Samuel", "1s": "1 Samuel", "1 sm": "1 Samuel", "1sm": "1 Samuel",
    "2 sam": "2 Samuel", "2sam": "2 Samuel", "2 sa": "2 Samuel", "2sa": "2 Samuel", "2 s": "2 Samuel", "2s": "2 Samuel", "2 sm": "2 Samuel", "2sm": "2 Samuel",
    "1 kgs": "1 Kings", "1kgs": "1 Kings", "1 ki": "1 Kings", "1ki": "1 Kings", "1 k": "1 Kings", "1k": "1 Kings", "1 kin": "1 Kings",
    "2 kgs": "2 Kings", "2kgs": "2 Kings", "2 ki": "2 Kings", "2ki": "2 Kings", "2 k": "2 Kings", "2k": "2 Kings", "2 kin": "2 Kings",
    "1 chr": "1 Chronicles", "1chr": "1 Chronicles", "1 ch": "1 Chronicles", "1ch": "1 Chronicles", "1 chron": "1 Chronicles",
    "2 chr": "2 Chronicles", "2chr": "2 Chronicles", "2 ch": "2 Chronicles", "2ch": "2 Chronicles", "2 chron": "2 Chronicles",
    "ezra": "Ezra", "ezr": "Ezra",
    "neh": "Nehemiah", "ne": "Nehemiah",
    "esth": "Esther", "est": "Esther", "es": "Esther",
    "job": "Job", "jb": "Job",
    "ps": "Psalms", "psa": "Psalms", "pss": "Psalms", "psalm": "Psalms", "psalms": "Psalms",
    "prov": "Proverbs", "pro": "Proverbs", "pr": "Proverbs", "prv": "Proverbs",
    "eccl": "Ecclesiastes", "ecc": "Ecclesiastes", "ec": "Ecclesiastes", "qoheleth": "Ecclesiastes", "qoh": "Ecclesiastes",
    "song of songs": "Song of Solomon", "song": "Song of Solomon", "sos": "Song of Solomon",
    "canticles": "Song of Solomon", "canticle of canticles": "Song of Solomon", "cant": "Song of Solomon",
    "isa": "Isaiah", "is": "Isaiah",
    "jer": "Jeremiah", "je": "Jeremiah", "jr": "Jeremiah",
    "lam": "Lamentations", "la": "Lamentations",
    "ezek": "Ezekiel", "eze": "Ezekiel", "ez": "Ezekiel",
    "dan": "Daniel", "da": "Daniel", "dn": "Daniel",
    "hos": "Hosea", "ho": "Hosea",
    "joel": "Joel", "joe": "Joel", "jl": "Joel",
    "amos": "Amos", "am": "Amos",
    "obad": "Obadiah", "ob": "Obadiah", "oba": "Obadiah",
    "jonah": "Jonah", "jon": "Jonah", "jnh": "Jonah",
    "mic": "Micah", "micah": "Micah", "mc": "Micah",
    "nah": "Nahum", "nahum": "Nahum", "na": "Nahum",
    "hab": "Habakkuk", "habakkuk": "Habakkuk", "hb": "Habakkuk",
    "zeph": "Zephaniah", "zephaniah": "Zephaniah", "zep": "Zephaniah", "zp": "Zephaniah",
    "hag": "Haggai", "haggai": "Haggai", "hg": "Haggai",
    "zech": "Zechariah", "zechariah": "Zechariah", "zec": "Zechariah", "zc": "Zechariah",
    "mal": "Malachi", "malachi": "Malachi", "ml": "Malachi",
    # NT
    "matt": "Matthew", "mat": "Matthew", "mt": "Matthew",
    "mark": "Mark", "mar": "Mark", "mk": "Mark", "mrk": "Mark",
    "luke": "Luke", "luk": "Luke", "lk": "Luke",
    "john": "John", "joh": "John", "jhn": "John", "jn": "John",
    "acts": "Acts", "act": "Acts", "ac": "Acts",
    "rom": "Romans", "romans": "Romans", "ro": "Romans", "rm": "Romans",
    "1 cor": "1 Corinthians", "1cor": "1 Corinthians", "1 co": "1 Corinthians", "1co": "1 Corinthians",
    "2 cor": "2 Corinthians", "2cor": "2 Corinthians", "2 co": "2 Corinthians", "2co": "2 Corinthians",
    "gal": "Galatians", "galatians": "Galatians", "galations": "Galatians", "ga": "Galatians",
    "eph": "Ephesians", "ephesians": "Ephesians", "ep": "Ephesians",
    "phil": "Philippians", "philippians": "Philippians", "php": "Philippians", "ph": "Philippians",
    "col": "Colossians", "colossians": "Colossians", "co": "Colossians",
    "1 thess": "1 Thessalonians", "1thess": "1 Thessalonians", "1 th": "1 Thessalonians", "1th": "1 Thessalonians",
    "2 thess": "2 Thessalonians", "2thess": "2 Thessalonians", "2 th": "2 Thessalonians", "2th": "2 Thessalonians",
    "1 tim": "1 Timothy", "1tim": "1 Timothy", "1 ti": "1 Timothy", "1ti": "1 Timothy",
    "2 tim": "2 Timothy", "2tim": "2 Timothy", "2 ti": "2 Timothy", "2ti": "2 Timothy",
    "titus": "Titus", "tit": "Titus", "ti": "Titus",
    "phlm": "Philemon", "philemon": "Philemon", "phm": "Philemon", "pm": "Philemon",
    "heb": "Hebrews", "hebrews": "Hebrews", "he": "Hebrews",
    "jas": "James", "james": "James", "jam": "James", "jm": "James",
    "1 pet": "1 Peter", "1pet": "1 Peter", "1 pe": "1 Peter", "1pe": "1 Peter", "1 pt": "1 Peter", "1pt": "1 Peter",
    "2 pet": "2 Peter", "2pet": "2 Peter", "2 pe": "2 Peter", "2pe": "2 Peter", "2 pt": "2 Peter", "2pt": "2 Peter",
    "1 john": "1 John", "1john": "1 John", "1 jn": "1 John", "1jn": "1 John", "1 jo": "1 John", "1jo": "1 John", "1 jhn": "1 John",
    "2 john": "2 John", "2john": "2 John", "2 jn": "2 John", "2jn": "2 John", "2 jo": "2 John", "2jo": "2 John", "2 jhn": "2 John",
    "3 john": "3 John", "3john": "3 John", "3 jn": "3 John", "3jn": "3 John", "3 jo": "3 John", "3jo": "3 John", "3 jhn": "3 John",
    "jude": "Jude", "jud": "Jude", "jd": "Jude",
    "rev": "Revelation", "revelation": "Revelation", "revelations": "Revelation", "apocalypse": "Revelation", "apoc": "Revelation", "rv": "Revelation",
}

# Populate _ALIASES with canonical names, OSIS codes, and alias table
for book in ALL_BOOKS:
    _ALIASES[_normalize_key(book.name)] = book
    _ALIASES[_normalize_key(book.osis)] = book
    _ALIASES[_normalize_key(book.name.replace(" ", ""))] = book

for alias_str, book_name in _COMMON_ALIASES.items():
    matching_book = next((b for b in ALL_BOOKS if b.name == book_name), None)
    if matching_book:
        _ALIASES[_normalize_key(alias_str)] = matching_book
        _ALIASES[_normalize_key(alias_str.replace(" ", ""))] = matching_book


def get_book(query: Union[str, int], default: Optional[Book] = None) -> Optional[Book]:
    """Retrieve a canonical Book by its 1-66 number, full name, OSIS code, or alias."""
    if isinstance(query, int):
        return BOOKS.get(query, default)
    if not isinstance(query, str):
        return default

    query_str = query.strip()
    if query_str.isdigit():
        return BOOKS.get(int(query_str), default)

    normalized = _normalize_key(query_str)
    if normalized in _ALIASES:
        return _ALIASES[normalized]

    # Try removing all spaces
    no_spaces = normalized.replace(" ", "")
    if no_spaces in _ALIASES:
        return _ALIASES[no_spaces]

    return default


@dataclass(frozen=True)
class Reference:
    """Canonical Scripture Reference model.

    Supports:
    - Single verse (e.g., John 3:16)
    - Single verse part (e.g., Mark 4:41b)
    - Verse range within chapter (e.g., Romans 8:28-30)
    - Cross-chapter verse span (e.g., Genesis 1:1 - 2:3)
    - Whole chapter (e.g., Genesis 1)
    - Chapter range (e.g., 1 Corinthians 12-14)
    """

    book: Book
    start_chapter: int
    start_verse: Optional[int] = None
    start_part: Optional[str] = None
    end_chapter: Optional[int] = None
    end_verse: Optional[int] = None
    end_part: Optional[str] = None

    def __post_init__(self) -> None:
        # Normalize chapter and verse boundary defaults
        ec = self.end_chapter
        ev = self.end_verse
        ep = self.end_part

        if self.start_verse is not None:
            if ec is None:
                ec = self.start_chapter
            if ev is None:
                ev = self.start_verse
                if ep is None:
                    ep = self.start_part
        else:
            if ec is None:
                ec = self.start_chapter

        # Use object.__setattr__ because class is frozen
        object.__setattr__(self, "end_chapter", ec)
        object.__setattr__(self, "end_verse", ev)
        object.__setattr__(self, "end_part", ep)

    @property
    def is_whole_chapter(self) -> bool:
        """True if the reference denotes an entire chapter without specific verse boundaries."""
        return self.start_verse is None and self.start_chapter == self.end_chapter

    @property
    def is_chapter_range(self) -> bool:
        """True if the reference spans multiple full chapters."""
        return self.start_verse is None and self.start_chapter != self.end_chapter

    @property
    def is_single_verse(self) -> bool:
        """True if the reference points to a single verse (or single verse clause)."""
        return (
            self.start_verse is not None
            and self.start_chapter == self.end_chapter
            and self.start_verse == self.end_verse
            and self.start_part == self.end_part
        )

    @property
    def is_verse_range(self) -> bool:
        """True if the reference spans multiple verses."""
        return self.start_verse is not None and not self.is_single_verse

    def format(self, style: str = "human") -> str:
        """Format the reference as human-readable text."""
        bname = self.book.name
        if self.is_single_verse:
            part = self.start_part or ""
            return f"{bname} {self.start_chapter}:{self.start_verse}{part}"
        elif self.is_whole_chapter:
            return f"{bname} {self.start_chapter}"
        elif self.is_chapter_range:
            return f"{bname} {self.start_chapter}-{self.end_chapter}"
        else:  # is_verse_range
            sp = self.start_part or ""
            ep = self.end_part or ""
            if self.start_chapter == self.end_chapter:
                return f"{bname} {self.start_chapter}:{self.start_verse}{sp}-{self.end_verse}{ep}"
            else:
                return f"{bname} {self.start_chapter}:{self.start_verse}{sp}-{self.end_chapter}:{self.end_verse}{ep}"

    def to_osis(self) -> str:
        """Format the reference conforming to standard OSIS reference syntax."""
        osis = self.book.osis
        if self.is_whole_chapter:
            return f"{osis}.{self.start_chapter}"
        elif self.is_chapter_range:
            return f"{osis}.{self.start_chapter}-{osis}.{self.end_chapter}"
        elif self.is_single_verse:
            part = self.start_part or ""
            return f"{osis}.{self.start_chapter}.{self.start_verse}{part}"
        else:  # is_verse_range
            sp = self.start_part or ""
            ep = self.end_part or ""
            start = f"{osis}.{self.start_chapter}.{self.start_verse}{sp}"
            end = f"{osis}.{self.end_chapter}.{self.end_verse}{ep}"
            return f"{start}-{end}"

    def contains(self, other: "Reference") -> bool:
        """Check if this reference completely encompasses another reference."""
        if self.book != other.book:
            return False

        if self.is_whole_chapter:
            assert self.end_chapter is not None
            return self.start_chapter <= other.start_chapter and self.end_chapter >= (other.end_chapter or other.start_chapter)

        if self.is_chapter_range:
            assert self.end_chapter is not None
            return self.start_chapter <= other.start_chapter and self.end_chapter >= (other.end_chapter or other.start_chapter)

        # Self has verse boundaries
        if other.start_verse is None:
            return False

        assert self.start_verse is not None
        assert self.end_verse is not None
        assert self.end_chapter is not None
        assert other.end_verse is not None
        assert other.end_chapter is not None

        start_cmp = (self.start_chapter, self.start_verse) <= (other.start_chapter, other.start_verse)
        end_cmp = (self.end_chapter, self.end_verse) >= (other.end_chapter, other.end_verse)
        return start_cmp and end_cmp

    def overlaps(self, other: "Reference") -> bool:
        """Check if this reference overlaps with another reference."""
        if self.book != other.book:
            return False

        # If both are whole chapters
        s_c1 = self.start_chapter
        s_c2 = self.end_chapter or self.start_chapter
        o_c1 = other.start_chapter
        o_c2 = other.end_chapter or other.start_chapter

        if s_c2 < o_c1 or o_c2 < s_c1:
            return False

        if self.start_verse is None or other.start_verse is None:
            return True

        s_v1 = (self.start_chapter, self.start_verse)
        s_v2 = (self.end_chapter or self.start_chapter, self.end_verse or self.start_verse)
        o_v1 = (other.start_chapter, other.start_verse)
        o_v2 = (other.end_chapter or other.start_chapter, other.end_verse or other.start_verse)

        return not (s_v2 < o_v1 or o_v2 < s_v1)

    def validate(self) -> None:
        """Validate chapter and verse numbers against canonical boundaries."""
        if self.start_chapter < 1:
            raise ValueError(f"Start chapter {self.start_chapter} must be >= 1")
        if self.start_chapter > self.book.total_chapters:
            raise ValueError(
                f"Chapter {self.start_chapter} exceeds total chapters ({self.book.total_chapters}) for {self.book.name}"
            )
        if self.end_chapter is not None:
            if self.end_chapter < self.start_chapter:
                raise ValueError(
                    f"End chapter {self.end_chapter} cannot be less than start chapter {self.start_chapter}"
                )
            if self.end_chapter > self.book.total_chapters:
                raise ValueError(
                    f"End chapter {self.end_chapter} exceeds total chapters ({self.book.total_chapters}) for {self.book.name}"
                )
        if self.start_verse is not None and self.start_verse < 1:
            raise ValueError(f"Start verse {self.start_verse} must be >= 1")
        if self.end_verse is not None and self.end_verse < 1:
            raise ValueError(f"End verse {self.end_verse} must be >= 1")
        if (
            self.start_verse is not None
            and self.end_verse is not None
            and self.start_chapter == self.end_chapter
            and self.end_verse < self.start_verse
        ):
            raise ValueError(
                f"End verse {self.end_verse} cannot be less than start verse {self.start_verse} in same chapter"
            )

    @property
    def is_valid(self) -> bool:
        """Return True if reference satisfies canonical chapter and verse bounds."""
        try:
            self.validate()
            return True
        except ValueError:
            return False

    def _sort_key(self) -> Tuple[int, int, int, str, int, int, str]:
        return (
            self.book.number,
            self.start_chapter,
            self.start_verse or 0,
            self.start_part or "",
            self.end_chapter or self.start_chapter,
            self.end_verse or 0,
            self.end_part or "",
        )

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Reference):
            return NotImplemented
        return self._sort_key() < other._sort_key()

    def __str__(self) -> str:
        return self.format()

    def __repr__(self) -> str:
        return f"Reference({self.format()!r})"

    @classmethod
    def from_csv_row(cls, row: Dict[str, str]) -> "Reference":
        """Parse a row dictionary (e.g. from favorite_bible_verses.csv) into a Reference."""
        book_name = row["book"].strip()
        book = get_book(book_name)
        if not book:
            raise ValueError(f"Unknown book in CSV row: {book_name!r}")

        chapter = int(row["chapter"].strip())
        sv_raw = row.get("start_verse", "").strip()
        ev_raw = row.get("end_verse", "").strip()

        start_verse: Optional[int] = None
        start_part: Optional[str] = None
        end_verse: Optional[int] = None
        end_part: Optional[str] = None

        if sv_raw:
            m = re.match(r"^(\d+)([a-zA-Z]?)$", sv_raw)
            if m:
                start_verse = int(m.group(1))
                start_part = m.group(2) or None
            else:
                raise ValueError(f"Invalid start verse format: {sv_raw!r}")

        if ev_raw:
            m = re.match(r"^(\d+)([a-zA-Z]?)$", ev_raw)
            if m:
                end_verse = int(m.group(1))
                end_part = m.group(2) or None
            else:
                raise ValueError(f"Invalid end verse format: {ev_raw!r}")

        return cls(
            book=book,
            start_chapter=chapter,
            start_verse=start_verse,
            start_part=start_part,
            end_chapter=chapter,
            end_verse=end_verse,
            end_part=end_part,
        )


def _parse_passage_numbers(
    num_part: str, is_single_chapter: bool = False
) -> Tuple[int, Optional[int], Optional[str], int, Optional[int], Optional[str]]:
    """Parse chapter and verse numbers from citation string."""
    # Normalize dashes and spaces
    clean = re.sub(r"[\u2013\u2014\u2212]", "-", num_part.strip())

    # 1. Cross chapter verse span: "1:1 - 2:3" or "1:1a-2:3b"
    m = re.match(r"^(\d+)\s*[:.]\s*(\d+)([a-zA-Z]?)\s*-\s*(\d+)\s*[:.]\s*(\d+)([a-zA-Z]?)$", clean)
    if m:
        c1, v1, p1, c2, v2, p2 = m.groups()
        return int(c1), int(v1), p1 or None, int(c2), int(v2), p2 or None

    # 2. Same chapter verse span: "8:28-30" or "8:28a-30b"
    m = re.match(r"^(\d+)\s*[:.]\s*(\d+)([a-zA-Z]?)\s*-\s*(\d+)([a-zA-Z]?)$", clean)
    if m:
        c1, v1, p1, v2, p2 = m.groups()
        return int(c1), int(v1), p1 or None, int(c1), int(v2), p2 or None

    # 3. Single verse: "3:16" or "4:41b"
    m = re.match(r"^(\d+)\s*[:.]\s*(\d+)([a-zA-Z]?)$", clean)
    if m:
        c1, v1, p1 = m.groups()
        return int(c1), int(v1), p1 or None, int(c1), int(v1), p1 or None

    # 4. Range: "1-3" or "4-7"
    m = re.match(r"^(\d+)\s*-\s*(\d+)$", clean)
    if m:
        n1, n2 = int(m.group(1)), int(m.group(2))
        if is_single_chapter:
            return 1, n1, None, 1, n2, None
        else:
            return n1, None, None, n2, None, None

    # 5. Single number: "1", "23", "24", or with part "41b"
    m = re.match(r"^(\d+)([a-zA-Z]?)$", clean)
    if m:
        n, p = int(m.group(1)), m.group(2) or None
        if is_single_chapter and (n > 1 or p):
            return 1, n, p, 1, n, p
        elif is_single_chapter and n == 1:
            return 1, None, None, 1, None, None
        else:
            return n, None, None, n, None, None

    raise ValueError(f"Unrecognized passage numbers: {num_part!r}")


def parse_reference(text: str) -> Reference:
    """Parse a single Scripture citation string into a Reference object.

    Handles full names, abbreviations, verse spans, cross-chapter spans,
    single-chapter books, and verse parts.
    """
    text = text.strip()
    if not text:
        raise ValueError("Cannot parse empty reference string")

    # Normalize dashes first
    text = re.sub(r"[\u2013\u2014\u2212]", "-", text)

    # Split into book part and number part
    # A book name can begin with 1, 2, 3, 1st, 2nd, 3rd, I, II, III followed by alpha chars
    m = re.match(r"^([1-3]?(?:st|nd|rd)?\s*[a-zA-Z\s]+?)\s*(\d.*)$", text)
    if not m:
        # Check if the entire string is just a book name (whole book reference)
        book = get_book(text)
        if book:
            return Reference(book=book, start_chapter=1, end_chapter=book.total_chapters)
        raise ValueError(f"Could not parse Scripture reference: {text!r}")

    book_str, num_str = m.group(1).strip(), m.group(2).strip()
    book = get_book(book_str)
    if not book:
        raise ValueError(f"Unknown Bible book: {book_str!r} in reference: {text!r}")

    c1, v1, p1, c2, v2, p2 = _parse_passage_numbers(num_str, is_single_chapter=book.is_single_chapter)

    return Reference(
        book=book,
        start_chapter=c1,
        start_verse=v1,
        start_part=p1,
        end_chapter=c2,
        end_verse=v2,
        end_part=p2,
    )


def parse_references(text: str) -> List[Reference]:
    """Parse multiple semicolon- or comma-separated Scripture references."""
    clean = text.strip()
    if not clean:
        return []

    # If semicolon delimited, split directly
    if ";" in clean:
        chunks = [c.strip() for c in clean.split(";") if c.strip()]
        return [parse_reference(c) for c in chunks]

    # Otherwise parse as single reference
    return [parse_reference(clean)]
