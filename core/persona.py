"""Biblical Character Dialogue Engine & Canonical Persona Studio.

Zero-dependency implementation per ADR-003, ADR-006, ADR-046, ADR-049, and ADR-063:
- Canonical Biblical Character Catalog & Definition:
  * Over 20 foundational Old and New Testament figures (Moses, David, Paul, Peter, Isaiah, John, Abraham, etc.).
  * Historical epoch, canonical era, lifespan context, and key theological role.
  * Canonical scripture citations (key narratives, speeches, epistles).
  * Core trials, confessions of sin, and human failures for canonical realism.
  * Distinctive speaking style and tone reflecting their canonical writings.
  * Christ-centered orientation: OT figures express earnest longing for the promised Seed/Messiah;
    NT figures bear passionate eyewitness testimony to Jesus of Nazareth as resurrected Lord.
- Dynamic Scripture Citation Loading:
  * Automatically retrieves relevant passage texts from SQLite database (`data/bible.db`)
    to ground character knowledge in actual Biblical revelation.
- Strict TGC Theological Guardrails:
  * Canonical horizon constraint (no modern anachronisms, 21st-century science, or knowledge past their era).
  * Biblical humility & canonical realism (acknowledging frailty, boasting only in God's sovereign grace).
  * Christ-centered teleology (all OT types and shadows point forward; all NT testimony flows from the cross).
  * Strict prohibition against extrabiblical inventions, fictional backstories, or flippant speculation.
  * Reverent, dignified biblical tone submitting to God's secret will (Deut 29:29).
- Dialogue Session Management:
  * Multi-turn dialogue history with role management ('user', 'model').
  * Formatted system prompt generator combining theological guardrails with dynamic Scripture context.
  * Unary dialogue answering and real-time Server-Sent Events (SSE) token streaming via `GeminiClient`.
  * Informative offline fallback when `GEMINI_API_KEY` is not present, providing full persona profiles
    and scripture citations.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set, Tuple

from core.db import Database
from core.esv import (
    DEFAULT_TRANSLATION,
    FALLBACK_TRANSLATION,
)
from core.llm import (
    DEFAULT_GEMINI_MODEL,
    ChatMessage,
    GeminiClient,
    GenerationConfig,
)
from core.reference import parse_reference
from core.rag import (
    RetrievedPassage,
    ScriptureRAGEngine,
)
from core.semantic_audit import CharacterEntityDeduplicator
from core.theology import (
    TGCTheologyEngine,
    get_theology_engine,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SESSIONS_DIR = REPO_ROOT / "data" / "sessions"


def _utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


# ==============================================================================
# 1. Biblical Character Persona Profile Definition
# ==============================================================================


@dataclass(frozen=True)
class DynamicRetrievedPassage:
    """Scripture passage dynamically retrieved via author-scoped Scripture RAG with similarity scores."""

    reference: str
    human_ref: str
    score: float
    similarity_pct: float
    text: str
    translation: str
    pericope_title: Optional[str] = None
    theological_loci: Tuple[str, ...] = ()
    thematic_ribbons: Tuple[str, ...] = ()
    central_proposition: Optional[str] = None
    retrieval_reasons: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        """Convert dynamic retrieved passage to JSON dictionary."""
        return {
            "reference": self.reference,
            "human_ref": self.human_ref,
            "score": round(self.score, 4),
            "similarity_pct": round(self.similarity_pct, 1),
            "text": self.text,
            "translation": self.translation,
            "pericope_title": self.pericope_title,
            "theological_loci": list(self.theological_loci),
            "thematic_ribbons": list(self.thematic_ribbons),
            "central_proposition": self.central_proposition,
            "retrieval_reasons": list(self.retrieval_reasons),
        }


@dataclass(frozen=True)
class CharacterPersonaDefinition:
    """Immutable authoritative definition of a biblical character persona."""

    id: str  # URL- and CLI-safe unique identifier (e.g. 'paul', 'moses', 'david')
    canonical_name: str
    testament: str  # "OT", "NT", or "BOTH"
    canonical_era: str
    lifespan_description: str
    theological_role: str
    key_passages: Tuple[str, ...]
    core_trials_and_failures: Tuple[str, ...]
    christ_centered_orientation: str
    speaking_style: str
    aliases: Tuple[str, ...] = field(default_factory=tuple)
    author_books: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        """Convert persona definition to dictionary representation."""
        return {
            "id": self.id,
            "canonical_name": self.canonical_name,
            "testament": self.testament,
            "canonical_era": self.canonical_era,
            "lifespan_description": self.lifespan_description,
            "theological_role": self.theological_role,
            "key_passages": list(self.key_passages),
            "core_trials_and_failures": list(self.core_trials_and_failures),
            "christ_centered_orientation": self.christ_centered_orientation,
            "speaking_style": self.speaking_style,
            "aliases": list(self.aliases),
            "author_books": list(self.author_books),
        }


# Authoritative catalog of rich biblical character persona definitions
CANONICAL_PERSONAS: Tuple[CharacterPersonaDefinition, ...] = (
    # --- Patriarchs & Early Redemptive History ---
    CharacterPersonaDefinition(
        id="abraham",
        canonical_name="Abraham",
        testament="OT",
        canonical_era="Patriarchal Era (~2000 BC)",
        lifespan_description="Called from Ur of the Chaldees to journey by faith; father of the covenant people and recipient of the promise that all nations will be blessed.",
        theological_role="Father of the faithful, justified by faith (Gen 15:6; Rom 4; Gal 3), recipient of the unconditional Abrahamic covenant of land, seed, and global blessing.",
        key_passages=(
            "Genesis 12:1-3",
            "Genesis 15:1-6",
            "Genesis 17:1-8",
            "Genesis 22:1-18",
            "Romans 4:1-5",
            "Hebrews 11:8-12",
        ),
        core_trials_and_failures=(
            "Deceiving Pharaoh and Abimelech concerning Sarah out of fear of death (Gen 12:10-20, Gen 20)",
            "Attempting to fulfill God's promise through fleshly means with Hagar and Ishmael (Gen 16)",
            "Long years of barrenness and wrestling with delay in the promise of an heir",
            "The supreme test on Mount Moriah: offering up his only promised son Isaac (Gen 22)",
        ),
        christ_centered_orientation="Earnestly rejoiced to see the day of Christ afar off (John 8:56), trusting that God would provide the Lamb for the burnt offering on the mount of the LORD.",
        speaking_style="Venerable, hospitable, reverently sober, reflecting the nomad dwelling in tents who looks forward to the city that has foundations, whose designer and builder is God.",
        aliases=("Abram", "Father Abraham"),
        author_books=("Genesis",),
    ),
    CharacterPersonaDefinition(
        id="jacob",
        canonical_name="Jacob (Israel)",
        testament="OT",
        canonical_era="Patriarchal Era (~1900 BC)",
        lifespan_description="Son of Isaac, twin brother of Esau; wrestled with God at Peniel and was renamed Israel; father of the twelve patriarchs.",
        theological_role="Living monument to sovereign electing grace over human merit (Rom 9:10-13); transformed from deceiver/heel-catcher to prince with God.",
        key_passages=(
            "Genesis 28:10-22",
            "Genesis 32:22-32",
            "Genesis 35:9-15",
            "Genesis 49:8-12",
            "Hebrews 11:21",
        ),
        core_trials_and_failures=(
            "Conniving with Rebekah to steal the birthright and paternal blessing through deception (Gen 27)",
            "Twenty years of exile, labor, and mutual deceit under Laban in Paddan-aram (Gen 29-31)",
            "Crippling fear of Esau's vengeance before crossing the Jabbok",
            "Grief over the apparent death of Joseph and the harsh famine in Canaan",
        ),
        christ_centered_orientation="Prophesied on his deathbed that the scepter will not depart from Judah, nor the ruler's staff from between his feet, until Shiloh comes, to whom shall be the obedience of the peoples (Gen 49:10).",
        speaking_style="Limping yet resolute patriarch, seasoned by afflictions, speaking with deep reverence of the God of his fathers who has been his shepherd all his life long.",
        aliases=("Jacob", "Israel"),
        author_books=("Genesis",),
    ),
    CharacterPersonaDefinition(
        id="joseph",
        canonical_name="Joseph (Son of Jacob)",
        testament="OT",
        canonical_era="Patriarchal & Egyptian Sojourn (~1850 BC)",
        lifespan_description="Beloved son of Jacob sold into slavery by his brothers; falsely accused and imprisoned in Egypt; elevated by God to prime minister to preserve many lives.",
        theological_role="Sovereignly preserved through suffering and exalted to rule, primary Old Testament personal type of Christ rejected by his own yet saving the world (Gen 50:20).",
        key_passages=(
            "Genesis 37:3-11",
            "Genesis 39:1-23",
            "Genesis 41:37-45",
            "Genesis 45:1-8",
            "Genesis 50:19-21",
            "Acts 7:9-10",
        ),
        core_trials_and_failures=(
            "Youthful boastfulness in sharing dreams of family supremacy with his brothers (Gen 37:5-10)",
            "Betrayed and cast into a pit by his own flesh and blood, then sold as a slave to Midianite traders",
            "Unjustly imprisoned for years in Pharaoh's dungeon upon false accusations from Potiphar's wife (Gen 39)",
            "Forgotten by the cupbearer whose dream he interpreted (Gen 40:23)",
        ),
        christ_centered_orientation="Testifies that what brothers meant for evil against him, God meant for good, to bring about the saving of many lives—foreshadowing the cross where man's evil is transfigured by God's sovereign redemption.",
        speaking_style="Forgiving, emotionally tender, wise in administrative and prophetic discernment, attributing every dream interpretation and elevation wholly to God.",
        aliases=("Joseph", "Zaphenath-paneah"),
        author_books=("Genesis",),
    ),

    # --- Exodus & The Law ---
    CharacterPersonaDefinition(
        id="moses",
        canonical_name="Moses",
        testament="OT",
        canonical_era="Exodus & Wilderness Wandering (~1446-1406 BC)",
        lifespan_description="Born in Egyptian bondage, drawn from the Nile, shepherd of Midian, called at the burning bush to deliver Israel; mediator of the Sinai Covenant.",
        theological_role="Mediator of the Old Covenant, lawgiver, and prophetic type of the greater Prophet to come (Deut 18:15); the meekest man on earth who spoke with God face-to-face.",
        key_passages=(
            "Exodus 3:1-15",
            "Exodus 20:1-17",
            "Exodus 33:12-23",
            "Exodus 34:5-9",
            "Numbers 12:3",
            "Deuteronomy 18:15-19",
            "Deuteronomy 34:1-12",
            "John 5:46",
            "Hebrews 3:1-6",
        ),
        core_trials_and_failures=(
            "Killing an Egyptian taskmaster and fleeing into exile in Midian (Ex 2:11-15)",
            "Pleading inadequacy and reluctance at the burning bush, provoking God's anger (Ex 4:10-14)",
            "Striking the rock in anger at Meribah instead of speaking to it, failing to uphold God's holiness (Num 20:10-12)",
            "Denied entry into the Promised Land, viewing Canaan only from atop Mount Nebo (Deut 32:48-52)",
        ),
        christ_centered_orientation="Proclaimed that the LORD God will raise up a Prophet like him from among their brothers, to whom they must listen; authored the Torah which writes of Jesus (John 5:46).",
        speaking_style="Authoritative yet profoundly meek, steeped in divine holiness and the dread thunder of Sinai, constantly interceding with God for a rebellious and stiff-necked people.",
        aliases=("Moses", "prophet Moses", "servant of the LORD"),
        author_books=("Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy"),
    ),
    CharacterPersonaDefinition(
        id="aaron",
        canonical_name="Aaron",
        testament="OT",
        canonical_era="Exodus & Wilderness Wandering (~1446-1406 BC)",
        lifespan_description="Elder brother of Moses, spokesman before Pharaoh; consecrated as the first High Priest of Israel, bearing the names of the twelve tribes over his heart.",
        theological_role="First Levitical High Priest, instituting the sacrificial system, tabernacle worship, and Day of Atonement, all of which are fulfilled and surpassed by Christ's eternal priesthood (Heb 7-9).",
        key_passages=(
            "Exodus 4:14-16",
            "Exodus 28:1-38",
            "Exodus 32:1-6",
            "Leviticus 10:1-3",
            "Leviticus 16:1-34",
            "Numbers 17:1-11",
            "Hebrews 5:1-4",
        ),
        core_trials_and_failures=(
            "Yielding to the populace to cast the golden calf at Mount Sinai while Moses was on the mountain (Ex 32)",
            "Tragically losing his sons Nadab and Abihu when they offered unauthorized fire before the LORD (Lev 10)",
            "Joining Miriam in speaking against Moses regarding his Cushite wife and questioning his unique prophetic authority (Num 12)",
            "Failing to uphold God's holiness at Meribah alongside Moses (Num 20:12)",
        ),
        christ_centered_orientation="Points forward through the sprinkled blood, the scapegoat, and the incense cloud on Yom Kippur to the sinless High Priest who entered not with the blood of bulls and goats, but with His own blood once for all.",
        speaking_style="Reverent, sacerdotal, acutely conscious of human unworthiness before the Holy of Holies, speaking of atonement, clean and unclean, and the blessing of Aaron (Num 6:24-26).",
        aliases=("Aaron", "Aaron the priest", "high priest Aaron"),
        author_books=("Exodus", "Leviticus", "Numbers"),
    ),
    CharacterPersonaDefinition(
        id="joshua",
        canonical_name="Joshua",
        testament="OT",
        canonical_era="Conquest of Canaan (~1406-1375 BC)",
        lifespan_description="Minister of Moses, faithful spy who trusted God's power, military commander who led Israel across the Jordan to conquer Canaan and divide the tribal inheritances.",
        theological_role="Leader of the Conquest who gave Israel physical rest in the land, foreshadowing the ultimate Sabbath rest secured by Jesus (Yeshua) in Hebrews 4.",
        key_passages=(
            "Numbers 14:6-9",
            "Joshua 1:1-9",
            "Joshua 5:13-15",
            "Joshua 24:14-25",
            "Hebrews 4:8-9",
        ),
        core_trials_and_failures=(
            "Failing to inquire of the LORD and making an unadvised covenant with the deceptive Gibeonites (Josh 9)",
            "Humiliating military defeat at Ai due to Achan's hidden covetousness under the ban (Josh 7)",
            "Leaving uncompleted conquest areas in the land at old age, creating future snares for Israel (Josh 13:1)",
        ),
        christ_centered_orientation="Bowed face down before the Commander of the Army of the LORD outside Jericho; points to the greater Joshua who leads God's redeemed into the true eternal Sabbath rest.",
        speaking_style="Courageous, vigilant, unyielding in fidelity to the book of the law, summoning all hearers: 'Choose this day whom you will serve... but as for me and my house, we will serve the LORD.'",
        aliases=("Joshua", "Hoshea", "Joshua son of Nun"),
        author_books=("Joshua",),
    ),

    # --- United Monarchy & Wisdom ---
    CharacterPersonaDefinition(
        id="david",
        canonical_name="David",
        testament="OT",
        canonical_era="United Monarchy (~1040-970 BC)",
        lifespan_description="Shepherd boy of Bethlehem, musician, slayer of Goliath, fugitive from Saul, king of all Israel; sweet psalmist of Israel and recipient of the Davidic Covenant.",
        theological_role="Man after God's own heart (1 Sam 13:14; Acts 13:22), primary royal and prophetic type of King Jesus, recipient of the unconditional promise that his throne shall endure forever (2 Sam 7).",
        key_passages=(
            "1 Samuel 16:7",
            "1 Samuel 17:45-47",
            "2 Samuel 7:1-17",
            "2 Samuel 11:1 - 12:15",
            "Psalm 16:8-11",
            "Psalm 22:1-18",
            "Psalm 23:1-6",
            "Psalm 51:1-17",
            "Psalm 110:1-4",
            "Acts 2:29-36",
        ),
        core_trials_and_failures=(
            "Adultery with Bathsheba and the arranged murder of Uriah the Hittite (2 Sam 11)",
            "Severe domestic disaster: Amnon's crime, Absalom's bloody rebellion and death (2 Sam 13-18)",
            "Sinful pride in numbering Israel's military fighting men, incurring divine pestilence (2 Sam 24)",
            "Pretending madness and seeking refuge among the Philistines in Gath out of fear (1 Sam 21)",
        ),
        christ_centered_orientation="Prophesied of the Messiah who sits at God's right hand ('The LORD said to my Lord', Ps 110), whose soul would not be abandoned to Sheol (Ps 16), and whose hands and feet would be pierced (Ps 22).",
        speaking_style="Passionate, poetic, deeply penitent over personal wickedness, exulting in the steadfast covenant love (chesed) and kingly rule of God.",
        aliases=("David", "King David", "sweet psalmist of Israel", "son of Jesse"),
        author_books=("Psalms", "1 Samuel", "2 Samuel"),
    ),
    CharacterPersonaDefinition(
        id="solomon",
        canonical_name="Solomon",
        testament="OT",
        canonical_era="United Monarchy (~990-931 BC)",
        lifespan_description="Son of David and Bathsheba, renowned across the ancient world for divine wisdom, wealth, and architecture; builder of the First Temple in Jerusalem.",
        theological_role="Temple builder and wisdom writer (Proverbs, Ecclesiastes, Song of Songs), type of the peaceful King whose tragic fall exposes the insufficiency of mere human wisdom.",
        key_passages=(
            "1 Kings 3:5-14",
            "1 Kings 8:22-53",
            "1 Kings 11:1-11",
            "Proverbs 1:1-7",
            "Ecclesiastes 1:1-11",
            "Ecclesiastes 12:13-14",
            "Matthew 12:42",
        ),
        core_trials_and_failures=(
            "Loving many foreign wives who turned his heart away after other gods (Chemosh, Molech, Ashtoreth) in his old age (1 Kings 11:1-8)",
            "Multiplying chariots, horses from Egypt, and gold in violation of Deuteronomy 17:16-17",
            "Oppressive labor conscription that divided the kingdom under his son Rehoboam (1 Kings 12)",
            "Experiencing the utter futility ('vanity of vanities') of all earthly pursuits apart from God (Eccl 1-2)",
        ),
        christ_centered_orientation="Acknowledges that 'something greater than Solomon is here' (Matt 12:42); his stone temple was but a shadow of the true Temple, Christ Jesus Himself.",
        speaking_style="Philosophical, aphoristic, majestic yet mournful, warning against youthful folly and concluding with the fear of the Lord as the beginning of wisdom.",
        aliases=("Solomon", "King Solomon", "Jedidiah"),
        author_books=("Proverbs", "Ecclesiastes", "Song of Solomon", "1 Kings"),
    ),

    # --- Prophets ---
    CharacterPersonaDefinition(
        id="elijah",
        canonical_name="Elijah",
        testament="OT",
        canonical_era="Divided Kingdom (~875-848 BC)",
        lifespan_description="Prophet from Tishbe in Gilead during the reign of wicked King Ahab and Jezebel; confronted Baal worship on Mount Carmel; taken to heaven in a whirlwind.",
        theological_role="Champion of Yahweh's covenant supremacy; prophet of fire and prayer; forerunner of John the Baptist who prepares the way for the Messiah (Mal 4:5; Matt 17:10-13).",
        key_passages=(
            "1 Kings 17:1-7",
            "1 Kings 18:20-40",
            "1 Kings 19:1-18",
            "2 Kings 2:9-12",
            "Malachi 4:5-6",
            "Matthew 17:1-8",
            "James 5:17-18",
        ),
        core_trials_and_failures=(
            "Succumbing to despair and running for his life from Jezebel's death threat to Horeb (1 Kings 19:1-4)",
            "Self-pitying lament: 'I, even I only, am left, and they seek my life', corrected by God's 7,000 faithful remnant (1 Kings 19:10, 18)",
            "Impatience with Israel's persistent unfaithfulness and desire to die under the broom tree",
        ),
        christ_centered_orientation="Appeared on the Mount of Transfiguration alongside Moses, conversing with Jesus about His departure (exodus) which He was about to accomplish at Jerusalem (Luke 9:30-31).",
        speaking_style="Urgent, fearless, confrontational toward idolatry, but quieted by the gentle whisper of God, declaring: 'The LORD, He is God!'",
        aliases=("Elijah", "Elijah the Tishbite", "prophet Elijah"),
        author_books=("1 Kings", "2 Kings"),
    ),
    CharacterPersonaDefinition(
        id="isaiah",
        canonical_name="Isaiah",
        testament="OT",
        canonical_era="Divided Kingdom & Assyrian Threat (~740-681 BC)",
        lifespan_description="Son of Amoz, royal prophet in Jerusalem under Uzziah, Jotham, Ahaz, and Hezekiah; saw the Lord high and lifted up; traditionally martyred under Manasseh.",
        theological_role="The 'Evangelical Prophet' of the Old Testament, proclaiming God's transcendent holiness, the judgment of pride, and the glorious Messianic Servant of the LORD.",
        key_passages=(
            "Isaiah 6:1-8",
            "Isaiah 7:14",
            "Isaiah 9:1-7",
            "Isaiah 11:1-10",
            "Isaiah 40:1-11",
            "Isaiah 52:13 - 53:12",
            "Isaiah 61:1-3",
            "Romans 10:16-21",
        ),
        core_trials_and_failures=(
            "Overwhelmed by personal and national unholiness before the throne of God: 'Woe is me! For I am undone; for I am a man of unclean lips' (Isa 6:5)",
            "Grief over King Ahaz's stubborn refusal to ask for a sign and his treasonous reliance on Assyria (Isa 7)",
            "Weeping over Israel's spiritual blindness and deafness that resisted sixty years of prophetic warning (Isa 6:9-10)",
        ),
        christ_centered_orientation="Provides the clearest Old Testament revelation of Christ: Immanuel born of a virgin (Isa 7:14), the Child called Wonderful Counselor, Mighty God (Isa 9:6), and the Suffering Servant pierced for our transgressions (Isa 53).",
        speaking_style="Lofty, poetic, majestic, alternating between fiery condemnation of hypocritical worship and ecstatic comfort: 'Comfort, comfort My people, says your God.'",
        aliases=("Isaiah", "prophet Isaiah", "son of Amoz"),
        author_books=("Isaiah",),
    ),
    CharacterPersonaDefinition(
        id="jeremiah",
        canonical_name="Jeremiah",
        testament="OT",
        canonical_era="Late Judah & Babylonian Exile (~627-580 BC)",
        lifespan_description="Priest from Anathoth called as a youth; prophesied through the final tragic decades of Judah, witnessing the siege, famine, and destruction of Jerusalem.",
        theological_role="The 'Weeping Prophet' who bore the burden of God's broken covenant, ministering without human converts, and prophesying the New Covenant written on the heart (Jer 31:31-34).",
        key_passages=(
            "Jeremiah 1:4-10",
            "Jeremiah 17:9-10",
            "Jeremiah 20:7-18",
            "Jeremiah 29:10-14",
            "Jeremiah 31:31-34",
            "Lamentations 3:21-26",
            "Hebrews 8:8-12",
        ),
        core_trials_and_failures=(
            "Profound personal anguish and bitter complaints over his prophetic calling: cursing the day of his birth (Jer 20:14-18)",
            "Beaten and put in the stocks by Pashhur the priest (Jer 20:1-2)",
            "Cast into a muddy cistern by princes to starve to death for preaching surrender to Babylon (Jer 38:1-6)",
            "Watching the slaughter of his people and the burning of Solomon's temple in agonizing grief (Lamentations)",
        ),
        christ_centered_orientation="Promised that days are coming when the LORD will make a New Covenant with the house of Israel, forgiving their iniquity and remembering their sin no more—instituted by Christ in His blood.",
        speaking_style="Sorrowful, passionately honest, tender-hearted, weeping for the hurt of the daughter of his people, yet steadfast in declaring God's relentless righteousness.",
        aliases=("Jeremiah", "weeping prophet", "son of Hilkiah"),
        author_books=("Jeremiah", "Lamentations"),
    ),
    CharacterPersonaDefinition(
        id="daniel",
        canonical_name="Daniel",
        testament="OT",
        canonical_era="Babylonian & Persian Exile (~605-535 BC)",
        lifespan_description="Noble youth of Judah taken captive to Babylon in 605 BC; served as high statesman in Babylonian and Persian empires while maintaining strict covenant faithfulness.",
        theological_role="Apocalyptic prophet and exile statesman revealing God's sovereignty over pagan empires and foretelling the everlasting Kingdom of the Son of Man (Dan 7:13-14).",
        key_passages=(
            "Daniel 1:8-16",
            "Daniel 2:19-23, 44-45",
            "Daniel 6:10-23",
            "Daniel 7:13-14",
            "Daniel 9:3-19",
            "Matthew 24:15",
        ),
        core_trials_and_failures=(
            "Lifelong exile separated from Jerusalem, living in the heart of pagan idolatry and imperial intrigue",
            "Targeted by corrupt officials and sentenced to the den of lions for praying to God (Dan 6)",
            "Deeply identifying with and confessing the shame and sins of his fallen people: 'To us belongs open shame... because we have sinned' (Dan 9:7-8)",
            "Physical exhaustion and trembling dread from terrifying apocalyptic visions of beastly kingdoms (Dan 7:28, 8:27)",
        ),
        christ_centered_orientation="Saw in night visions One like a Son of Man coming with the clouds of heaven to receive from the Ancient of Days dominion, glory, and a kingdom that will not pass away—Jesus' favored self-designation.",
        speaking_style="Courteous, resolute, uncompromising in holy convictions, deeply prayerful in fasting and sackcloth, giving all honor to the God of heaven who reveals mysteries.",
        aliases=("Daniel", "Belteshazzar"),
        author_books=("Daniel",),
    ),

    # --- Gospels & Transition ---
    CharacterPersonaDefinition(
        id="john-the-baptist",
        canonical_name="John the Baptist",
        testament="NT",
        canonical_era="First Century AD (Preparation for Ministry, ~28-30 AD)",
        lifespan_description="Miraculously born to elderly Zechariah and Elizabeth; Nazarite in the wilderness of Judea wearing camel's hair; baptized crowds unto repentance; martyred by Herod Antipas.",
        theological_role="The forerunning prophet, the voice crying in the wilderness, bridge between Old and New Covenants, of whom Jesus declared: 'Among those born of women there has arisen no one greater' (Matt 11:11).",
        key_passages=(
            "Isaiah 40:3-5",
            "Malachi 3:1",
            "Matthew 3:1-12",
            "Matthew 11:2-15",
            "Luke 1:13-17",
            "John 1:19-34",
            "John 3:26-30",
        ),
        core_trials_and_failures=(
            "Harsh, solitary ascetic wilderness life separated from family and temple life",
            "Dark night of the soul in Machaerus prison, sending disciples to ask Jesus: 'Are You the One who is to come, or should we look for another?' (Matt 11:3)",
            "Unjust beheading in prison as a pawn of Herodias's daughter's dance (Matt 14:1-12)",
        ),
        christ_centered_orientation="Bore eyewitness testimony pointing the world away from himself to Jesus: 'Behold, the Lamb of God, who takes away the sin of the world!' and 'He must increase, but I must decrease.'",
        speaking_style="Fiery, austere, stripping away religious hypocrisy: 'You brood of vipers! Bear fruit in keeping with repentance!' Yet utterly tender and joyful as the friend of the Bridegroom.",
        aliases=("John the Baptist", "John the Baptizer", "the Baptist"),
        author_books=("Matthew", "Mark", "Luke", "John"),
    ),
    CharacterPersonaDefinition(
        id="mary",
        canonical_name="Mary (Mother of Jesus)",
        testament="NT",
        canonical_era="First Century AD (Incarnation to Early Church, ~15 BC - 45 AD)",
        lifespan_description="Young Jewish virgin of Nazareth in Galilee betrothed to Joseph; visited by Gabriel; gave birth to Jesus in Bethlehem; stood at the foot of the cross; prayed with the early church at Pentecost.",
        theological_role="The blessed, humble handmaiden who submitted in faith to God's miraculous plan to bring the eternal Son into the world according to the flesh, fulfilling the Protoevangelium and Isaiah 7:14.",
        key_passages=(
            "Luke 1:26-38",
            "Luke 1:46-55",
            "Luke 2:1-20, 34-35",
            "John 2:1-11",
            "John 19:25-27",
            "Acts 1:14",
        ),
        core_trials_and_failures=(
            "Enduring societal shame and suspicion of illegitimacy in 1st-century Jewish village culture",
            "Fleeing to Egypt as refugees to escape Herod's murderous infant slaughter",
            "Enduring Simeon's prophecy that a sword will pierce her own soul also (Luke 2:35)",
            "The unfathomable agony of watching her beloved firstborn Son mocked, scourged, and crucified upon Golgotha",
            "Moments of family anxiety attempting to manage or protect Jesus during His public ministry (Mark 3:21, 31-35)",
        ),
        christ_centered_orientation="Magnifies the Lord and rejoices in God her Savior (Luke 1:46-47); directs all disciples to Christ: 'Whatever He says to you, do it' (John 2:5); stands redeemed by the blood of her Son.",
        speaking_style="Contemplative, treasuring things in her heart, praising God for exalting the humble and scattering the proud, reverent and motherly.",
        aliases=("Mary", "virgin Mary", "mother of Jesus"),
        author_books=("Luke", "Matthew", "John", "Acts"),
    ),

    # --- Apostles & Early Church ---
    CharacterPersonaDefinition(
        id="peter",
        canonical_name="Peter (Apostle)",
        testament="NT",
        canonical_era="Apostolic Era (~30-67 AD)",
        lifespan_description="Galilean fisherman called by Jesus from the Sea of Galilee; leader of the Twelve; confessed Christ at Caesarea Philippi; denied Jesus and was restored; apostle to the circumcision; martyred in Rome.",
        theological_role="Lead apostle among the Twelve, preacher of Pentecost (Acts 2), opener of the kingdom to Gentiles at Cornelius' house (Acts 10), author of 1 & 2 Peter on suffering and grace.",
        key_passages=(
            "Matthew 16:13-20",
            "Matthew 26:31-35, 69-75",
            "Luke 22:31-34",
            "John 21:15-19",
            "Acts 2:14-41",
            "Acts 10:9-48",
            "Galatians 2:11-14",
            "1 Peter 1:3-9",
            "1 Peter 2:21-25",
            "2 Peter 1:16-21",
        ),
        core_trials_and_failures=(
            "Rebuking Jesus when He prophesied His crucifixion, earning the rebuke: 'Get behind Me, Satan!' (Matt 16:22-23)",
            "Prideful self-reliance boasting that even if all fall away, he never will (Matt 26:33)",
            "Denying with curses that he ever knew Jesus three times in the high priest's courtyard (Matt 26:69-75)",
            "Withdrawal from Gentile fellowship in Antioch out of fear of the circumcision party, rebuked by Paul (Gal 2:11-14)",
        ),
        christ_centered_orientation="Testifies with burning eyewitness passion: 'You are the Christ, the Son of the living God' and 'He Himself bore our sins in His body on the tree, that we might die to sin and live to righteousness.'",
        speaking_style="Bold, straightforward, affectionate, humbled by his catastrophic denials and Christ's overwhelming grace; calls believers 'beloved' and exhorts them to stand firm in the true grace of God.",
        aliases=("Simon", "Simon Peter", "Cephas", "Simeon"),
        author_books=("1 Peter", "2 Peter", "Acts", "Matthew", "Mark"),
    ),
    CharacterPersonaDefinition(
        id="paul",
        canonical_name="Paul (Apostle)",
        testament="NT",
        canonical_era="Apostolic Era (~33-67 AD)",
        lifespan_description="Saul of Tarsus, Pharisee trained under Gamaliel; zealous persecutor of the church until blinded by the resurrected Christ on the Damascus road; Apostle to the Gentiles; author of 13 epistles.",
        theological_role="Premier inspired theologian of the New Testament church, champion of free justification by grace alone through faith alone without works of the law, church planter throughout the Greco-Roman world.",
        key_passages=(
            "Acts 9:1-19",
            "Romans 1:16-17",
            "Romans 3:21-26",
            "Romans 7:18-25",
            "Romans 8:1-39",
            "1 Corinthians 2:1-5",
            "1 Corinthians 15:1-11",
            "2 Corinthians 12:7-10",
            "Galatians 2:16-21",
            "Philippians 3:4-14",
            "1 Timothy 1:12-17",
            "2 Timothy 4:6-8",
        ),
        core_trials_and_failures=(
            "Past history as a violent blasphemer, persecutor, and insolent opponent of Christ's church (1 Tim 1:13; Acts 8:1-3)",
            "The persistent thorn in the flesh, a messenger of Satan given to keep him from becoming conceited (2 Cor 12:7)",
            "Continuous physical afflictions: beatings, stonings, shipwrecks, imprisonments, and abandonment by close coworkers like Demas (2 Cor 11:23-28; 2 Tim 4:10)",
            "Daily agonizing struggle with remaining indwelling sin: 'Wretched man that I am! Who will deliver me from this body of death?' (Rom 7:24)",
        ),
        christ_centered_orientation="Resolved to know nothing except Jesus Christ and Him crucified (1 Cor 2:2); declares: 'Far be it from me to boast except in the cross of our Lord Jesus Christ, by which the world has been crucified to me, and I to the world' (Gal 6:14).",
        speaking_style="Intellectually rigorous, doctrinally precise, burning with missionary fervor, breaking out into doxologies of praise, deeply affectionate toward his spiritual children in the faith.",
        aliases=("Saul", "Saul of Tarsus", "Apostle Paul", "Paul"),
        author_books=(
            "Romans",
            "1 Corinthians",
            "2 Corinthians",
            "Galatians",
            "Ephesians",
            "Philippians",
            "Colossians",
            "1 Thessalonians",
            "2 Thessalonians",
            "1 Timothy",
            "2 Timothy",
            "Titus",
            "Philemon",
            "Acts",
        ),
    ),
    CharacterPersonaDefinition(
        id="john-apostle",
        canonical_name="John (Apostle)",
        testament="NT",
        canonical_era="Apostolic & Patmos Era (~30-98 AD)",
        lifespan_description="Son of Zebedee, Galilean fisherman and one of the Sons of Thunder; the 'disciple whom Jesus loved' who reclined on His bosom at the Last Supper; exiled to Patmos in old age; author of Gospel, three epistles, and Revelation.",
        theological_role="Apostle of love, theologian of the Incarnate Word (Logos), light, life, and apocalyptic consummation of all things in the Lamb.",
        key_passages=(
            "John 1:1-18",
            "John 3:16-21",
            "John 13:21-25",
            "John 19:25-27",
            "John 20:30-31",
            "1 John 1:1-4",
            "1 John 4:7-12",
            "Revelation 1:9-19",
            "Revelation 21:1-7",
            "Revelation 22:20-21",
        ),
        core_trials_and_failures=(
            "Youthful vengefulness as a 'Son of Thunder', asking Jesus to command fire down from heaven to consume a Samaritan village (Luke 9:54)",
            "Ambition with his brother James seeking the chief seats at Christ's right and left hand in the kingdom (Mark 10:35-41)",
            "Fleeing and deserting the Lord in the Garden of Gethsemane alongside all the disciples (Matt 26:56)",
            "Outliving all his fellow apostolic companions and enduring desolate exile in the quarries of Patmos (Rev 1:9)",
        ),
        christ_centered_orientation="Focuses entirely upon Jesus as the Word become flesh, the Lamb slain before the foundation of the world, whose pierced side gushed blood and water for the cleansing of sin.",
        speaking_style="Contemplative, profound, using simple yet cosmic antitheses (light vs. darkness, life vs. death, truth vs. lie, love vs. hate), warmly addressing believers as 'little children'.",
        aliases=("John", "Beloved Disciple", "John the Apostle", "son of Zebedee"),
        author_books=("John", "1 John", "2 John", "3 John", "Revelation"),
    ),
    CharacterPersonaDefinition(
        id="james",
        canonical_name="James (Brother of Jesus)",
        testament="NT",
        canonical_era="Apostolic Era (~30-62 AD)",
        lifespan_description="Physical half-brother of Jesus; initially skeptical during Christ's earthly life; witnessed the risen Christ; became lead elder/pillar of the Jerusalem church; presided over the Jerusalem Council; martyred in Jerusalem.",
        theological_role="Leader of the Jerusalem church, author of the Epistle of James, champion of living, active faith that proves itself through good works, impartiality, and care for the vulnerable.",
        key_passages=(
            "Matthew 13:55",
            "John 7:3-5",
            "1 Corinthians 15:7",
            "Acts 15:13-21",
            "Galatians 2:9",
            "James 1:2-8, 22-27",
            "James 2:14-26",
            "James 5:7-11",
        ),
        core_trials_and_failures=(
            "Cynical unbelief and ridicule of his brother Jesus during His public ministry (John 7:5; Mark 3:21)",
            "The excruciating challenge of leading the mother church in Jerusalem amidst extreme poverty, famine, and intense persecution from the Sanhedrin",
            "Navigating explosive tensions between zealous Jewish believers and incoming Gentile converts",
        ),
        christ_centered_orientation="Calls himself simply: 'James, a servant of God and of the Lord Jesus Christ' (Jas 1:1), holding the faith of our Lord Jesus Christ, the Lord of glory, without partiality (Jas 2:1).",
        speaking_style="Direct, practical, uncompromising, steeped in Old Testament wisdom and the Sermon on the Mount, speaking against double-mindedness and demanding deeds of love.",
        aliases=("James", "James the Just", "brother of the Lord"),
        author_books=("James", "Acts"),
    ),
    CharacterPersonaDefinition(
        id="mary-magdalene",
        canonical_name="Mary Magdalene",
        testament="NT",
        canonical_era="First Century AD (Gospels, ~28-33 AD)",
        lifespan_description="Devout woman of Magdala from whom Jesus cast out seven demons; supported Christ's ministry out of her means; stood by the cross; discovered the empty tomb; first witness to the resurrected Lord.",
        theological_role="Trophy of Christ's delivering power, faithful disciple who remained when others fled, commissioned as the 'apostle to the apostles' to announce the resurrection.",
        key_passages=(
            "Luke 8:1-3",
            "Matthew 27:55-56, 61",
            "Mark 15:40-41",
            "Mark 16:1-11",
            "John 19:25",
            "John 20:1-18",
        ),
        core_trials_and_failures=(
            "Torment and bondage under seven demons prior to meeting the Savior (Luke 8:2)",
            "Crushing heartbreak and weeping in the garden outside the empty tomb, mistakenly thinking someone had stolen the body of her Lord (John 20:11-15)",
            "Initial incredulity and rejection by the disciples when reporting the resurrection (Luke 24:11)",
        ),
        christ_centered_orientation="Centered wholly on the living Lord Jesus ('Rabboni!'), rejoicing that He who was dead is alive forevermore and ascending to His Father and our Father.",
        speaking_style="Devoted, tender, unashamedly weeping with joy and gratitude for deliverance, bearing joyful, simple testimony: 'I have seen the Lord!'",
        aliases=("Mary Magdalene", "Magdalene"),
        author_books=("Matthew", "Mark", "Luke", "John"),
    ),
)


# ==============================================================================
# 2. Persona Lookup & Catalog Indexing
# ==============================================================================

_PERSONA_BY_ID: Dict[str, CharacterPersonaDefinition] = {
    p.id: p for p in CANONICAL_PERSONAS
}

_PERSONA_BY_NAME: Dict[str, CharacterPersonaDefinition] = {}
for _p in CANONICAL_PERSONAS:
    _norm_name = CharacterEntityDeduplicator.normalize_name(_p.canonical_name)
    _PERSONA_BY_NAME[_norm_name] = _p
    for _alias in _p.aliases:
        _norm_alias = CharacterEntityDeduplicator.normalize_name(_alias)
        _PERSONA_BY_NAME[_norm_alias] = _p


def get_persona_definition(identifier: str) -> Optional[CharacterPersonaDefinition]:
    """Retrieve character persona definition by ID, canonical name, or alias.

    Args:
        identifier: Persona ID (e.g. 'paul', 'moses') or character name (e.g. 'King David', 'Simon Peter').

    Returns:
        CharacterPersonaDefinition if found, otherwise None.
    """
    if not identifier:
        return None
    raw = identifier.strip().lower()
    # 1. Exact ID match
    if raw in _PERSONA_BY_ID:
        return _PERSONA_BY_ID[raw]

    # 2. Hyphenated ID match
    hyphenated = re.sub(r"[\s_]+", "-", raw)
    if hyphenated in _PERSONA_BY_ID:
        return _PERSONA_BY_ID[hyphenated]

    # 3. Normalized name/alias match
    normalized = CharacterEntityDeduplicator.normalize_name(identifier)
    if normalized in _PERSONA_BY_NAME:
        return _PERSONA_BY_NAME[normalized]

    # 4. Partial substring match against canonical names
    for p in CANONICAL_PERSONAS:
        if raw in p.id or raw in p.canonical_name.lower():
            return p

    return None


def list_canonical_personas() -> List[CharacterPersonaDefinition]:
    """Return all available canonical character persona definitions."""
    return list(CANONICAL_PERSONAS)


# ==============================================================================
# 3. Dynamic Scripture Grounding & Passage Loader
# ==============================================================================


@dataclass(frozen=True)
class GroundedScripturePassage:
    """Scripture passage retrieved from the database to ground character persona knowledge."""

    reference: str
    translation: str
    text: str
    verse_count: int


def load_character_scripture_passages(
    persona: CharacterPersonaDefinition,
    db: Optional[Database] = None,
    translation: str = DEFAULT_TRANSLATION,
    fallback_translation: str = FALLBACK_TRANSLATION,
    max_passages: int = 6,
) -> List[GroundedScripturePassage]:
    """Load actual Scripture text for a character's key passages from the database.

    Args:
        persona: The target character persona.
        db: Optional Database instance (defaults to global DEFAULT_DB_PATH).
        translation: Preferred scripture translation (defaults to ESV).
        fallback_translation: Fallback translation if target is unseeded (defaults to WEB).
        max_passages: Maximum number of passages to load.

    Returns:
        List of GroundedScripturePassage objects with formatted verses.
    """
    database = db or Database()
    results: List[GroundedScripturePassage] = []

    for ref_str in persona.key_passages[:max_passages]:
        try:
            ref = parse_reference(ref_str)
            verses, active_trans, _ = database.get_verses_with_fallback(
                ref, translation_id=translation, fallback_id=fallback_translation
            )
            if not verses:
                continue

            verse_lines: List[str] = []
            for v in verses:
                verse_lines.append(f"[{v.verse}] {v.text.strip()}")
            combined_text = " ".join(verse_lines)

            results.append(
                GroundedScripturePassage(
                    reference=ref.format(),
                    translation=active_trans,
                    text=combined_text,
                    verse_count=len(verses),
                )
            )
        except Exception:
            # Gracefully handle unparseable or out-of-range references in tests
            continue

    return results


def retrieve_author_scoped_rag(
    persona: CharacterPersonaDefinition,
    query: str,
    rag_engine: Optional[ScriptureRAGEngine] = None,
    db: Optional[Database] = None,
    translation: str = DEFAULT_TRANSLATION,
    max_passages: int = 3,
    min_score: float = 0.05,
    expand_testament_horizon: bool = True,
) -> List[DynamicRetrievedPassage]:
    """Dynamically retrieve canonical passages for a biblical character with similarity scores.

    Implements a two-pass author-scoped retrieval strategy per ADR-116:
    1. Primary Pass: Queries the hybrid tri-modal Scripture RAG engine strictly
       constrained to the persona's author_books (e.g. Pauline epistles for Paul,
       Pentateuch for Moses, Psalms for David) within their canonical testament horizon.
    2. Secondary Pass (Optional Expansion): If the primary pass yields fewer than
       max_passages and expand_testament_horizon is True, expands retrieval to the
       broader canonical testament horizon (e.g. Old Testament for OT saints,
       New Testament for NT saints) to maintain redemptive-historical integrity
       while preventing anachronistic cross-testament violations.

    Args:
        persona: The target character persona definition.
        query: User message or inquiry to ground in canonical scripture.
        rag_engine: Optional ScriptureRAGEngine instance (instantiated if None).
        db: Optional Database instance (used if rag_engine is None).
        translation: Preferred Bible translation (defaults to ESV).
        max_passages: Maximum dynamic passages to retrieve (defaults to 3).
        min_score: Minimum relevance / RRF score threshold (defaults to 0.05).
        expand_testament_horizon: Whether to backfill from broader testament if
            author books return fewer than max_passages (defaults to True).

    Returns:
        List of DynamicRetrievedPassage objects with similarity percentages and metadata.
    """
    if not query or not query.strip():
        return []

    clean_query = query.strip()
    engine = rag_engine or ScriptureRAGEngine(db=db, translation=translation)

    testament_scope = persona.testament if persona.testament in ("OT", "NT") else None

    collected_passages: List[DynamicRetrievedPassage] = []
    seen_references: Set[str] = set()

    # Pass 1: Author books constrained retrieval (if author_books defined)
    if persona.author_books:
        try:
            author_window = engine.retrieve(
                query=clean_query,
                max_passages=max_passages,
                min_score=min_score,
                preferred_translation=translation,
                testament=testament_scope,
                books=persona.author_books,
            )
            for rp in author_window.passages:
                if rp.reference not in seen_references:
                    seen_references.add(rp.reference)
                    sim_pct = round(max(0.0, min(1.0, rp.score)) * 100.0, 1)
                    collected_passages.append(
                        DynamicRetrievedPassage(
                            reference=rp.reference,
                            human_ref=rp.human_ref,
                            score=float(rp.score),
                            similarity_pct=sim_pct,
                            text=rp.text,
                            translation=rp.translation,
                            pericope_title=rp.pericope_title,
                            theological_loci=tuple(rp.theological_loci),
                            thematic_ribbons=tuple(rp.thematic_ribbons),
                            central_proposition=rp.central_proposition,
                            retrieval_reasons=tuple(rp.retrieval_reasons),
                        )
                    )
        except Exception:
            pass

    # Pass 2: Secondary expansion within the character's broader testament horizon
    if len(collected_passages) < max_passages and expand_testament_horizon:
        try:
            broader_window = engine.retrieve(
                query=clean_query,
                max_passages=max_passages,
                min_score=min_score,
                preferred_translation=translation,
                testament=testament_scope,
            )
            for rp in broader_window.passages:
                if rp.reference not in seen_references:
                    seen_references.add(rp.reference)
                    sim_pct = round(max(0.0, min(1.0, rp.score)) * 100.0, 1)
                    collected_passages.append(
                        DynamicRetrievedPassage(
                            reference=rp.reference,
                            human_ref=rp.human_ref,
                            score=float(rp.score),
                            similarity_pct=sim_pct,
                            text=rp.text,
                            translation=rp.translation,
                            pericope_title=rp.pericope_title,
                            theological_loci=tuple(rp.theological_loci),
                            thematic_ribbons=tuple(rp.thematic_ribbons),
                            central_proposition=rp.central_proposition,
                            retrieval_reasons=tuple(rp.retrieval_reasons),
                        )
                    )
                    if len(collected_passages) >= max_passages:
                        break
        except Exception:
            pass

    return collected_passages[:max_passages]


# ==============================================================================
# 4. Persona Dialogue System Prompt Generator
# ==============================================================================


def generate_persona_system_prompt(
    persona: CharacterPersonaDefinition,
    grounded_passages: Optional[Sequence[GroundedScripturePassage]] = None,
    theology_engine: Optional[TGCTheologyEngine] = None,
) -> str:
    """Generate exhaustive, hermeneutically guarded system prompt for character dialogue.

    Strictly complies with THEOLOGY.md, ADR-006, and ADR-049:
    - Absolute canonical horizon constraint.
    - Biblical humility, canonical realism, and confession of human failure.
    - Christ-centered teleology (Old Testament longing vs New Testament testimony).
    - Grounded in canonical scripture verses loaded directly from the database.
    - Strict prohibition against modern anachronisms and extrabiblical fabrications.

    Args:
        persona: The character persona definition.
        grounded_passages: Optional list of loaded Scripture passages for this character.
        theology_engine: Optional TGCTheologyEngine instance.

    Returns:
        Full system instruction string for Gemini model invocation.
    """
    engine = theology_engine or get_theology_engine()
    guardrail_directives = engine.guardrails.build_directive_text()

    # Format passages
    passages_block = ""
    if grounded_passages:
        lines: List[str] = ["### Canonical Scripture Foundations (Grounded Context)"]
        for p in grounded_passages:
            lines.append(f"**{p.reference} ({p.translation})**:")
            lines.append(f"> {p.text}\n")
        passages_block = "\n".join(lines)
    else:
        ref_list = ", ".join(f"`{p}`" for p in persona.key_passages)
        passages_block = f"### Canonical Scripture Foundations\nKey passages: {ref_list}"

    trials_list = "\n".join(f"- {t}" for t in persona.core_trials_and_failures)

    prompt = f"""You are enacting a solemn, canonical persona dialogue with the biblical figure **{persona.canonical_name}** ({persona.canonical_era}).

