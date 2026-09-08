"""Cross-Referencing & Scripture Relationship Graph Engine for Bible Engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003):
- Verse-to-verse and passage-to-passage relational connections.
- Canonical relationship edge types:
    * 'quotation' (Direct canonical quote e.g. NT citing OT)
    * 'prophecy_fulfillment' (OT Messianic/eschatological prophecy -> NT fulfillment)
    * 'typology' (OT shadow/pattern -> NT substance in Christ)
    * 'thematic' (Shared theological or redemptive-historical motif)
    * 'allusion' (Literary or verbal echo)
    * 'parallel' (Synoptic Gospel parallel or historical duplicate)
- Bidirectional and directed graph queries with confidence weights and notes.
- Hydrated scripture text retrieval across translations.
- Multi-hop relationship path finding and cross-reference neighbor discovery.
- Curated canonical seed cross-references connecting Old and New Testaments.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from core.db import (
    CrossReferenceRecord,
    Database,
    VerseRecord,
)
from core.reference import (
    Reference,
    parse_reference,
)


class RelationshipType:
    """Standardized relationship edge types between scripture passages."""

    THEMATIC = "thematic"
    PROPHECY_FULFILLMENT = "prophecy_fulfillment"
    TYPOLOGY = "typology"
    QUOTATION = "quotation"
    ALLUSION = "allusion"
    PARALLEL = "parallel"

    ALL: Tuple[str, ...] = (
        THEMATIC,
        PROPHECY_FULFILLMENT,
        TYPOLOGY,
        QUOTATION,
        ALLUSION,
        PARALLEL,
    )

    LABELS: Dict[str, str] = {
        THEMATIC: "Thematic Motif",
        PROPHECY_FULFILLMENT: "Prophecy & Fulfillment",
        TYPOLOGY: "Typology (Shadow & Substance)",
        QUOTATION: "Direct Citation / Quotation",
        ALLUSION: "Scriptural Allusion / Echo",
        PARALLEL: "Parallel Account",
    }

    ICONS: Dict[str, str] = {
        THEMATIC: "🔗",
        PROPHECY_FULFILLMENT: "⚡",
        TYPOLOGY: "🏛",
        QUOTATION: "📜",
        ALLUSION: "✨",
        PARALLEL: "⚖",
    }

    @classmethod
    def is_valid(cls, rel_type: str) -> bool:
        """Check if relationship type is recognized."""
        return rel_type.strip().lower() in cls.ALL

    @classmethod
    def get_label(cls, rel_type: str) -> str:
        """Get human-readable label for relationship type."""
        return cls.LABELS.get(rel_type.strip().lower(), rel_type.capitalize())

    @classmethod
    def get_icon(cls, rel_type: str) -> str:
        """Get decorative icon for relationship type."""
        return cls.ICONS.get(rel_type.strip().lower(), "🔗")


CANONICAL_CROSS_REFERENCES: List[Tuple[str, str, str, float, str]] = [
    # 1. The Seed of the Woman (Protoevangelium)
    (
        "Genesis 3:15",
        "Galatians 4:4-5",
        RelationshipType.PROPHECY_FULFILLMENT,
        1.0,
        "The Protoevangelium: God promises the Seed of the woman will crush the serpent's head, fulfilled in the incarnation.",
    ),
    (
        "Genesis 3:15",
        "Romans 16:20",
        RelationshipType.PROPHECY_FULFILLMENT,
        0.95,
        "The God of peace will soon crush Satan under your feet.",
    ),
    (
        "Genesis 3:15",
        "Revelation 12:9-10",
        RelationshipType.TYPOLOGY,
        0.9,
        "The ancient serpent identified and overthrown by the blood of the Lamb.",
    ),

    # 2. The Abrahamic Covenant & Universal Blessing
    (
        "Genesis 12:1-3",
        "Galatians 3:8-9",
        RelationshipType.QUOTATION,
        1.0,
        "Scripture, foreseeing that God would justify the Gentiles by faith, preached the gospel beforehand to Abraham: 'In you shall all nations be blessed.'",
    ),
    (
        "Genesis 12:1-3",
        "Galatians 3:16",
        RelationshipType.THEMATIC,
        0.95,
        "The promises were spoken to Abraham and to his offspring, referring not to many, but to one: Christ.",
    ),
    (
        "Genesis 15:6",
        "Romans 4:3",
        RelationshipType.QUOTATION,
        1.0,
        "Abraham believed God, and it was counted to him as righteousness (sola fide foundation).",
    ),
    (
        "Genesis 15:6",
        "Galatians 3:6",
        RelationshipType.QUOTATION,
        1.0,
        "Paul cites Abraham's belief as the paradigm for justification by faith.",
    ),

    # 3. Isaac & The Akedah (Sacrifice on Mount Moriah)
    (
        "Genesis 22:1-14",
        "John 3:16",
        RelationshipType.TYPOLOGY,
        0.95,
        "The father offering his beloved and only son on the mountain of the Lord, foreshadowing the Father giving His only begotten Son.",
    ),
    (
        "Genesis 22:8",
        "John 1:29",
        RelationshipType.PROPHECY_FULFILLMENT,
        1.0,
        "'God will provide for himself the lamb for a burnt offering' fulfilled in 'Behold, the Lamb of God who takes away the sin of the world!'",
    ),
    (
        "Genesis 22:10-18",
        "Hebrews 11:17-19",
        RelationshipType.TYPOLOGY,
        0.95,
        "Abraham considered that God was able even to raise him from the dead, from which figuratively speaking he did receive him back.",
    ),

    # 4. Melchizedek
    (
        "Genesis 14:18-20",
        "Psalm 110:4",
        RelationshipType.PROPHECY_FULFILLMENT,
        1.0,
        "The Lord has sworn: 'You are a priest forever after the order of Melchizedek.'",
    ),
    (
        "Psalm 110:4",
        "Hebrews 7:1-17",
        RelationshipType.TYPOLOGY,
        1.0,
        "Christ's eternal royal priesthood surpassing the Levitical order based on the power of an indestructible life.",
    ),

    # 5. Passover & The Exodus
    (
        "Exodus 12:1-13",
        "1 Corinthians 5:7",
        RelationshipType.TYPOLOGY,
        1.0,
        "Christ our Passover lamb has been sacrificed for us; cleanse out the old leaven.",
    ),
    (
        "Exodus 12:46",
        "John 19:36",
        RelationshipType.QUOTATION,
        1.0,
        "'Not one of his bones shall be broken' fulfilled at the crucifixion.",
    ),

    # 6. The Bronze Serpent
    (
        "Numbers 21:8-9",
        "John 3:14-15",
        RelationshipType.TYPOLOGY,
        1.0,
        "As Moses lifted up the serpent in the wilderness, so must the Son of Man be lifted up, that whoever believes in him may have eternal life.",
    ),

    # 7. The Prophet Like Moses
    (
        "Deuteronomy 18:15-19",
        "Acts 3:22-23",
        RelationshipType.QUOTATION,
        1.0,
        "Peter identifies Jesus as the Prophet like Moses raised up from among the brothers.",
    ),
    (
        "Deuteronomy 18:15-19",
        "John 1:45",
        RelationshipType.PROPHECY_FULFILLMENT,
        0.9,
        "'We have found him of whom Moses in the Law and also the prophets wrote, Jesus of Nazareth.'",
    ),

    # 8. The Davidic Covenant
    (
        "2 Samuel 7:12-16",
        "Luke 1:32-33",
        RelationshipType.PROPHECY_FULFILLMENT,
        1.0,
        "The throne of David established forever, fulfilled in Jesus who will reign over the house of Jacob forever.",
    ),
    (
        "2 Samuel 7:14",
        "Hebrews 1:5",
        RelationshipType.QUOTATION,
        1.0,
        "'I will be to him a father, and he shall be to me a son' applied directly to the exalted Christ.",
    ),

    # 9. The Suffering and Exaltation in the Psalms
    (
        "Psalm 2:7",
        "Acts 13:33",
        RelationshipType.QUOTATION,
        1.0,
        "'You are my Son, today I have begotten you' fulfilled in the resurrection of Jesus.",
    ),
    (
        "Psalm 2:7",
        "Hebrews 1:5",
        RelationshipType.QUOTATION,
        1.0,
        "The eternal divine sonship of Christ demonstrated above angels.",
    ),
    (
        "Psalm 16:10",
        "Acts 2:27-31",
        RelationshipType.QUOTATION,
        1.0,
        "Peter's Pentecost sermon: David foresaw the resurrection of Christ, that his soul was not abandoned to Hades nor did his flesh see corruption.",
    ),
    (
        "Psalm 22:1",
        "Matthew 27:46",
        RelationshipType.QUOTATION,
        1.0,
        "'My God, my God, why have you forsaken me?' cried out by Jesus on the cross.",
    ),
    (
        "Psalm 22:18",
        "John 19:24",
        RelationshipType.QUOTATION,
        1.0,
        "'They divided my garments among them, and for my clothing they cast lots.'",
    ),
    (
        "Psalm 110:1",
        "Matthew 22:42-45",
        RelationshipType.QUOTATION,
        1.0,
        "Jesus demonstrates to the Pharisees that David calls the Messiah Lord: 'The Lord said to my Lord, Sit at my right hand.'",
    ),
    (
        "Psalm 110:1",
        "Acts 2:34-35",
        RelationshipType.QUOTATION,
        1.0,
        "Peter proclaims Christ's ascension and session at the right hand of God.",
    ),
    (
        "Psalm 118:22",
        "Matthew 21:42",
        RelationshipType.QUOTATION,
        1.0,
        "'The stone that the builders rejected has become the cornerstone.'",
    ),
    (
        "Psalm 118:22",
        "1 Peter 2:7",
        RelationshipType.QUOTATION,
        1.0,
        "Peter expounds Christ as the precious cornerstone chosen by God but rejected by men.",
    ),

    # 10. The Suffering Servant (Isaiah 53)
    (
        "Isaiah 53:3",
        "John 1:11",
        RelationshipType.THEMATIC,
        0.9,
        "Despised and rejected by men; he came to his own, and his own people did not receive him.",
    ),
    (
        "Isaiah 53:4",
        "Matthew 8:17",
        RelationshipType.QUOTATION,
        1.0,
        "He took our illnesses and bore our diseases in his healing ministry.",
    ),
    (
        "Isaiah 53:5",
        "1 Peter 2:24",
        RelationshipType.QUOTATION,
        1.0,
        "He was pierced for our transgressions, crushed for our iniquities... by his wounds you have been healed.",
    ),
    (
        "Isaiah 53:5",
        "Romans 4:25",
        RelationshipType.THEMATIC,
        0.95,
        "Delivered up for our trespasses and raised for our justification.",
    ),
    (
        "Isaiah 53:7-8",
        "Acts 8:32-35",
        RelationshipType.QUOTATION,
        1.0,
        "Philip explains Isaiah 53 to the Ethiopian eunuch, beginning with this Scripture and telling him the good news about Jesus.",
    ),
    (
        "Isaiah 53:9",
        "1 Peter 2:22",
        RelationshipType.QUOTATION,
        1.0,
        "He committed no sin, neither was deceit found in his mouth, with the rich in his death.",
    ),
    (
        "Isaiah 53:12",
        "Luke 22:37",
        RelationshipType.QUOTATION,
        1.0,
        "Jesus: 'This Scripture must be fulfilled in me: And he was numbered with the transgressors.'",
    ),

    # 11. The Virgin Birth & Emmanuel
    (
        "Isaiah 7:14",
        "Matthew 1:22-23",
        RelationshipType.PROPHECY_FULFILLMENT,
        1.0,
        "The virgin shall conceive and bear a son, and they shall call his name Immanuel (God with us).",
    ),
    (
        "Micah 5:2",
        "Matthew 2:5-6",
        RelationshipType.PROPHECY_FULFILLMENT,
        1.0,
        "The ruler of Israel originating from of old, from ancient days, born in Bethlehem Ephrathah.",
    ),

    # 12. The New Covenant
    (
        "Jeremiah 31:31-34",
        "Luke 22:20",
        RelationshipType.PROPHECY_FULFILLMENT,
        1.0,
        "This cup that is poured out for you is the new covenant in my blood.",
    ),
    (
        "Jeremiah 31:31-34",
        "Hebrews 8:8-12",
        RelationshipType.QUOTATION,
        1.0,
        "The full quotation of Jeremiah's New Covenant, writing God's law on human hearts and remembering sins no more.",
    ),
    (
        "Jeremiah 31:31-34",
        "Hebrews 10:16-17",
        RelationshipType.QUOTATION,
        1.0,
        "The Holy Spirit witnesses the once-for-all sanctification through Christ's offering.",
    ),

    # 13. The Outpouring of the Spirit
    (
        "Joel 2:28-32",
        "Acts 2:16-21",
        RelationshipType.QUOTATION,
        1.0,
        "Peter at Pentecost: 'This is what was uttered through the prophet Joel: In the last days, I will pour out my Spirit on all flesh.'",
    ),

    # 14. Pierced and Looked Upon
    (
        "Zechariah 12:10",
        "John 19:37",
        RelationshipType.QUOTATION,
        1.0,
        "'They will look on him whom they have pierced.'",
    ),
    (
        "Zechariah 12:10",
        "Revelation 1:7",
        RelationshipType.ALLUSION,
        0.95,
        "Behold, he is coming with clouds, and every eye will see him, even those who pierced him.",
    ),

    # 15. The First Adam and the Last Adam
    (
        "Genesis 1:26-27",
        "Colossians 1:15",
        RelationshipType.TYPOLOGY,
        1.0,
        "Man created in the image of God; Christ is the exact image of the invisible God, the firstborn of all creation.",
    ),
    (
        "Genesis 2:7",
        "1 Corinthians 15:45",
        RelationshipType.TYPOLOGY,
        1.0,
        "The first man Adam became a living being; the last Adam became a life-giving spirit.",
    ),
    (
        "Genesis 3:1-6",
        "Romans 5:14-19",
        RelationshipType.TYPOLOGY,
        1.0,
        "Adam was a type of the one to come: through one man's disobedience the many were made sinners, through one man's obedience the many will be made righteous.",
    ),

    # 16. Noah's Ark & Deliverance Through Water
    (
        "Genesis 7:1-23",
        "1 Peter 3:20-21",
        RelationshipType.TYPOLOGY,
        0.95,
        "Eight souls brought safely through water in the ark, corresponding to baptism which now saves you through the resurrection of Christ.",
    ),

    # 17. Jacob's Ladder
    (
        "Genesis 28:12",
        "John 1:51",
        RelationshipType.TYPOLOGY,
        0.95,
        "The ladder set up on earth reaching to heaven with angels ascending and descending, fulfilled in the Son of Man as the sole mediator.",
    ),

    # 18. Joseph: Rejected and Exalted Savior
    (
        "Genesis 45:4-8",
        "Acts 7:9-14",
        RelationshipType.TYPOLOGY,
        0.95,
        "The patriarchs sold Joseph into Egypt out of jealousy, but God was with him to preserve life, prefiguring Christ rejected by his brothers then exalted as Savior.",
    ),

    # 19. The Burning Bush & Divine Name
    (
        "Exodus 3:14",
        "John 8:58",
        RelationshipType.THEMATIC,
        1.0,
        "God reveals his covenant name 'I AM WHO I AM' to Moses; Jesus declares 'Before Abraham was, I AM.'",
    ),

    # 20. The Wilderness Manna (Bread of Life)
    (
        "Exodus 16:4-15",
        "John 6:32-35",
        RelationshipType.TYPOLOGY,
        1.0,
        "The bread from heaven given in the wilderness; Jesus is the true Bread of Life who comes down from heaven and gives life to the world.",
    ),

    # 21. Water from the Struck Rock
    (
        "Exodus 17:6",
        "1 Corinthians 10:4",
        RelationshipType.TYPOLOGY,
        1.0,
        "Moses struck the rock in Horeb to give water; Paul reveals 'they drank from the spiritual Rock that followed them, and the Rock was Christ.'",
    ),

    # 22. The Tabernacle & Holy Dwelling
    (
        "Exodus 25:8-9",
        "John 1:14",
        RelationshipType.TYPOLOGY,
        1.0,
        "'Make me a sanctuary that I may dwell among them' fulfilled when the Word became flesh and tabernacled among us.",
    ),
    (
        "Exodus 40:34-35",
        "Hebrews 9:11-12",
        RelationshipType.TYPOLOGY,
        1.0,
        "The glory filling the earthly tent; Christ entered once for all into the holy places through the greater and more perfect tent not made with hands.",
    ),

    # 23. The High Priesthood of Aaron
    (
        "Exodus 28:1-3",
        "Hebrews 4:14-16",
        RelationshipType.TYPOLOGY,
        1.0,
        "Aaron the high priest with the names of Israel over his heart; Christ our great High Priest who sympathizes with our weaknesses.",
    ),

    # 24. Day of Atonement (Yom Kippur) & Scapegoat
    (
        "Leviticus 16:15-16",
        "Hebrews 9:11-14",
        RelationshipType.TYPOLOGY,
        1.0,
        "The annual blood of goats sprinkled on the mercy seat; Christ offered his own unblemished blood to purify our conscience from dead works.",
    ),

    # 25. Cities of Refuge
    (
        "Numbers 35:11-15",
        "Hebrews 6:18",
        RelationshipType.TYPOLOGY,
        0.95,
        "The six cities of refuge protecting the fugitive from the avenger of blood, typifying our strong encouragement to flee for refuge in Christ.",
    ),

    # 26. Boaz the Kinsman-Redeemer (Goel)
    (
        "Ruth 4:9-10",
        "Galatians 4:4-5",
        RelationshipType.TYPOLOGY,
        0.95,
        "Boaz redeems the lost inheritance and takes the Gentile Ruth as his bride, foreshadowing Christ redeeming those under the law to receive adoption.",
    ),

    # 27. Jonah & The Resurrection on the Third Day
    (
        "Jonah 1:17",
        "Matthew 12:40",
        RelationshipType.TYPOLOGY,
        1.0,
        "Jonah three days and three nights in the belly of the great fish; the Son of Man three days and three nights in the heart of the earth.",
    ),

    # 28. Light to Galilee & The Prince of Peace
    (
        "Isaiah 9:1-2",
        "Matthew 4:14-16",
        RelationshipType.PROPHECY_FULFILLMENT,
        1.0,
        "The people walking in darkness have seen a great light in Galilee of the Gentiles.",
    ),
    (
        "Isaiah 9:6-7",
        "Luke 1:32-33",
        RelationshipType.PROPHECY_FULFILLMENT,
        1.0,
        "To us a child is born, his name Wonderful Counselor, Mighty God; he will reign on the throne of David forever.",
    ),

    # 29. The Root and Branch of Jesse
    (
        "Isaiah 11:1-2",
        "Romans 15:12",
        RelationshipType.PROPHECY_FULFILLMENT,
        1.0,
        "A shoot will come from the stump of Jesse; the root of Jesse will arise to rule the Gentiles, and in him the Gentiles will hope.",
    ),

    # 30. The Precious Cornerstone in Zion
    (
        "Isaiah 28:16",
        "1 Peter 2:6",
        RelationshipType.QUOTATION,
        1.0,
        "Behold, I lay in Zion a stone, a cornerstone chosen and precious, and whoever believes in him will never be put to shame.",
    ),

    # 31. The Righteous Branch
    (
        "Jeremiah 23:5-6",
        "1 Corinthians 1:30",
        RelationshipType.THEMATIC,
        1.0,
        "The Righteous Branch of David: 'The Lord our Righteousness', fulfilled in Christ who became to us righteousness, sanctification, and redemption.",
    ),

    # 32. The Son of Man Coming on the Clouds
    (
        "Daniel 7:13-14",
        "Mark 14:62",
        RelationshipType.PROPHECY_FULFILLMENT,
        1.0,
        "One like a son of man coming with the clouds of heaven given everlasting dominion; Jesus testifies before the high priest: 'You will see the Son of Man seated at the right hand of Power.'",
    ),

    # 33. The Humble King on a Donkey
    (
        "Zechariah 9:9",
        "Matthew 21:4-5",
        RelationshipType.PROPHECY_FULFILLMENT,
        1.0,
        "Rejoice greatly, O daughter of Zion! Behold, your King comes to you, righteous and having salvation, gentle and mounted on a donkey.",
    ),

    # 34. Thirty Pieces of Silver
    (
        "Zechariah 11:12-13",
        "Matthew 27:9-10",
        RelationshipType.PROPHECY_FULFILLMENT,
        1.0,
        "They weighed out thirty pieces of silver, the handsome price at which I was valued, and threw them to the potter in the house of the Lord.",
    ),
]


@dataclass(frozen=True)
class HydratedCrossReference:
    """A cross-reference edge paired with hydrated verse texts and direction."""

    id: Optional[int]
    source_ref: str
    target_ref: str
    relationship_type: str
    weight: float
    notes: Optional[str]
    created_at: Optional[str]
    direction: str  # 'outgoing', 'incoming', 'loop'
    related_ref: str
    source_verses: List[VerseRecord] = field(default_factory=list)
    target_verses: List[VerseRecord] = field(default_factory=list)

    @property
    def related_verses(self) -> List[VerseRecord]:
        """Return the verses for the other end of this cross-reference."""
        return self.target_verses if self.direction == "outgoing" else self.source_verses

    @property
    def relationship_label(self) -> str:
        """Human-friendly label."""
        return RelationshipType.get_label(self.relationship_type)

    @property
    def icon(self) -> str:
        """Decorative icon."""
        return RelationshipType.get_icon(self.relationship_type)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize hydrated cross reference to dictionary."""
        return {
            "id": self.id,
            "source": self.source_ref,
            "target": self.target_ref,
            "related_ref": self.related_ref,
            "direction": self.direction,
            "relationship_type": self.relationship_type,
            "relationship_label": self.relationship_label,
            "icon": self.icon,
            "weight": self.weight,
            "notes": self.notes,
            "created_at": self.created_at,
            "source_text": " ".join(v.text for v in self.source_verses),
            "target_text": " ".join(v.text for v in self.target_verses),
            "related_text": " ".join(v.text for v in self.related_verses),
        }


