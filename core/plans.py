"""Curated Reading Plans & Scripture Collections for Bible Engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003).
Provides curated biblical reading plans, thematic scripture sequences, and
liturgical passage collections for study, prayer, and batch TV screensaver export.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ReadingPlan:
    """Represents a curated biblical reading plan or scripture collection."""

    name: str
    title: str
    description: str
    category: str
    passages: Tuple[str, ...]
    tags: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def passage_count(self) -> int:
        """Total number of passages in this plan."""
        return len(self.passages)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize reading plan to dictionary."""
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "passage_count": self.passage_count,
            "passages": list(self.passages),
            "tags": list(self.tags),
        }


# ==============================================================================
# Built-In Curated Reading Plans & Scripture Collections
# ==============================================================================

STANDARD_PLANS: Dict[str, ReadingPlan] = {
    "psalms_of_ascent": ReadingPlan(
        name="psalms_of_ascent",
        title="Psalms of Ascent (Songs of the Pilgrim)",
        description=(
            "The 15 pilgrim songs (Psalms 120-134) sung by worshippers traveling up "
            "to Jerusalem and the sacred Temple for the annual feasts."
        ),
        category="psalms",
        passages=(
            "Psalm 120",
            "Psalm 121",
            "Psalm 122",
            "Psalm 123",
            "Psalm 124",
            "Psalm 125",
            "Psalm 126",
            "Psalm 127",
            "Psalm 128",
            "Psalm 129",
            "Psalm 130",
            "Psalm 131",
            "Psalm 132",
            "Psalm 133",
            "Psalm 134",
        ),
        tags=("Psalms", "Worship", "Pilgrimage", "Temple", "Trust"),
    ),
    "sermon_on_the_mount": ReadingPlan(
        name="sermon_on_the_mount",
        title="Sermon on the Mount (Kingdom Manifesto)",
        description=(
            "Jesus Christ's seminal sermon from Matthew 5-7 establishing the character, "
            "righteousness, and posture of citizens of the Kingdom of Heaven."
        ),
        category="gospel",
        passages=(
            "Matthew 5:1-12",
            "Matthew 5:13-16",
            "Matthew 5:17-20",
            "Matthew 5:21-26",
            "Matthew 5:27-30",
            "Matthew 5:38-48",
            "Matthew 6:1-4",
            "Matthew 6:5-15",
            "Matthew 6:19-24",
            "Matthew 6:25-34",
            "Matthew 7:1-6",
            "Matthew 7:7-12",
            "Matthew 7:13-14",
            "Matthew 7:24-27",
        ),
        tags=("Gospel", "Kingdom of God", "Discipleship", "Righteousness", "Prayer"),
    ),
    "romans_road": ReadingPlan(
        name="romans_road",
        title="The Romans Road to Salvation",
        description=(
            "The foundational theological progression through Paul's Epistle to the Romans "
            "articulating universal sin, redemption in Christ, justification by faith alone, "
            "peace with God, and eternal security."
        ),
        category="theology",
        passages=(
            "Romans 3:23",
            "Romans 6:23",
            "Romans 5:8",
            "Romans 10:9-10",
            "Romans 5:1-2",
            "Romans 8:1-2",
            "Romans 8:38-39",
        ),
        tags=("Gospel", "Salvation", "Justification", "Grace", "Atonement"),
    ),
    "messianic_prophecies": ReadingPlan(
        name="messianic_prophecies",
        title="Messianic Prophecies & Fulfillment",
        description=(
            "Key Old Testament prophecies, types, and promises fulfilled in Jesus Christ: "
            "the seed of the woman, the suffering servant, the eternal priest-king, and the virgin birth."
        ),
        category="typology",
        passages=(
            "Genesis 3:15",
            "Genesis 22:18",
            "Deuteronomy 18:15",
            "Psalm 2:7-8",
            "Psalm 22:1-18",
            "Psalm 110:1-4",
            "Isaiah 7:14",
            "Isaiah 9:6-7",
            "Isaiah 53:1-12",
            "Micah 5:2",
            "Zechariah 9:9",
            "Malachi 3:1",
        ),
        tags=("Prophecy", "Christology", "Typology", "Redemption", "Messiah"),
    ),
    "comfort_and_peace": ReadingPlan(
        name="comfort_and_peace",
        title="Scriptures of Comfort, Solace, and Divine Peace",
        description=(
            "Timeless scriptures declaring God's sovereign protection, shepherd's care, "
            "solace in tribulation, and transcendent supernatural peace."
        ),
        category="devotional",
        passages=(
            "Psalm 23:1-6",
            "Psalm 46:1-11",
            "Psalm 91:1-16",
            "Psalm 121:1-8",
            "Isaiah 40:28-31",
            "Matthew 11:28-30",
            "John 14:1-6",
            "John 14:27",
            "Romans 8:28-39",
            "Philippians 4:4-9",
            "1 Peter 5:6-7",
            "Revelation 21:1-4",
        ),
        tags=("Peace", "Comfort", "Trust", "Preservation", "Hope"),
    ),
    "creation_and_covenant": ReadingPlan(
        name="creation_and_covenant",
        title="The Arc of Redemptive Covenants",
        description=(
            "The grand theological storyline of God's unfolding covenants with humanity: "
            "from Creation and the Fall to Noah, Abraham, Israel, David, and the New Covenant."
        ),
        category="theology",
        passages=(
            "Genesis 1:1-5",
            "Genesis 1:26-28",
            "Genesis 2:1-3",
            "Genesis 3:14-19",
            "Genesis 9:8-17",
            "Genesis 12:1-3",
            "Genesis 15:1-6",
            "Exodus 19:3-6",
            "2 Samuel 7:12-16",
            "Jeremiah 31:31-34",
            "Luke 22:19-20",
        ),
        tags=("Covenant", "Creation", "Redemptive History", "Kingdom", "Promise"),
    ),
    "beatitudes": ReadingPlan(
        name="beatitudes",
        title="The Beatitudes (Kingdom Character)",
        description=(
            "The eight blessings declared by Jesus in Matthew 5 revealing the humble, "
            "meek, merciful, and pure heart wrought by divine grace."
        ),
        category="gospel",
        passages=(
            "Matthew 5:3",
            "Matthew 5:4",
            "Matthew 5:5",
            "Matthew 5:6",
            "Matthew 5:7",
            "Matthew 5:8",
            "Matthew 5:9",
            "Matthew 5:10",
            "Matthew 5:11-12",
        ),
        tags=("Beatitudes", "Gospel", "Discipleship", "Blessing", "Grace"),
    ),
    "armor_of_god": ReadingPlan(
        name="armor_of_god",
        title="The Whole Armor of God",
        description=(
            "Paul's exhortation in Ephesians 6 for believers to stand firm against spiritual darkness "
            "clothed in truth, righteousness, the gospel of peace, faith, salvation, and the Word."
        ),
        category="epistles",
        passages=(
            "Ephesians 6:10-11",
            "Ephesians 6:12",
            "Ephesians 6:13",
            "Ephesians 6:14",
            "Ephesians 6:15",
            "Ephesians 6:16",
            "Ephesians 6:17-18",
            "Ephesians 6:19-20",
        ),
        tags=("Spiritual Warfare", "Epistles", "Faith", "Word of God", "Perseverance"),
    ),
    "fruit_of_the_spirit": ReadingPlan(
        name="fruit_of_the_spirit",
        title="The Fruit of the Spirit",
        description=(
            "The supernatural character produced by the Holy Spirit in the redeemed: "
            "love, joy, peace, patience, kindness, goodness, faithfulness, gentleness, self-control."
        ),
        category="epistles",
        passages=(
            "Galatians 5:16",
            "Galatians 5:19-21",
            "Galatians 5:22-23",
            "Galatians 5:24",
            "Galatians 5:25-26",
        ),
        tags=("Holy Spirit", "Sanctification", "Fruit", "Christian Living"),
    ),
    "love_chapter": ReadingPlan(
        name="love_chapter",
        title="The Way of Agape Love (1 Corinthians 13)",
        description=(
            "Paul's poetic masterpiece articulating the supreme necessity, endurance, "
            "and eternal preeminence of divine love."
        ),
        category="epistles",
        passages=(
            "1 Corinthians 13:1-3",
            "1 Corinthians 13:4-5",
            "1 Corinthians 13:6-7",
            "1 Corinthians 13:8-10",
            "1 Corinthians 13:11-12",
            "1 Corinthians 13:13",
        ),
        tags=("Love", "Epistles", "Church", "Sanctification"),
    ),
    "great_commandments": ReadingPlan(
        name="great_commandments",
        title="The Shema and the Great Commandments",
        description=(
            "The heart of biblical ethics: the Shema of Deuteronomy, the covenant call "
            "to love God with all heart, soul, and mind, and loving neighbor as oneself."
        ),
        category="theology",
        passages=(
            "Deuteronomy 6:4-9",
            "Leviticus 19:18",
            "Micah 6:8",
            "Matthew 22:34-40",
            "John 13:34-35",
        ),
        tags=("Law", "Gospel", "Love", "Shema", "Commandments"),
    ),
    "divine_names": ReadingPlan(
        name="divine_names",
        title="Names and Attributes of the Living God",
        description=(
            "Divine self-revelations throughout scripture: Elohim, Yahweh, El Shaddai, "
            "the Great I AM, the Holy One of Israel, and the Alpha and Omega."
        ),
        category="theology",
        passages=(
            "Genesis 1:1",
            "Genesis 17:1",
            "Exodus 3:13-15",
            "Exodus 34:5-7",
            "Psalm 23:1",
            "Isaiah 6:1-3",
            "Isaiah 9:6",
            "John 8:58",
            "Revelation 1:8",
        ),
        tags=("Theology", "God", "Trinity", "Holiness", "Worship"),
    ),
}

