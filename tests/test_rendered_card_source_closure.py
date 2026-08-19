import copy
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"validate_rendered_card_source_closure.py"
SPEC=importlib.util.spec_from_file_location("validate_rendered_card_source_closure",SCRIPT)
MODULE=importlib.util.module_from_spec(SPEC); assert SPEC.loader is not None; SPEC.loader.exec_module(MODULE)

class RenderedCardSourceClosureTests(unittest.TestCase):
    def base(self):
        return {"method_revision":MODULE.METHOD,"card_audits":[{
            "card_id":"C05",
            "blind_readback":{"content_node_inventory":[{"observed_node_id":"N1","text":"可複製性：個案難以在他處獨立重現。","material":True}]},
            "source_surface_reconciliation":{
                "content_node_checks":[{"observed_node_id":"N1","node_type":"explanatory_microcopy","queue_authorization_status":"not_authorized","primary_source_support_status":"supported","source_locators":["Roesler 2025: case-report limitations"],"disposition":"SOURCE_SUPPORTED_EXPLANATORY_EXPANSION","materiality":"material","finding_id":None,"semantic_novelty":"explanatory_decomposition","introduces_new_substantive_claim":False,"changes_scope":False,"changes_evidence_role":False,"changes_topology":False}],
                "expected_content_checks":[],"expected_role_checks":[],"evidence_role_checks":[],
                "source_surface_completion":{"all_observed_material_nodes_dispositioned":True,"all_expected_semantic_roles_checked":True,"all_evidence_role_markers_checked":True,"topic_plausibility_shortcut_not_used":True,"visible_text_whitelist_shortcut_not_used":True}},
            "axes":{"SOURCE_SURFACE":"pass"},"verdict":"PASS"}]}
    def test_source_supported_explanatory_microcopy_may_pass(self): self.assertEqual(MODULE.validate_bundle(self.base()),[])
    def test_visible_text_absence_alone_cannot_force_fail(self): self.assertEqual(MODULE.validate_bundle(self.base()),[])
    def test_plausible_unsourced_category_still_fails(self):
        b=self.base(); c=b["card_audits"][0]; c["blind_readback"]["content_node_inventory"][0].update(text="懷孕與產後脈絡")
        x=c["source_surface_reconciliation"]["content_node_checks"][0]; x.update(node_type="category",primary_source_support_status="not_supported",source_locators=[],disposition="UNAUTHORIZED_AND_UNSUPPORTED",finding_id="F1")
        c["axes"]["SOURCE_SURFACE"]="fail"; c["verdict"]="FAIL_RENDER"
        self.assertEqual(MODULE.validate_bundle(b),[])
    def test_specific_category_cannot_masquerade_as_explanatory_expansion(self):
        b=self.base(); x=b["card_audits"][0]["source_surface_reconciliation"]["content_node_checks"][0]; x["node_type"]="category"
        self.assertTrue(any("not safely bounded" in e for e in MODULE.validate_bundle(b)))
    def test_c06_duplicate_text_in_wrong_semantic_roles_fails(self):
        b=self.base(); c=b["card_audits"][0]; c["source_surface_reconciliation"]["expected_role_checks"]=[{"role_id":"inner-autonomous","status":"represented","finding_id":None},{"role_id":"relationship-change","status":"duplicated_wrong_role","finding_id":"F-C06-DUP"}]; c["axes"]["SOURCE_SURFACE"]="fail"; c["verdict"]="FAIL_RENDER"
        self.assertEqual(MODULE.validate_bundle(b),[])
    def test_c10_evidence_role_drift_fails(self):
        b=self.base(); c=b["card_audits"][0]; c["source_surface_reconciliation"]["evidence_role_checks"]=[{"marker_id":"M1","status":"drifted_role","finding_id":"F-C10-ROLE"}]; c["axes"]["SOURCE_SURFACE"]="fail"; c["verdict"]="FAIL_RENDER"
        self.assertEqual(MODULE.validate_bundle(b),[])
    def test_role_failure_cannot_be_marked_pass(self):
        b=self.base(); c=b["card_audits"][0]; c["source_surface_reconciliation"]["expected_role_checks"]=[{"role_id":"relationship-change","status":"duplicated_wrong_role","finding_id":"F1"}]
        self.assertTrue(any("SOURCE_SURFACE must be fail" in e or "PASS illegal" in e for e in MODULE.validate_bundle(b)))
    def test_missing_material_node_disposition_is_rejected(self):
        b=self.base(); b["card_audits"][0]["source_surface_reconciliation"]["content_node_checks"]=[]
        self.assertTrue(any("every observed material content node" in e for e in MODULE.validate_bundle(b)))
    def test_supported_node_requires_locator(self):
        b=self.base(); b["card_audits"][0]["source_surface_reconciliation"]["content_node_checks"][0]["source_locators"]=[]
        self.assertTrue(any("supported node requires source locator" in e for e in MODULE.validate_bundle(b)))
    def test_visible_text_whitelist_shortcut_is_forbidden(self):
        b=self.base(); b["card_audits"][0]["source_surface_reconciliation"]["source_surface_completion"]["visible_text_whitelist_shortcut_not_used"]=False
        self.assertTrue(any("visible_text whitelist shortcut" in e for e in MODULE.validate_bundle(b)))

if __name__=="__main__": unittest.main()
