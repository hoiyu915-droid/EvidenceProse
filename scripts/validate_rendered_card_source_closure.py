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
import argparse, json
from pathlib import Path
from typing import Any

METHOD="1.3-materiality-scope-and-role-binding"
PASS_DISPOSITIONS={
    "AUTHORIZED_AND_SUPPORTED",
    "SEMANTICALLY_EQUIVALENT_PARAPHRASE",
    "SOURCE_SUPPORTED_NONEXPANSIVE_ELABORATION",
}
FAIL_DISPOSITIONS={
    "SOURCE_SUPPORTED_BUT_OUT_OF_CARD_SCOPE",
    "UNAUTHORIZED_AND_UNSUPPORTED",
    "MATERIAL_QUEUE_PROTECTIVE_LOCK_VIOLATION",
}
BLOCK_DISPOSITIONS={"AUTHORIZED_BUT_SOURCE_UNVERIFIABLE"}
LEGACY_DISPOSITIONS={"SOURCE_SUPPORTED_BUT_NOT_QUEUE_AUTHORIZED"}
ALLOWED=PASS_DISPOSITIONS|FAIL_DISPOSITIONS|BLOCK_DISPOSITIONS|LEGACY_DISPOSITIONS|{"NON_MATERIAL_DECORATION"}
ANNOTATION_PASS={"equivalent"}
ANNOTATION_WARN={"duplicate_nonmaterial"}
ANNOTATION_FAIL={"wrong_role","wrong_binding","unsupported_annotation"}
ANNOTATION_ALLOWED=ANNOTATION_PASS|ANNOTATION_WARN|ANNOTATION_FAIL|{"unverifiable"}
EXPANSION_KEYS=(
    "adds_new_claim",
    "adds_new_category_or_closed_set_member",
    "adds_new_number",
    "adds_new_population_or_scope",
    "adds_new_mechanism",
    "adds_new_causal_or_directional_relation",
    "changes_attribution",
    "changes_evidence_role",
    "imports_sibling_specific_claim",
)

