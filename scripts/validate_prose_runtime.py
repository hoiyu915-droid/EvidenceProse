#!/usr/bin/env python3
"""Validate a TA06-backed EvidenceProse runtime bundle.

This validator is deliberately structural and consistency-oriented. It verifies
binding, permission projection, claim/contrast coverage against article spans,
statistical-interpretation constraints, public-surface separation, digests,
declared semantic-gate state, reader-outcome state, repair state, and the public
delivery shell. It does not claim that deterministic span binding can prove
scientific equivalence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
    "non_significance_not_promoted_to_zero",
    "attenuation_not_promoted_to_disappearance",
    "required_contrasts_preserved",
    "internal_process_absent_from_public_copy",
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
SIDECAR_CURRENT_FIELDS = {
    "contract_version",
    "article_id",
    "handoff_digest",
    "reader_contract_digest",
    "article_sha256",
    "delivery_length_exception",
    "semantic_guard",
    "claim_coverage",
    "contrast_coverage",
    "interpretation_constraint_checks",
    "public_surface_check",
    "reader_outcomes",
    "missing_action_info",
    "lint_warnings",
    "violations",
    "targeted_repairs",
    "final_gate",
}
HANDOFF_CONTRACT_VERSION = "1.1"
SIDECAR_CONTRACT_VERSION = "1.2"
INTERPRETATION_KINDS = {
    "non_significant_not_zero",
    "attenuation_not_disappearance",
    "concurrent_longitudinal_distinction",
    "custom",
}
MECHANICAL_LINT_CATEGORIES = frozenset(
    {
        "long_sentence",
        "long_paragraph",
        "de_chain",
        "passive_voice",
        "hedge_stack",
    }
)
DELIVERY_CONTENT_CEILING = 4000
LONG_SENTENCE_MIN_CHARACTERS = 40
LONG_PARAGRAPH_MIN_CHARACTERS = 180

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[。！？!?；;])")
_DE_CLAUSE_BOUNDARY_RE = re.compile(r"[，,、：:。！？!?；;\n]")
_PASSIVE_VERB_PATTERN = (
    r"(?:認為|視為|發現|觀察|證實|限制|排除|納入|分配|評估|測量|"
    r"報告|解讀|歸類|稱為|使用|選入|追蹤|診斷|治療|比較|分析|"
    r"低估|高估|混淆|控制|調整|記錄|呈現|指出)"
)
_PASSIVE_VOICE_RE = re.compile(
    rf"(?:被{_PASSIVE_VERB_PATTERN}|遭到|遭受|受到|"
    rf"為[^。！？!?；;\n]{{1,12}}所{_PASSIVE_VERB_PATTERN})"
)
_HEDGE_RE = re.compile(
    "|".join(
        re.escape(term)
        for term in (
            "不能排除",
            "尚不確定",
            "傾向於",
            "不排除",
            "可能",
            "或許",
            "也許",
            "似乎",
            "大概",
            "未必",
            "看來",
            "尚難",
        )
    )
)


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


def _unique_nonempty_strings(value: Any, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(_nonempty_string(item) for item in value)
        and len(value) == len(set(value))
    )


def _reader_claim_surface(article_text: str) -> str:
    """Return reader-visible prose while excluding bibliographic entries."""
    lines: list[str] = []
    inside_references = False
    for line in article_text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == "## 引用來源":
            inside_references = True
            lines.append(line)
            continue
        if inside_references and re.match(r"^[🟢🟡🔴] 證據分級：", stripped):
            inside_references = False
        if not inside_references:
            lines.append(line)
    return "".join(lines)


def _compact_for_match(value: str) -> str:
    return "".join(value.split())


def content_character_count(text: str) -> int | None:
    """Recompute the delivery count for the exact ``## 內容`` section."""
    lines = text.splitlines()
    content_positions = [
        index for index, line in enumerate(lines) if line.strip() == "## 內容"
    ]
    reference_positions = [
        index for index, line in enumerate(lines) if line.strip() == "## 引用來源"
    ]
    if len(content_positions) != 1 or len(reference_positions) != 1:
        return None
    content_start = content_positions[0]
    references_start = reference_positions[0]
    if references_start <= content_start:
        return None
    content = "\n".join(lines[content_start + 1 : references_start]).strip()
    return sum(1 for character in content if not character.isspace())


def _reader_prose_blocks(text: str) -> list[str]:
    """Return prose blocks before references, excluding Markdown headings.

    The lint is intentionally scoped to reader prose. Bibliographic entries,
    evidence labels, and the update footnote are excluded so they cannot create
    mechanical warnings that have nothing to do with article readability.
    """
    before_references = text.split("## 引用來源", 1)[0]
    blocks: list[str] = []
    current: list[str] = []
    for raw_line in before_references.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            if current:
                blocks.append(" ".join(current))
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(" ".join(current))
    return blocks


