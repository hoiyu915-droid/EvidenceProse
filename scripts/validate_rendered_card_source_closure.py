#!/usr/bin/env python3
"""Validate RCA v1.1 source-surface node closure.

This validator does not infer pixels or scientific truth. It checks that an auditor
has explicitly dispositioned every declared material observed content node and
that a PASS is structurally impossible when a material node is unsupported,
unverifiable, or omitted from closure.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

PASS_DISPOSITIONS={"AUTHORIZED_AND_SUPPORTED","SEMANTICALLY_EQUIVALENT_PARAPHRASE"}
FAIL_DISPOSITIONS={"SOURCE_SUPPORTED_BUT_NOT_QUEUE_AUTHORIZED","UNAUTHORIZED_AND_UNSUPPORTED"}
BLOCK_DISPOSITIONS={"AUTHORIZED_BUT_SOURCE_UNVERIFIABLE"}
ALLOWED=PASS_DISPOSITIONS|FAIL_DISPOSITIONS|BLOCK_DISPOSITIONS|{"NON_MATERIAL_DECORATION"}

def txt(v): return isinstance(v,str) and bool(v.strip())
def add(errors,msg): errors.append(msg)

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

    bad=unv=False
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
        if ss=="supported" and not any(txt(v) for v in loc if isinstance(v,str)): add(errors,f"{q} supported node requires source locator")
        if disp in FAIL_DISPOSITIONS:
            bad=True
            if not txt(x.get("finding_id")): add(errors,f"{q} failing disposition requires finding_id")
        elif disp in BLOCK_DISPOSITIONS:
            unv=True
            if not txt(x.get("finding_id")): add(errors,f"{q} unverifiable disposition requires finding_id")
        elif disp=="NON_MATERIAL_DECORATION":
            add(errors,f"{q} material node cannot be NON_MATERIAL_DECORATION")
        elif disp=="AUTHORIZED_AND_SUPPORTED" and not (qa=="authorized" and ss=="supported"):
            add(errors,f"{q} AUTHORIZED_AND_SUPPORTED requires authorized + supported")
        elif disp=="SEMANTICALLY_EQUIVALENT_PARAPHRASE" and ss!="supported":
            add(errors,f"{q} paraphrase requires primary-source support")

    exp=rec.get("expected_content_checks",[])
    if not isinstance(exp,list): add(errors,f"{p} expected_content_checks must be array"); exp=[]
    for i,x in enumerate(exp):
        if not isinstance(x,dict): add(errors,f"{p}.expected_content_checks[{i}] must be object"); continue
        if x.get("closed_set_member") is True and x.get("status") not in {"represented","semantically_equivalent"}:
            bad=True
            if not txt(x.get("finding_id")): add(errors,f"{p}.expected_content_checks[{i}] failed closed-set member requires finding_id")

    comp=rec.get("source_surface_completion",{})
    if comp.get("all_observed_material_nodes_dispositioned") is not (sorted(check_ids)==sorted(ids)):
        add(errors,f"{p} source_surface_completion.all_observed_material_nodes_dispositioned mismatch")
    if comp.get("topic_plausibility_shortcut_not_used") is not True:
        add(errors,f"{p} topic-plausibility shortcut is forbidden")

    axis=card.get("axes",{}).get("SOURCE_SURFACE") if isinstance(card.get("axes"),dict) else None
    expected="unverifiable" if unv else "fail" if bad else "pass"
    if axis!=expected: add(errors,f"{p} SOURCE_SURFACE must be {expected} from source-surface reconciliation")
    verdict=card.get("verdict")
    if verdict=="PASS" and expected!="pass": add(errors,f"{p} PASS illegal with source-surface status {expected}")
    if expected=="fail" and verdict not in {"FAIL_RENDER","FAIL_SPEC"}: add(errors,f"{p} material source-surface failure requires FAIL_RENDER or FAIL_SPEC")
    if expected=="unverifiable" and verdict!="BLOCK_UNVERIFIABLE": add(errors,f"{p} material source-surface uncertainty requires BLOCK_UNVERIFIABLE")

def validate_bundle(bundle:Any):
    errors=[]
    if not isinstance(bundle,dict): return ["bundle must be object"]
    if bundle.get("method_revision")!="1.2-topology-and-source-closure": add(errors,"method_revision must be 1.2-topology-and-source-closure")
    cards=bundle.get("card_audits")
    if not isinstance(cards,list) or not cards: add(errors,"card_audits must be non-empty"); return errors
    for card in cards: validate_card(card,errors)
    return errors

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("bundle",type=Path); ap.add_argument("--json",action="store_true"); a=ap.parse_args()
    try: bundle=json.loads(a.bundle.read_text(encoding="utf-8")); errors=validate_bundle(bundle)
    except (OSError,json.JSONDecodeError) as ex: errors=[str(ex)]
    out={"status":"pass" if not errors else "fail","method_revision":"1.2-topology-and-source-closure","errors":errors}
    print(json.dumps(out,ensure_ascii=False,sort_keys=True) if a.json else ("PASS" if not errors else "\n".join(errors)))
    return 0 if not errors else 1
if __name__=="__main__": raise SystemExit(main())
