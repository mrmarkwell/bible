"""Hermetic unit tests for curated reading plans and scripture collections."""

from __future__ import annotations

import unittest

from core.plans import (
    STANDARD_PLANS,
    ReadingPlan,
    format_plans_table,
    get_plan,
    list_plans,
)
from core.reference import parse_reference


class TestReadingPlans(unittest.TestCase):
    """Test suite for ReadingPlan catalog and resolution."""

    def test_catalog_integrity(self) -> None:
        """Verify all standard plans are well-formed and non-empty."""
        self.assertGreaterEqual(len(STANDARD_PLANS), 10)
        plans = list_plans()
        self.assertEqual(len(plans), len(STANDARD_PLANS))

        for plan in plans:
            self.assertIsInstance(plan, ReadingPlan)
            self.assertTrue(plan.name)
            self.assertTrue(plan.title)
            self.assertTrue(plan.description)
            self.assertTrue(plan.category)
            self.assertGreaterEqual(plan.passage_count, 1)
            self.assertEqual(len(plan.passages), plan.passage_count)

    def test_all_passage_citations_parseable(self) -> None:
        """Verify all passage citations in all plans parse into valid References."""
        for plan in list_plans():
            for cit in plan.passages:
                ref = parse_reference(cit)
                self.assertIsNotNone(
                    ref,
                    f"Citation '{cit}' in plan '{plan.name}' failed to parse as a canonical reference",
                )
                self.assertTrue(
                    ref.is_valid,
                    f"Reference '{ref}' in plan '{plan.name}' is invalid",
                )

    def test_get_plan_exact_names(self) -> None:
        """Verify get_plan resolves exact plan names."""
        for name, expected in STANDARD_PLANS.items():
            resolved = get_plan(name)
            self.assertIsNotNone(resolved)
            self.assertEqual(resolved.name, expected.name)

    def test_get_plan_aliases(self) -> None:
        """Verify get_plan resolves common ergonomic aliases."""
        test_cases = [
            ("ascent", "psalms_of_ascent"),
            ("psalms", "psalms_of_ascent"),
            ("pilgrim", "psalms_of_ascent"),
            ("sermon", "sermon_on_the_mount"),
            ("mount", "sermon_on_the_mount"),
            ("romans", "romans_road"),
            ("salvation", "romans_road"),
            ("prophecy", "messianic_prophecies"),
            ("messianic", "messianic_prophecies"),
            ("peace", "comfort_and_peace"),
            ("comfort", "comfort_and_peace"),
            ("covenant", "creation_and_covenant"),
            ("beatitude", "beatitudes"),
            ("armor", "armor_of_god"),
            ("fruit", "fruit_of_the_spirit"),
            ("love", "love_chapter"),
            ("names", "divine_names"),
        ]
        for alias, expected_name in test_cases:
            resolved = get_plan(alias)
            self.assertIsNotNone(resolved, f"Alias '{alias}' did not resolve")
            self.assertEqual(resolved.name, expected_name)

    def test_get_plan_case_and_punctuation_insensitive(self) -> None:
        """Verify get_plan handles uppercase, dashes, and whitespace."""
        self.assertEqual(get_plan("PSALMS-OF-ASCENT").name, "psalms_of_ascent")
        self.assertEqual(get_plan("Sermon on the Mount").name, "sermon_on_the_mount")
        self.assertEqual(get_plan("  romans-road  ").name, "romans_road")

    def test_get_plan_unknown_returns_none(self) -> None:
        """Verify non-existent plan names return None."""
        self.assertIsNone(get_plan("non_existent_plan_xyz"))
        self.assertIsNone(get_plan(""))

    def test_plan_to_dict(self) -> None:
        """Verify ReadingPlan serialization."""
        plan = get_plan("romans_road")
        self.assertIsNotNone(plan)
        d = plan.to_dict()
        self.assertEqual(d["name"], "romans_road")
        self.assertEqual(d["passage_count"], plan.passage_count)
        self.assertIn("Romans 3:23", d["passages"])
        self.assertIn("Gospel", d["tags"])

    def test_format_plans_table(self) -> None:
        """Verify terminal table generation with and without ANSI styling."""
        styled = format_plans_table(styling=True)
        self.assertIn("Curated Scripture Reading Plans", styled)
        self.assertIn("psalms_of_ascent", styled)
        self.assertIn("\033[", styled)

        plain = format_plans_table(styling=False)
        self.assertIn("Curated Scripture Reading Plans", plain)
        self.assertIn("sermon_on_the_mount", plain)
        self.assertNotIn("\033[", plain)


if __name__ == "__main__":
    unittest.main()
