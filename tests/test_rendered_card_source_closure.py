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

METHOD=MODULE.METHOD

class RenderedCardSourceClosureTests(unittest.TestCase):
    def base(self):
        return {
            "contract_version":MODULE.RESULT_CONTRACT_VERSION,
            "result_schema_version":MODULE.RESULT_SCHEMA_VERSION,
            "policy_id":MODULE.POLICY_ID,
            "policy_version":MODULE.POLICY_VERSION,
            "method_revision":METHOD,
            "policy_digest":MODULE.POLICY_DIGEST,
            "card_audits":[{
                "card_id":"C02",
                "blind_readback":{"content_node_inventory":[
                    {"observed_node_id":"N1","text":"性少數群體","material":True},
                    {"observed_node_id":"N2","text":"懷孕與產後脈絡","material":True}
                ],"evidence_annotation_inventory":[]},
                "expected_semantic_packet":{"expected_content_inventory":[],"expected_evidence_annotation_inventory":[]},
                "source_surface_reconciliation":{
                    "content_node_checks":[
                        {"observed_node_id":"N1","queue_authorization_status":"authorized","primary_source_support_status":"supported","source_locators":["SRC001:Dewitte 2020: diversity section"],"disposition":"AUTHORIZED_AND_SUPPORTED","materiality":"material","finding_id":None},
                        {"observed_node_id":"N2","queue_authorization_status":"not_authorized","primary_source_support_status":"not_supported","source_locators":[],"disposition":"UNAUTHORIZED_AND_UNSUPPORTED","materiality":"material","finding_id":"F-C02-PREG"}
                    ],
                    "expected_content_checks":[],
                    "evidence_annotation_checks":[],
                    "source_surface_completion":{
                        "all_observed_material_nodes_dispositioned":True,
                        "all_material_evidence_annotations_checked":True,
                        "topic_plausibility_shortcut_not_used":True,
                        "literal_queue_whitelist_shortcut_not_used":True,
                        "mixed_support_nodes_split_when_materially_different":True
                    }
                },
                "axes":{"SOURCE_SURFACE":"fail"},
                "verdict":"FAIL_RENDER"
            }]
        }

    def one_node(self, *, text, check, axis="pass", verdict="PASS", annotations=None):
        annotation_checks=annotations or []
        return {
            "contract_version":MODULE.RESULT_CONTRACT_VERSION,
            "result_schema_version":MODULE.RESULT_SCHEMA_VERSION,
            "policy_id":MODULE.POLICY_ID,
            "policy_version":MODULE.POLICY_VERSION,
            "method_revision":METHOD,
            "policy_digest":MODULE.POLICY_DIGEST,
            "card_audits":[{
                "card_id":"CXX",
                "blind_readback":{"content_node_inventory":[{"observed_node_id":"N1","text":text,"material":True}],"evidence_annotation_inventory":[{"annotation_id":x["annotation_id"]} for x in annotation_checks]},
                "expected_semantic_packet":{"expected_content_inventory":[],"expected_evidence_annotation_inventory":[]},
                "source_surface_reconciliation":{
                    "content_node_checks":[check],
                    "expected_content_checks":[],
                    "evidence_annotation_checks":annotation_checks,
                    "source_surface_completion":{
                        "all_observed_material_nodes_dispositioned":True,
                        "all_material_evidence_annotations_checked":True,
                        "topic_plausibility_shortcut_not_used":True,
                        "literal_queue_whitelist_shortcut_not_used":True,
                        "mixed_support_nodes_split_when_materially_different":True
                    }
                },
                "axes":{"SOURCE_SURFACE":axis},
                "verdict":verdict
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

    def test_literal_queue_whitelist_cannot_auto_fail_supported_nonexpansive_elaboration(self):
        # Roesler C04/C05 lesson: a source-supported explanatory gloss that stays
        # inside the same authorized semantic node is not a scientific failure
        # merely because it is not verbatim visible_text.
        check={
            "observed_node_id":"N1",
            "queue_authorization_status":"not_authorized",
            "primary_source_support_status":"supported",
            "source_locators":["SRC001:Roesler 2025: transformation-process models"],
            "disposition":"SOURCE_SUPPORTED_NONEXPANSIVE_ELABORATION",
            "materiality":"material",
            "finding_id":None,
            "semantic_parent_node_id":"Q-MODEL-CENTERING",
            "queue_protective_lock_material":False,
            "expansion_test":{k:False for k in MODULE.EXPANSION_KEYS},
        }
        b=self.one_node(text="以中心化為核心，回到內在平衡與整合。",check=check)
        self.assertEqual(MODULE.validate_bundle(b),[])

    def test_nonexpansive_elaboration_cannot_hide_new_mechanism(self):
        check={
            "observed_node_id":"N1","queue_authorization_status":"not_authorized","primary_source_support_status":"supported",
            "source_locators":["SRC001:Roesler 2025"],"disposition":"SOURCE_SUPPORTED_NONEXPANSIVE_ELABORATION","materiality":"material","finding_id":None,
            "semantic_parent_node_id":"Q1","queue_protective_lock_material":False,
            "expansion_test":{k:False for k in MODULE.EXPANSION_KEYS},
        }
        check["expansion_test"]["adds_new_mechanism"]=True
        errors=MODULE.validate_bundle(self.one_node(text="extra mechanism",check=check))
        self.assertTrue(any("adds_new_mechanism must be false" in e for e in errors))

    def test_source_supported_sibling_semantic_bleed_still_fails(self):
        # Roesler C09 lesson: support somewhere in the paper is not enough when a
        # renderer imports a sibling-card-specific mechanism into this card.
        check={
            "observed_node_id":"N1","queue_authorization_status":"not_authorized","primary_source_support_status":"supported",
            "source_locators":["SRC001:Roesler 2025: therapeutic relationship discussion"],
            "disposition":"SOURCE_SUPPORTED_BUT_OUT_OF_CARD_SCOPE","materiality":"material","finding_id":"F-C09-BLEED",
            "card_scope_status":"sibling_specific"
        }
        b=self.one_node(text="治療關係與其他因素可能共同影響變化。",check=check,axis="fail",verdict="FAIL_RENDER")
        self.assertEqual(MODULE.validate_bundle(b),[])

    def test_mixed_support_clause_must_be_split_before_disposition(self):
        b=self.base(); b["card_audits"][0]["source_surface_reconciliation"]["source_surface_completion"]["mixed_support_nodes_split_when_materially_different"]=False
        self.assertTrue(any("mixed-support clauses" in e for e in MODULE.validate_bundle(b)))

    def test_closed_set_inventory_requires_corresponding_expected_check(self):
        b=self.base()
        b["card_audits"][0]["blind_readback"]["content_node_inventory"][0]["closed_set_member"]=True
        b["card_audits"][0]["expected_semantic_packet"]["expected_content_inventory"]=[{
            "expected_node_id":"EXPECTED-CLOSED-1","material":True,"closed_set_member":True
        }]
        errors=MODULE.validate_bundle(copy.deepcopy(b))
        self.assertTrue(any("expected_content_checks must cover all expected closed-set members" in e for e in errors))
        b["card_audits"][0]["source_surface_reconciliation"]["expected_content_checks"]=[{
            "closed_set_member":True,
            "status":"represented",
            "expected_node_id":"EXPECTED-CLOSED-1",
            "observed_node_id":"N1",
        }]
        self.assertEqual(MODULE.validate_bundle(b),[])

    def test_wrong_evidence_role_marker_is_material_failure(self):
        # Roesler C10 lesson: a blue CONFLICT marker cannot be attached to a GAP-only card.
        check={
            "observed_node_id":"N1","queue_authorization_status":"authorized","primary_source_support_status":"supported",
            "source_locators":["SRC001:Roesler 2025: child motif forthcoming"],"disposition":"AUTHORIZED_AND_SUPPORTED","materiality":"material","finding_id":None
        }
        annotations=[{
            "annotation_id":"A1","expected_annotation_id":"EA1","observed_role":"CONFLICT","expected_role":"GAP","bound_observed_node_ids":["N1"],
            "status":"wrong_role","finding_id":"F-C10-ROLE"
        }]
        b=self.one_node(text="publication forthcoming",check=check,axis="fail",verdict="FAIL_RENDER",annotations=annotations)
        b["card_audits"][0]["expected_semantic_packet"]["expected_evidence_annotation_inventory"]=[{"expected_annotation_id":"EA1","expected_role":"GAP"}]
        self.assertEqual(MODULE.validate_bundle(b),[])

    def test_wrong_evidence_binding_is_material_failure(self):
        # Roesler C01 lesson: a valid CORE colour is still wrong if it is attached
        # to four theory branches as if each branch itself had CORE evidence status.
        check={
            "observed_node_id":"N1","queue_authorization_status":"authorized","primary_source_support_status":"supported",
            "source_locators":["SRC001:Roesler 2025: four-theory analytical split"],"disposition":"AUTHORIZED_AND_SUPPORTED","materiality":"material","finding_id":None
        }
        annotations=[{
            "annotation_id":"A1","expected_annotation_id":"EA1","observed_role":"CORE","expected_role":"CORE","bound_observed_node_ids":["N1"],
            "status":"wrong_binding","finding_id":"F-C01-BIND"
        }]
        b=self.one_node(text="生物預成",check=check,axis="fail",verdict="FAIL_RENDER",annotations=annotations)
        b["card_audits"][0]["expected_semantic_packet"]["expected_evidence_annotation_inventory"]=[{"expected_annotation_id":"EA1","expected_role":"CORE"}]
        self.assertEqual(MODULE.validate_bundle(b),[])

    def test_wrong_role_requires_bound_observed_nodes(self):
        check={
            "observed_node_id":"N1","queue_authorization_status":"authorized","primary_source_support_status":"supported",
            "source_locators":["SRC001:Roesler 2025: child motif forthcoming"],"disposition":"AUTHORIZED_AND_SUPPORTED","materiality":"material","finding_id":None
        }
        annotations=[{"annotation_id":"A1","expected_annotation_id":"EA1","observed_role":"CONFLICT","expected_role":"GAP","status":"wrong_role","finding_id":"F-C10-ROLE"}]
        b=self.one_node(text="publication forthcoming",check=check,axis="fail",verdict="FAIL_RENDER",annotations=annotations)
        b["card_audits"][0]["expected_semantic_packet"]["expected_evidence_annotation_inventory"]=[{"expected_annotation_id":"EA1","expected_role":"GAP"}]
        self.assertTrue(any("wrong_role requires bound observed node list" in e for e in MODULE.validate_bundle(b)))

    def test_wrong_role_requires_known_nonempty_bound_nodes(self):
        check={
            "observed_node_id":"N1","queue_authorization_status":"authorized","primary_source_support_status":"supported",
            "source_locators":["SRC001:Roesler 2025"],"disposition":"AUTHORIZED_AND_SUPPORTED","materiality":"material","finding_id":None
        }
        for bound in ([],["UNKNOWN"]):
            with self.subTest(bound=bound):
                annotations=[{"annotation_id":"A1","expected_annotation_id":"EA1","observed_role":"CONFLICT","expected_role":"GAP","bound_observed_node_ids":bound,"status":"wrong_role","finding_id":"F-C10-ROLE"}]
                b=self.one_node(text="publication forthcoming",check=check,axis="fail",verdict="FAIL_RENDER",annotations=annotations)
                b["card_audits"][0]["expected_semantic_packet"]["expected_evidence_annotation_inventory"]=[{"expected_annotation_id":"EA1","expected_role":"GAP"}]
                self.assertTrue(any("wrong_role" in e and "bound" in e for e in MODULE.validate_bundle(b)))

    def test_evidence_annotation_inventory_must_be_fully_checked(self):
        b=self.base()
        b["card_audits"][0]["blind_readback"]["evidence_annotation_inventory"]=[{"annotation_id":"A1"},{"annotation_id":"A2"}]
        b["card_audits"][0]["expected_semantic_packet"]["expected_evidence_annotation_inventory"]=[
            {"expected_annotation_id":"EA1","expected_role":"CORE"},
            {"expected_annotation_id":"EA2","expected_role":"CORE"},
        ]
        b["card_audits"][0]["source_surface_reconciliation"]["evidence_annotation_checks"]=[
            {"annotation_id":"A1","expected_annotation_id":"EA1","status":"equivalent","observed_role":"CORE","expected_role":"CORE","bound_observed_node_ids":["N1"]}
        ]
        self.assertTrue(any("every material evidence annotation must be checked" in e for e in MODULE.validate_bundle(b)))

    def test_expected_annotation_inventory_is_closed_against_explicit_checks(self):
        check={
            "observed_node_id":"N1","queue_authorization_status":"authorized","primary_source_support_status":"supported",
            "source_locators":["SRC001:Roesler 2025"],"disposition":"AUTHORIZED_AND_SUPPORTED","materiality":"material","finding_id":None
        }
        annotations=[{
            "annotation_id":"A1","expected_annotation_id":"EA1","observed_role":"GAP","expected_role":"GAP",
            "bound_observed_node_ids":["N1"],"status":"equivalent","finding_id":None
        }]
        b=self.one_node(text="publication forthcoming",check=check,axis="pass",verdict="PASS",annotations=annotations)
        b["card_audits"][0]["expected_semantic_packet"]["expected_evidence_annotation_inventory"]=[
            {"expected_annotation_id":"EA1","expected_role":"GAP"}
        ]
        self.assertEqual(MODULE.validate_bundle(b),[])
        b["card_audits"][0]["source_surface_reconciliation"]["evidence_annotation_checks"]=[]
        self.assertTrue(any("expected evidence annotation inventory must be closed" in e for e in MODULE.validate_bundle(b)))

    def test_annotation_check_cannot_invent_expected_id_when_inventory_is_empty(self):
        check={
            "observed_node_id":"N1","queue_authorization_status":"authorized","primary_source_support_status":"supported",
            "source_locators":["SRC001:results"],"disposition":"AUTHORIZED_AND_SUPPORTED","materiality":"material","finding_id":None
        }
        annotations=[{
            "annotation_id":"A1","expected_annotation_id":"FAKE","observed_role":"GAP","expected_role":"GAP",
            "bound_observed_node_ids":["N1"],"status":"equivalent","finding_id":None
        }]
        b=self.one_node(text="publication forthcoming",check=check,axis="pass",verdict="PASS",annotations=annotations)
        self.assertTrue(any("expected_annotation_id not in expected inventory" in e or "expected evidence annotation inventory must be closed" in e for e in MODULE.validate_bundle(b)))

    def test_malformed_blind_inventory_items_return_errors(self):
        b=self.base()
        b["card_audits"][0]["blind_readback"]["content_node_inventory"].extend(["not-an-object",{"observed_node_id":"N3","material":"true"}])
        errors=MODULE.validate_bundle(b)
        self.assertTrue(any("content_node_inventory[2] must be object" in e for e in errors))
        self.assertTrue(any("content_node_inventory[3].material must be boolean" in e for e in errors))

    def test_source_locator_requires_source_id_locator_form(self):
        b=self.base()
        b["card_audits"][0]["source_surface_reconciliation"]["content_node_checks"][0]["source_locators"]=["SRC001"]
        self.assertTrue(any("source_id:locator form" in e for e in MODULE.validate_bundle(b)))

    def test_closed_set_check_requires_rendered_known_observed_node(self):
        b=self.base()
        b["card_audits"][0]["blind_readback"]["content_node_inventory"][0]["closed_set_member"]=True
        b["card_audits"][0]["expected_semantic_packet"]["expected_content_inventory"]=[
            {"expected_node_id":"EXPECTED-CLOSED-1","material":True,"closed_set_member":True}
        ]
        b["card_audits"][0]["source_surface_reconciliation"]["expected_content_checks"]=[
            {"closed_set_member":True,"status":"represented","expected_node_id":"EXPECTED-CLOSED-1","observed_node_id":"N2"}
        ]
        errors=MODULE.validate_bundle(b)
        self.assertTrue(any("rendered closed-set member" in e for e in errors))

    def test_closed_set_checks_must_map_one_to_one_to_observed_nodes(self):
        b=self.base()
        inventory=b["card_audits"][0]["blind_readback"]["content_node_inventory"]
        inventory[0]["closed_set_member"]=True
        inventory[1]["closed_set_member"]=True
        b["card_audits"][0]["expected_semantic_packet"]["expected_content_inventory"]=[
            {"expected_node_id":"E1","material":True,"closed_set_member":True},
            {"expected_node_id":"E2","material":True,"closed_set_member":True},
        ]
        b["card_audits"][0]["source_surface_reconciliation"]["expected_content_checks"]=[
            {"expected_node_id":"E1","closed_set_member":True,"status":"represented","observed_node_id":"N1"},
            {"expected_node_id":"E2","closed_set_member":True,"status":"represented","observed_node_id":"N1"},
        ]
        errors=MODULE.validate_bundle(b)
        self.assertTrue(any("one-to-one" in e for e in errors))
        self.assertTrue(any("cover every rendered" in e for e in errors))

    def test_malformed_nested_shapes_return_errors(self):
        b=self.base()
        b["card_audits"][0]["source_surface_reconciliation"]["evidence_annotation_checks"]=[
            {"annotation_id":[],"status":"wrong_role","observed_role":"GAP","expected_role":"GAP","bound_observed_node_ids":None}
        ]
        errors=MODULE.validate_bundle(b)
        self.assertTrue(errors)

    def test_standalone_validator_requires_current_contract_and_policy_binding(self):
        expected={
            "contract_version":MODULE.RESULT_CONTRACT_VERSION,
            "result_schema_version":MODULE.RESULT_SCHEMA_VERSION,
            "policy_id":MODULE.POLICY_ID,
            "policy_version":MODULE.POLICY_VERSION,
            "method_revision":MODULE.METHOD,
            "policy_digest":MODULE.POLICY_DIGEST,
        }
        for field,current in expected.items():
            with self.subTest(field=field):
                b=self.base(); b[field]=("tampered" if isinstance(current,str) else None)
                errors=MODULE.validate_bundle(b)
                self.assertTrue(any(f"{field} must be" in e for e in errors))

    def test_evidence_annotation_inventory_is_mandatory_even_when_empty(self):
        b=self.base()
        del b["card_audits"][0]["blind_readback"]["evidence_annotation_inventory"]
        self.assertTrue(any("evidence_annotation_inventory required" in e for e in MODULE.validate_bundle(b)))

    def test_duplicate_nonmaterial_annotation_is_warning_not_failure(self):
        check={
            "observed_node_id":"N1","queue_authorization_status":"authorized","primary_source_support_status":"supported",
            "source_locators":["SRC001:Roesler 2025"],"disposition":"AUTHORIZED_AND_SUPPORTED","materiality":"material","finding_id":None
        }
        annotations=[{"annotation_id":"A1","expected_annotation_id":"EA1","expected_role":"CORE","status":"duplicate_nonmaterial","finding_id":None}]
        b=self.one_node(text="可複製性",check=check,axis="warning",verdict="PASS_WITH_WARNINGS",annotations=annotations)
        b["card_audits"][0]["expected_semantic_packet"]["expected_evidence_annotation_inventory"]=[{"expected_annotation_id":"EA1","expected_role":"CORE"}]
        self.assertEqual(MODULE.validate_bundle(b),[])

    def test_legacy_undifferentiated_source_supported_not_authorized_is_rejected(self):
        check={
            "observed_node_id":"N1","queue_authorization_status":"not_authorized","primary_source_support_status":"supported",
            "source_locators":["SRC001:Roesler 2025"],"disposition":"SOURCE_SUPPORTED_BUT_NOT_QUEUE_AUTHORIZED","materiality":"material","finding_id":"F1"
        }
        errors=MODULE.validate_bundle(self.one_node(text="ambiguous",check=check,axis="fail",verdict="FAIL_RENDER"))
        self.assertTrue(any("legacy SOURCE_SUPPORTED_BUT_NOT_QUEUE_AUTHORIZED is ambiguous" in e for e in errors))

if __name__=="__main__": unittest.main()
