"""Stratified Exegetical Prompt Architecture & TGC Hermeneutical System.

Zero-dependency implementation per ADR-003, ADR-006, ADR-042, ADR-049, ADR-050, and ADR-052:
- Stratified prompt layers:
  * Layer 0: Macro-Book Context Injection (BookHorizons for all 66 Protestant canonical books)
  * Layer 1: Pericope Structure & Propositions (genre, chiasm/outline, central proposition, redemptive summary)
  * Layer 2: Discourse Rhetoric & Logical Flow (connectives: ground, inference, purpose, contrast, condition, etc.)
  * Layer 3: Dual-Horizon Theological Classification ("Reading Along" epochs & "Reading Across" systematic loci)
  * Layer 4: Canonical Typology & Intertextual Arcs (OT types/shadows -> NT antitypes/fulfillments)
  * Layer 5: Semantic Propositions & Agent Triples (speech acts, agent, action, patient, tone, clause text)
- Resilient JSON parser and validator converting LLM responses into typed domain DTOs
- Native conversion to database records (PericopeRecord, DiscourseRelationRecord, VerseTheologyRecord, TypologicalArcRecord, SemanticPropositionRecord)
"""

from dataclasses import dataclass, field
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from core.db import (
    DiscourseRelationRecord,
    PericopeRecord,
    SemanticPropositionRecord,
    TypologicalArcRecord,
    VerseTheologyRecord,
)
from core.reference import (
    BOOKS,
    Book,
    Reference,
    get_book,
    parse_reference,
)
from core.theology import (
    RedemptiveEpoch,
    ThematicRibbon,
    TheologicalGuardrails,
    TheologicalLocus,
)


# ==============================================================================
# Discourse & Proposition Constants
# ==============================================================================

DISCOURSE_RELATION_TYPES: Tuple[str, ...] = (
    "ground",       # reason, basis, causal foundation (for, because, since)
    "inference",    # logical conclusion, result, deduction (therefore, so, consequently)
    "purpose",      # teleological goal, aim, design (in order that, to the end that)
    "contrast",     # opposition, sharp distinction, rebuttal (but, however, yet, rather)
    "condition",    # contingency, covenantal premise (if, unless, provided that)
    "concession",   # counter-expectation acknowledgment (although, though, even if)
    "result",       # effect, outcome, historical consequence (with the result that)
    "temporal",     # chronological sequence or framing (when, after, while, until)
)

SPEECH_ACT_TYPES: Tuple[str, ...] = (
    "indicative",   # statement of fact, redemptive reality, divine declaration
    "imperative",   # command, moral obligation, pastoral exhortation
    "promise",      # divine covenant assurance, pledge of future blessing
    "warning",      # solemn threat of judgment, disciplinary admonition
    "doxology",     # praise, adoration, worshipful exaltation of God
    "lament",       # grief, sorrow, mourning, cry of distress
    "prayer",       # petition, intercession, direct address to Yahweh
    "assertion",    # doctrinal thesis, truth claim, apostolic witness
)

LITERARY_GENRES: Tuple[str, ...] = (
    "Historical Narrative",
    "Law / Torah",
    "Wisdom & Poetry",
    "Major Prophets",
    "Minor Prophets",
    "Gospel",
    "Apostolic History",
    "Pauline Epistle",
    "General Epistle",
    "Apocalyptic",
)


# ==============================================================================
# Layer 0: Macro-Book Horizons (The 66 Canonical Books)
# ==============================================================================


@dataclass(frozen=True)
class BookHorizon:
    """Canonical macro-context for one biblical book, anchoring exegesis in authorial intent."""

    book_id: int
    name: str
    osis: str
    testament: str  # "OT" or "NT"
    genre: str
    author: str
    date_range: str
    historical_setting: str
    theological_theme: str
    christological_anticipation: str
    storyline_epoch: str
    key_motifs: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        """Convert book horizon to dictionary representation."""
        return {
            "book_id": self.book_id,
            "name": self.name,
            "osis": self.osis,
            "testament": self.testament,
            "genre": self.genre,
            "author": self.author,
            "date_range": self.date_range,
            "historical_setting": self.historical_setting,
            "theological_theme": self.theological_theme,
            "christological_anticipation": self.christological_anticipation,
            "storyline_epoch": self.storyline_epoch,
            "key_motifs": list(self.key_motifs),
        }


