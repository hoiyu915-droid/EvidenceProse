import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_probe_post_audit.py"
SPEC = importlib.util.spec_from_file_location("validate_probe_post_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ProbePostAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(
            (ROOT / "fixtures" / "valid_probe_post_audit_bundle.json").read_text(encoding="utf-8")
        )

    def test_valid_fixture_passes(self):
        self.assertEqual(MODULE.validate_bundle(copy.deepcopy(self.fixture)), [])

    def test_hard_finding_cannot_be_accepted_warning(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["audit_findings"][0]["status"] = "accepted_warning"
        errors = MODULE.validate_bundle(bundle)
        self.assertTrue(any("hard finding A017 must be resolved" in e for e in errors))

    def test_unexpected_edit_scope_fails(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["operations"][0]["actual_changed_element_ids"].append("C99.decorative_chart")
        errors = MODULE.validate_bundle(bundle)
        self.assertTrue(any("outside declared scope" in e for e in errors))

    def test_required_claim_cannot_disappear(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["coverage"]["represented_claim_ids"].remove("LIM_03")
        errors = MODULE.validate_bundle(bundle)
        self.assertTrue(any("required claims lack representation or disposition" in e for e in errors))

    def test_article_rewrite_cannot_add_claim(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["article_rewrite"]["new_claim_ids"] = ["CLM_NEW"]
        errors = MODULE.validate_bundle(bundle)
        self.assertTrue(any("new_claim_ids must be empty" in e for e in errors))

    def test_pass_gate_must_match_failed_guard(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["semantic_guard"]["numeric_fidelity"] = "fail"
        errors = MODULE.validate_bundle(bundle)
        self.assertTrue(any("final_gate.status must be fail" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
