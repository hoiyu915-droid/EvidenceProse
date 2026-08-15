"""File-bound artifact diff and immutable-asset verification for Probe v1.1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from probe_post_audit_common import (
    PRESENTATION_CHANGES, _cards, _digest_file, _digest_json, _path, _read_json,
    _strings, _text,
)


def _validate_artifacts(
    bundle: dict[str, Any], base: Path | None, state: dict[str, Any], errors: list[str]
) -> dict[str, Any]:
    block = bundle.get("artifact_verification")
    if not isinstance(block, dict):
        errors.append("artifact_verification must be an object")
        return {"failed": True, "output_text": "", "output_elements": {}}
    paths = {
        key: _path(base, block.get(key), f"artifact_verification.{key}", errors)
        for key in (
            "source_cards_path", "output_cards_path", "source_article_path",
            "output_article_path",
        )
    }
    source_cards_value = _read_json(paths["source_cards_path"], "source cards", errors)
    output_cards_value = _read_json(paths["output_cards_path"], "output cards", errors)
    source_cards, source_elements = _cards(source_cards_value, "source cards", errors)
    output_cards, output_elements = _cards(output_cards_value, "output cards", errors)
    output_text = ""
    for key, label in (("source_article_path", "source article"), ("output_article_path", "output article")):
        path = paths[key]
        if path is not None:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                errors.append(f"{label} cannot be read: {exc}")
            else:
                if key == "output_article_path":
                    output_text = text

    manifest = block.get("diff_manifest")
    artifact_error = False
    if not isinstance(manifest, dict):
        errors.append("artifact_verification.diff_manifest must be an object")
        manifest = {}
        artifact_error = True
    actual_file_digests: dict[str, str] = {}
    card_artifacts = (
        ("source_cards_path", "source_cards_digest", source_cards_value),
        ("output_cards_path", "output_cards_digest", output_cards_value),
    )
    for path_key, manifest_key, value in card_artifacts:
        if paths[path_key] is None or not isinstance(value, dict):
            artifact_error = True
            continue
        digest = _digest_json(value)
        actual_file_digests[path_key] = digest
        if manifest.get(manifest_key) != digest:
            artifact_error = True
            errors.append(
                f"artifact_verification.diff_manifest.{manifest_key} "
                "does not match canonical card JSON"
            )
    for path_key, manifest_key in (
        ("source_article_path", "source_article_digest"),
        ("output_article_path", "output_article_digest"),
    ):
        path = paths[path_key]
        if path is None:
            artifact_error = True
            continue
        digest = _digest_file(path)
        actual_file_digests[path_key] = digest
        if manifest.get(manifest_key) != digest:
            artifact_error = True
            errors.append(
                f"artifact_verification.diff_manifest.{manifest_key} "
                "does not match article bytes"
            )
    if actual_file_digests.get("source_article_path") != state["inputs"].get("source_article_digest"):
        artifact_error = True
        errors.append("inputs.source_article_digest does not match source article file")
    if actual_file_digests.get("source_article_path") != state["article"].get("source_article_digest"):
        artifact_error = True
        errors.append("article_rewrite.source_article_digest does not match source article file")
    if actual_file_digests.get("output_article_path") != state["article"].get("output_article_digest"):
        artifact_error = True
        errors.append("article_rewrite.output_article_digest does not match output article file")
    if actual_file_digests.get("output_article_path") != state["outputs"].get("article_digest"):
        artifact_error = True
        errors.append("outputs.article_digest does not match output article file")

    if set(source_cards) != set(state["source_ids"]):
        artifact_error = True
        errors.append("source card artifact IDs do not match scope.source_card_ids")
    if set(output_cards) != set(state["target_ids"]):
        artifact_error = True
        errors.append("output card artifact IDs do not match scope.target_card_ids")
    for card_id, card in source_cards.items():
        if state["source_card_digests"].get(card_id) != _digest_json(card):
            artifact_error = True
            errors.append(f"inputs.source_card_digests[{card_id!r}] does not match source artifact")
    for card_id, card in output_cards.items():
        if state["output_card_digests"].get(card_id) != _digest_json(card):
            artifact_error = True
            errors.append(f"outputs.card_digests[{card_id!r}] does not match output artifact")

    computed_changes = {
        element_id
        for element_id in set(source_elements) | set(output_elements)
        if source_elements.get(element_id) != output_elements.get(element_id)
    }
    manifest_changes = manifest.get("computed_changed_element_ids")
    if not _strings(manifest_changes):
        artifact_error = True
        errors.append("artifact_verification.diff_manifest.computed_changed_element_ids must be a unique string array")
        manifest_changes = []
    if set(manifest_changes) != computed_changes:
        artifact_error = True
        errors.append(
            "artifact_verification.diff_manifest.computed_changed_element_ids does not match computed artifact diff"
        )
    undeclared = computed_changes - state["declared_changes"]
    missing = state["declared_changes"] - computed_changes
    if undeclared:
        artifact_error = True
        errors.append(f"computed artifact diff contains undeclared changed elements: {sorted(undeclared)}")
    if missing:
        artifact_error = True
        errors.append(f"declared changed elements are absent from computed artifact diff: {sorted(missing)}")
    if manifest.get("status") != ("fail" if artifact_error else "pass"):
        errors.append(
            f"artifact_verification.diff_manifest.status must be {'fail' if artifact_error else 'pass'} from computed state"
        )

    assets = block.get("immutable_assets")
    asset_error = False
    if not isinstance(assets, list):
        errors.append("artifact_verification.immutable_assets must be an array")
        assets = []
        asset_error = True
    seen_assets: set[str] = set()
    for index, asset in enumerate(assets):
        label = f"artifact_verification.immutable_assets[{index}]"
        local_error = False
        if not isinstance(asset, dict) or not _text(asset.get("asset_id")):
            errors.append(f"{label}.asset_id must be non-empty")
            asset_error = True
            continue
        asset_id = asset["asset_id"]
        if asset_id in seen_assets:
            errors.append(f"duplicate immutable asset_id {asset_id}")
            local_error = True
        seen_assets.add(asset_id)
        before = _path(base, asset.get("before_path"), f"{label}.before_path", errors)
        after = _path(base, asset.get("after_path"), f"{label}.after_path", errors)
        before_digest = _digest_file(before) if before else None
        after_digest = _digest_file(after) if after else None
        if before_digest is None or after_digest is None:
            local_error = True
        if asset.get("before_digest") != before_digest:
            errors.append(f"{label}.before_digest does not match file bytes")
            local_error = True
        if asset.get("after_digest") != after_digest:
            errors.append(f"{label}.after_digest does not match file bytes")
            local_error = True
        if before_digest is not None and after_digest is not None and before_digest != after_digest:
            errors.append(f"{label} immutable asset bytes changed")
            local_error = True
        if asset.get("mutation_policy") != "byte_identical":
            errors.append(f"{label}.mutation_policy must be byte_identical")
            local_error = True
        if asset.get("regenerated") is not False:
            errors.append(f"{label}.regenerated must be false")
            local_error = True
        for field in ("bound_claim_ids", "referenced_by_element_ids"):
            if not _strings(asset.get(field), nonempty=True):
                errors.append(f"{label}.{field} must be a non-empty unique string array")
                local_error = True
        allowed = asset.get("allowed_presentation_changes")
        actual = asset.get("actual_presentation_changes")
        if not _strings(allowed) or set(allowed) - PRESENTATION_CHANGES:
            errors.append(f"{label}.allowed_presentation_changes is invalid")
            local_error = True
            allowed = []
        if not _strings(actual) or set(actual) - PRESENTATION_CHANGES:
            errors.append(f"{label}.actual_presentation_changes is invalid")
            local_error = True
            actual = []
        if set(actual) - set(allowed):
            errors.append(f"{label} has unauthorized presentation changes")
            local_error = True
        for element_id in asset.get("referenced_by_element_ids") or []:
            element = output_elements.get(element_id)
            if not isinstance(element, dict):
                errors.append(f"{label} references missing output element {element_id}")
                local_error = True
            elif element.get("asset_id") != asset_id:
                errors.append(f"{label} output element {element_id} is not bound to asset {asset_id}")
                local_error = True
        expected_status = "fail" if local_error else "pass"
        if asset.get("status") != expected_status:
            errors.append(f"{label}.status must be {expected_status} from verified asset state")
        asset_error |= local_error

    if asset_error and state["guard"].get("immutable_assets_preserved") == "pass":
        errors.append("semantic_guard.immutable_assets_preserved cannot pass when immutable-asset verification fails")
    if artifact_error and state["guard"].get("artifact_diff_verified") == "pass":
        errors.append("semantic_guard.artifact_diff_verified cannot pass when artifact verification fails")
    return {
        "failed": artifact_error or asset_error,
        "output_text": output_text,
        "output_elements": output_elements,
    }