# Authoritative Book Horizon Catalog for all 66 Protestant Canonical Books
BOOK_HORIZONS: Dict[int, BookHorizon] = {
    # --- Old Testament: Pentateuch (1-5) ---
    1: BookHorizon(
        book_id=1, name="Genesis", osis="Gen", testament="OT",
        genre="Historical Narrative", author="Moses", date_range="c. 1446-1406 BC",
        historical_setting="Israel encamped in the wilderness prior to Canaan entry, receiving origins of cosmos, humanity, and covenant election.",
        theological_theme="Sovereign creation, cosmic fall, unconditional covenant promises, and God's providence preserving the chosen lineage.",
        christological_anticipation="The promised Seed of the woman crushing the serpent (3:15), the blessing of all nations through Abraham (12:3), and the ruler from Judah's line (49:10).",
        storyline_epoch=RedemptiveEpoch.PATRIARCHAL_COVENANT.value,
        key_motifs=("Creation", "Fall", "Covenant of Grace", "Promised Seed", "Sovereign Election"),
    ),
    2: BookHorizon(
        book_id=2, name="Exodus", osis="Exod", testament="OT",
        genre="Historical Narrative / Law", author="Moses", date_range="c. 1446-1406 BC",
        historical_setting="Israel enslaved in Egypt, redeemed with mighty signs, brought to Sinai to receive the divine Law and Tabernacle.",
        theological_theme="Sovereign redemption from slavery, covenant ratification at Sinai, and God's holy dwelling presence among His redeemed people.",
        christological_anticipation="Christ our Passover Lamb (12:1-30), the true bread from heaven (16:4), the rock cleft for us (17:6), and the Tabernacle fulfilled in the Incarnation (John 1:14).",
        storyline_epoch=RedemptiveEpoch.EXODUS_WILDERNESS.value,
        key_motifs=("Exodus Deliverance", "Passover Lamb", "Sinai Covenant", "Tabernacle Presence", "Divine Law"),
    ),
    3: BookHorizon(
        book_id=3, name="Leviticus", osis="Lev", testament="OT",
        genre="Law / Liturgical Code", author="Moses", date_range="c. 1446-1406 BC",
        historical_setting="Given at the foot of Mount Sinai from the newly erected Tent of Meeting.",
        theological_theme="The absolute holiness of Yahweh, substitutionary blood atonement for sin, and the sanctified life of God's covenant community.",
        christological_anticipation="The Great High Priest offering His own sinless blood on the heavenly Day of Atonement, cleansing sinners once and for all (Heb 9-10).",
        storyline_epoch=RedemptiveEpoch.EXODUS_WILDERNESS.value,
        key_motifs=("Holiness", "Sacrifice & Substitution", "Priesthood Mediation", "Atonement", "Purity"),
    ),
    4: BookHorizon(
        book_id=4, name="Numbers", osis="Num", testament="OT",
        genre="Historical Narrative", author="Moses", date_range="c. 1446-1406 BC",
        historical_setting="Forty-year wilderness journey from Sinai to the plains of Moab opposite Jericho.",
        theological_theme="God's unswerving covenant faithfulness contrasting with persistent human unbelief, rebellion, and wilderness testing.",
        christological_anticipation="The Bronze Serpent lifted up for salvation (21:9; John 3:14) and the Star out of Jacob who shall crush God's enemies (24:17).",
        storyline_epoch=RedemptiveEpoch.EXODUS_WILDERNESS.value,
        key_motifs=("Wilderness Testing", "Divine Faithfulness", "Rebellion & Judgment", "Bronze Serpent", "Guidance"),
    ),
    5: BookHorizon(
        book_id=5, name="Deuteronomy", osis="Deut", testament="OT",
        genre="Covenant Treaty / Law", author="Moses", date_range="c. 1406 BC",
        historical_setting="Moses' farewell sermons on the plains of Moab to the second generation preparing to enter Canaan.",
        theological_theme="Covenant renewal, wholehearted devotion (Shema), grace-motivated obedience, and the promises of heart circumcision.",
        christological_anticipation="The Prophet like Moses to whom everyone must listen (18:15-18; Acts 3:22) and the curse of the Law borne on the tree (21:23; Gal 3:13).",
        storyline_epoch=RedemptiveEpoch.EXODUS_WILDERNESS.value,
        key_motifs=("Covenant Renewal", "Shema Devotion", "Love & Obedience", "Prophetic Word", "Circumcised Heart"),
    ),

    # --- Historical Books (6-17) ---
    6: BookHorizon(
        book_id=6, name="Joshua", osis="Josh", testament="OT",
        genre="Historical Narrative", author="Joshua / Contemporary", date_range="c. 1400-1375 BC",
        historical_setting="Israel crossing the Jordan, conquering Canaanite strongholds, and receiving tribal land allotments.",
        theological_theme="God's sovereign faithfulness in fulfilling His land promises, holy warfare, and covenant rest through obedience.",
        christological_anticipation="Jesus the true Commander of the Lord's army leading His people into eternal Sabbath rest (Heb 4:8-9).",
        storyline_epoch=RedemptiveEpoch.CONQUEST_JUDGES.value,
        key_motifs=("Conquest", "Covenant Land", "Sabbath Rest", "Divine Faithfulness", "Holy Warfare"),
    ),
    7: BookHorizon(
        book_id=7, name="Judges", osis="Judg", testament="OT",
        genre="Historical Narrative", author="Samuel / Contemporary", date_range="c. 1050-1000 BC",
        historical_setting="The dark era between Joshua and the monarchy characterized by spiritual apostasy, oppression, and tribal fragmentation.",
        theological_theme="The downward spiral of human depravity when there is no king, and God's compassionate raising of imperfect deliverers.",
        christological_anticipation="The desperate necessity for a righteous, eternal King who will deliver His people permanently from sin and spiritual chaos.",
        storyline_epoch=RedemptiveEpoch.CONQUEST_JUDGES.value,
        key_motifs=("Spiritual Apostasy", "Cycles of Judges", "Deliverance", "Covenant Mercy", "Need for a King"),
    ),
    8: BookHorizon(
        book_id=8, name="Ruth", osis="Ruth", testament="OT",
        genre="Historical Narrative", author="Anonymous (Samuel era)", date_range="c. 1000 BC",
        historical_setting="Set in Bethlehem during the famine-stricken days when the judges ruled.",
        theological_theme="Sovereign providence in ordinary lives, covenant lovingkindness (chesed), and the inclusion of Gentiles into the messianic line.",
        christological_anticipation="Boaz as the Kinsman-Redeemer (Goel), prefiguring Christ who purchases His bride from poverty and alienation.",
        storyline_epoch=RedemptiveEpoch.CONQUEST_JUDGES.value,
        key_motifs=("Kinsman Redeemer", "Covenant Lovingkindness", "Gentile Inclusion", "Providence", "Royal Lineage"),
    ),
    9: BookHorizon(
        book_id=9, name="1 Samuel", osis="1Sam", testament="OT",
        genre="Historical Narrative", author="Anonymous / Prophetic Circle", date_range="c. 930-722 BC",
        historical_setting="Transition from the theocratic era of judges to the monarchy under Samuel, Saul, and David.",
        theological_theme="God's sovereignty over kings, the rejection of fleshly pride (Saul), and the anointing of the humble shepherd (David).",
        christological_anticipation="David anointed as king while suffering rejection, prefiguring Christ the anointed Shepherd-King.",
        storyline_epoch=RedemptiveEpoch.UNITED_MONARCHY.value,
        key_motifs=("Kingship Reign", "Anointed One (Messiah)", "Humility vs Pride", "Prophetic Word", "Heart vs Appearance"),
    ),
    10: BookHorizon(
        book_id=10, name="2 Samuel", osis="2Sam", testament="OT",
        genre="Historical Narrative", author="Anonymous / Prophetic Circle", date_range="c. 930-722 BC",
        historical_setting="The reign of King David over all Israel, the capture of Jerusalem, and the establishment of the Davidic throne.",
        theological_theme="The Davidic Covenant (2 Sam 7) establishing an eternal dynasty, balanced with the tragic consequences of royal sin.",
        christological_anticipation="The eternal Son of David who will reign over God's kingdom forever without end (Luke 1:32-33).",
        storyline_epoch=RedemptiveEpoch.UNITED_MONARCHY.value,
        key_motifs=("Davidic Covenant", "Eternal Kingdom", "Jerusalem/Zion", "Grace and Judgment", "Royal Seed"),
    ),
    11: BookHorizon(
        book_id=11, name="1 Kings", osis="1Kgs", testament="OT",
        genre="Historical Narrative", author="Anonymous (Jeremiah tradition)", date_range="c. 560-540 BC",
        historical_setting="Solomon's golden age, temple construction, idolatrous decline, and the tragic kingdom division into Israel and Judah.",
        theological_theme="The glory of temple worship, the perils of spiritual compromise, and the prophetic contest between Yahweh and Baal (Elijah).",
        christological_anticipation="Christ as the greater Solomon possessed of infinite wisdom, and the one greater than the Temple (Matt 12:42).",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("Temple Presence", "Wisdom", "Kingdom Division", "Prophetic Word", "Covenant Faithfulness"),
    ),
    12: BookHorizon(
        book_id=12, name="2 Kings", osis="2Kgs", testament="OT",
        genre="Historical Narrative", author="Anonymous (Jeremiah tradition)", date_range="c. 560-540 BC",
        historical_setting="The declining history of the divided kingdoms leading to the Assyrian destruction of Samaria (722 BC) and Babylonian exile of Jerusalem (586 BC).",
        theological_theme="God's patient justice executing covenant curses against idolatry, while preserving the Davidic seed in exile.",
        christological_anticipation="The preservation of the Davidic line in Jehoiachin, looking forward to the True King who will reverse the exile of humanity.",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("Exile & Pilgrimage", "Covenant Judgment", "Prophetic Warning", "Royal Preservations", "Idolatry Exposed"),
    ),
    13: BookHorizon(
        book_id=13, name="1 Chronicles", osis="1Chr", testament="OT",
        genre="Historical Narrative", author="Ezra / The Chronicler", date_range="c. 450-400 BC",
        historical_setting="Post-exilic Jewish community in Judah needing encouragement regarding God's enduring covenant promises.",
        theological_theme="Genealogical continuity of the covenant people, Davidic kingship focused on temple preparation, and true liturgical worship.",
        christological_anticipation="The Davidic ruler who builds the ultimate house for God's holy name.",
        storyline_epoch=RedemptiveEpoch.POST_EXILIC_RESTORATION.value,
        key_motifs=("Genealogy & Identity", "Temple Worship", "Davidic Covenant", "Prayer & Praise", "Covenant Grace"),
    ),
    14: BookHorizon(
        book_id=14, name="2 Chronicles", osis="2Chr", testament="OT",
        genre="Historical Narrative", author="Ezra / The Chronicler", date_range="c. 450-400 BC",
        historical_setting="Post-exilic Judah reflecting on the temple from Solomon to Cyrus' decree of return.",
        theological_theme="Immediate retribution, repentance bringing divine healing (7:14), and sovereign restoration after exile.",
        christological_anticipation="The true Builder and Restorer of God's spiritual temple among men.",
        storyline_epoch=RedemptiveEpoch.POST_EXILIC_RESTORATION.value,
        key_motifs=("Temple Restoration", "Repentance", "Divine Sovereignty", "Covenant Hope", "Restoration Decree"),
    ),
    15: BookHorizon(
        book_id=15, name="Ezra", osis="Ezra", testament="OT",
        genre="Historical Narrative", author="Ezra", date_range="c. 450-400 BC",
        historical_setting="Return of Jewish exiles to Jerusalem under Zerubbabel and Ezra to rebuild the temple and re-establish the Torah.",
        theological_theme="God's sovereign movement of imperial rulers (Cyrus, Darius, Artaxerxes) to preserve His remnant and restore pure worship.",
        christological_anticipation="The spiritual rebuilding of God's people around the living Word of God.",
        storyline_epoch=RedemptiveEpoch.POST_EXILIC_RESTORATION.value,
        key_motifs=("Second Temple", "Word of God", "Remnant Restored", "Covenant Purity", "Sovereignty over Nations"),
    ),
    16: BookHorizon(
        book_id=16, name="Nehemiah", osis="Neh", testament="OT",
        genre="Historical Narrative / Memoir", author="Nehemiah", date_range="c. 430-400 BC",
        historical_setting="Rebuilding Jerusalem's walls amidst external opposition and internal socioeconomic reform.",
        theological_theme="Covenant renewal, holy leadership, prayerful dependence, and the protection of God's holy city.",
        christological_anticipation="Christ who builds and protects the heavenly Jerusalem against the gates of hell.",
        storyline_epoch=RedemptiveEpoch.POST_EXILIC_RESTORATION.value,
        key_motifs=("City of God", "Prayer & Action", "Covenant Renewal", "Opposition Overcome", "Social Justice"),
    ),
    17: BookHorizon(
        book_id=17, name="Esther", osis="Esth", testament="OT",
        genre="Historical Narrative", author="Anonymous", date_range="c. 460-350 BC",
        historical_setting="The Persian capital of Susa during the reign of Ahasuerus (Xerxes I).",
        theological_theme="The invisible, providential preservation of God's covenant people from annihilation even in pagan exile.",
        christological_anticipation="Deliverance from the ancient enemy (Haman the Agagite) anticipating Christ's victory over Satan.",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("Providence (Unseen Hand)", "Preservation of the Seed", "Courageous Faith", "Deliverance", "Purim Joy"),
    ),

    # --- Wisdom & Poetry (18-22) ---
    18: BookHorizon(
        book_id=18, name="Job", osis="Job", testament="OT",
        genre="Wisdom & Poetry", author="Anonymous (Patriarchal era setting)", date_range="Unknown",
        historical_setting="Land of Uz; an ancient righteous patriarch struck by catastrophic, undeserved suffering.",
        theological_theme="The sovereign majesty of God, the mystery of righteous suffering, and the dismantling of simplistic retributive theology.",
        christological_anticipation="The innocent Sufferer who redeems His people; Job's cry for a Mediator/Arbiter (9:33) and living Redeemer (19:25).",
        storyline_epoch=RedemptiveEpoch.PATRIARCHAL_COVENANT.value,
        key_motifs=("Sovereign Majesty", "Righteous Suffering", "The Arbiter/Mediator", "Faith Under Trial", "Living Redeemer"),
    ),
    19: BookHorizon(
        book_id=19, name="Psalms", osis="Ps", testament="OT",
        genre="Wisdom & Poetry", author="David, Asaph, Sons of Korah, Moses, Solomon, etc.", date_range="c. 1400-450 BC",
        historical_setting="The prayer book and hymnal of ancient Israel, structured in five books corresponding to the Pentateuch.",
        theological_theme="Lament, thanksgiving, praise, kingship, and divine law expressed in experiential communion with Yahweh.",
        christological_anticipation="The Messianic King (Ps 2, 110), the Suffering Servant bearing crucifixion anguish (Ps 22), the resurrected Holy One (Ps 16).",
        storyline_epoch=RedemptiveEpoch.UNITED_MONARCHY.value,
        key_motifs=("Praise & Worship", "Lament to Joy", "Messianic King", "Torah Delight", "Divine Refuge"),
    ),
    20: BookHorizon(
        book_id=20, name="Proverbs", osis="Prov", testament="OT",
        genre="Wisdom & Poetry", author="Solomon, Agur, Lemuel", date_range="c. 950-700 BC",
        historical_setting="Royal court and family instruction in ancient Israel.",
        theological_theme="The fear of the Lord as the beginning of wisdom, righteous living in daily affairs, and moral discernment.",
        christological_anticipation="Christ as the incarnate Wisdom of God (1 Cor 1:24, 30; Col 2:3) who perfectly embodies righteousness.",
        storyline_epoch=RedemptiveEpoch.UNITED_MONARCHY.value,
        key_motifs=("Fear of the Lord", "Wisdom vs Folly", "Righteous Living", "Speech & Integrity", "Family Instruction"),
    ),
    21: BookHorizon(
        book_id=21, name="Ecclesiastes", osis="Eccl", testament="OT",
        genre="Wisdom & Poetry", author="Solomon / The Preacher (Qoheleth)", date_range="c. 935 BC",
        historical_setting="A royal sage reflecting on human achievement and mortality in a fallen world.",
        theological_theme="The vanity and vapor (hebel) of life 'under the sun' apart from God, culminating in fearing God and keeping His commandments.",
        christological_anticipation="Deliverance from the cosmic frustration and futility of the Fall (Rom 8:20) in the eternal life of Christ.",
        storyline_epoch=RedemptiveEpoch.UNITED_MONARCHY.value,
        key_motifs=("Vanity under the Sun", "Mortality & Time", "Sovereignty of God", "Fear of the Lord", "Joy in Simple Gifts"),
    ),
    22: BookHorizon(
        book_id=22, name="Song of Solomon", osis="Song", testament="OT",
        genre="Wisdom & Poetry", author="Solomon", date_range="c. 950 BC",
        historical_setting="Celebration of marital romantic love and covenant delight in ancient Israel.",
        theological_theme="The goodness, purity, and beauty of marital love as created by God.",
        christological_anticipation="Typological shadow of the mutual love, beauty, and unbreakable covenant union between Christ and His Bride, the Church (Eph 5:31-32).",
        storyline_epoch=RedemptiveEpoch.UNITED_MONARCHY.value,
        key_motifs=("Spousal Union", "Covenant Love", "Delight & Desire", "Beauty", "Unquenchable Flame"),
    ),

    # --- Major Prophets (23-27) ---
    23: BookHorizon(
        book_id=23, name="Isaiah", osis="Isa", testament="OT",
        genre="Major Prophets", author="Isaiah son of Amoz", date_range="c. 740-680 BC",
        historical_setting="Judah during the reigns of Uzziah, Jotham, Ahaz, and Hezekiah amidst the Assyrian threat.",
        theological_theme="The Holy One of Israel: holy judgment on national sin, the remnant, and cosmic salvation through the Servant of the Lord.",
        christological_anticipation="Immanuel born of a virgin (7:14), Prince of Peace (9:6), the Shoot of Jesse (11:1), the Suffering Servant bearing our iniquities (53:1-12), and the Anointed Preacher (61:1).",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("Holy One of Israel", "Suffering Servant", "Substitutionary Atonement", "New Heavens & Earth", "Messianic King"),
    ),
    24: BookHorizon(
        book_id=24, name="Jeremiah", osis="Jer", testament="OT",
        genre="Major Prophets", author="Jeremiah", date_range="c. 627-580 BC",
        historical_setting="The final turbulent decades of Judah leading to the siege, fall, and exile of Jerusalem to Babylon.",
        theological_theme="The weeping prophet proclaiming inevitable judgment on covenant unfaithfulness, alongside the promise of the New Covenant.",
        christological_anticipation="The Righteous Branch from David (23:5-6) and the Mediator of the New Covenant with the law written on hearts (31:31-34; Luke 22:20).",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("New Covenant", "Righteous Branch", "Judgment & Exile", "Heart Transformation", "Weeping Prophet"),
    ),
    25: BookHorizon(
        book_id=25, name="Lamentations", osis="Lam", testament="OT",
        genre="Wisdom & Poetry", author="Jeremiah", date_range="c. 586 BC",
        historical_setting="The smoking ruins of destroyed Jerusalem immediately following the Babylonian devastation.",
        theological_theme="Acrostic elegies mourning holy judgment on sin while confessing that Yahweh's steadfast love and mercies never cease (3:22-23).",
        christological_anticipation="Christ weeping over Jerusalem and bearing the full cup of God's holy wrath in our place.",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("Grief & Lament", "Steadfast Love (Chesed)", "Divine Justice", "Hope in Darkness", "Sovereign Chastening"),
    ),
    26: BookHorizon(
        book_id=26, name="Ezekiel", osis="Ezek", testament="OT",
        genre="Major Prophets", author="Ezekiel son of Buzi", date_range="c. 593-571 BC",
        historical_setting="Among the Jewish exiles by the river Chebar in Babylon.",
        theological_theme="The departure of God's glory from Jerusalem due to idolatry, the promise of spiritual regeneration (heart of flesh), and the visionary new temple.",
        christological_anticipation="The True Shepherd (34:23), the Source of life-giving water (47:1-12; John 7:38), and the resurrection of dead bones by the Spirit (37:1-14).",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("Glory of God", "Regeneration (Heart of Flesh)", "Valley of Dry Bones", "True Shepherd", "New Temple"),
    ),
    27: BookHorizon(
        book_id=27, name="Daniel", osis="Dan", testament="OT",
        genre="Apocalyptic", author="Daniel", date_range="c. 605-536 BC",
        historical_setting="The royal courts of Babylon and Persia during the 70-year exile.",
        theological_theme="God's sovereign rule over pagan empires, the preservation of the holy remnant, and the coming eternal Kingdom.",
        christological_anticipation="The Son of Man coming on the clouds of heaven receiving an everlasting dominion (7:13-14) and the Messiah cut off (9:26).",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("Kingdom of God", "Son of Man", "Sovereignty over Nations", "Faithful Remnant", "Messianic Decree"),
    ),

    # --- Minor Prophets (28-39) ---
    28: BookHorizon(
        book_id=28, name="Hosea", osis="Hos", testament="OT",
        genre="Minor Prophets", author="Hosea son of Beeri", date_range="c. 750-715 BC",
        historical_setting="Northern Kingdom of Israel in its final years before Assyrian destruction.",
        theological_theme="Israel's spiritual adultery contrasted with Yahweh's relentless, pursuing covenant love.",
        christological_anticipation="The true Son called out of Egypt (11:1; Matt 2:15) and the ransom from death (13:14; 1 Cor 15:55).",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("Spiritual Adultery", "Relentless Covenant Love", "Out of Egypt", "Repentance", "Restoration"),
    ),
    29: BookHorizon(
        book_id=29, name="Joel", osis="Joel", testament="OT",
        genre="Minor Prophets", author="Joel son of Pethuel", date_range="c. 835 BC or post-exilic",
        historical_setting="Judah devastated by a catastrophic locust plague foreshadowing the Day of the Lord.",
        theological_theme="Repentance in the face of judgment, the Day of the Lord, and the universal outpouring of the Holy Spirit.",
        christological_anticipation="The outpouring of the Spirit on all flesh at Pentecost (2:28-32; Acts 2:16-21) through the exalted Christ.",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("Day of the Lord", "Outpouring of the Spirit", "Rend Your Hearts", "Judgment and Mercy", "Zion Refuge"),
    ),
    30: BookHorizon(
        book_id=30, name="Amos", osis="Amos", testament="OT",
        genre="Minor Prophets", author="Amos of Tekoa", date_range="c. 760-750 BC",
        historical_setting="Northern kingdom enjoying wealthy, complacent self-indulgence paired with oppression of the poor.",
        theological_theme="God's universal justice demanding authentic righteousness rather than hollow religious ritual.",
        christological_anticipation="The restoration of David's fallen tent (9:11-12; Acts 15:16-17) encompassing the Gentiles.",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("Justice & Mercy", "Hollow Religion Rebuked", "Day of the Lord", "David's Fallen Tent", "Gentile Inclusion"),
    ),
    31: BookHorizon(
        book_id=31, name="Obadiah", osis="Obad", testament="OT",
        genre="Minor Prophets", author="Obadiah", date_range="c. 586 BC",
        historical_setting="Edom gloating over and assisting the Babylonian destruction of Jerusalem.",
        theological_theme="The downfall of haughty Edom and the triumph of Mount Zion in the universal Kingdom of Yahweh.",
        christological_anticipation="The final overthrow of all hostile anti-God powers under the reign of King Jesus.",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("Pride Brought Low", "Brotherly Betrayal", "Mount Zion Triumph", "Kingdom Belonging to Yahweh", "Divine Justice"),
    ),
    32: BookHorizon(
        book_id=32, name="Jonah", osis="Jonah", testament="OT",
        genre="Historical Narrative", author="Jonah son of Amittai", date_range="c. 760 BC",
        historical_setting="Northern Israel prophet sent to the brutal Assyrian capital of Nineveh.",
        theological_theme="God's sovereign mercy extending beyond Israel to repentant Gentiles, exposing narrow nationalistic self-righteousness.",
        christological_anticipation="The 'sign of the prophet Jonah': three days in the belly of the fish prefiguring Christ's burial and third-day resurrection (Matt 12:39-40).",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("Sovereign Mercy", "Salvation is of the Lord", "Gentile Repentance", "Sign of Jonah", "Resurrection Shadow"),
    ),
    33: BookHorizon(
        book_id=33, name="Micah", osis="Mic", testament="OT",
        genre="Minor Prophets", author="Micah of Moresheth", date_range="c. 735-700 BC",
        historical_setting="Judah during the reigns of Jotham, Ahaz, and Hezekiah amidst social injustice and hypocritical religion.",
        theological_theme="Judgment on corrupt rulers and false prophets, true religion (justice, kindness, walking humbly), and the shepherd from Bethlehem.",
        christological_anticipation="The eternal Ruler born in Bethlehem Ephrathah who will shepherd His flock in the strength of Yahweh (5:2; Matt 2:6).",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("Bethlehem Ruler", "Justice, Kindness, Humility", "Sins Cast into Sea", "Shepherd of Israel", "True Religion"),
    ),
    34: BookHorizon(
        book_id=34, name="Nahum", osis="Nah", testament="OT",
        genre="Minor Prophets", author="Nahum of Elkosh", date_range="c. 663-612 BC",
        historical_setting="Anticipating the destruction of Nineveh, the brutal capital of the Assyrian Empire.",
        theological_theme="Yahweh as a jealous, avenging God who destroys wicked oppressors and provides a stronghold for those who trust Him.",
        christological_anticipation="The proclamation of good news of peace and deliverance for God's oppressed people (1:15; Rom 10:15).",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("Divine Vengeance", "Stronghold in Trouble", "Fall of Nineveh", "Good News of Peace", "Justice for Oppressed"),
    ),
    35: BookHorizon(
        book_id=35, name="Habakkuk", osis="Hab", testament="OT",
        genre="Minor Prophets", author="Habakkuk", date_range="c. 605 BC",
        historical_setting="Judah on the brink of the Babylonian invasion, questioning divine justice.",
        theological_theme="Moving from perplexity to triumphant faith: 'the righteous shall live by his faith' (2:4).",
        christological_anticipation="Forensic justification through living faith in God's promises, fulfilled in Christ (Rom 1:17; Gal 3:11; Heb 10:38).",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("Just Shall Live by Faith", "Lament to Triumph", "Sovereign Justice", "Wait for the Vision", "Joy in God"),
    ),
    36: BookHorizon(
        book_id=36, name="Zephaniah", osis="Zeph", testament="OT",
        genre="Minor Prophets", author="Zephaniah great-great-grandson of Hezekiah", date_range="c. 640-621 BC",
        historical_setting="Judah during the reign of King Josiah, prior to his great religious reforms.",
        theological_theme="The fierce purifying Day of the Lord, followed by Yahweh rejoicing over His humble remnant with singing (3:17).",
        christological_anticipation="Christ the King of Israel in our midst, removing judgment and rejoicing over His redeemed people.",
        storyline_epoch=RedemptiveEpoch.DIVIDED_EXILE.value,
        key_motifs=("Day of the Lord", "Humble Remnant", "Rejoicing Over with Singing", "Purifying Judgment", "Restoration"),
    ),
    37: BookHorizon(
        book_id=37, name="Haggai", osis="Hag", testament="OT",
        genre="Minor Prophets", author="Haggai", date_range="520 BC",
        historical_setting="Post-exilic Jerusalem where returning exiles stopped rebuilding the temple to focus on paneling their own homes.",
        theological_theme="Prioritizing God's house over personal luxury, accompanied by the promise of greater future glory.",
        christological_anticipation="The Desire of all nations filling the temple with glory (2:7) and Zerubbabel as the messianic signet ring (2:23).",
        storyline_epoch=RedemptiveEpoch.POST_EXILIC_RESTORATION.value,
        key_motifs=("Rebuilding the Temple", "Consider Your Ways", "Latter Glory", "Messianic Signet Ring", "Priority of God"),
    ),
    38: BookHorizon(
        book_id=38, name="Zechariah", osis="Zech", testament="OT",
        genre="Apocalyptic", author="Zechariah son of Berechiah", date_range="c. 520-480 BC",
        historical_setting="Post-exilic restoration community in Jerusalem rebuilding the temple and awaiting messianic fulfillment.",
        theological_theme="Visions of restoration, the cleansing of the priesthood, the Branch, and the universal reign of Yahweh.",
        christological_anticipation="The humble King riding on a donkey (9:9; Matt 21:5), the Shepherd pierced for thirty pieces of silver (11:12-13; 12:10), and the cleansing fountain for sin (13:1).",
        storyline_epoch=RedemptiveEpoch.POST_EXILIC_RESTORATION.value,
        key_motifs=("The Branch", "King on a Donkey", "Pierced Shepherd", "Fountain for Sin", "Priest-King"),
    ),
    39: BookHorizon(
        book_id=39, name="Malachi", osis="Mal", testament="OT",
        genre="Minor Prophets", author="Malachi", date_range="c. 430 BC",
        historical_setting="Final prophetic voice of the Old Testament to cynical, spiritually complacent post-exilic Judah.",
        theological_theme="Yahweh's enduring covenant love rebuking corrupt priests, dishonorable offerings, and divorce, promising the messenger of the covenant.",
        christological_anticipation="The Sun of Righteousness rising with healing in His wings (4:2) preceded by Elijah the messenger (John the Baptist, Matt 11:14).",
        storyline_epoch=RedemptiveEpoch.POST_EXILIC_RESTORATION.value,
        key_motifs=("Messenger of the Covenant", "Sun of Righteousness", "Refining Fire", "Covenant Faithfulness", "Unchanging Love"),
    ),

    # --- New Testament: Gospels & Acts (40-44) ---
    40: BookHorizon(
        book_id=40, name="Matthew", osis="Matt", testament="NT",
        genre="Gospel", author="Matthew (Levi) the Apostle", date_range="c. AD 60-65",
        historical_setting="Written primarily to Jewish Christians demonstrating how Jesus fulfills the Old Testament Scriptures.",
        theological_theme="Jesus as the promised Davidic King, the new Moses fulfilling the Law, and the authoritative Teacher of the Kingdom.",
        christological_anticipation="Emmanuel, God with us (1:23); the Son of David who establishes the Kingdom of Heaven and gives the Great Commission.",
        storyline_epoch=RedemptiveEpoch.INCARNATION_CLIMAX.value,
        key_motifs=("Kingdom of Heaven", "Fulfillment of Prophecy", "Son of David", "Sermon on the Mount", "Great Commission"),
    ),
    41: BookHorizon(
        book_id=41, name="Mark", osis="Mark", testament="NT",
        genre="Gospel", author="John Mark (recording Peter's apostolic witness)", date_range="c. AD 55-62",
        historical_setting="Written in Rome for Gentile Christians facing persecution under Nero.",
        theological_theme="Jesus as the authoritative, suffering Servant of the Lord who gives His life as a ransom for many.",
        christological_anticipation="The Son of God who came not to be served, but to serve, and to give His life a ransom for many (10:45).",
        storyline_epoch=RedemptiveEpoch.INCARNATION_CLIMAX.value,
        key_motifs=("Suffering Servant", "Ransom for Many", "Messianic Secret", "Discipleship Cost", "Authority & Power"),
    ),
    42: BookHorizon(
        book_id=42, name="Luke", osis="Luke", testament="NT",
        genre="Gospel", author="Luke the Physician", date_range="c. AD 60-62",
        historical_setting="Written to Theophilus ('friend of God') providing an orderly, historically verified account of Jesus.",
        theological_theme="The universal scope of the gospel reaching outcasts, sinners, women, the poor, and Gentiles by sovereign grace.",
        christological_anticipation="The Son of Man who came to seek and to save the lost (19:10) through His cross, resurrection, and ascension.",
        storyline_epoch=RedemptiveEpoch.INCARNATION_CLIMAX.value,
        key_motifs=("Seek & Save Lost", "Holy Spirit", "Outcasts & Sinners", "Prayer & Joy", "Road to Emmaus"),
    ),
    43: BookHorizon(
        book_id=43, name="John", osis="John", testament="NT",
        genre="Gospel", author="John the Apostle (the beloved disciple)", date_range="c. AD 85-95",
        historical_setting="Written in Ephesus to both Jewish and Gentile audiences to inspire saving belief in Jesus as the Christ.",
        theological_theme="The eternal Word made flesh, the seven miraculous signs, the 'I AM' declarations, and eternal life through believing.",
        christological_anticipation="The Lamb of God who takes away the sin of the world (1:29) and the resurrection and the life (11:25).",
        storyline_epoch=RedemptiveEpoch.INCARNATION_CLIMAX.value,
        key_motifs=("The Incarnate Word (Logos)", "I AM Declarations", "Eternal Life", "Seven Signs", "Believe & Live"),
    ),
    44: BookHorizon(
        book_id=44, name="Acts", osis="Acts", testament="NT",
        genre="Apostolic History", author="Luke the Physician", date_range="c. AD 62-64",
        historical_setting="The continuation of Jesus' ministry from heaven through the Holy Spirit and the apostles, spreading from Jerusalem to Rome.",
        theological_theme="The unstoppable expansion of the gospel by the power of the Holy Spirit amidst opposition, incorporating Gentiles into the Church.",
        christological_anticipation="The exalted, reigning Lord Jesus at the right hand of God directing the mission of His Church.",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Power of the Spirit", "Gospel to the Nations", "Apostolic Preaching", "Persecution & Growth", "Exalted Lord"),
    ),

    # --- Pauline Epistles (45-57) ---
    45: BookHorizon(
        book_id=45, name="Romans", osis="Rom", testament="NT",
        genre="Pauline Epistle", author="Paul the Apostle", date_range="c. AD 57",
        historical_setting="Written from Corinth to the mixed Jewish-Gentile church in Rome preparing for his visit and mission to Spain.",
        theological_theme="The gospel of God's righteousness: universal human depravity, justification by faith alone, union with Christ, sovereign election, and transformed living.",
        christological_anticipation="Christ the propitiation for our sins by His blood (3:25), the second Adam conferring life (5:12-21), and the triumphant Lord over all (8:31-39).",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Righteousness of God", "Justification by Faith", "Union with Christ", "Sovereign Election", "Gospel Power"),
    ),
    46: BookHorizon(
        book_id=46, name="1 Corinthians", osis="1Cor", testament="NT",
        genre="Pauline Epistle", author="Paul the Apostle", date_range="c. AD 55",
        historical_setting="Written from Ephesus to the fractured, worldly, charismatically proud church in cosmopolitan Corinth.",
        theological_theme="The word of the cross transforming church unity, sexual purity, marriage, Christian liberty, spiritual gifts, and bodily resurrection.",
        christological_anticipation="Christ the power and wisdom of God (1:24), our Passover Lamb (5:7), and the firstfruits of the resurrection (15:20-23).",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Word of the Cross", "Bodily Resurrection", "Love (Agape)", "Church Order & Unity", "Temple of the Spirit"),
    ),
    47: BookHorizon(
        book_id=47, name="2 Corinthians", osis="2Cor", testament="NT",
        genre="Pauline Epistle", author="Paul the Apostle", date_range="c. AD 55-56",
        historical_setting="Written from Macedonia following a painful visit, defending apostolic legitimacy against boastful 'super-apostles'.",
        theological_theme="Strength made perfect in weakness, the glory of the New Covenant ministry of reconciliation, and generous gospel giving.",
        christological_anticipation="God made Him who knew no sin to be sin for us, that in Him we might become the righteousness of God (5:21).",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Power in Weakness", "Ministry of Reconciliation", "New Covenant Glory", "Generous Grace", "Clay Jars"),
    ),
    48: BookHorizon(
        book_id=48, name="Galatians", osis="Gal", testament="NT",
        genre="Pauline Epistle", author="Paul the Apostle", date_range="c. AD 48-49",
        historical_setting="Written to the churches of southern Galatia battling legalistic Judaizers demanding circumcision for salvation.",
        theological_theme="Justification by grace alone through faith alone apart from the works of the Law; Christian freedom walking by the Spirit.",
        christological_anticipation="Christ redeemed us from the curse of the law by becoming a curse for us on the cross (3:13).",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Gospel Freedom", "Justification Apart from Law", "Crucified with Christ", "Fruit of the Spirit", "No Other Gospel"),
    ),
    49: BookHorizon(
        book_id=49, name="Ephesians", osis="Eph", testament="NT",
        genre="Pauline Epistle", author="Paul the Apostle", date_range="c. AD 60-62",
        historical_setting="Written from Roman imprisonment as a circular letter to churches in Asia Minor.",
        theological_theme="The cosmic mystery of God's eternal decree in Christ: uniting all things in Him, breaking down the dividing wall between Jew and Gentile, and equipping the Church for spiritual warfare.",
        christological_anticipation="Christ the Head of the Church, having broken down the wall of hostility and given gifts to His body.",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Saved by Grace Through Faith", "One New Man", "Mystery of the Church", "Spiritual Armor", "Sovereign Election"),
    ),
    50: BookHorizon(
        book_id=50, name="Philippians", osis="Phil", testament="NT",
        genre="Pauline Epistle", author="Paul the Apostle", date_range="c. AD 60-62",
        historical_setting="Written from prison to the affectionate, supportive congregation in Philippi.",
        theological_theme="Unshakable joy in Christ, gospel partnership, humble unity modeled after Christ's self-emptying, and pursuing the prize.",
        christological_anticipation="The Christ Hymn (2:5-11): Jesus emptying Himself, obedient unto death on a cross, exalted above every name.",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Joy in Chains", "Christ Hymn (Kenosis)", "Gospel Partnership", "Surpassing Worth of Christ", "Contentment"),
    ),
    51: BookHorizon(
        book_id=51, name="Colossians", osis="Col", testament="NT",
        genre="Pauline Epistle", author="Paul the Apostle", date_range="c. AD 60-62",
        historical_setting="Written from prison to combat syncretistic heresy (Gnostic asceticism and mysticism) in Colossae.",
        theological_theme="The absolute supremacy, sufficiency, and preeminence of Jesus Christ in creation and redemption.",
        christological_anticipation="Christ the image of the invisible God, the firstborn over all creation, in whom all the fullness of deity dwells bodily (1:15-20; 2:9).",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Supremacy of Christ", "Fullness in Him", "Shadow vs Substance", "Put on the New Self", "Treasures of Wisdom"),
    ),
    52: BookHorizon(
        book_id=52, name="1 Thessalonians", osis="1Thess", testament="NT",
        genre="Pauline Epistle", author="Paul the Apostle", date_range="c. AD 50-51",
        historical_setting="Written to a young, persecuted Macedonian church needing encouragement and clarity regarding the Parousia.",
        theological_theme="Holiness, brotherly love, steadfast faith under persecution, and the glorious second coming of Jesus Christ.",
        christological_anticipation="Jesus our Deliverer from the wrath to come (1:10), descending from heaven with a cry of command (4:16).",
        storyline_epoch=RedemptiveEpoch.CONSUMMATION.value,
        key_motifs=("Parousia Hope", "Holiness & Sanctification", "Resurrection of Believers", "Faith, Hope & Love", "Comfort in Grief"),
    ),
    53: BookHorizon(
        book_id=53, name="2 Thessalonians", osis="2Thess", testament="NT",
        genre="Pauline Epistle", author="Paul the Apostle", date_range="c. AD 51-52",
        historical_setting="Follow-up letter correcting false rumors that the Day of the Lord had already come.",
        theological_theme="God's righteous judgment at the Parousia, the rebellion and the man of lawlessness, and disciplined daily work.",
        christological_anticipation="The Lord Jesus revealed from heaven with His mighty angels in flaming fire, destroying the lawless one with the breath of His mouth.",
        storyline_epoch=RedemptiveEpoch.CONSUMMATION.value,
        key_motifs=("Day of the Lord", "Man of Lawlessness", "Steadfast Endurance", "Righteous Retribution", "Disciplined Living"),
    ),
    54: BookHorizon(
        book_id=54, name="1 Timothy", osis="1Tim", testament="NT",
        genre="Pauline Epistle", author="Paul the Apostle", date_range="c. AD 62-64",
        historical_setting="Pastoral letter to young Timothy leading the church in Ephesus amidst false ascetic teachers.",
        theological_theme="Order, sound doctrine, godly leadership qualifications (elders/deacons), and pastoral vigilance in the household of God.",
        christological_anticipation="The one Mediator between God and men, the man Christ Jesus, who gave Himself as a ransom for all (2:5-6).",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Sound Doctrine", "Household of God", "One Mediator", "Pastoral Qualifications", "Godliness with Contentment"),
    ),
    55: BookHorizon(
        book_id=55, name="2 Timothy", osis="2Tim", testament="NT",
        genre="Pauline Epistle", author="Paul the Apostle", date_range="c. AD 66-67",
        historical_setting="Paul's final testament from a cold Roman dungeon facing imminent martyrdom under Nero.",
        theological_theme="Unyielding endurance in ministry, unashamed loyalty to the gospel, and preaching the inspired Word in the face of apostasy.",
        christological_anticipation="The righteous Judge who will award the crown of righteousness to all who have loved His appearing (4:8).",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Inspired Scripture", "Preach the Word", "Endurance in Ministry", "Finishing the Race", "Crown of Righteousness"),
    ),
    56: BookHorizon(
        book_id=56, name="Titus", osis="Titus", testament="NT",
        genre="Pauline Epistle", author="Paul the Apostle", date_range="c. AD 62-64",
        historical_setting="Pastoral guidance for Titus establishing order and appointing elders in the unruly churches of Crete.",
        theological_theme="Sound doctrine producing holy, exemplary living and zealous good works motivated by God's saving grace.",
        christological_anticipation="Waiting for our blessed hope: the appearing of the glory of our great God and Savior Jesus Christ (2:13).",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Grace Trains in Godliness", "Zealous for Good Works", "Sound Doctrine", "Elder Qualifications", "Blessed Hope"),
    ),
    57: BookHorizon(
        book_id=57, name="Philemon", osis="Phlm", testament="NT",
        genre="Pauline Epistle", author="Paul the Apostle", date_range="c. AD 60-62",
        historical_setting="Personal letter to Christian slaveholder Philemon regarding his runaway slave Onesimus who became a believer.",
        theological_theme="Gospel reconciliation transforming social hierarchies; receiving former slaves as beloved brothers in Christ.",
        christological_anticipation="Paul offering to pay Onesimus' debt ('charge that to my account', v. 18), prefiguring Christ's substitutionary imputation.",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Reconciliation", "Imputation of Debt", "Brothers in Christ", "Gospel Love", "Forgiveness"),
    ),

    # --- General Epistles & Revelation (58-66) ---
    58: BookHorizon(
        book_id=58, name="Hebrews", osis="Heb", testament="NT",
        genre="General Epistle", author="Anonymous (Pauline / Alexandrian circle)", date_range="c. AD 64-68",
        historical_setting="Written to Jewish Christians tempted to abandon Christ and return to the Levitical temple system under persecution.",
        theological_theme="The absolute superiority of Jesus Christ over angels, Moses, and the Old Covenant; His eternal high priesthood and once-for-all sacrifice.",
        christological_anticipation="The great High Priest after the order of Melchizedek who has passed through the heavens, offering His own blood.",
        storyline_epoch=RedemptiveEpoch.INCARNATION_CLIMAX.value,
        key_motifs=("Superiority of Christ", "High Priest (Melchizedek)", "Better Covenant", "Hall of Faith", "Once for All Sacrifice"),
    ),
    59: BookHorizon(
        book_id=59, name="James", osis="Jas", testament="NT",
        genre="General Epistle", author="James the brother of the Lord", date_range="c. AD 45-48",
        historical_setting="Written to the twelve Jewish-Christian tribes dispersed among the nations.",
        theological_theme="Living, active faith demonstrated through trials, controlled speech, justice for the poor, and practical godliness.",
        christological_anticipation="Faith in our Lord Jesus Christ, the Lord of glory (2:1), producing a harvest of righteousness.",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Faith Without Works is Dead", "Taming the Tongue", "Trials & Endurance", "Wisdom from Above", "Justice for Poor"),
    ),
    60: BookHorizon(
        book_id=60, name="1 Peter", osis="1Pet", testament="NT",
        genre="General Epistle", author="Peter the Apostle", date_range="c. AD 62-64",
        historical_setting="Written from Rome ('Babylon') to elect exiles suffering social alienation and persecution across Asia Minor.",
        theological_theme="Living hope through Christ's resurrection, suffering for righteousness, and walking as a royal priesthood in an alien world.",
        christological_anticipation="The sinless Lamb of God whose precious blood ransomed us, and the Chief Shepherd who will soon appear (1:19; 5:4).",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Living Hope", "Suffering & Glory", "Elect Exiles", "Royal Priesthood", "Precious Blood"),
    ),
    61: BookHorizon(
        book_id=61, name="2 Peter", osis="2Pet", testament="NT",
        genre="General Epistle", author="Peter the Apostle", date_range="c. AD 64-67",
        historical_setting="Peter's final testament before martyrdom, warning against insidious, antinomian false teachers.",
        theological_theme="True knowledge of God, moral virtue, the reliability of prophetic Scripture, and the certainty of the Day of the Lord.",
        christological_anticipation="The coming of the Day of the Lord and the creation of new heavens and a new earth in which righteousness dwells (3:13).",
        storyline_epoch=RedemptiveEpoch.CONSUMMATION.value,
        key_motifs=("Sure Prophetic Word", "False Teachers Exposed", "Day of the Lord", "New Heavens & Earth", "Growth in Grace"),
    ),
    62: BookHorizon(
        book_id=62, name="1 John", osis="1John", testament="NT",
        genre="General Epistle", author="John the Apostle", date_range="c. AD 85-95",
        historical_setting="Pastoral letter written to churches in Asia Minor combating proto-Gnostic deceivers denying Jesus' real incarnation.",
        theological_theme="Assurance of eternal life tested by three criteria: doctrinal truth (Jesus came in the flesh), moral obedience, and brotherly love.",
        christological_anticipation="Jesus Christ the righteous, our Advocate with the Father and the propitiation for our sins (2:1-2; 4:10).",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Fellowship in the Light", "Assurance of Salvation", "Love One Another", "Christ Our Advocate", "God is Love"),
    ),
    63: BookHorizon(
        book_id=63, name="2 John", osis="2John", testament="NT",
        genre="General Epistle", author="John the Apostle", date_range="c. AD 85-95",
        historical_setting="Short pastoral note to the 'elect lady and her children' concerning traveling teachers.",
        theological_theme="Walking in truth and love while maintaining strict doctrinal discernment against antichrist deceivers.",
        christological_anticipation="Guarding the apostolic doctrine of Christ incarnate.",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Truth & Love", "Hospitality Discernment", "Doctrine of Christ", "Abiding in Truth", "Antichrist Warning"),
    ),
    64: BookHorizon(
        book_id=64, name="3 John", osis="3John", testament="NT",
        genre="General Epistle", author="John the Apostle", date_range="c. AD 85-95",
        historical_setting="Personal letter to Gaius commending hospitality to traveling gospel workers despite Diotrephes' prideful opposition.",
        theological_theme="Faithful support for gospel truth and warning against domineering, arrogant leadership in the local church.",
        christological_anticipation="Working together for the sake of the Name of Jesus Christ.",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Gospel Hospitality", "Walking in Truth", "Humble vs Arrogant Leadership", "Fellow Workers", "For the Name"),
    ),
    65: BookHorizon(
        book_id=65, name="Jude", osis="Jude", testament="NT",
        genre="General Epistle", author="Jude the brother of James and the Lord", date_range="c. AD 65-70",
        historical_setting="Urgent letter warning the church against ungodly infiltrators who pervert God's grace into sensuality.",
        theological_theme="Contending earnestly for the faith once for all delivered to the saints, trusting in God who is able to keep us from stumbling.",
        christological_anticipation="Looking for the mercy of our Lord Jesus Christ that leads to eternal life, presenting us blameless before His glory (vv. 21, 24).",
        storyline_epoch=RedemptiveEpoch.APOSTOLIC_CHURCH.value,
        key_motifs=("Contend for the Faith", "Perversion of Grace", "Divine Judgment", "Kept from Stumbling", "Doxology of Glory"),
    ),
    66: BookHorizon(
        book_id=66, name="Revelation", osis="Rev", testament="NT",
        genre="Apocalyptic", author="John the Apostle", date_range="c. AD 95",
        historical_setting="Exiled on the island of Patmos during the reign of Domitian, writing to seven churches in Asia Minor.",
        theological_theme="The apocalyptic unveiling of Jesus Christ as the triumphant Lamb who conquers Satan, Babylon, and death, ushering in the New Jerusalem.",
        christological_anticipation="The Lion of Judah who is the slain Lamb, King of kings and Lord of lords, returning to reign forever with His Bride (5:5-6; 19:16; 21:1-4).",
        storyline_epoch=RedemptiveEpoch.CONSUMMATION.value,
        key_motifs=("The Slain Lamb", "Triumph Over Dragon", "New Jerusalem", "Marriage Supper of the Lamb", "He Makes All Things New"),
    ),
}


