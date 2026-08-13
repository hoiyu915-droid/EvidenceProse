#!/usr/bin/env python3
"""Apply content-truth corrections without touching integrity sealing metadata.

This helper is deliberately narrow: audit/edit is allowed to rewrite content-bearing
fields and audit annotations in the canonical storyboard JSON, but it must not
recompute, replace, or otherwise mutate digests, counts, queue bindings, or seals.
Those belong to the explicit seal/execution stage.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Iterable


CURRENT_CARD_CONTENT_FIELDS = {
    "title",
    "visible_text",
    "allowed_visible_numbers",
    "main_visual_scene",
}

# These names are accepted only when the current storyboard already carries them.
# They make the helper portable to richer card contracts without silently extending
# the current EvidenceProse schema.
OPTIONAL_SEMANTIC_MIRROR_FIELDS = {
    "main_visual",
    "required_relations",
    "scene",
    "prompt",
    "canonical_text",
}

AUDIT_METADATA_FIELDS = {
    "content_truth_audit",
    "required_correction",
    "targeted_audit",
}

READER_CONTRACT_FIELDS = {
    "central_claim",
    "evidence_weight",
    "limitations",
    "applicability",
    "misuse_boundaries",
}

INTEGRITY_EXACT_KEYS = {
    "sha256",
    "image_sha256",
    "article_sha256",
    "pdf_sha256",
    "git_blob_sha1",
    "prompt_char_count",
    "imagegen_args_digest",
    "renderer_payload_digest",
    "queue_digest",
    "attestation_digest",
}


class AuditEditError(ValueError):
    """Raised when an audit correction attempts an unsafe or invalid mutation."""


def _is_integrity_key(key: str) -> bool:
    lowered = key.lower()
    return (
        lowered in INTEGRITY_EXACT_KEYS
        or lowered.endswith("_sha256")
        or lowered.endswith("_digest")
        or lowered.endswith("_attestation")
    )


def _integrity_snapshot(value: Any, path: str = "$") -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if _is_integrity_key(key):
                snapshot[child_path] = copy.deepcopy(child)
            snapshot.update(_integrity_snapshot(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            snapshot.update(_integrity_snapshot(child, f"{path}[{index}]"))
    return snapshot


def _require_non_empty_text(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise AuditEditError(f"{label} must be non-empty text")


def _validate_content_patch(card: dict[str, Any], patch: dict[str, Any]) -> None:
    if not isinstance(patch, dict) or not patch:
        raise AuditEditError("content patch must be a non-empty object")

    allowed = CURRENT_CARD_CONTENT_FIELDS | OPTIONAL_SEMANTIC_MIRROR_FIELDS
    unexpected = set(patch) - allowed
    if unexpected:
        raise AuditEditError(f"content patch contains non-content fields: {sorted(unexpected)}")

    missing_optional = {
        key for key in patch if key in OPTIONAL_SEMANTIC_MIRROR_FIELDS and key not in card
    }
    if missing_optional:
        raise AuditEditError(
            "semantic mirror field is not present in this storyboard schema: "
            + ", ".join(sorted(missing_optional))
        )

    if "title" in patch:
        _require_non_empty_text(patch["title"], "title")
    if "main_visual_scene" in patch:
        _require_non_empty_text(patch["main_visual_scene"], "main_visual_scene")
    if "visible_text" in patch:
        visible = patch["visible_text"]
        if not isinstance(visible, list) or not visible:
            raise AuditEditError("visible_text must be a non-empty array")
        if any(not isinstance(item, str) or not item.strip() for item in visible):
            raise AuditEditError("visible_text must contain non-empty strings")
        if len(visible) != len(set(visible)):
            raise AuditEditError("visible_text must not contain duplicates")
    if "allowed_visible_numbers" in patch:
        values = patch["allowed_visible_numbers"]
        if not isinstance(values, list):
            raise AuditEditError("allowed_visible_numbers must be an array")
        if any(not isinstance(item, str) or not item.strip() for item in values):
            raise AuditEditError("allowed_visible_numbers must contain non-empty strings")
        if len(values) != len(set(values)):
            raise AuditEditError("allowed_visible_numbers must not contain duplicates")


def _validate_audit_patch(patch: dict[str, Any] | None) -> None:
    if patch is None:
        return
    if not isinstance(patch, dict):
        raise AuditEditError("audit patch must be an object")
    unexpected = set(patch) - AUDIT_METADATA_FIELDS
    if unexpected:
        raise AuditEditError(f"audit patch contains unsupported fields: {sorted(unexpected)}")
    if "content_truth_audit" in patch:
        audit = patch["content_truth_audit"]
        if not isinstance(audit, dict) or set(audit) != {"status", "violations"}:
            raise AuditEditError("content_truth_audit must contain status and violations")
        if audit["status"] not in {"pass", "fail"}:
            raise AuditEditError("content_truth_audit status must be pass or fail")
        violations = audit["violations"]
        if not isinstance(violations, list) or any(
            not isinstance(item, str) or not item.strip() for item in violations
        ):
            raise AuditEditError("content_truth_audit violations must be an array of non-empty strings")
        if audit["status"] == "pass" and violations:
            raise AuditEditError("passed content_truth_audit cannot retain violations")
        if audit["status"] == "fail" and not violations:
            raise AuditEditError("failed content_truth_audit requires violations")
    if "required_correction" in patch:
        correction = patch["required_correction"]
        if correction is not None and (not isinstance(correction, str) or not correction.strip()):
            raise AuditEditError("required_correction must be null or non-empty text")
    if "targeted_audit" in patch:
        _require_non_empty_text(patch["targeted_audit"], "targeted_audit")


def apply_card_correction(
    storyboard: dict[str, Any],
    card_id: str,
    content_patch: dict[str, Any],
    *,
    audit_patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mutate one card's canonical content while preserving every integrity field.

    The caller is responsible for supplying every semantic mirror that actually
    carries the same meaning in the current contract. This function refuses to
    synthesize absent schema fields and refuses any integrity-key mutation.
    """

    if not isinstance(storyboard, dict):
        raise AuditEditError("storyboard must be an object")
    cards = storyboard.get("cards")
    if not isinstance(cards, list):
        raise AuditEditError("storyboard cards must be an array")

    matching = [card for card in cards if isinstance(card, dict) and card.get("card_id") == card_id]
    if len(matching) != 1:
        raise AuditEditError(f"expected exactly one card {card_id}, found {len(matching)}")
    card = matching[0]

    _validate_content_patch(card, content_patch)
    _validate_audit_patch(audit_patch)
    before = _integrity_snapshot(storyboard)

    for key, value in content_patch.items():
        card[key] = copy.deepcopy(value)
    if audit_patch:
        for key, value in audit_patch.items():
            card[key] = copy.deepcopy(value)

    after = _integrity_snapshot(storyboard)
    if before != after:
        raise AuditEditError("audit correction mutated integrity metadata")
    return storyboard


