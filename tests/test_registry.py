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
            {"samples": 1, "rules": 10, "stable_rules": 0, "contamination_notes": 3},
        )

    def test_sample_article_is_preserved(self) -> None:
        sample = json.loads((ROOT / "data/samples/S001/sample.json").read_text(encoding="utf-8"))
        article = (ROOT / sample["article_path"]).read_text(encoding="utf-8")
        self.assertIn("一年後約三分之二恢復正常", article)
        self.assertIn("OR 1.054", article)
        self.assertIn("最後更新：20260810", article)

    def test_no_rule_is_prematurely_stable(self) -> None:
        rules = json.loads((ROOT / "data/rules/rules.json").read_text(encoding="utf-8"))["rules"]
        self.assertTrue(rules)
        self.assertFalse(any(rule["status"] == "stable" for rule in rules))


if __name__ == "__main__":
    unittest.main()