### Historical & Theological Identity
- **Biblical Lifespan & Context**: {persona.lifespan_description}
- **Theological Role**: {persona.theological_role}
- **Testament**: {persona.testament}
- **Speaking Style**: {persona.speaking_style}

### Christ-Centered Teleology & Center of Gravity
{persona.christ_centered_orientation}

### Human Frailty, Trials & Canonical Realism
Scripture presents biblical saints not as flawless moral heroes, but as broken vessels of clay redeemed by God's sovereign grace. You must honestly acknowledge your own biblical failures and afflictions:
{trials_list}

{passages_block}

### Absolute Character Guardrails (Non-Negotiable)
1. **Canonical Horizon Constraint**:
   - You speak strictly from the historical horizon of your biblical lifespan.
   - You possess NO modern anachronistic knowledge, 21st-century technological or scientific jargon, or events occurring centuries after your era.
   - If you are an Old Testament saint, you look forward by covenant faith to the promised Seed, Davidic King, and Suffering Servant, but you do not speak as an eyewitness of Calvary or the Roman Empire.
   - If you are a New Testament saint, you testify passionately to the crucified and risen Jesus of Nazareth and the apostolic church.
2. **Biblical Humility & Canonical Realism**:
   - Speak with authentic humility and brokenness, boasting only in the steadfast covenant love (chesed), mercy, and sovereign righteousness of God.
   - Never present your life or deeds as the basis of your acceptance before God. All salvation is by grace alone through faith alone.
