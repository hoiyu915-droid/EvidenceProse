from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_registry import validate  # noqa: E402


class RegistryTests(unittest.TestCase):
    def test_registry_is_internally_consistent(self) -> None:
        self.assertEqual(
            validate(),
            {
                "samples": 2,
                "rules": 11,
                "stable_rules": 0,
                "contamination_notes": 6,
                "strict_render_failures": 6,
            },
        )

    def test_sample_article_is_preserved(self) -> None:
        sample = json.loads((ROOT / "data/samples/S001/sample.json").read_text(encoding="utf-8"))
        article = (ROOT / sample["article_path"]).read_text(encoding="utf-8")
        self.assertIn("一年後約三分之二恢復正常", article)
        self.assertIn("OR 1.054", article)
        self.assertIn("最後更新：20260810", article)

    def test_second_sample_and_card_binding_are_preserved(self) -> None:
        sample = json.loads((ROOT / "data/samples/S002/sample.json").read_text(encoding="utf-8"))
        article = (ROOT / sample["article_path"]).read_text(encoding="utf-8")
        storyboard = json.loads((ROOT / sample["card_storyboard_path"]).read_text(encoding="utf-8"))
        self.assertIn("56項研究看斷貨", article)
        self.assertEqual(storyboard["canonical_queue"]["plan_id"], "TA07-20260810-010543-18237b69")
        self.assertEqual(storyboard["summary"]["strict_render_failures"], 6)
        self.assertTrue(all(card["semantic_audit"] == "pass" for card in storyboard["cards"]))

    def test_narrative_review_does_not_invent_not_applicable_denominators(self) -> None:
        sample = json.loads((ROOT / "data/samples/S002/sample.json").read_text(encoding="utf-8"))
        profile = sample["study_profile"]
        self.assertIsNone(profile["total_participants"])
        self.assertIn("total_participants", profile["not_applicable_reasons"])

    def test_no_rule_is_prematurely_stable(self) -> None:
        rules = json.loads((ROOT / "data/rules/rules.json").read_text(encoding="utf-8"))["rules"]
        self.assertTrue(rules)
        self.assertFalse(any(rule["status"] == "stable" for rule in rules))


if __name__ == "__main__":
    unittest.main()
