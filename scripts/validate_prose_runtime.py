#!/usr/bin/env python3
"""Validate a TA06-backed EvidenceProse runtime bundle.

This validator is deliberately structural and consistency-oriented. It verifies
binding, permission projection, digests, declared semantic-gate state,
reader-outcome state, repair state, and the public delivery shell. It does not
claim that deterministic string matching can prove scientific truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from validate_explainer_output import validate_text as validate_delivery_text


HARD_CHECKS = (
    "no_loss",
    "no_add",
    "numeric_fidelity",
    "denominator_fidelity",
    "comparator_fidelity",
    "timeframe_fidelity",
    "population_scope_fidelity",
    "causal_strength_fidelity",
    "uncertainty_fidelity",
    "evidence_role_fidelity",
    "attribution_fidelity",
    "source_layer_fidelity",
    "required_qualifiers_present",
    "forbidden_overclaims_absent",
    "headline_not_stronger_than_body",
    "analogy_not_presented_as_mechanism",
    "practical_meaning_not_upgraded_to_recommendation",
)
READER_AXES = ("relevant", "findable", "understandable", "usable")
LINT_CATEGORIES = {
    "long_sentence",
    "long_paragraph",
    "de_chain",
    "vague_pronoun",
    "unnecessary_code_switching",
    "passive_voice",
    "hedge_stack",
    "jargon_density",
}


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: Path, label: str, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"{label}: cannot read {path}: {exc}")
    except json.JSONDecodeError as exc:
        errors.append(f"{label}: invalid JSON at {exc.lineno}:{exc.colno}: {exc.msg}")
    return None


def _require_object(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return value


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_handoff(handoff: Any) -> list[str]:
    errors: list[str] = []
    h = _require_object(handoff, "handoff", errors)
    if not h:
        return errors

    for field in (
        "contract_version", "handoff_id", "producer", "consumer", "ta06_packet",
        "reader_context", "claims", "evidence", "citations", "terminology",
        "numeric_ledger", "permission",
    ):
        if field not in h:
            errors.append(f"handoff missing required field {field}")

    if h.get("contract_version") != "1.0":
        errors.append("handoff.contract_version must be 1.0")
    if h.get("producer") != "TA06":
        errors.append("handoff.producer must be TA06")
    if h.get("consumer") != "EvidenceProse":
        errors.append("handoff.consumer must be EvidenceProse")

    packet = h.get("ta06_packet")
    if isinstance(packet, dict):
        if packet.get("status") != "pass":
            errors.append("handoff.ta06_packet.status must be pass")
        if packet.get("execution_profile") not in {"lite", "numeric", "full"}:
            errors.append("handoff.ta06_packet.execution_profile is invalid")
        if not isinstance(packet.get("source_count"), int) or packet.get("source_count", 0) < 1:
            errors.append("handoff.ta06_packet.source_count must be >= 1")
        digest = packet.get("packet_digest")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            errors.append("handoff.ta06_packet.packet_digest must be a lowercase SHA-256")
    else:
        errors.append("handoff.ta06_packet must be an object")

    claims = h.get("claims")
    claim_map: dict[str, dict[str, Any]] = {}
    if not isinstance(claims, list) or not claims:
        errors.append("handoff.claims must be a non-empty array")
    else:
        for index, claim in enumerate(claims):
            label = f"handoff.claims[{index}]"
            if not isinstance(claim, dict):
                errors.append(f"{label} must be an object")
                continue
            cid = claim.get("claim_id")
            if not _nonempty_string(cid):
                errors.append(f"{label}.claim_id must be non-empty")
                continue
            if cid in claim_map:
                errors.append(f"duplicate claim_id {cid}")
            claim_map[cid] = claim
            if claim.get("permission") not in {"allowed", "conditional", "forbidden"}:
                errors.append(f"{label}.permission is invalid")
            if claim.get("label") not in {"CORE", "INFERENCE", "GAP", "CONFLICT"}:
                errors.append(f"{label}.label is invalid")
            if claim.get("support_state") not in {
                "supported", "mixed", "plausible_unverified", "unsupported", "conflicted"
            }:
                errors.append(f"{label}.support_state is invalid")
            if claim.get("permission") == "conditional" and not _nonempty_string(claim.get("condition_if_any")):
                errors.append(f"{label} is conditional but condition_if_any is empty")
            if claim.get("permission") in {"allowed", "conditional"}:
                locators = claim.get("source_locators")
                if not isinstance(locators, list) or not any(_nonempty_string(x) for x in locators):
                    errors.append(f"{label} is releasable but has no source locator")

    evidence = h.get("evidence")
    if not isinstance(evidence, list):
        errors.append("handoff.evidence must be an array")
    else:
        evidence_ids: set[str] = set()
        for index, item in enumerate(evidence):
            label = f"handoff.evidence[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{label} must be an object")
                continue
            eid = item.get("evidence_id")
            if not _nonempty_string(eid):
                errors.append(f"{label}.evidence_id must be non-empty")
            elif eid in evidence_ids:
                errors.append(f"duplicate evidence_id {eid}")
            else:
                evidence_ids.add(eid)
            cid = item.get("claim_id")
            if cid not in claim_map:
                errors.append(f"{label}.claim_id {cid!r} does not resolve to a claim")
            if not _nonempty_string(item.get("source_locator")):
                errors.append(f"{label}.source_locator must be non-empty")
            if not _nonempty_string(item.get("evidence_role")):
                errors.append(f"{label}.evidence_role must be non-empty")

    numeric = h.get("numeric_ledger")
    if not isinstance(numeric, list):
        errors.append("handoff.numeric_ledger must be an array")
    else:
        ledger_ids: set[str] = set()
        for index, item in enumerate(numeric):
            label = f"handoff.numeric_ledger[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{label} must be an object")
                continue
            lid = item.get("ledger_id")
            if not _nonempty_string(lid):
                errors.append(f"{label}.ledger_id must be non-empty")
            elif lid in ledger_ids:
                errors.append(f"duplicate ledger_id {lid}")
            else:
                ledger_ids.add(lid)
            cid = item.get("claim_id")
            if cid not in claim_map:
                errors.append(f"{label}.claim_id {cid!r} does not resolve to a claim")
            if item.get("transformation_state") not in {"direct", "derived"}:
                errors.append(f"{label}.transformation_state is invalid")
            if not _nonempty_string(item.get("source_locator")):
                errors.append(f"{label}.source_locator must be non-empty")

    permission = h.get("permission")
    if isinstance(permission, dict):
        doc_permission = permission.get("document_permission")
        if doc_permission not in {"allowed", "conditional", "forbidden"}:
            errors.append("handoff.permission.document_permission is invalid")
        if doc_permission == "forbidden":
            errors.append("handoff document_permission is forbidden; live prose lane must stop")

        released = permission.get("released_claim_ids")
        blocked = permission.get("blocked_claim_ids")
        if not isinstance(released, list) or not isinstance(blocked, list):
            errors.append("handoff permission released_claim_ids/blocked_claim_ids must be arrays")
        else:
            expected_released = {
                cid for cid, claim in claim_map.items()
                if claim.get("permission") in {"allowed", "conditional"}
            }
            expected_blocked = {
                cid for cid, claim in claim_map.items()
                if claim.get("permission") == "forbidden"
            }
            if set(released) != expected_released:
                errors.append(
                    "handoff.permission.released_claim_ids must exactly equal allowed+conditional claims"
                )
            if set(blocked) != expected_blocked:
                errors.append(
                    "handoff.permission.blocked_claim_ids must exactly equal forbidden claims"
                )
            overlap = set(released) & set(blocked)
            if overlap:
                errors.append(f"claims cannot be both released and blocked: {sorted(overlap)}")
    else:
        errors.append("handoff.permission must be an object")

    return errors


def validate_reader_contract(reader: Any, *, handoff_digest: str) -> list[str]:
    errors: list[str] = []
    r = _require_object(reader, "reader_contract", errors)
    if not r:
        return errors

    required = (
        "contract_version", "article_id", "handoff_digest", "audience", "purpose",
        "reader_question", "intended_takeaway", "forbidden_takeaway", "central_claim",
        "evidence_weight", "limitations", "applicability", "misuse_boundaries",
        "resolution_source",
    )
    for field in required:
        if field not in r:
            errors.append(f"reader_contract missing required field {field}")
    if r.get("contract_version") != "1.0":
        errors.append("reader_contract.contract_version must be 1.0")
    if r.get("handoff_digest") != handoff_digest:
        errors.append("reader_contract.handoff_digest does not match canonical handoff digest")
    if r.get("resolution_source") not in {
        "explicit_user", "ta06_input", "local_rendering_default"
    }:
        errors.append("reader_contract.resolution_source is invalid")
    if r.get("local_default_is_user_fact", False) is not False:
        errors.append("reader_contract.local_default_is_user_fact must be false")
    for field in required:
        if field in {"contract_version", "handoff_digest", "resolution_source"}:
            continue
        if not _nonempty_string(r.get(field)):
            errors.append(f"reader_contract.{field} must be non-empty")
    return errors


def validate_sidecar(
    sidecar: Any,
    *,
    handoff_digest: str,
    reader_digest: str,
    article_id: str,
) -> list[str]:
    errors: list[str] = []
    s = _require_object(sidecar, "audit_sidecar", errors)
    if not s:
        return errors

    if s.get("contract_version") != "1.0":
        errors.append("audit_sidecar.contract_version must be 1.0")
    if s.get("article_id") != article_id:
        errors.append("audit_sidecar.article_id must match reader_contract.article_id")
    if s.get("handoff_digest") != handoff_digest:
        errors.append("audit_sidecar.handoff_digest does not match canonical handoff digest")
    if s.get("reader_contract_digest") != reader_digest:
        errors.append(
            "audit_sidecar.reader_contract_digest does not match canonical reader-contract digest"
        )

    guard = s.get("semantic_guard")
    if not isinstance(guard, dict):
        errors.append("audit_sidecar.semantic_guard must be an object")
        guard = {}
    for check in HARD_CHECKS:
        if guard.get(check) not in {"pass", "fail"}:
            errors.append(f"audit_sidecar.semantic_guard.{check} must be pass/fail")
    unexpected = set(guard) - set(HARD_CHECKS)
    if unexpected:
        errors.append(f"audit_sidecar.semantic_guard has unexpected checks: {sorted(unexpected)}")

    outcomes = s.get("reader_outcomes")
    if not isinstance(outcomes, dict):
        errors.append("audit_sidecar.reader_outcomes must be an object")
        outcomes = {}
    for axis in READER_AXES:
        item = outcomes.get(axis)
        if not isinstance(item, dict):
            errors.append(f"audit_sidecar.reader_outcomes.{axis} must be an object")
            continue
        if item.get("status") not in {"pass", "warning", "fail"}:
            errors.append(f"audit_sidecar.reader_outcomes.{axis}.status is invalid")
        if not isinstance(item.get("note"), str):
            errors.append(f"audit_sidecar.reader_outcomes.{axis}.note must be a string")

    lints = s.get("lint_warnings")
    if not isinstance(lints, list):
        errors.append("audit_sidecar.lint_warnings must be an array")
    else:
        for index, item in enumerate(lints):
            if not isinstance(item, dict):
                errors.append(f"audit_sidecar.lint_warnings[{index}] must be an object")
                continue
            if item.get("category") not in LINT_CATEGORIES:
                errors.append(f"audit_sidecar.lint_warnings[{index}].category is invalid")

    repairs = s.get("targeted_repairs")
    if not isinstance(repairs, list):
        errors.append("audit_sidecar.targeted_repairs must be an array")
        repairs = []

    final_gate = s.get("final_gate")
    if not isinstance(final_gate, dict):
        errors.append("audit_sidecar.final_gate must be an object")
        return errors

    semantic_pass = all(guard.get(check) == "pass" for check in HARD_CHECKS)
    reader_pass = all(
        isinstance(outcomes.get(axis), dict)
        and outcomes[axis].get("status") != "fail"
        for axis in READER_AXES
    )
    repairs_verified = all(
        isinstance(item, dict) and item.get("status") == "verified"
        for item in repairs
    )
    expected = "pass" if semantic_pass and reader_pass and repairs_verified else "fail"
    if final_gate.get("status") != expected:
        errors.append(
            f"audit_sidecar.final_gate.status must be {expected} from semantic/readability/repair state"
        )
    if not _nonempty_string(final_gate.get("rationale")):
        errors.append("audit_sidecar.final_gate.rationale must be non-empty")

    if not isinstance(s.get("missing_action_info"), list):
        errors.append("audit_sidecar.missing_action_info must be an array")
    if not isinstance(s.get("violations"), list):
        errors.append("audit_sidecar.violations must be an array")

    return errors


def validate_bundle(
    *,
    handoff_path: Path,
    reader_path: Path,
    sidecar_path: Path,
    article_path: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    handoff = _load_json(handoff_path, "handoff", errors)
    reader = _load_json(reader_path, "reader_contract", errors)
    sidecar = _load_json(sidecar_path, "audit_sidecar", errors)

    try:
        article_text = article_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"article: cannot read {article_path}: {exc}")
        article_text = ""

    if handoff is not None:
        errors.extend(validate_handoff(handoff))
        handoff_digest = canonical_digest(handoff)
    else:
        handoff_digest = ""

    if reader is not None and handoff_digest:
        errors.extend(validate_reader_contract(reader, handoff_digest=handoff_digest))
        reader_digest = canonical_digest(reader)
        article_id = reader.get("article_id", "") if isinstance(reader, dict) else ""
    else:
        reader_digest = ""
        article_id = ""

    if sidecar is not None and handoff_digest and reader_digest:
        errors.extend(
            validate_sidecar(
                sidecar,
                handoff_digest=handoff_digest,
                reader_digest=reader_digest,
                article_id=article_id,
            )
        )

    if article_text:
        for error in validate_delivery_text(article_text, filename=article_path.name):
            errors.append(f"article delivery: {error}")

    return {
        "status": "pass" if not errors else "fail",
        "handoff_digest": handoff_digest or None,
        "reader_contract_digest": reader_digest or None,
        "article": str(article_path),
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a TA06-backed EvidenceProse prose runtime bundle"
    )
    parser.add_argument("--handoff", required=True)
    parser.add_argument("--reader-contract", required=True)
    parser.add_argument("--audit-sidecar", required=True)
    parser.add_argument("--article", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = validate_bundle(
        handoff_path=Path(args.handoff),
        reader_path=Path(args.reader_contract),
        sidecar_path=Path(args.audit_sidecar),
        article_path=Path(args.article),
    )
    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"{report['status'].upper()}: {report['article']}")
        if report["handoff_digest"]:
            print(f"  handoff_digest: {report['handoff_digest']}")
        if report["reader_contract_digest"]:
            print(f"  reader_contract_digest: {report['reader_contract_digest']}")
        for error in report["errors"]:
            print(f"  - {error}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
