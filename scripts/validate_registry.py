#!/usr/bin/env python3
"""Fail-closed structural validation for the EvidenceProse induction registry."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ID = re.compile(r"^S\d{3}$")
RULE_ID = re.compile(r"^R\d{3}$")
VOICE_RULE_ID = re.compile(r"^V\d{3}$")
BATCH_ID = re.compile(r"^B\d{3}$")
OBSERVATION_ID = re.compile(r"^O\d{3}$")
ARTIFACT_ID = re.compile(r"^A\d{3}$")
CARD_ID = re.compile(r"^C\d{2}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
RULE_STATES = {"hypothesis", "candidate", "conditional", "stable", "contradicted", "rejected"}


class ValidationError(Exception):
    """Raised when the registry is internally inconsistent."""


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load {path.relative_to(ROOT)}: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate() -> dict[str, int]:
    registry = load_json(ROOT / "data/registry.json")
    rules_doc = load_json(ROOT / "data/rules/rules.json")
    voice_rules_doc = load_json(ROOT / "data/voice/voice_rules.json")
    batch_doc = load_json(ROOT / "data/batch_results.json")
    require(isinstance(registry, dict), "registry must be an object")
    require(isinstance(rules_doc, dict) and isinstance(rules_doc.get("rules"), list), "rules document must contain a rules array")
    require(isinstance(voice_rules_doc, dict) and isinstance(voice_rules_doc.get("rules"), list), "voice rules document must contain a rules array")
    require(isinstance(batch_doc, dict) and isinstance(batch_doc.get("batches"), list), "batch results document must contain a batches array")

    sample_ids = registry.get("sample_ids")
    rule_ids = registry.get("rule_ids")
    stable_rule_ids = registry.get("stable_rule_ids")
    voice_rule_ids = registry.get("voice_rule_ids")
    stable_voice_rule_ids = registry.get("stable_voice_rule_ids")
    batch_ids = registry.get("batch_ids")
    require(isinstance(sample_ids, list) and sample_ids, "registry sample_ids must be a non-empty array")
    require(isinstance(rule_ids, list), "registry rule_ids must be an array")
    require(isinstance(stable_rule_ids, list), "registry stable_rule_ids must be an array")
    require(isinstance(voice_rule_ids, list), "registry voice_rule_ids must be an array")
    require(isinstance(stable_voice_rule_ids, list), "registry stable_voice_rule_ids must be an array")
    require(isinstance(batch_ids, list) and batch_ids, "registry batch_ids must be a non-empty array")
    require(len(sample_ids) == len(set(sample_ids)), "duplicate sample_ids in registry")
    require(len(rule_ids) == len(set(rule_ids)), "duplicate rule_ids in registry")
    require(len(voice_rule_ids) == len(set(voice_rule_ids)), "duplicate voice_rule_ids in registry")
    require(len(batch_ids) == len(set(batch_ids)), "duplicate batch_ids in registry")

    observations_by_sample: dict[str, set[str]] = {}
    contamination_count = 0
    strict_render_failures = 0
    semantic_failures = 0
    for sample_id in sample_ids:
        require(isinstance(sample_id, str) and SAMPLE_ID.fullmatch(sample_id) is not None, f"invalid sample id: {sample_id!r}")
        sample_path = ROOT / f"data/samples/{sample_id}/sample.json"
        sample = load_json(sample_path)
        require(isinstance(sample, dict), f"{sample_id} sample must be an object")
        require(sample.get("sample_id") == sample_id, f"{sample_id} identity mismatch")
        article_path = sample.get("article_path")
        require(isinstance(article_path, str), f"{sample_id} article_path must be a string")
        require((ROOT / article_path).is_file(), f"{sample_id} article file is missing: {article_path}")

        study_profile = sample.get("study_profile")
        require(isinstance(study_profile, dict), f"{sample_id} study_profile must be an object")
        not_applicable_reasons = study_profile.get("not_applicable_reasons")
        require(isinstance(not_applicable_reasons, dict), f"{sample_id} not_applicable_reasons must be an object")
        for nullable_field in ("total_participants", "quantitative_datasets", "follow_up"):
            if study_profile.get(nullable_field) is None:
                reason = not_applicable_reasons.get(nullable_field)
                require(isinstance(reason, str) and reason.strip(), f"{sample_id} null {nullable_field} requires a reason")

        artifact_receipts = sample.get("artifact_receipts", [])
        require(isinstance(artifact_receipts, list), f"{sample_id} artifact_receipts must be an array")
        artifact_ids: set[str] = set()
        for receipt in artifact_receipts:
            require(isinstance(receipt, dict), f"{sample_id} artifact receipt must be an object")
            artifact_id = receipt.get("artifact_id")
            require(isinstance(artifact_id, str) and ARTIFACT_ID.fullmatch(artifact_id) is not None, f"{sample_id} invalid artifact id")
            require(artifact_id not in artifact_ids, f"{sample_id} duplicate artifact {artifact_id}")
            digest = receipt.get("sha256")
            require(isinstance(digest, str) and SHA256.fullmatch(digest) is not None, f"{sample_id}/{artifact_id} invalid sha256")
            artifact_ids.add(artifact_id)

        storyboard_path = sample.get("card_storyboard_path")
        if storyboard_path is not None:
            require(isinstance(storyboard_path, str), f"{sample_id} card_storyboard_path must be a string")
            storyboard = load_json(ROOT / storyboard_path)
            require(isinstance(storyboard, dict) and storyboard.get("sample_id") == sample_id, f"{sample_id} storyboard identity mismatch")
            cards = storyboard.get("cards")
            require(isinstance(cards, list) and cards, f"{sample_id} storyboard requires cards")
            card_ids: set[str] = set()
            observed_failures = 0
            observed_semantic_failures = 0
            for card in cards:
                require(isinstance(card, dict), f"{sample_id} storyboard card must be an object")
                card_id = card.get("card_id")
                require(isinstance(card_id, str) and CARD_ID.fullmatch(card_id) is not None, f"{sample_id} invalid card id")
                require(card_id not in card_ids, f"{sample_id} duplicate card {card_id}")
                image_digest = card.get("image_sha256")
                require(isinstance(image_digest, str) and SHA256.fullmatch(image_digest) is not None, f"{sample_id}/{card_id} invalid image sha256")
                strict_audit = card.get("strict_render_audit")
                require(isinstance(strict_audit, dict) and strict_audit.get("status") in {"pass", "fail"}, f"{sample_id}/{card_id} invalid strict render audit")
                semantic_audit = card.get("semantic_audit")
                require(semantic_audit in {"pass", "fail"}, f"{sample_id}/{card_id} invalid semantic audit")
                if semantic_audit == "fail":
                    semantic_violations = card.get("semantic_violations")
                    require(isinstance(semantic_violations, list) and semantic_violations, f"{sample_id}/{card_id} failed semantic audit requires violations")
                    observed_semantic_failures += 1
                if strict_audit["status"] == "fail":
                    violations = strict_audit.get("violations")
                    require(isinstance(violations, list) and violations, f"{sample_id}/{card_id} failed audit requires violations")
                    observed_failures += 1
                card_ids.add(card_id)
            summary = storyboard.get("summary")
            require(isinstance(summary, dict), f"{sample_id} storyboard summary must be an object")
            require(summary.get("cards") == len(cards), f"{sample_id} storyboard card count mismatch")
            require(summary.get("strict_render_failures") == observed_failures, f"{sample_id} strict-render failure count mismatch")
            require(summary.get("strict_render_passes") == len(cards) - observed_failures, f"{sample_id} strict-render pass count mismatch")
            require(summary.get("semantic_failures") == observed_semantic_failures, f"{sample_id} semantic failure count mismatch")
            require(summary.get("semantic_passes") == len(cards) - observed_semantic_failures, f"{sample_id} semantic pass count mismatch")
            strict_render_failures += observed_failures
            semantic_failures += observed_semantic_failures

        observations = sample.get("observations")
        require(isinstance(observations, list) and observations, f"{sample_id} requires observations")
        observation_ids: set[str] = set()
        for observation in observations:
            require(isinstance(observation, dict), f"{sample_id} observation must be an object")
            observation_id = observation.get("observation_id")
            require(isinstance(observation_id, str) and OBSERVATION_ID.fullmatch(observation_id) is not None, f"{sample_id} invalid observation id")
            require(observation_id not in observation_ids, f"{sample_id} duplicate observation {observation_id}")
            locations = observation.get("evidence_locations")
            require(isinstance(locations, list) and locations, f"{sample_id}/{observation_id} requires evidence locations")
            observation_ids.add(observation_id)
        observations_by_sample[sample_id] = observation_ids

        contamination_notes = sample.get("contamination_notes")
        require(isinstance(contamination_notes, list), f"{sample_id} contamination_notes must be an array")
        contamination_count += len(contamination_notes)

    rules = rules_doc["rules"]
    actual_rule_ids: list[str] = []
    actual_stable_ids: list[str] = []
    for rule in rules:
        require(isinstance(rule, dict), "each rule must be an object")
        rule_id = rule.get("rule_id")
        require(isinstance(rule_id, str) and RULE_ID.fullmatch(rule_id) is not None, f"invalid rule id: {rule_id!r}")
        require(rule_id not in actual_rule_ids, f"duplicate rule {rule_id}")
        actual_rule_ids.append(rule_id)
        status = rule.get("status")
        require(status in RULE_STATES, f"{rule_id} has invalid state {status!r}")
        if status == "stable":
            actual_stable_ids.append(rule_id)

        support = rule.get("support")
        require(isinstance(support, list), f"{rule_id} support must be an array")
        for receipt in support:
            require(isinstance(receipt, dict), f"{rule_id} support receipt must be an object")
            sample_id = receipt.get("sample_id")
            require(sample_id in observations_by_sample, f"{rule_id} references unknown sample {sample_id!r}")
            observation_ids = receipt.get("observation_ids")
            require(isinstance(observation_ids, list) and observation_ids, f"{rule_id}/{sample_id} requires observation ids")
            missing = set(observation_ids) - observations_by_sample[sample_id]
            require(not missing, f"{rule_id}/{sample_id} references unknown observations: {sorted(missing)}")

        if status == "stable":
            support_samples = {receipt.get("sample_id") for receipt in support}
            require(len(support_samples) >= 2, f"{rule_id} cannot be stable without multiple independent samples")

    require(actual_rule_ids == rule_ids, "registry rule_ids do not exactly match ordered rule catalogue")
    require(actual_stable_ids == stable_rule_ids, "registry stable_rule_ids do not match stable rule states")

    voice_rules = voice_rules_doc["rules"]
    actual_voice_rule_ids: list[str] = []
    actual_stable_voice_ids: list[str] = []
    for rule in voice_rules:
        require(isinstance(rule, dict), "each voice rule must be an object")
        rule_id = rule.get("rule_id")
        require(isinstance(rule_id, str) and VOICE_RULE_ID.fullmatch(rule_id) is not None, f"invalid voice rule id: {rule_id!r}")
        require(rule_id not in actual_voice_rule_ids, f"duplicate voice rule {rule_id}")
        actual_voice_rule_ids.append(rule_id)
        status = rule.get("status")
        require(status in RULE_STATES, f"{rule_id} has invalid state {status!r}")
        if status == "stable":
            actual_stable_voice_ids.append(rule_id)

        register_markers = rule.get("register_markers")
        require(isinstance(register_markers, list), f"{rule_id} register_markers must be an array")
        support = rule.get("support")
        require(isinstance(support, list), f"{rule_id} support must be an array")
        for receipt in support:
            require(isinstance(receipt, dict), f"{rule_id} support receipt must be an object")
            sample_id = receipt.get("sample_id")
            require(sample_id in observations_by_sample, f"{rule_id} references unknown sample {sample_id!r}")
            observation_ids = receipt.get("observation_ids")
            require(isinstance(observation_ids, list) and observation_ids, f"{rule_id}/{sample_id} requires observation ids")
            missing = set(observation_ids) - observations_by_sample[sample_id]
            require(not missing, f"{rule_id}/{sample_id} references unknown observations: {sorted(missing)}")

        if status == "stable":
            support_samples = {receipt.get("sample_id") for receipt in support}
            require(len(support_samples) >= 2, f"{rule_id} cannot be stable without multiple independent samples")

    require(actual_voice_rule_ids == voice_rule_ids, "registry voice_rule_ids do not exactly match ordered voice rule catalogue")
    require(actual_stable_voice_ids == stable_voice_rule_ids, "registry stable_voice_rule_ids do not match stable voice rule states")

    batches = batch_doc["batches"]
    require(batch_doc.get("batch_count") == len(batches), "batch_count does not match batch array")
    actual_batch_ids: list[str] = []
    for batch in batches:
        require(isinstance(batch, dict), "each batch result must be an object")
        batch_id = batch.get("batch_id")
        require(isinstance(batch_id, str) and BATCH_ID.fullmatch(batch_id) is not None, f"invalid batch id: {batch_id!r}")
        require(batch_id not in actual_batch_ids, f"duplicate batch {batch_id}")
        actual_batch_ids.append(batch_id)
        sample_id = batch.get("sample_id")
        require(sample_id in observations_by_sample, f"{batch_id} references unknown sample {sample_id!r}")
        for field in ("topic", "source_class", "article_result", "method_result", "voice_result"):
            require(isinstance(batch.get(field), str) and batch[field].strip(), f"{batch_id} {field} must be non-empty text")
        companion_audit = batch.get("companion_audit")
        require(isinstance(companion_audit, dict), f"{batch_id} companion_audit must be an object")
        if "cards" in companion_audit:
            cards = companion_audit.get("cards")
            require(isinstance(cards, int) and cards >= 0, f"{batch_id} companion card count must be a non-negative integer")
            for field in ("semantic_passes", "semantic_failures", "strict_render_passes", "strict_render_failures"):
                value = companion_audit.get(field)
                require(isinstance(value, int) and value >= 0, f"{batch_id} {field} must be a non-negative integer")
            require(companion_audit["semantic_passes"] + companion_audit["semantic_failures"] == cards, f"{batch_id} semantic card count mismatch")
            require(companion_audit["strict_render_passes"] + companion_audit["strict_render_failures"] == cards, f"{batch_id} strict-render card count mismatch")
        for field in ("induced_rule_ids", "qualified_rule_ids"):
            ids = batch.get(field)
            require(isinstance(ids, list), f"{batch_id} {field} must be an array")
            require(set(ids).issubset(set(rule_ids)), f"{batch_id} {field} references unknown processing rules")
        voice_ids = batch.get("induced_voice_rule_ids")
        require(isinstance(voice_ids, list), f"{batch_id} induced_voice_rule_ids must be an array")
        require(set(voice_ids).issubset(set(voice_rule_ids)), f"{batch_id} induced_voice_rule_ids references unknown voice rules")
        contamination_ids = batch.get("contamination_note_ids")
        require(isinstance(contamination_ids, list), f"{batch_id} contamination_note_ids must be an array")

    require(actual_batch_ids == batch_ids, "registry batch_ids do not exactly match ordered batch result index")

    return {
        "samples": len(sample_ids),
        "rules": len(rules),
        "stable_rules": len(actual_stable_ids),
        "voice_rules": len(voice_rules),
        "batches": len(batches),
        "contamination_notes": contamination_count,
        "strict_render_failures": strict_render_failures,
        "semantic_failures": semantic_failures,
    }


def main() -> int:
    try:
        counts = validate()
    except ValidationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print("PASS: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