def _lint_character_count(text: str) -> int:
    trimmed = text.strip("。！？!?；;")
    return sum(1 for character in trimmed if not character.isspace())


def _sentences(blocks: list[str]) -> list[str]:
    sentences: list[str] = []
    for block in blocks:
        sentences.extend(
            sentence.strip()
            for sentence in _SENTENCE_BOUNDARY_RE.split(block)
            if sentence.strip()
        )
    return sentences


def _contains_de_chain(text: str) -> bool:
    """Detect three nearby ``的`` modifiers inside one punctuation-bounded clause."""
    for clause in _DE_CLAUSE_BOUNDARY_RE.split(text):
        compact = "".join(character for character in clause if not character.isspace())
        positions = [index for index, character in enumerate(compact) if character == "的"]
        if any(end - start <= 24 for start, end in zip(positions, positions[2:])):
            return True
    return False


def computed_zh_hant_lint_categories(article_text: str) -> set[str]:
    """Recompute the five deterministic zh-Hant warning categories.

    Thresholds are local review heuristics, not language standards. The result
    verifies audit provenance; warnings remain non-blocking and never authorize
    a precision-reducing rewrite.
    """
    blocks = _reader_prose_blocks(article_text)
    sentences = _sentences(blocks)
    categories: set[str] = set()

    if any(
        _lint_character_count(sentence) >= LONG_SENTENCE_MIN_CHARACTERS
        for sentence in sentences
    ):
        categories.add("long_sentence")
    if any(
        _lint_character_count(block) >= LONG_PARAGRAPH_MIN_CHARACTERS
        for block in blocks
    ):
        categories.add("long_paragraph")
    if any(_contains_de_chain(sentence) for sentence in sentences):
        categories.add("de_chain")
    if any(_PASSIVE_VOICE_RE.search(sentence) for sentence in sentences):
        categories.add("passive_voice")
    if any(len(_HEDGE_RE.findall(sentence)) >= 2 for sentence in sentences):
        categories.add("hedge_stack")

    return categories


def _validate_computed_lints(
    lints: list[Any],
    *,
    article_text: str,
) -> list[str]:
    declared = {
        item.get("category")
        for item in lints
        if isinstance(item, dict)
        and item.get("category") in MECHANICAL_LINT_CATEGORIES
    }
    computed = computed_zh_hant_lint_categories(article_text)
    warnings: list[str] = []
    missing = computed - declared
    unsupported = declared - computed
    if missing:
        warnings.append(
            "audit_sidecar.lint_warnings is missing recomputed categories: "
            f"{sorted(missing)}"
        )
    if unsupported:
        warnings.append(
            "audit_sidecar.lint_warnings declares uncomputed categories: "
            f"{sorted(unsupported)}"
        )
    return warnings


def _validate_length_exception(
    sidecar: dict[str, Any],
    *,
    measured_content_characters: int | None,
) -> list[str]:
    errors: list[str] = []
    version = sidecar.get("contract_version")
    exception = sidecar.get("delivery_length_exception")

    if version != SIDECAR_CONTRACT_VERSION:
        return errors
    if not isinstance(exception, dict):
        return ["audit_sidecar.delivery_length_exception must be an object"]

    expected_keys = {"granted", "measured_characters", "ceiling", "reason"}
    actual_keys = set(exception)
    missing = expected_keys - actual_keys
    unexpected = actual_keys - expected_keys
    if missing:
        errors.append(
            "audit_sidecar.delivery_length_exception missing fields: "
            f"{sorted(missing)}"
        )
    if unexpected:
        errors.append(
            "audit_sidecar.delivery_length_exception has unexpected fields: "
            f"{sorted(unexpected)}"
        )

    granted = exception.get("granted")
    declared_count = exception.get("measured_characters")
    ceiling = exception.get("ceiling")
    reason = exception.get("reason")
    if not isinstance(granted, bool):
        errors.append("audit_sidecar.delivery_length_exception.granted must be boolean")
    if (
        not isinstance(declared_count, int)
        or isinstance(declared_count, bool)
        or declared_count < 0
    ):
        errors.append(
            "audit_sidecar.delivery_length_exception.measured_characters "
            "must be a non-negative integer"
        )
    if ceiling != DELIVERY_CONTENT_CEILING:
        errors.append(
            "audit_sidecar.delivery_length_exception.ceiling must be 4000"
        )
    if reason is not None and not isinstance(reason, str):
        errors.append(
            "audit_sidecar.delivery_length_exception.reason must be string or null"
        )

    if measured_content_characters is None:
        errors.append(
            "audit_sidecar.delivery_length_exception cannot be verified because "
            "the article content count is unavailable"
        )
    elif isinstance(declared_count, int) and not isinstance(declared_count, bool):
        if declared_count != measured_content_characters:
            errors.append(
                "audit_sidecar.delivery_length_exception.measured_characters "
                f"must equal recomputed article count {measured_content_characters}"
            )

    if granted is True:
        if not _nonempty_string(reason):
            errors.append(
                "granted delivery length exception requires a non-empty reason"
            )
        if (
            measured_content_characters is not None
            and measured_content_characters <= DELIVERY_CONTENT_CEILING
        ):
            errors.append(
                "delivery length exception is unnecessary at or below 4000 characters"
            )
    elif granted is False:
        if reason is not None:
            errors.append(
                "non-granted delivery length exception reason must be null"
            )
        if (
            measured_content_characters is not None
            and measured_content_characters > DELIVERY_CONTENT_CEILING
        ):
            errors.append(
                "article exceeds 4000 characters without a granted sidecar exception"
            )

    return errors


