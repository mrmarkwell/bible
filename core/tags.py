"""Semantic Tagging & Knowledge Database Engine for Bible Engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003):
- Multi-resolution semantic tagging across individual verses, arbitrary spans,
  whole chapters, and multi-chapter ranges.
- Canonical span registration and lifecycle management in SQLite database.
- Predefined theological, redemptive-historical, and thematic taxonomies.
- High-level query abstractions with hydrated scripture text, tag co-occurrence,
  and passage relevance.
- Fast tag search, categorization, and statistics.
"""

from dataclasses import dataclass, field
import json
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

from core.db import (
    Database,
    SpanRecord,
    TagRecord,
    VerseRecord,
    VerseTagRecord,
    normalize_tag_name,
)
from core.reference import (
    Book,
    Reference,
    get_book,
    parse_reference,
    parse_references,
)


# ==============================================================================
# Canonical Taxonomy Categories
# ==============================================================================


class TagCategory:
    """Canonical categories for organizing semantic tags."""

    THEMATIC = "thematic"
    THEOLOGICAL = "theological"
    HISTORICAL = "historical"
    LITURGICAL = "liturgical"
    CURATION = "curation"
    PROPHECY = "prophecy"
    TYPOLOGY = "typology"

    ALL: Tuple[str, ...] = (
        THEMATIC,
        THEOLOGICAL,
        HISTORICAL,
        LITURGICAL,
        CURATION,
        PROPHECY,
        TYPOLOGY,
    )

    @classmethod
    def is_valid(cls, category: str) -> bool:
        """Check if a category string is recognized."""
        return category.strip().lower() in cls.ALL


# Predefined theological & redemptive-historical taxonomy presets (TGC-aligned, snake_case canonical identifiers)
CANONICAL_TAXONOMY: Dict[str, List[Tuple[str, str, str]]] = {
    # (tag_name, category, description)
    "redemptive_historical": [
        ("creation", TagCategory.HISTORICAL, "The original good creation of the heavens and earth by God."),
        ("fall", TagCategory.THEOLOGICAL, "The rebellion of humanity into sin and cosmic brokenness."),
        ("covenant", TagCategory.THEOLOGICAL, "God's binding oaths and promises with Adam, Noah, Abraham, Moses, David, and Christ."),
        ("exodus", TagCategory.HISTORICAL, "God delivering His people out of bondage through signs, blood, and the Red Sea."),
        ("temple", TagCategory.TYPOLOGY, "The dwelling place of God with man, culminating in Christ and the church."),
        ("kingship", TagCategory.THEOLOGICAL, "God's sovereignty exercised through the Davidic line, realized in Christ."),
        ("exile", TagCategory.HISTORICAL, "Covenant judgment, dispersion, and the longing for restoration."),
        ("restoration", TagCategory.PROPHECY, "The return from exile, spiritual renewal, and the new creation."),
        ("redemption", TagCategory.THEOLOGICAL, "Deliverance from sin and death purchased by the blood of Christ."),
        ("new_creation", TagCategory.PROPHECY, "The final renewal of all things in the New Jerusalem."),
    ],
    "systematic_theology": [
        ("trinity", TagCategory.THEOLOGICAL, "One God eternally existing in three co-equal persons: Father, Son, and Holy Spirit."),
        ("christology", TagCategory.THEOLOGICAL, "The person and dual divine-human nature of Jesus Christ."),
        ("pneumatology", TagCategory.THEOLOGICAL, "The person, work, gifts, and fruit of the Holy Spirit."),
        ("holy_spirit", TagCategory.THEOLOGICAL, "The third person of the Trinity indwelling, empowering, and sanctifying believers."),
        ("justification", TagCategory.THEOLOGICAL, "God's forensic declaration of righteousness by grace alone through faith alone."),
        ("sanctification", TagCategory.THEOLOGICAL, "The progressive transformation of the believer into the likeness of Christ."),
        ("sovereign_grace", TagCategory.THEOLOGICAL, "God's unconditional love and unmerited favor in election and salvation."),
        ("resurrection", TagCategory.THEOLOGICAL, "The bodily rising of Jesus Christ from the dead and future resurrection of the saints."),
        ("atonement", TagCategory.THEOLOGICAL, "Christ's penal substitutionary sacrifice satisfying divine justice."),
    ],
    "practical_christian_living": [
        ("prayer", TagCategory.THEMATIC, "Communion with God, petitions, thanksgiving, and intercession."),
        ("wisdom", TagCategory.THEMATIC, "Skill in godly living according to God's created order and fear of the Lord."),
        ("suffering", TagCategory.THEMATIC, "Trials, affliction, endurance, and God's sovereign comfort in hardship."),
        ("joy", TagCategory.THEMATIC, "Deep gladness rooted in God's character and salvation regardless of circumstances."),
        ("faith", TagCategory.THEMATIC, "Trust, reliance, and assurance in God's character and revealed promises."),
        ("love", TagCategory.THEMATIC, "Self-sacrificial devotion modeled after God's love in Christ."),
    ],
}