def txt(v): return isinstance(v,str) and bool(v.strip())
def add(errors,msg): errors.append(msg)

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
    material=[n for n in inventory if isinstance(n,dict) and n.get("material") is True]
    ids=[n.get("observed_node_id") for n in material]
    if any(not txt(x) for x in ids): add(errors,f"{p} every material observed content node requires observed_node_id")
    if len(ids)!=len(set(ids)): add(errors,f"{p} material observed content node ids must be unique")

    rec=card.get("source_surface_reconciliation")
    if not isinstance(rec,dict): add(errors,f"{p} source_surface_reconciliation required"); return
    checks=rec.get("content_node_checks")
    if not isinstance(checks,list): add(errors,f"{p} content_node_checks must be array"); return
    check_ids=[x.get("observed_node_id") for x in checks if isinstance(x,dict)]
    if sorted(check_ids)!=sorted(ids): add(errors,f"{p} every observed material content node must be dispositioned exactly once")

    bad=unv=warn=False
    for i,x in enumerate(checks):
        q=f"{p}.content_node_checks[{i}]"
        if not isinstance(x,dict): add(errors,f"{q} must be object"); continue
        disp=x.get("disposition")
        if disp not in ALLOWED: add(errors,f"{q} disposition invalid"); continue
        if x.get("materiality")!="material": add(errors,f"{q} material node check must declare materiality=material")
        qa=x.get("queue_authorization_status")
        ss=x.get("primary_source_support_status")
        if qa not in {"authorized","not_authorized","unverifiable"}: add(errors,f"{q} queue_authorization_status invalid")
        if ss not in {"supported","not_supported","unverifiable"}: add(errors,f"{q} primary_source_support_status invalid")
        loc=x.get("source_locators",[])
        if not isinstance(loc,list): add(errors,f"{q} source_locators must be array"); loc=[]
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
        elif disp=="NON_MATERIAL_DECORATION":
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
            if x.get("card_scope_status") not in {"sibling_specific","outside_current_card_function"}: add(errors,f"{q} out-of-card-scope requires explicit card_scope_status")
        if disp=="MATERIAL_QUEUE_PROTECTIVE_LOCK_VIOLATION":
            if x.get("queue_protective_lock_material") is not True or not txt(x.get("protective_purpose")):
                add(errors,f"{q} protective-lock failure requires material protective purpose")

    exp=rec.get("expected_content_checks",[])
    if not isinstance(exp,list): add(errors,f"{p} expected_content_checks must be array"); exp=[]
    for i,x in enumerate(exp):
        if not isinstance(x,dict): add(errors,f"{p}.expected_content_checks[{i}] must be object"); continue
        if x.get("closed_set_member") is True and x.get("status") not in {"represented","semantically_equivalent"}:
            bad=True
            if not txt(x.get("finding_id")): add(errors,f"{p}.expected_content_checks[{i}] failed closed-set member requires finding_id")

    annotations=rec.get("evidence_annotation_checks",[])
    if not isinstance(annotations,list): add(errors,f"{p} evidence_annotation_checks must be array"); annotations=[]
    annotation_ids=[]
    for i,x in enumerate(annotations):
        q=f"{p}.evidence_annotation_checks[{i}]"
        if not isinstance(x,dict): add(errors,f"{q} must be object"); continue
        aid=x.get("annotation_id"); annotation_ids.append(aid)
        if not txt(aid): add(errors,f"{q} annotation_id required")
        st=x.get("status")
        if st not in ANNOTATION_ALLOWED: add(errors,f"{q} status invalid"); continue
        if st in ANNOTATION_FAIL:
            bad=True
            if not txt(x.get("finding_id")): add(errors,f"{q} failing annotation requires finding_id")
        elif st=="unverifiable":
            unv=True
            if not txt(x.get("finding_id")): add(errors,f"{q} unverifiable annotation requires finding_id")
        elif st in ANNOTATION_WARN:
            warn=True
        if st in {"equivalent","wrong_role","wrong_binding"}:
            if x.get("observed_role") not in {"CORE","INFERENCE","GAP","CONFLICT"}: add(errors,f"{q} observed_role invalid")
            if x.get("expected_role") not in {"CORE","INFERENCE","GAP","CONFLICT"}: add(errors,f"{q} expected_role invalid")
        if st in {"equivalent","wrong_binding"}:
            bound=x.get("bound_observed_node_ids")
            if not isinstance(bound,list) or not bound or any(not txt(v) for v in bound): add(errors,f"{q} bound_observed_node_ids required")
    if len(annotation_ids)!=len(set(annotation_ids)): add(errors,f"{p} evidence annotation ids must be unique")

    comp=rec.get("source_surface_completion",{})
    if comp.get("all_observed_material_nodes_dispositioned") is not (sorted(check_ids)==sorted(ids)):
        add(errors,f"{p} source_surface_completion.all_observed_material_nodes_dispositioned mismatch")
    if comp.get("all_material_evidence_annotations_checked") is not True:
        add(errors,f"{p} source_surface_completion.all_material_evidence_annotations_checked must be true")
    if comp.get("topic_plausibility_shortcut_not_used") is not True:
        add(errors,f"{p} topic-plausibility shortcut is forbidden")
    if comp.get("literal_queue_whitelist_shortcut_not_used") is not True:
        add(errors,f"{p} literal queue whitelist cannot be used as an automatic science-failure shortcut")
    if comp.get("mixed_support_nodes_split_when_materially_different") is not True:
        add(errors,f"{p} materially mixed-support clauses must be split before disposition")

    axis=card.get("axes",{}).get("SOURCE_SURFACE") if isinstance(card.get("axes"),dict) else None
    expected="unverifiable" if unv else "fail" if bad else "warning" if warn else "pass"
    if axis!=expected: add(errors,f"{p} SOURCE_SURFACE must be {expected} from source-surface reconciliation")
    verdict=card.get("verdict")
    if verdict=="PASS" and expected!="pass": add(errors,f"{p} PASS illegal with source-surface status {expected}")
    if expected=="warning" and verdict not in {"PASS_WITH_WARNINGS","FAIL_RENDER","FAIL_SPEC","BLOCK_UNVERIFIABLE"}: add(errors,f"{p} source-surface warning cannot yield clean PASS")
    if expected=="fail" and verdict not in {"FAIL_RENDER","FAIL_SPEC"}: add(errors,f"{p} material source-surface failure requires FAIL_RENDER or FAIL_SPEC")
    if expected=="unverifiable" and verdict!="BLOCK_UNVERIFIABLE": add(errors,f"{p} material source-surface uncertainty requires BLOCK_UNVERIFIABLE")
    return expected

def validate_bundle(bundle:Any):
    errors=[]
    if not isinstance(bundle,dict): return ["bundle must be object"]
    if bundle.get("method_revision")!=METHOD: add(errors,f"method_revision must be {METHOD}")
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