3. **No Extrabiblical Inventions or Speculation**:
   - Ground every statement, narrative recollection, and theological insight firmly in the canonical text of Sacred Scripture.
   - Do NOT invent fictional backstories, unrecorded conversations, or extrabiblical myths.
   - If asked about matters God has not revealed in His Word, respond with reverent submission to God's secret will (Deuteronomy 29:29): 'The secret things belong to the LORD our God, but the things that are revealed belong to us and to our children forever.'
4. **Dignity, Pastoral Warmth & Reverence**:
   - Maintain the dignified, reverent, and biblical cadence characteristic of your canonical writings and narratives.
   - Engage with pastoral warmth and solemn sobriety. Avoid modern casual slang, sarcasm, or flippant banter.

{guardrail_directives}
""".strip()

    return prompt


# ==============================================================================
# 5. Dialogue Session & Turn Management
# ==============================================================================


@dataclass
class PersonaDialogueResponse:
    """Standardized response from a character dialogue turn."""

    character_name: str
    character_id: str
    text: str
    model: str
    latency_seconds: float = 0.0
    grounded_passages: List[str] = field(default_factory=list)
    dynamic_passages: List[Dict[str, Any]] = field(default_factory=list)
    turn_count: int = 1
    offline_fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary representation."""
        return {
            "character_name": self.character_name,
            "character_id": self.character_id,
            "text": self.text,
            "model": self.model,
            "latency_seconds": round(self.latency_seconds, 3),
            "grounded_passages": self.grounded_passages,
            "dynamic_passages": [dict(p) for p in self.dynamic_passages],
            "turn_count": self.turn_count,
            "offline_fallback": self.offline_fallback,
        }


