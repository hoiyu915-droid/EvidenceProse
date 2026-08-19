#!/usr/bin/env python3
"""Structural validator for EP_RENDERED_CARD_AUDIT v1.2.

This validator does not infer pixels or scientific truth. It makes PASS structurally
illegal when the audit record has not completed queue-surface authorization,
protected-term, topology/test-identity, and primary-source closure.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

METHOD = "1.3-queue-diff-test-identity"
FAIL = {"FAIL_RENDER", "FAIL_SPEC"}
PASS_QUEUE = {"AUTHORIZED_AND_SUPPORTED", "SEMANTICALLY_EQUIVALENT_PARAPHRASE"}
FAIL_QUEUE = {"SOURCE_SUPPORTED_BUT_NOT_QUEUE_AUTHORIZED", "UNAUTHORIZED_AND_UNSUPPORTED", "SIBLING_CARD_ONLY_AUTHORIZATION", "MATERIAL_RENDERER_AUTHORED_FRAMING"}
BLOCK_QUEUE = {"AUTHORIZATION_UNVERIFIABLE", "AUTHORIZED_BUT_SOURCE_UNVERIFIABLE"}
TEST_FAIL = {"wrong_operator", "wrong_operands", "wrong_outcome", "wrong_conditioning_context", "null_interaction_rendered_as_null_direct_associations", "wrong_test_identity"}
PROTECTED_FAIL = {"corrupted", "invented", "substituted", "wrong_number", "wrong_unit", "wrong_denominator", "wrong_direction"}

def txt(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())

def add(errors: list[str], msg: str) -> None:
    errors.append(msg)

def ids(items: Any, key: str) -> list[str]:
    if not isinstance(items, list):
        return []
    return [x.get(key) for x in items if isinstance(x, dict) and txt(x.get(key))]

def validate_card(card: Any, errors: list[str]) -> None:
    if not isinstance(card, dict):
        add(errors, "card audit must be object")
        return
    cid = card.get("card_id", "?")
    p = f"card {cid}"
    blind = card.get("blind_readback")
    if not isinstance(blind, dict) or blind.get("frozen_before_comparison") is not True:
        add(errors, f"{p} blind_readback must be frozen before comparison")
        return

    nodes = blind.get("content_node_inventory")
    if not isinstance(nodes, list):
        add(errors, f"{p} blind content_node_inventory must be array")
        return
    material_nodes = [n for n in nodes if isinstance(n, dict) and n.get("material") is True]
    node_ids = ids(material_nodes, "observed_node_id")
    if len(node_ids) != len(material_nodes) or len(node_ids) != len(set(node_ids)):
        add(errors, f"{p} every material observed node requires a unique observed_node_id")

    relations = blind.get("relation_inventory")
    if not isinstance(relations, list):
        add(errors, f"{p} blind relation_inventory must be array")
        relations = []
    material_relations = [r for r in relations if isinstance(r, dict) and r.get("material") is True]
    relation_ids = ids(material_relations, "observed_relation_id")
    if len(relation_ids) != len(material_relations) or len(relation_ids) != len(set(relation_ids)):
        add(errors, f"{p} every material observed relation requires a unique observed_relation_id")

    queue = card.get("queue_surface_reconciliation")
    if not isinstance(queue, dict):
        add(errors, f"{p} queue_surface_reconciliation required")
        queue = {}
    qchecks = queue.get("content_node_checks")
    if not isinstance(qchecks, list):
        add(errors, f"{p} queue content_node_checks must be array")
        qchecks = []
    qids = ids(qchecks, "observed_node_id")
    if sorted(qids) != sorted(node_ids) or len(qids) != len(set(qids)):
        add(errors, f"{p} every material observed node must be queue-authorized/dispositioned exactly once")
    queue_fail = queue_block = False
    for i, check in enumerate(qchecks):
        if not isinstance(check, dict):
            add(errors, f"{p} queue check {i} must be object")
            continue
        disp = check.get("disposition")
        if disp in FAIL_QUEUE:
            queue_fail = True
            if not txt(check.get("finding_id")):
                add(errors, f"{p} queue check {i} failure requires finding_id")
        elif disp in BLOCK_QUEUE:
            queue_block = True
            if not txt(check.get("finding_id")):
                add(errors, f"{p} queue check {i} unverifiable requires finding_id")
        elif disp not in PASS_QUEUE:
            add(errors, f"{p} queue check {i} disposition invalid")
    qcomp = queue.get("completion", {})
    if qcomp.get("all_observed_material_nodes_checked") is not (sorted(qids) == sorted(node_ids) and len(qids) == len(set(qids))):
        add(errors, f"{p} queue completion mismatch")
    if qcomp.get("current_card_only_authorization_used") is not True:
        add(errors, f"{p} sibling/ambient authorization shortcut forbidden")
    if qcomp.get("source_support_not_used_as_authorization") is not True:
        add(errors, f"{p} source support cannot substitute for queue authorization")

    test = card.get("test_identity_reconciliation")
    if not isinstance(test, dict):
        add(errors, f"{p} test_identity_reconciliation required")
        test = {}
    tchecks = test.get("relation_checks")
    if not isinstance(tchecks, list):
        add(errors, f"{p} test relation_checks must be array")
        tchecks = []
    tids = ids(tchecks, "observed_relation_id")
    if sorted(tids) != sorted(relation_ids) or len(tids) != len(set(tids)):
        add(errors, f"{p} every material observed relation must receive test-identity disposition exactly once")
    test_fail = test_block = False
    for i, check in enumerate(tchecks):
        if not isinstance(check, dict):
            add(errors, f"{p} test check {i} must be object")
            continue
        for field in ("observed_operands", "observed_operator", "observed_outcome", "observed_conditioning_context"):
            if field not in check:
                add(errors, f"{p} test check {i} missing {field}")
        status = check.get("status")
        if status in TEST_FAIL:
            test_fail = True
            if not txt(check.get("finding_id")):
                add(errors, f"{p} test check {i} failure requires finding_id")
        elif status == "unverifiable":
            test_block = True
            if not txt(check.get("finding_id")):
                add(errors, f"{p} test check {i} unverifiable requires finding_id")
        elif status not in {"equivalent", "not_applicable"}:
            add(errors, f"{p} test check {i} status invalid")
    tcomp = test.get("completion", {})
    if tcomp.get("all_material_relations_checked") is not (sorted(tids) == sorted(relation_ids) and len(tids) == len(set(tids))):
        add(errors, f"{p} test-identity completion mismatch")
    if tcomp.get("direct_association_not_substituted_for_interaction") is not True:
        add(errors, f"{p} direct-association/interaction substitution gate not completed")

    protected = card.get("protected_term_reconciliation")
    if not isinstance(protected, dict):
        add(errors, f"{p} protected_term_reconciliation required")
        protected = {}
    protected_nodes = [n for n in material_nodes if n.get("protected_term") is True]
    protected_ids = ids(protected_nodes, "observed_node_id")
    pchecks = protected.get("checks")
    if not isinstance(pchecks, list):
        add(errors, f"{p} protected term checks must be array")
        pchecks = []
    pids = ids(pchecks, "observed_node_id")
    if sorted(pids) != sorted(protected_ids) or len(pids) != len(set(pids)):
        add(errors, f"{p} every protected material term must be checked exactly once")
    protected_fail = protected_block = False
    for i, check in enumerate(pchecks):
        status = check.get("status") if isinstance(check, dict) else None
        if status in PROTECTED_FAIL:
            protected_fail = True
            if not txt(check.get("finding_id")):
                add(errors, f"{p} protected check {i} failure requires finding_id")
        elif status == "unverifiable":
            protected_block = True
        elif status not in {"exact", "semantically_equivalent"}:
            add(errors, f"{p} protected check {i} status invalid")

    source = card.get("source_surface_reconciliation")
    if not isinstance(source, dict) or source.get("completion", {}).get("all_material_nodes_source_checked") is not True:
        add(errors, f"{p} primary-source surface closure incomplete")

    topology = card.get("visual_semantic_reconciliation")
    if not isinstance(topology, dict) or topology.get("topology_completion", {}).get("complete") is not True:
        add(errors, f"{p} topology closure incomplete")

    verdict = card.get("verdict")
    any_block = queue_block or test_block or protected_block
    any_fail = queue_fail or test_fail or protected_fail
    if any_block and verdict != "BLOCK_UNVERIFIABLE":
        add(errors, f"{p} material unverifiable closure requires BLOCK_UNVERIFIABLE")
    if any_fail and verdict not in FAIL:
        add(errors, f"{p} declared material render/spec failure cannot PASS")
    if verdict == "PASS":
        gate = card.get("pass_gate", {})
        required = ("topology_complete", "test_identity_complete", "queue_surface_complete", "source_surface_complete", "protected_terms_complete", "sibling_leakage_absent", "material_framing_additions_absent")
        for key in required:
            if gate.get(key) is not True:
                add(errors, f"{p} PASS illegal: pass_gate.{key} must be true")
        if any_fail or any_block:
            add(errors, f"{p} PASS illegal with material failure/unverifiable disposition")

def validate_bundle(bundle: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(bundle, dict):
        return ["bundle must be object"]
    if bundle.get("contract_version") != "1.2":
        add(errors, "contract_version must be 1.2")
    if bundle.get("method_revision") != METHOD:
        add(errors, f"method_revision must be {METHOD}")
    cards = bundle.get("card_audits")
    if not isinstance(cards, list) or not cards:
        add(errors, "card_audits must be non-empty")
        return errors
    for card in cards:
        validate_card(card, errors)
    return errors

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
        errors = validate_bundle(bundle)
    except (OSError, json.JSONDecodeError) as exc:
        errors = [str(exc)]
    result = {"status": "pass" if not errors else "fail", "method_revision": METHOD, "errors": errors}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True) if args.json else ("PASS" if not errors else "\n".join(errors)))
    return 0 if not errors else 1

if __name__ == "__main__":
    raise SystemExit(main())