def _length_exception_authorization(sidecar: Any) -> tuple[bool, str | None]:
    if (
        not isinstance(sidecar, dict)
        or sidecar.get("contract_version") != SIDECAR_CONTRACT_VERSION
    ):
        return False, None
    exception = sidecar.get("delivery_length_exception")
    if not isinstance(exception, dict):
        return False, None
    granted = exception.get("granted") is True
    reason = exception.get("reason")
    return granted, reason if isinstance(reason, str) else None


def validate_handoff(handoff: Any) -> list[str]:
    errors: list[str] = []
    h = _require_object(handoff, "handoff", errors)
    if not h:
        return errors

    for field in (
        "contract_version", "handoff_id", "producer", "consumer", "ta06_packet",
        "reader_context", "claims", "evidence", "citations", "terminology",
        "numeric_ledger", "permission", "reader_projection",
    ):
        if field not in h:
            errors.append(f"handoff missing required field {field}")

    if h.get("contract_version") != HANDOFF_CONTRACT_VERSION:
        errors.append(
            f"handoff.contract_version must be {HANDOFF_CONTRACT_VERSION}"
        )
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

    projection = h.get("reader_projection")
    if not isinstance(projection, dict):
        errors.append("handoff.reader_projection must be an object")
        return errors

    projection_fields = {
        "required_claim_ids",
        "optional_claim_ids",
        "internal_only_statements",
        "contrast_sets",
        "interpretation_constraints",
    }
    if set(projection) != projection_fields:
        errors.append(
            "handoff.reader_projection must contain exactly "
            f"{sorted(projection_fields)}"
        )

    required_claim_ids = projection.get("required_claim_ids")
    optional_claim_ids = projection.get("optional_claim_ids")
    if not _unique_nonempty_strings(required_claim_ids):
        errors.append(
            "handoff.reader_projection.required_claim_ids must be a unique "
            "non-empty string array"
        )
        required_claim_ids = []
    if not _unique_nonempty_strings(optional_claim_ids, allow_empty=True):
        errors.append(
            "handoff.reader_projection.optional_claim_ids must be a unique "
            "non-empty string array"
        )
        optional_claim_ids = []
    required_set = set(required_claim_ids)
    optional_set = set(optional_claim_ids)
    if required_set & optional_set:
        errors.append(
            "handoff.reader_projection required and optional claim IDs must be disjoint"
        )
    released_set = (
        set(permission.get("released_claim_ids", []))
        if isinstance(permission, dict)
        and isinstance(permission.get("released_claim_ids"), list)
        else set()
    )
    if required_set | optional_set != released_set:
        errors.append(
            "handoff.reader_projection required+optional claim IDs must exactly "
            "partition released_claim_ids"
        )

    internal_statements = projection.get("internal_only_statements")
    if not _unique_nonempty_strings(internal_statements, allow_empty=True):
        errors.append(
            "handoff.reader_projection.internal_only_statements must be a unique "
            "non-empty string array"
        )

    contrast_sets = projection.get("contrast_sets")
    contrast_ids: set[str] = set()
    if not isinstance(contrast_sets, list):
        errors.append("handoff.reader_projection.contrast_sets must be an array")
    else:
        contrast_fields = {
            "contrast_id",
            "claim_ids",
            "joint_representation_required",
            "reason",
        }
        for index, contrast in enumerate(contrast_sets):
            label = f"handoff.reader_projection.contrast_sets[{index}]"
            if not isinstance(contrast, dict):
                errors.append(f"{label} must be an object")
                continue
            if set(contrast) != contrast_fields:
                errors.append(f"{label} has invalid fields")
            contrast_id = contrast.get("contrast_id")
            if not _nonempty_string(contrast_id):
                errors.append(f"{label}.contrast_id must be non-empty")
            elif contrast_id in contrast_ids:
                errors.append(f"duplicate contrast_id {contrast_id}")
            else:
                contrast_ids.add(contrast_id)
            claim_ids = contrast.get("claim_ids")
            if (
                not _unique_nonempty_strings(claim_ids)
                or len(claim_ids) < 2
            ):
                errors.append(
                    f"{label}.claim_ids must contain at least two unique claim IDs"
                )
            elif not set(claim_ids).issubset(required_set):
                errors.append(
                    f"{label}.claim_ids must resolve to required reader claims"
                )
            if contrast.get("joint_representation_required") is not True:
                errors.append(
                    f"{label}.joint_representation_required must be true"
                )
            if not _nonempty_string(contrast.get("reason")):
                errors.append(f"{label}.reason must be non-empty")

    constraints = projection.get("interpretation_constraints")
    constraint_ids: set[str] = set()
    if not isinstance(constraints, list):
        errors.append(
            "handoff.reader_projection.interpretation_constraints must be an array"
        )
    else:
        constraint_fields = {
            "constraint_id",
            "claim_ids",
            "kind",
            "forbidden_phrases",
            "required_boundary",
        }
        for index, constraint in enumerate(constraints):
            label = (
                "handoff.reader_projection.interpretation_constraints"
                f"[{index}]"
            )
            if not isinstance(constraint, dict):
                errors.append(f"{label} must be an object")
                continue
            if set(constraint) != constraint_fields:
                errors.append(f"{label} has invalid fields")
            constraint_id = constraint.get("constraint_id")
            if not _nonempty_string(constraint_id):
                errors.append(f"{label}.constraint_id must be non-empty")
            elif constraint_id in constraint_ids:
                errors.append(f"duplicate constraint_id {constraint_id}")
            else:
                constraint_ids.add(constraint_id)
            claim_ids = constraint.get("claim_ids")
            if not _unique_nonempty_strings(claim_ids):
                errors.append(
                    f"{label}.claim_ids must be a unique non-empty string array"
                )
            elif not set(claim_ids).issubset(required_set):
                errors.append(
                    f"{label}.claim_ids must resolve to required reader claims"
                )
            if constraint.get("kind") not in INTERPRETATION_KINDS:
                errors.append(f"{label}.kind is invalid")
            if not _unique_nonempty_strings(constraint.get("forbidden_phrases")):
                errors.append(
                    f"{label}.forbidden_phrases must be a unique non-empty "
                    "string array"
                )
            if not _nonempty_string(constraint.get("required_boundary")):
                errors.append(f"{label}.required_boundary must be non-empty")

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


