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
                "samples": 3,
                "rules": 13,
                "stable_rules": 0,
                "voice_rules": 5,
                "batches": 3,
                "contamination_notes": 8,
                "strict_render_failures": 12,
                "semantic_failures": 1,
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

    def test_third_sample_preserves_model_and_source_discrepancies(self) -> None:
        sample = json.loads((ROOT / "data/samples/S003/sample.json").read_text(encoding="utf-8"))
        article = (ROOT / sample["article_path"]).read_text(encoding="utf-8")
        storyboard = json.loads((ROOT / sample["card_storyboard_path"]).read_text(encoding="utf-8"))
        self.assertIn("正文報告p=0.055,對應表格數值則為0.06", article)
        self.assertIn("流程圖(Fig. 2)標示高頻率組n=64", article)
        self.assertEqual(storyboard["canonical_queue"]["plan_id"], "TP_20260810_s44276_026_00246_6")
        self.assertEqual(storyboard["summary"]["semantic_failures"], 1)
        c03 = next(card for card in storyboard["cards"] if card["card_id"] == "C03")
        self.assertEqual(c03["semantic_audit"], "fail")
        self.assertIn("6", " ".join(c03["strict_render_audit"]["violations"]))

    def test_domain_and_denominator_rules_remain_hypotheses(self) -> None:
        rules = {rule["rule_id"]: rule for rule in json.loads((ROOT / "data/rules/rules.json").read_text(encoding="utf-8"))["rules"]}
        self.assertEqual(rules["R012"]["status"], "hypothesis")
        self.assertEqual(rules["R013"]["status"], "hypothesis")

    def test_method_and_voice_layers_are_recorded_separately(self) -> None:
        registry = json.loads((ROOT / "data/registry.json").read_text(encoding="utf-8"))
        batches = json.loads((ROOT / "data/batch_results.json").read_text(encoding="utf-8"))
        voice_rules = json.loads((ROOT / "data/voice/voice_rules.json").read_text(encoding="utf-8"))["rules"]
        self.assertEqual(registry["batch_ids"], ["B001", "B002", "B003"])
        self.assertEqual(registry["voice_rule_ids"], ["V001", "V002", "V003", "V004", "V005"])
        self.assertEqual([batch["sample_id"] for batch in batches["batches"]], ["S001", "S002", "S003"])
        self.assertTrue(all(rule["status"] == "hypothesis" for rule in voice_rules))
        self.assertNotIn("V001", registry["rule_ids"])

    def test_no_rule_is_prematurely_stable(self) -> None:
        rules = json.loads((ROOT / "data/rules/rules.json").read_text(encoding="utf-8"))["rules"]
        self.assertTrue(rules)
        self.assertFalse(any(rule["status"] == "stable" for rule in rules))


if __name__ == "__main__":
    unittest.main()
