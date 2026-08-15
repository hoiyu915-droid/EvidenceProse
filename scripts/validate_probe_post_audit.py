#!/usr/bin/env python3
"""Validate an EvidenceProse Probe post-audit transform bundle.

The validator is intentionally narrow: it checks transformation integrity,
audit-finding closure, package coverage, change scope, and declared hard guards.
It does not redo TA06 source audit or Claude semantic judgment.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HARD_GUARDS = (
    "no_new_epistemic_content",
    "claim_strength_preserved",
    "numeric_fidelity",
    "required_qualifiers_preserved",
    "forbidden_overclaims_absent",
    "cross_card_consistency",
    "package_coverage_complete",
    "article_card_alignment",
    "edit_scope_respected",
)
KINDS = {"KEEP", "PATCH", "MERGE", "RECOMPOSE", "REGENERATE"}
ARTICLE_ACTIONS = {
    "reorder",
    "compress",
    "expand_supported_explanation",
    "simplify",
    "strengthen_rhetoric",
    "add_supported_bridge",
    "retitle",
}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sha(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def _list_of_strings(value: Any, *, nonempty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (not nonempty or bool(value))
        and all(_nonempty(x) for x in value)
        and len(value) == len(set(value))
    )


def validate_bundle(bundle: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(bundle, dict):
        return ["bundle must be a JSON object"]

    required = {
        "contract_version", "run_id", "producer", "inputs", "scope",
        "audit_findings", "operations", "article_rewrite", "coverage",
        "semantic_guard", "outputs", "final_gate",
    }
    missing = sorted(required - set(bundle))
    if missing:
        errors.append(f"bundle missing required fields: {missing}")

    if bundle.get("contract_version") != "1.0":
        errors.append("contract_version must be 1.0")
    if bundle.get("producer") != "Probe":
        errors.append("producer must be Probe")
    if not _nonempty(bundle.get("run_id")):
        errors.append("run_id must be non-empty")

    inputs = bundle.get("inputs")
    if not isinstance(inputs, dict):
        errors.append("inputs must be an object")
        inputs = {}
    for key in ("truth_boundary_digest", "claude_audit_digest", "source_article_digest"):
        if not _sha(inputs.get(key)):
            errors.append(f"inputs.{key} must be lowercase SHA-256")
    source_card_digests = inputs.get("source_card_digests")
    if not isinstance(source_card_digests, dict) or not source_card_digests:
        errors.append("inputs.source_card_digests must be a non-empty object")
        source_card_digests = {}
    else:
        for card_id, digest in source_card_digests.items():
            if not _nonempty(card_id) or not _sha(digest):
                errors.append(f"invalid source-card digest binding for {card_id!r}")

    scope = bundle.get("scope")
    if not isinstance(scope, dict):
        errors.append("scope must be an object")
        scope = {}
    source_card_ids = scope.get("source_card_ids")
    target_card_ids = scope.get("target_card_ids")
    if not _list_of_strings(source_card_ids, nonempty=True):
        errors.append("scope.source_card_ids must be a non-empty unique string array")
        source_card_ids = []
    if not _list_of_strings(target_card_ids, nonempty=True):
        errors.append("scope.target_card_ids must be a non-empty unique string array")
        target_card_ids = []
    if set(source_card_ids) != set(source_card_digests):
        errors.append("scope.source_card_ids must exactly match inputs.source_card_digests keys")
    if not _nonempty(scope.get("article_id")):
        errors.append("scope.article_id must be non-empty")

    findings = bundle.get("audit_findings")
    finding_map: dict[str, dict[str, Any]] = {}
    if not isinstance(findings, list):
        errors.append("audit_findings must be an array")
        findings = []
    for index, finding in enumerate(findings):
        label = f"audit_findings[{index}]"
        if not isinstance(finding, dict):
            errors.append(f"{label} must be an object")
            continue
        fid = finding.get("finding_id")
        if not _nonempty(fid):
            errors.append(f"{label}.finding_id must be non-empty")
            continue
        if fid in finding_map:
            errors.append(f"duplicate finding_id {fid}")
        finding_map[fid] = finding
        severity = finding.get("severity")
        status = finding.get("status")
        if severity not in {"hard", "warning"}:
            errors.append(f"{label}.severity is invalid")
        if status not in {"resolved", "accepted_warning"}:
            errors.append(f"{label}.status is invalid")
        if severity == "hard" and status != "resolved":
            errors.append(f"hard finding {fid} must be resolved")
        if status == "accepted_warning" and severity != "warning":
            errors.append(f"only warning findings may be accepted_warning: {fid}")
        if not _nonempty(finding.get("reason")):
            errors.append(f"{label}.reason must be non-empty")
        if not _list_of_strings(finding.get("operation_ids")):
            errors.append(f"{label}.operation_ids must be a unique string array")

    operations = bundle.get("operations")
    operation_map: dict[str, dict[str, Any]] = {}
    scope_error = False
    if not isinstance(operations, list) or not operations:
        errors.append("operations must be a non-empty array")
        operations = []
    for index, op in enumerate(operations):
        label = f"operations[{index}]"
        if not isinstance(op, dict):
            errors.append(f"{label} must be an object")
            continue
        oid = op.get("operation_id")
        if not _nonempty(oid):
            errors.append(f"{label}.operation_id must be non-empty")
            continue
        if oid in operation_map:
            errors.append(f"duplicate operation_id {oid}")
        operation_map[oid] = op
        if op.get("kind") not in KINDS:
            errors.append(f"{label}.kind is invalid")
        for field in (
            "source_card_ids", "target_card_ids", "finding_ids", "claim_ids",
            "expected_changed_element_ids", "actual_changed_element_ids",
        ):
            if not _list_of_strings(op.get(field), nonempty=(field == "target_card_ids")):
                errors.append(f"{label}.{field} must be a unique string array")
        if op.get("introduces_new_epistemic_content") is not False:
            errors.append(f"{label}.introduces_new_epistemic_content must be false")
        if not isinstance(op.get("scope_expansion_authorized"), bool):
            errors.append(f"{label}.scope_expansion_authorized must be boolean")
        if not _nonempty(op.get("reason")):
            errors.append(f"{label}.reason must be non-empty")

        unexpected = set(op.get("actual_changed_element_ids") or []) - set(
            op.get("expected_changed_element_ids") or []
        )
        if unexpected and op.get("scope_expansion_authorized") is not True:
            scope_error = True
            errors.append(
                f"{label} changed elements outside declared scope without authorization: {sorted(unexpected)}"
            )
        for fid in op.get("finding_ids") or []:
            if fid not in finding_map:
                errors.append(f"{label}.finding_ids references unknown finding {fid}")

    for fid, finding in finding_map.items():
        for oid in finding.get("operation_ids") or []:
            if oid not in operation_map:
                errors.append(f"finding {fid} references unknown operation {oid}")

    article = bundle.get("article_rewrite")
    if not isinstance(article, dict):
        errors.append("article_rewrite must be an object")
        article = {}
    if not isinstance(article.get("performed"), bool):
        errors.append("article_rewrite.performed must be boolean")
    if article.get("source_article_digest") != inputs.get("source_article_digest"):
        errors.append("article_rewrite.source_article_digest must match inputs.source_article_digest")
    if not _sha(article.get("output_article_digest")):
        errors.append("article_rewrite.output_article_digest must be lowercase SHA-256")
    actions = article.get("actions")
    if not isinstance(actions, list) or len(actions) != len(set(actions)) or any(a not in ARTICLE_ACTIONS for a in actions):
        errors.append("article_rewrite.actions contains invalid or duplicate actions")
    if article.get("new_claim_ids") != []:
        errors.append("article_rewrite.new_claim_ids must be empty")
    if article.get("removed_material_claim_ids") != []:
        errors.append("article_rewrite.removed_material_claim_ids must be empty")
    if article.get("claim_strength_changed") is not False:
        errors.append("article_rewrite.claim_strength_changed must be false")

    coverage = bundle.get("coverage")
    coverage_error = False
    if not isinstance(coverage, dict):
        errors.append("coverage must be an object")
        coverage = {}
    required_claims = coverage.get("required_claim_ids")
    represented = coverage.get("represented_claim_ids")
    if not _list_of_strings(required_claims):
        errors.append("coverage.required_claim_ids must be a unique string array")
        required_claims = []
    if not _list_of_strings(represented):
        errors.append("coverage.represented_claim_ids must be a unique string array")
        represented = []
    omitted = coverage.get("omitted_claims")
    omitted_ids: set[str] = set()
    if not isinstance(omitted, list):
        errors.append("coverage.omitted_claims must be an array")
        omitted = []
    for index, item in enumerate(omitted):
        label = f"coverage.omitted_claims[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        cid = item.get("claim_id")
        if not _nonempty(cid):
            errors.append(f"{label}.claim_id must be non-empty")
            continue
        if cid in omitted_ids:
            errors.append(f"duplicate omitted claim {cid}")
        omitted_ids.add(cid)
        if item.get("disposition") not in {"out_of_scope", "blocked_upstream", "deferred"}:
            errors.append(f"{label}.disposition is invalid")
        if not _nonempty(item.get("reason")):
            errors.append(f"{label}.reason must be non-empty")
    overlap = set(represented) & omitted_ids
    if overlap:
        coverage_error = True
        errors.append(f"claims cannot be both represented and omitted: {sorted(overlap)}")
    uncovered = set(required_claims) - set(represented) - omitted_ids
    if uncovered:
        coverage_error = True
        errors.append(f"required claims lack representation or disposition: {sorted(uncovered)}")

    guard = bundle.get("semantic_guard")
    if not isinstance(guard, dict):
        errors.append("semantic_guard must be an object")
        guard = {}
    for check in HARD_GUARDS:
        if guard.get(check) not in {"pass", "fail"}:
            errors.append(f"semantic_guard.{check} must be pass/fail")
    unexpected_guard = set(guard) - set(HARD_GUARDS)
    if unexpected_guard:
        errors.append(f"semantic_guard has unexpected checks: {sorted(unexpected_guard)}")
    if scope_error and guard.get("edit_scope_respected") == "pass":
        errors.append("semantic_guard.edit_scope_respected cannot pass when change scope is violated")
    if coverage_error and guard.get("package_coverage_complete") == "pass":
        errors.append("semantic_guard.package_coverage_complete cannot pass when coverage is incomplete")

    outputs = bundle.get("outputs")
    if not isinstance(outputs, dict):
        errors.append("outputs must be an object")
        outputs = {}
    if outputs.get("article_id") != scope.get("article_id"):
        errors.append("outputs.article_id must match scope.article_id")
    if outputs.get("article_digest") != article.get("output_article_digest"):
        errors.append("outputs.article_digest must match article_rewrite.output_article_digest")
    card_digests = outputs.get("card_digests")
    if not isinstance(card_digests, dict) or not card_digests:
        errors.append("outputs.card_digests must be a non-empty object")
        card_digests = {}
    else:
        for card_id, digest in card_digests.items():
            if not _nonempty(card_id) or not _sha(digest):
                errors.append(f"invalid output-card digest binding for {card_id!r}")
    if set(card_digests) != set(target_card_ids):
        errors.append("outputs.card_digests keys must exactly match scope.target_card_ids")

    guards_pass = all(guard.get(check) == "pass" for check in HARD_GUARDS)
    findings_pass = all(
        isinstance(f, dict) and (f.get("severity") != "hard" or f.get("status") == "resolved")
        for f in findings
    )
    article_pass = (
        article.get("new_claim_ids") == []
        and article.get("removed_material_claim_ids") == []
        and article.get("claim_strength_changed") is False
    )
    expected_gate = "pass" if guards_pass and findings_pass and article_pass and not scope_error and not coverage_error else "fail"

    final_gate = bundle.get("final_gate")
    if not isinstance(final_gate, dict):
        errors.append("final_gate must be an object")
    else:
        if final_gate.get("status") != expected_gate:
            errors.append(f"final_gate.status must be {expected_gate} from hard guards and transform state")
        if not _nonempty(final_gate.get("rationale")):
            errors.append("final_gate.rationale must be non-empty")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    except OSError as exc:
        errors = [f"cannot read {args.bundle}: {exc}"]
    except json.JSONDecodeError as exc:
        errors = [f"invalid JSON at {exc.lineno}:{exc.colno}: {exc.msg}"]
    else:
        errors = validate_bundle(bundle)

    result = {"status": "pass" if not errors else "fail", "errors": errors}
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    else:
        print("Probe post-audit bundle: PASS")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
