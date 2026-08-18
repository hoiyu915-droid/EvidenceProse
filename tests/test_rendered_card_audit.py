import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_rendered_card_audit.py"
SPEC = importlib.util.spec_from_file_location("validate_rendered_card_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RenderedCardAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(
            (ROOT / "fixtures" / "valid_rendered_card_audit.json").read_text(encoding="utf-8")
        )

    def validate(self, bundle):
        return MODULE.validate_bundle(copy.deepcopy(bundle), base_dir=ROOT / "fixtures")

    def test_valid_fixture_passes(self):
        self.assertEqual(self.validate(self.fixture), [])

    def test_wording_divergence_does_not_fail(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["card_audits"][0]["historical_text_comparison"] = "wording_divergence"
        self.assertEqual(self.validate(bundle), [])

    def test_image_hash_must_match(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["card_audits"][0]["image_sha256"] = "0" * 64
        errors = self.validate(bundle)
        self.assertTrue(any("image hash mismatch" in error for error in errors))

    def test_fail_render_requires_repair_ticket(self):
        bundle = copy.deepcopy(self.fixture)
        card = bundle["card_audits"][0]
        card["axes"]["VISUAL_SEMANTICS"] = "fail"
        card["findings"] = [{
            "finding_id":"F01","axis":"VISUAL_SEMANTICS","finding_type":"CAUSAL_ARROW_UPGRADE",
            "materiality":"material","observed":"solid arrow","expected":"association",
            "reader_risk":"causal overread","source_support":["SRC001:p1"],
            "repair_prescription":{"action":"REWIRE","instruction":"Replace the solid arrow with an association relation."}
        }]
        card["verdict"] = "FAIL_RENDER"
        card["release_blocking"] = True
        bundle["release_gate"]["status"] = "FAIL"
        bundle["release_gate"]["counts"]["PASS"] = 0
        bundle["release_gate"]["counts"]["FAIL_RENDER"] = 1
        bundle["release_gate"]["blocking_card_ids"] = ["C01"]
        bundle["release_gate"]["release_allowed"] = False
        errors = self.validate(bundle)
        self.assertTrue(any("fail requires repair ticket" in error for error in errors))

    def test_fail_spec_requires_origin(self):
        bundle = copy.deepcopy(self.fixture)
        card = bundle["card_audits"][0]
        card["axes"]["CONTENT_MEANING"] = "fail"
        card["findings"] = [{
            "finding_id":"F01","axis":"CONTENT_MEANING","finding_type":"MEANING_DISTORTION",
            "materiality":"material","observed":"wrong claim","expected":"source claim",
            "reader_risk":"wrong evidence model","source_support":["SRC001:p1"],
            "repair_prescription":{"action":"REPLACE","instruction":"Return upstream and replace the unsupported claim."}
        }]
        card["verdict"] = "FAIL_SPEC"
        card["release_blocking"] = True
        card["repair_ticket_id"] = "RT01"
        bundle["repair_tickets"] = [self._small_ticket("RT01", "FAIL_SPEC")]
        bundle["release_gate"]["status"] = "FAIL"
        bundle["release_gate"]["counts"]["PASS"] = 0
        bundle["release_gate"]["counts"]["FAIL_SPEC"] = 1
        bundle["release_gate"]["blocking_card_ids"] = ["C01"]
        bundle["release_gate"]["release_allowed"] = False
        errors = self.validate(bundle)
        self.assertTrue(any("FAIL_SPEC requires failure_origin" in error for error in errors))

    def test_same_family_high_stakes_blocks_pending_secondary_review(self):
        bundle = copy.deepcopy(self.fixture)
        risk = bundle["methodological_risk"]
        risk.update({
            "auditor_model_family":"family-a",
            "relationship":"same_family",
            "correlated_error_risk":"present",
            "material_to_run":True,
            "secondary_review_required":True,
            "secondary_review_status":"pending",
            "secondary_review_outcome":"not_applicable",
            "release_effect":"blocked_pending_secondary_review"
        })
        bundle["provenance"]["methodological_limitations"][0].update({
            "status":"present","material_to_run":True
        })
        bundle["release_gate"]["status"] = "BLOCKED"
        bundle["release_gate"]["release_allowed"] = False
        self.assertEqual(self.validate(bundle), [])

    def test_same_family_non_high_stakes_is_warning_ceiling(self):
        bundle = copy.deepcopy(self.fixture)
        risk = bundle["methodological_risk"]
        risk.update({
            "high_stakes_cardset":False,
            "high_stakes_reasons":[],
            "auditor_model_family":"family-a",
            "relationship":"same_family",
            "correlated_error_risk":"present",
            "material_to_run":True,
            "secondary_review_required":False,
            "secondary_review_status":"not_required",
            "secondary_review_outcome":"not_applicable",
            "release_effect":"warning_ceiling"
        })
        bundle["provenance"]["methodological_limitations"][0].update({
            "status":"present","material_to_run":True
        })
        bundle["release_gate"]["status"] = "PASS_WITH_WARNINGS"
        self.assertEqual(self.validate(bundle), [])

    def test_single_card_failure_does_not_force_cardset_fail(self):
        bundle = copy.deepcopy(self.fixture)
        card = bundle["card_audits"][0]
        card["axes"]["VISUAL_SEMANTICS"] = "fail"
        card["findings"] = [{
            "finding_id":"F01","axis":"VISUAL_SEMANTICS","finding_type":"RELATION_TYPE_DISTORTION",
            "materiality":"material","observed":"causal","expected":"association",
            "reader_risk":"overclaim","source_support":["SRC001:p1"],
            "repair_prescription":{"action":"REWIRE","instruction":"Use an association relation."}
        }]
        card["verdict"] = "FAIL_RENDER"
        card["release_blocking"] = True
        card["repair_ticket_id"] = "RT01"
        bundle["repair_tickets"] = [self._small_ticket("RT01", "FAIL_RENDER")]
        bundle["release_gate"].update({
            "status":"FAIL","release_allowed":False,"blocking_card_ids":["C01"]
        })
        bundle["release_gate"]["counts"].update({"PASS":0,"FAIL_RENDER":1})
        self.assertEqual(bundle["cardset_audit"]["status"], "NOT_APPLICABLE")
        self.assertEqual(self.validate(bundle), [])

    def test_substantial_repair_requires_replacement_material(self):
        bundle = copy.deepcopy(self.fixture)
        card = bundle["card_audits"][0]
        card["axes"]["CONTENT_MEANING"] = "fail"
        card["findings"] = [{
            "finding_id":"F01","axis":"CONTENT_MEANING","finding_type":"MEANING_DISTORTION",
            "materiality":"material","observed":"bad module","expected":"supported module",
            "reader_risk":"wrong claim","source_support":["SRC001:p1"],
            "repair_prescription":{"action":"RECOMPOSE","instruction":"Recompose the module."}
        }]
        card["verdict"] = "FAIL_RENDER"
        card["release_blocking"] = True
        card["repair_ticket_id"] = "RT01"
        ticket = self._small_ticket("RT01", "FAIL_RENDER")
        ticket["substantial_change"].update({
            "total_semantic_weight":20,
            "changed_semantic_weight":4,
            "estimated_weighted_semantic_fraction":0.2,
            "triggered":True,
            "replacement_required":True,
            "replacement_status":"SUPPORTED",
            "replacement_material":None
        })
        bundle["repair_tickets"] = [ticket]
        bundle["release_gate"].update({"status":"FAIL","release_allowed":False,"blocking_card_ids":["C01"]})
        bundle["release_gate"]["counts"].update({"PASS":0,"FAIL_RENDER":1})
        errors = self.validate(bundle)
        self.assertTrue(any("SUPPORTED replacement requires writing_block text" in error for error in errors))

    @staticmethod
    def _small_ticket(ticket_id, verdict):
        return {
            "ticket_id":ticket_id,"card_id":"C01","verdict":verdict,
            "problem_summary":"Repair one material relation.",
            "action_plan":[{
                "action":"REWIRE","target":"central relation",
                "instruction":"Change only the failed relation.",
                "expected_reader_effect":"Restore the audited evidence boundary."
            }],
            "keep":["title","citation"],"remove":[],"add_or_replace":[],"rewire":["central relation"],
            "do_not_touch":["unrelated modules"],"acceptance_test":["No causal upgrade remains."],
            "recheck_axes":["VISUAL_SEMANTICS"],
            "substantial_change":{
                "triggered":False,
                "total_semantic_weight":20,
                "changed_semantic_weight":1,
                "structural_triggers":[],
                "estimated_weighted_semantic_fraction":0.05,
                "replacement_required":False,
                "replacement_status":"NOT_REQUIRED",
                "replacement_material":None
            }
        }


if __name__ == "__main__":
    unittest.main()
