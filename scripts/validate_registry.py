#!/usr/bin/env python3
"""Fail-closed structural validation for the EvidenceProse registry."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ID = re.compile(r"^S\d{3}$")
RULE_ID = re.compile(r"^R\d{3}$")
VOICE_RULE_ID = re.compile(r"^V\d{3}$")
BATCH_ID = re.compile(r"^B\d{3}$")
OBSERVATION_ID = re.compile(r"^O\d{3}$")
ARTIFACT_ID = re.compile(r"^A\d{3}$")
CARD_ID = re.compile(r"^C\d{2}$")
CONTAMINATION_ID = re.compile(r"^C\d{3}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")

RULE_STATES = {"hypothesis", "candidate", "conditional", "stable", "contradicted", "rejected"}
METHOD_CATEGORIES = {
    "architecture",
    "claim_transform",
    "calibration",
    "provenance",
    "mechanism",
    "limitations",
    "decision_positioning",
    "evidence_grade",
    "quantitative_semantics",
}
OBSERVATION_KINDS = METHOD_CATEGORIES | {"companion_artifact", "voice_register"}
VOICE_CATEGORIES = {"stance", "attribution", "sentence_posture", "reader_address", "density"}
CONFIDENCE_LEVELS = {"low", "moderate", "high"}
VALIDATOR_POTENTIALS = {"none", "manual", "partial", "automatable"}
VERIFICATION_STATES = {"metadata_only", "abstract", "full_text", "full_text_audited"}
ARTIFACT_KINDS = {"source_pdf", "canonical_render_queue", "alternate_render_queue", "rendered_cardset"}
SOURCE_RESOLUTIONS = {"library_selected", "current_upload_fallback", "unresolved"}
SOURCE_SEARCH_STRATEGIES = {"doi", "exact_title", "filename", "supplement", "data"}
READER_DIMENSION_STATES = {"clear", "not_clear", "distorted"}


class ValidationError(Exception):
    """Raised when the registry is internally inconsistent."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def load_json(path: Path, root: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load {relative(path, root)}: {exc}") from exc


def parse_date(value: object, label: str) -> date:
    require(isinstance(value, str), f"{label} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{label} must be an ISO date: {value!r}") from exc


def parse_datetime(value: object, label: str) -> datetime:
    require(isinstance(value, str), f"{label} must be an ISO date-time")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{label} must be an ISO date-time: {value!r}") from exc
    require(parsed.tzinfo is not None, f"{label} must include a timezone offset")
    return parsed


