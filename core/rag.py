"""Scripture RAG (Retrieval-Augmented Generation) Engine.

Zero-dependency implementation per ADR-003, ADR-006, ADR-041, ADR-042, and ADR-049:
- Multi-signal hybrid scripture retrieval combining:
  1. Direct canonical scripture reference parsing and boundary resolution.
  2. SQLite FTS5 BM25 full-text keyword search across scripture verses.
  3. Semantic tag intersection and topic relevance scoring.
  4. Phase 7 theological locus, redemptive epoch, and thematic ribbon matching.
  5. Canonical cross-reference expansion and typological arc shadow-to-fulfillment links.
- Multi-signal composite scoring, pericope-level coherence grouping, and deduplication.
- Hermeneutically focused context window assembly (TGC Foundation Documents standard).
- Token budgeting, clean markdown generation, structured JSON serialization,
  and native Google Gemini API prompt payload preparation.
- Optional inquiry answering via zero-dependency Gemini client when configured.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set, Tuple, Union

from core.crossref import CrossReferenceService
from core.db import (
    DEFAULT_DB_PATH,
    Database,
    SearchResult,
    TypologicalArcRecord,
    VerseRecord,
)
from core.esv import (
    DEFAULT_TRANSLATION,
    FALLBACK_TRANSLATION,
)
from core.llm import (
    DEFAULT_GEMINI_MODEL,
    GeminiClient,
    LLMAuthError,
    get_gemini_api_key,
)
from core.pericopes import PericopeService
from core.reference import (
    Reference,
    get_book,
    parse_reference,
)
from core.tags import TaggingService
from core.theology import (
    RedemptiveEpoch,
    TGCTheologyEngine,
    ThematicRibbon,
    TheologicalGuardrails,
    TheologicalLocus,
    get_theology_engine,
)


def _utc_now_iso() -> str:
    """Return current UTC ISO-8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def estimate_tokens(text: str) -> int:
    """Estimate token count for text using the standard ~4 chars per token rule."""
    if not text:
        return 0
    return max(1, len(text) // 4)


# ==============================================================================
# Common English Stop Words for Biblical Query Tokenization
# ==============================================================================

STOP_WORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "explain", "few", "for", "from", "further", "had", "hadn't",
    "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's",
    "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how",
    "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't",
    "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't",
    "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "tell", "show", "give", "list", "describe", "trace",
    "teach", "bible", "scripture", "passage", "passages", "verse", "verses",
    "theme", "themes", "concept", "concepts", "mean", "meaning", "study", "studies",
    "biblical", "theology", "theological", "truth", "truths", "role", "roles",
    "connection", "connections", "relationship", "relation", "tracing",
}

# Thematic ribbon canonical motif keywords for typological arc discovery
RIBBON_MOTIF_WORDS: Dict[ThematicRibbon, List[str]] = {
    ThematicRibbon.TEMPLE_PRESENCE: [
        "temple", "tabernacle", "sanctuary", "dwelling", "tent", "presence",
        "holy of holies", "eden", "new jerusalem",
    ],
    ThematicRibbon.SACRIFICE_ATONEMENT: [
        "atonement", "sacrifice", "passover", "lamb", "blood", "goat", "bull",
        "offering", "propitiation", "mercy seat", "altar",
    ],
    ThematicRibbon.PRIESTHOOD_MEDIATION: [
        "priest", "priesthood", "high priest", "melchizedek", "aaron",
        "levitical", "intercession", "mediator",
    ],
    ThematicRibbon.SEED_OFFSPRING: [
        "seed", "offspring", "son of david", "virgin", "lineage", "promise", "son",
    ],
    ThematicRibbon.COVENANT_GRACE: [
        "covenant", "promise", "grace", "oath", "circumcision", "everlasting covenant",
    ],
    ThematicRibbon.KINGSHIP_REIGN: [
        "king", "kingdom", "throne", "david", "reign", "sovereignty", "scepter",
    ],
    ThematicRibbon.PROPHETIC_WORD: [
        "prophet", "word of the lord", "prophecy", "spoke", "scripture",
    ],
    ThematicRibbon.SABBATH_REST: [
        "sabbath", "rest", "creation rest", "promised land", "cease",
    ],
    ThematicRibbon.EXODUS_DELIVERANCE: [
        "exodus", "deliverance", "redemption", "wilderness", "manna", "rock", "sea",
    ],
    ThematicRibbon.EXILE_PILGRIMAGE: [
        "exile", "strangers", "aliens", "pilgrims", "babylon", "remnant",
    ],
    ThematicRibbon.CITY_OF_GOD: [
        "jerusalem", "zion", "city of god", "new jerusalem", "holy city",
    ],
    ThematicRibbon.BRIDE_UNION: [
        "bride", "bridegroom", "marriage", "wedding", "husband", "wife",
    ],
}


# ==============================================================================
# Query Analysis & Feature Extraction
# ==============================================================================