# ==============================================================================
# Data Records & DTOs
# ==============================================================================


@dataclass(frozen=True)
class BookTopicDensity:
    """Aggregated topic density metrics for a specific canonical book."""

    book_id: int
    book_name: str
    osis: str
    testament: str
    total_chapters: int
    passage_count: int
    starred_count: int
    distinct_tags: int
    tag_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert book topic density to dictionary representation."""
        return {
            "book_id": self.book_id,
            "book_name": self.book_name,
            "osis": self.osis,
            "testament": self.testament,
            "total_chapters": self.total_chapters,
            "passage_count": self.passage_count,
            "starred_count": self.starred_count,
            "distinct_tags": self.distinct_tags,
            "tag_counts": dict(self.tag_counts),
        }


@dataclass(frozen=True)
class ChapterTopicDensity:
    """Aggregated topic density metrics for a specific chapter within a canonical book."""

    book_id: int
    book_name: str
    osis: str
    chapter: int
    passage_count: int
    starred_count: int
    distinct_tags: int
    tag_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert chapter topic density to dictionary representation."""
        return {
            "book_id": self.book_id,
            "book_name": self.book_name,
            "osis": self.osis,
            "chapter": self.chapter,
            "passage_count": self.passage_count,
            "starred_count": self.starred_count,
            "distinct_tags": self.distinct_tags,
            "tag_counts": dict(self.tag_counts),
        }


@dataclass(frozen=True)
class TagCoOccurrence:
    """Co-occurrence pair metrics between two semantic tags."""

    tag_a: str
    tag_b: str
    shared_passages: int
    jaccard_similarity: float
    dice_coefficient: float
    category_a: Optional[str] = None
    category_b: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert co-occurrence pair to dictionary representation."""
        return {
            "tag_a": self.tag_a,
            "tag_b": self.tag_b,
            "shared_passages": self.shared_passages,
            "jaccard_similarity": round(self.jaccard_similarity, 4),
            "dice_coefficient": round(self.dice_coefficient, 4),
            "category_a": self.category_a,
            "category_b": self.category_b,
        }


@dataclass(frozen=True)
class TagCoOccurrenceMatrix:
    """Matrix representation of tag co-occurrences across the corpus."""

    tags: List[str]
    matrix: Dict[str, Dict[str, int]]
    pair_metrics: List[TagCoOccurrence]

    def to_dict(self) -> Dict[str, Any]:
        """Convert co-occurrence matrix to dictionary representation."""
        return {
            "tags": list(self.tags),
            "matrix": {k: dict(v) for k, v in self.matrix.items()},
            "pairs": [p.to_dict() for p in self.pair_metrics],
        }


@dataclass(frozen=True)
class VerseRelevance:
    """Relevance scoring and ranking for a scripture passage against a set of topic tags."""

    reference: Reference
    human_ref: str
    osis: str
    score: float
    matched_tags: List[str]
    total_requested_tags: int
    match_ratio: float
    starred: bool
    highest_confidence: float
    text: str = ""
    verses: List[VerseRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert verse relevance ranking to dictionary representation."""
        return {
            "reference": self.human_ref,
            "osis": self.osis,
            "score": round(self.score, 4),
            "matched_tags": list(self.matched_tags),
            "total_requested_tags": self.total_requested_tags,
            "match_ratio": round(self.match_ratio, 4),
            "starred": self.starred,
            "highest_confidence": round(self.highest_confidence, 4),
            "verse_count": len(self.verses),
            "text": self.text,
        }


