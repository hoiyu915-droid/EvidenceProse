#!/usr/bin/env python3
"""Validate EP_RENDERED_CARD_AUDIT v1.0 result bundles.

Structural validator only: it checks hashes, dedup closure, verdict/repair
closure, substantial-repair replacement rules, cardset aggregation and
correlated-model-risk consequences. It does not redo source or image semantics.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
from typing import Any

VERSION = "1.0"
SEM = ("CONTENT_MEANING","SOURCE_SURFACE","VISUAL_SEMANTICS","CITATION_TRACEABILITY")
FAIL = {"FAIL_RENDER","FAIL_SPEC"}
BLOCK = FAIL | {"BLOCK_UNVERIFIABLE"}

def text(v): return isinstance(v,str) and bool(v.strip())
def sha(v): return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)

def file_digest(base, rel):
    if base is None or not text(rel):
        return None, "unsafe"
    p=Path(rel)
    if p.is_absolute() or ".." in p.parts: return None, "unsafe"
    p=(base/p).resolve()
    if not p.is_file(): return None, "missing"
    return hashlib.sha256(p.read_bytes()).hexdigest(), None

def relationship(g,a):
    if not text(g) or not text(a) or g=="unknown" or a=="unknown": return "unknown"
    return "same_family" if g==a else "different_family"

def risk_expected(r):
    rel=r.get("relationship")
    material=rel in {"same_family","unknown"}
    secondary=material and r.get("high_stakes_cardset") is True
    if secondary:
        if r.get("secondary_review_status")=="completed" and r.get("secondary_review_outcome")=="agreement":
            effect="none"
        elif r.get("secondary_review_status")=="completed" and r.get("secondary_review_outcome")=="disagreement":
            effect="blocked_unresolved_disagreement"
        else:
            effect="blocked_pending_secondary_review"
    else:
        effect="warning_ceiling" if material else "none"
    corr={"same_family":"present","unknown":"unknown","different_family":"low"}.get(rel,"unknown")
    return material,secondary,effect,corr

def cardset_expected(bundle):
    cs=bundle.get("cardset_audit",{})
    findings=cs.get("cross_card_findings",[])
    cov=cs.get("package_coverage",{}).get("status","BLOCKED")
    if len(bundle.get("card_audits",[]))<2 and not findings and cov=="NOT_APPLICABLE": return "NOT_APPLICABLE"
    mats=[f.get("materiality") for f in findings if isinstance(f,dict)]
    if cov=="BLOCKED" or "blocking_unverifiable" in mats: return "BLOCKED"
    if cov=="FAIL" or "material" in mats: return "FAIL"
    if cov=="WARNING" or "non_material" in mats: return "WARNING"
    return "PASS" if cov=="PASS" else "NOT_APPLICABLE"

def release_expected(bundle):
    effect=bundle.get("methodological_risk",{}).get("release_effect")
    verdicts=[c.get("verdict") for c in bundle.get("card_audits",[]) if isinstance(c,dict)]
    cs=bundle.get("cardset_audit",{})
    cstat=cs.get("status","BLOCKED"); cov=cs.get("package_coverage",{}).get("status","BLOCKED")
    if effect in {"blocked_pending_secondary_review","blocked_unresolved_disagreement"}: return "BLOCKED"
    if "BLOCK_UNVERIFIABLE" in verdicts or "BLOCKED" in {cstat,cov}: return "BLOCKED"
    if any(v in FAIL for v in verdicts) or "FAIL" in {cstat,cov}: return "FAIL"
    if effect=="warning_ceiling" or "PASS_WITH_WARNINGS" in verdicts or "WARNING" in {cstat,cov}: return "PASS_WITH_WARNINGS"
    return "PASS"

def findings_ok(items, prefix, errors):
    if not isinstance(items,list): errors.append(f"{prefix} must be an array"); return
    for i,f in enumerate(items):
        p=f"{prefix}[{i}]"
        if not isinstance(f,dict): errors.append(f"{p} must be object"); continue
        m=f.get("materiality")
        if m not in {"non_material","material","blocking_unverifiable"}: errors.append(f"{p}.materiality invalid")
        if m in {"material","blocking_unverifiable"} and not any(text(x) for x in f.get("source_support",[]) if isinstance(x,str)):
            errors.append(f"{p} material finding requires source_support")
        rp=f.get("repair_prescription")
        if not isinstance(rp,dict) or not text(rp.get("instruction")): errors.append(f"{p} requires repair_prescription")

def validate_ticket(t, errors):
    tid=t.get("ticket_id") if isinstance(t,dict) else "?"
    p=f"repair ticket {tid}"
    if not isinstance(t,dict): errors.append("repair ticket must be object"); return
    if t.get("verdict") not in FAIL: errors.append(f"{p} verdict invalid")
    if not t.get("action_plan"): errors.append(f"{p} action_plan required")
    s=t.get("substantial_change")
    if not isinstance(s,dict): errors.append(f"{p} substantial_change required"); return
    total=s.get("total_semantic_weight"); changed=s.get("changed_semantic_weight")
    if not isinstance(total,(int,float)) or not isinstance(changed,(int,float)) or total<0 or changed<0 or (total and changed>total):
        errors.append(f"{p} semantic weights invalid"); return
    fraction=None if total<=0 else changed/total
    if fraction is not None and abs(s.get("estimated_weighted_semantic_fraction",-1)-fraction)>1e-9:
        errors.append(f"{p} fraction must equal changed/total")
    trigger=bool(s.get("structural_triggers")) or (total>=10 and fraction is not None and fraction>=.10)
    if s.get("triggered") is not trigger: errors.append(f"{p} triggered does not match policy")
    if trigger:
        if s.get("replacement_required") is not True: errors.append(f"{p} substantial repair requires replacement")
        if s.get("replacement_status")=="SUPPORTED":
            rm=s.get("replacement_material")
            if not isinstance(rm,dict) or rm.get("presentation")!="writing_block" or not text(rm.get("text")):
                errors.append(f"{p} SUPPORTED replacement requires writing_block text")
        elif s.get("replacement_status")!="BLOCKED_NO_SUPPORTED_MATERIAL":
            errors.append(f"{p} replacement_status invalid")
    elif s.get("replacement_required") is not False or s.get("replacement_status")!="NOT_REQUIRED" or s.get("replacement_material") is not None:
        errors.append(f"{p} non-substantial replacement state invalid")

def validate_bundle(bundle:Any, *, base_dir:Path|None=None):
    errors=[]
    if not isinstance(bundle,dict): return ["bundle must be object"]
    if bundle.get("contract_version")!=VERSION: errors.append("contract_version must be 1.0")
    sources=bundle.get("source_bindings")
    if not isinstance(sources,list) or not sources: errors.append("source_bindings must be non-empty")
    else:
        ids=[]
        for s in sources:
            if not isinstance(s,dict): errors.append("source binding must be object"); continue
            ids.append(s.get("source_id"))
            if s.get("status")=="verified" and not sha(s.get("source_digest")): errors.append(f"source {s.get('source_id')} verified digest invalid")
        if len(ids)!=len(set(ids)): errors.append("source ids must be unique")

    raw_t=bundle.get("repair_tickets")
    if not isinstance(raw_t,list): errors.append("repair_tickets must be array"); raw_t=[]
    tickets={}
    for t in raw_t:
        validate_ticket(t,errors)
        if isinstance(t,dict) and text(t.get("ticket_id")):
            if t["ticket_id"] in tickets: errors.append("duplicate repair ticket id")
            tickets[t["ticket_id"]]=t

    cards=bundle.get("card_audits")
    if not isinstance(cards,list) or not cards: errors.append("card_audits must be non-empty"); cards=[]
    ids=[]
    for c in cards:
        if not isinstance(c,dict): errors.append("card audit must be object"); continue
        cid=c.get("card_id"); ids.append(cid); p=f"card {cid}"
        digest,err=file_digest(base_dir,c.get("image_path"))
        if err: errors.append(f"{p} image_path {err}")
        elif not sha(c.get("image_sha256")) or digest!=c.get("image_sha256"): errors.append(f"{p} image hash mismatch")
        br=c.get("blind_readback",{})
        if br.get("frozen_before_comparison") is not True or not sha(br.get("digest")): errors.append(f"{p} blind readback not frozen/bound")
        if not sha(c.get("expected_semantic_packet_digest")): errors.append(f"{p} expected semantic digest invalid")
        axes=c.get("axes",{})
        if any(a not in axes for a in SEM+("ENGINEERING_CONFORMANCE",)): errors.append(f"{p} axes incomplete")
        findings_ok(c.get("findings"),f"{p}.findings",errors)
        v=c.get("verdict")
        if c.get("release_blocking") is not (v in BLOCK): errors.append(f"{p} release_blocking mismatch")
        if v=="FAIL_SPEC" and c.get("failure_origin") not in {"FINAL_CARD_SPEC","TRUTH_BOUNDARY","SOURCE_BINDING","MIXED"}: errors.append(f"{p} FAIL_SPEC requires failure_origin")
        if v!="FAIL_SPEC" and c.get("failure_origin") is not None: errors.append(f"{p} failure_origin only for FAIL_SPEC")
        tid=c.get("repair_ticket_id")
        if v in FAIL and (not text(tid) or tid not in tickets): errors.append(f"{p} fail requires repair ticket")
        if v not in FAIL and tid is not None: errors.append(f"{p} non-fail cannot have repair ticket")
        vals=[axes.get(a) for a in SEM]; eng=axes.get("ENGINEERING_CONFORMANCE")
        if v=="PASS" and (any(x!="pass" for x in vals) or eng!="pass"): errors.append(f"{p} PASS axes mismatch")
        if v=="PASS_WITH_WARNINGS" and (any(x in {"fail","unverifiable"} for x in vals) or not(any(x=="warning" for x in vals) or eng=="warning" or any(isinstance(f,dict) and f.get("materiality")=="non_material" for f in c.get("findings",[])))): errors.append(f"{p} warning verdict mismatch")
        if v=="BLOCK_UNVERIFIABLE" and not any(x=="unverifiable" for x in vals): errors.append(f"{p} block requires unverifiable axis")
        if v in FAIL:
            substantive=[f for f in c.get("findings",[]) if isinstance(f,dict) and f.get("materiality")=="material" and not(f.get("axis")=="ENGINEERING_CONFORMANCE" and f.get("finding_type") in {"WORDING_DIVERGENCE","EXTRA_VISIBLE_TEXT"})]
            if not substantive: errors.append(f"{p} fail cannot be wording/engineering-only")
    if len(ids)!=len(set(ids)): errors.append("card ids must be unique")

    dd=bundle.get("dedup_manifest",{}); dups=dd.get("duplicates",[]) if isinstance(dd,dict) else []
    if dd.get("unique_card_count")!=len(cards) or dd.get("duplicate_count")!=len(dups): errors.append("dedup counts mismatch")
    byid={c.get("card_id"):c for c in cards if isinstance(c,dict)}
    for d in dups:
        target=byid.get(d.get("duplicate_of_card_id")) if isinstance(d,dict) else None
        if not target or d.get("image_sha256")!=target.get("image_sha256"): errors.append("dedup binding mismatch")

    cs=bundle.get("cardset_audit",{})
    findings_ok(cs.get("cross_card_findings"),"cardset findings",errors)
    exp=cardset_expected(bundle)
    if cs.get("scope")!="cross_card_and_package_only" or cs.get("status")!=exp: errors.append(f"cardset status must be {exp}")

    risk=bundle.get("methodological_risk",{})
    rel=relationship(risk.get("generator_model_family"),risk.get("auditor_model_family"))
    if risk.get("relationship")!=rel: errors.append(f"methodological relationship must be {rel}")
    material,secondary,effect,corr=risk_expected(risk)
    if risk.get("material_to_run") is not material: errors.append(f"material_to_run must be {material}")
    if risk.get("secondary_review_required") is not secondary: errors.append(f"secondary_review_required must be {secondary}")
    if risk.get("release_effect")!=effect: errors.append(f"release_effect must be {effect}")
    if risk.get("correlated_error_risk")!=corr: errors.append(f"correlated_error_risk must be {corr}")
    reasons=risk.get("high_stakes_reasons",[])
    if risk.get("high_stakes_cardset") is True and not reasons: errors.append("high-stakes run requires reasons")
    if risk.get("high_stakes_cardset") is False and reasons: errors.append("non-high-stakes run must not list reasons")

    rg=bundle.get("release_gate",{}); exp=release_expected(bundle)
    if rg.get("status")!=exp or rg.get("release_allowed") is not (exp in {"PASS","PASS_WITH_WARNINGS"}): errors.append(f"release gate must be {exp}")
    if rg.get("unique_card_count")!=len(cards) or rg.get("duplicate_count")!=len(dups): errors.append("release counts mismatch")
    counts=rg.get("counts",{})
    for v in ("PASS","PASS_WITH_WARNINGS","FAIL_RENDER","FAIL_SPEC","BLOCK_UNVERIFIABLE"):
        if counts.get(v)!=sum(1 for c in cards if isinstance(c,dict) and c.get("verdict")==v): errors.append(f"release count {v} mismatch")
    blocking=sorted(c.get("card_id") for c in cards if isinstance(c,dict) and c.get("verdict") in BLOCK)
    warning=sorted(c.get("card_id") for c in cards if isinstance(c,dict) and c.get("verdict")=="PASS_WITH_WARNINGS")
    if sorted(rg.get("blocking_card_ids",[]))!=blocking or sorted(rg.get("warning_card_ids",[]))!=warning: errors.append("release card id lists mismatch")

    prov=bundle.get("provenance",{})
    if prov.get("auditor_role")!="post_render_auditor" or prov.get("mutated_upstream_artifacts") is not False or prov.get("generation_calls_made")!=0: errors.append("RCA provenance mutation/generation boundary violated")
    lim=[x for x in prov.get("methodological_limitations",[]) if isinstance(x,dict) and x.get("type")=="CORRELATED_MODEL_ERROR"]
    if len(lim)!=1 or lim[0].get("material_to_run") is not risk.get("material_to_run"): errors.append("correlated-model limitation must match risk")
    return errors

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("bundle",type=Path); ap.add_argument("--json",action="store_true",dest="as_json"); a=ap.parse_args()
    try: b=json.loads(a.bundle.read_text(encoding="utf-8")); e=validate_bundle(b,base_dir=a.bundle.resolve().parent); v=b.get("contract_version") if isinstance(b,dict) else None
    except (OSError,json.JSONDecodeError) as exc: e=[str(exc)]; v=None
    out={"status":"pass" if not e else "fail","contract_version":v,"errors":e}
    if a.as_json: print(json.dumps(out,ensure_ascii=False,sort_keys=True))
    elif e:
        for x in e: print(f"ERROR: {x}",file=sys.stderr)
    else: print(f"Rendered Card Audit v{v}: PASS")
    return 0 if not e else 1
if __name__=="__main__": raise SystemExit(main())