@dataclass
class RAGQuery:
    """Structured representation of a parsed user inquiry."""

    raw_query: str
    explicit_references: List[Reference] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    detected_tags: List[str] = field(default_factory=list)
    detected_epochs: List[RedemptiveEpoch] = field(default_factory=list)
    detected_loci: List[TheologicalLocus] = field(default_factory=list)
    detected_ribbons: List[ThematicRibbon] = field(default_factory=list)
    typological_keywords: List[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """Return True if no usable tokens or references were found."""
        return (
            not self.explicit_references
            and not self.keywords
            and not self.detected_tags
            and not self.detected_loci
            and not self.detected_ribbons
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize query features to dictionary."""
        return {
            "raw_query": self.raw_query,
            "explicit_references": [r.format() for r in self.explicit_references],
            "keywords": self.keywords,
            "detected_tags": self.detected_tags,
            "detected_epochs": [e.value for e in self.detected_epochs],
            "detected_loci": [l.value for l in self.detected_loci],
            "detected_ribbons": [r.value for r in self.detected_ribbons],
            "typological_keywords": self.typological_keywords,
        }


# Typological keywords to thematic mappings
TYPOLOGICAL_KEYWORD_MAP: Dict[str, List[ThematicRibbon]] = {
    "temple": [ThematicRibbon.TEMPLE_PRESENCE],
    "tabernacle": [ThematicRibbon.TEMPLE_PRESENCE],
    "dwelling": [ThematicRibbon.TEMPLE_PRESENCE],
    "eden": [ThematicRibbon.TEMPLE_PRESENCE],
    "sanctuary": [ThematicRibbon.TEMPLE_PRESENCE],
    "holy of holies": [ThematicRibbon.TEMPLE_PRESENCE],
    "ark": [ThematicRibbon.TEMPLE_PRESENCE, ThematicRibbon.COVENANT_GRACE],
    "atonement": [ThematicRibbon.SACRIFICE_ATONEMENT],
    "sacrifice": [ThematicRibbon.SACRIFICE_ATONEMENT],
    "passover": [ThematicRibbon.SACRIFICE_ATONEMENT, ThematicRibbon.EXODUS_DELIVERANCE],
    "lamb": [ThematicRibbon.SACRIFICE_ATONEMENT],
    "blood": [ThematicRibbon.SACRIFICE_ATONEMENT],
    "scapegoat": [ThematicRibbon.SACRIFICE_ATONEMENT],
    "high priest": [ThematicRibbon.PRIESTHOOD_MEDIATION],
    "priesthood": [ThematicRibbon.PRIESTHOOD_MEDIATION],
    "priest": [ThematicRibbon.PRIESTHOOD_MEDIATION],
    "melchizedek": [ThematicRibbon.PRIESTHOOD_MEDIATION, ThematicRibbon.KINGSHIP_REIGN],
    "seed": [ThematicRibbon.SEED_OFFSPRING],
    "offspring": [ThematicRibbon.SEED_OFFSPRING],
    "son of david": [ThematicRibbon.SEED_OFFSPRING, ThematicRibbon.KINGSHIP_REIGN],
    "covenant": [ThematicRibbon.COVENANT_GRACE],
    "promise": [ThematicRibbon.COVENANT_GRACE],
    "exodus": [ThematicRibbon.EXODUS_DELIVERANCE],
    "deliverance": [ThematicRibbon.EXODUS_DELIVERANCE],
    "redemption": [ThematicRibbon.EXODUS_DELIVERANCE, ThematicRibbon.SACRIFICE_ATONEMENT],
    "sabbath": [ThematicRibbon.SABBATH_REST],
    "rest": [ThematicRibbon.SABBATH_REST],
    "city of god": [ThematicRibbon.CITY_OF_GOD],
    "jerusalem": [ThematicRibbon.CITY_OF_GOD, ThematicRibbon.TEMPLE_PRESENCE],
    "zion": [ThematicRibbon.CITY_OF_GOD],
    "babylon": [ThematicRibbon.CITY_OF_GOD, ThematicRibbon.EXILE_PILGRIMAGE],
    "exile": [ThematicRibbon.EXILE_PILGRIMAGE],
    "wilderness": [ThematicRibbon.EXILE_PILGRIMAGE, ThematicRibbon.EXODUS_DELIVERANCE],
    "bride": [ThematicRibbon.BRIDE_UNION],
    "marriage": [ThematicRibbon.BRIDE_UNION],
    "manna": [ThematicRibbon.EXODUS_DELIVERANCE],
    "serpent": [ThematicRibbon.SEED_OFFSPRING, ThematicRibbon.SACRIFICE_ATONEMENT],
    "bronze serpent": [ThematicRibbon.SACRIFICE_ATONEMENT],
    "justification": [ThematicRibbon.COVENANT_GRACE],
    "resurrection": [ThematicRibbon.KINGSHIP_REIGN],
}


def _extract_references_from_text(text: str) -> List[Reference]:
    """Scan query text for explicit canonical scripture references."""
    found: List[Reference] = []
    seen: Set[str] = set()

    pattern = re.compile(
        r"\b((?:[1-3]\s+)?[A-Za-z]+(?:\s+of\s+[A-Za-z]+)?)\s+(\d+)(?:[:\.](\d+)(?:\s*-\s*(\d+))?)?\b",
        re.IGNORECASE,
    )

    for match in pattern.finditer(text):
        candidate = match.group(0).strip()
        try:
            ref = parse_reference(candidate)
            formatted = ref.format()
            if formatted not in seen:
                seen.add(formatted)
                found.append(ref)
        except Exception:
            continue

    return found


def extract_query_features(query_text: str, db: Database) -> RAGQuery:
    """Analyze natural language query text to extract search terms, references, and theological tags."""
    clean_text = query_text.strip()
    explicit_refs = _extract_references_from_text(clean_text)

    # Word tokenization
    raw_tokens = re.findall(r"[A-Za-z0-9_]+", clean_text.lower())
    keywords: List[str] = [t for t in raw_tokens if len(t) >= 2 and t not in STOP_WORDS]

    # Tag matching: find registered tags in SQLite
    cur = db.conn.cursor()
    cur.execute("SELECT name FROM tags")
    all_db_tags = {r["name"].lower(): r["name"] for r in cur.fetchall()}
    cur.close()

    detected_tags: List[str] = []
    seen_tags: Set[str] = set()

    lower_query = clean_text.lower()
    for tag_lower, tag_canon in all_db_tags.items():
        if tag_lower in lower_query:
            if tag_canon not in seen_tags:
                seen_tags.add(tag_canon)
                detected_tags.append(tag_canon)

    for token in keywords:
        if token in all_db_tags:
            canon = all_db_tags[token]
            if canon not in seen_tags:
                seen_tags.add(canon)
                detected_tags.append(canon)

    # Theological Loci detection
    detected_loci: List[TheologicalLocus] = []
    seen_loci: Set[TheologicalLocus] = set()
    for locus in TheologicalLocus:
        l_name = locus.value.lower()
        if l_name in lower_query:
            if locus not in seen_loci:
                seen_loci.add(locus)
                detected_loci.append(locus)

    loci_synonyms = {
        TheologicalLocus.SOTERIOLOGY: ["justification", "atonement", "salvation", "grace", "faith", "redemption"],
        TheologicalLocus.CHRISTOLOGY: ["jesus", "christ", "incarnation", "messiah", "cross", "resurrection"],
        TheologicalLocus.PNEUMATOLOGY: ["holy spirit", "spirit", "regeneration", "indwelling", "pentecost"],
        TheologicalLocus.BIBLIOLOGY: ["scripture", "word of god", "inerrancy", "canon", "inspiration"],
        TheologicalLocus.ANTHROPOLOGY_HAMARTIOLOGY: ["fall", "sin", "depravity", "image of god", "adam"],
        TheologicalLocus.ECCLESIOLOGY: ["church", "body of christ", "baptism", "communion", "lord's supper"],
        TheologicalLocus.ESCHATOLOGY: ["new jerusalem", "second coming", "parousia", "new creation", "judgment", "consummation"],
        TheologicalLocus.THEOLOGY_PROPER: ["trinity", "sovereignty", "providence", "father", "creator"],
    }
    for locus, syn_list in loci_synonyms.items():
        if locus not in seen_loci:
            if any(s in lower_query for s in syn_list):
                seen_loci.add(locus)
                detected_loci.append(locus)

    # Redemptive Epochs detection
    detected_epochs: List[RedemptiveEpoch] = []
    seen_epochs: Set[RedemptiveEpoch] = set()
    epoch_synonyms = {
        RedemptiveEpoch.CREATION: ["creation", "eden", "beginning", "adam and eve"],
        RedemptiveEpoch.FALL: ["the fall", "fall of man", "original sin"],
        RedemptiveEpoch.PATRIARCHAL_COVENANT: ["abraham", "isaac", "jacob", "patriarchs", "patriarchal"],
        RedemptiveEpoch.EXODUS_WILDERNESS: ["exodus", "wilderness", "moses", "sinai", "law", "tabernacle"],
        RedemptiveEpoch.CONQUEST_JUDGES: ["joshua", "judges", "conquest", "promised land"],
        RedemptiveEpoch.UNITED_MONARCHY: ["david", "solomon", "davidic", "united monarchy", "kingdom of israel"],
        RedemptiveEpoch.DIVIDED_EXILE: ["exile", "babylon", "prophets", "divided kingdom", "dispersion"],
        RedemptiveEpoch.POST_EXILIC_RESTORATION: ["post-exilic", "ezra", "nehemiah", "second temple", "zerubbabel"],
        RedemptiveEpoch.INCARNATION_CLIMAX: ["incarnation", "gospel", "crucifixion", "resurrection of jesus", "ascension"],
        RedemptiveEpoch.APOSTOLIC_CHURCH: ["acts", "apostolic", "early church", "paul", "peter"],
        RedemptiveEpoch.CONSUMMATION: ["consummation", "new heavens", "new earth", "revelation", "new jerusalem"],
    }
    for epoch, syn_list in epoch_synonyms.items():
        if epoch not in seen_epochs:
            if any(s in lower_query for s in syn_list):
                seen_epochs.add(epoch)
                detected_epochs.append(epoch)

    # Thematic Ribbons & Typological keywords
    detected_ribbons: List[ThematicRibbon] = []
    seen_ribbons: Set[ThematicRibbon] = set()
    typological_keywords: List[str] = []

    for kw, ribbons in TYPOLOGICAL_KEYWORD_MAP.items():
        if kw in lower_query:
            typological_keywords.append(kw)
            for r in ribbons:
                if r not in seen_ribbons:
                    seen_ribbons.add(r)
                    detected_ribbons.append(r)

    # Expand typological search terms with canonical motif words from detected ribbons
    for r in detected_ribbons:
        for mw in RIBBON_MOTIF_WORDS.get(r, []):
            if mw not in typological_keywords:
                typological_keywords.append(mw)

    return RAGQuery(
        raw_query=query_text,
        explicit_references=explicit_refs,
        keywords=keywords,
        detected_tags=detected_tags,
        detected_epochs=detected_epochs,
        detected_loci=detected_loci,
        detected_ribbons=detected_ribbons,
        typological_keywords=typological_keywords,
    )


# ==============================================================================
# Retrieved Passage & Context Window Models
# ==============================================================================


@dataclass
class RetrievedPassage:
    """A scripture passage retrieved and enriched for grounded RAG synthesis."""

    reference: str
    human_ref: str
    translation: str
    verses: List[VerseRecord]
    text: str
    score: float
    pericope_title: Optional[str] = None
    storyline_epoch: Optional[str] = None
    theological_loci: List[str] = field(default_factory=list)
    thematic_ribbons: List[str] = field(default_factory=list)
    central_proposition: Optional[str] = None
    christological_fulfillment: Optional[str] = None
    typological_arcs: List[Dict[str, str]] = field(default_factory=list)
    cross_references: List[str] = field(default_factory=list)
    retrieval_reasons: List[str] = field(default_factory=list)
    starred: bool = False
    estimated_tokens: int = 0

    def format_markdown(self, index: Optional[int] = None) -> str:
        """Render passage into an illuminated, hermeneutically annotated markdown block."""
        header_prefix = f"### {index}. " if index is not None else "### "
        lines: List[str] = []

        title_suffix = f" — *{self.pericope_title}*" if self.pericope_title else ""
        lines.append(f"{header_prefix}{self.human_ref} ({self.translation}){title_suffix}")

        meta_parts: List[str] = []
        if self.storyline_epoch:
            meta_parts.append(f"**Epoch**: {self.storyline_epoch}")
        if self.theological_loci:
            meta_parts.append(f"**Loci**: {', '.join(self.theological_loci)}")
        if self.thematic_ribbons:
            meta_parts.append(f"**Themes**: {', '.join(self.thematic_ribbons)}")

        if meta_parts:
            lines.append(" | ".join(meta_parts))

        if self.central_proposition:
            lines.append(f"**Proposition**: *\"{self.central_proposition}\"*")

        lines.append("")
        for v in self.verses:
            lines.append(f"> [{v.verse}] {v.text}")
        lines.append("")

        if self.typological_arcs:
            lines.append("**Typological Connections**:")
            for arc in self.typological_arcs:
                type_name = arc.get("type_human_ref", "")
                antitype = arc.get("antitype_human_ref", "")
                correspondence = arc.get("theological_correspondence", "")
                warrant = arc.get("warrant", "")
                line = f"- *Type*: {type_name} ➔ *Antitype*: {antitype}"
                if correspondence:
                    line += f" ({correspondence})"
                if warrant:
                    line += f": {warrant}"
                lines.append(line)
            lines.append("")

        if self.cross_references:
            lines.append(f"**Cross-References**: {', '.join(self.cross_references[:6])}")
            lines.append("")

        return "\n".join(lines).strip()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize retrieved passage to dictionary."""
        return {
            "reference": self.reference,
            "human_ref": self.human_ref,
            "translation": self.translation,
            "score": round(self.score, 4),
            "text": self.text,
            "pericope_title": self.pericope_title,
            "storyline_epoch": self.storyline_epoch,
            "theological_loci": self.theological_loci,
            "thematic_ribbons": self.thematic_ribbons,
            "central_proposition": self.central_proposition,
            "christological_fulfillment": self.christological_fulfillment,
            "typological_arcs": self.typological_arcs,
            "cross_references": self.cross_references,
            "retrieval_reasons": self.retrieval_reasons,
            "starred": self.starred,
            "estimated_tokens": self.estimated_tokens,
            "verse_count": len(self.verses),
            "verses": [
                {
                    "chapter": v.chapter,
                    "verse": v.verse,
                    "text": v.text,
                    "canonical_id": v.canonical_verse_id,
                }
                for v in self.verses
            ],
        }


@dataclass
class RAGContextWindow:
    """Assembled scripture context window ready for LLM prompt generation and human inspection."""

    query: str
    rag_query: Optional[RAGQuery] = None
    passages: List[RetrievedPassage] = field(default_factory=list)
    system_prompt: str = ""
    theological_guardrails: TheologicalGuardrails = field(default_factory=TheologicalGuardrails)
    max_tokens_budget: int = 4000
    total_verses: int = 0
    estimated_tokens: int = 0

    def format_context_markdown(self) -> str:
        """Format the entire RAG context into illuminated markdown."""
        lines: List[str] = [
            f"# Scripture RAG Grounded Context: {self.query}",
            "",
            "## Hermeneutical Directives & Guardrails (The Gospel Coalition Standard)",
            self.theological_guardrails.build_directive_text(),
            "",
            f"## Grounded Scripture Passages ({len(self.passages)} Passages, {self.total_verses} Verses, ~{self.estimated_tokens} Tokens)",
            "",
        ]

        if not self.passages:
            lines.append("*(No matching scripture passages found for this inquiry.)*")
        else:
            for idx, p in enumerate(self.passages, 1):
                lines.append(p.format_markdown(index=idx))
                lines.append("")

        return "\n".join(lines).strip()

    def format_prompt_payload(
        self,
        custom_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format structured payload suitable for Google Gemini API."""
        markdown_context = self.format_context_markdown()

        user_content_parts = [
            f"## User Inquiry\n{self.query}\n\n",
            f"## Retrieved Scripture Context\n{markdown_context}\n\n",
            "## Synthesis Instruction\n",
            custom_instructions or (
                "Answer the user's inquiry based strictly upon the provided Scripture passages and theological "
                "context above. Show how the themes unfold along redemptive history and climax in Jesus Christ. "
                "Cite book, chapter, and verse accurately."
            ),
        ]

        return {
            "system_instruction": {
                "parts": [{"text": self.system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "".join(user_content_parts)}],
                }
            ],
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context window to JSON-compatible dictionary."""
        return {
            "query": self.query,
            "query_features": self.rag_query.to_dict() if self.rag_query else None,
            "passage_count": len(self.passages),
            "total_verses": self.total_verses,
            "estimated_tokens": self.estimated_tokens,
            "max_tokens_budget": self.max_tokens_budget,
            "passages": [p.to_dict() for p in self.passages],
            "system_prompt": self.system_prompt,
        }


@dataclass
class RAGResponse:
    """Result of an answered Scripture RAG inquiry."""

    query: str
    answer: str
    context: RAGContextWindow
    model: str
    created_at: str = field(default_factory=_utc_now_iso)
    token_usage: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize RAG response to dictionary."""
        return {
            "query": self.query,
            "answer": self.answer,
            "model": self.model,
            "created_at": self.created_at,
            "token_usage": self.token_usage,
            "context": self.context.to_dict(),
        }


# ==============================================================================
# Scoring Weights Configuration
# ==============================================================================


@dataclass
class RAGScoringWeights:
    """Configurable weights for combining multi-signal retrieval relevance."""

    explicit_ref_score: float = 1.00
    fts_weight: float = 0.25
    tag_weight: float = 0.20
    theology_weight: float = 0.15
    crossref_weight: float = 0.15
    typology_weight: float = 0.35
    starred_boost: float = 0.05


# ==============================================================================
# Scripture RAG Engine
# ==============================================================================


class ScriptureRAGEngine:
    """High-performance, zero-dependency Scripture RAG retrieval and synthesis engine."""

    def __init__(
        self,
        db: Optional[Database] = None,
        translation: str = DEFAULT_TRANSLATION,
        fallback_translation: str = FALLBACK_TRANSLATION,
        theology_engine: Optional[TGCTheologyEngine] = None,
        weights: Optional[RAGScoringWeights] = None,
    ) -> None:
        self.db = db if db is not None else Database(DEFAULT_DB_PATH)
        self.translation = translation
        self.fallback_translation = fallback_translation
        self.theology_engine = theology_engine or get_theology_engine()
        self.weights = weights or RAGScoringWeights()
        self.tag_mgr = TaggingService(self.db)
        self.crossref_mgr = CrossReferenceService(self.db)
        self.pericope_svc = PericopeService(self.db)

    # --------------------------------------------------------------------------
    # Core Retrieval Method
    # --------------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        max_passages: int = 5,
        max_tokens: int = 4000,
        min_score: float = 0.05,
        allow_expansion: bool = True,
        preferred_translation: Optional[str] = None,
    ) -> RAGContextWindow:
        """Execute multi-signal hybrid retrieval to build a grounded Scripture context window.

        Args:
            query: Natural language question, theological prompt, or passage topic.
            max_passages: Maximum distinct passages to include.
            max_tokens: Maximum estimated tokens budget for the context window.
            min_score: Minimum composite score threshold.
            allow_expansion: Whether to expand OT/NT connections via cross-refs and typological arcs.
            preferred_translation: Override translation (defaults to ESV with WEB fallback).

        Returns:
            Populated RAGContextWindow.
        """
        active_translation = preferred_translation or self.translation
        rag_query = extract_query_features(query, self.db)

        candidates: Dict[str, Dict[str, Any]] = {}

        def _get_candidate(ref_str: str) -> Dict[str, Any]:
            if ref_str not in candidates:
                candidates[ref_str] = {
                    "ref": ref_str,
                    "fts_score": 0.0,
                    "tag_score": 0.0,
                    "theology_score": 0.0,
                    "crossref_score": 0.0,
                    "typology_score": 0.0,
                    "explicit": False,
                    "reasons": [],
                    "arcs": [],
                    "crossrefs": [],
                }
            return candidates[ref_str]

        # ----------------------------------------------------------------------
        # Stage 1: Explicit Scripture References
        # ----------------------------------------------------------------------
        for ref_obj in rag_query.explicit_references:
            ref_str = ref_obj.format()
            cand = _get_candidate(ref_str)
            cand["explicit"] = True
            cand["reasons"].append(f"Explicit reference: {ref_str}")

        # ----------------------------------------------------------------------
        # Stage 2: FTS5 Full-Text Keyword Search
        # ----------------------------------------------------------------------
        if rag_query.keywords:
            fts_results: List[SearchResult] = []
            seen_verse_ids: Set[int] = set()

            # 1. Try multi-keyword OR query
            or_query = " OR ".join(rag_query.keywords[:6])
            try:
                or_hits = self.db.search_text(
                    or_query,
                    translation_id=[active_translation, self.fallback_translation],
                    limit=25,
                )
                for res in or_hits:
                    if res.verse_id not in seen_verse_ids:
                        fts_results.append(res)
                        seen_verse_ids.add(res.verse_id)
            except Exception:
                pass

            # 2. If multi-keyword AND query is possible, boost exact intersection
            if len(rag_query.keywords) >= 2:
                and_query = " ".join(rag_query.keywords[:4])
                try:
                    and_hits = self.db.search_text(
                        and_query,
                        translation_id=[active_translation, self.fallback_translation],
                        limit=10,
                    )
                    # Prepend AND hits so they get top rank
                    for res in reversed(and_hits):
                        if res.verse_id in seen_verse_ids:
                            fts_results = [r for r in fts_results if r.verse_id != res.verse_id]
                        fts_results.insert(0, res)
                        seen_verse_ids.add(res.verse_id)
                except Exception:
                    pass

            for idx, res in enumerate(fts_results):
                try:
                    ref_obj = parse_reference(res.human_ref)
                    pericopes = self.pericope_svc.get_pericopes_for_passage(ref_obj)
                    target_ref_str = pericopes[0].human_ref if pericopes else res.human_ref
                except Exception:
                    target_ref_str = res.human_ref

                cand = _get_candidate(target_ref_str)
                fts_score = max(0.1, 1.0 - (idx / max(1, len(fts_results))))
                cand["fts_score"] = max(cand["fts_score"], fts_score)
                reason = f"FTS5 match '{res.text[:45]}...'"
                if reason not in cand["reasons"]:
                    cand["reasons"].append(reason)

        # ----------------------------------------------------------------------
        # Stage 3: Semantic Tag & Topic Intersection
        # ----------------------------------------------------------------------
        if rag_query.detected_tags:
            try:
                tag_relevances = self.tag_mgr.score_verse_relevance(
                    rag_query.detected_tags,
                    translation_id=active_translation,
                    limit=20,
                    hydrate_verses=False,
                )
                for tr in tag_relevances:
                    cand = _get_candidate(tr.human_ref)
                    cand["tag_score"] = max(cand["tag_score"], tr.score)
                    reason = f"Matched tag(s): {', '.join(tr.matched_tags)}"
                    if reason not in cand["reasons"]:
                        cand["reasons"].append(reason)
            except Exception:
                pass

        # ----------------------------------------------------------------------
        # Stage 4: Theological Locus & Thematic Ribbon Matching
        # ----------------------------------------------------------------------
        for ribbon in rag_query.detected_ribbons:
            try:
                theology_records = self.db.get_verse_theology_by_ribbon(ribbon.value, limit=10)
                for rec in theology_records:
                    cand = _get_candidate(rec.human_ref)
                    cand["theology_score"] = max(cand["theology_score"], 0.85)
                    reason = f"Thematic Ribbon: {ribbon.display_name.split(' (')[0]}"
                    if reason not in cand["reasons"]:
                        cand["reasons"].append(reason)
            except Exception:
                pass

        for locus in rag_query.detected_loci:
            try:
                theology_records = self.db.get_verse_theology_by_locus(locus.value, limit=8)
                for rec in theology_records:
                    cand = _get_candidate(rec.human_ref)
                    cand["theology_score"] = max(cand["theology_score"], 0.70)
                    reason = f"Theological Locus: {locus.display_name.split(' (')[0]}"
                    if reason not in cand["reasons"]:
                        cand["reasons"].append(reason)
            except Exception:
                pass

        # ----------------------------------------------------------------------
        # Stage 5: Typological Arc Shadow-to-Fulfillment Expansion
        # ----------------------------------------------------------------------
        if allow_expansion:
            all_arcs: List[TypologicalArcRecord] = []
            try:
                all_arcs = self.db.get_all_typological_arcs()
            except Exception:
                pass

            for kw in rag_query.typological_keywords:
                kw_lower = kw.lower()
                for arc in all_arcs:
                    t_ref = (arc.type_human_ref or "").lower()
                    a_ref = (arc.antitype_human_ref or "").lower()
                    corr = (arc.theological_correspondence or "").lower()
                    warr = (arc.warrant or "").lower()
                    if kw_lower in corr or kw_lower in warr or kw_lower in t_ref or kw_lower in a_ref:
                        if arc.type_human_ref:
                            cand_type = _get_candidate(arc.type_human_ref)
                            cand_type["typology_score"] = max(cand_type["typology_score"], 0.90)
                            cand_type["arcs"].append(arc.to_dict())
                            reason = f"Typological Type: {arc.type_human_ref} ➔ {arc.antitype_human_ref}"
                            if reason not in cand_type["reasons"]:
                                cand_type["reasons"].append(reason)

                        if arc.antitype_human_ref:
                            cand_anti = _get_candidate(arc.antitype_human_ref)
                            cand_anti["typology_score"] = max(cand_anti["typology_score"], 0.95)
                            cand_anti["arcs"].append(arc.to_dict())
                            reason = f"Typological Antitype: {arc.antitype_human_ref} (from {arc.type_human_ref})"
                            if reason not in cand_anti["reasons"]:
                                cand_anti["reasons"].append(reason)

            top_prelim = sorted(
                candidates.values(),
                key=lambda c: (
                    1.0 if c["explicit"] else (
                        c["fts_score"] * self.weights.fts_weight +
                        c["tag_score"] * self.weights.tag_weight +
                        c["theology_score"] * self.weights.theology_weight +
                        c["typology_score"] * self.weights.typology_weight
                    )
                ),
                reverse=True,
            )[:5]

            for cand_item in top_prelim:
                ref_str = cand_item["ref"]
                parent_score = (
                    cand_item["fts_score"] * self.weights.fts_weight +
                    cand_item["tag_score"] * self.weights.tag_weight +
                    cand_item["theology_score"] * self.weights.theology_weight +
                    cand_item["typology_score"] * self.weights.typology_weight
                )
                try:
                    ref_obj = parse_reference(ref_str)
                    xrefs = self.db.get_cross_references(ref_obj)
                    for x in xrefs[:4]:
                        source_overlap = max(0, min(ref_obj.canonical_end_id, x.source_end_id) - max(ref_obj.canonical_start_id, x.source_start_id) + 1) > 0
                        other_ref = x.target_human_ref if source_overlap else x.source_human_ref
                        if other_ref and other_ref != ref_str:
                            cand_x = _get_candidate(other_ref)
                            # Attenuate expansion by parent score
                            cand_x["crossref_score"] = max(cand_x["crossref_score"], x.weight * parent_score * 0.60)
                            cand_x["crossrefs"].append(f"{ref_str} ({x.relationship_type})")
                            reason = f"Cross-reference connected to {ref_str}"
                            if reason not in cand_x["reasons"]:
                                cand_x["reasons"].append(reason)

                    arcs = self.db.get_typological_arcs_for_reference(ref_obj)
                    for arc in arcs:
                        type_overlap = max(0, min(ref_obj.canonical_end_id, arc.type_end_id) - max(ref_obj.canonical_start_id, arc.type_start_id) + 1) > 0
                        paired_ref = arc.antitype_human_ref if type_overlap else arc.type_human_ref
                        if paired_ref and paired_ref != ref_str:
                            cand_p = _get_candidate(paired_ref)
                            # Attenuate expansion by parent score
                            cand_p["typology_score"] = max(cand_p["typology_score"], parent_score * 0.70)
                            cand_p["arcs"].append(arc.to_dict())
                            reason = f"Typological fulfillment linked to {ref_str}" if type_overlap else f"Typological shadow linked to {ref_str}"
                            if reason not in cand_p["reasons"]:
                                cand_p["reasons"].append(reason)
                except Exception:
                    continue

        # ----------------------------------------------------------------------
        # Stage 6: Scoring, Deduplication & Ranking
        # ----------------------------------------------------------------------
        scored_candidates: List[Tuple[float, str, Dict[str, Any]]] = []
        for ref_str, cand in candidates.items():
            if cand["explicit"]:
                composite = self.weights.explicit_ref_score
            else:
                composite = (
                    cand["fts_score"] * self.weights.fts_weight +
                    cand["tag_score"] * self.weights.tag_weight +
                    cand["theology_score"] * self.weights.theology_weight +
                    cand["crossref_score"] * self.weights.crossref_weight +
                    cand["typology_score"] * self.weights.typology_weight
                )

            if composite >= min_score:
                scored_candidates.append((composite, ref_str, cand))

        scored_candidates.sort(key=lambda item: item[0], reverse=True)

        # ----------------------------------------------------------------------
        # Stage 7: Passage Text Hydration & Enrichment
        # ----------------------------------------------------------------------
        retrieved_passages: List[RetrievedPassage] = []
        seen_canonical_spans: List[Tuple[int, int]] = []
        running_token_count = 0
        total_verses = 0

        for comp_score, ref_str, cand in scored_candidates:
            if len(retrieved_passages) >= max_passages:
                break

            try:
                ref_obj = parse_reference(ref_str)
            except Exception:
                continue

            start_cid = ref_obj.canonical_start_id
            end_cid = ref_obj.canonical_end_id
            overlap = False
            for prev_s, prev_e in seen_canonical_spans:
                intersection = max(0, min(end_cid, prev_e) - max(start_cid, prev_s) + 1)
                span_len = end_cid - start_cid + 1
                if span_len > 0 and (intersection / span_len) > 0.50:
                    overlap = True
                    break
            if overlap:
                continue

            try:
                verses, eff_trans, _ = self.db.get_verses_with_fallback(
                    ref_obj,
                    translation_id=active_translation,
                    fallback_id=self.fallback_translation,
                    allow_network=False,
                )
            except Exception:
                continue

            if not verses:
                continue

            # Clamp long pericopes (e.g. 52-verse chapters) to a concise, readable excerpt
            if len(verses) > 14:
                verses = verses[:12]
                ref_obj = Reference(
                    book=get_book(verses[0].book_id),
                    start_chapter=verses[0].chapter,
                    start_verse=verses[0].verse,
                    end_chapter=verses[-1].chapter,
                    end_verse=verses[-1].verse,
                )

            passage_text = " ".join(f"[{v.verse}] {v.text}" for v in verses)

            pericope_title: Optional[str] = None
            central_prop: Optional[str] = None
            christological: Optional[str] = None
            try:
                pericopes = self.pericope_svc.get_pericopes_for_passage(ref_obj)
                if pericopes:
                    pericope_title = pericopes[0].title
                    central_prop = pericopes[0].central_proposition
                    christological = pericopes[0].christological_fulfillment
            except Exception:
                pass

            storyline_epoch: Optional[str] = None
            loci: List[str] = []
            ribbons: List[str] = []
            try:
                theology_records = self.db.get_verse_theology_for_reference(ref_obj)
                if theology_records:
                    rec = theology_records[0]
                    storyline_epoch = rec.storyline_epoch
                    loci = list(dict.fromkeys(r.theological_locus for r in theology_records if r.theological_locus))
                    ribbons = list(dict.fromkeys(r.thematic_ribbon for r in theology_records if r.thematic_ribbon))
            except Exception:
                pass

            arcs_raw = cand["arcs"]
            if not arcs_raw:
                try:
                    db_arcs = self.db.get_typological_arcs_for_reference(ref_obj)
                    arcs_raw = [a.to_dict() for a in db_arcs]
                except Exception:
                    arcs_raw = []
            arcs_list = list({f"{a.get('type_human_ref')}->{a.get('antitype_human_ref')}": a for a in arcs_raw}.values())

            xrefs_raw = cand["crossrefs"]
            if not xrefs_raw:
                try:
                    db_xrefs = self.db.get_cross_references(ref_obj)
                    xrefs_raw = [
                        x.target_human_ref
                        if x.source_start_id <= start_cid <= x.source_end_id
                        else x.source_human_ref
                        for x in db_xrefs[:4]
                    ]
                except Exception:
                    xrefs_raw = []
            xrefs_list = list(dict.fromkeys(xrefs_raw))

            starred = False
            try:
                vt_list = self.db.get_favorites()
                fav_spans = {(vt.start_canonical_id, vt.end_canonical_id) for vt in vt_list if vt.starred}
                if any(start_cid <= fs <= end_cid or start_cid <= fe <= end_cid for fs, fe in fav_spans):
                    starred = True
                    comp_score += self.weights.starred_boost
            except Exception:
                pass

            p_tokens = estimate_tokens(passage_text)
            if running_token_count + p_tokens > max_tokens and retrieved_passages:
                break

            retrieved = RetrievedPassage(
                reference=ref_str,
                human_ref=ref_obj.format(),
                translation=eff_trans,
                verses=verses,
                text=passage_text,
                score=min(1.0, comp_score),
                pericope_title=pericope_title,
                storyline_epoch=storyline_epoch,
                theological_loci=loci,
                thematic_ribbons=ribbons,
                central_proposition=central_prop,
                christological_fulfillment=christological,
                typological_arcs=arcs_list,
                cross_references=xrefs_list,
                retrieval_reasons=cand["reasons"],
                starred=starred,
                estimated_tokens=p_tokens,
            )

            retrieved_passages.append(retrieved)
            seen_canonical_spans.append((start_cid, end_cid))
            running_token_count += p_tokens
            total_verses += len(verses)

        system_prompt = self.theology_engine.generate_rag_system_prompt()

        return RAGContextWindow(
            query=query,
            rag_query=rag_query,
            passages=retrieved_passages,
            system_prompt=system_prompt,
            theological_guardrails=self.theology_engine.guardrails,
            max_tokens_budget=max_tokens,
            total_verses=total_verses,
            estimated_tokens=running_token_count,
        )

    # --------------------------------------------------------------------------
    # Deterministic Reference Context Builder
    # --------------------------------------------------------------------------

    def build_context_for_references(
        self,
        references: Sequence[Union[str, Reference]],
        query: str = "",
        preferred_translation: Optional[str] = None,
        max_tokens: int = 4000,
    ) -> RAGContextWindow:
        """Construct a grounded RAGContextWindow for an explicit list of scripture references."""
        active_translation = preferred_translation or self.translation
        passages: List[RetrievedPassage] = []
        running_tokens = 0
        total_verses = 0

        for ref_item in references:
            ref_obj = parse_reference(ref_item) if isinstance(ref_item, str) else ref_item
            try:
                verses, eff_trans, _ = self.db.get_verses_with_fallback(
                    ref_obj,
                    translation_id=active_translation,
                    fallback_id=self.fallback_translation,
                    allow_network=False,
                )
            except Exception:
                continue

            if not verses:
                continue

            passage_text = " ".join(f"[{v.verse}] {v.text}" for v in verses)

            pericope_title: Optional[str] = None
            central_prop: Optional[str] = None
            christological: Optional[str] = None
            try:
                pericopes = self.pericope_svc.get_pericopes_for_passage(ref_obj)
                if pericopes:
                    pericope_title = pericopes[0].title
                    central_prop = pericopes[0].central_proposition
                    christological = pericopes[0].christological_fulfillment
            except Exception:
                pass

            storyline_epoch: Optional[str] = None
            loci: List[str] = []
            ribbons: List[str] = []
            try:
                theology_records = self.db.get_verse_theology_for_reference(ref_obj)
                if theology_records:
                    rec = theology_records[0]
                    storyline_epoch = rec.storyline_epoch
                    loci = list(dict.fromkeys(r.theological_locus for r in theology_records if r.theological_locus))
                    ribbons = list(dict.fromkeys(r.thematic_ribbon for r in theology_records if r.thematic_ribbon))
            except Exception:
                pass

            arcs_list: List[Dict[str, str]] = []
            try:
                db_arcs = self.db.get_typological_arcs_for_reference(ref_obj)
                arcs_list = [a.to_dict() for a in db_arcs]
            except Exception:
                pass

            xrefs_list: List[str] = []
            try:
                db_xrefs = self.db.get_cross_references(ref_obj)
                xrefs_list = [
                    x.target_human_ref
                    if x.source_start_id <= ref_obj.canonical_start_id <= x.source_end_id
                    else x.source_human_ref
                    for x in db_xrefs[:4]
                ]
            except Exception:
                pass

            p_tokens = estimate_tokens(passage_text)
            retrieved = RetrievedPassage(
                reference=ref_obj.format(),
                human_ref=ref_obj.format(),
                translation=eff_trans,
                verses=verses,
                text=passage_text,
                score=1.0,
                pericope_title=pericope_title,
                storyline_epoch=storyline_epoch,
                theological_loci=loci,
                thematic_ribbons=ribbons,
                central_proposition=central_prop,
                christological_fulfillment=christological,
                typological_arcs=arcs_list,
                cross_references=xrefs_list,
                retrieval_reasons=["Explicitly requested citation"],
                starred=False,
                estimated_tokens=p_tokens,
            )
            passages.append(retrieved)
            running_tokens += p_tokens
            total_verses += len(verses)

        system_prompt = self.theology_engine.generate_rag_system_prompt()

        return RAGContextWindow(
            query=query or "Direct Scripture Inquiry",
            passages=passages,
            system_prompt=system_prompt,
            theological_guardrails=self.theology_engine.guardrails,
            max_tokens_budget=max_tokens,
            total_verses=total_verses,
            estimated_tokens=running_tokens,
        )

    # --------------------------------------------------------------------------
    # Optional LLM Synthesis Method (Zero External Dependencies)
    # --------------------------------------------------------------------------

    def answer(
        self,
        query: str,
        client: Optional[GeminiClient] = None,
        max_passages: int = 5,
        model: Optional[str] = None,
        custom_instructions: Optional[str] = None,
    ) -> RAGResponse:
        """Execute complete Scripture RAG pipeline: retrieval followed by grounded generation.

        Raises:
            LLMAuthError: If GEMINI_API_KEY is not set or authorized.
            LLMError: If LLM generation fails or network is offline.
        """
        context = self.retrieve(query, max_passages=max_passages)

        gemini_client = client
        if gemini_client is None:
            api_key = get_gemini_api_key()
            if not api_key:
                raise LLMAuthError(
                    "GEMINI_API_KEY is not configured. Scripture RAG retrieval succeeded, "
                    "but LLM answer synthesis requires an API key in the environment or ~/.config/bible/gemini_api_key."
                )
            gemini_client = GeminiClient(api_key=api_key)

        prompt_payload = context.format_prompt_payload(custom_instructions=custom_instructions)
        chosen_model = model or DEFAULT_GEMINI_MODEL

        system_text = prompt_payload["system_instruction"]["parts"][0]["text"]
        user_prompt = prompt_payload["contents"][0]["parts"][0]["text"]

        response = gemini_client.generate(
            user_prompt,
            system_instruction=system_text,
            model=chosen_model,
        )

        token_usage = dict(response.usage) if response.usage else {}

        return RAGResponse(
            query=query,
            answer=response.text,
            context=context,
            model=response.model,
            token_usage=token_usage,
        )

    def answer_stream(
        self,
        query: str,
        client: Optional[GeminiClient] = None,
        max_passages: int = 5,
        model: Optional[str] = None,
        custom_instructions: Optional[str] = None,
    ) -> Iterator[str]:
        """Execute Scripture RAG pipeline streaming answer tokens incrementally.

        Raises:
            LLMAuthError: If GEMINI_API_KEY is not set or authorized.
            LLMError: If LLM generation fails or network is offline.
        """
        context = self.retrieve(query, max_passages=max_passages)

        gemini_client = client
        if gemini_client is None:
            api_key = get_gemini_api_key()
            if not api_key:
                raise LLMAuthError(
                    "GEMINI_API_KEY is not configured. Scripture RAG retrieval succeeded, "
                    "but LLM answer synthesis requires an API key in the environment or ~/.config/bible/gemini_api_key."
                )
            gemini_client = GeminiClient(api_key=api_key)

        prompt_payload = context.format_prompt_payload(custom_instructions=custom_instructions)
        chosen_model = model or DEFAULT_GEMINI_MODEL

        system_text = prompt_payload["system_instruction"]["parts"][0]["text"]
        user_prompt = prompt_payload["contents"][0]["parts"][0]["text"]

        for chunk in gemini_client.generate_stream(
            user_prompt,
            system_instruction=system_text,
            model=chosen_model,
        ):
            if chunk.text:
                yield chunk.text


# ==============================================================================
# Factory & Convenience Functions
# ==============================================================================

_DEFAULT_RAG_ENGINE: Optional[ScriptureRAGEngine] = None


def get_rag_engine(db: Optional[Database] = None) -> ScriptureRAGEngine:
    """Return a shared or newly initialized ScriptureRAGEngine instance."""
    global _DEFAULT_RAG_ENGINE
    if db is not None:
        return ScriptureRAGEngine(db=db)
    if _DEFAULT_RAG_ENGINE is None:
        _DEFAULT_RAG_ENGINE = ScriptureRAGEngine()
    return _DEFAULT_RAG_ENGINE


def retrieve_rag_context(
    query: str,
    db: Optional[Database] = None,
    max_passages: int = 5,
    max_tokens: int = 4000,
    preferred_translation: Optional[str] = None,
) -> RAGContextWindow:
    """Convenience function to retrieve a grounded Scripture RAG context window."""
    engine = get_rag_engine(db=db)
    return engine.retrieve(
        query,
        max_passages=max_passages,
        max_tokens=max_tokens,
        preferred_translation=preferred_translation,
    )