def non_empty_text(value: object, label: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{label} must be non-empty text")
    return value


def string_list(value: object, label: str, *, non_empty: bool = False) -> list[str]:
    require(isinstance(value, list), f"{label} must be an array")
    if non_empty:
        require(bool(value), f"{label} must not be empty")
    require(all(isinstance(item, str) and item.strip() for item in value), f"{label} must contain non-empty strings")
    require(len(value) == len(set(value)), f"{label} contains duplicates")
    return value


def exact_keys(document: dict[str, Any], required: set[str], optional: set[str], label: str) -> None:
    missing = required - document.keys()
    unexpected = document.keys() - required - optional
    require(not missing, f"{label} is missing fields: {sorted(missing)}")
    require(not unexpected, f"{label} has unexpected fields: {sorted(unexpected)}")


def integer(value: object, label: str, *, minimum: int = 0) -> int:
    require(isinstance(value, int) and not isinstance(value, bool) and value >= minimum, f"{label} must be an integer >= {minimum}")
    return value


def repository_file(root: Path, raw_path: object, label: str) -> Path:
    path_text = non_empty_text(raw_path, label)
    require(not Path(path_text).is_absolute(), f"{label} must be repository-relative")
    root = root.resolve()
    path = (root / path_text).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValidationError(f"{label} escapes the repository: {path_text}") from exc
    require(path.is_file(), f"{label} is missing: {path_text}")
    return path


def validate_reader_outcome(
    outcome: object,
    card_ids: list[str],
    label: str,
) -> list[str]:
    require(isinstance(outcome, dict), f"{label} must be an object")
    exact_keys(
        outcome,
        {
            "status",
            "central_claim",
            "evidence_weight",
            "limitations",
            "applicability",
            "misuse_boundaries",
            "blocking_card_ids",
            "interpretation",
        },
        set(),
        label,
    )
    status = outcome.get("status")
    require(status in {"communicated", "materially_incomplete", "misleading"}, f"{label} has invalid status")
    dimensions = []
    for field in ("central_claim", "evidence_weight", "limitations", "applicability", "misuse_boundaries"):
        value = outcome.get(field)
        require(value in READER_DIMENSION_STATES, f"{label} has invalid {field}")
        dimensions.append(value)
    blocking_ids = string_list(outcome.get("blocking_card_ids"), f"{label} blocking_card_ids")
    require(set(blocking_ids).issubset(card_ids), f"{label} references unknown blocking cards")
    non_empty_text(outcome.get("interpretation"), f"{label} interpretation")
    if status == "communicated":
        require(not blocking_ids, f"{label} communicated outcome cannot have blocking cards")
        require(all(value == "clear" for value in dimensions), f"{label} communicated outcome requires all dimensions clear")
    else:
        require(bool(blocking_ids), f"{label} non-communicated outcome requires blocking cards")
        require(any(value != "clear" for value in dimensions), f"{label} non-communicated outcome requires a non-clear dimension")
        if status == "misleading":
            require("distorted" in dimensions, f"{label} misleading outcome requires a distorted dimension")
    return blocking_ids


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_support(
    rule: dict[str, Any],
    rule_id: str,
    observations_by_sample: dict[str, dict[str, str]],
    sample_dates: dict[str, date],
    expected_kind: str | None,
) -> tuple[set[str], set[str], date | None]:
    support = rule.get("support")
    require(isinstance(support, list), f"{rule_id} support must be an array")
    support_samples: set[str] = set()
    evidence_dates: list[date] = []
    for receipt in support:
        require(isinstance(receipt, dict), f"{rule_id} support receipt must be an object")
        exact_keys(receipt, {"sample_id", "observation_ids"}, set(), f"{rule_id} support receipt")
        sample_id = receipt.get("sample_id")
        require(sample_id in observations_by_sample, f"{rule_id} references unknown sample {sample_id!r}")
        require(sample_id not in support_samples, f"{rule_id} has duplicate support receipt for {sample_id}")
        observation_ids = string_list(receipt.get("observation_ids"), f"{rule_id}/{sample_id} observation_ids", non_empty=True)
        missing = set(observation_ids) - set(observations_by_sample[sample_id])
        require(not missing, f"{rule_id}/{sample_id} references unknown observations: {sorted(missing)}")
        if expected_kind is not None:
            wrong_kinds = {
                observation_id: observations_by_sample[sample_id][observation_id]
                for observation_id in observation_ids
                if observations_by_sample[sample_id][observation_id] != expected_kind
            }
            require(not wrong_kinds, f"{rule_id}/{sample_id} support has wrong observation kinds: {wrong_kinds}")
        support_samples.add(sample_id)
        evidence_dates.append(sample_dates[sample_id])

    counterexamples = rule.get("counterexamples")
    require(isinstance(counterexamples, list), f"{rule_id} counterexamples must be an array")
    counterexample_samples: set[str] = set()
    for counterexample in counterexamples:
        require(isinstance(counterexample, dict), f"{rule_id} counterexample must be an object")
        exact_keys(counterexample, {"sample_id", "description"}, set(), f"{rule_id} counterexample")
        sample_id = counterexample.get("sample_id")
        require(sample_id in observations_by_sample, f"{rule_id} counterexample references unknown sample {sample_id!r}")
        require(sample_id not in counterexample_samples, f"{rule_id} has duplicate counterexample for {sample_id}")
        non_empty_text(counterexample.get("description"), f"{rule_id}/{sample_id} counterexample description")
        counterexample_samples.add(sample_id)
        evidence_dates.append(sample_dates[sample_id])

    overlap = support_samples & counterexample_samples
    require(not overlap, f"{rule_id} treats samples as both support and counterexample: {sorted(overlap)}")
    return support_samples, counterexample_samples, max(evidence_dates) if evidence_dates else None


def validate(root: Path = ROOT) -> dict[str, int]:
    root = root.resolve()
    registry = load_json(root / "data/registry.json", root)
    require(isinstance(registry, dict), "registry must be an object")
    exact_keys(
        registry,
        {
            "schema_version",
            "project_phase",
            "primary_language",
            "sample_ids",
            "rule_ids",
            "stable_rule_ids",
            "voice_rule_ids",
            "stable_voice_rule_ids",
            "batch_ids",
            "rules_path",
            "batch_results_path",
            "voice_rules_path",
            "last_updated",
        },
        set(),
        "registry",
    )
    non_empty_text(registry.get("schema_version"), "registry schema_version")
    non_empty_text(registry.get("project_phase"), "registry project_phase")
    require(registry.get("primary_language") == "zh-Hant", "registry primary_language must be zh-Hant")
    registry_date = parse_date(registry.get("last_updated"), "registry last_updated")

    rules_path = repository_file(root, registry.get("rules_path"), "registry rules_path")
    voice_rules_path = repository_file(root, registry.get("voice_rules_path"), "registry voice_rules_path")
    batch_path = repository_file(root, registry.get("batch_results_path"), "registry batch_results_path")
    rules_doc = load_json(rules_path, root)
    voice_rules_doc = load_json(voice_rules_path, root)
    batch_doc = load_json(batch_path, root)
    require(isinstance(rules_doc, dict), "rules document must be an object")
    require(isinstance(voice_rules_doc, dict), "voice rules document must be an object")
    require(isinstance(batch_doc, dict), "batch results document must be an object")
    exact_keys(rules_doc, {"schema_version", "last_updated", "rules"}, set(), "rules document")
    exact_keys(voice_rules_doc, {"schema_version", "last_updated", "layer", "not_persona", "definition", "rules"}, set(), "voice rules document")
    exact_keys(batch_doc, {"schema_version", "last_updated", "batch_count", "batches", "cross_batch_summary"}, set(), "batch results document")
    non_empty_text(rules_doc.get("schema_version"), "rules schema_version")
    non_empty_text(voice_rules_doc.get("schema_version"), "voice rules schema_version")
    non_empty_text(batch_doc.get("schema_version"), "batch schema_version")
    rules_date = parse_date(rules_doc.get("last_updated"), "rules last_updated")
    voice_rules_date = parse_date(voice_rules_doc.get("last_updated"), "voice rules last_updated")
    batch_date = parse_date(batch_doc.get("last_updated"), "batch last_updated")
    require(voice_rules_doc.get("layer") == "article_register", "voice rules layer must be article_register")
    require(voice_rules_doc.get("not_persona") is True, "voice rules not_persona must be true")
    non_empty_text(voice_rules_doc.get("definition"), "voice rules definition")

    sample_ids = string_list(registry.get("sample_ids"), "registry sample_ids", non_empty=True)
    rule_ids = string_list(registry.get("rule_ids"), "registry rule_ids")
    stable_rule_ids = string_list(registry.get("stable_rule_ids"), "registry stable_rule_ids")
    voice_rule_ids = string_list(registry.get("voice_rule_ids"), "registry voice_rule_ids")
    stable_voice_rule_ids = string_list(registry.get("stable_voice_rule_ids"), "registry stable_voice_rule_ids")
    batch_ids = string_list(registry.get("batch_ids"), "registry batch_ids", non_empty=True)
    require(all(SAMPLE_ID.fullmatch(value) for value in sample_ids), "registry contains invalid sample id")
    require(all(RULE_ID.fullmatch(value) for value in rule_ids), "registry contains invalid rule id")
    require(all(VOICE_RULE_ID.fullmatch(value) for value in voice_rule_ids), "registry contains invalid voice rule id")
    require(all(BATCH_ID.fullmatch(value) for value in batch_ids), "registry contains invalid batch id")
    require(sample_ids == sorted(sample_ids), "registry sample_ids must be ordered")
    require(rule_ids == sorted(rule_ids), "registry rule_ids must be ordered")
    require(voice_rule_ids == sorted(voice_rule_ids), "registry voice_rule_ids must be ordered")
    require(batch_ids == sorted(batch_ids), "registry batch_ids must be ordered")

    sample_root = root / "data/samples"
    require(sample_root.is_dir(), "data/samples directory is missing")
    discovered_sample_ids = sorted(
        path.name for path in sample_root.iterdir() if path.is_dir() and (path / "sample.json").is_file()
    )
    require(discovered_sample_ids == sample_ids, "registered samples do not exactly match sample directories")

    observations_by_sample: dict[str, dict[str, str]] = {}
    contamination_ids_by_sample: dict[str, list[str]] = {}
    sample_dates: dict[str, date] = {}
    storyboard_summaries: dict[str, dict[str, Any]] = {}
    storyboard_failures: dict[str, dict[str, list[str]]] = {}
    contamination_count = 0
    artifact_count = 0
    card_count = 0
    historical_text_wording_divergences = 0
    content_truth_failures = 0
    render_fidelity_failures = 0
    reader_outcome_blocking_cards = 0

    sample_required = {
        "sample_id",
        "title",
        "language",
        "article_path",
        "article_sha256",
        "source",
        "source_resolution",
        "study_profile",
        "observations",
        "contamination_notes",
        "analysis_date",
    }
    sample_optional = {"card_storyboard_path", "artifact_receipts"}

    for sample_id in sample_ids:
        sample_path = root / f"data/samples/{sample_id}/sample.json"
        sample = load_json(sample_path, root)
        require(isinstance(sample, dict), f"{sample_id} sample must be an object")
        exact_keys(sample, sample_required, sample_optional, f"{sample_id} sample")
        require(sample.get("sample_id") == sample_id, f"{sample_id} identity mismatch")
        non_empty_text(sample.get("title"), f"{sample_id} title")
        require(sample.get("language") == "zh-Hant", f"{sample_id} language must be zh-Hant")
        sample_date = parse_date(sample.get("analysis_date"), f"{sample_id} analysis_date")
        require(sample_date <= registry_date, f"{sample_id} analysis_date is newer than registry last_updated")
        sample_dates[sample_id] = sample_date

        expected_article_path = f"data/samples/{sample_id}/article.md"
        require(sample.get("article_path") == expected_article_path, f"{sample_id} article_path must be {expected_article_path}")
        article_path = repository_file(root, sample.get("article_path"), f"{sample_id} article_path")
        article_digest = sample.get("article_sha256")
        require(isinstance(article_digest, str) and SHA256.fullmatch(article_digest) is not None, f"{sample_id} article_sha256 is invalid")
        require(file_sha256(article_path) == article_digest, f"{sample_id} article digest mismatch")

        source = sample.get("source")
        require(isinstance(source, dict), f"{sample_id} source must be an object")
        exact_keys(source, {"citation", "doi", "verification_state"}, {"pdf_sha256"}, f"{sample_id} source")
        non_empty_text(source.get("citation"), f"{sample_id} source citation")
        doi = non_empty_text(source.get("doi"), f"{sample_id} source doi")
        require(doi.startswith("10."), f"{sample_id} source doi is invalid")
        verification_state = source.get("verification_state")
        require(verification_state in VERIFICATION_STATES, f"{sample_id} verification_state is invalid")
        pdf_digest = source.get("pdf_sha256")
        if pdf_digest is not None:
            require(isinstance(pdf_digest, str) and SHA256.fullmatch(pdf_digest) is not None, f"{sample_id} source pdf_sha256 is invalid")
        if verification_state in {"full_text", "full_text_audited"}:
            require(pdf_digest is not None, f"{sample_id} full-text verification requires pdf_sha256")

        source_resolution = sample.get("source_resolution")
        require(isinstance(source_resolution, dict), f"{sample_id} source_resolution must be an object")
        exact_keys(
            source_resolution,
            {"searched_at", "stage", "query_keys", "searches", "resolution", "selected_pdf", "fallback"},
            set(),
            f"{sample_id} source_resolution",
        )
        parse_datetime(source_resolution.get("searched_at"), f"{sample_id} source_resolution searched_at")
        require(source_resolution.get("stage") in {"pre_audit", "retrospective_backfill"}, f"{sample_id} source_resolution stage is invalid")
        query_keys = source_resolution.get("query_keys")
        require(isinstance(query_keys, dict), f"{sample_id} source_resolution query_keys must be an object")
        exact_keys(query_keys, {"title", "doi", "filename"}, {"authors", "year"}, f"{sample_id} source_resolution query_keys")
        for field in ("title", "doi", "filename"):
            non_empty_text(query_keys.get(field), f"{sample_id} source_resolution query_keys {field}")
        require(query_keys["doi"] == doi, f"{sample_id} source_resolution DOI must match source DOI")
        if "authors" in query_keys:
            string_list(query_keys["authors"], f"{sample_id} source_resolution query_keys authors")
        if "year" in query_keys:
            year = query_keys["year"]
            require(year is None or isinstance(year, int) and not isinstance(year, bool) and year >= 1900, f"{sample_id} source_resolution query_keys year is invalid")

        searches = source_resolution.get("searches")
        require(isinstance(searches, list) and searches, f"{sample_id} source_resolution searches must not be empty")
        primary_strategies: list[str] = []
        found_primary = False
        found_primary_candidates: set[str] = set()
        for index, search in enumerate(searches, start=1):
            require(isinstance(search, dict), f"{sample_id} source search must be an object")
            exact_keys(
                search,
                {"priority", "target_kind", "strategy", "query", "query_keys_used", "search_title_only", "outcome", "candidate_library_file_ids"},
                set(),
                f"{sample_id} source search {index}",
            )
            require(integer(search.get("priority"), f"{sample_id} source search {index} priority", minimum=1) == index, f"{sample_id} source search priorities must be contiguous and ordered")
            target_kind = search.get("target_kind")
            require(target_kind in {"source_pdf", "supplement", "data"}, f"{sample_id} source search {index} target_kind is invalid")
            strategy = search.get("strategy")
            require(strategy in SOURCE_SEARCH_STRATEGIES, f"{sample_id} source search {index} strategy is invalid")
            non_empty_text(search.get("query"), f"{sample_id} source search {index} query")
            used_keys = string_list(search.get("query_keys_used"), f"{sample_id} source search {index} query_keys_used", non_empty=True)
            require(len(used_keys) == len(set(used_keys)), f"{sample_id} source search {index} query keys must be unique")
            require(set(used_keys).issubset(query_keys), f"{sample_id} source search {index} references unavailable query keys")
            require(isinstance(search.get("search_title_only"), bool), f"{sample_id} source search {index} search_title_only must be boolean")
            outcome = search.get("outcome")
            require(outcome in {"found", "not_found"}, f"{sample_id} source search {index} outcome is invalid")
            candidates = string_list(search.get("candidate_library_file_ids"), f"{sample_id} source search {index} candidate ids")
            require(len(candidates) == len(set(candidates)), f"{sample_id} source search {index} candidate ids must be unique")
            require(bool(candidates) == (outcome == "found"), f"{sample_id} source search {index} candidates disagree with outcome")
            if target_kind == "source_pdf":
                require(strategy in {"doi", "exact_title", "filename"}, f"{sample_id} primary PDF search uses non-primary strategy")
                require(not found_primary, f"{sample_id} continued primary PDF search after a source was found")
                required_query_key = {"doi": "doi", "exact_title": "title", "filename": "filename"}[strategy]
                require(required_query_key in used_keys, f"{sample_id} {strategy} search must use the {required_query_key} query key")
                primary_strategies.append(strategy)
                if outcome == "found":
                    found_primary = True
                    found_primary_candidates.update(candidates)
            else:
                require(strategy == target_kind, f"{sample_id} {target_kind} lookup must use matching strategy")
                require(
                    found_primary or primary_strategies == ["doi", "exact_title", "filename"],
                    f"{sample_id} supplement/data search precedes primary PDF resolution or exhaustion",
                )
        expected_primary_prefix = ["doi", "exact_title", "filename"][:len(primary_strategies)]
        require(primary_strategies == expected_primary_prefix, f"{sample_id} primary PDF search order must be DOI, exact title, then filename")
        require(primary_strategies and primary_strategies[0] == "doi", f"{sample_id} primary PDF search must begin with DOI")

        resolution = source_resolution.get("resolution")
        require(resolution in SOURCE_RESOLUTIONS, f"{sample_id} source_resolution resolution is invalid")
        selected_pdf = source_resolution.get("selected_pdf")
        fallback = source_resolution.get("fallback")
        require(isinstance(fallback, dict), f"{sample_id} source_resolution fallback must be an object")
        exact_keys(fallback, {"used", "reason"}, set(), f"{sample_id} source_resolution fallback")
        require(isinstance(fallback.get("used"), bool), f"{sample_id} source_resolution fallback used must be boolean")
        reason = fallback.get("reason")
        require(reason is None or isinstance(reason, str) and reason.strip(), f"{sample_id} source_resolution fallback reason must be null or non-empty text")
        if resolution == "library_selected":
            require(found_primary, f"{sample_id} library selection requires a successful primary PDF search")
            require(isinstance(selected_pdf, dict), f"{sample_id} library-selected PDF must be an object")
            exact_keys(selected_pdf, {"origin", "library_file_id", "file_id", "library_path", "filename", "version", "version_state", "sha256"}, set(), f"{sample_id} selected library PDF")
            require(selected_pdf.get("origin") == "library", f"{sample_id} library-selected PDF origin is invalid")
            for field in ("library_file_id", "file_id", "library_path", "filename"):
                non_empty_text(selected_pdf.get(field), f"{sample_id} selected library PDF {field}")
            require(selected_pdf["library_file_id"] in found_primary_candidates, f"{sample_id} selected Library PDF was not returned by the successful search")
            require(selected_pdf.get("version_state") in {"recorded", "not_exposed"}, f"{sample_id} selected library PDF version_state is invalid")
            version = selected_pdf.get("version")
            if selected_pdf["version_state"] == "not_exposed":
                require(version is None, f"{sample_id} unexposed Library version must be null")
            else:
                require((isinstance(version, int) and not isinstance(version, bool) and version >= 0) or isinstance(version, str) and version.isdigit(), f"{sample_id} recorded Library version is invalid")
            require(fallback == {"used": False, "reason": None}, f"{sample_id} Library selection cannot use fallback")
        elif resolution == "current_upload_fallback":
            require(not found_primary and primary_strategies == ["doi", "exact_title", "filename"], f"{sample_id} upload fallback requires exhausting Library DOI/title/filename search")
            require(isinstance(selected_pdf, dict), f"{sample_id} upload-selected PDF must be an object")
            exact_keys(selected_pdf, {"origin", "upload_file_id", "workspace_path", "filename", "sha256"}, set(), f"{sample_id} selected upload PDF")
            require(selected_pdf.get("origin") == "current_upload", f"{sample_id} upload-selected PDF origin is invalid")
            for field in ("upload_file_id", "workspace_path", "filename"):
                non_empty_text(selected_pdf.get(field), f"{sample_id} selected upload PDF {field}")
            require(fallback.get("used") is True and isinstance(reason, str) and reason.strip(), f"{sample_id} upload fallback requires a reason")
        else:
            require(not found_primary and primary_strategies == ["doi", "exact_title", "filename"], f"{sample_id} unresolved source requires exhausting Library DOI/title/filename search")
            require(selected_pdf is None, f"{sample_id} unresolved source cannot select a PDF")
            require(fallback.get("used") is False and isinstance(reason, str) and reason.strip(), f"{sample_id} unresolved source requires a non-fallback reason")
        if selected_pdf is not None:
            selected_digest = selected_pdf.get("sha256")
            require(isinstance(selected_digest, str) and SHA256.fullmatch(selected_digest) is not None, f"{sample_id} selected PDF sha256 is invalid")
            require(selected_digest == pdf_digest, f"{sample_id} selected PDF digest does not match source pdf_sha256")

        study_profile = sample.get("study_profile")
        require(isinstance(study_profile, dict), f"{sample_id} study_profile must be an object")
        exact_keys(
            study_profile,
            {"study_type", "synthesis_mode", "included_reports", "total_participants", "quantitative_datasets", "follow_up", "not_applicable_reasons"},
            set(),
            f"{sample_id} study_profile",
        )
        non_empty_text(study_profile.get("study_type"), f"{sample_id} study_type")
        non_empty_text(study_profile.get("synthesis_mode"), f"{sample_id} synthesis_mode")
        integer(study_profile.get("included_reports"), f"{sample_id} included_reports")
        for field in ("total_participants", "quantitative_datasets"):
            value = study_profile.get(field)
            if value is not None:
                integer(value, f"{sample_id} {field}")
        follow_up = study_profile.get("follow_up")
        require(follow_up is None or isinstance(follow_up, str) and follow_up.strip(), f"{sample_id} follow_up must be null or non-empty text")
        not_applicable_reasons = study_profile.get("not_applicable_reasons")
        require(isinstance(not_applicable_reasons, dict), f"{sample_id} not_applicable_reasons must be an object")
        nullable_fields = {"total_participants", "quantitative_datasets", "follow_up"}
        require(set(not_applicable_reasons).issubset(nullable_fields), f"{sample_id} has unknown not_applicable reason fields")
        for field in nullable_fields:
            reason = not_applicable_reasons.get(field)
            if study_profile.get(field) is None:
                non_empty_text(reason, f"{sample_id} null {field} reason")
            else:
                require(reason is None, f"{sample_id} has a stale not_applicable reason for {field}")

        artifact_receipts = sample.get("artifact_receipts", [])
        require(isinstance(artifact_receipts, list), f"{sample_id} artifact_receipts must be an array")
        artifact_ids: set[str] = set()
        receipts_by_kind: dict[str, list[dict[str, Any]]] = {}
        for receipt in artifact_receipts:
            require(isinstance(receipt, dict), f"{sample_id} artifact receipt must be an object")
            exact_keys(receipt, {"artifact_id", "kind", "filename", "sha256", "role"}, set(), f"{sample_id} artifact receipt")
            artifact_id = receipt.get("artifact_id")
            require(isinstance(artifact_id, str) and ARTIFACT_ID.fullmatch(artifact_id) is not None, f"{sample_id} invalid artifact id")
            require(artifact_id not in artifact_ids, f"{sample_id} duplicate artifact {artifact_id}")
            kind = receipt.get("kind")
            require(kind in ARTIFACT_KINDS, f"{sample_id}/{artifact_id} invalid artifact kind")
            non_empty_text(receipt.get("filename"), f"{sample_id}/{artifact_id} filename")
            digest = receipt.get("sha256")
            require(isinstance(digest, str) and SHA256.fullmatch(digest) is not None, f"{sample_id}/{artifact_id} invalid sha256")
            non_empty_text(receipt.get("role"), f"{sample_id}/{artifact_id} role")
            artifact_ids.add(artifact_id)
            receipts_by_kind.setdefault(kind, []).append(receipt)
        artifact_count += len(artifact_receipts)
        if "source_pdf" in receipts_by_kind:
            require(len(receipts_by_kind["source_pdf"]) == 1, f"{sample_id} must not have multiple source_pdf receipts")
            require(receipts_by_kind["source_pdf"][0]["sha256"] == pdf_digest, f"{sample_id} source_pdf receipt does not match source digest")

        storyboard_path_value = sample.get("card_storyboard_path")
        expected_storyboard_file = root / f"data/samples/{sample_id}/card_storyboard.json"
        require(expected_storyboard_file.is_file() == (storyboard_path_value is not None), f"{sample_id} storyboard file and sample pointer disagree")
        if storyboard_path_value is not None:
            expected_storyboard_path = f"data/samples/{sample_id}/card_storyboard.json"
            require(storyboard_path_value == expected_storyboard_path, f"{sample_id} card_storyboard_path must be {expected_storyboard_path}")
            storyboard_path = repository_file(root, storyboard_path_value, f"{sample_id} card_storyboard_path")
            storyboard = load_json(storyboard_path, root)
            require(isinstance(storyboard, dict), f"{sample_id} storyboard must be an object")
            exact_keys(storyboard, {"sample_id", "audit_policy", "reader_contract", "canonical_queue", "rejected_queue", "cards", "summary"}, set(), f"{sample_id} storyboard")
            require(storyboard.get("sample_id") == sample_id, f"{sample_id} storyboard identity mismatch")
            require(len(receipts_by_kind.get("source_pdf", [])) == 1, f"{sample_id} storyboard requires one source_pdf receipt")
            require(len(receipts_by_kind.get("canonical_render_queue", [])) == 1, f"{sample_id} storyboard requires one canonical_render_queue receipt")
            require(len(receipts_by_kind.get("rendered_cardset", [])) == 1, f"{sample_id} storyboard requires one rendered_cardset receipt")
            require(bool(receipts_by_kind.get("alternate_render_queue")), f"{sample_id} storyboard requires an alternate_render_queue receipt for the rejected queue")

            audit_policy = storyboard.get("audit_policy")
            require(isinstance(audit_policy, dict), f"{sample_id} audit_policy must be an object")
            exact_keys(
                audit_policy,
                {"content_truth_track", "render_fidelity_track", "materiality_test", "engineering_conformance_track", "engineering_conformance_is_gate", "historical_text_comparison_track", "global_constraints_checked"},
                set(),
                f"{sample_id} audit_policy",
            )
            non_empty_text(audit_policy.get("content_truth_track"), f"{sample_id} content_truth_track")
            non_empty_text(audit_policy.get("render_fidelity_track"), f"{sample_id} render_fidelity_track")
            materiality_test = audit_policy.get("materiality_test")
            require(isinstance(materiality_test, dict), f"{sample_id} materiality_test must be an object")
            exact_keys(materiality_test, {"gate_only_substantive", "substantive_definition", "presentation_only_handling"}, set(), f"{sample_id} materiality_test")
            require(materiality_test.get("gate_only_substantive") is True, f"{sample_id} must gate only substantive defects")
            non_empty_text(materiality_test.get("substantive_definition"), f"{sample_id} substantive definition")
            non_empty_text(materiality_test.get("presentation_only_handling"), f"{sample_id} presentation-only handling")
            non_empty_text(audit_policy.get("engineering_conformance_track"), f"{sample_id} engineering conformance track")
            require(audit_policy.get("engineering_conformance_is_gate") is False, f"{sample_id} engineering conformance cannot be a quality gate")
            non_empty_text(audit_policy.get("historical_text_comparison_track"), f"{sample_id} historical text comparison track")
            string_list(audit_policy.get("global_constraints_checked"), f"{sample_id} global_constraints_checked")

            reader_contract = storyboard.get("reader_contract")
            require(isinstance(reader_contract, dict), f"{sample_id} reader_contract must be an object")
            exact_keys(reader_contract, {"central_claim", "evidence_weight", "limitations", "applicability", "misuse_boundaries"}, set(), f"{sample_id} reader_contract")
            for field in ("central_claim", "evidence_weight", "limitations", "applicability", "misuse_boundaries"):
                non_empty_text(reader_contract.get(field), f"{sample_id} reader_contract {field}")

            canonical_queue = storyboard.get("canonical_queue")
            require(isinstance(canonical_queue, dict), f"{sample_id} canonical_queue must be an object")
            exact_keys(canonical_queue, {"filename", "sha256", "plan_id", "binding_basis"}, set(), f"{sample_id} canonical_queue")
            for field in ("filename", "plan_id", "binding_basis"):
                non_empty_text(canonical_queue.get(field), f"{sample_id} canonical_queue {field}")
            require(isinstance(canonical_queue.get("sha256"), str) and SHA256.fullmatch(canonical_queue["sha256"]) is not None, f"{sample_id} canonical queue digest is invalid")
            canonical_receipt = receipts_by_kind["canonical_render_queue"][0]
            require(canonical_queue["filename"] == canonical_receipt["filename"], f"{sample_id} canonical queue filename does not match receipt")
            require(canonical_queue["sha256"] == canonical_receipt["sha256"], f"{sample_id} canonical queue digest does not match receipt")

            rejected_queue = storyboard.get("rejected_queue")
            require(isinstance(rejected_queue, dict), f"{sample_id} rejected_queue must be an object")
            exact_keys(rejected_queue, {"filename", "sha256", "reason"}, set(), f"{sample_id} rejected_queue")
            non_empty_text(rejected_queue.get("filename"), f"{sample_id} rejected queue filename")
            non_empty_text(rejected_queue.get("reason"), f"{sample_id} rejected queue reason")
            require(isinstance(rejected_queue.get("sha256"), str) and SHA256.fullmatch(rejected_queue["sha256"]) is not None, f"{sample_id} rejected queue digest is invalid")
            alternate_receipts = receipts_by_kind.get("alternate_render_queue", [])
            require(any(receipt["filename"] == rejected_queue["filename"] and receipt["sha256"] == rejected_queue["sha256"] for receipt in alternate_receipts), f"{sample_id} rejected queue does not match an alternate receipt")

            cards = storyboard.get("cards")
            require(isinstance(cards, list) and cards, f"{sample_id} storyboard requires cards")
            card_ids: list[str] = []
            observed_historical_equivalent: list[str] = []
            observed_historical_divergence: list[str] = []
            observed_content_failures: list[str] = []
            observed_render_failures: list[str] = []
            targeted_failures: list[str] = []
            required_card_fields = {
                "card_id",
                "title",
                "visible_text",
                "allowed_visible_numbers",
                "main_visual_scene",
                "image_filename",
                "image_sha256",
                "content_truth_audit",
                "render_fidelity_audit",
            }
            optional_card_fields = {"historical_text_comparison", "targeted_audit", "required_correction"}
            for card in cards:
                require(isinstance(card, dict), f"{sample_id} storyboard card must be an object")
                exact_keys(card, required_card_fields, optional_card_fields, f"{sample_id} storyboard card")
                card_id = card.get("card_id")
                require(isinstance(card_id, str) and CARD_ID.fullmatch(card_id) is not None, f"{sample_id} invalid card id")
                require(card_id not in card_ids, f"{sample_id} duplicate card {card_id}")
                non_empty_text(card.get("title"), f"{sample_id}/{card_id} title")
                string_list(card.get("visible_text"), f"{sample_id}/{card_id} visible_text", non_empty=True)
                string_list(card.get("allowed_visible_numbers"), f"{sample_id}/{card_id} allowed_visible_numbers")
                non_empty_text(card.get("main_visual_scene"), f"{sample_id}/{card_id} main_visual_scene")
                non_empty_text(card.get("image_filename"), f"{sample_id}/{card_id} image_filename")
                image_digest = card.get("image_sha256")
                require(isinstance(image_digest, str) and SHA256.fullmatch(image_digest) is not None, f"{sample_id}/{card_id} invalid image sha256")

                for field, label, failures in (
                    ("content_truth_audit", "content truth", observed_content_failures),
                    ("render_fidelity_audit", "render fidelity", observed_render_failures),
                ):
                    audit = card.get(field)
                    require(isinstance(audit, dict), f"{sample_id}/{card_id} {label} audit must be an object")
                    exact_keys(audit, {"status", "violations"}, set(), f"{sample_id}/{card_id} {label} audit")
                    require(audit.get("status") in {"pass", "fail"}, f"{sample_id}/{card_id} invalid {label} status")
                    violations = audit.get("violations")
                    require(isinstance(violations, list), f"{sample_id}/{card_id} {label} violations must be an array")
                    require(all(isinstance(item, str) and item.strip() for item in violations), f"{sample_id}/{card_id} {label} violations must be non-empty text")
                    if audit["status"] == "fail":
                        require(bool(violations), f"{sample_id}/{card_id} failed {label} audit requires violations")
                        failures.append(card_id)
                    else:
                        require(not violations, f"{sample_id}/{card_id} passed {label} audit cannot retain violations")
                historical = card.get("historical_text_comparison")
                if historical is not None:
                    exact_keys(historical, {"status", "differences", "gating"}, set(), f"{sample_id}/{card_id} historical text comparison")
                    status = historical.get("status")
                    require(status in {"equivalent", "wording_divergence"}, f"{sample_id}/{card_id} invalid historical text comparison status")
                    differences = historical.get("differences")
                    require(isinstance(differences, list), f"{sample_id}/{card_id} historical differences must be an array")
                    require(all(isinstance(item, str) and item.strip() for item in differences), f"{sample_id}/{card_id} historical differences must be non-empty text")
                    require(historical.get("gating") is False, f"{sample_id}/{card_id} historical wording comparison cannot be gating")
                    if status == "wording_divergence":
                        require(bool(differences), f"{sample_id}/{card_id} wording divergence requires differences")
                        observed_historical_divergence.append(card_id)
                    else:
                        require(not differences, f"{sample_id}/{card_id} equivalent wording cannot retain differences")
                        observed_historical_equivalent.append(card_id)

                targeted_audit = card.get("targeted_audit")
                if targeted_audit is not None:
                    targeted_audit = non_empty_text(targeted_audit, f"{sample_id}/{card_id} targeted_audit")
                    if targeted_audit.startswith("fail"):
                        targeted_failures.append(card_id)
                correction = card.get("required_correction")
                require(correction is None or isinstance(correction, str) and correction.strip(), f"{sample_id}/{card_id} required_correction must be null or non-empty text")
                card_ids.append(card_id)

            expected_card_ids = [f"C{index:02d}" for index in range(1, len(cards) + 1)]
            require(card_ids == expected_card_ids, f"{sample_id} card ids must be contiguous and ordered")
            summary = storyboard.get("summary")
            require(isinstance(summary, dict), f"{sample_id} storyboard summary must be an object")
            exact_keys(
                summary,
                {"cards", "content_truth_failures", "content_truth_passes", "render_fidelity_failures", "render_fidelity_passes", "derived_reader_outcome", "interpretation"},
                {"historical_text_equivalent", "historical_text_wording_divergence", "targeted_correction_ids"},
                f"{sample_id} storyboard summary",
            )
            integer(summary.get("cards"), f"{sample_id} storyboard card count", minimum=1)
            require(summary["cards"] == len(cards), f"{sample_id} storyboard card count mismatch")
            expected_counts = {
                "content_truth_failures": len(observed_content_failures),
                "content_truth_passes": len(cards) - len(observed_content_failures),
                "render_fidelity_failures": len(observed_render_failures),
                "render_fidelity_passes": len(cards) - len(observed_render_failures),
            }
            if "historical_text_equivalent" in summary or "historical_text_wording_divergence" in summary:
                require("historical_text_equivalent" in summary and "historical_text_wording_divergence" in summary, f"{sample_id} historical text summary must include both counts")
                require(len(observed_historical_equivalent) + len(observed_historical_divergence) == len(cards), f"{sample_id} historical text comparison must cover every card")
                expected_counts["historical_text_equivalent"] = len(observed_historical_equivalent)
                expected_counts["historical_text_wording_divergence"] = len(observed_historical_divergence)
            else:
                require(not observed_historical_equivalent and not observed_historical_divergence, f"{sample_id} historical text cards require historical summary counts")
            for field, expected in expected_counts.items():
                integer(summary.get(field), f"{sample_id} {field}")
                require(summary[field] == expected, f"{sample_id} {field} count mismatch")
            non_empty_text(summary.get("interpretation"), f"{sample_id} storyboard interpretation")
            reader_blocking_ids = validate_reader_outcome(summary.get("derived_reader_outcome"), card_ids, f"{sample_id} derived_reader_outcome")
            require(reader_blocking_ids == observed_render_failures, f"{sample_id} reader blocking cards must equal substantive render failures")
            summary_targeted = string_list(summary.get("targeted_correction_ids", []), f"{sample_id} targeted_correction_ids")
            require(set(summary_targeted).issubset(targeted_failures), f"{sample_id} targeted correction ids do not match failed targeted audits")
            corrections_by_card = {card["card_id"]: card.get("required_correction") for card in cards}
            require(all(corrections_by_card[card_id] for card_id in summary_targeted), f"{sample_id} targeted correction ids require correction instructions")
            storyboard_summaries[sample_id] = summary
            storyboard_failures[sample_id] = {
                "content": observed_content_failures,
                "render": observed_render_failures,
                "historical": observed_historical_divergence,
                "targeted": summary_targeted,
                "reader": reader_blocking_ids,
            }
            card_count += len(cards)
            historical_text_wording_divergences += len(observed_historical_divergence)
            content_truth_failures += len(observed_content_failures)
            render_fidelity_failures += len(observed_render_failures)
            reader_outcome_blocking_cards += len(reader_blocking_ids)
        else:
            card_artifact_kinds = {"canonical_render_queue", "alternate_render_queue", "rendered_cardset"} & receipts_by_kind.keys()
            require(not card_artifact_kinds, f"{sample_id} has card artifact receipts without a storyboard")

        observations = sample.get("observations")
        require(isinstance(observations, list) and observations, f"{sample_id} requires observations")
        observation_kinds: dict[str, str] = {}
        for observation in observations:
            require(isinstance(observation, dict), f"{sample_id} observation must be an object")
            exact_keys(observation, {"observation_id", "kind", "description", "evidence_locations"}, set(), f"{sample_id} observation")
            observation_id = observation.get("observation_id")
            require(isinstance(observation_id, str) and OBSERVATION_ID.fullmatch(observation_id) is not None, f"{sample_id} invalid observation id")
            require(observation_id not in observation_kinds, f"{sample_id} duplicate observation {observation_id}")
            kind = observation.get("kind")
            require(kind in OBSERVATION_KINDS, f"{sample_id}/{observation_id} invalid observation kind")
            non_empty_text(observation.get("description"), f"{sample_id}/{observation_id} description")
            string_list(observation.get("evidence_locations"), f"{sample_id}/{observation_id} evidence_locations", non_empty=True)
            observation_kinds[observation_id] = kind
        observations_by_sample[sample_id] = observation_kinds

        contamination_notes = sample.get("contamination_notes")
        require(isinstance(contamination_notes, list), f"{sample_id} contamination_notes must be an array")
        note_ids: list[str] = []
        for note in contamination_notes:
            require(isinstance(note, dict), f"{sample_id} contamination note must be an object")
            exact_keys(note, {"note_id", "location", "issue", "preferred_handling"}, set(), f"{sample_id} contamination note")
            note_id = note.get("note_id")
            require(isinstance(note_id, str) and CONTAMINATION_ID.fullmatch(note_id) is not None, f"{sample_id} invalid contamination id")
            require(note_id not in note_ids, f"{sample_id} duplicate contamination note {note_id}")
            for field in ("location", "issue", "preferred_handling"):
                non_empty_text(note.get(field), f"{sample_id}/{note_id} {field}")
            note_ids.append(note_id)
        contamination_ids_by_sample[sample_id] = note_ids
        contamination_count += len(note_ids)

    latest_sample_date = max(sample_dates.values())
    require(registry_date == latest_sample_date, "registry last_updated must equal the latest sample analysis_date")
    require(rules_date == registry_date, "rules last_updated must match registry last_updated")
    require(voice_rules_date == registry_date, "voice rules last_updated must match registry last_updated")
    require(batch_date == registry_date, "batch last_updated must match registry last_updated")

    rules = rules_doc.get("rules")
    require(isinstance(rules, list), "rules document must contain a rules array")
    actual_rule_ids: list[str] = []
    actual_stable_ids: list[str] = []
    rule_support_samples: dict[str, set[str]] = {}
    rule_counterexample_samples: dict[str, set[str]] = {}
    rule_statuses: dict[str, str] = {}
    for rule in rules:
        require(isinstance(rule, dict), "each rule must be an object")
        exact_keys(
            rule,
            {"rule_id", "name", "category", "statement", "status", "applies_when", "does_not_apply_when", "support", "counterexamples", "confidence", "validator_potential", "last_updated"},
            set(),
            "method rule",
        )
        rule_id = rule.get("rule_id")
        require(isinstance(rule_id, str) and RULE_ID.fullmatch(rule_id) is not None, f"invalid rule id: {rule_id!r}")
        require(rule_id not in actual_rule_ids, f"duplicate rule {rule_id}")
        actual_rule_ids.append(rule_id)
        non_empty_text(rule.get("name"), f"{rule_id} name")
        non_empty_text(rule.get("statement"), f"{rule_id} statement")
        category = rule.get("category")
        require(category in METHOD_CATEGORIES, f"{rule_id} has invalid category {category!r}")
        status = rule.get("status")
        require(status in RULE_STATES, f"{rule_id} has invalid state {status!r}")
        rule_statuses[rule_id] = status
        if status == "stable":
            actual_stable_ids.append(rule_id)
        string_list(rule.get("applies_when"), f"{rule_id} applies_when")
        does_not_apply = string_list(rule.get("does_not_apply_when"), f"{rule_id} does_not_apply_when")
        require(rule.get("confidence") in CONFIDENCE_LEVELS, f"{rule_id} has invalid confidence")
        require(rule.get("validator_potential") in VALIDATOR_POTENTIALS, f"{rule_id} has invalid validator_potential")
        support_samples, counterexample_samples, latest_evidence_date = validate_support(
            rule, rule_id, observations_by_sample, sample_dates, category
        )
        rule_support_samples[rule_id] = support_samples
        rule_counterexample_samples[rule_id] = counterexample_samples
        updated = parse_date(rule.get("last_updated"), f"{rule_id} last_updated")
        if latest_evidence_date is not None:
            require(updated >= latest_evidence_date, f"{rule_id} last_updated predates referenced evidence")
        require(updated <= rules_date, f"{rule_id} last_updated is newer than the rules catalogue")
        if status in {"candidate", "stable"}:
            require(len(support_samples) >= 2, f"{rule_id} cannot be {status} without multiple independent samples")
        if status == "conditional":
            require(bool(support_samples), f"{rule_id} conditional rule requires support")
            require(bool(does_not_apply or counterexample_samples), f"{rule_id} conditional rule requires an explicit boundary")
        if status in {"contradicted", "rejected"}:
            require(bool(counterexample_samples), f"{rule_id} {status} rule requires counterexamples")

    require(actual_rule_ids == rule_ids, "registry rule_ids do not exactly match ordered rule catalogue")
    require(actual_stable_ids == stable_rule_ids, "registry stable_rule_ids do not match stable rule states")

    voice_rules = voice_rules_doc.get("rules")
    require(isinstance(voice_rules, list), "voice rules document must contain a rules array")
    actual_voice_rule_ids: list[str] = []
    actual_stable_voice_ids: list[str] = []
    voice_support_samples: dict[str, set[str]] = {}
    for rule in voice_rules:
        require(isinstance(rule, dict), "each voice rule must be an object")
        exact_keys(
            rule,
            {"rule_id", "name", "category", "statement", "register_markers", "status", "applies_when", "does_not_apply_when", "support", "counterexamples", "confidence", "validator_potential", "last_updated"},
            set(),
            "voice rule",
        )
        rule_id = rule.get("rule_id")
        require(isinstance(rule_id, str) and VOICE_RULE_ID.fullmatch(rule_id) is not None, f"invalid voice rule id: {rule_id!r}")
        require(rule_id not in actual_voice_rule_ids, f"duplicate voice rule {rule_id}")
        actual_voice_rule_ids.append(rule_id)
        non_empty_text(rule.get("name"), f"{rule_id} name")
        non_empty_text(rule.get("statement"), f"{rule_id} statement")
        require(rule.get("category") in VOICE_CATEGORIES, f"{rule_id} has invalid category")
        string_list(rule.get("register_markers"), f"{rule_id} register_markers")
        status = rule.get("status")
        require(status in RULE_STATES, f"{rule_id} has invalid state {status!r}")
        if status == "stable":
            actual_stable_voice_ids.append(rule_id)
        string_list(rule.get("applies_when"), f"{rule_id} applies_when")
        does_not_apply = string_list(rule.get("does_not_apply_when"), f"{rule_id} does_not_apply_when")
        require(rule.get("confidence") in CONFIDENCE_LEVELS, f"{rule_id} has invalid confidence")
        require(rule.get("validator_potential") in VALIDATOR_POTENTIALS, f"{rule_id} has invalid validator_potential")
        support_samples, counterexample_samples, latest_evidence_date = validate_support(
            rule, rule_id, observations_by_sample, sample_dates, "voice_register"
        )
        voice_support_samples[rule_id] = support_samples
        updated = parse_date(rule.get("last_updated"), f"{rule_id} last_updated")
        if latest_evidence_date is not None:
            require(updated >= latest_evidence_date, f"{rule_id} last_updated predates referenced evidence")
        require(updated <= voice_rules_date, f"{rule_id} last_updated is newer than the voice catalogue")
        if status in {"candidate", "stable"}:
            require(len(support_samples) >= 2, f"{rule_id} cannot be {status} without multiple independent samples")
        if status == "conditional":
            require(bool(support_samples), f"{rule_id} conditional rule requires support")
            require(bool(does_not_apply or counterexample_samples), f"{rule_id} conditional rule requires an explicit boundary")
        if status in {"contradicted", "rejected"}:
            require(bool(counterexample_samples), f"{rule_id} {status} rule requires counterexamples")

    require(actual_voice_rule_ids == voice_rule_ids, "registry voice_rule_ids do not exactly match ordered voice rule catalogue")
    require(actual_stable_voice_ids == stable_voice_rule_ids, "registry stable_voice_rule_ids do not match stable voice rule states")

    batches = batch_doc.get("batches")
    require(isinstance(batches, list), "batch results document must contain a batches array")
    require(batch_doc.get("batch_count") == len(batches), "batch_count does not match batch array")
    actual_batch_ids: list[str] = []
    batch_sample_ids: list[str] = []
    for batch in batches:
        require(isinstance(batch, dict), "each batch result must be an object")
        exact_keys(
            batch,
            {"batch_id", "sample_id", "topic", "source_class", "article_result", "method_result", "voice_result", "companion_audit", "induced_rule_ids", "qualified_rule_ids", "induced_voice_rule_ids", "contamination_note_ids"},
            {"canonical_queue_family"},
            "batch result",
        )
        batch_id = batch.get("batch_id")
        require(isinstance(batch_id, str) and BATCH_ID.fullmatch(batch_id) is not None, f"invalid batch id: {batch_id!r}")
        require(batch_id not in actual_batch_ids, f"duplicate batch {batch_id}")
        actual_batch_ids.append(batch_id)
        sample_id = batch.get("sample_id")
        require(sample_id in observations_by_sample, f"{batch_id} references unknown sample {sample_id!r}")
        require(sample_id not in batch_sample_ids, f"multiple batches reference sample {sample_id}")
        batch_sample_ids.append(sample_id)
        for field in ("topic", "source_class", "article_result", "method_result", "voice_result"):
            non_empty_text(batch.get(field), f"{batch_id} {field}")
        queue_family = batch.get("canonical_queue_family")
        require(queue_family is None or isinstance(queue_family, str) and queue_family.strip(), f"{batch_id} canonical_queue_family must be null or non-empty text")

        companion_audit = batch.get("companion_audit")
        require(isinstance(companion_audit, dict), f"{batch_id} companion_audit must be an object")
        non_empty_text(companion_audit.get("status"), f"{batch_id} companion audit status")
        if sample_id in storyboard_summaries:
            exact_keys(
                companion_audit,
                {"status", "cards", "content_truth_passes", "content_truth_failures", "render_fidelity_passes", "render_fidelity_failures", "engineering_conformance_is_gate", "derived_reader_outcome"},
                {"historical_text_equivalent", "historical_text_wording_divergence", "content_truth_failure_ids", "render_fidelity_failure_ids", "historical_text_wording_divergence_ids", "targeted_correction_ids", "content_truth_failure_note", "render_fidelity_failure_note", "historical_text_comparison_note"},
                f"{batch_id} companion_audit",
            )
            require(companion_audit.get("engineering_conformance_is_gate") is False, f"{batch_id} engineering conformance cannot be a quality gate")
            summary = storyboard_summaries[sample_id]
            for field in ("cards", "content_truth_passes", "content_truth_failures", "render_fidelity_passes", "render_fidelity_failures"):
                integer(companion_audit.get(field), f"{batch_id} {field}")
                require(companion_audit[field] == summary[field], f"{batch_id} {field} does not match storyboard")
            content_failure_ids = string_list(companion_audit.get("content_truth_failure_ids", []), f"{batch_id} content_truth_failure_ids")
            require(content_failure_ids == storyboard_failures[sample_id]["content"], f"{batch_id} content truth failure ids do not match storyboard")
            render_failure_ids = string_list(companion_audit.get("render_fidelity_failure_ids", []), f"{batch_id} render_fidelity_failure_ids")
            require(render_failure_ids == storyboard_failures[sample_id]["render"], f"{batch_id} render fidelity failure ids do not match storyboard")
            has_historical = any(field in companion_audit for field in ("historical_text_equivalent", "historical_text_wording_divergence", "historical_text_wording_divergence_ids"))
            if has_historical:
                for field in ("historical_text_equivalent", "historical_text_wording_divergence"):
                    integer(companion_audit.get(field), f"{batch_id} {field}")
                    require(companion_audit[field] == summary.get(field), f"{batch_id} {field} does not match storyboard")
                historical_ids = string_list(companion_audit.get("historical_text_wording_divergence_ids", []), f"{batch_id} historical_text_wording_divergence_ids")
                require(historical_ids == storyboard_failures[sample_id]["historical"], f"{batch_id} historical wording divergence ids do not match storyboard")
            else:
                require(not storyboard_failures[sample_id]["historical"], f"{batch_id} historical wording divergence cards require historical fields")
            targeted_ids = string_list(companion_audit.get("targeted_correction_ids", []), f"{batch_id} targeted_correction_ids")
            require(targeted_ids == storyboard_failures[sample_id]["targeted"], f"{batch_id} targeted correction ids do not match storyboard")
            for note_field in ("content_truth_failure_note", "render_fidelity_failure_note", "historical_text_comparison_note"):
                if companion_audit.get(note_field) is not None:
                    non_empty_text(companion_audit[note_field], f"{batch_id} {note_field}")
            batch_reader_ids = validate_reader_outcome(companion_audit.get("derived_reader_outcome"), [f"C{index:02d}" for index in range(1, summary["cards"] + 1)], f"{batch_id} derived_reader_outcome")
            require(batch_reader_ids == storyboard_failures[sample_id]["reader"], f"{batch_id} reader outcome does not match storyboard")
            require(companion_audit["derived_reader_outcome"] == summary["derived_reader_outcome"], f"{batch_id} derived reader outcome does not match storyboard")
        else:
            exact_keys(companion_audit, {"status", "note"}, set(), f"{batch_id} companion_audit")
            non_empty_text(companion_audit.get("note"), f"{batch_id} companion audit note")

        induced_rule_ids = string_list(batch.get("induced_rule_ids"), f"{batch_id} induced_rule_ids")
        qualified_rule_ids = string_list(batch.get("qualified_rule_ids"), f"{batch_id} qualified_rule_ids")
        induced_voice_rule_ids = string_list(batch.get("induced_voice_rule_ids"), f"{batch_id} induced_voice_rule_ids")
        require(set(induced_rule_ids).issubset(rule_ids), f"{batch_id} induced_rule_ids reference unknown processing rules")
        require(set(qualified_rule_ids).issubset(rule_ids), f"{batch_id} qualified_rule_ids reference unknown processing rules")
        require(set(induced_voice_rule_ids).issubset(voice_rule_ids), f"{batch_id} induced_voice_rule_ids reference unknown voice rules")
        for rule_id in induced_rule_ids:
            require(sample_id in rule_support_samples[rule_id], f"{batch_id} induces {rule_id} without support from {sample_id}")
        for rule_id in qualified_rule_ids:
            require(sample_id in rule_counterexample_samples[rule_id], f"{batch_id} qualifies {rule_id} without a counterexample from {sample_id}")
        for rule_id in induced_voice_rule_ids:
            require(sample_id in voice_support_samples[rule_id], f"{batch_id} induces {rule_id} without support from {sample_id}")
        contamination_ids = string_list(batch.get("contamination_note_ids"), f"{batch_id} contamination_note_ids")
        require(contamination_ids == contamination_ids_by_sample[sample_id], f"{batch_id} contamination notes do not match {sample_id}")

    require(actual_batch_ids == batch_ids, "registry batch_ids do not exactly match ordered batch result index")
    require(batch_sample_ids == sample_ids, "batch sample order does not exactly match registry sample order")

    cross_batch_summary = batch_doc.get("cross_batch_summary")
    require(isinstance(cross_batch_summary, dict), "cross_batch_summary must be an object")
    exact_keys(cross_batch_summary, {"method_layer", "voice_layer", "next_gate"}, set(), "cross_batch_summary")
    method_layer = cross_batch_summary.get("method_layer")
    require(isinstance(method_layer, dict), "cross_batch_summary method_layer must be an object")
    exact_keys(method_layer, {"candidate_rule_ids", "conditional_rule_ids", "hypothesis_rule_ids", "stable_rule_ids", "current_reading"}, set(), "method_layer")
    for state, field in (("candidate", "candidate_rule_ids"), ("conditional", "conditional_rule_ids"), ("hypothesis", "hypothesis_rule_ids"), ("stable", "stable_rule_ids")):
        summary_ids = string_list(method_layer.get(field), f"method_layer {field}")
        expected_ids = [rule_id for rule_id in rule_ids if rule_statuses[rule_id] == state]
        require(summary_ids == expected_ids, f"method_layer {field} does not match rule catalogue")
    non_empty_text(method_layer.get("current_reading"), "method_layer current_reading")
    voice_layer = cross_batch_summary.get("voice_layer")
    require(isinstance(voice_layer, dict), "cross_batch_summary voice_layer must be an object")
    exact_keys(voice_layer, {"rule_ids", "status", "current_reading"}, set(), "voice_layer")
    require(string_list(voice_layer.get("rule_ids"), "voice_layer rule_ids") == voice_rule_ids, "voice_layer rule_ids do not match catalogue")
    non_empty_text(voice_layer.get("status"), "voice_layer status")
    non_empty_text(voice_layer.get("current_reading"), "voice_layer current_reading")
    non_empty_text(cross_batch_summary.get("next_gate"), "cross_batch_summary next_gate")

    schema_root = root / "schemas"
    require(schema_root.is_dir(), "schemas directory is missing")
    schemas = sorted(schema_root.glob("*.json"))
    require(bool(schemas), "schemas directory must contain JSON schema documents")
    for schema_path in schemas:
        schema = load_json(schema_path, root)
        require(isinstance(schema, dict), f"{relative(schema_path, root)} must contain an object")
        require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{relative(schema_path, root)} must use JSON Schema 2020-12")
        non_empty_text(schema.get("$id"), f"{relative(schema_path, root)} $id")

    return {
        "samples": len(sample_ids),
        "observations": sum(len(value) for value in observations_by_sample.values()),
        "rules": len(rules),
        "stable_rules": len(actual_stable_ids),
        "voice_rules": len(voice_rules),
        "stable_voice_rules": len(actual_stable_voice_ids),
        "batches": len(batches),
        "artifact_receipts": artifact_count,
        "cards": card_count,
        "contamination_notes": contamination_count,
        "historical_text_wording_divergences": historical_text_wording_divergences,
        "content_truth_failures": content_truth_failures,
        "render_fidelity_failures": render_fidelity_failures,
        "reader_outcome_blocking_cards": reader_outcome_blocking_cards,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (defaults to this checkout)")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable result")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        counts = validate(args.root)
    except ValidationError as exc:
        if args.json:
            print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        else:
            print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"status": "pass", "counts": counts}, ensure_ascii=False, sort_keys=True))
    else:
        print("PASS: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
