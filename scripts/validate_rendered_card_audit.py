#!/usr/bin/env python3
"""Structural validator for EP_RENDERED_CARD_AUDIT v1.2 / method 1.3."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
from typing import Any

SCRIPT_DIR=Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path: sys.path.insert(0,str(SCRIPT_DIR))
from validate_rendered_card_source_closure import validate_card as validate_source_surface_card, METHOD as SOURCE_METHOD

VERSION="1.0"; METHOD="1.3-materiality-scope-and-role-binding"
assert SOURCE_METHOD==METHOD
SEM=("CONTENT_MEANING","SOURCE_SURFACE","VISUAL_SEMANTICS","CITATION_TRACEABILITY")
FAIL={"FAIL_RENDER","FAIL_SPEC"}; BLOCK=FAIL|{"BLOCK_UNVERIFIABLE"}
EDGE_FAIL={"wrong_source_node","wrong_target_node","wrong_direction","wrong_condition","wrong_relation_type","unsupported_relation"}
REL_FAIL={"omitted_material","distorted"}

def txt(v): return isinstance(v,str) and bool(v.strip())
def sha(v): return txt(v) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def jd(v): return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def file_sha(base,rel):
    if base is None or not txt(rel): return None
    p=Path(rel)
    if p.is_absolute() or ".." in p.parts: return None
    p=(base/p).resolve()
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None

def add(errors,msg): errors.append(msg)

def finding_map(items,prefix,errors):
    if not isinstance(items,list): add(errors,f"{prefix} must be array"); return {}
    out={}
    for i,f in enumerate(items):
        p=f"{prefix}[{i}]"
        if not isinstance(f,dict): add(errors,f"{p} must be object"); continue
        fid=f.get("finding_id")
        if not txt(fid): add(errors,f"{p}.finding_id required")
        elif fid in out: add(errors,f"{prefix} duplicate finding_id {fid}")
        else: out[fid]=f
        m=f.get("materiality")
        if m not in {"non_material","material","blocking_unverifiable"}: add(errors,f"{p}.materiality invalid")
        if m in {"material","blocking_unverifiable"} and not any(txt(x) for x in f.get("source_support",[]) if isinstance(x,str)): add(errors,f"{p} material finding requires source_support")
        rp=f.get("repair_prescription")
        if not isinstance(rp,dict) or not txt(rp.get("instruction")): add(errors,f"{p} repair_prescription required")
    return out

def linked(fid,findings,prefix,errors):
    if not txt(fid) or fid not in findings: add(errors,f"{prefix} requires linked finding"); return
    if findings[fid].get("axis")!="VISUAL_SEMANTICS": add(errors,f"{prefix} finding must be VISUAL_SEMANTICS")

def visual_status(rec,findings,prefix,errors):
    if not isinstance(rec,dict): add(errors,f"{prefix} reconciliation required"); return "unverifiable"
    src=rec.get("source_structure",{}); kind=src.get("source_kind") if isinstance(src,dict) else None
    if not isinstance(src,dict) or src.get("structure_required") is not True: add(errors,f"{prefix} source structure required")
    if kind not in {"body_text","figure","table","mixed"}: add(errors,f"{prefix} source_kind invalid")
    if not any(txt(x) for x in src.get("source_locators",[]) if isinstance(x,str)): add(errors,f"{prefix} source locators required")
    if kind in {"figure","table","mixed"} and src.get("figure_or_table_directly_inspected") is not True: add(errors,f"{prefix} figure/table-derived structure requires direct inspection")
    if src.get("expected_graph_derived") is not True: add(errors,f"{prefix} expected graph must be derived")
    og,eg=rec.get("observed_graph"),rec.get("expected_graph")
    if not isinstance(og,dict) or not isinstance(eg,dict): add(errors,f"{prefix} observed/expected graph required"); return "unverifiable"
    if rec.get("observed_graph_digest")!=jd(og): add(errors,f"{prefix} observed_graph_digest mismatch")
    if rec.get("expected_graph_digest")!=jd(eg): add(errors,f"{prefix} expected_graph_digest mismatch")
    edges=[e.get("edge_id") for e in og.get("edges",[]) if isinstance(e,dict) and e.get("material") is True]
    rels=[r.get("relation_id") for r in eg.get("relations",[]) if isinstance(r,dict) and r.get("material") is True]
    branches=[b.get("branch_id") for b in eg.get("branch_points",[]) if isinstance(b,dict) and b.get("material") is True]
    terms=[t.get("terminal_id") for t in eg.get("terminal_states",[]) if isinstance(t,dict) and t.get("material") is True]
    partitions=[r.get("partition_id") for r in eg.get("role_partitions",[]) if isinstance(r,dict) and r.get("material") is True]
    bad=warn=unv=False
    ec=rec.get("edge_checks",[]); eids=[x.get("edge_id") for x in ec if isinstance(x,dict)] if isinstance(ec,list) else []
    if sorted(eids)!=sorted(edges): add(errors,f"{prefix} every observed material edge must be dispositioned exactly once")
    for x in ec if isinstance(ec,list) else []:
        st=x.get("status")
        if st=="unverifiable": unv=True; linked(x.get("finding_id"),findings,f"{prefix} edge {x.get('edge_id')}",errors)
        elif st in EDGE_FAIL: bad=True; linked(x.get("finding_id"),findings,f"{prefix} edge {x.get('edge_id')}",errors)
        elif st=="warning": warn=True
        elif st not in {"equivalent","non_material_variation"}: add(errors,f"{prefix} edge status invalid")
    rc=rec.get("expected_relation_checks",[]); rids=[x.get("relation_id") for x in rc if isinstance(x,dict)] if isinstance(rc,list) else []
    if sorted(rids)!=sorted(rels): add(errors,f"{prefix} every expected material relation must be covered exactly once")
    for x in rc if isinstance(rc,list) else []:
        st=x.get("status")
        if st=="unverifiable": unv=True; linked(x.get("finding_id"),findings,f"{prefix} relation {x.get('relation_id')}",errors)
        elif st in REL_FAIL: bad=True; linked(x.get("finding_id"),findings,f"{prefix} relation {x.get('relation_id')}",errors)
        elif st=="omitted_non_material": warn=True
        elif st not in {"represented","semantically_equivalent"}: add(errors,f"{prefix} relation status invalid")
    bc=rec.get("branch_point_checks",[]); bids=[x.get("branch_id") for x in bc if isinstance(x,dict)] if isinstance(bc,list) else []
    if sorted(bids)!=sorted(branches): add(errors,f"{prefix} every material branch point must be checked exactly once")
    tc=rec.get("terminal_state_checks",[]); tids=[x.get("terminal_id") for x in tc if isinstance(x,dict)] if isinstance(tc,list) else []
    if sorted(tids)!=sorted(terms): add(errors,f"{prefix} every material terminal state must be checked exactly once")
    for label,items,key in (("branch",bc,"branch_id"),("terminal",tc,"terminal_id")):
        for x in items if isinstance(items,list) else []:
            st=x.get("status")
            if st=="unverifiable": unv=True; linked(x.get("finding_id"),findings,f"{prefix} {label} {x.get(key)}",errors)
            elif st=="fail": bad=True; linked(x.get("finding_id"),findings,f"{prefix} {label} {x.get(key)}",errors)
            elif st=="warning": warn=True
            elif st!="pass": add(errors,f"{prefix} {label} status invalid")
    pc=rec.get("role_partition_checks",[]); pids=[x.get("partition_id") for x in pc if isinstance(x,dict)] if isinstance(pc,list) else []
    if sorted(pids)!=sorted(partitions): add(errors,f"{prefix} every material role partition must be checked exactly once")
    for x in pc if isinstance(pc,list) else []:
        st=x.get("status")
        if st=="unverifiable": unv=True; linked(x.get("finding_id"),findings,f"{prefix} role partition {x.get('partition_id')}",errors)
        elif st in {"collapsed_contrast","wrong_attribution","wrong_grouping"}: bad=True; linked(x.get("finding_id"),findings,f"{prefix} role partition {x.get('partition_id')}",errors)
        elif st=="warning": warn=True
        elif st!="pass": add(errors,f"{prefix} role partition status invalid")
    tv=rec.get("text_visual_consistency",{}); st=tv.get("status") if isinstance(tv,dict) else None
    if st=="unverifiable": unv=True; linked(tv.get("finding_id"),findings,f"{prefix} text/visual failure",errors)
    elif st=="fail": bad=True; linked(tv.get("finding_id"),findings,f"{prefix} text/visual failure",errors)
    elif st=="warning": warn=True
    elif st!="pass": add(errors,f"{prefix} text_visual_consistency invalid")
    comp=rec.get("topology_completion",{})
    required={"all_observed_material_edges_dispositioned":sorted(eids)==sorted(edges),"all_expected_material_relations_covered":sorted(rids)==sorted(rels),"all_material_branch_points_checked":sorted(bids)==sorted(branches),"all_material_terminal_states_checked":sorted(tids)==sorted(terms),"all_material_role_partitions_checked":sorted(pids)==sorted(partitions),"text_visual_consistency_checked":st in {"pass","warning","fail","unverifiable"},"concept_presence_shortcut_not_used":True}
    for k,v in required.items():
        if comp.get(k) is not v: add(errors,f"{prefix} topology_completion.{k} must be {v}")
    if comp.get("concept_presence_shortcut_not_used") is not True: add(errors,f"{prefix} concept-presence shortcut is forbidden")
    return "unverifiable" if unv else "fail" if bad else "warning" if warn else "pass"

def validate_ticket(t,errors):
    if not isinstance(t,dict): add(errors,"repair ticket must be object"); return
    p=f"repair ticket {t.get('ticket_id')}"
    if t.get("verdict") not in FAIL: add(errors,f"{p} verdict invalid")
    if not txt(t.get("card_title")) or not txt(t.get("human_repair_text")): add(errors,f"{p} card_title and human_repair_text required for every failure")
    if not t.get("action_plan"): add(errors,f"{p} action_plan required")
    s=t.get("substantial_change")
    if not isinstance(s,dict): add(errors,f"{p} substantial_change required"); return
    total,changed=s.get("total_semantic_weight"),s.get("changed_semantic_weight")
    if not isinstance(total,(int,float)) or not isinstance(changed,(int,float)) or total<0 or changed<0 or (total and changed>total): add(errors,f"{p} semantic weights invalid"); return
    frac=None if total<=0 else changed/total
    if frac is not None and abs(s.get("estimated_weighted_semantic_fraction",-1)-frac)>1e-9: add(errors,f"{p} fraction must equal changed/total")
    triggered=bool(s.get("structural_triggers")) or (total>=10 and frac is not None and frac>=.10)
    if s.get("triggered") is not triggered: add(errors,f"{p} triggered does not match policy")
    if triggered:
        if s.get("replacement_required") is not True: add(errors,f"{p} substantial repair requires replacement")
        if s.get("replacement_status")=="SUPPORTED":
            rm=s.get("replacement_material")
            if not isinstance(rm,dict) or rm.get("presentation")!="writing_block" or not txt(rm.get("text")): add(errors,f"{p} SUPPORTED replacement requires writing_block text")
        elif s.get("replacement_status")!="BLOCKED_NO_SUPPORTED_MATERIAL": add(errors,f"{p} replacement_status invalid")
    elif s.get("replacement_required") is not False or s.get("replacement_status")!="NOT_REQUIRED" or s.get("replacement_material") is not None: add(errors,f"{p} non-substantial replacement state invalid")

def relation(g,a):
    if not txt(g) or not txt(a) or "unknown" in {g,a}: return "unknown"
    return "same_family" if g==a else "different_family"

def risk_effect(r):
    rel=r.get("relationship"); material=rel in {"same_family","unknown"}; secondary=material and r.get("high_stakes_cardset") is True
    if secondary:
        if r.get("secondary_review_status")=="completed" and r.get("secondary_review_outcome")=="agreement": effect="none"
        elif r.get("secondary_review_status")=="completed" and r.get("secondary_review_outcome")=="disagreement": effect="blocked_unresolved_disagreement"
        else: effect="blocked_pending_secondary_review"
    else: effect="warning_ceiling" if material else "none"
    return material,secondary,effect,{"same_family":"present","unknown":"unknown","different_family":"low"}.get(rel,"unknown")

def cardset_status(b):
    cs=b.get("cardset_audit",{}); fs=cs.get("cross_card_findings",[]); cov=cs.get("package_coverage",{}).get("status","BLOCKED")
    if len(b.get("card_audits",[]))<2 and not fs and cov=="NOT_APPLICABLE": return "NOT_APPLICABLE"
    mats=[x.get("materiality") for x in fs if isinstance(x,dict)]
    if cov=="BLOCKED" or "blocking_unverifiable" in mats: return "BLOCKED"
    if cov=="FAIL" or "material" in mats: return "FAIL"
    if cov=="WARNING" or "non_material" in mats: return "WARNING"
    return "PASS" if cov=="PASS" else "NOT_APPLICABLE"

def release_status(b):
    effect=b.get("methodological_risk",{}).get("release_effect"); vs=[c.get("verdict") for c in b.get("card_audits",[]) if isinstance(c,dict)]; cs=b.get("cardset_audit",{}); pair={cs.get("status"),cs.get("package_coverage",{}).get("status")}
    if effect in {"blocked_pending_secondary_review","blocked_unresolved_disagreement"}: return "BLOCKED"
    if "BLOCK_UNVERIFIABLE" in vs or "BLOCKED" in pair: return "BLOCKED"
    if any(v in FAIL for v in vs) or "FAIL" in pair: return "FAIL"
    if effect=="warning_ceiling" or "PASS_WITH_WARNINGS" in vs or "WARNING" in pair: return "PASS_WITH_WARNINGS"
    return "PASS"

def human_display(b,tickets,errors):
    fails=[c for c in b.get("card_audits",[]) if isinstance(c,dict) and c.get("verdict") in FAIL]; d=b.get("human_repair_display")
    if not fails:
        if d is not None: add(errors,"human_repair_display must be null when no failed cards")
        return
    if not isinstance(d,dict): add(errors,"failed cards require human_repair_display writing block"); return
    if d.get("surface")!="writing_block" or d.get("single_block") is not True: add(errors,"human_repair_display must be one writing_block")
    if d.get("first_line")!="imgedit": add(errors,"human_repair_display first line must be exactly imgedit")
    secs=d.get("sections",[]); expected=[c.get("card_id") for c in fails]; actual=[s.get("card_id") for s in secs if isinstance(s,dict)]
    if actual!=expected: add(errors,"human_repair_display sections must match failed cards in card order")
    for c,s in zip(fails,secs):
        title,tid=c.get("card_title"),c.get("repair_ticket_id"); t=tickets.get(tid,{})
        if s.get("card_title")!=title or s.get("heading")!=f"[{title}]": add(errors,f"human repair section {c.get('card_id')} heading must be exact [card title]")
        if s.get("ticket_id")!=tid or s.get("content")!=t.get("human_repair_text"): add(errors,f"human repair section {c.get('card_id')} ticket/content mismatch")
    expected_text="imgedit"+"".join(f"\n[{s['card_title']}]\n{s['content']}" for s in secs if isinstance(s,dict))
    if d.get("rendered_text")!=expected_text: add(errors,"human_repair_display.rendered_text format mismatch")

def validate_bundle(b:Any,*,base_dir:Path|None=None):
    e=[]
    if not isinstance(b,dict): return ["bundle must be object"]
    if b.get("contract_version")!=VERSION: add(e,"contract_version must be 1.0")
    if b.get("method_revision")!=METHOD: add(e,f"method_revision must be {METHOD}")
    if not isinstance(b.get("source_bindings"),list) or not b.get("source_bindings"): add(e,"source_bindings must be non-empty")
    raw=b.get("repair_tickets",[]); tickets={}
    if not isinstance(raw,list): add(e,"repair_tickets must be array"); raw=[]
    for t in raw:
        validate_ticket(t,e)
        if isinstance(t,dict) and txt(t.get("ticket_id")): tickets[t["ticket_id"]]=t
    cards=b.get("card_audits",[])
    if not isinstance(cards,list) or not cards: add(e,"card_audits must be non-empty"); cards=[]
    ids=[]
    for c in cards:
        if not isinstance(c,dict): add(e,"card audit must be object"); continue
        cid=c.get("card_id"); ids.append(cid); p=f"card {cid}"
        if not txt(c.get("card_title")): add(e,f"{p} card_title required")
        if file_sha(base_dir,c.get("image_path"))!=c.get("image_sha256"): add(e,f"{p} image hash mismatch")
        br=c.get("blind_readback",{})
        if br.get("frozen_before_comparison") is not True or not sha(br.get("digest")) or not sha(br.get("visual_graph_digest")): add(e,f"{p} blind readback not frozen/bound")
        if not sha(c.get("expected_semantic_packet_digest")): add(e,f"{p} expected semantic digest invalid")
        fm=finding_map(c.get("findings"),f"{p}.findings",e); expected=visual_status(c.get("visual_semantic_reconciliation"),fm,p,e)
        source_expected=validate_source_surface_card(c,e)
        ssr=c.get("source_surface_reconciliation",{})
        if isinstance(ssr,dict):
            for group in (ssr.get("content_node_checks",[]),ssr.get("evidence_annotation_checks",[])):
                for item in group if isinstance(group,list) else []:
                    if not isinstance(item,dict): continue
                    fid=item.get("finding_id")
                    if txt(fid):
                        if fid not in fm: add(e,f"{p} source-surface finding {fid} must link to card finding")
                        elif fm[fid].get("axis")!="SOURCE_SURFACE": add(e,f"{p} source-surface finding {fid} must use SOURCE_SURFACE axis")
        rec=c.get("visual_semantic_reconciliation",{})
        if isinstance(rec,dict) and br.get("visual_graph_digest")!=rec.get("observed_graph_digest"): add(e,f"{p} frozen blind graph digest mismatch")
        axes=c.get("axes",{})
        if any(x not in axes for x in SEM+("ENGINEERING_CONFORMANCE",)): add(e,f"{p} axes incomplete")
        else:
            if axes.get("VISUAL_SEMANTICS")!=expected: add(e,f"{p} VISUAL_SEMANTICS must be {expected} from topology reconciliation")
            if source_expected is not None and axes.get("SOURCE_SURFACE")!=source_expected: add(e,f"{p} SOURCE_SURFACE must be {source_expected} from source-surface reconciliation")
        v=c.get("verdict")
        if c.get("release_blocking") is not (v in BLOCK): add(e,f"{p} release_blocking mismatch")
        if v=="FAIL_SPEC" and c.get("failure_origin") not in {"FINAL_CARD_SPEC","TRUTH_BOUNDARY","SOURCE_BINDING","MIXED"}: add(e,f"{p} FAIL_SPEC requires failure_origin")
        if v!="FAIL_SPEC" and c.get("failure_origin") is not None: add(e,f"{p} failure_origin only for FAIL_SPEC")
        tid=c.get("repair_ticket_id")
        if v in FAIL and tid not in tickets: add(e,f"{p} fail requires repair ticket")
        if v not in FAIL and tid is not None: add(e,f"{p} non-fail cannot have repair ticket")
        vals=[axes.get(x) for x in SEM]; eng=axes.get("ENGINEERING_CONFORMANCE")
        if v=="PASS" and (any(x!="pass" for x in vals) or eng!="pass"): add(e,f"{p} PASS axes mismatch")
        if v=="PASS_WITH_WARNINGS" and any(x in {"fail","unverifiable"} for x in vals): add(e,f"{p} warning verdict contains failed/unverifiable axis")
        if v=="BLOCK_UNVERIFIABLE" and not any(x=="unverifiable" for x in vals): add(e,f"{p} block requires unverifiable axis")
        if v in FAIL and not any(isinstance(f,dict) and f.get("materiality")=="material" and f.get("axis")!="ENGINEERING_CONFORMANCE" for f in c.get("findings",[])): add(e,f"{p} fail requires substantive material finding")
    if len(ids)!=len(set(ids)): add(e,"card ids must be unique")
    dd=b.get("dedup_manifest",{}); dups=dd.get("duplicates",[]) if isinstance(dd,dict) else []
    if dd.get("unique_card_count")!=len(cards) or dd.get("duplicate_count")!=len(dups): add(e,"dedup counts mismatch")
    cs=b.get("cardset_audit",{}); finding_map(cs.get("cross_card_findings"),"cardset findings",e); cexp=cardset_status(b)
    if cs.get("scope")!="cross_card_and_package_only" or cs.get("status")!=cexp: add(e,f"cardset status must be {cexp}")
    r=b.get("methodological_risk",{}); rel=relation(r.get("generator_model_family"),r.get("auditor_model_family"))
    if r.get("relationship")!=rel: add(e,f"methodological relationship must be {rel}")
    material,secondary,effect,corr=risk_effect(r)
    if r.get("material_to_run") is not material or r.get("secondary_review_required") is not secondary or r.get("release_effect")!=effect or r.get("correlated_error_risk")!=corr: add(e,"methodological-risk derivation mismatch")
    if r.get("high_stakes_cardset") is True and not r.get("high_stakes_reasons"): add(e,"high-stakes run requires reasons")
    rg=b.get("release_gate",{}); rexp=release_status(b)
    if rg.get("status")!=rexp or rg.get("release_allowed") is not (rexp in {"PASS","PASS_WITH_WARNINGS"}): add(e,f"release gate must be {rexp}")
    counts=rg.get("counts",{})
    for v in ("PASS","PASS_WITH_WARNINGS","FAIL_RENDER","FAIL_SPEC","BLOCK_UNVERIFIABLE"):
        if counts.get(v)!=sum(1 for c in cards if isinstance(c,dict) and c.get("verdict")==v): add(e,f"release count {v} mismatch")
    human_display(b,tickets,e)
    p=b.get("provenance",{})
    if p.get("auditor_role")!="post_render_auditor" or p.get("mutated_upstream_artifacts") is not False or p.get("generation_calls_made")!=0: add(e,"RCA read-only provenance violated")
    return e

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("bundle",type=Path); ap.add_argument("--json",action="store_true"); a=ap.parse_args()
    try: b=json.loads(a.bundle.read_text(encoding="utf-8")); errors=validate_bundle(b,base_dir=a.bundle.resolve().parent)
    except (OSError,json.JSONDecodeError) as ex: b={}; errors=[str(ex)]
    out={"status":"pass" if not errors else "fail","contract_version":b.get("contract_version"),"method_revision":METHOD,"errors":errors}
    print(json.dumps(out,ensure_ascii=False,sort_keys=True) if a.json else ("PASS" if not errors else "\n".join(errors)))
    return 0 if not errors else 1
if __name__=="__main__": raise SystemExit(main())