def get_book_horizon(book_identifier: Union[int, str, Book]) -> BookHorizon:
    """Retrieve canonical BookHorizon by book ID (1-66), name, OSIS, or Book object."""
    if isinstance(book_identifier, int):
        if book_identifier in BOOK_HORIZONS:
            return BOOK_HORIZONS[book_identifier]
        b = BOOKS.get(book_identifier)
        if not b:
            raise ValueError(f"Invalid canonical book ID: {book_identifier}")
    elif isinstance(book_identifier, Book):
        b = book_identifier
    else:
        b = get_book(str(book_identifier))
        if not b:
            raise ValueError(f"Unrecognized book identifier: {book_identifier}")

    if b.number in BOOK_HORIZONS:
        return BOOK_HORIZONS[b.number]

    # Fallback default horizon
    return BookHorizon(
        book_id=b.number,
        name=b.name,
        osis=b.osis,
        testament=b.testament,
        genre="Canonical Scripture",
        author="Canonical Witness",
        date_range="Biblical Era",
        historical_setting=f"Canonical witness of {b.name}.",
        theological_theme=f"God's redemptive revelation in {b.name}.",
        christological_anticipation="Witnessing to God's redemptive climax in Jesus Christ.",
        storyline_epoch=(
            RedemptiveEpoch.PATRIARCHAL_COVENANT.value
            if b.testament == "OT"
            else RedemptiveEpoch.APOSTOLIC_CHURCH.value
        ),
        key_motifs=("Covenant", "Faithfulness", "Redemption"),
    )