def _validate_projection_closure(
    *,
    handoff: Any,
    sidecar: dict[str, Any],
    article_text: str | None,
) -> tuple[list[str], bool]:
    """Bind required claims, contrasts, constraints and internal-only state.

    The semantic auditor still decides whether a span represents a claim. This
    function makes that decision falsifiable against the exact delivered bytes:
    every required claim needs a real article span, every closed contrast needs
    one joint span, every interpretation constraint needs a recorded check, and
    internal-only text is recomputed rather than trusted from the sidecar.
    """
    errors: list[str] = []
    closure_pass = True
    projection = (
        handoff.get("reader_projection")
        if isinstance(handoff, dict)
        and isinstance(handoff.get("reader_projection"), dict)
        else {}
    )
    if not projection:
        return ["handoff.reader_projection is unavailable for sidecar closure"], False
    if not isinstance(article_text, str):
        return ["reader-facing article text is unavailable for sidecar closure"], False

    reader_surface = _reader_claim_surface(article_text)
    reader_surface_compact = _compact_for_match(reader_surface)
    expected_required = set(projection.get("required_claim_ids", []))

    claim_coverage = sidecar.get("claim_coverage")
    represented_spans: dict[str, str] = {}
    if not isinstance(claim_coverage, dict):
        errors.append("audit_sidecar.claim_coverage must be an object")
        closure_pass = False
    else:
        expected_fields = {
            "required_claim_ids",
            "represented_claims",
            "omitted_claim_ids",
        }
        if set(claim_coverage) != expected_fields:
            errors.append("audit_sidecar.claim_coverage has invalid fields")
            closure_pass = False
        declared_required = claim_coverage.get("required_claim_ids")
        if not _unique_nonempty_strings(declared_required):
            errors.append(
                "audit_sidecar.claim_coverage.required_claim_ids must be a "
                "unique non-empty string array"
            )
            closure_pass = False
            declared_required = []
        if set(declared_required) != expected_required:
            errors.append(
                "audit_sidecar.claim_coverage.required_claim_ids must exactly "
                "match handoff reader_projection.required_claim_ids"
            )
            closure_pass = False

        represented = claim_coverage.get("represented_claims")
        if not isinstance(represented, list):
            errors.append(
                "audit_sidecar.claim_coverage.represented_claims must be an array"
            )
            closure_pass = False
        else:
            for index, item in enumerate(represented):
                label = (
                    "audit_sidecar.claim_coverage.represented_claims"
                    f"[{index}]"
                )
                if not isinstance(item, dict) or set(item) != {
                    "claim_id",
                    "article_span",
                }:
                    errors.append(f"{label} must contain claim_id/article_span")
                    closure_pass = False
                    continue
                claim_id = item.get("claim_id")
                span = item.get("article_span")
                if not _nonempty_string(claim_id):
                    errors.append(f"{label}.claim_id must be non-empty")
                    closure_pass = False
                    continue
                if claim_id in represented_spans:
                    errors.append(f"duplicate represented claim_id {claim_id}")
                    closure_pass = False
                if not _nonempty_string(span):
                    errors.append(f"{label}.article_span must be non-empty")
                    closure_pass = False
                    continue
                represented_spans[claim_id] = span
                if _compact_for_match(span) not in reader_surface_compact:
                    errors.append(
                        f"{label}.article_span is not present in reader-facing article"
                    )
                    closure_pass = False
        if set(represented_spans) != expected_required:
            errors.append(
                "audit_sidecar.claim_coverage represented claim IDs must exactly "
                "match required claim IDs"
            )
            closure_pass = False

        omitted = claim_coverage.get("omitted_claim_ids")
        if not _unique_nonempty_strings(omitted, allow_empty=True):
            errors.append(
                "audit_sidecar.claim_coverage.omitted_claim_ids must be a unique "
                "string array"
            )
            closure_pass = False
        elif omitted:
            errors.append(
                "audit_sidecar.claim_coverage.omitted_claim_ids must be empty for release"
            )
            closure_pass = False

    expected_contrasts = {
        item.get("contrast_id"): item
        for item in projection.get("contrast_sets", [])
        if isinstance(item, dict) and _nonempty_string(item.get("contrast_id"))
    }
    contrast_coverage = sidecar.get("contrast_coverage")
    if not isinstance(contrast_coverage, list):
        errors.append("audit_sidecar.contrast_coverage must be an array")
        closure_pass = False
        contrast_coverage = []
    seen_contrasts: set[str] = set()
    for index, item in enumerate(contrast_coverage):
        label = f"audit_sidecar.contrast_coverage[{index}]"
        if not isinstance(item, dict) or set(item) != {
            "contrast_id",
            "claim_ids",
            "joint_article_span",
        }:
            errors.append(
                f"{label} must contain contrast_id/claim_ids/joint_article_span"
            )
            closure_pass = False
            continue
        contrast_id = item.get("contrast_id")
        if not _nonempty_string(contrast_id):
            errors.append(f"{label}.contrast_id must be non-empty")
            closure_pass = False
            continue
        if contrast_id in seen_contrasts:
            errors.append(f"duplicate contrast coverage {contrast_id}")
            closure_pass = False
        seen_contrasts.add(contrast_id)
        expected_contrast = expected_contrasts.get(contrast_id)
        if expected_contrast is None:
            errors.append(f"{label}.contrast_id does not resolve to handoff")
            closure_pass = False
            continue
        claim_ids = item.get("claim_ids")
        if not _unique_nonempty_strings(claim_ids):
            errors.append(f"{label}.claim_ids must be unique and non-empty")
            closure_pass = False
        elif set(claim_ids) != set(expected_contrast.get("claim_ids", [])):
            errors.append(f"{label}.claim_ids do not match handoff contrast")
            closure_pass = False
        joint_span = item.get("joint_article_span")
        if not _nonempty_string(joint_span):
            errors.append(f"{label}.joint_article_span must be non-empty")
            closure_pass = False
            continue
        compact_joint = _compact_for_match(joint_span)
        if compact_joint not in reader_surface_compact:
            errors.append(
                f"{label}.joint_article_span is not present in reader-facing article"
            )
            closure_pass = False
        for claim_id in expected_contrast.get("claim_ids", []):
            represented_span = represented_spans.get(claim_id)
            if (
                represented_span
                and _compact_for_match(represented_span) not in compact_joint
            ):
                errors.append(
                    f"{label}.joint_article_span does not contain represented "
                    f"span for {claim_id}"
                )
                closure_pass = False
    if seen_contrasts != set(expected_contrasts):
        errors.append(
            "audit_sidecar.contrast_coverage IDs must exactly match handoff contrasts"
        )
        closure_pass = False

    expected_constraints = {
        item.get("constraint_id"): item
        for item in projection.get("interpretation_constraints", [])
        if isinstance(item, dict) and _nonempty_string(item.get("constraint_id"))
    }
    constraint_checks = sidecar.get("interpretation_constraint_checks")
    if not isinstance(constraint_checks, list):
        errors.append(
            "audit_sidecar.interpretation_constraint_checks must be an array"
        )
        closure_pass = False
        constraint_checks = []
    seen_constraints: set[str] = set()
    for index, item in enumerate(constraint_checks):
        label = f"audit_sidecar.interpretation_constraint_checks[{index}]"
        if not isinstance(item, dict) or set(item) != {
            "constraint_id",
            "status",
            "article_span",
        }:
            errors.append(
                f"{label} must contain constraint_id/status/article_span"
            )
            closure_pass = False
            continue
        constraint_id = item.get("constraint_id")
        if not _nonempty_string(constraint_id):
            errors.append(f"{label}.constraint_id must be non-empty")
            closure_pass = False
            continue
        if constraint_id in seen_constraints:
            errors.append(f"duplicate constraint check {constraint_id}")
            closure_pass = False
        seen_constraints.add(constraint_id)
        constraint = expected_constraints.get(constraint_id)
        if constraint is None:
            errors.append(f"{label}.constraint_id does not resolve to handoff")
            closure_pass = False
            continue
        if item.get("status") != "pass":
            errors.append(f"{label}.status must be pass for release")
            closure_pass = False
        span = item.get("article_span")
        if not _nonempty_string(span):
            errors.append(f"{label}.article_span must be non-empty")
            closure_pass = False
        elif _compact_for_match(span) not in reader_surface_compact:
            errors.append(
                f"{label}.article_span is not present in reader-facing article"
            )
            closure_pass = False
        for phrase in constraint.get("forbidden_phrases", []):
            if _compact_for_match(phrase) in reader_surface_compact:
                errors.append(
                    f"reader-facing article violates interpretation constraint "
                    f"{constraint_id}: forbidden phrase {phrase!r}"
                )
                closure_pass = False
    if seen_constraints != set(expected_constraints):
        errors.append(
            "audit_sidecar interpretation constraint IDs must exactly match handoff"
        )
        closure_pass = False

    public_surface = sidecar.get("public_surface_check")
    if not isinstance(public_surface, dict) or set(public_surface) != {
        "internal_only_absent",
        "leaked_statements",
    }:
        errors.append(
            "audit_sidecar.public_surface_check must contain "
            "internal_only_absent/leaked_statements"
        )
        closure_pass = False
        public_surface = {}
    internal_statements = projection.get("internal_only_statements", [])
    recomputed_leaks = [
        statement
        for statement in internal_statements
        if _compact_for_match(statement) in reader_surface_compact
    ]
    declared_leaks = public_surface.get("leaked_statements")
    if not _unique_nonempty_strings(declared_leaks, allow_empty=True):
        errors.append(
            "audit_sidecar.public_surface_check.leaked_statements must be a "
            "unique string array"
        )
        closure_pass = False
        declared_leaks = []
    if declared_leaks != recomputed_leaks:
        errors.append(
            "audit_sidecar.public_surface_check.leaked_statements must equal "
            "recomputed internal-only leaks"
        )
        closure_pass = False
    expected_internal_status = "pass" if not recomputed_leaks else "fail"
    if public_surface.get("internal_only_absent") != expected_internal_status:
        errors.append(
            "audit_sidecar.public_surface_check.internal_only_absent must be "
            f"{expected_internal_status}"
        )
        closure_pass = False
    if recomputed_leaks:
        errors.append("reader-facing article exposes handoff internal-only statements")
        closure_pass = False

    return errors, closure_pass


