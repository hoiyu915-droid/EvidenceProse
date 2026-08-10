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
    for sample_id in sample_ids:
        require(isinstance(sample_id, str) and SAMPLE_ID.fullmatch(sample_id) is not None, f"invalid sample id: {sample_id!r}")
        sample_path = ROOT / f"data/samples/{sample_id}/sample.json"
        sample = load_json(sample_path)
        require(isinstance(sample, dict), f"{sample_id} sample must be an object")
        require(sample.get("sample_id") == sample_id, f"{sample_id} identity mismatch")
        article_path = sample.get("article_path")
        require(isinstance(article_path, str), f"{sample_id} article_path must be a string")
        require((ROOT / article_path).is_file(), f"{sample_id} article file is missing: {article_path}")

        observations = sample.get("observations")
        require(isinstance(observations, list) and observations, f"{sample_id} requires observations")
        observation_ids: set[str] = set()
        for observation in observations:
            require(isinstance(observation, dict), f"{sample_id} observation must be an object")
            observation_id = observation.get("observation_id")
            require(isinstance(observation_id, str) and OBSERVATION_ID.fullmatch(observation_id) is not None, f"{sample_id} invalid observation id")
            require(observation_id not in observation_ids, f"{sample_id} duplicate observation {observation_id}")
            locations = observation.get("article_locations")
            require(isinstance(locations, list) and locations, f"{sample_id}/{observation_id} requires article locations")
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

    require(actual_rule_ids == rule_ids, "registry rule_ids do not exactly match ordered rule catalogue")
    require(actual_stable_ids == stable_rule_ids, "registry stable_rule_ids do not match stable rule states")
    require(not stable_rule_ids, "initial S001 registry must not promote any rule to stable")

    return {
        "samples": len(sample_ids),
        "rules": len(rules),
        "stable_rules": len(actual_stable_ids),
        "contamination_notes": contamination_count,
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

