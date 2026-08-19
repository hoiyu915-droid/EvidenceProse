#!/usr/bin/env python3
"""Validate RCA v1.2 source-surface, scope and evidence-annotation closure.

This validator does not infer pixels or scientific truth. It checks that an auditor
has explicitly dispositioned every declared material content node and evidence
annotation, while preventing two opposite shortcuts:

1. topic-plausible additions cannot pass without bound-source support and card scope;
2. literal queue wording is not a science gate by itself when a source-supported,
   non-expansive explanation preserves the same semantic node.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any

SCRIPT_DIR=Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path: sys.path.insert(0,str(SCRIPT_DIR))
from validate_rca_policy import get_current_policy

RCA_POLICY,POLICY_DIGEST=get_current_policy()
POLICY_ID=RCA_POLICY["policy_id"]
METHOD=RCA_POLICY["method_revision"]
POLICY_VERSION=RCA_POLICY["policy_version"]
RESULT_SCHEMA_VERSION=RCA_POLICY["result_schema_version"]
RESULT_CONTRACT_VERSION=RCA_POLICY["contract_version"]
SOURCE_POLICY=RCA_POLICY["source_surface"]
DISPOSITIONS=SOURCE_POLICY["dispositions"]
PASS_DISPOSITIONS=set(DISPOSITIONS["pass"])
FAIL_DISPOSITIONS=set(DISPOSITIONS["fail"])
BLOCK_DISPOSITIONS=set(DISPOSITIONS["block"])
LEGACY_DISPOSITIONS=set(DISPOSITIONS["deprecated"])
NON_MATERIAL_DISPOSITIONS=set(DISPOSITIONS["non_material"])
ALLOWED=set().union(*DISPOSITIONS.values())
ANNOTATION_POLICY=SOURCE_POLICY["annotation"]
ANNOTATION_PASS=set(ANNOTATION_POLICY["statuses"]["pass"])
ANNOTATION_WARN=set(ANNOTATION_POLICY["statuses"]["warning"])
ANNOTATION_FAIL=set(ANNOTATION_POLICY["statuses"]["fail"])
ANNOTATION_BLOCK=set(ANNOTATION_POLICY["statuses"]["block"])
ANNOTATION_ALLOWED=ANNOTATION_PASS|ANNOTATION_WARN|ANNOTATION_FAIL|ANNOTATION_BLOCK
ANNOTATION_ROLES=set(ANNOTATION_POLICY["roles"])
QUEUE_AUTHORIZATION_STATUSES=set(SOURCE_POLICY["queue_authorization_statuses"])
SOURCE_SUPPORT_STATUSES=set(SOURCE_POLICY["primary_source_support_statuses"])
CARD_SCOPE_STATUSES=set(SOURCE_POLICY["card_scope_statuses"])
EXPANSION_KEYS=tuple(SOURCE_POLICY["expansion_keys"])
AXIS_STATUSES=set(RCA_POLICY["verdict_mapping"]["axis_status_to_verdict"])
VERDICTS=set(RCA_POLICY["verdict_mapping"]["verdicts"])

def txt(v): return isinstance(v,str) and bool(v.strip())
def sha(v): return txt(v) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def add(errors,msg): errors.append(msg)

def _validate_source_locators(value:Any,path:str,errors:list[str])->list[str]:
    """Validate locator grammar and return the source ids present.

    Locators are integrity references, not free-form source prose.  Keeping
    the parser here means the standalone source-closure validator cannot
    silently accept a locator that the integrated audit would later ignore.
    """
    if not isinstance(value,list):
        add(errors,f"{path} must be array")
        return []
    source_ids=[]
    for i,locator in enumerate(value):
        q=f"{path}[{i}]"
        if not isinstance(locator,str) or not locator.strip():
            add(errors,f"{q} must be a non-empty source_id:locator string")
            continue
        source_id,separator,detail=locator.partition(":")
        if not separator or not source_id.strip() or not detail.strip():
            add(errors,f"{q} must use source_id:locator form")
            continue
        source_ids.append(source_id.strip())
    return source_ids

def _material_nodes(card:Any) -> list[dict[str,Any]]:
    br=card.get("blind_readback",{})
    inventory=br.get("content_node_inventory") if isinstance(br,dict) else None
    if not isinstance(inventory,list):
        return []
    return [n for n in inventory if isinstance(n,dict) and n.get("material") is True]

def _closed_set_ids(nodes:list[dict[str,Any]]) -> list[str]:
    return [
        node.get("observed_node_id")
        for node in nodes
        if node.get("closed_set_member") is True
        and txt(node.get("observed_node_id"))
    ]

def _expected_closed_set_ids(card:dict[str,Any],p:str,errors:list[str])->list[str]:
    packet=card.get("expected_semantic_packet")
    if not isinstance(packet,dict):
        add(errors,f"{p} expected_semantic_packet required")
        return []
    inventory=packet.get("expected_content_inventory")
    if not isinstance(inventory,list):
        add(errors,f"{p} expected_semantic_packet.expected_content_inventory must be array")
        return []
    ids=[]
    for i,item in enumerate(inventory):
        q=f"{p}.expected_semantic_packet.expected_content_inventory[{i}]"
        if not isinstance(item,dict):
            add(errors,f"{q} must be object")
            continue
        if not isinstance(item.get("material"),bool):
            add(errors,f"{q}.material must be boolean")
        if not isinstance(item.get("closed_set_member"),bool):
            add(errors,f"{q}.closed_set_member must be boolean")
        if item.get("material") is not True or item.get("closed_set_member") is not True:
            continue
        expected_id=item.get("expected_node_id")
        if not txt(expected_id):
            add(errors,f"{q} material closed-set member requires expected_node_id")
        else:
            ids.append(expected_id)
    if len(ids)!=len(set(ids)):
        add(errors,f"{p} expected closed-set node ids must be unique")
    return ids

def _expected_annotation_specs(card:dict[str,Any],p:str,errors:list[str])->dict[str,str]:
    packet=card.get("expected_semantic_packet")
    if not isinstance(packet,dict):
        return {}
    inventory=packet.get("expected_evidence_annotation_inventory")
    if not isinstance(inventory,list):
        add(errors,f"{p} expected_semantic_packet.expected_evidence_annotation_inventory must be array")
        return {}
    specs:dict[str,str]={}
    for i,item in enumerate(inventory):
        q=f"{p}.expected_semantic_packet.expected_evidence_annotation_inventory[{i}]"
        if not isinstance(item,dict):
            add(errors,f"{q} must be object")
            continue
        aid=item.get("expected_annotation_id")
        role=item.get("expected_role")
        if not txt(aid):
            add(errors,f"{q}.expected_annotation_id required")
            continue
        if aid in specs:
            add(errors,f"{q}.expected_annotation_id must be unique")
        if not isinstance(role,str) or role not in ANNOTATION_ROLES:
            add(errors,f"{q}.expected_role invalid")
        else:
            specs[aid]=role
    return specs

def _nonexpansive_check(x:dict[str,Any],q:str,errors:list[str])->None:
    if not txt(x.get("semantic_parent_node_id")):
        add(errors,f"{q} non-expansive elaboration requires semantic_parent_node_id")
    ex=x.get("expansion_test")
    if not isinstance(ex,dict):
        add(errors,f"{q} non-expansive elaboration requires expansion_test")
        return
    for k in EXPANSION_KEYS:
        if ex.get(k) is not False:
            add(errors,f"{q} expansion_test.{k} must be false for non-expansive elaboration")
    if x.get("queue_protective_lock_material") is not False:
        add(errors,f"{q} non-expansive elaboration requires queue_protective_lock_material=false")

def validate_card(card:Any,errors:list[str]):
    if not isinstance(card,dict): add(errors,"card audit must be object"); return
    cid=card.get("card_id","?"); p=f"card {cid}"
    br=card.get("blind_readback",{})
    inventory=br.get("content_node_inventory") if isinstance(br,dict) else None
    if not isinstance(inventory,list): add(errors,f"{p} blind_readback.content_node_inventory must be array"); return
    for i,node in enumerate(inventory):
        q=f"{p}.blind_readback.content_node_inventory[{i}]"
        if not isinstance(node,dict):
            add(errors,f"{q} must be object")
            continue
        if not isinstance(node.get("material"),bool):
            add(errors,f"{q}.material must be boolean")
        if "closed_set_member" in node and not isinstance(node.get("closed_set_member"),bool):
            add(errors,f"{q}.closed_set_member must be boolean")
    material=_material_nodes(card)
    raw_ids=[n.get("observed_node_id") for n in material]
    ids=[x for x in raw_ids if txt(x)]
    if len(ids)!=len(raw_ids): add(errors,f"{p} every material observed content node requires observed_node_id")
    if len(ids)!=len(set(ids)): add(errors,f"{p} material observed content node ids must be unique")
    ann_inventory=[]
    if "evidence_annotation_inventory" not in br:
        add(errors,f"{p}.blind_readback.evidence_annotation_inventory required")
    raw_ann_inv=br.get("evidence_annotation_inventory",[]) if isinstance(br,dict) else []
    if not isinstance(raw_ann_inv,list):
        add(errors,f"{p}.evidence_annotation_inventory must be array")
        raw_ann_inv=[]
    for i,a in enumerate(raw_ann_inv):
        if not isinstance(a,dict):
            add(errors,f"{p}.evidence_annotation_inventory[{i}] must be object"); continue
        aid=a.get("annotation_id")
        if not txt(aid):
            add(errors,f"{p}.evidence_annotation_inventory[{i}].annotation_id required")
        ann_inventory.append(aid)

    rec=card.get("source_surface_reconciliation")
    if not isinstance(rec,dict): add(errors,f"{p} source_surface_reconciliation required"); return
    checks=rec.get("content_node_checks")
    if not isinstance(checks,list): add(errors,f"{p} content_node_checks must be array"); return
    check_values=[x.get("observed_node_id") for x in checks if isinstance(x,dict)]
    check_ids=[x for x in check_values if txt(x)]
    if len(check_ids)!=len(check_values): add(errors,f"{p} every content node check requires observed_node_id")
    if sorted(check_ids)!=sorted(ids): add(errors,f"{p} every observed material content node must be dispositioned exactly once")

    bad=unv=warn=False
    observed_closed_set_ids=_closed_set_ids(material)
    for i,x in enumerate(checks):
        q=f"{p}.content_node_checks[{i}]"
        if not isinstance(x,dict): add(errors,f"{q} must be object"); continue
        disp=x.get("disposition")
        if not isinstance(disp,str) or disp not in ALLOWED: add(errors,f"{q} disposition invalid"); continue
        if x.get("materiality")!="material": add(errors,f"{q} material node check must declare materiality=material")
        qa=x.get("queue_authorization_status")
        ss=x.get("primary_source_support_status")
        if not isinstance(qa,str) or qa not in QUEUE_AUTHORIZATION_STATUSES: add(errors,f"{q} queue_authorization_status invalid")
        if not isinstance(ss,str) or ss not in SOURCE_SUPPORT_STATUSES: add(errors,f"{q} primary_source_support_status invalid")
        loc=x.get("source_locators",[])
        _validate_source_locators(loc,f"{q}.source_locators",errors)
        if not isinstance(loc,list): loc=[]
        if ss=="supported" and not any(txt(v) for v in loc if isinstance(v,str)): add(errors,f"{q} supported node requires source locator")

        if disp in FAIL_DISPOSITIONS:
            bad=True
            if not txt(x.get("finding_id")): add(errors,f"{q} failing disposition requires finding_id")
        elif disp in BLOCK_DISPOSITIONS:
            unv=True
            if not txt(x.get("finding_id")): add(errors,f"{q} unverifiable disposition requires finding_id")
        elif disp=="SOURCE_SUPPORTED_BUT_NOT_QUEUE_AUTHORIZED":
            # v1.2 audits must decide whether this is a real semantic expansion or merely
            # a faithful elaboration. The old undifferentiated disposition is no longer
            # sufficient to derive a verdict.
            add(errors,f"{q} legacy SOURCE_SUPPORTED_BUT_NOT_QUEUE_AUTHORIZED is ambiguous; use SOURCE_SUPPORTED_NONEXPANSIVE_ELABORATION, SOURCE_SUPPORTED_BUT_OUT_OF_CARD_SCOPE, or MATERIAL_QUEUE_PROTECTIVE_LOCK_VIOLATION")
        elif disp in NON_MATERIAL_DISPOSITIONS:
            add(errors,f"{q} material node cannot be NON_MATERIAL_DECORATION")
        elif disp=="AUTHORIZED_AND_SUPPORTED" and not (qa=="authorized" and ss=="supported"):
            add(errors,f"{q} AUTHORIZED_AND_SUPPORTED requires authorized + supported")
        elif disp=="SEMANTICALLY_EQUIVALENT_PARAPHRASE":
            if ss!="supported": add(errors,f"{q} paraphrase requires primary-source support")
            if x.get("semantic_equivalence_to_queue") is not True: add(errors,f"{q} paraphrase requires semantic_equivalence_to_queue=true")
        elif disp=="SOURCE_SUPPORTED_NONEXPANSIVE_ELABORATION":
            if ss!="supported": add(errors,f"{q} non-expansive elaboration requires primary-source support")
            _nonexpansive_check(x,q,errors)
        if disp=="SOURCE_SUPPORTED_BUT_OUT_OF_CARD_SCOPE":
            if ss!="supported" or qa!="not_authorized": add(errors,f"{q} out-of-card-scope requires supported + not_authorized")
            if not isinstance(x.get("card_scope_status"),str) or x.get("card_scope_status") not in CARD_SCOPE_STATUSES: add(errors,f"{q} out-of-card-scope requires explicit card_scope_status")
        if disp=="MATERIAL_QUEUE_PROTECTIVE_LOCK_VIOLATION":
            if x.get("queue_protective_lock_material") is not True or not txt(x.get("protective_purpose")):
                add(errors,f"{q} protective-lock failure requires material protective purpose")

    exp=rec.get("expected_content_checks",[])
    if not isinstance(exp,list): add(errors,f"{p} expected_content_checks must be array"); exp=[]
    expected_closed_set_ids=_expected_closed_set_ids(card,p,errors)
    if len(observed_closed_set_ids)!=len(expected_closed_set_ids):
        add(errors,f"{p} rendered closed-set members must match expected inventory cardinality")
        bad=True
    for i,x in enumerate(exp):
        if not isinstance(x,dict): add(errors,f"{p}.expected_content_checks[{i}] must be object"); continue
        if "source_locators" in x:
            _validate_source_locators(x.get("source_locators"),f"{p}.expected_content_checks[{i}].source_locators",errors)
        if x.get("closed_set_member") is True and (not isinstance(x.get("status"),str) or x.get("status") not in {"represented","semantically_equivalent"}):
            bad=True
            if not txt(x.get("finding_id")): add(errors,f"{p}.expected_content_checks[{i}] failed closed-set member requires finding_id")
        if x.get("closed_set_member") is True:
            xid=x.get("expected_node_id")
            if not txt(xid): add(errors,f"{p}.expected_content_checks[{i}] closed_set item requires expected_node_id")
            elif x.get("status") in {"represented","semantically_equivalent"}:
                observed_id=x.get("observed_node_id")
                if not txt(observed_id) or observed_id not in ids:
                    add(errors,f"{p}.expected_content_checks[{i}] represented closed-set member requires known observed_node_id")
                    bad=True
                elif observed_id not in observed_closed_set_ids:
                    add(errors,f"{p}.expected_content_checks[{i}] observed_node_id must be a rendered closed-set member")
                    bad=True
    declared=[x.get("expected_node_id") for x in exp if isinstance(x,dict) and x.get("closed_set_member") is True and txt(x.get("expected_node_id"))]
    if sorted(declared)!=sorted(expected_closed_set_ids):
        add(errors,f"{p} expected_content_checks must cover all expected closed-set members")
        bad=True
    if len(declared)!=len(set(declared)):
        add(errors,f"{p} expected closed-set checks must be unique")
        bad=True
    represented_observed_ids=[
        x.get("observed_node_id")
        for x in exp
        if isinstance(x,dict)
        and x.get("closed_set_member") is True
        and x.get("status") in {"represented","semantically_equivalent"}
        and txt(x.get("observed_node_id"))
    ]
    if len(represented_observed_ids)!=len(set(represented_observed_ids)):
        add(errors,f"{p} represented closed-set checks must map one-to-one to observed nodes")
        bad=True
    if sorted(represented_observed_ids)!=sorted(observed_closed_set_ids):
        add(errors,f"{p} represented closed-set checks must cover every rendered closed-set member")
        bad=True

    annotations=rec.get("evidence_annotation_checks",[])
    if not isinstance(annotations,list): add(errors,f"{p} evidence_annotation_checks must be array"); annotations=[]
    expected_annotation_specs=_expected_annotation_specs(card,p,errors)
    packet=card.get("expected_semantic_packet")
    expected_annotation_inventory_declared=isinstance(packet,dict) and "expected_evidence_annotation_inventory" in packet
    annotation_ids=[]
    checked_expected_annotation_ids=[]
    for i,x in enumerate(annotations):
        q=f"{p}.evidence_annotation_checks[{i}]"
        if not isinstance(x,dict): add(errors,f"{q} must be object"); continue
        aid=x.get("annotation_id"); annotation_ids.append(aid)
        if not txt(aid): add(errors,f"{q} annotation_id required")
        st=x.get("status")
        if "source_locators" in x:
            _validate_source_locators(x.get("source_locators"),f"{q}.source_locators",errors)
        if not isinstance(st,str) or st not in ANNOTATION_ALLOWED: add(errors,f"{q} status invalid"); continue
        if expected_annotation_inventory_declared:
            expected_id=x.get("expected_annotation_id")
            if not txt(expected_id):
                add(errors,f"{q} expected_annotation_id required")
            elif expected_id not in expected_annotation_specs:
                add(errors,f"{q} expected_annotation_id not in expected inventory")
            else:
                checked_expected_annotation_ids.append(expected_id)
                if x.get("expected_role")!=expected_annotation_specs[expected_id]:
                    add(errors,f"{q} expected_role does not match expected annotation inventory")
        if st in ANNOTATION_FAIL:
            bad=True
            if not txt(x.get("finding_id")): add(errors,f"{q} failing annotation requires finding_id")
        elif st in ANNOTATION_BLOCK:
            unv=True
            if not txt(x.get("finding_id")): add(errors,f"{q} unverifiable annotation requires finding_id")
        elif st in ANNOTATION_WARN:
            warn=True
        if st in {"equivalent","wrong_role","wrong_binding"}:
            if not isinstance(x.get("observed_role"),str) or x.get("observed_role") not in ANNOTATION_ROLES: add(errors,f"{q} observed_role invalid")
            if not isinstance(x.get("expected_role"),str) or x.get("expected_role") not in ANNOTATION_ROLES: add(errors,f"{q} expected_role invalid")
            bound=x.get("bound_observed_node_ids")
            if not isinstance(bound,list) or not bound or any(not txt(v) for v in bound): add(errors,f"{q} {st} requires bound observed node list")
            elif any(oid not in ids for oid in bound):
                for oid in bound:
                    if oid not in ids:
                        add(errors,f"{q} {st} bound observed node {oid} not in blind inventory")
    valid_annotation_ids=[x for x in annotation_ids if txt(x)]
    valid_inventory_ids=[x for x in ann_inventory if txt(x)]
    if sorted(valid_annotation_ids)!=sorted(valid_inventory_ids):
        add(errors,f"{p} every material evidence annotation must be checked")
        bad=True
    if expected_annotation_inventory_declared and sorted(checked_expected_annotation_ids)!=sorted(expected_annotation_specs):
        add(errors,f"{p} expected evidence annotation inventory must be closed against checks")
        bad=True
    if len(valid_annotation_ids)!=len(set(valid_annotation_ids)): add(errors,f"{p} evidence annotation ids must be unique")

    comp=rec.get("source_surface_completion",{})
    if not isinstance(comp,dict):
        add(errors,f"{p} source_surface_completion must be object")
        comp={}
    if comp.get("all_observed_material_nodes_dispositioned") is not (sorted(check_ids)==sorted(ids)):
        add(errors,f"{p} source_surface_completion.all_observed_material_nodes_dispositioned mismatch")
    annotations_complete=sorted([x for x in annotation_ids if txt(x)])==sorted([x for x in ann_inventory if txt(x)])
    if comp.get("all_material_evidence_annotations_checked") is not annotations_complete:
        add(errors,f"{p} source_surface_completion.all_material_evidence_annotations_checked mismatch")
    if comp.get("topic_plausibility_shortcut_not_used") is not True:
        add(errors,f"{p} topic-plausibility shortcut is forbidden")
    if comp.get("literal_queue_whitelist_shortcut_not_used") is not True:
        add(errors,f"{p} literal queue whitelist cannot be used as an automatic science-failure shortcut")
    if comp.get("mixed_support_nodes_split_when_materially_different") is not True:
        add(errors,f"{p} materially mixed-support clauses must be split before disposition")

    axis=card.get("axes",{}).get("SOURCE_SURFACE") if isinstance(card.get("axes"),dict) else None
    expected="unverifiable" if unv else "fail" if bad else "warning" if warn else "pass"
    if not isinstance(axis,str) or axis not in AXIS_STATUSES:
        add(errors,f"{p} SOURCE_SURFACE status invalid")
    if axis!=expected: add(errors,f"{p} SOURCE_SURFACE must be {expected} from source-surface reconciliation")
    verdict=card.get("verdict")
    if not isinstance(verdict,str) or verdict not in VERDICTS:
        add(errors,f"{p} verdict invalid")
    if verdict=="PASS" and expected!="pass": add(errors,f"{p} PASS illegal with source-surface status {expected}")
    if expected=="warning" and (not isinstance(verdict,str) or verdict not in {"PASS_WITH_WARNINGS","FAIL_RENDER","FAIL_SPEC","BLOCK_UNVERIFIABLE"}): add(errors,f"{p} source-surface warning cannot yield clean PASS")
    if expected=="fail" and (not isinstance(verdict,str) or verdict not in {"FAIL_RENDER","FAIL_SPEC"}): add(errors,f"{p} material source-surface failure requires FAIL_RENDER or FAIL_SPEC")
    if expected=="unverifiable" and verdict!="BLOCK_UNVERIFIABLE": add(errors,f"{p} material source-surface uncertainty requires BLOCK_UNVERIFIABLE")
    return expected

def validate_bundle(bundle:Any):
    errors=[]
    if not isinstance(bundle,dict): return ["bundle must be object"]
    expected_versions={
        "contract_version":RESULT_CONTRACT_VERSION,
        "result_schema_version":RESULT_SCHEMA_VERSION,
        "policy_id":POLICY_ID,
        "policy_version":POLICY_VERSION,
        "method_revision":METHOD,
        "policy_digest":POLICY_DIGEST,
    }
    for field,expected in expected_versions.items():
        if bundle.get(field)!=expected:
            errors.append(f"{field} must be {expected}")
    cards=bundle.get("card_audits")
    if not isinstance(cards,list) or not cards: add(errors,"card_audits must be non-empty"); return errors
    for card in cards: validate_card(card,errors)
    return errors

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("bundle",type=Path); ap.add_argument("--json",action="store_true"); a=ap.parse_args()
    try: bundle=json.loads(a.bundle.read_text(encoding="utf-8")); errors=validate_bundle(bundle)
    except (OSError,json.JSONDecodeError) as ex: errors=[str(ex)]
    out={"status":"pass" if not errors else "fail","method_revision":METHOD,"errors":errors}
    print(json.dumps(out,ensure_ascii=False,sort_keys=True) if a.json else ("PASS" if not errors else "\n".join(errors)))
    return 0 if not errors else 1
if __name__=="__main__": raise SystemExit(main())
