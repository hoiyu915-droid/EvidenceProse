#!/usr/bin/env python3
"""Structural validator for EP_RENDERED_CARD_AUDIT v1.2 / method 1.3."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
from typing import Any

SCRIPT_DIR=Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path: sys.path.insert(0,str(SCRIPT_DIR))
from validate_rendered_card_source_closure import validate_card as validate_source_surface_card, METHOD as SOURCE_METHOD
from validate_rca_policy import get_current_policy

RCA_POLICY,POLICY_DIGEST=get_current_policy()
POLICY_ID=RCA_POLICY["policy_id"]
METHOD=RCA_POLICY["method_revision"]
POLICY_VERSION=RCA_POLICY["policy_version"]
RESULT_SCHEMA_VERSION=RCA_POLICY["result_schema_version"]
RESULT_CONTRACT_VERSION=RCA_POLICY["contract_version"]
assert SOURCE_METHOD==METHOD
SEM=("CONTENT_MEANING","SOURCE_SURFACE","VISUAL_SEMANTICS","CITATION_TRACEABILITY")
FAIL=set(RCA_POLICY["verdict_mapping"]["material_failure_verdicts"]); BLOCK=FAIL|{"BLOCK_UNVERIFIABLE"}
TOPOLOGY_POLICY=RCA_POLICY["topology"]
EDGE_STATUSES=TOPOLOGY_POLICY["edge_statuses"]
RELATION_STATUSES=TOPOLOGY_POLICY["relation_statuses"]
BRANCH_STATUSES=TOPOLOGY_POLICY["branch_statuses"]
TERMINAL_STATUSES=TOPOLOGY_POLICY["terminal_statuses"]
ROLE_PARTITION_STATUSES=TOPOLOGY_POLICY["role_partition_statuses"]
TEXT_VISUAL_STATUSES=TOPOLOGY_POLICY["text_visual_consistency_statuses"]
SOURCE_POLICY_ANNOTATION_ROLES=set(RCA_POLICY["source_surface"]["annotation"]["roles"])
AXIS_STATUSES=set(RCA_POLICY["verdict_mapping"]["axis_status_to_verdict"])
VERDICTS=set(RCA_POLICY["verdict_mapping"]["verdicts"])
# Package coverage is a separately aggregated status, not a card verdict.
# Keep its closed set explicit so an unknown value cannot fall through to
# NOT_APPLICABLE and release PASS.
PACKAGE_COVERAGE_STATUSES={"PASS","WARNING","FAIL","BLOCKED","NOT_APPLICABLE"}

def txt(v): return isinstance(v,str) and bool(v.strip())
def sha(v): return txt(v) and len(v)==64 and all(c in "0123456789abcdef" for c in v)

def jd(v):
    """Return a canonical digest, or ``None`` for an invalid JSON shape."""

    try:
        return hashlib.sha256(
            json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
        ).hexdigest()
    except (TypeError, ValueError):
        return None

def _source_binding_digest(binding:dict[str,Any]) -> str|None:
    # The metadata binding must cover the complete source object.  Excluding
    # only the digest field prevents unrecognised metadata from being silently
    # added outside the integrity boundary.
    payload={k:v for k,v in binding.items() if k!="binding_digest"}
    return jd(payload)

def blind_payload_digest(br:dict[str,Any]) -> str:
    payload={k:v for k,v in br.items() if k!="digest"}
    return jd(payload)

def expected_semantic_packet_digest(card:dict[str,Any]) -> str|None:
    packet=card.get("expected_semantic_packet")
    return jd(packet) if isinstance(packet,dict) else None

def _string_list(value:Any, path:str, errors:list[str], *, nonempty:bool=False) -> list[str]:
    if not isinstance(value,list):
        add(errors,f"{path} must be array")
        return []
    if nonempty and not value:
        add(errors,f"{path} must be non-empty")
    result=[]
    for i,item in enumerate(value):
        if not txt(item):
            add(errors,f"{path}[{i}] must be a non-empty string")
        else:
            result.append(item)
    if len(result)!=len(set(result)):
        add(errors,f"{path} must not contain duplicate values")
    return result

def _status_bucket(status:Any, groups:dict[str,Any]) -> str|None:
    if not isinstance(status,str):
        return None
    for bucket,values in groups.items():
        if isinstance(values,list) and status in values:
            return bucket
    return None

def _validate_semantic_packet(
    card:dict[str,Any],
    source_bindings:dict[str,dict[str,Any]],
    prefix:str,
    errors:list[str],
) -> dict[str,Any]:
    packet=card.get("expected_semantic_packet")
    if not isinstance(packet,dict):
        add(errors,f"{prefix} expected_semantic_packet must be object")
        return {}
    _string_list(packet.get("central_claims"),f"{prefix}.expected_semantic_packet.central_claims",errors,nonempty=True)
    if not txt(packet.get("causal_ceiling")):
        add(errors,f"{prefix}.expected_semantic_packet.causal_ceiling must be non-empty string")
    _string_list(packet.get("limitations"),f"{prefix}.expected_semantic_packet.limitations",errors)
    source_ids=_string_list(packet.get("source_binding_ids"),f"{prefix}.expected_semantic_packet.source_binding_ids",errors,nonempty=True)
    unknown=sorted(set(source_ids)-set(source_bindings))
    if unknown:
        add(errors,f"{prefix} expected semantic packet references unknown source ids: {', '.join(unknown)}")

    source_digests=packet.get("source_binding_digests")
    if not isinstance(source_digests,dict):
        add(errors,f"{prefix}.expected_semantic_packet.source_binding_digests must be object")
        source_digests={}
    if set(source_digests)!=set(source_ids):
        add(errors,f"{prefix}.expected_semantic_packet.source_binding_digests must exactly cover source_binding_ids")
    for sid in source_ids:
        value=source_digests.get(sid)
        if not sha(value):
            add(errors,f"{prefix}.expected_semantic_packet.source_binding_digests.{sid} must be sha256")
        elif sid in source_bindings and value!=source_bindings[sid].get("binding_digest"):
            add(errors,f"{prefix}.expected semantic packet source binding digest mismatch for {sid}")

    expected_graph=packet.get("expected_graph")
    if not isinstance(expected_graph,dict):
        add(errors,f"{prefix}.expected_semantic_packet.expected_graph must be object")
    else:
        for graph_key in ("nodes","relations","branch_points","terminal_states","role_partitions"):
            graph_values=expected_graph.get(graph_key)
            if not isinstance(graph_values,list):
                add(errors,f"{prefix}.expected_semantic_packet.expected_graph.{graph_key} must be array")
            else:
                for i,item in enumerate(graph_values):
                    if not isinstance(item,dict):
                        add(errors,f"{prefix}.expected_semantic_packet.expected_graph.{graph_key}[{i}] must be object")
    expected_graph_digest=packet.get("expected_graph_digest")
    if not sha(expected_graph_digest):
        add(errors,f"{prefix}.expected_semantic_packet.expected_graph_digest must be sha256")
    elif isinstance(expected_graph,dict) and expected_graph_digest!=jd(expected_graph):
        add(errors,f"{prefix}.expected_semantic_packet.expected_graph_digest mismatch")

    expected_inventory=packet.get("expected_content_inventory")
    if not isinstance(expected_inventory,list):
        add(errors,f"{prefix}.expected_semantic_packet.expected_content_inventory must be array")
        expected_inventory=[]
    expected_ids=[]
    for i,item in enumerate(expected_inventory):
        q=f"{prefix}.expected_semantic_packet.expected_content_inventory[{i}]"
        if not isinstance(item,dict):
            add(errors,f"{q} must be object")
            continue
        node_id=item.get("expected_node_id")
        if not txt(node_id): add(errors,f"{q}.expected_node_id required")
        else: expected_ids.append(node_id)
        if not isinstance(item.get("material"),bool): add(errors,f"{q}.material must be boolean")
        if not isinstance(item.get("closed_set_member"),bool): add(errors,f"{q}.closed_set_member must be boolean")
    if len(expected_ids)!=len(set(expected_ids)):
        add(errors,f"{prefix}.expected_semantic_packet.expected_content_inventory ids must be unique")

    expected_annotations=packet.get("expected_evidence_annotation_inventory")
    if not isinstance(expected_annotations,list):
        add(errors,f"{prefix}.expected_semantic_packet.expected_evidence_annotation_inventory must be array")
        expected_annotations=[]
    annotation_ids=[]
    for i,item in enumerate(expected_annotations):
        q=f"{prefix}.expected_semantic_packet.expected_evidence_annotation_inventory[{i}]"
        if not isinstance(item,dict):
            add(errors,f"{q} must be object")
            continue
        aid=item.get("expected_annotation_id")
        role=item.get("expected_role")
        if not txt(aid): add(errors,f"{q}.expected_annotation_id required")
        else: annotation_ids.append(aid)
        if not isinstance(role,str) or role not in set(SOURCE_POLICY_ANNOTATION_ROLES): add(errors,f"{q}.expected_role invalid")
    if len(annotation_ids)!=len(set(annotation_ids)):
        add(errors,f"{prefix}.expected_semantic_packet.expected_evidence_annotation_inventory ids must be unique")

    rec=card.get("visual_semantic_reconciliation")
    if isinstance(rec,dict):
        rec_graph=rec.get("expected_graph")
        if isinstance(expected_graph,dict) and isinstance(rec_graph,dict) and expected_graph!=rec_graph:
            add(errors,f"{prefix} expected semantic packet graph does not equal reconciliation graph")
        if packet.get("expected_graph_digest")!=rec.get("expected_graph_digest"):
            add(errors,f"{prefix} expected semantic packet graph digest mismatch")
    return packet

def _source_locator_id(locator:Any,path:str,errors:list[str]) -> str|None:
    if not isinstance(locator,str) or not locator.strip():
        add(errors,f"{path} must be a non-empty source_id:locator string")
        return None
    source_id,separator,detail=locator.partition(":")
    if not separator or not source_id.strip() or not detail.strip():
        add(errors,f"{path} must use source_id:locator form")
        return None
    return source_id.strip()

def source_locator_ids(card:dict[str,Any],errors:list[str]|None=None) -> set[str]:
    local_errors=errors if errors is not None else []
    out:set[str]=set()
    rec=card.get("source_surface_reconciliation",{})
    if not isinstance(rec,dict): rec={}
    for key in ("content_node_checks","expected_content_checks","evidence_annotation_checks"):
        checks=rec.get(key,[])
        if not isinstance(checks,list):
            continue
        for i,item in enumerate(checks):
            if not isinstance(item,dict):
                continue
            locators=item.get("source_locators",[])
            if not isinstance(locators,list):
                continue
            for j,locator in enumerate(locators):
                sid=_source_locator_id(locator,f"source_surface_reconciliation.{key}[{i}].source_locators[{j}]",local_errors)
                if sid:
                    out.add(sid)
    visual=card.get("visual_semantic_reconciliation",{})
    source_structure=visual.get("source_structure",{}) if isinstance(visual,dict) else {}
    locators=source_structure.get("source_locators",[]) if isinstance(source_structure,dict) else []
    if isinstance(locators,list):
        for i,locator in enumerate(locators):
            sid=_source_locator_id(locator,f"visual_semantic_reconciliation.source_structure.source_locators[{i}]",local_errors)
            if sid:
                out.add(sid)
    return out

def file_sha(base,rel):
    if base is None or not txt(rel): return None
    p=Path(rel)
    if p.is_absolute() or ".." in p.parts: return None
    try:
        root=Path(base).resolve()
        p=(root/p).resolve()
        p.relative_to(root)
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
    except (OSError, RuntimeError, ValueError, TypeError):
        return None

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
        if not isinstance(m,str) or m not in {"non_material","material","blocking_unverifiable"}: add(errors,f"{p}.materiality invalid")
        support=f.get("source_support",[])
        if isinstance(m,str) and m in {"material","blocking_unverifiable"} and (not isinstance(support,list) or not any(txt(x) for x in support if isinstance(x,str))): add(errors,f"{p} material finding requires source_support")
        rp=f.get("repair_prescription")
        if not isinstance(rp,dict) or not txt(rp.get("instruction")): add(errors,f"{p} repair_prescription required")
    return out

def linked(fid,findings,prefix,errors):
    if not txt(fid) or fid not in findings: add(errors,f"{prefix} requires linked finding"); return
    if findings[fid].get("axis")!="VISUAL_SEMANTICS": add(errors,f"{prefix} finding must be VISUAL_SEMANTICS")

def visual_status(rec,findings,prefix,errors):
    if not isinstance(rec,dict): add(errors,f"{prefix} reconciliation required"); return "unverifiable"
    src=rec.get("source_structure",{})
    if not isinstance(src,dict): src={}
    kind=src.get("source_kind")
    if src.get("structure_required") is not True: add(errors,f"{prefix} source structure required")
    if not isinstance(kind,str) or kind not in {"body_text","figure","table","mixed"}: add(errors,f"{prefix} source_kind invalid")
    source_locators=src.get("source_locators",[])
    if not isinstance(source_locators,list):
        add(errors,f"{prefix} source locators must be array")
        source_locators=[]
    if not any(txt(x) for x in source_locators if isinstance(x,str)): add(errors,f"{prefix} source locators required")
    for i,locator in enumerate(source_locators):
        _source_locator_id(locator,f"{prefix}.source_structure.source_locators[{i}]",errors)
    if isinstance(kind,str) and kind in {"figure","table","mixed"} and src.get("figure_or_table_directly_inspected") is not True: add(errors,f"{prefix} figure/table-derived structure requires direct inspection")
    if src.get("expected_graph_derived") is not True: add(errors,f"{prefix} expected graph must be derived")
    og,eg=rec.get("observed_graph"),rec.get("expected_graph")
    if not isinstance(og,dict) or not isinstance(eg,dict): add(errors,f"{prefix} observed/expected graph required"); return "unverifiable"
    if rec.get("observed_graph_digest")!=jd(og): add(errors,f"{prefix} observed_graph_digest mismatch")
    if rec.get("expected_graph_digest")!=jd(eg): add(errors,f"{prefix} expected_graph_digest mismatch")
    def graph_nodes(graph,label):
        values=graph.get("nodes")
        if not isinstance(values,list):
            add(errors,f"{prefix} {label} graph nodes must be array")
            return
        for i,item in enumerate(values):
            if not isinstance(item,dict):
                add(errors,f"{prefix} {label} graph nodes[{i}] must be object")

    graph_nodes(og,"observed")
    graph_nodes(eg,"expected")

    def graph_items(graph,key):
        values=graph.get(key,[])
        if not isinstance(values,list):
            add(errors,f"{prefix} expected graph {key} must be array")
            return []
        items=[]
        for i,item in enumerate(values):
            if not isinstance(item,dict):
                add(errors,f"{prefix} expected graph {key}[{i}] must be object")
                continue
            if item.get("material") is True:
                items.append(item)
        return items

    def graph_ids(graph,key,id_key):
        values=graph_items(graph,key)
        ids=[]
        for item in values:
            value=item.get(id_key)
            if not txt(value):
                add(errors,f"{prefix} material {key} item requires {id_key}")
            else:
                ids.append(value)
        if len(ids)!=len(set(ids)):
            add(errors,f"{prefix} material {key} ids must be unique")
        return ids

    edges=graph_ids(og,"edges","edge_id")
    rels=graph_ids(eg,"relations","relation_id")
    branches=graph_ids(eg,"branch_points","branch_id")
    terms=graph_ids(eg,"terminal_states","terminal_id")
    partitions=graph_ids(eg,"role_partitions","partition_id")
    bad=warn=unv=False
    def check_ids(value,key,label):
        if not isinstance(value,list):
            add(errors,f"{prefix} {label} must be array")
            return []
        ids=[]
        for item in value:
            if not isinstance(item,dict):
                add(errors,f"{prefix} {label} items must be objects")
                continue
            ident=item.get(key)
            if not txt(ident):
                add(errors,f"{prefix} {label} item requires {key}")
            else:
                ids.append(ident)
        if len(ids)!=len(set(ids)):
            add(errors,f"{prefix} {label} ids must be unique")
        return ids

    ec=rec.get("edge_checks",[]); eids=check_ids(ec,"edge_id","edge_checks")
    if sorted(eids)!=sorted(edges): add(errors,f"{prefix} every observed material edge must be dispositioned exactly once")
    for x in ec if isinstance(ec,list) else []:
        if not isinstance(x,dict):
            continue
        st=x.get("status")
        bucket=_status_bucket(st,EDGE_STATUSES)
        if bucket=="block": unv=True; linked(x.get("finding_id"),findings,f"{prefix} edge {x.get('edge_id')}",errors)
        elif bucket=="fail": bad=True; linked(x.get("finding_id"),findings,f"{prefix} edge {x.get('edge_id')}",errors)
        elif bucket=="warning": warn=True
        elif bucket!="pass": add(errors,f"{prefix} edge status invalid")
    rc=rec.get("expected_relation_checks",[]); rids=check_ids(rc,"relation_id","expected_relation_checks")
    if sorted(rids)!=sorted(rels): add(errors,f"{prefix} every expected material relation must be covered exactly once")
    for x in rc if isinstance(rc,list) else []:
        if not isinstance(x,dict):
            continue
        st=x.get("status")
        bucket=_status_bucket(st,RELATION_STATUSES)
        if bucket=="block": unv=True; linked(x.get("finding_id"),findings,f"{prefix} relation {x.get('relation_id')}",errors)
        elif bucket=="fail": bad=True; linked(x.get("finding_id"),findings,f"{prefix} relation {x.get('relation_id')}",errors)
        elif bucket=="warning": warn=True
        elif bucket!="pass": add(errors,f"{prefix} relation status invalid")
    bc=rec.get("branch_point_checks",[]); bids=check_ids(bc,"branch_id","branch_point_checks")
    if sorted(bids)!=sorted(branches): add(errors,f"{prefix} every material branch point must be checked exactly once")
    tc=rec.get("terminal_state_checks",[]); tids=check_ids(tc,"terminal_id","terminal_state_checks")
    if sorted(tids)!=sorted(terms): add(errors,f"{prefix} every material terminal state must be checked exactly once")
    for label,items,key,statuses in (("branch",bc,"branch_id",BRANCH_STATUSES),("terminal",tc,"terminal_id",TERMINAL_STATUSES)):
        for x in items if isinstance(items,list) else []:
            if not isinstance(x,dict):
                continue
            st=x.get("status")
            bucket=_status_bucket(st,statuses)
            if bucket=="block": unv=True; linked(x.get("finding_id"),findings,f"{prefix} {label} {x.get(key)}",errors)
            elif bucket=="fail": bad=True; linked(x.get("finding_id"),findings,f"{prefix} {label} {x.get(key)}",errors)
            elif bucket=="warning": warn=True
            elif bucket!="pass": add(errors,f"{prefix} {label} status invalid")
    pc=rec.get("role_partition_checks",[]); pids=check_ids(pc,"partition_id","role_partition_checks")
    if sorted(pids)!=sorted(partitions): add(errors,f"{prefix} every material role partition must be checked exactly once")
    for x in pc if isinstance(pc,list) else []:
        if not isinstance(x,dict):
            continue
        st=x.get("status")
        bucket=_status_bucket(st,ROLE_PARTITION_STATUSES)
        if bucket=="block": unv=True; linked(x.get("finding_id"),findings,f"{prefix} role partition {x.get('partition_id')}",errors)
        elif bucket=="fail": bad=True; linked(x.get("finding_id"),findings,f"{prefix} role partition {x.get('partition_id')}",errors)
        elif bucket=="warning": warn=True
        elif bucket!="pass": add(errors,f"{prefix} role partition status invalid")
    tv=rec.get("text_visual_consistency",{}); st=tv.get("status") if isinstance(tv,dict) else None
    text_visual_bucket=_status_bucket(st,TEXT_VISUAL_STATUSES)
    if text_visual_bucket=="block": unv=True; linked(tv.get("finding_id"),findings,f"{prefix} text/visual failure",errors)
    elif text_visual_bucket=="fail": bad=True; linked(tv.get("finding_id"),findings,f"{prefix} text/visual failure",errors)
    elif text_visual_bucket=="warning": warn=True
    elif text_visual_bucket!="pass": add(errors,f"{prefix} text_visual_consistency invalid")
    comp=rec.get("topology_completion",{})
    if not isinstance(comp,dict):
        add(errors,f"{prefix} topology_completion must be object")
        comp={}
    required={"all_observed_material_edges_dispositioned":sorted(eids)==sorted(edges),"all_expected_material_relations_covered":sorted(rids)==sorted(rels),"all_material_branch_points_checked":sorted(bids)==sorted(branches),"all_material_terminal_states_checked":sorted(tids)==sorted(terms),"all_material_role_partitions_checked":sorted(pids)==sorted(partitions),"text_visual_consistency_checked":text_visual_bucket is not None,"concept_presence_shortcut_not_used":True}
    for k,v in required.items():
        if comp.get(k) is not v: add(errors,f"{prefix} topology_completion.{k} must be {v}")
    if comp.get("concept_presence_shortcut_not_used") is not True: add(errors,f"{prefix} concept-presence shortcut is forbidden")
    return "unverifiable" if unv else "fail" if bad else "warning" if warn else "pass"

def validate_ticket(t,errors):
    if not isinstance(t,dict): add(errors,"repair ticket must be object"); return
    p=f"repair ticket {t.get('ticket_id')}"
    if not isinstance(t.get("verdict"),str) or t.get("verdict") not in FAIL: add(errors,f"{p} verdict invalid")
    if not txt(t.get("card_title")) or not txt(t.get("human_repair_text")): add(errors,f"{p} card_title and human_repair_text required for every failure")
    if not t.get("action_plan"): add(errors,f"{p} action_plan required")
    s=t.get("substantial_change")
    if not isinstance(s,dict): add(errors,f"{p} substantial_change required"); return
    total,changed=s.get("total_semantic_weight"),s.get("changed_semantic_weight")
    if not isinstance(total,(int,float)) or not isinstance(changed,(int,float)) or total<0 or changed<0 or (total and changed>total): add(errors,f"{p} semantic weights invalid"); return
    frac=None if total<=0 else changed/total
    fraction_value=s.get("estimated_weighted_semantic_fraction")
    if frac is not None and (not isinstance(fraction_value,(int,float)) or abs(fraction_value-frac)>1e-9): add(errors,f"{p} fraction must equal changed/total")
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
    rel=r.get("relationship")
    material=isinstance(rel,str) and rel in {"same_family","unknown"}
    secondary=material and r.get("high_stakes_cardset") is True
    if secondary:
        if r.get("secondary_review_status")=="completed" and r.get("secondary_review_outcome")=="agreement": effect="none"
        elif r.get("secondary_review_status")=="completed" and r.get("secondary_review_outcome")=="disagreement": effect="blocked_unresolved_disagreement"
        else: effect="blocked_pending_secondary_review"
    else: effect="warning_ceiling" if material else "none"
    corr={"same_family":"present","unknown":"unknown","different_family":"low"}.get(rel,"unknown") if isinstance(rel,str) else "unknown"
    return material,secondary,effect,corr

def cardset_status(b):
    cs=b.get("cardset_audit",{})
    if not isinstance(cs,dict): return "BLOCKED"
    fs=cs.get("cross_card_findings",[])
    if not isinstance(fs,list): return "BLOCKED"
    coverage=cs.get("package_coverage",{})
    if not isinstance(coverage,dict): return "BLOCKED"
    cov=coverage.get("status","BLOCKED")
    if not isinstance(cov,str) or cov not in PACKAGE_COVERAGE_STATUSES:
        return "BLOCKED"
    audits=b.get("card_audits",[])
    if not isinstance(audits,list): audits=[]
    if len(audits)<2 and not fs and cov=="NOT_APPLICABLE": return "NOT_APPLICABLE"
    mats=[x.get("materiality") for x in fs if isinstance(x,dict)]
    if cov=="BLOCKED" or "blocking_unverifiable" in mats: return "BLOCKED"
    if cov=="FAIL" or "material" in mats: return "FAIL"
    if cov=="WARNING" or "non_material" in mats: return "WARNING"
    return "PASS" if cov=="PASS" else "NOT_APPLICABLE"

def release_status(b):
    risk=b.get("methodological_risk",{})
    if not isinstance(risk,dict): risk={}
    effect=risk.get("release_effect")
    audits=b.get("card_audits",[])
    if not isinstance(audits,list): audits=[]
    vs=[c.get("verdict") for c in audits if isinstance(c,dict)]
    cs=b.get("cardset_audit",{})
    if not isinstance(cs,dict): cs={}
    coverage=cs.get("package_coverage",{})
    if not isinstance(coverage,dict): coverage={}
    cs_status=cs.get("status") if isinstance(cs.get("status"),str) else None
    cov_status=coverage.get("status") if isinstance(coverage.get("status"),str) else None
    pair={cs_status,cov_status}
    if isinstance(effect,str) and effect in {"blocked_pending_secondary_review","blocked_unresolved_disagreement"}: return "BLOCKED"
    if "BLOCK_UNVERIFIABLE" in vs or "BLOCKED" in pair: return "BLOCKED"
    if any(isinstance(v,str) and v in FAIL for v in vs) or "FAIL" in pair: return "FAIL"
    if effect=="warning_ceiling" or "PASS_WITH_WARNINGS" in vs or "WARNING" in pair: return "PASS_WITH_WARNINGS"
    return "PASS"

def human_display(b,tickets,errors):
    audits=b.get("card_audits",[])
    if not isinstance(audits,list): audits=[]
    fails=[c for c in audits if isinstance(c,dict) and isinstance(c.get("verdict"),str) and c.get("verdict") in FAIL]; d=b.get("human_repair_display")
    if not fails:
        if d is not None: add(errors,"human_repair_display must be null when no failed cards")
        return
    if not isinstance(d,dict): add(errors,"failed cards require human_repair_display writing block"); return
    if d.get("surface")!="writing_block" or d.get("single_block") is not True: add(errors,"human_repair_display must be one writing_block")
    if d.get("first_line")!="imgedit": add(errors,"human_repair_display first line must be exactly imgedit")
    secs=d.get("sections",[])
    if not isinstance(secs,list):
        add(errors,"human_repair_display.sections must be array")
        return
    expected=[c.get("card_id") for c in fails]; actual=[s.get("card_id") for s in secs if isinstance(s,dict)]
    if actual!=expected: add(errors,"human_repair_display sections must match failed cards in card order")
    for c,s in zip(fails,secs):
        if not isinstance(s,dict):
            add(errors,f"human repair section {c.get('card_id')} must be object")
            continue
        title,tid=c.get("card_title"),c.get("repair_ticket_id"); t=tickets.get(tid,{}) if txt(tid) else {}
        if s.get("card_title")!=title or s.get("heading")!=f"[{title}]": add(errors,f"human repair section {c.get('card_id')} heading must be exact [card title]")
        if s.get("ticket_id")!=tid or s.get("content")!=t.get("human_repair_text"): add(errors,f"human repair section {c.get('card_id')} ticket/content mismatch")
    expected_text="imgedit"+"".join(f"\n[{s['card_title']}]\n{s['content']}" for s in secs if isinstance(s,dict))
    if d.get("rendered_text")!=expected_text: add(errors,"human_repair_display.rendered_text format mismatch")

def validate_bundle(b:Any,*,base_dir:Path|None=None):
    e=[]
    if not isinstance(b,dict): return ["bundle must be object"]
    contract_version=b.get("contract_version")
    if contract_version!=RESULT_CONTRACT_VERSION: add(e,f"contract_version must be {RESULT_CONTRACT_VERSION}")
    if b.get("result_schema_version")!=RESULT_SCHEMA_VERSION: add(e,f"result_schema_version must be {RESULT_SCHEMA_VERSION}")
    if b.get("policy_id")!=POLICY_ID: add(e,f"policy_id must be {POLICY_ID}")
    if b.get("policy_version")!=POLICY_VERSION: add(e,f"policy_version must be {POLICY_VERSION}")
    if b.get("method_revision")!=METHOD: add(e,f"method_revision must be {METHOD}")
    if b.get("policy_digest")!=POLICY_DIGEST: add(e,"policy_digest does not match canonical policy pack")
    raw_source_bindings=b.get("source_bindings")
    if not isinstance(raw_source_bindings,list) or not raw_source_bindings:
        add(e,"source_bindings must be non-empty")
        raw_source_bindings=[]
    source_bindings={}
    for i,sb in enumerate(raw_source_bindings):
        p=f"source_bindings[{i}]"
        if not isinstance(sb,dict):
            add(e,f"{p} must be object")
            continue
        sid=sb.get("source_id")
        if not txt(sid):
            add(e,f"{p} source_id required")
            continue
        if sid in source_bindings:
            add(e,f"{p} duplicate source_id {sid}")
        else:
            source_bindings[sid]=sb
        if not txt(sb.get("type")):
            add(e,f"{p}.type required")
        if not txt(sb.get("status")):
            add(e,f"{p}.status required")
        identity=sb.get("identity")
        if not isinstance(identity,dict) or not identity:
            add(e,f"{p}.identity must be non-empty object")
        artifact_path=sb.get("artifact_path")
        if not txt(artifact_path):
            add(e,f"{p}.artifact_path required")
        actual_source_digest=file_sha(base_dir,artifact_path)
        if actual_source_digest is None:
            add(e,f"{p}.artifact_path must resolve to a repository-local artifact")
        if not sha(sb.get("source_digest")):
            add(e,f"{p}.source_digest invalid")
        elif actual_source_digest is not None and sb.get("source_digest")!=actual_source_digest:
            add(e,f"{p}.source_digest must match artifact bytes")
        if not sha(sb.get("binding_digest")):
            add(e,f"{p}.binding_digest invalid")
        elif sb.get("binding_digest")!=_source_binding_digest(sb):
            add(e,f"{p}.binding_digest must bind source metadata and artifact digest")
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
        cid=c.get("card_id");
        if not txt(cid): add(e,"card_id must be non-empty string")
        else: ids.append(cid)
        p=f"card {cid}"
        if not txt(c.get("card_title")): add(e,f"{p} card_title required")
        if file_sha(base_dir,c.get("image_path"))!=c.get("image_sha256"): add(e,f"{p} image hash mismatch")
        br=c.get("blind_readback")
        if not isinstance(br,dict):
            add(e,f"{p} blind_readback must be object")
            br={}
        else:
            if br.get("frozen_before_comparison") is not True or not sha(br.get("digest")): add(e,f"{p} blind readback not frozen/bound")
            if br.get("digest")!=blind_payload_digest(br): add(e,f"{p} blind readback digest must match frozen payload")
            if not sha(br.get("visual_graph_digest")): add(e,f"{p} visual graph digest required")
            if not isinstance(br.get("evidence_annotation_inventory"),list): add(e,f"{p} evidence_annotation_inventory must be frozen as an array")
        packet=_validate_semantic_packet(c,source_bindings,p,e)
        if not sha(c.get("expected_semantic_packet_digest")): add(e,f"{p} expected semantic digest invalid")
        if c.get("expected_semantic_packet_digest") != expected_semantic_packet_digest(c): add(e,f"{p} expected_semantic_packet_digest must bind canonical semantic packet")
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
        source_refs=source_locator_ids(c,e)
        if source_refs and source_bindings:
            unknown=[sid for sid in source_refs if sid not in source_bindings]
            if unknown: add(e,f"{p} source references unknown source ids: {', '.join(sorted(unknown))}")
        rec=c.get("visual_semantic_reconciliation",{})
        if isinstance(rec,dict):
            if br.get("visual_graph_digest")!=rec.get("observed_graph_digest"): add(e,f"{p} frozen blind graph digest mismatch")
        axes=c.get("axes",{})
        if not isinstance(axes,dict):
            add(e,f"{p} axes must be object")
            axes={}
        axis_names=SEM+("ENGINEERING_CONFORMANCE",)
        if any(x not in axes for x in axis_names): add(e,f"{p} axes incomplete")
        else:
            if axes.get("VISUAL_SEMANTICS")!=expected: add(e,f"{p} VISUAL_SEMANTICS must be {expected} from topology reconciliation")
            if source_expected is not None and axes.get("SOURCE_SURFACE")!=source_expected: add(e,f"{p} SOURCE_SURFACE must be {source_expected} from source-surface reconciliation")
        for axis_name in axis_names:
            axis_value=axes.get(axis_name)
            if not isinstance(axis_value,str) or axis_value not in AXIS_STATUSES:
                add(e,f"{p} {axis_name} status invalid")
        v=c.get("verdict")
        if not isinstance(v,str) or v not in VERDICTS:
            add(e,f"{p} verdict invalid")
        if c.get("release_blocking") is not (isinstance(v,str) and v in BLOCK): add(e,f"{p} release_blocking mismatch")
        if v=="FAIL_SPEC" and c.get("failure_origin") not in {"FINAL_CARD_SPEC","TRUTH_BOUNDARY","SOURCE_BINDING","MIXED"}: add(e,f"{p} FAIL_SPEC requires failure_origin")
        if v!="FAIL_SPEC" and c.get("failure_origin") is not None: add(e,f"{p} failure_origin only for FAIL_SPEC")
        tid=c.get("repair_ticket_id")
        if isinstance(v,str) and v in FAIL and (not txt(tid) or tid not in tickets): add(e,f"{p} fail requires repair ticket")
        if (not isinstance(v,str) or v not in FAIL) and tid is not None: add(e,f"{p} non-fail cannot have repair ticket")
        vals=[axes.get(x) for x in SEM]; eng=axes.get("ENGINEERING_CONFORMANCE")
        if v=="PASS" and (any(x!="pass" for x in vals) or eng!="pass"): add(e,f"{p} PASS axes mismatch")
        if v=="PASS_WITH_WARNINGS" and any(x in {"fail","unverifiable"} for x in vals): add(e,f"{p} warning verdict contains failed/unverifiable axis")
        if v=="BLOCK_UNVERIFIABLE" and not any(x=="unverifiable" for x in vals): add(e,f"{p} block requires unverifiable axis")
        if isinstance(v,str) and v in FAIL and not any(isinstance(f,dict) and f.get("materiality")=="material" and f.get("axis")!="ENGINEERING_CONFORMANCE" for f in (c.get("findings",[]) if isinstance(c.get("findings",[]),list) else [])): add(e,f"{p} fail requires substantive material finding")
    if len(ids)!=len(set(ids)): add(e,"card ids must be unique")
    dd=b.get("dedup_manifest",{})
    if not isinstance(dd,dict):
        add(e,"dedup_manifest must be object")
        dd={}
    dups=dd.get("duplicates",[])
    if not isinstance(dups,list):
        add(e,"dedup_manifest.duplicates must be array")
        dups=[]
    if dd.get("unique_card_count")!=len(cards) or dd.get("duplicate_count")!=len(dups): add(e,"dedup counts mismatch")
    cs=b.get("cardset_audit",{})
    if not isinstance(cs,dict):
        add(e,"cardset_audit must be object")
        cs={}
    finding_map(cs.get("cross_card_findings"),"cardset findings",e); cexp=cardset_status({**b,"cardset_audit":cs})
    package_coverage=cs.get("package_coverage")
    package_status=package_coverage.get("status") if isinstance(package_coverage,dict) else None
    if not isinstance(package_status,str) or package_status not in PACKAGE_COVERAGE_STATUSES:
        add(e,"cardset_audit.package_coverage.status invalid")
    if cs.get("scope")!="cross_card_and_package_only" or cs.get("status")!=cexp: add(e,f"cardset status must be {cexp}")
    r=b.get("methodological_risk",{})
    if not isinstance(r,dict):
        add(e,"methodological_risk must be object")
        r={}
    rel=relation(r.get("generator_model_family"),r.get("auditor_model_family"))
    if r.get("relationship")!=rel: add(e,f"methodological relationship must be {rel}")
    material,secondary,effect,corr=risk_effect(r)
    if r.get("material_to_run") is not material or r.get("secondary_review_required") is not secondary or r.get("release_effect")!=effect or r.get("correlated_error_risk")!=corr: add(e,"methodological-risk derivation mismatch")
    if r.get("high_stakes_cardset") is True and not r.get("high_stakes_reasons"): add(e,"high-stakes run requires reasons")
    rg=b.get("release_gate",{})
    if not isinstance(rg,dict):
        add(e,"release_gate must be object")
        rg={}
    rexp=release_status({**b,"methodological_risk":r,"cardset_audit":cs})
    if rg.get("status")!=rexp or rg.get("release_allowed") is not (rexp in {"PASS","PASS_WITH_WARNINGS"}): add(e,f"release gate must be {rexp}")
    counts=rg.get("counts",{})
    if not isinstance(counts,dict):
        add(e,"release_gate.counts must be object")
        counts={}
    for v in ("PASS","PASS_WITH_WARNINGS","FAIL_RENDER","FAIL_SPEC","BLOCK_UNVERIFIABLE"):
        if counts.get(v)!=sum(1 for c in cards if isinstance(c,dict) and c.get("verdict")==v): add(e,f"release count {v} mismatch")
    human_display(b,tickets,e)
    p=b.get("provenance",{})
    if not isinstance(p,dict):
        add(e,"provenance must be object")
        p={}
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
