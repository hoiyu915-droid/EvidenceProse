import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"validate_rendered_card_audit.py"
SPEC=importlib.util.spec_from_file_location("validate_rendered_card_audit",SCRIPT)
MODULE=importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

class RenderedCardAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads((ROOT/"fixtures"/"valid_rendered_card_audit.json").read_text(encoding="utf-8"))
    def validate(self,b): return MODULE.validate_bundle(copy.deepcopy(b),base_dir=ROOT/"fixtures")
    def c02_wrong_branch_bundle(self):
        b=copy.deepcopy(self.fixture); c=b["card_audits"][0]
        c["card_id"]="C02"; c["card_title"]="威脅來時，依附系統怎麼分岔？"
        og={"nodes":[{"node_id":"T","label":"威脅"},{"node_id":"A","label":"依附系統啟動"},{"node_id":"S","label":"支持可得／安全感上升"},{"node_id":"H","label":"過度活化"},{"node_id":"D","label":"去活化"}],"edges":[{"edge_id":"E1","from_node":"T","to_node":"A","relation_as_read":"sequence","material":True},{"edge_id":"E2","from_node":"A","to_node":"S","relation_as_read":"sequence","material":True},{"edge_id":"E3","from_node":"S","to_node":"H","relation_as_read":"branch","material":True},{"edge_id":"E4","from_node":"S","to_node":"D","relation_as_read":"branch","material":True}]}
        eg={"nodes":[{"node_id":"T"},{"node_id":"A"},{"node_id":"S"},{"node_id":"I"},{"node_id":"H"},{"node_id":"D"}],"relations":[{"relation_id":"R1","from_node":"T","to_node":"A","relation_type":"sequence","material":True},{"relation_id":"R2","from_node":"A","to_node":"S","relation_type":"conditional_branch","condition":"可得且回應","material":True},{"relation_id":"R3","from_node":"A","to_node":"I","relation_type":"conditional_branch","condition":"不可得或缺乏回應","material":True},{"relation_id":"R4","from_node":"I","to_node":"H","relation_type":"strategy_branch","condition":"不安全感持續","material":True},{"relation_id":"R5","from_node":"I","to_node":"D","relation_type":"strategy_branch","condition":"不安全感持續","material":True}],"branch_points":[{"branch_id":"B1","node_id":"A","material":True}],"terminal_states":[{"terminal_id":"TS1","node_id":"S","material":True}],"role_partitions":[]}
        c["blind_readback"]["visual_graph_digest"]=MODULE.jd(og)
        c["visual_semantic_reconciliation"]={"source_structure":{"structure_required":True,"source_kind":"figure","source_locators":["Dewitte 2012 Figure 1"],"figure_or_table_directly_inspected":True,"expected_graph_derived":True},"observed_graph":og,"observed_graph_digest":MODULE.jd(og),"expected_graph":eg,"expected_graph_digest":MODULE.jd(eg),"edge_checks":[{"edge_id":"E1","status":"equivalent","finding_id":None},{"edge_id":"E2","status":"equivalent","finding_id":None},{"edge_id":"E3","status":"wrong_source_node","finding_id":"F1"},{"edge_id":"E4","status":"wrong_source_node","finding_id":"F1"}],"expected_relation_checks":[{"relation_id":"R1","status":"represented","finding_id":None},{"relation_id":"R2","status":"represented","finding_id":None},{"relation_id":"R3","status":"omitted_material","finding_id":"F2"},{"relation_id":"R4","status":"distorted","finding_id":"F1"},{"relation_id":"R5","status":"distorted","finding_id":"F1"}],"branch_point_checks":[{"branch_id":"B1","status":"fail","finding_id":"F2"}],"terminal_state_checks":[{"terminal_id":"TS1","status":"fail","finding_id":"F3"}],"role_partition_checks":[],"text_visual_consistency":{"status":"fail","contradictions":["文字說持續不安才分岔；箭頭卻從安全感上升分岔。"],"finding_id":"F4"},"topology_completion":{"all_observed_material_edges_dispositioned":True,"all_expected_material_relations_covered":True,"all_material_branch_points_checked":True,"all_material_terminal_states_checked":True,"all_material_role_partitions_checked":True,"text_visual_consistency_checked":True,"concept_presence_shortcut_not_used":True}}
        def f(fid,typ): return {"finding_id":fid,"axis":"VISUAL_SEMANTICS","finding_type":typ,"materiality":"material","observed":"wrong topology","expected":"Figure 1 conditional branch topology","reader_risk":"reader learns wrong branch model","source_support":["Dewitte 2012 Figure 1"],"repair_prescription":{"action":"REWIRE","instruction":"Restore persistent-insecurity branch topology."}}
        c["findings"]=[f("F1","WRONG_EDGE_SOURCE_NODE"),f("F2","BRANCH_TOPOLOGY_DISTORTION"),f("F3","TERMINAL_STATE_CONTINUED"),f("F4","TEXT_VISUAL_CONTRADICTION")]
        c["axes"]["VISUAL_SEMANTICS"]="fail"; c["verdict"]="FAIL_RENDER"; c["release_blocking"]=True; c["repair_ticket_id"]="RT-C02"
        repair="刪除安全感上升直接連到過度活化／去活化的箭頭。把依附系統啟動改為可得且回應→安全感上升並降溫；不可得或缺乏回應→不安全感持續→過度活化或去活化。"
        b["repair_tickets"]=[{"ticket_id":"RT-C02","card_id":"C02","card_title":c["card_title"],"verdict":"FAIL_RENDER","problem_summary":"Wrong branch source.","human_repair_text":repair,"action_plan":[{"action":"REWIRE","instruction":"Restore the two conditional branches."}],"substantial_change":{"triggered":True,"total_semantic_weight":20,"changed_semantic_weight":4,"structural_triggers":["central_visual_graph_rewire"],"estimated_weighted_semantic_fraction":0.2,"replacement_required":True,"replacement_status":"SUPPORTED","replacement_material":{"presentation":"writing_block","text":"支持可得且有回應→安全感上升→依附系統降溫；支持不可得或缺乏回應→不安全感持續→過度活化或去活化。"}}}]
        b["human_repair_display"]={"surface":"writing_block","single_block":True,"first_line":"imgedit","sections":[{"card_id":"C02","card_title":c["card_title"],"ticket_id":"RT-C02","heading":f"[{c['card_title']}]","content":repair}],"rendered_text":f"imgedit\n[{c['card_title']}]\n{repair}"}
        b["release_gate"].update({"status":"FAIL","release_allowed":False,"blocking_card_ids":["C02"]}); b["release_gate"]["counts"].update({"PASS":0,"FAIL_RENDER":1})
        return b
    def test_valid_fixture_passes(self): self.assertEqual(self.validate(self.fixture),[])
    def test_c02_wrong_branch_is_canonical_fail_record(self): self.assertEqual(self.validate(self.c02_wrong_branch_bundle()),[])
    def test_wording_divergence_does_not_fail(self):
        b=copy.deepcopy(self.fixture); b["card_audits"][0]["historical_text_comparison"]="wording_divergence"; self.assertEqual(self.validate(b),[])
    def test_image_hash_must_match(self):
        b=copy.deepcopy(self.fixture); b["card_audits"][0]["image_sha256"]="0"*64; self.assertTrue(any("image hash mismatch" in e for e in self.validate(b)))
    def test_every_observed_material_edge_requires_disposition(self):
        b=copy.deepcopy(self.fixture); b["card_audits"][0]["visual_semantic_reconciliation"]["edge_checks"]=[]; self.assertTrue(any("every observed material edge" in e for e in self.validate(b)))
    def test_every_expected_relation_requires_coverage(self):
        b=copy.deepcopy(self.fixture); b["card_audits"][0]["visual_semantic_reconciliation"]["expected_relation_checks"]=[]; self.assertTrue(any("every expected material relation" in e for e in self.validate(b)))
    def test_c02_wrong_source_node_cannot_be_marked_pass(self):
        b=self.c02_wrong_branch_bundle(); c=b["card_audits"][0]; c["axes"]["VISUAL_SEMANTICS"]="pass"; c["verdict"]="PASS"; c["release_blocking"]=False; c["repair_ticket_id"]=None; b["repair_tickets"]=[]; b["human_repair_display"]=None; b["release_gate"].update({"status":"PASS","release_allowed":True,"blocking_card_ids":[]}); b["release_gate"]["counts"].update({"PASS":1,"FAIL_RENDER":0})
        self.assertTrue(any("VISUAL_SEMANTICS must be fail" in e for e in self.validate(b)))
    def test_branch_failure_requires_linked_finding(self):
        b=self.c02_wrong_branch_bundle(); b["card_audits"][0]["visual_semantic_reconciliation"]["branch_point_checks"][0]["finding_id"]=None
        self.assertTrue(any("branch B1 requires linked finding" in e for e in self.validate(b)))
    def test_terminal_failure_requires_linked_finding(self):
        b=self.c02_wrong_branch_bundle(); b["card_audits"][0]["visual_semantic_reconciliation"]["terminal_state_checks"][0]["finding_id"]=None
        self.assertTrue(any("terminal TS1 requires linked finding" in e for e in self.validate(b)))
    def test_text_visual_contradiction_requires_linked_finding(self):
        b=self.c02_wrong_branch_bundle(); b["card_audits"][0]["visual_semantic_reconciliation"]["text_visual_consistency"]["finding_id"]=None
        self.assertTrue(any("text/visual failure requires linked finding" in e for e in self.validate(b)))
    def test_concept_presence_shortcut_is_forbidden(self):
        b=copy.deepcopy(self.fixture); b["card_audits"][0]["visual_semantic_reconciliation"]["topology_completion"]["concept_presence_shortcut_not_used"]=False
        self.assertTrue(any("concept-presence shortcut is forbidden" in e for e in self.validate(b)))
    def test_figure_derived_structure_requires_direct_inspection(self):
        b=self.c02_wrong_branch_bundle(); b["card_audits"][0]["visual_semantic_reconciliation"]["source_structure"]["figure_or_table_directly_inspected"]=False
        self.assertTrue(any("requires direct inspection" in e for e in self.validate(b)))
    def test_failed_card_requires_writing_block_display(self):
        b=self.c02_wrong_branch_bundle(); b["human_repair_display"]=None
        self.assertTrue(any("require human_repair_display" in e for e in self.validate(b)))
    def test_writing_block_first_line_is_imgedit(self):
        b=self.c02_wrong_branch_bundle(); b["human_repair_display"]["first_line"]="edit"
        self.assertTrue(any("first line must be exactly imgedit" in e for e in self.validate(b)))
    def test_writing_block_heading_must_be_actual_card_title(self):
        b=self.c02_wrong_branch_bundle(); b["human_repair_display"]["sections"][0]["heading"]="[C02]"
        self.assertTrue(any("heading must be exact" in e for e in self.validate(b)))
    def test_small_failure_still_requires_human_repair_text(self):
        b=self.c02_wrong_branch_bundle(); t=b["repair_tickets"][0]; t["substantial_change"]={"triggered":False,"total_semantic_weight":20,"changed_semantic_weight":1,"structural_triggers":[],"estimated_weighted_semantic_fraction":0.05,"replacement_required":False,"replacement_status":"NOT_REQUIRED","replacement_material":None}; t["human_repair_text"]=""; b["human_repair_display"]["sections"][0]["content"]=""
        self.assertTrue(any("human_repair_text required for every failure" in e for e in self.validate(b)))
    def test_substantial_repair_requires_supported_writing_block_material(self):
        b=self.c02_wrong_branch_bundle(); b["repair_tickets"][0]["substantial_change"]["replacement_material"]=None
        self.assertTrue(any("SUPPORTED replacement requires writing_block text" in e for e in self.validate(b)))
    def test_roesler_c03_directional_speculative_bridge_cannot_pass(self):
        b=copy.deepcopy(self.fixture); c=b["card_audits"][0]
        c["card_id"]="C03"; c["card_title"]="共時性：有影響，不等於驗證"
        vr=c["visual_semantic_reconciliation"]
        vr["edge_checks"][0].update({"status":"wrong_direction","finding_id":"F-C03-DIR"})
        c["findings"]=[{
            "finding_id":"F-C03-DIR","axis":"VISUAL_SEMANTICS","finding_type":"WRONG_DIRECTION","materiality":"material",
            "observed":"Bridge rendered as one-way direction.","expected":"Unordered/speculative bridge without directional implication.",
            "reader_risk":"Reader may infer directed influence.","source_support":["Roesler 2025: synchronicity/unus mundus discussion"],
            "repair_prescription":{"action":"REWIRE","instruction":"Remove arrowhead and retain non-directional bridge."}
        }]
        c["axes"]["VISUAL_SEMANTICS"]="fail"; c["verdict"]="FAIL_RENDER"; c["release_blocking"]=True; c["repair_ticket_id"]="RT-C03"
        repair="移除心與物之間虛線橋接的箭頭尖端，保留無方向的思辨性連接。"
        b["repair_tickets"]=[{
            "ticket_id":"RT-C03","card_id":"C03","card_title":c["card_title"],"verdict":"FAIL_RENDER","problem_summary":"Speculative bridge became directional.",
            "human_repair_text":repair,"action_plan":[{"action":"REWIRE","instruction":"Remove the arrowhead."}],
            "substantial_change":{"triggered":False,"total_semantic_weight":20,"changed_semantic_weight":1,"structural_triggers":[],"estimated_weighted_semantic_fraction":0.05,"replacement_required":False,"replacement_status":"NOT_REQUIRED","replacement_material":None}
        }]
        b["human_repair_display"]={"surface":"writing_block","single_block":True,"first_line":"imgedit","sections":[{"card_id":"C03","card_title":c["card_title"],"ticket_id":"RT-C03","heading":f"[{c['card_title']}]","content":repair}],"rendered_text":f"imgedit\n[{c['card_title']}]\n{repair}"}
        b["release_gate"].update({"status":"FAIL","release_allowed":False,"blocking_card_ids":["C03"]}); b["release_gate"]["counts"].update({"PASS":0,"FAIL_RENDER":1})
        self.assertEqual(self.validate(b),[])

    def test_roesler_c06_duplicate_text_collapsing_contrast_cannot_pass(self):
        b=copy.deepcopy(self.fixture); c=b["card_audits"][0]
        c["card_id"]="C06"; c["card_title"]="改變從哪裡來？還沒解決"
        vr=c["visual_semantic_reconciliation"]
        vr["expected_graph"]["role_partitions"]=[{
            "partition_id":"P1","left_role":"Jung_inner_autonomous_transformation","right_role":"modern_relationship_corrective_experience","material":True
        }]
        vr["expected_graph_digest"]=MODULE.jd(vr["expected_graph"])
        vr["role_partition_checks"]=[{"partition_id":"P1","status":"collapsed_contrast","finding_id":"F-C06-PART"}]
        vr["topology_completion"]["all_material_role_partitions_checked"]=True
        c["findings"]=[{
            "finding_id":"F-C06-PART","axis":"VISUAL_SEMANTICS","finding_type":"ROLE_PARTITION_COLLAPSE","materiality":"material",
            "observed":"Both contrast boxes repeat the full two-sided sentence.",
            "expected":"Left box carries Jung's inner-autonomous emphasis; right box carries modern relationship/corrective-experience emphasis.",
            "reader_risk":"The visual comparison collapses two distinct positions into identical content.",
            "source_support":["Roesler 2025: change mechanism discussion"],
            "repair_prescription":{"action":"REPLACE","instruction":"Partition the two supported positions into their correct boxes."}
        }]
        c["axes"]["VISUAL_SEMANTICS"]="fail"; c["verdict"]="FAIL_RENDER"; c["release_blocking"]=True; c["repair_ticket_id"]="RT-C06"
        repair="左框只放榮格偏向內在自主轉化；右框只放當代治療研究較強調治療聯盟與修正性情緒經驗等關係性因素。"
        b["repair_tickets"]=[{
            "ticket_id":"RT-C06","card_id":"C06","card_title":c["card_title"],"verdict":"FAIL_RENDER","problem_summary":"Contrast roles collapsed by duplicated placement.",
            "human_repair_text":repair,"action_plan":[{"action":"REPLACE","instruction":"Partition duplicated text by semantic role."}],
            "substantial_change":{"triggered":False,"total_semantic_weight":20,"changed_semantic_weight":1,"structural_triggers":[],"estimated_weighted_semantic_fraction":0.05,"replacement_required":False,"replacement_status":"NOT_REQUIRED","replacement_material":None}
        }]
        b["human_repair_display"]={"surface":"writing_block","single_block":True,"first_line":"imgedit","sections":[{"card_id":"C06","card_title":c["card_title"],"ticket_id":"RT-C06","heading":f"[{c['card_title']}]","content":repair}],"rendered_text":f"imgedit\n[{c['card_title']}]\n{repair}"}
        b["release_gate"].update({"status":"FAIL","release_allowed":False,"blocking_card_ids":["C06"]}); b["release_gate"]["counts"].update({"PASS":0,"FAIL_RENDER":1})
        self.assertEqual(self.validate(b),[])
        c["axes"]["VISUAL_SEMANTICS"]="pass"; c["verdict"]="PASS"; c["release_blocking"]=False; c["repair_ticket_id"]=None; b["repair_tickets"]=[]; b["human_repair_display"]=None
        b["release_gate"].update({"status":"PASS","release_allowed":True,"blocking_card_ids":[]}); b["release_gate"]["counts"].update({"PASS":1,"FAIL_RENDER":0})
        self.assertTrue(any("VISUAL_SEMANTICS must be fail" in e for e in self.validate(b)))

    def test_same_family_high_stakes_blocks_pending_secondary_review(self):
        b=copy.deepcopy(self.fixture); r=b["methodological_risk"]; r.update({"auditor_model_family":"family-a","relationship":"same_family","correlated_error_risk":"present","material_to_run":True,"secondary_review_required":True,"secondary_review_status":"pending","secondary_review_outcome":"not_applicable","release_effect":"blocked_pending_secondary_review"}); b["release_gate"]["status"]="BLOCKED"; b["release_gate"]["release_allowed"]=False
        self.assertEqual(self.validate(b),[])

if __name__=="__main__": unittest.main()