# ==============================================================================
# Stratified Exegetical Data Models & DTOs
# ==============================================================================


@dataclass(frozen=True)
class PericopeAnalysisInput:
    """Input payload for generating a stratified pericope analysis prompt."""

    reference: Union[Reference, str]
    passage_text: str
    book_horizon: Optional[BookHorizon] = None
    preceding_context: str = ""
    following_context: str = ""
    translation_id: str = "ESV"

    def get_reference_obj(self) -> Reference:
        """Parse or return canonical Reference object."""
        if isinstance(self.reference, Reference):
            return self.reference
        return parse_reference(self.reference)

    def get_book_horizon(self) -> BookHorizon:
        """Return explicit or auto-resolved BookHorizon."""
        if self.book_horizon:
            return self.book_horizon
        ref = self.get_reference_obj()
        return get_book_horizon(ref.book)


@dataclass(frozen=True)
class DiscourseRelationData:
    """Represents an extracted discourse connective or rhetorical relation."""

    source_verse: str
    target_verse: Optional[str] = None
    relation_type: str = "ground"
    marker_text: Optional[str] = None
    greek_marker: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert discourse relation to dictionary representation."""
        return {
            "source_verse": self.source_verse,
            "target_verse": self.target_verse,
            "relation_type": self.relation_type,
            "marker_text": self.marker_text,
            "greek_marker": self.greek_marker,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class VerseTheologyData:
    """Represents a theological classification along redemptive epochs and systematic loci."""

    verse_ref: str
    storyline_epoch: str
    theological_locus: str
    primary_doctrine: str
    thematic_ribbon: Optional[str] = None
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert verse theology data to dictionary representation."""
        return {
            "verse_ref": self.verse_ref,
            "storyline_epoch": self.storyline_epoch,
            "theological_locus": self.theological_locus,
            "primary_doctrine": self.primary_doctrine,
            "thematic_ribbon": self.thematic_ribbon,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class TypologicalArcData:
    """Represents an extracted typological correspondence between OT type and NT fulfillment."""

    type_ref: str
    type_name: str
    antitype_ref: str
    antitype_name: str
    theological_correspondence: str
    warrant: Optional[str] = None
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert typological arc data to dictionary representation."""
        return {
            "type_ref": self.type_ref,
            "type_name": self.type_name,
            "antitype_ref": self.antitype_ref,
            "antitype_name": self.antitype_name,
            "theological_correspondence": self.theological_correspondence,
            "warrant": self.warrant,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class SemanticPropositionData:
    """Represents an agent-action-patient micro-proposition, speech act, and affect tone."""

    verse_ref: str
    speech_act: str
    agent: str
    action: str
    patient: Optional[str] = None
    tone: Optional[str] = None
    clause_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert semantic proposition to dictionary representation."""
        return {
            "verse_ref": self.verse_ref,
            "speech_act": self.speech_act,
            "agent": self.agent,
            "action": self.action,
            "patient": self.patient,
            "tone": self.tone,
            "clause_text": self.clause_text,
        }


@dataclass(frozen=True)
class PericopeAnalysisResult:
    """Complete structured result produced by stratified exegesis."""

    reference: str
    title: str
    genre: str
    literary_structure: str
    central_proposition: str
    redemptive_summary: str
    christological_fulfillment: str
    discourse_relations: List[DiscourseRelationData] = field(default_factory=list)
    verse_theologies: List[VerseTheologyData] = field(default_factory=list)
    typological_arcs: List[TypologicalArcData] = field(default_factory=list)
    semantic_propositions: List[SemanticPropositionData] = field(default_factory=list)
    raw_json: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert complete pericope analysis result to dictionary representation."""
        return {
            "reference": self.reference,
            "title": self.title,
            "genre": self.genre,
            "literary_structure": self.literary_structure,
            "central_proposition": self.central_proposition,
            "redemptive_summary": self.redemptive_summary,
            "christological_fulfillment": self.christological_fulfillment,
            "discourse_relations": [d.to_dict() for d in self.discourse_relations],
            "verse_theology": [v.to_dict() for v in self.verse_theologies],
            "typological_arcs": [t.to_dict() for t in self.typological_arcs],
            "semantic_propositions": [p.to_dict() for p in self.semantic_propositions],
        }

    def to_db_records(
        self,
        default_book_id: Optional[int] = None,
    ) -> Tuple[
        PericopeRecord,
        List[DiscourseRelationRecord],
        List[VerseTheologyRecord],
        List[TypologicalArcRecord],
        List[SemanticPropositionRecord],
    ]:
        """Convert parsed analysis result into database records ready for batch insertion."""
        # 1. Resolve Pericope Coordinates
        ref_obj = parse_reference(self.reference)
        book_id = ref_obj.book.number if ref_obj.book else (default_book_id or 1)
        book_ref = ref_obj.book

        pericope_rec = PericopeRecord(
            id=None,
            book_id=book_id,
            start_canonical_id=ref_obj.canonical_start_id,
            end_canonical_id=ref_obj.canonical_end_id,
            human_ref=ref_obj.format(),
            title=self.title,
            redemptive_summary=self.redemptive_summary,
            genre=self.genre,
            literary_structure=self.literary_structure,
            central_proposition=self.central_proposition,
        )

        # Helper to resolve relative verse references within context
        def _resolve_ref(
            text_ref: str,
            default_ch: int = ref_obj.start_chapter,
        ) -> Optional[Reference]:
            if not text_ref or not text_ref.strip():
                return None
            clean = text_ref.strip()
            # If plain verse number e.g. "28" or "v. 28"
            m_v = re.match(r"^(?:v(?:erse)?\.?\s*)?(\d+)([a-z]?)$", clean, re.IGNORECASE)
            if m_v and book_ref:
                try:
                    return parse_reference(f"{book_ref.name} {default_ch}:{m_v.group(1)}{m_v.group(2)}")
                except Exception:
                    pass
            # If chapter:verse e.g. "8:28"
            m_cv = re.match(r"^(\d+):(\d+.*)$", clean)
            if m_cv and book_ref:
                try:
                    return parse_reference(f"{book_ref.name} {clean}")
                except Exception:
                    pass
            try:
                return parse_reference(clean)
            except Exception:
                return None

        # 2. Discourse Relations
        discourse_recs: List[DiscourseRelationRecord] = []
        for dr in self.discourse_relations:
            src = _resolve_ref(dr.source_verse)
            if not src:
                continue
            tgt = _resolve_ref(dr.target_verse) if dr.target_verse else None
            discourse_recs.append(
                DiscourseRelationRecord(
                    id=None,
                    source_canonical_id=src.canonical_start_id,
                    source_human_ref=src.format(),
                    relation_type=dr.relation_type,
                    target_canonical_id=tgt.canonical_start_id if tgt else None,
                    target_human_ref=tgt.format() if tgt else None,
                    marker_text=dr.marker_text,
                    greek_marker=dr.greek_marker,
                    notes=dr.notes,
                )
            )

        # 3. Verse Theologies
        theology_recs: List[VerseTheologyRecord] = []
        for vt in self.verse_theologies:
            r = _resolve_ref(vt.verse_ref) or ref_obj
            theology_recs.append(
                VerseTheologyRecord(
                    id=None,
                    start_canonical_id=r.canonical_start_id,
                    end_canonical_id=r.canonical_end_id,
                    human_ref=r.format(),
                    storyline_epoch=vt.storyline_epoch,
                    theological_locus=vt.theological_locus,
                    primary_doctrine=vt.primary_doctrine,
                    thematic_ribbon=vt.thematic_ribbon,
                    confidence=vt.confidence,
                )
            )

        # 4. Typological Arcs
        typology_recs: List[TypologicalArcRecord] = []
        for ta in self.typological_arcs:
            type_r = _resolve_ref(ta.type_ref)
            antitype_r = _resolve_ref(ta.antitype_ref)
            if not type_r or not antitype_r:
                continue
            typology_recs.append(
                TypologicalArcRecord(
                    id=None,
                    type_start_id=type_r.canonical_start_id,
                    type_end_id=type_r.canonical_end_id,
                    type_human_ref=type_r.format(),
                    antitype_start_id=antitype_r.canonical_start_id,
                    antitype_end_id=antitype_r.canonical_end_id,
                    antitype_human_ref=antitype_r.format(),
                    theological_correspondence=ta.theological_correspondence,
                    warrant=ta.warrant,
                    confidence=ta.confidence,
                )
            )

        # 5. Semantic Propositions
        prop_recs: List[SemanticPropositionRecord] = []
        for sp in self.semantic_propositions:
            r = _resolve_ref(sp.verse_ref) or ref_obj
            prop_recs.append(
                SemanticPropositionRecord(
                    id=None,
                    canonical_verse_id=r.canonical_start_id,
                    human_ref=r.format(),
                    speech_act=sp.speech_act,
                    agent=sp.agent,
                    action=sp.action,
                    patient=sp.patient,
                    tone=sp.tone,
                    clause_text=sp.clause_text,
                )
            )

        return pericope_rec, discourse_recs, theology_recs, typology_recs, prop_recs


# ==============================================================================
# Prompt Generator Architecture
# ==============================================================================


class SemanticPromptGenerator:
    """Generates stratified exegetical prompts adhering to TGC Foundation Documents."""

    def __init__(self, guardrails: Optional[TheologicalGuardrails] = None) -> None:
        self.guardrails = guardrails or TheologicalGuardrails()

    def format_book_horizon(self, horizon: BookHorizon) -> str:
        """Render markdown text block representing Layer 0 Macro-Book context."""
        motifs_str = ", ".join(f"`{m}`" for m in horizon.key_motifs)
        return f"""### Layer 0: Macro-Book Context ({horizon.name})
- **Canon & Testament**: {horizon.name} ({horizon.osis}), {horizon.testament}
- **Genre & Author**: {horizon.genre} by {horizon.author} ({horizon.date_range})
- **Historical Setting**: {horizon.historical_setting}
- **Overarching Theological Theme**: {horizon.theological_theme}
- **Christological Trajectory**: {horizon.christological_anticipation}
- **Primary Redemptive Epoch**: `{horizon.storyline_epoch}`
- **Key Canonical Motifs**: {motifs_str}""".strip()

    def build_pericope_prompt(self, input_data: PericopeAnalysisInput) -> str:
        """Build a comprehensive, stratified exegetical prompt for pericope analysis."""
        ref_obj = input_data.get_reference_obj()
        horizon = input_data.get_book_horizon()
        human_ref = ref_obj.format()

        horizon_block = self.format_book_horizon(horizon)
        guardrail_block = self.guardrails.build_directive_text()

        epochs_list = ", ".join(f"`{e.value}`" for e in RedemptiveEpoch)
        loci_list = ", ".join(f"`{l.value}`" for l in TheologicalLocus)
        ribbons_list = ", ".join(f"`{r.value}`" for r in ThematicRibbon)
        relations_list = ", ".join(f"`{rel}`" for rel in DISCOURSE_RELATION_TYPES)
        speech_acts_list = ", ".join(f"`{sa}`" for sa in SPEECH_ACT_TYPES)

        # Immediate surrounding context blocks
        context_section = ""
        if input_data.preceding_context:
            context_section += f"- **Preceding Context**:\n\"\"\"{input_data.preceding_context.strip()}\"\"\"\n"
        if input_data.following_context:
            context_section += f"- **Following Context**:\n\"\"\"{input_data.following_context.strip()}\"\"\"\n"

        return f"""You are executing an exhaustive, stratified exegetical and theological analysis of Scripture for the Bible Engine, governed by The Gospel Coalition (TGC) Foundation Documents (THEOLOGY.md).

{guardrail_block}

{horizon_block}

### Target Scripture Passage
- **Citation**: {human_ref}
- **Translation**: {input_data.translation_id}
- **Passage Text**:
\"\"\"{input_data.passage_text.strip()}\"\"\"
{context_section}
### Stratified Analytical Directives

1. **Layer 1: Pericope Structure & Propositions**
   - Provide a dignified, Christ-centered `title`.
   - Identify the specific `genre` (e.g., Narrative, Chiasm, Expository Discourse, Parable, Doxology).
   - Outline the `literary_structure` (chiasm, progressive parallelism, or structural outline).
   - Formulate a single, concise `central_proposition` expressing the exegetical thesis of the author.
   - Summarize the `redemptive_summary` (1-2 sentences) situating this unit within God's historical plan.
   - Articulate the `christological_fulfillment` (1-2 paragraphs) demonstrating how this passage points to, prepares for, or flows from the person, offices, and finished substitutionary work of Jesus Christ.

2. **Layer 2: Discourse Rhetoric & Propositional Flow**
   - Identify rhetorical connectives linking verses or key clauses.
   - For each relation, specify:
     * `source_verse`: citation (e.g. "{ref_obj.book.name} {ref_obj.start_chapter}:{ref_obj.start_verse}")
     * `target_verse`: citation connected to, or null
     * `relation_type`: one of {relations_list}
     * `marker_text`: English connective (e.g., "for", "therefore", "in order that", "but")
     * `greek_marker`: original Greek/Hebrew particle if known (e.g. "γάρ", "οὖν", "ἵνα"), or null
     * `notes`: concise explanation of rhetorical function

3. **Layer 3: Dual-Horizon Theological Classification**
   - Classify the theological content across verses or the whole passage:
     * `verse_ref`: specific verse or span (e.g. "{human_ref}")
     * `storyline_epoch`: exactly one of {epochs_list}
     * `theological_locus`: exactly one of {loci_list}
     * `primary_doctrine`: standard systematic formulation (e.g., "Justification by Faith Alone", "Sovereign Election", "Penal Substitution")
     * `thematic_ribbon`: optional cross-canonical ribbon from {ribbons_list}
     * `confidence`: float between 0.0 and 1.0

4. **Layer 4: Canonical Typology & Intertextual Arcs**
   - Extract typological correspondences (OT types/shadows to NT antitypes/fulfillments):
     * `type_ref`: Old Testament passage citation
     * `type_name`: description of type/shadow (e.g., "Melchizedek the Priest-King")
     * `antitype_ref`: New Testament passage citation
     * `antitype_name`: description of antitype fulfillment (e.g., "Christ's Eternal Priesthood")
     * `theological_correspondence`: explanation of how the type foreshadows Christ
     * `warrant`: `explicit_nt_citation` or `canonical_thematic_pattern`
     * `confidence`: float between 0.0 and 1.0

5. **Layer 5: Semantic Propositions & Agent Triples**
   - Extract micro-propositional triples for key verses:
     * `verse_ref`: citation (e.g. "{ref_obj.book.name} {ref_obj.start_chapter}:{ref_obj.start_verse}")
     * `speech_act`: one of {speech_acts_list}
     * `agent`: who is acting (e.g. "God", "Jesus Christ", "Holy Spirit", "Paul", "Believer")
     * `action`: verb or action phrase
     * `patient`: recipient or direct object, or null
     * `tone`: emotional affect or devotional tone (e.g. "pastoral assurance", "holy awe", "triumphant confidence")
     * `clause_text`: excerpted clause from text

### Output Format Specification (Strict JSON Only)
Return ONLY a valid JSON object matching this exact schema:
```json
{{
  "reference": "{human_ref}",
  "title": "<pericope_title>",
  "genre": "<literary_genre>",
  "literary_structure": "<structural_outline_or_chiasm>",
  "central_proposition": "<single_sentence_main_idea>",
  "redemptive_summary": "<redemptive_historical_summary>",
  "christological_fulfillment": "<christ_centered_explanation>",
  "discourse_relations": [
    {{
      "source_verse": "{ref_obj.book.name} {ref_obj.start_chapter}:{ref_obj.start_verse}",
      "target_verse": null,
      "relation_type": "ground",
      "marker_text": "for",
      "greek_marker": "γάρ",
      "notes": "Explains foundational reason"
    }}
  ],
  "verse_theology": [
    {{
      "verse_ref": "{human_ref}",
      "storyline_epoch": "{horizon.storyline_epoch}",
      "theological_locus": "soteriology",
      "primary_doctrine": "Justification by Faith Alone",
      "thematic_ribbon": "covenant_grace",
      "confidence": 1.0
    }}
  ],
  "typological_arcs": [
    {{
      "type_ref": "<ot_reference>",
      "type_name": "<type_description>",
      "antitype_ref": "<nt_reference>",
      "antitype_name": "<antitype_description>",
      "theological_correspondence": "<explanation>",
      "warrant": "explicit_nt_citation",
      "confidence": 1.0
    }}
  ],
  "semantic_propositions": [
    {{
      "verse_ref": "{ref_obj.book.name} {ref_obj.start_chapter}:{ref_obj.start_verse}",
      "speech_act": "promise",
      "agent": "God",
      "action": "works all things together for good",
      "patient": "those who love Him",
      "tone": "triumphant assurance",
      "clause_text": "for those who love God all things work together for good"
    }}
  ]
}}
```
Do not include conversational preamble or markdown formatting beyond the json block.""".strip()

    def build_typology_prompt(
        self,
        type_ref: str,
        type_text: str,
        antitype_ref: Optional[str] = None,
        antitype_text: Optional[str] = None,
    ) -> str:
        """Build focused prompt for deep typological arc extraction."""
        guardrail_block = self.guardrails.build_directive_text()
        antitype_block = ""
        if antitype_ref and antitype_text:
            antitype_block = f"\n### Candidate Antitype\n- **Reference**: {antitype_ref}\n- **Text**: \"\"\"{antitype_text.strip()}\"\"\"\n"

        return f"""You are analyzing biblical typology and canonical correspondences for the Bible Engine.

{guardrail_block}

### Old Testament Shadow / Type
- **Reference**: {type_ref}
- **Text**: \"\"\"{type_text.strip()}\"\"\"
{antitype_block}
### Typological Directives
1. Identify the historical-redemptive correspondence between the Old Testament type (institution, person, office, event, or object) and its New Testament Christological fulfillment.
2. Ensure the correspondence is grounded in organic biblical theology and covenantal continuity, avoiding allegorical flight.
3. Formulate the warrant level (`explicit_nt_citation` if quoted by NT authors, or `canonical_thematic_pattern`).

### Output Schema (Strict JSON)
```json
{{
  "type_ref": "{type_ref}",
  "type_name": "<name_of_type>",
  "antitype_ref": "<nt_fulfillment_ref>",
  "antitype_name": "<name_of_antitype>",
  "theological_correspondence": "<detailed_theological_explanation>",
  "warrant": "explicit_nt_citation|canonical_thematic_pattern",
  "confidence": 1.0
}}
```""".strip()

    def build_discourse_prompt(
        self,
        reference: Union[Reference, str],
        passage_text: str,
    ) -> str:
        """Build focused prompt for micro-level discourse rhetoric analysis."""
        ref_obj = parse_reference(reference) if isinstance(reference, str) else reference
        human_ref = ref_obj.format()
        relations_list = ", ".join(f"`{rel}`" for rel in DISCOURSE_RELATION_TYPES)

        return f"""Analyze the micro-level discourse logic and rhetorical flow of the following passage.

- **Reference**: {human_ref}
- **Text**:
\"\"\"{passage_text.strip()}\"\"\"

Identify all propositional connectives and clause relations. Relation types must be chosen from: {relations_list}.

### Output Schema (Strict JSON)
```json
{{
  "reference": "{human_ref}",
  "discourse_relations": [
    {{
      "source_verse": "<verse_ref>",
      "target_verse": "<target_ref_or_null>",
      "relation_type": "ground|inference|purpose|contrast|condition|concession|result|temporal",
      "marker_text": "<connective_word_in_english>",
      "greek_marker": "<greek_or_hebrew_particle_or_null>",
      "notes": "<concise_logical_function>"
    }}
  ]
}}
```""".strip()


# ==============================================================================
# JSON Response Parser & Normalizer
# ==============================================================================


def _extract_json_substring(raw_text: str) -> str:
    """Extract clean JSON substring from potential markdown wrappers or preamble."""
    text = raw_text.strip()
    # Check for ```json ... ``` or ``` ... ```
    m_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m_block:
        return m_block.group(1).strip()
    # Check for direct outermost braces
    m_outer = re.search(r"(\{.*\})", text, re.DOTALL)
    if m_outer:
        return m_outer.group(1).strip()
    return text


def _normalize_enum_value(
    val: Optional[str],
    enum_cls: Any,
    default_val: str,
) -> str:
    """Normalize user or LLM input string to canonical enum value."""
    if not val:
        return default_val
    # Strip non-alphanumeric/space characters and normalize spaces/hyphens to underscore
    clean = re.sub(r"[^\w\s]", " ", val.strip().lower())
    clean = re.sub(r"[\s\-]+", "_", clean).strip("_")
    # Check direct match
    for item in enum_cls:
        if clean == item.value.lower() or clean == item.name.lower():
            return item.value
    # Check partial match
    for item in enum_cls:
        if clean in item.value.lower() or item.value.lower() in clean:
            return item.value
    return default_val


def parse_pericope_analysis_json(raw_text: str) -> PericopeAnalysisResult:
    """Parse, validate, and normalize raw LLM output into a PericopeAnalysisResult."""
    clean_json = _extract_json_substring(raw_text)
    try:
        data = json.loads(clean_json)
    except json.JSONDecodeError as err:
        raise ValueError(f"Failed to parse LLM pericope response as JSON: {err}\nPayload: {raw_text[:200]}") from err

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in pericope analysis response, got {type(data).__name__}")

    ref_str = str(data.get("reference") or "Unknown")
    title = str(data.get("title") or "Untitled Pericope").strip()
    genre = str(data.get("genre") or "Biblical Text").strip()
    literary_structure = str(data.get("literary_structure") or "").strip()
    central_proposition = str(data.get("central_proposition") or "").strip()
    redemptive_summary = str(data.get("redemptive_summary") or "").strip()
    christological_fulfillment = str(data.get("christological_fulfillment") or "").strip()

    # 1. Parse Discourse Relations
    raw_discourse = data.get("discourse_relations") or []
    discourse_list: List[DiscourseRelationData] = []
    if isinstance(raw_discourse, list):
        for item in raw_discourse:
            if not isinstance(item, dict):
                continue
            src = str(item.get("source_verse") or "").strip()
            if not src:
                continue
            tgt = item.get("target_verse")
            tgt_str = str(tgt).strip() if tgt else None
            rel = str(item.get("relation_type") or "ground").strip().lower()
            if rel not in DISCOURSE_RELATION_TYPES:
                rel = "ground"
            discourse_list.append(
                DiscourseRelationData(
                    source_verse=src,
                    target_verse=tgt_str,
                    relation_type=rel,
                    marker_text=item.get("marker_text"),
                    greek_marker=item.get("greek_marker"),
                    notes=item.get("notes"),
                )
            )

    # 2. Parse Verse Theology Classifications
    raw_theology = data.get("verse_theology") or []
    theology_list: List[VerseTheologyData] = []
    if isinstance(raw_theology, list):
        for item in raw_theology:
            if not isinstance(item, dict):
                continue
            vref = str(item.get("verse_ref") or ref_str).strip()
            epoch = _normalize_enum_value(
                item.get("storyline_epoch"),
                RedemptiveEpoch,
                RedemptiveEpoch.PATRIARCHAL_COVENANT.value,
            )
            locus = _normalize_enum_value(
                item.get("theological_locus"),
                TheologicalLocus,
                TheologicalLocus.SOTERIOLOGY.value,
            )
            doctrine = str(item.get("primary_doctrine") or "General Revelation").strip()
            ribbon_raw = item.get("thematic_ribbon")
            ribbon = (
                _normalize_enum_value(ribbon_raw, ThematicRibbon, ThematicRibbon.COVENANT_GRACE.value)
                if ribbon_raw
                else None
            )
            conf = float(item.get("confidence") or 1.0)
            conf = max(0.0, min(1.0, conf))
            theology_list.append(
                VerseTheologyData(
                    verse_ref=vref,
                    storyline_epoch=epoch,
                    theological_locus=locus,
                    primary_doctrine=doctrine,
                    thematic_ribbon=ribbon,
                    confidence=conf,
                )
            )

    # 3. Parse Typological Arcs
    raw_typology = data.get("typological_arcs") or []
    typology_list: List[TypologicalArcData] = []
    if isinstance(raw_typology, list):
        for item in raw_typology:
            if not isinstance(item, dict):
                continue
            t_ref = str(item.get("type_ref") or "").strip()
            t_name = str(item.get("type_name") or "").strip()
            at_ref = str(item.get("antitype_ref") or "").strip()
            at_name = str(item.get("antitype_name") or "").strip()
            corr = str(item.get("theological_correspondence") or "").strip()
            if not t_ref or not at_ref or not corr:
                continue
            warrant = str(item.get("warrant") or "canonical_thematic_pattern").strip()
            conf = float(item.get("confidence") or 1.0)
            conf = max(0.0, min(1.0, conf))
            typology_list.append(
                TypologicalArcData(
                    type_ref=t_ref,
                    type_name=t_name or t_ref,
                    antitype_ref=at_ref,
                    antitype_name=at_name or at_ref,
                    theological_correspondence=corr,
                    warrant=warrant,
                    confidence=conf,
                )
            )

    # 4. Parse Semantic Propositions
    raw_props = data.get("semantic_propositions") or []
    prop_list: List[SemanticPropositionData] = []
    if isinstance(raw_props, list):
        for item in raw_props:
            if not isinstance(item, dict):
                continue
            vref = str(item.get("verse_ref") or ref_str).strip()
            sa = str(item.get("speech_act") or "indicative").strip().lower()
            if sa not in SPEECH_ACT_TYPES:
                sa = "indicative"
            agent = str(item.get("agent") or "God").strip()
            action = str(item.get("action") or "").strip()
            if not action:
                continue
            patient = item.get("patient")
            patient_str = str(patient).strip() if patient else None
            tone = item.get("tone")
            tone_str = str(tone).strip() if tone else None
            clause = item.get("clause_text")
            clause_str = str(clause).strip() if clause else None
            prop_list.append(
                SemanticPropositionData(
                    verse_ref=vref,
                    speech_act=sa,
                    agent=agent,
                    action=action,
                    patient=patient_str,
                    tone=tone_str,
                    clause_text=clause_str,
                )
            )

    return PericopeAnalysisResult(
        reference=ref_str,
        title=title,
        genre=genre,
        literary_structure=literary_structure,
        central_proposition=central_proposition,
        redemptive_summary=redemptive_summary,
        christological_fulfillment=christological_fulfillment,
        discourse_relations=discourse_list,
        verse_theologies=theology_list,
        typological_arcs=typology_list,
        semantic_propositions=prop_list,
        raw_json=data,
    )


# ==============================================================================
# Module Singletons & Convenience Functions
# ==============================================================================

_DEFAULT_PROMPT_GENERATOR = SemanticPromptGenerator()


def get_semantic_prompt_generator() -> SemanticPromptGenerator:
    """Return default singleton SemanticPromptGenerator."""
    return _DEFAULT_PROMPT_GENERATOR


def generate_pericope_prompt(
    reference: Union[Reference, str],
    passage_text: str,
    book_horizon: Optional[BookHorizon] = None,
    preceding_context: str = "",
    following_context: str = "",
    translation_id: str = "ESV",
) -> str:
    """Convenience helper to generate a complete stratified pericope prompt."""
    inp = PericopeAnalysisInput(
        reference=reference,
        passage_text=passage_text,
        book_horizon=book_horizon,
        preceding_context=preceding_context,
        following_context=following_context,
        translation_id=translation_id,
    )
    return _DEFAULT_PROMPT_GENERATOR.build_pericope_prompt(inp)


def parse_pericope_response(raw_text: str) -> PericopeAnalysisResult:
    """Convenience helper to parse and validate LLM pericope JSON output."""
    return parse_pericope_analysis_json(raw_text)