def validate_sidecar(
    sidecar: Any,
    *,
    handoff_digest: str,
    reader_digest: str,
    article_id: str,
    handoff: Any = None,
    article_text: str | None = None,
    measured_content_characters: int | None = None,
    article_sha256: str | None = None,
) -> list[str]:
    errors: list[str] = []
    s = _require_object(sidecar, "audit_sidecar", errors)
    if not s:
        return errors

    if s.get("contract_version") != SIDECAR_CONTRACT_VERSION:
        errors.append(
            f"audit_sidecar.contract_version must be {SIDECAR_CONTRACT_VERSION}"
        )
    else:
        missing_fields = SIDECAR_CURRENT_FIELDS - set(s)
        unexpected_fields = set(s) - SIDECAR_CURRENT_FIELDS
        if missing_fields:
            errors.append(
                f"audit_sidecar missing required fields: {sorted(missing_fields)}"
            )
        if unexpected_fields:
            errors.append(
                f"audit_sidecar has unexpected fields: {sorted(unexpected_fields)}"
            )
    if s.get("article_id") != article_id:
        errors.append("audit_sidecar.article_id must match reader_contract.article_id")
    if s.get("handoff_digest") != handoff_digest:
        errors.append("audit_sidecar.handoff_digest does not match canonical handoff digest")
    if s.get("reader_contract_digest") != reader_digest:
        errors.append(
            "audit_sidecar.reader_contract_digest does not match canonical reader-contract digest"
        )
    declared_article_sha256 = s.get("article_sha256")
    if s.get("contract_version") == SIDECAR_CONTRACT_VERSION:
        if (
            not isinstance(declared_article_sha256, str)
            or len(declared_article_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in declared_article_sha256
            )
        ):
            errors.append(
                "audit_sidecar.article_sha256 must be a lowercase SHA-256"
            )
        elif article_sha256 is None:
            errors.append(
                "audit_sidecar.article_sha256 cannot be verified because "
                "the article bytes are unavailable"
            )
        elif declared_article_sha256 != article_sha256:
            errors.append(
                "audit_sidecar.article_sha256 does not match exact article bytes"
            )
    errors.extend(
        _validate_length_exception(
            s,
            measured_content_characters=measured_content_characters,
        )
    )
    projection_errors, projection_pass = _validate_projection_closure(
        handoff=handoff,
        sidecar=s,
        article_text=article_text,
    )
    errors.extend(projection_errors)

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
        if set(item) != {"status", "note"}:
            errors.append(
                f"audit_sidecar.reader_outcomes.{axis} must contain only status/note"
            )
        if item.get("status") not in {"pass", "warning", "fail"}:
            errors.append(f"audit_sidecar.reader_outcomes.{axis}.status is invalid")
        if not isinstance(item.get("note"), str):
            errors.append(f"audit_sidecar.reader_outcomes.{axis}.note must be a string")
    unexpected_axes = set(outcomes) - set(READER_AXES)
    if unexpected_axes:
        errors.append(
            "audit_sidecar.reader_outcomes has unexpected axes: "
            f"{sorted(unexpected_axes)}"
        )

    lints = s.get("lint_warnings")
    if not isinstance(lints, list):
        errors.append("audit_sidecar.lint_warnings must be an array")
    else:
        for index, item in enumerate(lints):
            if not isinstance(item, dict):
                errors.append(f"audit_sidecar.lint_warnings[{index}] must be an object")
                continue
            if set(item) != {"category", "location", "message"}:
                errors.append(
                    f"audit_sidecar.lint_warnings[{index}] must contain only "
                    "category/location/message"
                )
            if item.get("category") not in LINT_CATEGORIES:
                errors.append(f"audit_sidecar.lint_warnings[{index}].category is invalid")
            if not _nonempty_string(item.get("location")):
                errors.append(
                    f"audit_sidecar.lint_warnings[{index}].location must be non-empty"
                )
            if not _nonempty_string(item.get("message")):
                errors.append(
                    f"audit_sidecar.lint_warnings[{index}].message must be non-empty"
                )

    repairs = s.get("targeted_repairs")
    if not isinstance(repairs, list):
        errors.append("audit_sidecar.targeted_repairs must be an array")
        repairs = []
    else:
        repair_fields = {"repair_id", "location", "status", "description"}
        for index, item in enumerate(repairs):
            if not isinstance(item, dict):
                errors.append(
                    f"audit_sidecar.targeted_repairs[{index}] must be an object"
                )
                continue
            if set(item) != repair_fields:
                errors.append(
                    f"audit_sidecar.targeted_repairs[{index}] has invalid fields"
                )
            for field in ("repair_id", "location", "description"):
                if not _nonempty_string(item.get(field)):
                    errors.append(
                        f"audit_sidecar.targeted_repairs[{index}].{field} "
                        "must be non-empty"
                    )
            if item.get("status") not in {"proposed", "applied", "verified"}:
                errors.append(
                    f"audit_sidecar.targeted_repairs[{index}].status is invalid"
                )

    violations = s.get("violations")
    if not isinstance(violations, list):
        errors.append("audit_sidecar.violations must be an array")
        violations = []
    else:
        violation_allowed_fields = {
            "code",
            "severity",
            "location",
            "claim_id",
            "description",
            "required_repair",
        }
        violation_required_fields = violation_allowed_fields - {"claim_id"}
        for index, item in enumerate(violations):
            if not isinstance(item, dict):
                errors.append(f"audit_sidecar.violations[{index}] must be an object")
                continue
            missing = violation_required_fields - set(item)
            unexpected = set(item) - violation_allowed_fields
            if missing:
                errors.append(
                    f"audit_sidecar.violations[{index}] missing fields: {sorted(missing)}"
                )
            if unexpected:
                errors.append(
                    f"audit_sidecar.violations[{index}] has unexpected fields: "
                    f"{sorted(unexpected)}"
                )
            for field in ("code", "location", "description", "required_repair"):
                if not _nonempty_string(item.get(field)):
                    errors.append(
                        f"audit_sidecar.violations[{index}].{field} must be non-empty"
                    )
            if "claim_id" in item and item["claim_id"] is not None:
                if not isinstance(item["claim_id"], str):
                    errors.append(
                        f"audit_sidecar.violations[{index}].claim_id must be string/null"
                    )
            if item.get("severity") not in {"hard", "warning"}:
                errors.append(
                    f"audit_sidecar.violations[{index}].severity must be hard/warning"
                )

    final_gate = s.get("final_gate")
    if not isinstance(final_gate, dict):
        errors.append("audit_sidecar.final_gate must be an object")
        return errors
    if set(final_gate) != {"status", "rationale"}:
        errors.append("audit_sidecar.final_gate must contain only status/rationale")

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
    hard_violations_absent = not any(
        isinstance(item, dict) and item.get("severity") == "hard"
        for item in violations
    )
    expected = (
        "pass"
        if semantic_pass
        and projection_pass
        and reader_pass
        and repairs_verified
        and hard_violations_absent
        else "fail"
    )
    if final_gate.get("status") != expected:
        errors.append(
            f"audit_sidecar.final_gate.status must be {expected} from "
            "semantic/projection/readability/repair/violation state"
        )
    if not _nonempty_string(final_gate.get("rationale")):
        errors.append("audit_sidecar.final_gate.rationale must be non-empty")

    missing_action_info = s.get("missing_action_info")
    if not isinstance(missing_action_info, list):
        errors.append("audit_sidecar.missing_action_info must be an array")
    elif not all(_nonempty_string(item) for item in missing_action_info):
        errors.append(
            "audit_sidecar.missing_action_info items must be non-empty strings"
        )

    return errors


