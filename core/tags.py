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


# Predefined theological & redemptive-historical taxonomy presets (TGC-aligned)
CANONICAL_TAXONOMY: Dict[str, List[Tuple[str, str, str]]] = {
    # (tag_name, category, description)
    "redemptive_historical": [
        ("Creation", TagCategory.HISTORICAL, "The original good creation of the heavens and earth by God."),
        ("Fall", TagCategory.THEOLOGICAL, "The rebellion of humanity into sin and cosmic brokenness."),
        ("Covenant", TagCategory.THEOLOGICAL, "God's binding oaths and promises with Adam, Noah, Abraham, Moses, David, and Christ."),
        ("Exodus", TagCategory.HISTORICAL, "God delivering His people out of bondage through signs, blood, and the Red Sea."),
        ("Temple", TagCategory.TYPOLOGY, "The dwelling place of God with man, culminating in Christ and the church."),
        ("Kingship", TagCategory.THEOLOGICAL, "God's sovereignty exercised through the Davidic line, realized in Christ."),
        ("Exile", TagCategory.HISTORICAL, "Covenant judgment, dispersion, and the longing for restoration."),
        ("Restoration", TagCategory.PROPHECY, "The return from exile, spiritual renewal, and the new creation."),
        ("Redemption", TagCategory.THEOLOGICAL, "Deliverance from sin and death purchased by the blood of Christ."),
        ("New Creation", TagCategory.PROPHECY, "The final renewal of all things in the New Jerusalem."),
    ],
    "systematic_theology": [
        ("Trinity", TagCategory.THEOLOGICAL, "One God eternally existing in three co-equal persons: Father, Son, and Holy Spirit."),
        ("Christology", TagCategory.THEOLOGICAL, "The person and dual divine-human nature of Jesus Christ."),
        ("Pneumatology", TagCategory.THEOLOGICAL, "The person, work, gifts, and fruit of the Holy Spirit."),
        ("Holy Spirit", TagCategory.THEOLOGICAL, "The third person of the Trinity indwelling, empowering, and sanctifying believers."),
        ("Justification", TagCategory.THEOLOGICAL, "God's forensic declaration of righteousness by grace alone through faith alone."),
        ("Sanctification", TagCategory.THEOLOGICAL, "The progressive transformation of the believer into the likeness of Christ."),
        ("Sovereign Grace", TagCategory.THEOLOGICAL, "God's unconditional love and unmerited favor in election and salvation."),
        ("Resurrection", TagCategory.THEOLOGICAL, "The bodily rising of Jesus Christ from the dead and future resurrection of the saints."),
        ("Atonement", TagCategory.THEOLOGICAL, "Christ's penal substitutionary sacrifice satisfying divine justice."),
    ],
    "practical_christian_living": [
        ("Prayer", TagCategory.THEMATIC, "Communion with God, petitions, thanksgiving, and intercession."),
        ("Wisdom", TagCategory.THEMATIC, "Skill in godly living according to God's created order and fear of the Lord."),
        ("Suffering", TagCategory.THEMATIC, "Trials, affliction, endurance, and God's sovereign comfort in hardship."),
        ("Joy", TagCategory.THEMATIC, "Deep gladness rooted in God's character and salvation regardless of circumstances."),
        ("Faith", TagCategory.THEMATIC, "Trust, reliance, and assurance in God's character and revealed promises."),
        ("Love", TagCategory.THEMATIC, "Self-sacrificial devotion modeled after God's love in Christ."),
    ],
}


# ==============================================================================
# Data Records & DTOs
# ==============================================================================


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
        """Register a new semantic tag definition or update its metadata."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Tag name cannot be empty.")
        clean_cat = category.strip().lower()
        return self.db.add_tag(clean_name, category=clean_cat, description=description)

    def get_tag(self, name: str) -> Optional[TagRecord]:
        """Retrieve tag record by name (case-insensitive)."""
        return self.db.get_tag(name)

    def get_or_create_tag(
        self,
        name: str,
        category: str = TagCategory.THEMATIC,
        description: Optional[str] = None,
    ) -> TagRecord:
        """Retrieve tag by name or create it if absent."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Tag name cannot be empty.")
        return self.db.get_or_create_tag(clean_name, category=category, description=description)

    def delete_tag(self, name: str) -> bool:
        """Delete a tag definition and all its passage associations."""
        return self.db.delete_tag(name)

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
        stats_list = self.db.get_tag_stats(tag_name=tag_name)
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
        the passage in the `spans` table.

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

        tag_names: List[str] = []
        if isinstance(tags, str):
            # Split comma-separated string if provided
            parts = [t.strip() for t in tags.split(",") if t.strip()]
            tag_names.extend(parts)
        else:
            for t in tags:
                clean = t.strip()
                if clean:
                    tag_names.append(clean)

        if not tag_names:
            raise ValueError("At least one tag name must be provided.")

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
        return self.db.untag_reference(reference, tag_name)

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
        translation_id: str = "WEB",
        starred_only: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
        hydrate_verses: bool = True,
    ) -> List[TaggedPassage]:
        """Retrieve passages associated with a tag, hydrated with scripture text.

        Args:
            tag_name: Tag name to inspect.
            translation_id: Bible translation ID for verse text hydration (default 'WEB').
            starred_only: Only return starred passages.
            limit: Maximum passages to return.
            offset: Pagination offset.
            hydrate_verses: If True, queries the verses table and populates VerseRecords.

        Returns:
            List of TaggedPassage records.
        """
        records = self.db.get_references_for_tag(tag_name, starred_only=starred_only)
        if offset > 0:
            records = records[offset:]
        if limit is not None:
            records = records[:limit]

        results: List[TaggedPassage] = []
        for r in records:
            ref = parse_reference(r.human_ref)
            verses: List[VerseRecord] = []
            if hydrate_verses:
                verses = self.db.get_verses_by_reference(ref, translation_id=translation_id)

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