def apply_reader_contract_correction(
    storyboard: dict[str, Any], patch: dict[str, Any]
) -> dict[str, Any]:
    """Edit reader-contract semantics without resealing the storyboard."""

    if not isinstance(patch, dict) or not patch:
        raise AuditEditError("reader-contract patch must be a non-empty object")
    unexpected = set(patch) - READER_CONTRACT_FIELDS
    if unexpected:
        raise AuditEditError(f"reader-contract patch contains unsupported fields: {sorted(unexpected)}")
    reader_contract = storyboard.get("reader_contract")
    if not isinstance(reader_contract, dict):
        raise AuditEditError("storyboard reader_contract must be an object")

    before = _integrity_snapshot(storyboard)
    for key, value in patch.items():
        _require_non_empty_text(value, f"reader_contract.{key}")
        reader_contract[key] = value
    after = _integrity_snapshot(storyboard)
    if before != after:
        raise AuditEditError("reader-contract correction mutated integrity metadata")
    return storyboard


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditEditError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditEditError(f"{path} must contain a JSON object")
    return value


def _parse_json_object(raw: str | None, label: str) -> dict[str, Any] | None:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AuditEditError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditEditError(f"{label} must decode to an object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboard", type=Path, help="canonical card_storyboard.json to edit")
    parser.add_argument("--card", help="card id such as C01")
    parser.add_argument("--content-json", help="JSON object of canonical card content fields to replace")
    parser.add_argument("--audit-json", help="optional JSON object for content_truth_audit/required_correction/targeted_audit")
    parser.add_argument("--reader-contract-json", help="optional JSON object for reader_contract fields")
    parser.add_argument("--stdout", action="store_true", help="print corrected JSON instead of writing the file")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        document = _load_json_object(args.storyboard)
        content_patch = _parse_json_object(args.content_json, "--content-json")
        audit_patch = _parse_json_object(args.audit_json, "--audit-json")
        reader_patch = _parse_json_object(args.reader_contract_json, "--reader-contract-json")

        if content_patch is not None or audit_patch is not None:
            if not args.card:
                raise AuditEditError("--card is required when applying a card correction")
            if content_patch is None:
                raise AuditEditError("card correction requires --content-json; do not emit review-only corrections")
            apply_card_correction(document, args.card, content_patch, audit_patch=audit_patch)
        if reader_patch is not None:
            apply_reader_contract_correction(document, reader_patch)
        if content_patch is None and reader_patch is None:
            raise AuditEditError("no content correction was supplied")

        rendered = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        if args.stdout:
            print(rendered, end="")
        else:
            args.storyboard.write_text(rendered, encoding="utf-8")
    except AuditEditError as exc:
        print(f"FAIL: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
