"""Shared helpers and constants for Probe post-audit validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


VERSIONS = {"1.0", "1.1"}
BASE_GUARDS = (
    "no_new_epistemic_content", "claim_strength_preserved", "numeric_fidelity",
    "required_qualifiers_preserved", "forbidden_overclaims_absent",
    "cross_card_consistency", "package_coverage_complete",
    "article_card_alignment", "edit_scope_respected",
)
V11_GUARDS = BASE_GUARDS + (
    "immutable_assets_preserved", "artifact_diff_verified",
    "reader_reconstruction_passed",
)
KINDS = {"KEEP", "PATCH", "MERGE", "RECOMPOSE", "REGENERATE"}
ARTICLE_ACTIONS = {
    "reorder", "compress", "expand_supported_explanation", "simplify",
    "strengthen_rhetoric", "add_supported_bridge", "retitle",
}
PRESENTATION_CHANGES = {"position", "scale", "frame"}
QUIZ_CATEGORIES = {
    "central_claim", "evidence_weight", "evidence_role", "numeric_context",
    "population", "limitation", "uncertainty", "causal_boundary",
    "applicability", "misuse_boundary",
}
MIN_QUIZ_CATEGORIES = {
    "central_claim", "limitation", "causal_boundary", "applicability",
    "misuse_boundary",
}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value
    )


def _strings(value: Any, *, nonempty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (not nonempty or bool(value))
        and all(_text(item) for item in value)
        and len(value) == len(set(value))
    )


def _digest_json(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path(base: Path | None, raw: Any, label: str, errors: list[str]) -> Path | None:
    if base is None:
        errors.append(f"{label} cannot be verified without a bundle base directory")
        return None
    if not _text(raw):
        errors.append(f"{label} must be a non-empty relative path")
        return None
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        errors.append(f"{label} must stay inside the bundle directory")
        return None
    resolved = (base / candidate).resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError:
        errors.append(f"{label} escapes the bundle directory")
        return None
    if not resolved.is_file():
        errors.append(f"{label} does not exist: {raw}")
        return None
    return resolved


def _read_json(path: Path | None, label: str, errors: list[str]) -> Any:
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        errors.append(f"{label} cannot be read: {exc}")
    except json.JSONDecodeError as exc:
        errors.append(f"{label} is invalid JSON at {exc.lineno}:{exc.colno}: {exc.msg}")
    return None


def _cards(value: Any, label: str, errors: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict) or not isinstance(value.get("cards"), list):
        errors.append(f"{label} must contain a cards array")
        return {}, {}
    cards: dict[str, Any] = {}
    elements: dict[str, Any] = {}
    for index, card in enumerate(value["cards"]):
        card_label = f"{label}.cards[{index}]"
        if not isinstance(card, dict) or not _text(card.get("card_id")):
            errors.append(f"{card_label}.card_id must be non-empty")
            continue
        card_id = card["card_id"]
        if card_id in cards:
            errors.append(f"{label} has duplicate card_id {card_id}")
        cards[card_id] = card
        if not isinstance(card.get("elements"), list):
            errors.append(f"{card_label}.elements must be an array")
            continue
        for element_index, element in enumerate(card["elements"]):
            element_label = f"{card_label}.elements[{element_index}]"
            if not isinstance(element, dict) or not _text(element.get("element_id")):
                errors.append(f"{element_label}.element_id must be non-empty")
                continue
            element_id = element["element_id"]
            if element_id in elements:
                errors.append(f"{label} has duplicate element_id {element_id}")
            elements[element_id] = element
    return cards, elements
