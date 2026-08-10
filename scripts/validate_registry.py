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
    require(isinstance(registry, dict), "registry must be an object")
    require(isinstance(rules_doc, dict) and isinstance(rules_doc.get("rules"), list), "rules document must contain a rules array")

    sample_ids = registry.get("sample_ids")
    rule_ids = registry.get("rule_ids")
    stable_rule_ids = registry.get("stable_rule_ids")
    require(isinstance(sample_ids, list) and sample_ids, "registry sample_ids must be a non-empty array")
    require(isinstance(rule_ids, list), "registry rule_ids must be an array")
    require(isinstance(stable_rule_ids, list), "registry stable_rule_ids must be an array")
    require(len(sample_ids) == len(set(sample_ids)), "duplicate sample_ids in registry")
    require(len(rule_ids) == len(set(rule_ids)), "duplicate rule_ids in registry")

    observations_by_sample: dict[str, set[str]] = {}
    contamination_count = 0
    strict_render_failures = 0
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
            for card in cards:
                require(isinstance(card, dict), f"{sample_id} storyboard card must be an object")
                card_id = card.get("card_id")
                require(isinstance(card_id, str) and CARD_ID.fullmatch(card_id) is not None, f"{sample_id} invalid card id")
                require(card_id not in card_ids, f"{sample_id} duplicate card {card_id}")
                image_digest = card.get("image_sha256")
                require(isinstance(image_digest, str) and SHA256.fullmatch(image_digest) is not None, f"{sample_id}/{card_id} invalid image sha256")
                strict_audit = card.get("strict_render_audit")
                require(isinstance(strict_audit, dict) and strict_audit.get("status") in {"pass", "fail"}, f"{sample_id}/{card_id} invalid strict render audit")
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
            strict_render_failures += observed_failures

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

    return {
        "samples": len(sample_ids),
        "rules": len(rules),
        "stable_rules": len(actual_stable_ids),
        "contamination_notes": contamination_count,
        "strict_render_failures": strict_render_failures,
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