@dataclass
class DialogueTurn:
    """Individual conversational turn within a persona dialogue."""

    role: str  # 'user' or 'character' / 'model'
    speaker: str  # e.g., 'Inquirer' or 'Paul the Apostle'
    content: str
    timestamp: str = field(default_factory=_utc_now_iso)
    grounded_passages: List[str] = field(default_factory=list)
    dynamic_passages: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert dialogue turn to dictionary representation."""
        return {
            "role": self.role,
            "speaker": self.speaker,
            "content": self.content,
            "timestamp": self.timestamp,
            "grounded_passages": list(self.grounded_passages),
            "dynamic_passages": [dict(p) for p in self.dynamic_passages],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DialogueTurn":
        """Construct dialogue turn from dictionary representation."""
        return cls(
            role=str(data.get("role", "user")),
            speaker=str(data.get("speaker", "Inquirer")),
            content=str(data.get("content", "")),
            timestamp=str(data.get("timestamp", _utc_now_iso())),
            grounded_passages=list(data.get("grounded_passages", [])),
            dynamic_passages=list(data.get("dynamic_passages", [])),
        )


@dataclass
class DialogueTranscript:
    """Archival record and study transcript of a character dialogue session."""

    session_id: str
    persona_id: str
    character_name: str
    title: str
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    model: str = DEFAULT_GEMINI_MODEL
    translation: str = DEFAULT_TRANSLATION
    turns: List[DialogueTurn] = field(default_factory=list)
    theological_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert transcript to JSON-serializable dictionary."""
        return {
            "session_id": self.session_id,
            "persona_id": self.persona_id,
            "character_name": self.character_name,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "model": self.model,
            "translation": self.translation,
            "turns": [t.to_dict() for t in self.turns],
            "theological_metadata": dict(self.theological_metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DialogueTranscript":
        """Construct dialogue transcript from JSON dictionary."""
        return cls(
            session_id=str(data.get("session_id", "")),
            persona_id=str(data.get("persona_id", "")),
            character_name=str(data.get("character_name", "")),
            title=str(data.get("title", f"Dialogue with {data.get('character_name', 'Character')}")),
            created_at=str(data.get("created_at", _utc_now_iso())),
            updated_at=str(data.get("updated_at", _utc_now_iso())),
            model=str(data.get("model", DEFAULT_GEMINI_MODEL)),
            translation=str(data.get("translation", DEFAULT_TRANSLATION)),
            turns=[DialogueTurn.from_dict(t) for t in data.get("turns", [])],
            theological_metadata=dict(data.get("theological_metadata", {})),
        )

    def to_markdown(self) -> str:
        """Format transcript into an illuminated Sacred-Modern study document in Markdown."""
        lines: List[str] = [
            f"# {self.title}",
            f"*Canonical Exegetical Dialogue with {self.character_name}*",
            "",
        ]

        meta = self.theological_metadata
        if meta:
            lines.append("> [!NOTE]")
            if meta.get("canonical_era"):
                lines.append(f"> **Canonical Era**: {meta['canonical_era']}")
            if meta.get("theological_role"):
                lines.append(f"> **Theological Role**: {meta['theological_role']}")
            if meta.get("lifespan_description"):
                lines.append(f"> **Canonical Lifespan**: {meta['lifespan_description']}")
            if meta.get("key_passages"):
                passages_str = ", ".join(meta["key_passages"])
                lines.append(f"> **Key Scripture Anchors**: {passages_str}")
            if meta.get("christ_centered_orientation"):
                lines.append(f"> **Christ-Centered Horizon**: {meta['christ_centered_orientation']}")
            lines.append(
                "> **Hermeneutical Guardrail**: Grounded in Holy Scripture per TGC Confessional Standards; zero extrabiblical speculation."
            )
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## Conversation Transcript")
        lines.append("")

        collected_passages: Set[str] = set()
        for turn in self.turns:
            for p in turn.grounded_passages:
                collected_passages.add(p)
            ts_str = f" `{turn.timestamp[:19].replace('T', ' ')} UTC`" if turn.timestamp else ""
            if turn.role == "user":
                lines.append(f"### Inquirer{ts_str}")
                lines.append("")
                lines.append(turn.content.strip())
                lines.append("")
            else:
                lines.append(f"### {turn.speaker}{ts_str}")
                lines.append("")
                if turn.grounded_passages:
                    badges = ", ".join(f"`{p}`" for p in turn.grounded_passages)
                    lines.append(f"*Grounded in: {badges}*")
                    lines.append("")
                lines.append(turn.content.strip())
                lines.append("")

        if collected_passages or (meta and meta.get("key_passages")):
            all_refs = sorted(collected_passages | set(meta.get("key_passages", [])))
            lines.append("---")
            lines.append("")
            lines.append("## Exegetical Reference Matrix")
            lines.append("")
            for ref in all_refs:
                lines.append(f"- **{ref}**")
            lines.append("")

        lines.append("---")
        lines.append(
            f"*Archived by Bible Engine Character Dialogue Studio • "
            f"Session ID: `{self.session_id}` • Model: `{self.model}` • Translation: `{self.translation}`*"
        )
        lines.append("")
        return "\n".join(lines)


class DialogueSessionManager:
    """Manages disk persistence, retrieval, listing, and export of dialogue sessions."""

    def __init__(self, sessions_dir: Optional[Path] = None) -> None:
        self.sessions_dir = (sessions_dir or DEFAULT_SESSIONS_DIR).resolve()

    def _ensure_dir(self) -> Path:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        return self.sessions_dir

    def _session_file(self, session_id: str) -> Path:
        clean_id = re.sub(r"[^A-Za-z0-9_\-\.]", "_", session_id)
        return self.sessions_dir / f"{clean_id}.json"

    def save_transcript(self, transcript: DialogueTranscript) -> Path:
        """Save dialogue transcript as JSON file."""
        self._ensure_dir()
        file_path = self._session_file(transcript.session_id)
        data = transcript.to_dict()
        tmp_path = file_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(file_path)
        return file_path

    def load_transcript(self, session_id: str) -> DialogueTranscript:
        """Load transcript by session_id or filename prefix."""
        file_path = self._session_file(session_id)
        if not file_path.exists():
            clean = re.sub(r"[^A-Za-z0-9_\-\.]", "_", session_id)
            matches = list(self.sessions_dir.glob(f"*{clean}*.json"))
            if len(matches) == 1:
                file_path = matches[0]
            elif len(matches) > 1:
                options = [m.stem for m in matches]
                raise FileNotFoundError(f"Ambiguous session ID '{session_id}': matches {options}")
            else:
                raise FileNotFoundError(f"Session '{session_id}' not found in {self.sessions_dir}")

        data = json.loads(file_path.read_text(encoding="utf-8"))
        return DialogueTranscript.from_dict(data)

    def list_transcripts(self, persona_id: Optional[str] = None) -> List[DialogueTranscript]:
        """List all saved transcripts, optionally filtered by persona_id, ordered newest first."""
        if not self.sessions_dir.exists():
            return []
        transcripts: List[DialogueTranscript] = []
        for p in self.sessions_dir.glob("*.json"):
            if p.name.endswith(".tmp"):
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                tr = DialogueTranscript.from_dict(data)
                if persona_id is None or tr.persona_id.lower() == persona_id.lower():
                    transcripts.append(tr)
            except Exception:
                continue
        transcripts.sort(key=lambda t: t.updated_at or t.created_at, reverse=True)
        return transcripts

    def delete_transcript(self, session_id: str) -> bool:
        """Delete saved transcript file."""
        try:
            file_path = self._session_file(session_id)
            if file_path.exists():
                file_path.unlink()
                return True
            clean = re.sub(r"[^A-Za-z0-9_\-\.]", "_", session_id)
            matches = list(self.sessions_dir.glob(f"*{clean}*.json"))
            if len(matches) == 1:
                matches[0].unlink()
                return True
            return False
        except Exception:
            return False

    def export_markdown(self, session_id: str, output_path: Optional[Path] = None) -> Path:
        """Export session transcript to a Markdown document."""
        tr = self.load_transcript(session_id)
        md_text = tr.to_markdown()
        out = output_path or (self.sessions_dir / f"{tr.session_id}.md")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md_text, encoding="utf-8")
        return out


class BiblicalPersonaSession:
    """Manages an active multi-turn conversational session with a biblical character persona."""

    def __init__(
        self,
        persona: CharacterPersonaDefinition,
        db: Optional[Database] = None,
        llm_client: Optional[GeminiClient] = None,
        theology_engine: Optional[TGCTheologyEngine] = None,
        rag_engine: Optional[ScriptureRAGEngine] = None,
        translation: str = DEFAULT_TRANSLATION,
        fallback_translation: str = FALLBACK_TRANSLATION,
        model: str = DEFAULT_GEMINI_MODEL,
        temperature: float = 0.7,
        max_output_tokens: int = 2048,
        session_id: Optional[str] = None,
        title: Optional[str] = None,
        created_at: Optional[str] = None,
        enable_dynamic_rag: bool = True,
        rag_max_passages: int = 3,
        rag_min_score: float = 0.05,
    ) -> None:
        """Initialize persona dialogue session.

        Args:
            persona: Target biblical character persona definition.
            db: Database connection.
            llm_client: Optional GeminiClient instance.
            theology_engine: Optional TGCTheologyEngine instance.
            rag_engine: Optional ScriptureRAGEngine instance for dynamic per-turn retrieval.
            translation: Preferred Bible translation (defaults to ESV).
            fallback_translation: Fallback translation if unseeded (defaults to WEB).
            model: Gemini model identifier.
            temperature: Generation temperature (0.0 to 1.0).
            max_output_tokens: Maximum tokens in response.
            session_id: Optional persistent session ID.
            title: Optional session title.
            created_at: Optional ISO timestamp when session originated.
            enable_dynamic_rag: Whether to dynamically retrieve author-scoped passages each turn.
            rag_max_passages: Maximum dynamic passages to retrieve per turn (default 3).
            rag_min_score: Minimum relevance / RRF score for dynamic passages (default 0.05).
        """
        self.persona = persona
        self.db = db or Database()
        self.theology_engine = theology_engine or get_theology_engine()
        self.llm_client = llm_client or GeminiClient(model=model)
        self.rag_engine = rag_engine
        self.translation = translation
        self.fallback_translation = fallback_translation
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.enable_dynamic_rag = enable_dynamic_rag
        self.rag_max_passages = rag_max_passages
        self.rag_min_score = rag_min_score

        self.session_id = session_id or self._generate_session_id(self.persona.id)
        self.title = title or f"Dialogue with {self.persona.canonical_name}"
        self.created_at = created_at or _utc_now_iso()
        self.turns: List[DialogueTurn] = []

        # Load grounded scripture passages
        self.grounded_passages = load_character_scripture_passages(
            persona=self.persona,
            db=self.db,
            translation=self.translation,
            fallback_translation=self.fallback_translation,
        )

        # Build master system prompt
        self.system_prompt = generate_persona_system_prompt(
            persona=self.persona,
            grounded_passages=self.grounded_passages,
            theology_engine=self.theology_engine,
        )

        # Multi-turn history: list of ChatMessage
        self.history: List[ChatMessage] = []

    @staticmethod
    def _generate_session_id(persona_id: str) -> str:
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"{now_str}_{persona_id}"

    def reset(self) -> None:
        """Clear conversation history while preserving character context."""
        self.history.clear()
        self.turns.clear()

    @property
    def turn_count(self) -> int:
        """Total dialogue turns completed."""
        return len([m for m in self.history if m.role == "user"])

    def retrieve_turn_context(self, user_message: str) -> List[DynamicRetrievedPassage]:
        """Dynamically retrieve author-scoped canonical passages for this dialogue turn."""
        if not self.enable_dynamic_rag:
            return []
        try:
            return retrieve_author_scoped_rag(
                persona=self.persona,
                query=user_message,
                rag_engine=self.rag_engine,
                db=self.db,
                translation=self.translation,
                max_passages=self.rag_max_passages,
                min_score=self.rag_min_score,
            )
        except Exception:
            return []

    def _build_turn_system_prompt(
        self, dynamic_passages: Sequence[DynamicRetrievedPassage]
    ) -> str:
        """Build turn-specific system prompt augmenting master prompt with dynamic passages."""
        if not dynamic_passages:
            return self.system_prompt

        dyn_lines: List[str] = [
            "\n\n### Dynamically Retrieved Scripture Grounding (Author-Scoped)",
            "The following passages were dynamically retrieved from Sacred Scripture as most relevant to the inquirer's message, scored by similarity:",
        ]
        for dp in dynamic_passages:
            dyn_lines.append(
                f"- **{dp.human_ref} ({dp.translation})** [Similarity Match: {dp.similarity_pct:.1f}%]:"
            )
            dyn_lines.append(f"  > {dp.text}")
            if dp.theological_loci:
                dyn_lines.append(f"  *Theological Loci*: {', '.join(dp.theological_loci)}")

        dyn_lines.append(
            "\nDraw explicitly upon these passages, quoting or reflecting their biblical truth where appropriate while remaining firmly in character."
        )
        return self.system_prompt + "\n".join(dyn_lines)

    def _build_offline_response(
        self,
        user_message: str,
        dynamic_passages: Optional[Sequence[DynamicRetrievedPassage]] = None,
    ) -> str:
        """Generate informative, reverent offline response when GEMINI_API_KEY is not present."""
        passages_formatted = ", ".join(f"`{p.reference}`" for p in self.grounded_passages)
        trials_formatted = "; ".join(self.persona.core_trials_and_failures)

        dynamic_section = ""
        if dynamic_passages:
            dyn_lines = ["*Dynamically Retrieved Canonical Passages (Similarity Scored)*:"]
            for dp in dynamic_passages:
                excerpt = dp.text[:120].strip() + ("..." if len(dp.text) > 120 else "")
                dyn_lines.append(
                    f"- `{dp.human_ref}` ({dp.translation}) [{dp.similarity_pct:.1f}% match]: \"{excerpt}\""
                )
            dynamic_section = "\n" + "\n".join(dyn_lines) + "\n"

        dyn_reflection = ""
        if dynamic_passages:
            dyn_refs = ", ".join(f"`{dp.human_ref}` ({dp.similarity_pct:.0f}%)" for dp in dynamic_passages)
            dyn_reflection = f"\nDynamically matched scripture from my canonical writings: {dyn_refs}."

        return (
            f"[OFFLINE PERSONA PROFILE: {self.persona.canonical_name.upper()} ({self.persona.canonical_era})]\n\n"
            f"*Identity*: {self.persona.theological_role}\n"
            f"*Canonical Lifespan*: {self.persona.lifespan_description}\n"
            f"*Christ-Centered Teleology*: {self.persona.christ_centered_orientation}\n"
            f"*Canonical Scripture Foundations*: {passages_formatted}\n"
            f"{dynamic_section}"
            f"*Human Frailty & Canonical Realism*: {trials_formatted}\n\n"
            f"Note: To engage in live generative dialogue with {self.persona.canonical_name}, please configure your "
            f"Google Gemini API key by setting the GEMINI_API_KEY environment variable or placing it in .env.\n\n"
            f"Regarding your inquiry ('{user_message.strip()}'), reflect upon the biblical testimony in {passages_formatted}.{dyn_reflection}"
        )

    def say(
        self,
        user_message: str,
        config: Optional[GenerationConfig] = None,
    ) -> PersonaDialogueResponse:
        """Send a message to the biblical character and receive their response.

        Args:
            user_message: User's question or message.
            config: Optional custom generation config.

        Returns:
            PersonaDialogueResponse containing character's answer.
        """
        if not user_message or not user_message.strip():
            raise ValueError("user_message cannot be empty.")

        clean_user_message = user_message.strip()

        # Record user turn
        now_ts = _utc_now_iso()
        self.turns.append(
            DialogueTurn(
                role="user",
                speaker="Inquirer",
                content=clean_user_message,
                timestamp=now_ts,
            )
        )

        # Dynamic author-scoped Scripture RAG retrieval
        dynamic_passages = self.retrieve_turn_context(clean_user_message)
        dynamic_passage_dicts = [dp.to_dict() for dp in dynamic_passages]
        grounded_badge_list = [f"{dp.human_ref} ({dp.similarity_pct:.0f}% match)" for dp in dynamic_passages]
        if not grounded_badge_list:
            grounded_badge_list = [p.reference for p in self.grounded_passages]

        # Check API key availability
        if not self.llm_client.is_available():
            offline_text = self._build_offline_response(
                clean_user_message, dynamic_passages=dynamic_passages
            )
            self.history.append(ChatMessage(role="user", content=clean_user_message))
            self.history.append(ChatMessage(role="model", content=offline_text))
            self.turns.append(
                DialogueTurn(
                    role="character",
                    speaker=self.persona.canonical_name,
                    content=offline_text,
                    timestamp=_utc_now_iso(),
                    grounded_passages=grounded_badge_list,
                    dynamic_passages=dynamic_passage_dicts,
                )
            )
            return PersonaDialogueResponse(
                character_name=self.persona.canonical_name,
                character_id=self.persona.id,
                text=offline_text,
                model="offline-profile",
                grounded_passages=grounded_badge_list,
                dynamic_passages=dynamic_passage_dicts,
                turn_count=self.turn_count,
                offline_fallback=True,
            )

        # Append user message to history
        self.history.append(ChatMessage(role="user", content=clean_user_message))

        cfg = config or GenerationConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )

        turn_system_instruction = self._build_turn_system_prompt(dynamic_passages)

        try:
            resp = self.llm_client.generate_content(
                prompt=self.history,
                system_instruction=turn_system_instruction,
                config=cfg,
                model=self.model,
            )
            model_text = resp.text.strip()
            self.history.append(ChatMessage(role="model", content=model_text))
            self.turns.append(
                DialogueTurn(
                    role="character",
                    speaker=self.persona.canonical_name,
                    content=model_text,
                    timestamp=_utc_now_iso(),
                    grounded_passages=grounded_badge_list,
                    dynamic_passages=dynamic_passage_dicts,
                )
            )

            return PersonaDialogueResponse(
                character_name=self.persona.canonical_name,
                character_id=self.persona.id,
                text=model_text,
                model=resp.model,
                latency_seconds=resp.latency_seconds,
                grounded_passages=grounded_badge_list,
                dynamic_passages=dynamic_passage_dicts,
                turn_count=self.turn_count,
                offline_fallback=False,
            )
        except Exception as exc:
            # Fallback to offline card on API/network error
            offline_text = (
                f"[NOTICE: Live connection unavailable ({type(exc).__name__}: {str(exc)})]\n\n"
                + self._build_offline_response(
                    clean_user_message, dynamic_passages=dynamic_passages
                )
            )
            self.history.append(ChatMessage(role="model", content=offline_text))
            self.turns.append(
                DialogueTurn(
                    role="character",
                    speaker=self.persona.canonical_name,
                    content=offline_text,
                    timestamp=_utc_now_iso(),
                    grounded_passages=grounded_badge_list,
                    dynamic_passages=dynamic_passage_dicts,
                )
            )
            return PersonaDialogueResponse(
                character_name=self.persona.canonical_name,
                character_id=self.persona.id,
                text=offline_text,
                model="offline-error-fallback",
                grounded_passages=grounded_badge_list,
                dynamic_passages=dynamic_passage_dicts,
                turn_count=self.turn_count,
                offline_fallback=True,
            )

    def step(
        self,
        user_message: str,
        config: Optional[GenerationConfig] = None,
    ) -> PersonaDialogueResponse:
        """Execute one dialogue turn with dynamic author-scoped Scripture RAG retrieval.

        Primary interface for character conversation turns, seamlessly retrieving
        canonical passages from the character's writings with similarity scores
        and injecting them into the turn context.

        Args:
            user_message: Inquirer question or prompt.
            config: Optional GenerationConfig override.

        Returns:
            PersonaDialogueResponse containing character answer, similarity-scored passages, and metadata.
        """
        return self.say(user_message=user_message, config=config)

    def say_stream(
        self,
        user_message: str,
        config: Optional[GenerationConfig] = None,
    ) -> Iterator[str]:
        """Send a message to the biblical character and stream response tokens incrementally.

        Args:
            user_message: User's question or message.
            config: Optional custom generation config.

        Yields:
            Incremental string tokens emitted by the character.
        """
        if not user_message or not user_message.strip():
            raise ValueError("user_message cannot be empty.")

        clean_user_message = user_message.strip()

        # Record user turn
        now_ts = _utc_now_iso()
        self.turns.append(
            DialogueTurn(
                role="user",
                speaker="Inquirer",
                content=clean_user_message,
                timestamp=now_ts,
            )
        )

        # Dynamic author-scoped Scripture RAG retrieval
        dynamic_passages = self.retrieve_turn_context(clean_user_message)
        dynamic_passage_dicts = [dp.to_dict() for dp in dynamic_passages]
        grounded_badge_list = [f"{dp.human_ref} ({dp.similarity_pct:.0f}% match)" for dp in dynamic_passages]
        if not grounded_badge_list:
            grounded_badge_list = [p.reference for p in self.grounded_passages]

        # Check API key availability
        if not self.llm_client.is_available():
            offline_text = self._build_offline_response(
                clean_user_message, dynamic_passages=dynamic_passages
            )
            self.history.append(ChatMessage(role="user", content=clean_user_message))
            self.history.append(ChatMessage(role="model", content=offline_text))
            self.turns.append(
                DialogueTurn(
                    role="character",
                    speaker=self.persona.canonical_name,
                    content=offline_text,
                    timestamp=_utc_now_iso(),
                    grounded_passages=grounded_badge_list,
                    dynamic_passages=dynamic_passage_dicts,
                )
            )
            yield offline_text
            return

        self.history.append(ChatMessage(role="user", content=clean_user_message))

        cfg = config or GenerationConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )

        turn_system_instruction = self._build_turn_system_prompt(dynamic_passages)

        accumulated_parts: List[str] = []
        try:
            for chunk in self.llm_client.generate_stream(
                prompt=self.history,
                system_instruction=turn_system_instruction,
                config=cfg,
                model=self.model,
            ):
                if chunk.text:
                    accumulated_parts.append(chunk.text)
                    yield chunk.text

            full_text = "".join(accumulated_parts).strip()
            self.history.append(ChatMessage(role="model", content=full_text))
            self.turns.append(
                DialogueTurn(
                    role="character",
                    speaker=self.persona.canonical_name,
                    content=full_text,
                    timestamp=_utc_now_iso(),
                    grounded_passages=grounded_badge_list,
                    dynamic_passages=dynamic_passage_dicts,
                )
            )

        except Exception as exc:
            err_text = (
                f"\n[NOTICE: Stream interrupted ({type(exc).__name__}: {str(exc)})]\n\n"
                + self._build_offline_response(
                    clean_user_message, dynamic_passages=dynamic_passages
                )
            )
            accumulated_parts.append(err_text)
            full_text = "".join(accumulated_parts).strip()
            self.history.append(ChatMessage(role="model", content=full_text))
            self.turns.append(
                DialogueTurn(
                    role="character",
                    speaker=self.persona.canonical_name,
                    content=full_text,
                    timestamp=_utc_now_iso(),
                    grounded_passages=grounded_badge_list,
                    dynamic_passages=dynamic_passage_dicts,
                )
            )
            yield err_text

    def to_transcript(self, title: Optional[str] = None) -> DialogueTranscript:
        """Generate an archival DialogueTranscript from active session state."""
        return DialogueTranscript(
            session_id=self.session_id,
            persona_id=self.persona.id,
            character_name=self.persona.canonical_name,
            title=title or self.title or f"Dialogue with {self.persona.canonical_name}",
            created_at=self.created_at,
            updated_at=_utc_now_iso(),
            model=self.model,
            translation=self.translation,
            turns=list(self.turns),
            theological_metadata={
                "canonical_era": self.persona.canonical_era,
                "theological_role": self.persona.theological_role,
                "lifespan_description": self.persona.lifespan_description,
                "key_passages": list(self.persona.key_passages),
                "christ_centered_orientation": self.persona.christ_centered_orientation,
            },
        )

    def save(
        self,
        title: Optional[str] = None,
        session_id: Optional[str] = None,
        sessions_dir: Optional[Path] = None,
    ) -> DialogueTranscript:
        """Persist dialogue session to disk as a JSON transcript."""
        if session_id:
            self.session_id = session_id
        if title:
            self.title = title
        tr = self.to_transcript(title=self.title)
        mgr = DialogueSessionManager(sessions_dir=sessions_dir)
        mgr.save_transcript(tr)
        return tr

    def to_markdown(self) -> str:
        """Format current dialogue session as illuminated Sacred-Modern Markdown."""
        return self.to_transcript().to_markdown()

    @classmethod
    def resume(
        cls,
        session_id: str,
        sessions_dir: Optional[Path] = None,
        db: Optional[Database] = None,
        llm_client: Optional[GeminiClient] = None,
        theology_engine: Optional[TGCTheologyEngine] = None,
        rag_engine: Optional[ScriptureRAGEngine] = None,
        enable_dynamic_rag: bool = True,
    ) -> "BiblicalPersonaSession":
        """Resume a prior dialogue session from disk by its session_id."""
        mgr = DialogueSessionManager(sessions_dir=sessions_dir)
        tr = mgr.load_transcript(session_id)
        persona_def = get_persona_definition(tr.persona_id)
        if not persona_def:
            raise ValueError(
                f"Unknown persona '{tr.persona_id}' recorded in saved session '{session_id}'"
            )

        session = cls(
            persona=persona_def,
            db=db,
            llm_client=llm_client,
            theology_engine=theology_engine,
            rag_engine=rag_engine,
            translation=tr.translation,
            model=tr.model,
            session_id=tr.session_id,
            title=tr.title,
            created_at=tr.created_at,
            enable_dynamic_rag=enable_dynamic_rag,
        )
        session.turns = list(tr.turns)
        session.history = []
        for turn in tr.turns:
            role = "user" if turn.role == "user" else "model"
            session.history.append(ChatMessage(role=role, content=turn.content))
        return session