# Ergonomic lookup aliases
PLAN_ALIASES: Dict[str, str] = {
    "ascent": "psalms_of_ascent",
    "psalms": "psalms_of_ascent",
    "pilgrim": "psalms_of_ascent",
    "sermon": "sermon_on_the_mount",
    "mount": "sermon_on_the_mount",
    "romans": "romans_road",
    "salvation": "romans_road",
    "prophecy": "messianic_prophecies",
    "prophecies": "messianic_prophecies",
    "messianic": "messianic_prophecies",
    "peace": "comfort_and_peace",
    "comfort": "comfort_and_peace",
    "solace": "comfort_and_peace",
    "covenant": "creation_and_covenant",
    "covenants": "creation_and_covenant",
    "creation": "creation_and_covenant",
    "beatitude": "beatitudes",
    "armor": "armor_of_god",
    "warfare": "armor_of_god",
    "fruit": "fruit_of_the_spirit",
    "spirit": "fruit_of_the_spirit",
    "love": "love_chapter",
    "agape": "love_chapter",
    "commandments": "great_commandments",
    "shema": "great_commandments",
    "names": "divine_names",
    "attributes": "divine_names",
}


def get_plan(name_or_alias: str) -> Optional[ReadingPlan]:
    """Resolve a reading plan by name or ergonomic alias.

    Args:
        name_or_alias: Identifier or alias string (e.g. 'psalms_of_ascent', 'sermon', 'romans').

    Returns:
        ReadingPlan instance or None if not recognized.
    """
    cleaned = str(name_or_alias).strip().lower().replace("-", "_").replace(" ", "_")
    resolved = PLAN_ALIASES.get(cleaned, cleaned)
    return STANDARD_PLANS.get(resolved)


