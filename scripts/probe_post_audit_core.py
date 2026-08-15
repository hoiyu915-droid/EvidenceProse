"""Core declared-state validation for Probe v1.0 and v1.1 bundles."""

from __future__ import annotations

from typing import Any

from probe_post_audit_common import (
    ARTICLE_ACTIONS, BASE_GUARDS, KINDS, V11_GUARDS, _sha, _strings, _text,
)


def _validate_core(bundle: dict[str, Any], version: str, errors: list[str]) -> dict[str, Any]:
    required = {
        "contract_version", "run_id", "producer", "inputs", "scope",
        "audit_findings", "operations", "article_rewrite", "coverage",
        "semantic_guard", "outputs", "final_gate",
    }
    if version == "1.1":
        required |= {"artifact_verification", "reader_reconstruction"}
    missing = sorted(required - set(bundle))
    if missing:
        errors.append(f"bundle missing required fields: {missing}")
    if bundle.get("producer") != "Probe":
        errors.append("producer must be Probe")
    if not _text(bundle.get("run_id")):
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
            if not _text(card_id) or not _sha(digest):
                errors.append(f"invalid source-card digest binding for {card_id!r}")

    scope = bundle.get("scope")
    if not isinstance(scope, dict):
        errors.append("scope must be an object")
        scope = {}
    source_ids = scope.get("source_card_ids")
    target_ids = scope.get("target_card_ids")
    if not _strings(source_ids, nonempty=True):
        errors.append("scope.source_card_ids must be a non-empty unique string array")
        source_ids = []
    if not _strings(target_ids, nonempty=True):
        errors.append("scope.target_card_ids must be a non-empty unique string array")
        target_ids = []
    if set(source_ids) != set(source_card_digests):
        errors.append("scope.source_card_ids must exactly match inputs.source_card_digests keys")
    if not _text(scope.get("article_id")):
        errors.append("scope.article_id must be non-empty")

    findings = bundle.get("audit_findings")
    finding_map: dict[str, dict[str, Any]] = {}
    if not isinstance(findings, list):
        errors.append("audit_findings must be an array")
        findings = []
    for index, finding in enumerate(findings):
        label = f"audit_findings[{index}]"
        if not isinstance(finding, dict) or not _text(finding.get("finding_id")):
            errors.append(f"{label}.finding_id must be non-empty")
            continue
        finding_id = finding["finding_id"]
        if finding_id in finding_map:
            errors.append(f"duplicate finding_id {finding_id}")
        finding_map[finding_id] = finding
        severity = finding.get("severity")
        status = finding.get("status")
        if severity not in {"hard", "warning"}:
            errors.append(f"{label}.severity is invalid")
        if status not in {"resolved", "accepted_warning"}:
            errors.append(f"{label}.status is invalid")
        if severity == "hard" and status != "resolved":
            errors.append(f"hard finding {finding_id} must be resolved")
        if status == "accepted_warning" and severity != "warning":
            errors.append(f"only warning findings may be accepted_warning: {finding_id}")
        if not _text(finding.get("reason")):
            errors.append(f"{label}.reason must be non-empty")
        if not _strings(finding.get("operation_ids")):
            errors.append(f"{label}.operation_ids must be a unique string array")

    operations = bundle.get("operations")
    operation_map: dict[str, dict[str, Any]] = {}
    declared_changes: set[str] = set()
    scope_error = False
    if not isinstance(operations, list) or not operations:
        errors.append("operations must be a non-empty array")
        operations = []
    for index, operation in enumerate(operations):
        label = f"operations[{index}]"
        if not isinstance(operation, dict) or not _text(operation.get("operation_id")):
            errors.append(f"{label}.operation_id must be non-empty")
            continue
        operation_id = operation["operation_id"]
        if operation_id in operation_map:
            errors.append(f"duplicate operation_id {operation_id}")
        operation_map[operation_id] = operation
        if operation.get("kind") not in KINDS:
            errors.append(f"{label}.kind is invalid")
        for field in (
            "source_card_ids", "target_card_ids", "finding_ids", "claim_ids",
            "expected_changed_element_ids", "actual_changed_element_ids",
        ):
            if not _strings(operation.get(field), nonempty=(field == "target_card_ids")):
                errors.append(f"{label}.{field} must be a unique string array")
        if operation.get("introduces_new_epistemic_content") is not False:
            errors.append(f"{label}.introduces_new_epistemic_content must be false")
        if not isinstance(operation.get("scope_expansion_authorized"), bool):
            errors.append(f"{label}.scope_expansion_authorized must be boolean")
        if not _text(operation.get("reason")):
            errors.append(f"{label}.reason must be non-empty")
        expected = set(operation.get("expected_changed_element_ids") or [])
        actual = set(operation.get("actual_changed_element_ids") or [])
        declared_changes |= actual
        unexpected = actual - expected
        if unexpected and operation.get("scope_expansion_authorized") is not True:
            scope_error = True
            errors.append(
                f"{label} changed elements outside declared scope without authorization: {sorted(unexpected)}"
            )
        for finding_id in operation.get("finding_ids") or []:
            if finding_id not in finding_map:
                errors.append(f"{label}.finding_ids references unknown finding {finding_id}")
    for finding_id, finding in finding_map.items():
        for operation_id in finding.get("operation_ids") or []:
            if operation_id not in operation_map:
                errors.append(f"finding {finding_id} references unknown operation {operation_id}")

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
    if not isinstance(actions, list) or len(actions) != len(set(actions)) or any(
        action not in ARTICLE_ACTIONS for action in actions
    ):
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
    if not _strings(required_claims):
        errors.append("coverage.required_claim_ids must be a unique string array")
        required_claims = []
    if not _strings(represented):
        errors.append("coverage.represented_claim_ids must be a unique string array")
        represented = []
    omitted = coverage.get("omitted_claims")
    omitted_ids: set[str] = set()
    if not isinstance(omitted, list):
        errors.append("coverage.omitted_claims must be an array")
        omitted = []
    for index, item in enumerate(omitted):
        label = f"coverage.omitted_claims[{index}]"
        if not isinstance(item, dict) or not _text(item.get("claim_id")):
            errors.append(f"{label}.claim_id must be non-empty")
            continue
        claim_id = item["claim_id"]
        if claim_id in omitted_ids:
            errors.append(f"duplicate omitted claim {claim_id}")
        omitted_ids.add(claim_id)
        if item.get("disposition") not in {"out_of_scope", "blocked_upstream", "deferred"}:
            errors.append(f"{label}.disposition is invalid")
        if not _text(item.get("reason")):
            errors.append(f"{label}.reason must be non-empty")
    overlap = set(represented) & omitted_ids
    if overlap:
        coverage_error = True
        errors.append(f"claims cannot be both represented and omitted: {sorted(overlap)}")
    uncovered = set(required_claims) - set(represented) - omitted_ids
    if uncovered:
        coverage_error = True
        errors.append(f"required claims lack representation or disposition: {sorted(uncovered)}")

    guards = V11_GUARDS if version == "1.1" else BASE_GUARDS
    guard = bundle.get("semantic_guard")
    if not isinstance(guard, dict):
        errors.append("semantic_guard must be an object")
        guard = {}
    for check in guards:
        if guard.get(check) not in {"pass", "fail"}:
            errors.append(f"semantic_guard.{check} must be pass/fail")
    extra_guards = set(guard) - set(guards)
    if extra_guards:
        errors.append(f"semantic_guard has unexpected checks: {sorted(extra_guards)}")
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
            if not _text(card_id) or not _sha(digest):
                errors.append(f"invalid output-card digest binding for {card_id!r}")
    if set(card_digests) != set(target_ids):
        errors.append("outputs.card_digests keys must exactly match scope.target_card_ids")

    return {
        "inputs": inputs, "scope": scope, "source_ids": source_ids,
        "target_ids": target_ids, "source_card_digests": source_card_digests,
        "findings": findings, "article": article, "coverage": coverage,
        "required_claims": set(required_claims), "represented": set(represented),
        "guard": guard, "guards": guards, "outputs": outputs,
        "output_card_digests": card_digests, "declared_changes": declared_changes,
        "scope_error": scope_error, "coverage_error": coverage_error,
    }