def validate_bundle(
    *,
    handoff_path: Path,
    reader_path: Path,
    sidecar_path: Path,
    article_path: Path,
    allow_large_literature: bool = False,
    length_exception_reason: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    handoff = _load_json(handoff_path, "handoff", errors)
    reader = _load_json(reader_path, "reader_contract", errors)
    sidecar = _load_json(sidecar_path, "audit_sidecar", errors)

    try:
        article_bytes = article_path.read_bytes()
    except OSError as exc:
        errors.append(f"article: cannot read {article_path}: {exc}")
        article_bytes = b""
        article_text = ""
        article_sha256 = None
    else:
        article_sha256 = hashlib.sha256(article_bytes).hexdigest()
        try:
            article_text = article_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"article: invalid UTF-8 at byte {exc.start}")
            article_text = ""
    measured_content_characters = (
        content_character_count(article_text) if article_text else None
    )

    if allow_large_literature or length_exception_reason is not None:
        errors.append(
            "runtime length exception must come from the bound audit sidecar, "
            "not function or command-line arguments"
        )

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
                handoff=handoff,
                article_text=article_text,
                measured_content_characters=measured_content_characters,
                article_sha256=article_sha256,
            )
        )
        if article_text and isinstance(sidecar, dict):
            lints = sidecar.get("lint_warnings")
            if isinstance(lints, list):
                warnings.extend(
                    _validate_computed_lints(lints, article_text=article_text)
                )

    if article_text:
        authorized, exception_reason = _length_exception_authorization(sidecar)
        for error in validate_delivery_text(
            article_text,
            filename=article_path.name,
            allow_large_literature=authorized,
            length_exception_reason=exception_reason,
        ):
            errors.append(f"article delivery: {error}")

    return {
        "status": "pass" if not errors else "fail",
        "handoff_digest": handoff_digest or None,
        "reader_contract_digest": reader_digest or None,
        "article_sha256": article_sha256,
        "measured_content_characters": measured_content_characters,
        "article": str(article_path),
        "errors": errors,
        "warnings": warnings,
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
    parser.add_argument(
        "--allow-large-literature", action="store_true", help=argparse.SUPPRESS
    )
    parser.add_argument("--length-exception-reason", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.allow_large_literature or args.length_exception_reason is not None:
        parser.error("runtime length exception must come from the audit sidecar")

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
        for warning in report["warnings"]:
            print(f"  - WARNING: {warning}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
