#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
METHOD="1.3-semantic-surface-and-role-closure"
PASS={"AUTHORIZED_AND_SUPPORTED","SEMANTICALLY_EQUIVALENT_PARAPHRASE","SOURCE_SUPPORTED_EXPLANATORY_EXPANSION"}
FAIL={"SOURCE_SUPPORTED_BUT_NOT_QUEUE_AUTHORIZED","UNAUTHORIZED_AND_UNSUPPORTED"}
BLOCK={"AUTHORIZED_BUT_SOURCE_UNVERIFIABLE"}
ALLOWED=PASS|FAIL|BLOCK|{"NON_MATERIAL_DECORATION"}
EXPLAIN={"explanatory_microcopy","definition","descriptive_label"}
NO_EXPAND={"category","example","population","context","outcome","intervention","mechanism","number","citation","evidence_role_marker","source_defined_list_member"}
ROLE_FAIL={"duplicated_wrong_role","omitted_material","distorted","wrong_role_assignment"}
ER_FAIL={"unauthorized_role","drifted_role","missing_material","wrong_role_assignment"}
def txt(v): return isinstance(v,str) and bool(v.strip())
def add(e,m): e.append(m)
def validate_card(c:Any,e:list[str]):
    if not isinstance(c,dict): add(e,"card audit must be object"); return
    cid=c.get("card_id","?"); p=f"card {cid}"; br=c.get("blind_readback",{})
    inv=br.get("content_node_inventory") if isinstance(br,dict) else None
    if not isinstance(inv,list): add(e,f"{p} blind_readback.content_node_inventory must be array"); return
    material=[n for n in inv if isinstance(n,dict) and n.get("material") is True]; ids=[n.get("observed_node_id") for n in material]
    if any(not txt(x) for x in ids): add(e,f"{p} every material observed content node requires observed_node_id")
    if len(ids)!=len(set(ids)): add(e,f"{p} material observed content node ids must be unique")
    rec=c.get("source_surface_reconciliation")
    if not isinstance(rec,dict): add(e,f"{p} source_surface_reconciliation required"); return
    checks=rec.get("content_node_checks")
    if not isinstance(checks,list): add(e,f"{p} content_node_checks must be array"); return
    got=[x.get("observed_node_id") for x in checks if isinstance(x,dict)]
    if sorted(got)!=sorted(ids): add(e,f"{p} every observed material content node must be dispositioned exactly once")
    bad=unv=False
    for i,x in enumerate(checks):
        q=f"{p}.content_node_checks[{i}]"
        if not isinstance(x,dict): add(e,f"{q} must be object"); continue
        d=x.get("disposition"); t=x.get("node_type"); qa=x.get("queue_authorization_status"); ss=x.get("primary_source_support_status")
        if d not in ALLOWED: add(e,f"{q} disposition invalid"); continue
        if x.get("materiality")!="material": add(e,f"{q} materiality=material required")
        if not txt(t): add(e,f"{q} node_type required")
        if qa not in {"authorized","not_authorized","unverifiable"}: add(e,f"{q} queue_authorization_status invalid")
        if ss not in {"supported","not_supported","unverifiable"}: add(e,f"{q} primary_source_support_status invalid")
        loc=x.get("source_locators",[])
        if ss=="supported" and not any(txt(v) for v in loc if isinstance(v,str)): add(e,f"{q} supported node requires source locator")
        if d in FAIL: bad=True; add(e,f"{q} failing disposition requires finding_id") if not txt(x.get("finding_id")) else None
        elif d in BLOCK: unv=True; add(e,f"{q} unverifiable disposition requires finding_id") if not txt(x.get("finding_id")) else None
        elif d=="NON_MATERIAL_DECORATION": add(e,f"{q} material node cannot be NON_MATERIAL_DECORATION")
        elif d=="AUTHORIZED_AND_SUPPORTED" and not (qa=="authorized" and ss=="supported"): add(e,f"{q} AUTHORIZED_AND_SUPPORTED requires authorized + supported")
        elif d=="SEMANTICALLY_EQUIVALENT_PARAPHRASE" and ss!="supported": add(e,f"{q} paraphrase requires primary-source support")
        elif d=="SOURCE_SUPPORTED_EXPLANATORY_EXPANSION":
            safe=ss=="supported" and t in EXPLAIN and t not in NO_EXPAND and x.get("semantic_novelty") in {"restatement","explanatory_decomposition"} and x.get("introduces_new_substantive_claim") is False and x.get("changes_scope") is False and x.get("changes_evidence_role") is False and x.get("changes_topology") is False
            if not safe: add(e,f"{q} explanatory expansion is not safely bounded")
    for i,x in enumerate(rec.get("expected_content_checks",[])):
        if isinstance(x,dict) and x.get("closed_set_member") is True and x.get("status") not in {"represented","semantically_equivalent"}: bad=True; add(e,f"{p}.expected_content_checks[{i}] failed closed-set member requires finding_id") if not txt(x.get("finding_id")) else None
    for key,fails in (("expected_role_checks",ROLE_FAIL),("evidence_role_checks",ER_FAIL)):
        arr=rec.get(key,[])
        if not isinstance(arr,list): add(e,f"{p} {key} must be array"); arr=[]
        ok={"represented","semantically_equivalent","non_material_warning"} if key=="expected_role_checks" else {"authorized","semantically_equivalent","non_material_warning"}
        for i,x in enumerate(arr):
            if not isinstance(x,dict): add(e,f"{p}.{key}[{i}] must be object"); continue
            st=x.get("status")
            if st in fails: bad=True; add(e,f"{p}.{key}[{i}] failing check requires finding_id") if not txt(x.get("finding_id")) else None
            elif st not in ok: add(e,f"{p}.{key}[{i}] status invalid")
    comp=rec.get("source_surface_completion",{})
    if comp.get("all_observed_material_nodes_dispositioned") is not (sorted(got)==sorted(ids)): add(e,f"{p} all_observed_material_nodes_dispositioned mismatch")
    for k,msg in (("all_expected_semantic_roles_checked","all expected semantic roles must be checked"),("all_evidence_role_markers_checked","all evidence-role markers must be checked"),("topic_plausibility_shortcut_not_used","topic-plausibility shortcut is forbidden"),("visible_text_whitelist_shortcut_not_used","visible_text whitelist shortcut is forbidden")):
        if comp.get(k) is not True: add(e,f"{p} {msg}")
    expected="unverifiable" if unv else "fail" if bad else "pass"; axis=c.get("axes",{}).get("SOURCE_SURFACE") if isinstance(c.get("axes"),dict) else None
    if axis!=expected: add(e,f"{p} SOURCE_SURFACE must be {expected} from reconciliation")
    v=c.get("verdict")
    if v=="PASS" and expected!="pass": add(e,f"{p} PASS illegal with SOURCE_SURFACE {expected}")
    if expected=="fail" and v not in {"FAIL_RENDER","FAIL_SPEC"}: add(e,f"{p} source-surface failure requires FAIL_RENDER or FAIL_SPEC")
    if expected=="unverifiable" and v!="BLOCK_UNVERIFIABLE": add(e,f"{p} uncertainty requires BLOCK_UNVERIFIABLE")
def validate_bundle(b:Any):
    e=[]
    if not isinstance(b,dict): return ["bundle must be object"]
    if b.get("method_revision")!=METHOD: add(e,f"method_revision must be {METHOD}")
    cards=b.get("card_audits")
    if not isinstance(cards,list) or not cards: add(e,"card_audits must be non-empty"); return e
    for c in cards: validate_card(c,e)
    return e
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("bundle",type=Path); ap.add_argument("--json",action="store_true"); a=ap.parse_args()
    try: e=validate_bundle(json.loads(a.bundle.read_text(encoding="utf-8")))
    except (OSError,json.JSONDecodeError) as ex: e=[str(ex)]
    out={"status":"pass" if not e else "fail","method_revision":METHOD,"errors":e}; print(json.dumps(out,ensure_ascii=False,sort_keys=True) if a.json else ("PASS" if not e else "\n".join(e))); return 0 if not e else 1
if __name__=="__main__": raise SystemExit(main())