@dataclass(frozen=True)
class TagSummary:
    """Aggregated summary information for a semantic tag."""

    id: int
    name: str
    category: str
    description: Optional[str]
    passage_count: int
    starred_count: int
    distinct_books: int
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "passage_count": self.passage_count,
            "starred_count": self.starred_count,
            "distinct_books": self.distinct_books,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class TaggedPassage:
    """Represents a passage associated with a tag, hydrated with scripture text."""

    id: int  # verse_tags row id
    tag_id: int
    tag_name: str
    reference: Reference
    human_ref: str
    confidence: float
    source: str
    starred: bool
    notes: Optional[str]
    span_id: Optional[int]
    created_at: Optional[str]
    verses: List[VerseRecord] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Joined passage text from hydrated verses."""
        return " ".join(v.text for v in self.verses)

    @property
    def verse_count(self) -> int:
        """Number of verses in this passage."""
        return len(self.verses)

    def to_dict(self) -> Dict[str, Any]:
        """Convert tagged passage to dictionary representation."""
        return {
            "id": self.id,
            "tag_id": self.tag_id,
            "tag_name": self.tag_name,
            "human_ref": self.human_ref,
            "osis": self.reference.to_osis(),
            "confidence": self.confidence,
            "source": self.source,
            "starred": self.starred,
            "notes": self.notes,
            "span_id": self.span_id,
            "created_at": self.created_at,
            "verse_count": len(self.verses),
            "text": self.text,
            "verses": [
                {
                    "reference": v.human_ref,
                    "text": v.text,
                    "chapter": v.chapter,
                    "verse": v.verse,
                    "subverse": v.subverse,
                }
                for v in self.verses
            ],
        }


# ==============================================================================
# Tagging Service Engine
# ==============================================================================


class TaggingService:
    """Domain service for managing semantic tags, passage annotations, and taxonomies."""

    def __init__(self, db: Optional[Database] = None) -> None:
        """Initialize TaggingService with database instance."""
        self.db = db if db is not None else Database()

    # --- Tag Definitions & Taxonomy Lifecycle ---

    def add_tag(
        self,
        name: str,
        category: str = TagCategory.THEMATIC,
        description: Optional[str] = None,
    ) -> TagRecord:
        """Register a new semantic tag definition or update its metadata in canonical snake_case."""
        clean_name = normalize_tag_name(name)
        clean_cat = category.strip().lower()
        return self.db.add_tag(clean_name, category=clean_cat, description=description)

    def get_tag(self, name: str) -> Optional[TagRecord]:
        """Retrieve tag record by name (case-insensitive, snake_case normalized)."""
        clean_name = normalize_tag_name(name)
        return self.db.get_tag(clean_name)

    def get_or_create_tag(
        self,
        name: str,
        category: str = TagCategory.THEMATIC,
        description: Optional[str] = None,
    ) -> TagRecord:
        """Retrieve tag by name or create it if absent in canonical snake_case."""
        clean_name = normalize_tag_name(name)
        return self.db.get_or_create_tag(clean_name, category=category, description=description)

    def delete_tag(self, name: str) -> bool:
        """Delete a tag definition and all its passage associations."""
        clean_name = normalize_tag_name(name)
        return self.db.delete_tag(clean_name)

    def prune_unlinked_tags(self, preserve_tags: Sequence[str] = ("favorites", "starred")) -> int:
        """Prune unused tags that have zero verse associations (preserves favorites and starred)."""
        return self.db.prune_unlinked_tags(preserve_tags=preserve_tags)

    def list_tags(
        self,
        category: Optional[str] = None,
        sort_by: str = "passages",
    ) -> List[TagSummary]:
        """List tags with usage statistics, optionally filtered by category.

        Args:
            category: Optional category filter.
            sort_by: Sorting field ('passages', 'name', 'starred', 'category').

        Returns:
            List of TagSummary objects.
        """
        stats = self.db.get_tag_stats()
        summaries = [
            TagSummary(
                id=s["id"],
                name=s["name"],
                category=s["category"],
                description=s["description"],
                passage_count=s["passage_count"],
                starred_count=s["starred_count"],
                distinct_books=s["distinct_books"],
                created_at=s["created_at"],
            )
            for s in stats
        ]

        if category:
            cat_norm = category.strip().lower()
            summaries = [s for s in summaries if s.category.lower() == cat_norm]

        if sort_by == "name":
            summaries.sort(key=lambda s: s.name.lower())
        elif sort_by == "starred":
            summaries.sort(key=lambda s: (s.starred_count, s.passage_count), reverse=True)
        elif sort_by == "category":
            summaries.sort(key=lambda s: (s.category, s.name.lower()))
        else:  # default: passages
            summaries.sort(key=lambda s: (s.passage_count, s.name.lower()), reverse=True)

        return summaries

    def search_tags(
        self,
        query: str,
        category: Optional[str] = None,
    ) -> List[TagSummary]:
        """Search tag names and descriptions matching the given keyword."""
        q = query.strip().lower()
        all_tags = self.list_tags(category=category, sort_by="name")
        if not q:
            return all_tags

        matches: List[TagSummary] = []
        for tag in all_tags:
            if q in tag.name.lower() or (tag.description and q in tag.description.lower()):
                matches.append(tag)
        return matches

    def get_tag_stats(self, tag_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve aggregated metrics for a specific tag name."""
        clean_tag = normalize_tag_name(tag_name)
        stats_list = self.db.get_tag_stats(tag_name=clean_tag)
        if not stats_list:
            return None
        return stats_list[0]

    # --- Passage Tagging (Verses & Arbitrary Spans) ---

    def tag_passage(
        self,
        reference: Union[Reference, str],
        tags: Union[str, Sequence[str]],
        category: str = TagCategory.THEMATIC,
        confidence: float = 1.0,
        source: str = "user",
        starred: bool = False,
        notes: Optional[str] = None,
    ) -> List[VerseTagRecord]:
        """Attach one or more semantic tags to an individual verse, span, or chapter.

        Supports multi-resolution passage tagging:
          - Single verse: "John 3:16"
          - Arbitrary verse span: "Romans 8:1-11"
          - Whole chapter: "Psalm 23"
          - Cross-chapter span: "Genesis 1:1 - Genesis 2:3"

        If the reference is a multi-verse passage, automatically links/registers
        the passage in the `spans` table. Automatically normalizes all tag names
        to canonical snake_case.

        Args:
            reference: Citation string or canonical Reference object.
            tags: Tag name, comma-separated string, or list of tag names.
            category: Default category if tag is newly created.
            confidence: Confidence score (0.0 to 1.0).
            source: Provenance source ('user', 'curation', 'llm-gemini').
            starred: Priority star flag.
            notes: Optional explanatory notes.

        Returns:
            List of created or updated VerseTagRecord objects.
        """
        ref = parse_reference(reference) if isinstance(reference, str) else reference

        raw_tag_names: List[str] = []
        if isinstance(tags, str):
            # Split comma-separated string if provided
            parts = [t.strip() for t in tags.split(",") if t.strip()]
            raw_tag_names.extend(parts)
        else:
            for t in tags:
                clean = str(t).strip()
                if clean:
                    raw_tag_names.append(clean)

        if not raw_tag_names:
            raise ValueError("At least one tag name must be provided.")

        tag_names = [normalize_tag_name(t) for t in raw_tag_names]

        results: List[VerseTagRecord] = []
        for tag_name in tag_names:
            vt_rec = self.db.tag_reference(
                reference=ref,
                tag_name=tag_name,
                category=category,
                confidence=confidence,
                source=source,
                starred=starred,
                notes=notes,
            )
            results.append(vt_rec)

        return results

    def untag_passage(
        self,
        reference: Union[Reference, str],
        tag_name: str,
    ) -> int:
        """Remove a specific tag from a passage citation.

        Returns the number of removed association rows.
        """
        clean_tag = normalize_tag_name(tag_name)
        return self.db.untag_reference(reference, clean_tag)

    def get_tags_for_passage(
        self,
        reference: Union[Reference, str],
        exact_only: bool = False,
    ) -> List[VerseTagRecord]:
        """Retrieve all tags associated with or overlapping the given passage.

        Args:
            reference: Citation string or Reference object.
            exact_only: If True, only returns tags assigned to this exact passage boundary.
                       If False, returns all tags whose range overlaps this passage.

        Returns:
            List of VerseTagRecord objects.
        """
        return self.db.get_tags_for_reference(reference, exact_only=exact_only)

    def get_passages_for_tag(
        self,
        tag_name: str,
        translation_id: str = "ESV",
        starred_only: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
        hydrate_verses: bool = True,
    ) -> List[TaggedPassage]:
        """Retrieve passages associated with a tag, hydrated with scripture text.

        Args:
            tag_name: Tag name to inspect.
            translation_id: Bible translation ID for verse text hydration (default 'ESV' with WEB fallback).
            starred_only: Only return starred passages.
            limit: Maximum passages to return.
            offset: Pagination offset.
            hydrate_verses: If True, queries the verses table and populates VerseRecords.

        Returns:
            List of TaggedPassage records.
        """
        clean_tag = normalize_tag_name(tag_name)
        records = self.db.get_references_for_tag(clean_tag, starred_only=starred_only)
        if offset > 0:
            records = records[offset:]
        if limit is not None:
            records = records[:limit]

        results: List[TaggedPassage] = []
        for r in records:
            ref = parse_reference(r.human_ref)
            verses: List[VerseRecord] = []
            if hydrate_verses:
                verses, _, _ = self.db.get_verses_with_fallback(
                    ref, translation_id=translation_id, fallback_id="WEB"
                )

            results.append(
                TaggedPassage(
                    id=r.id or 0,
                    tag_id=r.tag_id,
                    tag_name=r.tag_name,
                    reference=ref,
                    human_ref=r.human_ref,
                    confidence=r.confidence,
                    source=r.source,
                    starred=r.starred,
                    notes=r.notes,
                    span_id=r.span_id,
                    created_at=r.created_at,
                    verses=verses,
                )
            )

        return results

    # --- Seed & Taxonomy Management ---

    def seed_canonical_taxonomies(self) -> int:
        """Seed predefined theological and redemptive-historical tags into the database.

        Returns the number of tags created or updated.
        """
        count = 0
        for group, tags in CANONICAL_TAXONOMY.items():
            for name, cat, desc in tags:
                self.add_tag(name=name, category=cat, description=desc)
                count += 1
        return count

    def export_taxonomy(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Export tags and their metadata as a list of dictionaries."""
        tags = self.list_tags(category=category, sort_by="name")
        return [t.to_dict() for t in tags]

    def import_taxonomy(self, tags: Sequence[Dict[str, Any]]) -> int:
        """Import tag definitions from a sequence of tag dictionaries.

        Returns count of tags imported.
        """
        count = 0
        for t in tags:
            name = t.get("name")
            if not name:
                continue
            cat = t.get("category", TagCategory.THEMATIC)
            desc = t.get("description")
            self.add_tag(name, category=cat, description=desc)
            count += 1
        return count

    # --- Aggregation Queries & Analytical Engine (Task 3.4) ---

    def get_topic_density_per_book(
        self,
        tag_name: Optional[str] = None,
        category: Optional[str] = None,
        testament: Optional[str] = None,
        min_passages: int = 0,
    ) -> List[BookTopicDensity]:
        """Compute topic/tag distribution and density across the 66 canonical books.

        Args:
            tag_name: Optional tag name to filter distribution (case-insensitive).
            category: Optional tag category filter (e.g. 'theological', 'thematic').
            testament: Optional testament filter ('OT' or 'NT').
            min_passages: Minimum passage count threshold to include book in results.

        Returns:
            List of BookTopicDensity records ordered by canonical book order.
        """
        # Fetch canonical books
        cur = self.db.conn.cursor()
        book_query = "SELECT id, name, osis, testament, total_chapters, canonical_order FROM books"
        book_params: List[Any] = []
        if testament:
            t_clean = testament.strip().upper()
            if t_clean in ("OT", "OLD"):
                t_clean = "OT"
            elif t_clean in ("NT", "NEW"):
                t_clean = "NT"
            book_query += " WHERE testament = ?"
            book_params.append(t_clean)
        book_query += " ORDER BY canonical_order ASC"
        cur.execute(book_query, book_params)
        book_rows = cur.fetchall()

        # Query tag associations
        # Each verse_tags row has start_canonical_id, where (start_canonical_id / 1000000) corresponds to book_id.
        vt_query = """
            SELECT
                (vt.start_canonical_id / 1000000) AS b_id,
                vt.start_canonical_id,
                vt.end_canonical_id,
                t.name AS tag_name,
                vt.starred,
                vt.id AS vt_id
            FROM verse_tags vt
            JOIN tags t ON t.id = vt.tag_id
            WHERE 1=1
        """
        vt_params: List[Any] = []
        if tag_name:
            vt_query += " AND t.name = ? COLLATE NOCASE"
            vt_params.append(normalize_tag_name(tag_name))
        if category:
            vt_query += " AND t.category = ? COLLATE NOCASE"
            vt_params.append(category.strip().lower())

        cur.execute(vt_query, vt_params)
        vt_rows = cur.fetchall()
        cur.close()

        # Aggregate metrics per book
        book_stats: Dict[int, Dict[str, Any]] = {}
        for r in vt_rows:
            b_id = int(r["b_id"])
            t_name = str(r["tag_name"])
            is_starred = bool(r["starred"])
            passage_key = (int(r["start_canonical_id"]), int(r["end_canonical_id"]))

            if b_id not in book_stats:
                book_stats[b_id] = {
                    "passages": set(),
                    "starred_passages": set(),
                    "tags": set(),
                    "tag_counts": {},
                }
            book_stats[b_id]["passages"].add(passage_key)
            if is_starred:
                book_stats[b_id]["starred_passages"].add(passage_key)
            book_stats[b_id]["tags"].add(t_name)
            book_stats[b_id]["tag_counts"][t_name] = (
                book_stats[b_id]["tag_counts"].get(t_name, 0) + 1
            )

        results: List[BookTopicDensity] = []
        for b in book_rows:
            b_id = b["id"]
            stats = book_stats.get(
                b_id,
                {"passages": set(), "starred_passages": set(), "tags": set(), "tag_counts": {}},
            )
            p_count = len(stats["passages"])
            if p_count < min_passages:
                continue

            results.append(
                BookTopicDensity(
                    book_id=b_id,
                    book_name=b["name"],
                    osis=b["osis"],
                    testament=b["testament"],
                    total_chapters=b["total_chapters"],
                    passage_count=p_count,
                    starred_count=len(stats["starred_passages"]),
                    distinct_tags=len(stats["tags"]),
                    tag_counts=stats["tag_counts"],
                )
            )

        return results

    def get_topic_density_per_chapter(
        self,
        book: Union[Book, str, int],
        tag_name: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[ChapterTopicDensity]:
        """Compute chapter-by-chapter topic/tag distribution and density within a book.

        Args:
            book: Canonical Book instance, OSIS identifier, name, or book number.
            tag_name: Optional tag name to filter distribution (case-insensitive).
            category: Optional tag category filter (e.g. 'theological', 'thematic').

        Returns:
            List of ChapterTopicDensity records ordered by chapter number (1 to total_chapters).
        """
        b = get_book(book)
        cur = self.db.conn.cursor()

        vt_query = """
            SELECT
                ((vt.start_canonical_id % 1000000) / 1000) AS ch,
                t.name AS tag_name,
                vt.starred,
                vt.id AS vt_id
            FROM verse_tags vt
            JOIN tags t ON t.id = vt.tag_id
            WHERE (vt.start_canonical_id / 1000000) = ?
        """
        vt_params: List[Any] = [b.number]
        if tag_name:
            vt_query += " AND t.name = ? COLLATE NOCASE"
            vt_params.append(tag_name.strip())
        if category:
            vt_query += " AND t.category = ? COLLATE NOCASE"
            vt_params.append(category.strip().lower())

        cur.execute(vt_query, vt_params)
        vt_rows = cur.fetchall()

        chapter_stats: Dict[int, Dict[str, Any]] = {}
        for ch in range(1, b.total_chapters + 1):
            chapter_stats[ch] = {
                "passages": set(),
                "starred_passages": set(),
                "tags": set(),
                "tag_counts": {},
            }

        for r in vt_rows:
            ch_num = int(r[0])
            t_name = r[1]
            starred = bool(r[2])
            vt_id = r[3]

            if 1 <= ch_num <= b.total_chapters:
                st = chapter_stats[ch_num]
                st["passages"].add(vt_id)
                if starred:
                    st["starred_passages"].add(vt_id)
                st["tags"].add(t_name)
                st["tag_counts"][t_name] = st["tag_counts"].get(t_name, 0) + 1

        results: List[ChapterTopicDensity] = []
        for ch in range(1, b.total_chapters + 1):
            st = chapter_stats[ch]
            results.append(
                ChapterTopicDensity(
                    book_id=b.number,
                    book_name=b.name,
                    osis=b.osis,
                    chapter=ch,
                    passage_count=len(st["passages"]),
                    starred_count=len(st["starred_passages"]),
                    distinct_tags=len(st["tags"]),
                    tag_counts=st["tag_counts"],
                )
            )

        return results

    def get_tag_co_occurrences(
        self,
        tags: Optional[Sequence[str]] = None,
        category: Optional[str] = None,
        min_co_occurrences: int = 1,
    ) -> TagCoOccurrenceMatrix:
        """Compute co-occurrence frequencies and similarity metrics between pairs of tags.

        Two tags co-occur when they are attached to overlapping or identical passage boundaries.

        Args:
            tags: Optional list of tag names to restrict the matrix analysis.
            category: Optional category filter for tags.
            min_co_occurrences: Minimum shared passages to include in pair metrics.

        Returns:
            TagCoOccurrenceMatrix containing matrix grid and pairwise similarity stats.
        """
        cur = self.db.conn.cursor()

        # Step 1: Select relevant tags and their individual passage counts
        tag_query = """
            SELECT t.id, t.name, t.category, COUNT(vt.id) as passage_count
            FROM tags t
            LEFT JOIN verse_tags vt ON vt.tag_id = t.id
            WHERE 1=1
        """
        tag_params: List[Any] = []
        if tags:
            clean_tags = [normalize_tag_name(t) for t in tags if str(t).strip()]
            if clean_tags:
                placeholders = ",".join("?" for _ in clean_tags)
                tag_query += f" AND t.name IN ({placeholders}) COLLATE NOCASE"
                tag_params.extend(clean_tags)
        if category:
            tag_query += " AND t.category = ? COLLATE NOCASE"
            tag_params.append(category.strip().lower())

        tag_query += " GROUP BY t.id ORDER BY t.name ASC"
        cur.execute(tag_query, tag_params)
        tag_rows = cur.fetchall()

        tag_meta: Dict[int, Dict[str, Any]] = {
            r["id"]: {
                "name": r["name"],
                "category": r["category"],
                "count": r["passage_count"],
            }
            for r in tag_rows
        }
        tag_id_by_name: Dict[str, int] = {
            r["name"].lower(): r["id"] for r in tag_rows
        }
        ordered_tag_names = [r["name"] for r in tag_rows]

        # Step 2: Query overlapping verse_tags associations
        # Two associations overlap if: vt1.start_canonical_id <= vt2.end_canonical_id
        #                         AND vt1.end_canonical_id >= vt2.start_canonical_id
        overlap_query = """
            SELECT
                vt1.tag_id AS tag_a_id,
                vt2.tag_id AS tag_b_id,
                COUNT(DISTINCT vt1.id || '-' || vt2.id) AS shared_count
            FROM verse_tags vt1
            JOIN verse_tags vt2 ON vt1.tag_id < vt2.tag_id
            WHERE vt1.start_canonical_id <= vt2.end_canonical_id
              AND vt1.end_canonical_id >= vt2.start_canonical_id
        """
        overlap_params: List[Any] = []
        if tag_meta:
            id_placeholders = ",".join("?" for _ in tag_meta.keys())
            overlap_query += f" AND vt1.tag_id IN ({id_placeholders}) AND vt2.tag_id IN ({id_placeholders})"
            overlap_params.extend(tag_meta.keys())
            overlap_params.extend(tag_meta.keys())

        overlap_query += " GROUP BY vt1.tag_id, vt2.tag_id"
        cur.execute(overlap_query, overlap_params)
        overlap_rows = cur.fetchall()
        cur.close()

        # Step 3: Populate matrix grid
        matrix: Dict[str, Dict[str, int]] = {
            t_name: {other: 0 for other in ordered_tag_names}
            for t_name in ordered_tag_names
        }

        # Diagonal entries = total passages for that tag
        for t_info in tag_meta.values():
            name = t_info["name"]
            if name in matrix:
                matrix[name][name] = t_info["count"]

        pair_metrics: List[TagCoOccurrence] = []
        for r in overlap_rows:
            id_a = r["tag_a_id"]
            id_b = r["tag_b_id"]
            if id_a not in tag_meta or id_b not in tag_meta:
                continue

            name_a = tag_meta[id_a]["name"]
            name_b = tag_meta[id_b]["name"]
            shared = int(r["shared_count"])

            matrix[name_a][name_b] = shared
            matrix[name_b][name_a] = shared

            if shared >= min_co_occurrences:
                count_a = tag_meta[id_a]["count"]
                count_b = tag_meta[id_b]["count"]
                union_count = (count_a + count_b) - shared
                jaccard = shared / union_count if union_count > 0 else 0.0
                dice = (2.0 * shared) / (count_a + count_b) if (count_a + count_b) > 0 else 0.0

                pair_metrics.append(
                    TagCoOccurrence(
                        tag_a=name_a,
                        tag_b=name_b,
                        shared_passages=shared,
                        jaccard_similarity=jaccard,
                        dice_coefficient=dice,
                        category_a=tag_meta[id_a]["category"],
                        category_b=tag_meta[id_b]["category"],
                    )
                )

        # Sort pairs by shared passages descending, then jaccard descending
        pair_metrics.sort(key=lambda p: (p.shared_passages, p.jaccard_similarity), reverse=True)

        return TagCoOccurrenceMatrix(
            tags=ordered_tag_names,
            matrix=matrix,
            pair_metrics=pair_metrics,
        )

    def score_verse_relevance(
        self,
        tags: Union[str, Sequence[str]],
        translation_id: str = "ESV",
        starred_only: bool = False,
        min_score: float = 0.0,
        limit: Optional[int] = None,
        hydrate_verses: bool = True,
    ) -> List[VerseRelevance]:
        """Compute multi-tag relevance scoring and ranking across scripture passages.

        Scoring formula combines:
          - Tag coverage / match ratio: (matched_tags / total_query_tags)
          - Starred status boost (+25%)
          - Association confidence weighted sum
          - Specificity bonus: rewards exact / tight passage boundaries

        Args:
            tags: Comma-separated string or list of tag names to query.
            translation_id: Translation ID for verse text hydration.
            starred_only: Only return passages marked starred.
            min_score: Minimum relevance score threshold (0.0 to 1.0).
            limit: Maximum ranked passages to return.
            hydrate_verses: If True, populates VerseRecord texts.

        Returns:
            List of VerseRelevance records sorted in descending order of relevance.
        """
        tag_list: List[str] = []
        if isinstance(tags, str):
            parts = [t.strip() for t in tags.split(",") if t.strip()]
            tag_list.extend(parts)
        else:
            for t in tags:
                clean = t.strip()
                if clean:
                    tag_list.append(clean)

        if not tag_list:
            raise ValueError("At least one tag name must be provided for relevance scoring.")

        # Resolve tag records
        resolved_tags: List[TagRecord] = []
        for t_name in tag_list:
            t_rec = self.get_tag(t_name)
            if t_rec:
                resolved_tags.append(t_rec)

        if not resolved_tags:
            return []

        tag_ids = [t.id for t in resolved_tags if t.id is not None]
        tag_id_to_name = {t.id: t.name for t in resolved_tags if t.id is not None}
        total_query_count = len(tag_list)

        cur = self.db.conn.cursor()
        placeholders = ",".join("?" for _ in tag_ids)
        query = f"""
            SELECT
                vt.start_canonical_id,
                vt.end_canonical_id,
                vt.human_ref,
                vt.starred,
                vt.confidence,
                vt.tag_id
            FROM verse_tags vt
            WHERE vt.tag_id IN ({placeholders})
        """
        params: List[Any] = list(tag_ids)
        if starred_only:
            query += " AND vt.starred = 1"

        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()

        # Group matched associations by canonical passage range
        passages: Dict[Tuple[int, int], Dict[str, Any]] = {}
        for r in rows:
            key = (int(r["start_canonical_id"]), int(r["end_canonical_id"]))
            t_id = int(r["tag_id"])
            t_name = tag_id_to_name.get(t_id, "")
            is_starred = bool(r["starred"])
            conf = float(r["confidence"])

            if key not in passages:
                passages[key] = {
                    "human_ref": r["human_ref"],
                    "starred": is_starred,
                    "matched_tags": set(),
                    "confidences": [],
                }

            if is_starred:
                passages[key]["starred"] = True
            if t_name:
                passages[key]["matched_tags"].add(t_name)
            passages[key]["confidences"].append(conf)

        ranked: List[VerseRelevance] = []
        for (start_id, end_id), data in passages.items():
            ref = parse_reference(data["human_ref"])
            matched = sorted(list(data["matched_tags"]))
            match_count = len(matched)
            match_ratio = match_count / total_query_count
            max_conf = max(data["confidences"]) if data["confidences"] else 1.0
            avg_conf = sum(data["confidences"]) / len(data["confidences"]) if data["confidences"] else 1.0

            # Base score: match ratio * average confidence (weight 0.60)
            score = match_ratio * avg_conf * 0.60

            # Exact multi-tag bonus: if all requested tags match (weight 0.20)
            if match_count == total_query_count:
                score += 0.20
            else:
                score += (match_ratio * 0.15)

            # Starred boost (+0.10)
            if data["starred"]:
                score += 0.10

            # Specificity bonus: clamp range length (shorter passages get up to +0.10)
            span_len = max(1, (end_id - start_id) + 1)
            specificity_bonus = max(0.0, 0.10 - min(0.08, (span_len - 1) * 0.01))
            score += specificity_bonus

            # Clamp final score to 1.0
            final_score = min(1.0, score)
            if final_score < min_score:
                continue

            verses: List[VerseRecord] = []
            text = ""
            if hydrate_verses:
                verses, _, _ = self.db.get_verses_with_fallback(
                    ref, translation_id=translation_id, fallback_id="WEB"
                )
                text = " ".join(v.text for v in verses)

            ranked.append(
                VerseRelevance(
                    reference=ref,
                    human_ref=data["human_ref"],
                    osis=ref.to_osis(),
                    score=final_score,
                    matched_tags=matched,
                    total_requested_tags=total_query_count,
                    match_ratio=match_ratio,
                    starred=data["starred"],
                    highest_confidence=max_conf,
                    text=text,
                    verses=verses,
                )
            )

        # Sort descending by score, then starred, then match_ratio
        ranked.sort(
            key=lambda r: (r.score, r.starred, r.match_ratio, -len(r.verses)),
            reverse=True,
        )

        if limit is not None:
            ranked = ranked[:limit]

        return ranked