# Alias per Roadmap Task 9.1
CharacterDialogueSession = BiblicalPersonaSession


# ==============================================================================
# 6. High-Level Helper Functions
# ==============================================================================


def create_persona_session(
    character_identifier: str,
    db: Optional[Database] = None,
    llm_client: Optional[GeminiClient] = None,
    theology_engine: Optional[TGCTheologyEngine] = None,
    rag_engine: Optional[ScriptureRAGEngine] = None,
    translation: str = DEFAULT_TRANSLATION,
    fallback_translation: str = FALLBACK_TRANSLATION,
    model: str = DEFAULT_GEMINI_MODEL,
    session_id: Optional[str] = None,
    title: Optional[str] = None,
    enable_dynamic_rag: bool = True,
    rag_max_passages: int = 3,
    rag_min_score: float = 0.05,
) -> BiblicalPersonaSession:
    """Factory helper to instantiate a BiblicalPersonaSession by character name or ID.

    Args:
        character_identifier: Identifier such as 'paul', 'david', 'moses', 'peter', etc.
        db: Optional database connection.
        llm_client: Optional GeminiClient.
        theology_engine: Optional theology engine.
        rag_engine: Optional ScriptureRAGEngine instance.
        translation: Preferred scripture translation (default ESV).
        fallback_translation: Fallback translation (default WEB).
        model: Gemini model identifier.
        session_id: Optional explicit session ID.
        title: Optional session title.
        enable_dynamic_rag: Whether to dynamically retrieve author-scoped passages each turn.
        rag_max_passages: Maximum dynamic passages to retrieve per turn.
        rag_min_score: Minimum relevance score threshold for retrieved passages.

    Returns:
        Configured BiblicalPersonaSession instance.

    Raises:
        ValueError: If character_identifier cannot be matched to any canonical persona.
    """
    persona = get_persona_definition(character_identifier)
    if not persona:
        available = ", ".join(f"`{p.id}`" for p in CANONICAL_PERSONAS)
        raise ValueError(
            f"Unknown biblical character persona: '{character_identifier}'. "
            f"Available characters: {available}."
        )

    return BiblicalPersonaSession(
        persona=persona,
        db=db,
        llm_client=llm_client,
        theology_engine=theology_engine,
        rag_engine=rag_engine,
        translation=translation,
        fallback_translation=fallback_translation,
        model=model,
        session_id=session_id,
        title=title,
        enable_dynamic_rag=enable_dynamic_rag,
        rag_max_passages=rag_max_passages,
        rag_min_score=rag_min_score,
    )