def list_plans() -> List[ReadingPlan]:
    """Return all standard reading plans in canonical catalog order."""
    return list(STANDARD_PLANS.values())


def format_plans_table(styling: bool = True) -> str:
    """Format all reading plans as a human-readable ANSI terminal table.

    Args:
        styling: Whether to apply ANSI colors.

    Returns:
        Formatted multi-line string.
    """
    gold = "\033[38;2;212;175;55m" if styling else ""
    cyan = "\033[36m" if styling else ""
    gray = "\033[90m" if styling else ""
    reset = "\033[0m" if styling else ""
    bold = "\033[1m" if styling else ""

    lines: List[str] = [
        f"{bold}{gold}=== Curated Scripture Reading Plans & Collections ==={reset}",
        f"{gray}Use with './bible slide-batch --plan <name>' to generate TV screensaver albums.{reset}",
        "",
        f"{'Plan Name':<24} {'Category':<14} {'Passages':<10} {'Description'}",
        f"{'-'*24} {'-'*14} {'-'*10} {'-'*35}",
    ]

    for plan in list_plans():
        p_count = f"{plan.passage_count} verses" if plan.passage_count > 1 else "1 verse"
        desc = plan.description
        if len(desc) > 55:
            desc = desc[:52] + "..."
        lines.append(
            f"{cyan}{plan.name:<24}{reset} {plan.category:<14} {p_count:<10} {desc}"
        )

    lines.append("")
    lines.append(f"{gray}Total curated plans: {len(STANDARD_PLANS)}{reset}")
    return "\n".join(lines)