@dataclass(frozen=True)
class CrossReferenceGraphNode:
    """A node in the cross-reference graph."""

    citation: str
    canonical_start_id: int
    canonical_end_id: int
    degree: int = 0
    outgoing_count: int = 0
    incoming_count: int = 0


@dataclass(frozen=True)
class CrossReferenceSummary:
    """Summary statistics for cross-reference repository."""

    total_edges: int
    by_relationship_type: Dict[str, int]
    testament_connections: Dict[str, int]  # 'OT->NT', 'OT->OT', 'NT->NT', 'NT->OT'
    distinct_sources: int
    distinct_targets: int


class CrossReferenceService:
    """High-level service managing scripture cross-references and graph connections."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def link_passages(
        self,
        source: Union[Reference, str],
        target: Union[Reference, str],
        relationship_type: str = RelationshipType.THEMATIC,
        weight: float = 1.0,
        notes: Optional[str] = None,
    ) -> CrossReferenceRecord:
        """Link two scripture passages with a typed relational edge."""
        s_ref = parse_reference(source) if isinstance(source, str) else source
        t_ref = parse_reference(target) if isinstance(target, str) else target

        rel_type = relationship_type.strip().lower()
        if not RelationshipType.is_valid(rel_type):
            valid_list = ", ".join(RelationshipType.ALL)
            raise ValueError(f"Invalid relationship type '{relationship_type}'. Must be one of: {valid_list}")

        return self.db.add_cross_reference(
            source=s_ref,
            target=t_ref,
            relationship_type=rel_type,
            weight=weight,
            notes=notes,
        )

    def link_passages_batch(
        self,
        edges: Sequence[Tuple[Union[Reference, str], Union[Reference, str], str, float, Optional[str]]],
    ) -> int:
        """Batch link passages inside an atomic database transaction."""
        if not edges:
            return 0

        inserted = 0
        with self.db.transaction():
            for src, tgt, rel, weight, notes in edges:
                self.link_passages(src, tgt, relationship_type=rel, weight=weight, notes=notes)
                inserted += 1
        return inserted

    def unlink_passages(
        self,
        source: Union[Reference, str],
        target: Union[Reference, str],
        relationship_type: Optional[str] = None,
    ) -> int:
        """Remove relationship edge(s) between two citations."""
        s_ref = parse_reference(source) if isinstance(source, str) else source
        t_ref = parse_reference(target) if isinstance(target, str) else target

        s_start = s_ref.canonical_start_id
        s_end = s_ref.canonical_end_id
        t_start = t_ref.canonical_start_id
        t_end = t_ref.canonical_end_id

        cur = self.db.conn.cursor()
        query = """
            DELETE FROM cross_references
            WHERE ((source_start_id <= ? AND source_end_id >= ?) AND (target_start_id <= ? AND target_end_id >= ?))
               OR ((source_start_id <= ? AND source_end_id >= ?) AND (target_start_id <= ? AND target_end_id >= ?))
        """
        params: List[Any] = [s_end, s_start, t_end, t_start, t_end, t_start, s_end, s_start]

        if relationship_type:
            query += " AND relationship_type = ?"
            params.append(relationship_type.strip().lower())

        with self.db.conn:
            cur.execute(query, params)
            deleted = cur.rowcount
        cur.close()
        return deleted

    def delete_edge_by_id(self, edge_id: int) -> bool:
        """Delete an edge by its primary key ID."""
        with self.db.conn:
            cur = self.db.conn.execute("DELETE FROM cross_references WHERE id = ?", (edge_id,))
            return cur.rowcount > 0

    def seed_canonical_cross_references(self) -> int:
        """Seed curated canonical OT/NT cross-references into the database."""
        existing_edges = self.list_all_cross_references(limit=5000)
        existing_keys = {
            (e.source_human_ref, e.target_human_ref, e.relationship_type)
            for e in existing_edges
        }

        to_insert: List[Tuple[Union[Reference, str], Union[Reference, str], str, float, Optional[str]]] = []
        for src, tgt, rel, weight, notes in CANONICAL_CROSS_REFERENCES:
            s_parsed = parse_reference(src).format()
            t_parsed = parse_reference(tgt).format()
            if (s_parsed, t_parsed, rel) not in existing_keys:
                to_insert.append((src, tgt, rel, weight, notes))

        return self.link_passages_batch(to_insert)

    def get_cross_references(
        self,
        reference: Union[Reference, str],
        relationship_type: Optional[str] = None,
        bidirectional: bool = True,
        min_weight: float = 0.0,
    ) -> List[CrossReferenceRecord]:
        """Fetch raw cross-reference records linked to reference."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        records = self.db.get_cross_references(ref, bidirectional=bidirectional)

        filtered: List[CrossReferenceRecord] = []
        for r in records:
            if min_weight > 0.0 and r.weight < min_weight:
                continue
            if relationship_type and r.relationship_type.lower() != relationship_type.strip().lower():
                continue
            filtered.append(r)
        return filtered

    def get_hydrated_cross_references(
        self,
        reference: Union[Reference, str],
        translation_id: str = "WEB",
        relationship_type: Optional[str] = None,
        bidirectional: bool = True,
        min_weight: float = 0.0,
    ) -> List[HydratedCrossReference]:
        """Retrieve cross-references for a citation hydrated with verse texts."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        raw_records = self.get_cross_references(
            ref,
            relationship_type=relationship_type,
            bidirectional=bidirectional,
            min_weight=min_weight,
        )

        q_start = ref.canonical_start_id
        q_end = ref.canonical_end_id

        hydrated_list: List[HydratedCrossReference] = []

        for rec in raw_records:
            is_source = (rec.source_start_id <= q_end and rec.source_end_id >= q_start)
            is_target = (rec.target_start_id <= q_end and rec.target_end_id >= q_start)

            if is_source and is_target:
                direction = "loop"
                related_ref = rec.target_human_ref
            elif is_source:
                direction = "outgoing"
                related_ref = rec.target_human_ref
            else:
                direction = "incoming"
                related_ref = rec.source_human_ref

            # Fetch source verses
            try:
                s_ref = parse_reference(rec.source_human_ref)
                s_verses, _, _ = self.db.get_verses_with_fallback(
                    s_ref, translation_id=translation_id, fallback_id="WEB"
                )
            except Exception:
                s_verses = []

            # Fetch target verses
            try:
                t_ref = parse_reference(rec.target_human_ref)
                t_verses, _, _ = self.db.get_verses_with_fallback(
                    t_ref, translation_id=translation_id, fallback_id="WEB"
                )
            except Exception:
                t_verses = []

            hydrated_list.append(
                HydratedCrossReference(
                    id=rec.id,
                    source_ref=rec.source_human_ref,
                    target_ref=rec.target_human_ref,
                    relationship_type=rec.relationship_type,
                    weight=rec.weight,
                    notes=rec.notes,
                    created_at=rec.created_at,
                    direction=direction,
                    related_ref=related_ref,
                    source_verses=list(s_verses),
                    target_verses=list(t_verses),
                )
            )

        return hydrated_list

    def list_all_cross_references(
        self,
        relationship_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CrossReferenceRecord]:
        """List all stored cross-references with optional relationship type filter."""
        cur = self.db.conn.cursor()
        query = "SELECT * FROM cross_references"
        params: List[Any] = []
        if relationship_type:
            query += " WHERE relationship_type = ?"
            params.append(relationship_type.strip().lower())
        query += " ORDER BY id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()

        return [
            CrossReferenceRecord(
                id=r["id"],
                source_start_id=r["source_start_id"],
                source_end_id=r["source_end_id"],
                source_human_ref=r["source_human_ref"],
                target_start_id=r["target_start_id"],
                target_end_id=r["target_end_id"],
                target_human_ref=r["target_human_ref"],
                relationship_type=r["relationship_type"],
                weight=r["weight"],
                notes=r["notes"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def find_path(
        self,
        start_citation: Union[Reference, str],
        end_citation: Union[Reference, str],
        max_depth: int = 3,
    ) -> Optional[List[CrossReferenceRecord]]:
        """Breadth-first search for a multi-hop cross-reference chain connecting two citations."""
        start_ref = parse_reference(start_citation) if isinstance(start_citation, str) else start_citation
        end_ref = parse_reference(end_citation) if isinstance(end_citation, str) else end_citation

        target_start = end_ref.canonical_start_id
        target_end = end_ref.canonical_end_id

        queue: List[Tuple[Reference, List[CrossReferenceRecord]]] = [(start_ref, [])]
        visited_ranges: Set[Tuple[int, int]] = {(start_ref.canonical_start_id, start_ref.canonical_end_id)}

        while queue:
            curr_ref, path = queue.pop(0)

            if len(path) >= max_depth:
                continue

            edges = self.get_cross_references(curr_ref, bidirectional=True)
            for edge in edges:
                is_source = (edge.source_start_id <= curr_ref.canonical_end_id and edge.source_end_id >= curr_ref.canonical_start_id)
                neighbor_str = edge.target_human_ref if is_source else edge.source_human_ref
                neighbor_ref = parse_reference(neighbor_str)

                if (neighbor_ref.canonical_start_id <= target_end and neighbor_ref.canonical_end_id >= target_start):
                    return path + [edge]

                key = (neighbor_ref.canonical_start_id, neighbor_ref.canonical_end_id)
                if key not in visited_ranges:
                    visited_ranges.add(key)
                    queue.append((neighbor_ref, path + [edge]))

        return None

    def get_summary_statistics(self) -> CrossReferenceSummary:
        """Compute aggregated statistics across the cross-reference graph."""
        cur = self.db.conn.cursor()

        cur.execute("SELECT COUNT(*) AS total FROM cross_references")
        total_edges = int(cur.fetchone()["total"])

        cur.execute(
            """
            SELECT relationship_type, COUNT(*) AS count
            FROM cross_references
            GROUP BY relationship_type
            ORDER BY count DESC
            """
        )
        by_rel = {r["relationship_type"]: int(r["count"]) for r in cur.fetchall()}

        cur.execute(
            """
            SELECT
                CASE
                    WHEN source_start_id < 40000000 AND target_start_id >= 40000000 THEN 'OT->NT'
                    WHEN source_start_id < 40000000 AND target_start_id < 40000000 THEN 'OT->OT'
                    WHEN source_start_id >= 40000000 AND target_start_id >= 40000000 THEN 'NT->NT'
                    ELSE 'NT->OT'
                END AS connection_type,
                COUNT(*) AS count
            FROM cross_references
            GROUP BY connection_type
            """
        )
        testament_counts = {r["connection_type"]: int(r["count"]) for r in cur.fetchall()}

        cur.execute("SELECT COUNT(DISTINCT source_human_ref) AS src_cnt, COUNT(DISTINCT target_human_ref) AS tgt_cnt FROM cross_references")
        row = cur.fetchone()
        distinct_sources = int(row["src_cnt"]) if row else 0
        distinct_targets = int(row["tgt_cnt"]) if row else 0

        cur.close()

        return CrossReferenceSummary(
            total_edges=total_edges,
            by_relationship_type=by_rel,
            testament_connections=testament_counts,
            distinct_sources=distinct_sources,
            distinct_targets=distinct_targets,
        )
