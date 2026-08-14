from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import validate_prose_runtime as runtime


FIXTURES = ROOT / "fixtures"


def load_json(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ProseRuntimeTests(unittest.TestCase):
    def test_valid_fixture_passes(self):
        report = runtime.validate_bundle(
            handoff_path=FIXTURES / "valid_ta06_prose_handoff.json",
            reader_path=FIXTURES / "valid_prose_reader_contract.json",
            sidecar_path=FIXTURES / "valid_prose_audit_sidecar.json",
            article_path=FIXTURES / "20260815_demo-explainer.md",
        )
        self.assertEqual(report["status"], "pass", report["errors"])

    def test_permission_projection_is_fail_closed(self):
        handoff = load_json("valid_ta06_prose_handoff.json")
        handoff["permission"]["released_claim_ids"].remove("CLM002")
        errors = runtime.validate_handoff(handoff)
        self.assertTrue(any("released_claim_ids" in error for error in errors))

    def test_conditional_claim_requires_condition(self):
        handoff = load_json("valid_ta06_prose_handoff.json")
        handoff["claims"][1]["condition_if_any"] = ""
        errors = runtime.validate_handoff(handoff)
        self.assertTrue(any("condition_if_any" in error for error in errors))

    def test_reader_contract_must_bind_handoff_digest(self):
        handoff = load_json("valid_ta06_prose_handoff.json")
        reader = load_json("valid_prose_reader_contract.json")
        reader["handoff_digest"] = "0" * 64
        errors = runtime.validate_reader_contract(
            reader, handoff_digest=runtime.canonical_digest(handoff)
        )
        self.assertTrue(any("handoff_digest" in error for error in errors))

    def test_final_pass_rejected_when_hard_semantic_check_fails(self):
        handoff = load_json("valid_ta06_prose_handoff.json")
        reader = load_json("valid_prose_reader_contract.json")
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["semantic_guard"]["no_add"] = "fail"
        sidecar["final_gate"]["status"] = "pass"
        errors = runtime.validate_sidecar(
            sidecar,
            handoff_digest=runtime.canonical_digest(handoff),
            reader_digest=runtime.canonical_digest(reader),
            article_id=reader["article_id"],
        )
        self.assertTrue(any("final_gate.status must be fail" in error for error in errors))

    def test_reader_outcome_fail_blocks_release(self):
        handoff = load_json("valid_ta06_prose_handoff.json")
        reader = load_json("valid_prose_reader_contract.json")
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["reader_outcomes"]["understandable"]["status"] = "fail"
        sidecar["final_gate"]["status"] = "pass"
        errors = runtime.validate_sidecar(
            sidecar,
            handoff_digest=runtime.canonical_digest(handoff),
            reader_digest=runtime.canonical_digest(reader),
            article_id=reader["article_id"],
        )
        self.assertTrue(any("final_gate.status must be fail" in error for error in errors))

    def test_unverified_targeted_repair_blocks_release(self):
        handoff = load_json("valid_ta06_prose_handoff.json")
        reader = load_json("valid_prose_reader_contract.json")
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["targeted_repairs"] = [
            {
                "repair_id": "R1",
                "location": "## 內容，第 1 段",
                "status": "applied",
                "description": "補回時間範圍限定詞。",
            }
        ]
        sidecar["final_gate"]["status"] = "pass"
        errors = runtime.validate_sidecar(
            sidecar,
            handoff_digest=runtime.canonical_digest(handoff),
            reader_digest=runtime.canonical_digest(reader),
            article_id=reader["article_id"],
        )
        self.assertTrue(any("final_gate.status must be fail" in error for error in errors))

    def test_delivery_shell_errors_are_in_runtime_report(self):
        article = (FIXTURES / "20260815_demo-explainer.md").read_text(encoding="utf-8")
        article = article.replace("## 引用來源", "## Sources")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bad_article = tmp / "20260815_demo-explainer.md"
            bad_article.write_text(article, encoding="utf-8")
            report = runtime.validate_bundle(
                handoff_path=FIXTURES / "valid_ta06_prose_handoff.json",
                reader_path=FIXTURES / "valid_prose_reader_contract.json",
                sidecar_path=FIXTURES / "valid_prose_audit_sidecar.json",
                article_path=bad_article,
            )
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("article delivery" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
