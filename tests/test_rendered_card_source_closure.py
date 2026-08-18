import copy
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"validate_rendered_card_source_closure.py"
SPEC=importlib.util.spec_from_file_location("validate_rendered_card_source_closure",SCRIPT)
MODULE=importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

class RenderedCardSourceClosureTests(unittest.TestCase):
    def base(self):
        return {
            "method_revision":"1.2-topology-and-source-closure",
            "card_audits":[{
                "card_id":"C02",
                "blind_readback":{"content_node_inventory":[
                    {"observed_node_id":"N1","text":"性少數群體","material":True},
                    {"observed_node_id":"N2","text":"懷孕與產後脈絡","material":True}
                ]},
                "source_surface_reconciliation":{
                    "content_node_checks":[
                        {"observed_node_id":"N1","queue_authorization_status":"authorized","primary_source_support_status":"supported","source_locators":["Dewitte 2020: diversity section"],"disposition":"AUTHORIZED_AND_SUPPORTED","materiality":"material","finding_id":None},
                        {"observed_node_id":"N2","queue_authorization_status":"not_authorized","primary_source_support_status":"not_supported","source_locators":[],"disposition":"UNAUTHORIZED_AND_UNSUPPORTED","materiality":"material","finding_id":"F-C02-PREG"}
                    ],
                    "expected_content_checks":[],
                    "source_surface_completion":{"all_observed_material_nodes_dispositioned":True,"topic_plausibility_shortcut_not_used":True}
                },
                "axes":{"SOURCE_SURFACE":"fail"},
                "verdict":"FAIL_RENDER"
            }]
        }
    def test_plausible_unsourced_category_is_valid_fail_record(self):
        self.assertEqual(MODULE.validate_bundle(self.base()),[])
    def test_plausible_unsourced_category_cannot_pass(self):
        b=self.base(); b["card_audits"][0]["axes"]["SOURCE_SURFACE"]="pass"; b["card_audits"][0]["verdict"]="PASS"
        errors=MODULE.validate_bundle(copy.deepcopy(b))
        self.assertTrue(any("SOURCE_SURFACE must be fail" in e or "PASS illegal" in e for e in errors))
    def test_missing_material_node_disposition_is_rejected(self):
        b=self.base(); b["card_audits"][0]["source_surface_reconciliation"]["content_node_checks"]=b["card_audits"][0]["source_surface_reconciliation"]["content_node_checks"][:1]
        errors=MODULE.validate_bundle(copy.deepcopy(b))
        self.assertTrue(any("every observed material content node" in e for e in errors))
    def test_supported_node_requires_locator(self):
        b=self.base(); b["card_audits"][0]["source_surface_reconciliation"]["content_node_checks"][0]["source_locators"]=[]
        self.assertTrue(any("supported node requires source locator" in e for e in MODULE.validate_bundle(copy.deepcopy(b))))
    def test_topic_plausibility_shortcut_is_forbidden(self):
        b=self.base(); b["card_audits"][0]["source_surface_reconciliation"]["source_surface_completion"]["topic_plausibility_shortcut_not_used"]=False
        self.assertTrue(any("topic-plausibility shortcut is forbidden" in e for e in MODULE.validate_bundle(copy.deepcopy(b))))

if __name__=="__main__": unittest.main()
