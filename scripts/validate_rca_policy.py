#!/usr/bin/env python3
"""Validate and expose the canonical RCA policy pack.

The versioned JSON under ``policies/rca`` is the runtime policy source.  This
module deliberately keeps the validator independent from the existing RCA
validators so that callers can import one deterministic policy object and its
canonical SHA-256 digest without importing a validator implementation.

The validator checks the policy's required shape and internal closure.  It
does not copy the current disposition/status identifiers into Python: adding
or revising a policy value therefore only requires changing the JSON policy
and its regression cases.  Runtime callers should read the JSON returned by
:func:`load_current_policy`.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
POLICY_DIR = REPO_ROOT / "policies" / "rca"
CURRENT_MANIFEST_PATH = POLICY_DIR / "current.json"

ACTIVE_CONTRACT_REL = Path("contracts/EP_RENDERED_CARD_AUDIT_CONTRACT_v1.2.json")
LEGACY_CONTRACT_RELS = (
    Path("contracts/EP_RENDERED_CARD_AUDIT_CONTRACT_v1.0.json"),
    Path("contracts/EP_RENDERED_CARD_AUDIT_CONTRACT_v1.1.json"),
)
ACTIVE_SCHEMA_REL = Path("schemas/runtime/rendered_card_audit.schema.json")
ACTIVE_FIXTURE_REL = Path("fixtures/valid_rendered_card_audit.json")
ACTIVE_DOC_REL = Path("docs/rendered_card_audit.md")
VERSIONED_DOC_REL = Path("docs/rendered_card_audit_v1.2.md")

VERSION_FIELDS = (
    "contract_version",
    "result_schema_version",
    "policy_version",
    "method_revision",
)

SURFACE_FIELDS = (
    "contract_version",
    "result_schema_version",
    "policy_id",
    "policy_version",
    "method_revision",
    "policy_digest",
)

# Required paths are shape requirements, not a second copy of policy values.
# Their values and mappings remain solely in policy_v1.3.0.json.
REQUIRED_POLICY_LIST_PATHS = (
    "source_surface.dispositions.pass",
    "source_surface.dispositions.warning",
    "source_surface.dispositions.fail",
    "source_surface.dispositions.block",
    "source_surface.dispositions.non_material",
    "source_surface.dispositions.deprecated",
    "source_surface.queue_authorization_statuses",
    "source_surface.primary_source_support_statuses",
    "source_surface.card_scope_statuses",
    "source_surface.expansion_keys",
    "source_surface.annotation.roles",
    "source_surface.annotation.statuses.pass",
    "source_surface.annotation.statuses.warning",
    "source_surface.annotation.statuses.fail",
    "source_surface.annotation.statuses.block",
    "topology.edge_statuses.pass",
    "topology.edge_statuses.warning",
    "topology.edge_statuses.fail",
    "topology.edge_statuses.block",
    "topology.relation_statuses.pass",
    "topology.relation_statuses.warning",
    "topology.relation_statuses.fail",
    "topology.relation_statuses.block",
    "topology.branch_statuses.pass",
    "topology.branch_statuses.warning",
    "topology.branch_statuses.fail",
    "topology.branch_statuses.block",
    "topology.terminal_statuses.pass",
    "topology.terminal_statuses.warning",
    "topology.terminal_statuses.fail",
    "topology.terminal_statuses.block",
    "topology.role_partition_statuses.pass",
    "topology.role_partition_statuses.warning",
    "topology.role_partition_statuses.fail",
    "topology.role_partition_statuses.block",
    "topology.text_visual_consistency_statuses.pass",
    "topology.text_visual_consistency_statuses.warning",
    "topology.text_visual_consistency_statuses.fail",
    "topology.text_visual_consistency_statuses.block",
)


class PolicyLoadError(RuntimeError):
    """Raised when the current manifest or policy cannot be loaded safely."""


class PolicySyncError(PolicyLoadError):
    """Raised when a policy-only surface synchronization is unsafe."""


def canonical_policy_json(policy: Mapping[str, Any]) -> str:
    """Return the deterministic, UTF-8-ready canonical JSON representation."""

    return json.dumps(
        policy,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def policy_digest(policy: Mapping[str, Any]) -> str:
    """Return the SHA-256 digest of :func:`canonical_policy_json`."""

    return hashlib.sha256(canonical_policy_json(policy).encode("utf-8")).hexdigest()


# Explicit alias for integrations that prefer a digest-oriented name.
canonical_policy_digest = policy_digest


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyLoadError(f"cannot read JSON {path}: {exc}") from exc


def _is_relative_safe(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts


def _major_minor(value: Any) -> str | None:
    """Return the numeric ``major.minor`` prefix of a version string."""

    if not isinstance(value, str):
        return None
    parts = value.split(".")
    if len(parts) < 2 or not all(part.isdigit() for part in parts[:2]):
        return None
    return ".".join(parts[:2])


def _path_get(value: Mapping[str, Any], dotted_path: str) -> Any:
    current: Any = value
    for part in dotted_path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _add(errors: list[str], message: str) -> None:
    errors.append(message)


def _check_string_list(
    policy: Mapping[str, Any],
    path: str,
    errors: list[str],
) -> None:
    value = _path_get(policy, path)
    if not isinstance(value, list):
        _add(errors, f"{path} must be an array")
        return
    if any(not isinstance(item, str) or not item.strip() for item in value):
        _add(errors, f"{path} must contain non-empty strings")
    if all(isinstance(item, str) for item in value) and len(value) != len(set(value)):
        _add(errors, f"{path} must not contain duplicate values")


def _check_mapping_keys(
    policy: Mapping[str, Any],
    path: str,
    expected: set[str],
    errors: list[str],
) -> Mapping[str, Any] | None:
    value = _path_get(policy, path)
    if not isinstance(value, Mapping):
        _add(errors, f"{path} must be an object")
        return None
    actual = set(value)
    if actual != expected:
        _add(errors, f"{path} keys drifted: expected {sorted(expected)}, got {sorted(actual)}")
    return value


def _check_required_sets(policy: Mapping[str, Any], errors: list[str]) -> None:
    allow_empty = {"source_surface.dispositions.warning"}
    for path in REQUIRED_POLICY_LIST_PATHS:
        _check_string_list(policy, path, errors)
        value = _path_get(policy, path)
        if path not in allow_empty and isinstance(value, list) and not value:
            _add(errors, f"{path} must not be empty")


def _check_disjoint_status_sets(
    groups: Mapping[str, Any] | None,
    path: str,
    errors: list[str],
) -> None:
    """Require each status token to belong to exactly one result category."""

    if groups is None:
        return
    seen: dict[str, str] = {}
    for status, values in groups.items():
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, str):
                continue
            previous = seen.get(value)
            if previous is not None:
                _add(errors, f"{path} value {value!r} appears in both {previous} and {status}")
            else:
                seen[value] = status


def _check_source_surface_mappings(policy: Mapping[str, Any], errors: list[str]) -> None:
    dispositions = _check_mapping_keys(
        policy,
        "source_surface.dispositions",
        {"pass", "warning", "fail", "block", "non_material", "deprecated"},
        errors,
    )
    _check_disjoint_status_sets(dispositions, "source_surface.dispositions", errors)
    mapping = _path_get(policy, "verdict_mapping.disposition_to_axis_status")
    if not isinstance(mapping, Mapping):
        _add(errors, "verdict_mapping.disposition_to_axis_status must be an object")
        return
    expected: dict[str, str] = {}
    if dispositions is not None:
        for status in ("pass", "warning", "fail", "block", "non_material", "deprecated"):
            values = dispositions.get(status, [])
            if isinstance(values, list):
                expected.update(
                    {
                        item: (
                            "warning"
                            if status == "non_material"
                            else "unverifiable"
                            if status == "block"
                            else status
                        )
                        for item in values
                        if isinstance(item, str)
                    }
                )
    if dict(mapping) != expected:
        _add(errors, "verdict_mapping.disposition_to_axis_status does not match source-surface disposition sets")


def _check_annotation_mappings(policy: Mapping[str, Any], errors: list[str]) -> None:
    statuses = _check_mapping_keys(
        policy,
        "source_surface.annotation.statuses",
        {"pass", "warning", "fail", "block"},
        errors,
    )
    _check_disjoint_status_sets(
        statuses, "source_surface.annotation.statuses", errors
    )
    mapping = _path_get(policy, "verdict_mapping.annotation_status_to_axis_status")
    if not isinstance(mapping, Mapping):
        _add(errors, "verdict_mapping.annotation_status_to_axis_status must be an object")
        return
    expected: dict[str, str] = {}
    if statuses is not None:
        for status, values in statuses.items():
            if isinstance(values, list):
                expected.update(
                    {
                        item: "unverifiable" if status == "block" else status
                        for item in values
                        if isinstance(item, str)
                    }
                )
    if dict(mapping) != expected:
        _add(errors, "verdict_mapping.annotation_status_to_axis_status does not match annotation status sets")


def _check_topology_mappings(policy: Mapping[str, Any], errors: list[str]) -> None:
    topology_groups = {
        "edge_statuses",
        "relation_statuses",
        "branch_statuses",
        "terminal_statuses",
        "role_partition_statuses",
        "text_visual_consistency_statuses",
    }
    mapping = _path_get(policy, "verdict_mapping.topology_status_to_axis_status")
    if not isinstance(mapping, Mapping):
        _add(errors, "verdict_mapping.topology_status_to_axis_status must be an object")
        return
    expected: dict[str, str] = {}
    for group in sorted(topology_groups):
        statuses = _check_mapping_keys(
            policy,
            f"topology.{group}",
            {"pass", "warning", "fail", "block"},
            errors,
        )
        if statuses is None:
            continue
        _check_disjoint_status_sets(statuses, f"topology.{group}", errors)
        for status, values in statuses.items():
            if isinstance(values, list):
                mapped_status = "unverifiable" if status == "block" else status
                for item in values:
                    if not isinstance(item, str):
                        continue
                    previous = expected.get(item)
                    if previous is not None and previous != mapped_status:
                        _add(
                            errors,
                            f"topology status {item!r} maps to both {previous} and {mapped_status}",
                        )
                    else:
                        expected[item] = mapped_status
    if dict(mapping) != expected:
        _add(errors, "verdict_mapping.topology_status_to_axis_status does not match topology status sets")


def _check_verdict_mapping(policy: Mapping[str, Any], errors: list[str]) -> None:
    axis = _check_mapping_keys(
        policy,
        "verdict_mapping.axis_status_to_verdict",
        {"pass", "warning", "fail", "unverifiable"},
        errors,
    )
    if axis is not None:
        for status, verdict in axis.items():
            if not isinstance(verdict, str) or not verdict.strip():
                _add(errors, f"verdict_mapping.axis_status_to_verdict.{status} must be a non-empty string")
        axis_values = list(axis.values())
        if all(isinstance(value, str) and value.strip() for value in axis_values):
            axis_verdicts = set(axis_values)
        else:
            axis_verdicts = set()
            _add(errors, "verdict_mapping.axis_status_to_verdict values must be non-empty strings")
    else:
        axis_verdicts = set()
    failures = _path_get(policy, "verdict_mapping.material_failure_verdicts")
    failure_verdicts: set[str] = set()
    if not isinstance(failures, list) or not failures:
        _add(errors, "verdict_mapping.material_failure_verdicts must be a non-empty array")
    elif any(not isinstance(value, str) or not value.strip() for value in failures):
        _add(errors, "verdict_mapping.material_failure_verdicts must contain non-empty strings")
    elif len(failures) != len(set(failures)):
        _add(errors, "verdict_mapping.material_failure_verdicts must not contain duplicates")
    else:
        failure_verdicts = set(failures)
    verdicts = _path_get(policy, "verdict_mapping.verdicts")
    if not isinstance(verdicts, Mapping) or not verdicts:
        _add(errors, "verdict_mapping.verdicts must be a non-empty object")
    else:
        if any(not isinstance(key, str) or not key.strip() for key in verdicts):
            _add(errors, "verdict_mapping.verdicts keys must be non-empty strings")
        if any(not isinstance(value, str) or not value.strip() for value in verdicts.values()):
            _add(errors, "verdict_mapping.verdicts values must be non-empty strings")
        if axis is not None:
            missing = axis_verdicts - set(verdicts)
            if missing:
                _add(errors, f"verdict_mapping.verdicts is missing axis verdicts: {sorted(missing)}")
        if failure_verdicts:
            missing = failure_verdicts - set(verdicts)
            if missing:
                _add(errors, f"verdict_mapping.verdicts is missing material failure verdicts: {sorted(missing)}")


def validate_policy(policy: Any, manifest: Mapping[str, Any] | None = None) -> list[str]:
    """Return structural and synchronization errors for one policy object."""

    errors: list[str] = []
    if not isinstance(policy, Mapping):
        return ["policy must be an object"]
    for field in ("policy_id", *VERSION_FIELDS):
        value = policy.get(field)
        if not isinstance(value, str) or not value.strip():
            _add(errors, f"{field} must be a non-empty string")
    version_values = [policy.get(field) for field in VERSION_FIELDS[:3]]
    if all(isinstance(value, str) and value.strip() for value in version_values):
        if len(set(version_values)) != len(version_values):
            _add(errors, "contract_version, result_schema_version and policy_version must remain separate")
    policy_major_minor = _major_minor(policy.get("policy_version"))
    method_revision = policy.get("method_revision")
    if policy_major_minor is None:
        _add(errors, "policy_version must begin with numeric major.minor components")
    elif isinstance(method_revision, str) and method_revision.strip():
        expected_prefix = f"{policy_major_minor}-"
        if not method_revision.startswith(expected_prefix):
            _add(
                errors,
                "method_revision must begin with policy_version major.minor "
                f"prefix {expected_prefix!r}",
            )
    if policy.get("status") != "canonical":
        _add(errors, "status must be canonical")

    _check_required_sets(policy, errors)
    _check_mapping_keys(
        policy,
        "source_surface",
        {
            "dispositions",
            "queue_authorization_statuses",
            "primary_source_support_statuses",
            "card_scope_statuses",
            "expansion_keys",
            "annotation",
        },
        errors,
    )
    _check_mapping_keys(
        policy,
        "source_surface.annotation",
        {"roles", "statuses"},
        errors,
    )
    _check_mapping_keys(
        policy,
        "topology",
        {
            "edge_statuses",
            "relation_statuses",
            "branch_statuses",
            "terminal_statuses",
            "role_partition_statuses",
            "text_visual_consistency_statuses",
        },
        errors,
    )
    _check_mapping_keys(
        policy,
        "verdict_mapping",
        {
            "disposition_to_axis_status",
            "annotation_status_to_axis_status",
            "topology_status_to_axis_status",
            "axis_status_to_verdict",
            "material_failure_verdicts",
            "verdicts",
        },
        errors,
    )
    _check_source_surface_mappings(policy, errors)
    _check_annotation_mappings(policy, errors)
    _check_topology_mappings(policy, errors)
    _check_verdict_mapping(policy, errors)

    if manifest is not None:
        _validate_manifest_shape(manifest, policy, errors)
    return errors


def _validate_manifest_shape(
    manifest: Any,
    policy: Mapping[str, Any],
    errors: list[str],
) -> None:
    if not isinstance(manifest, Mapping):
        _add(errors, "current policy manifest must be an object")
        return
    expected_keys = {
        "manifest_version",
        "policy_id",
        "policy_path",
        "policy_sha256",
        "contract_version",
        "result_schema_version",
        "policy_version",
        "method_revision",
    }
    if set(manifest) != expected_keys:
        _add(errors, f"current policy manifest keys drifted: expected {sorted(expected_keys)}, got {sorted(manifest)}")
    if manifest.get("manifest_version") != "1.0.0":
        _add(errors, "manifest_version must be 1.0.0")
    if manifest.get("policy_id") != policy.get("policy_id"):
        _add(errors, "current policy manifest policy_id does not match policy")
    if not _is_relative_safe(manifest.get("policy_path")):
        _add(errors, "current policy manifest policy_path must be a safe relative path")
    digest = manifest.get("policy_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        _add(errors, "current policy manifest policy_sha256 must be lowercase SHA-256")
    for field in VERSION_FIELDS:
        if manifest.get(field) != policy.get(field):
            _add(errors, f"current policy manifest {field} does not match canonical policy")
    forbidden_content = {"source_surface", "topology", "verdict_mapping"}.intersection(manifest)
    if forbidden_content:
        _add(errors, "current policy manifest must point to policy content, not copy it")


def _manifest_path(base_dir: Path) -> Path:
    return base_dir / "policies" / "rca" / "current.json"


def _resolve_policy_path(manifest_path: Path, policy_path_value: Any) -> Path:
    """Resolve a manifest policy path and keep it inside ``policies/rca``."""

    policy_root = manifest_path.parent.resolve()
    candidate = manifest_path.parent / str(policy_path_value)
    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError) as exc:
        raise PolicyLoadError(f"cannot resolve current policy path {candidate}: {exc}") from exc
    try:
        resolved.relative_to(policy_root)
    except ValueError as exc:
        raise PolicyLoadError(
            f"current policy path {candidate} resolves outside policies/rca"
        ) from exc
    return resolved


def _load_current_bundle_unchecked(base_dir: Path | str | None = None) -> dict[str, Any]:
    """Load the current bundle without validating its policy or manifest."""

    base = Path(base_dir) if base_dir is not None else REPO_ROOT
    manifest_path = _manifest_path(base)
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, Mapping) or not _is_relative_safe(manifest.get("policy_path")):
        raise PolicyLoadError("current policy manifest has an unsafe policy_path")
    policy_path = _resolve_policy_path(manifest_path, manifest["policy_path"])
    policy = _read_json(policy_path)
    if not isinstance(policy, Mapping):
        raise PolicyLoadError(f"policy file {policy_path} must contain an object")
    canonical = canonical_policy_json(policy)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "policy": dict(policy),
        "manifest": dict(manifest) if isinstance(manifest, Mapping) else manifest,
        "policy_path": policy_path,
        "canonical_policy_json": canonical,
        "policy_sha256": digest,
    }


def _bundle_validation_errors(bundle: Mapping[str, Any]) -> list[str]:
    """Return policy, manifest-shape, and canonical-digest errors for a bundle."""

    errors = validate_policy(bundle["policy"], bundle["manifest"])
    manifest_digest = bundle["manifest"].get("policy_sha256")
    if manifest_digest != bundle["policy_sha256"]:
        _add(errors, "current policy manifest policy_sha256 does not match canonical policy digest")
    return errors


def load_current_bundle(base_dir: Path | str | None = None) -> dict[str, Any]:
    """Load and validate the current bundle for runtime integrations."""

    bundle = _load_current_bundle_unchecked(base_dir)
    errors = _bundle_validation_errors(bundle)
    if errors:
        raise PolicyLoadError("; ".join(errors))
    return bundle


def load_current_policy(base_dir: Path | str | None = None) -> dict[str, Any]:
    """Return the canonical current policy object for runtime use."""

    return load_current_bundle(base_dir)["policy"]


def get_current_policy(base_dir: Path | str | None = None) -> tuple[dict[str, Any], str]:
    """Return ``(policy, digest)`` for a concise runtime integration path."""

    bundle = load_current_bundle(base_dir)
    return bundle["policy"], bundle["policy_sha256"]


def validate_current_policy(base_dir: Path | str | None = None) -> list[str]:
    """Validate policy, manifest pointer, versions, digest and required sets."""

    base = Path(base_dir) if base_dir is not None else REPO_ROOT
    try:
        bundle = _load_current_bundle_unchecked(base)
    except PolicyLoadError as exc:
        return [str(exc)]
    return _bundle_validation_errors(bundle)


def _surface_expected_fields(
    policy: Mapping[str, Any], digest: str
) -> dict[str, str]:
    return {
        "contract_version": str(policy.get("contract_version", "")),
        "result_schema_version": str(policy.get("result_schema_version", "")),
        "policy_id": str(policy.get("policy_id", "")),
        "policy_version": str(policy.get("policy_version", "")),
        "method_revision": str(policy.get("method_revision", "")),
        "policy_digest": digest,
    }


def _compare_surface_fields(
    document: Any,
    label: str,
    expected: Mapping[str, str],
    errors: list[str],
) -> None:
    if not isinstance(document, Mapping):
        _add(errors, f"{label} must be an object")
        return
    for field in SURFACE_FIELDS:
        if document.get(field) != expected[field]:
            _add(
                errors,
                f"{label}.{field} must be {expected[field]!r}, got {document.get(field)!r}",
            )


def _load_surface_json(base: Path, relative: Path, label: str, errors: list[str]) -> Any:
    path = base / relative
    try:
        return _read_json(path)
    except PolicyLoadError as exc:
        _add(errors, f"{label}: {exc}")
        return None


def _require_path_values(
    document: Any,
    path: str,
    expected: set[str],
    label: str,
    errors: list[str],
) -> Any:
    value = _path_get(document, path) if isinstance(document, Mapping) else None
    if not isinstance(value, list):
        _add(errors, f"{label}.{path} must be an array")
        return value
    missing = sorted(expected - set(value))
    if missing:
        _add(errors, f"{label}.{path} is missing required fields: {missing}")
    return value


def _check_active_schema(schema: Any, expected: Mapping[str, str], errors: list[str]) -> None:
    label = "active schema"
    if not isinstance(schema, Mapping):
        _add(errors, f"{label} must be an object")
        return
    required = set(schema.get("required", []))
    missing = sorted(set(SURFACE_FIELDS) - required)
    if missing:
        _add(errors, f"{label}.required is missing policy/version fields: {missing}")
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        _add(errors, f"{label}.properties must be an object")
        return
    for field in SURFACE_FIELDS:
        prop = properties.get(field)
        if not isinstance(prop, Mapping):
            _add(errors, f"{label}.properties.{field} must be defined")
            continue
        if field == "policy_digest":
            if prop.get("$ref") != "#/$defs/sha256":
                _add(errors, f"{label}.properties.policy_digest must use sha256 definition")
        elif prop.get("const") != expected[field]:
            _add(
                errors,
                f"{label}.properties.{field} must const {expected[field]!r}, got {prop.get('const')!r}",
            )

    defs = schema.get("$defs")
    if not isinstance(defs, Mapping):
        _add(errors, f"{label}.$defs must be an object")
        return
    source_binding = defs.get("sourceBinding")
    if not isinstance(source_binding, Mapping):
        _add(errors, f"{label}.$defs.sourceBinding must be defined")
    else:
        _require_path_values(
            source_binding,
            "required",
            {
                "source_id",
                "type",
                "status",
                "identity",
                "artifact_path",
                "source_digest",
                "binding_digest",
            },
            f"{label}.$defs.sourceBinding",
            errors,
        )
    card = defs.get("cardAudit")
    if not isinstance(card, Mapping):
        _add(errors, f"{label}.$defs.cardAudit must be defined")
        return
    _require_path_values(
        card,
        "required",
        {"expected_semantic_packet", "expected_semantic_packet_digest"},
        f"{label}.$defs.cardAudit",
        errors,
    )
    card_properties = card.get("properties")
    blind = card_properties.get("blind_readback") if isinstance(card_properties, Mapping) else None
    if not isinstance(blind, Mapping):
        _add(errors, f"{label}.$defs.cardAudit.properties.blind_readback must be defined")
    else:
        _require_path_values(
            blind,
            "required",
            {"evidence_annotation_inventory"},
            f"{label}.$defs.blind_readback",
            errors,
        )
    if not isinstance(defs.get("semanticPacket"), Mapping):
        _add(errors, f"{label}.$defs.semanticPacket must be defined")
    else:
        semantic_packet = defs["semanticPacket"]
        _require_path_values(
            semantic_packet,
            "required",
            {
                "source_binding_ids",
                "source_binding_digests",
                "central_claims",
                "causal_ceiling",
                "limitations",
                "expected_graph",
                "expected_graph_digest",
                "expected_content_inventory",
                "expected_evidence_annotation_inventory",
            },
            f"{label}.$defs.semanticPacket",
            errors,
        )
        packet_properties = semantic_packet.get("properties")
        if not isinstance(packet_properties, Mapping):
            _add(errors, f"{label}.$defs.semanticPacket.properties must be an object")
        else:
            expected_graph_property = packet_properties.get("expected_graph")
            if not isinstance(expected_graph_property, Mapping) or expected_graph_property.get("$ref") != "#/$defs/expectedGraph":
                _add(errors, f"{label}.$defs.semanticPacket.properties.expected_graph must use expectedGraph definition")
            source_digests = packet_properties.get("source_binding_digests")
            additional = source_digests.get("additionalProperties") if isinstance(source_digests, Mapping) else None
            if not isinstance(additional, Mapping) or additional.get("$ref") != "#/$defs/sha256":
                _add(errors, f"{label}.$defs.semanticPacket.properties.source_binding_digests values must use sha256 definition")
            expected_annotations = packet_properties.get("expected_evidence_annotation_inventory")
            annotation_items = expected_annotations.get("items") if isinstance(expected_annotations, Mapping) else None
            if not isinstance(annotation_items, Mapping) or annotation_items.get("$ref") != "#/$defs/expectedEvidenceAnnotationInventoryItem":
                _add(errors, f"{label}.$defs.semanticPacket.properties.expected_evidence_annotation_inventory must use expected annotation definition")

    expected_graph = defs.get("expectedGraph")
    if not isinstance(expected_graph, Mapping):
        _add(errors, f"{label}.$defs.expectedGraph must be defined")
    else:
        _require_path_values(
            expected_graph,
            "required",
            {"nodes", "relations", "branch_points", "terminal_states", "role_partitions"},
            f"{label}.$defs.expectedGraph",
            errors,
        )

    expected_annotation = defs.get("expectedEvidenceAnnotationInventoryItem")
    if not isinstance(expected_annotation, Mapping):
        _add(errors, f"{label}.$defs.expectedEvidenceAnnotationInventoryItem must be defined")
    else:
        _require_path_values(
            expected_annotation,
            "required",
            {"expected_annotation_id", "expected_role"},
            f"{label}.$defs.expectedEvidenceAnnotationInventoryItem",
            errors,
        )


def _find_contract_stage(
    contract: Mapping[str, Any], stage_name: str, errors: list[str]
) -> Mapping[str, Any] | None:
    stages = contract.get("mandatory_audit_sop")
    if not isinstance(stages, list):
        _add(errors, "active contract.mandatory_audit_sop must be an array")
        return None
    matches = [
        stage
        for stage in stages
        if isinstance(stage, Mapping) and stage.get("stage") == stage_name
    ]
    if len(matches) != 1:
        _add(
            errors,
            f"active contract.mandatory_audit_sop must contain exactly one {stage_name} stage",
        )
        return None
    return matches[0]


def _compare_string_membership(
    actual: Any,
    expected: list[str],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(actual, list) or any(not isinstance(value, str) for value in actual):
        _add(errors, f"{label} must be an array of strings")
        return
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        _add(errors, f"{label} must have exact membership parity with active policy")


def _check_active_contract_policy_parity(
    contract: Mapping[str, Any], policy: Mapping[str, Any], errors: list[str]
) -> None:
    rca05 = _find_contract_stage(contract, "RCA-05", errors)
    if rca05 is not None:
        expected_dispositions: list[str] = []
        for group in ("pass", "warning", "fail", "block", "non_material"):
            values = _path_get(policy, f"source_surface.dispositions.{group}")
            if isinstance(values, list):
                expected_dispositions.extend(
                    value for value in values if isinstance(value, str)
                )
        _compare_string_membership(
            rca05.get("allowed_node_dispositions"),
            expected_dispositions,
            "active contract.RCA-05.allowed_node_dispositions",
            errors,
        )

    policy_verdicts = _path_get(policy, "verdict_mapping.verdicts")
    contract_verdicts = contract.get("verdicts")
    if not isinstance(policy_verdicts, Mapping):
        _add(errors, "active policy verdict_mapping.verdicts must be an object")
    elif not isinstance(contract_verdicts, Mapping):
        _add(errors, "active contract.verdicts must be an object")
    elif set(contract_verdicts) != set(policy_verdicts):
        _add(errors, "active contract.verdicts must have exact key parity with active policy")

    policy_failures = _path_get(policy, "verdict_mapping.material_failure_verdicts")
    human_display = contract.get("human_repair_display")
    include_only = human_display.get("include_only") if isinstance(human_display, Mapping) else None
    if not isinstance(policy_failures, list):
        _add(errors, "active policy material_failure_verdicts must be an array")
    else:
        _compare_string_membership(
            include_only,
            [value for value in policy_failures if isinstance(value, str)],
            "active contract.human_repair_display.include_only",
            errors,
        )


def validate_current_surfaces(base_dir: Path | str | None = None) -> list[str]:
    """Validate active contract/schema/fixture/document synchronization.

    This is intentionally separate from the runtime policy loader: callers that
    only need the policy object do not depend on documentation or fixture files,
    while the CLI/CI gate can fail closed on surface drift.
    """

    base = Path(base_dir) if base_dir is not None else REPO_ROOT
    errors: list[str] = []
    try:
        bundle = load_current_bundle(base)
    except PolicyLoadError as exc:
        return [str(exc)]
    policy = bundle["policy"]
    digest = bundle["policy_sha256"]
    expected = _surface_expected_fields(policy, digest)

    contract_major_minor = _major_minor(policy.get("contract_version"))
    if contract_major_minor is None:
        _add(errors, "contract_version must begin with numeric major.minor components")
    else:
        expected_doc_name = f"rendered_card_audit_v{contract_major_minor}.md"
        if VERSIONED_DOC_REL.name != expected_doc_name:
            _add(
                errors,
                "versioned RCA document filename must match contract_version "
                f"major.minor: expected {expected_doc_name!r}, got {VERSIONED_DOC_REL.name!r}",
            )

    contract = _load_surface_json(base, ACTIVE_CONTRACT_REL, "active contract", errors)
    _compare_surface_fields(contract, "active contract", expected, errors)
    if isinstance(contract, Mapping):
        if contract.get("contract_name") != expected["policy_id"]:
            _add(errors, "active contract.contract_name must match policy_id")
        if contract.get("status") != "canonical":
            _add(errors, "active contract.status must be canonical")
        documents = contract.get("canonical_documents")
        active_policy_rel = str(
            Path("policies/rca") / str(bundle["manifest"].get("policy_path", ""))
        )
        expected_documents = {
            "specification": str(VERSIONED_DOC_REL),
            "canonical_alias": str(ACTIVE_DOC_REL),
            "policy": active_policy_rel,
            "policy_manifest": "policies/rca/current.json",
            "result_schema": str(ACTIVE_SCHEMA_REL),
        }
        if not isinstance(documents, Mapping):
            _add(errors, "active contract.canonical_documents must be an object")
        else:
            for key, value in expected_documents.items():
                if documents.get(key) != value:
                    _add(errors, f"active contract.canonical_documents.{key} must be {value!r}")
        _check_active_contract_policy_parity(contract, policy, errors)

    for relative in LEGACY_CONTRACT_RELS:
        legacy = _load_surface_json(base, relative, f"legacy contract {relative.name}", errors)
        if isinstance(legacy, Mapping):
            label = f"legacy contract {relative.name}"
            if legacy.get("status") != "superseded":
                _add(errors, f"{label}.status must be superseded")
            if legacy.get("superseded_by") != ACTIVE_CONTRACT_REL.name:
                _add(errors, f"{label}.superseded_by must be {ACTIVE_CONTRACT_REL.name!r}")

    schema = _load_surface_json(base, ACTIVE_SCHEMA_REL, "active schema", errors)
    _check_active_schema(schema, expected, errors)

    fixture = _load_surface_json(base, ACTIVE_FIXTURE_REL, "active fixture", errors)
    _compare_surface_fields(fixture, "active fixture", expected, errors)
    if isinstance(fixture, Mapping):
        bindings = fixture.get("source_bindings")
        if not isinstance(bindings, list) or not bindings:
            _add(errors, "active fixture.source_bindings must be non-empty")
        else:
            for index, binding in enumerate(bindings):
                if not isinstance(binding, Mapping):
                    _add(errors, f"active fixture.source_bindings[{index}] must be an object")
                    continue
                for field in ("artifact_path", "source_digest", "binding_digest"):
                    if not binding.get(field):
                        _add(errors, f"active fixture.source_bindings[{index}].{field} is required")
        cards = fixture.get("card_audits")
        if not isinstance(cards, list) or not cards:
            _add(errors, "active fixture.card_audits must be non-empty")
        else:
            for index, card in enumerate(cards):
                if not isinstance(card, Mapping):
                    _add(errors, f"active fixture.card_audits[{index}] must be an object")
                    continue
                for field in ("expected_semantic_packet", "expected_semantic_packet_digest"):
                    if field not in card:
                        _add(errors, f"active fixture.card_audits[{index}].{field} is required")
                blind = card.get("blind_readback")
                if not isinstance(blind, Mapping) or "evidence_annotation_inventory" not in blind:
                    _add(errors, f"active fixture.card_audits[{index}].blind_readback.evidence_annotation_inventory is required")

    active_doc = base / ACTIVE_DOC_REL
    versioned_doc = base / VERSIONED_DOC_REL
    try:
        if active_doc.read_bytes() != versioned_doc.read_bytes():
            _add(errors, "active rendered-card specification must be byte-identical to v1.2 document")
    except OSError as exc:
        _add(errors, f"rendered-card specification alias check failed: {exc}")
    return errors


POLICY_ONLY_INVARIANT_FIELDS = (
    "policy_id",
    "contract_version",
    "result_schema_version",
    "method_revision",
)


def _policy_only_source_errors(bundle: Mapping[str, Any]) -> list[str]:
    """Validate a candidate policy while allowing only policy-version drift."""

    policy = bundle.get("policy")
    manifest = bundle.get("manifest")
    errors = validate_policy(policy)
    if not isinstance(manifest, Mapping):
        _add(errors, "current policy manifest must be an object")
        return errors
    expected_keys = {
        "manifest_version",
        "policy_id",
        "policy_path",
        "policy_sha256",
        "contract_version",
        "result_schema_version",
        "policy_version",
        "method_revision",
    }
    if set(manifest) != expected_keys:
        _add(
            errors,
            f"current policy manifest keys drifted: expected {sorted(expected_keys)}, got {sorted(manifest)}",
        )
    if manifest.get("manifest_version") != "1.0.0":
        _add(errors, "manifest_version must be 1.0.0")
    if not _is_relative_safe(manifest.get("policy_path")):
        _add(errors, "current policy manifest policy_path must be a safe relative path")
    if not isinstance(policy, Mapping):
        return errors
    for field in POLICY_ONLY_INVARIANT_FIELDS:
        if manifest.get(field) != policy.get(field):
            _add(
                errors,
                f"policy-only sync refuses {field} change; full migration is required",
            )
    return errors


def _read_sync_object(base: Path, relative: Path, label: str) -> dict[str, Any]:
    try:
        value = _read_json(base / relative)
    except PolicyLoadError as exc:
        raise PolicySyncError(f"{label}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise PolicySyncError(f"{label} must be an object")
    return copy.deepcopy(dict(value))


def _build_sync_documents(
    base: Path, bundle: Mapping[str, Any]
) -> tuple[dict[Path, dict[str, Any]], str]:
    policy = bundle["policy"]
    manifest = copy.deepcopy(dict(bundle["manifest"]))
    digest = policy_digest(policy)
    manifest["policy_sha256"] = digest
    manifest["policy_version"] = policy["policy_version"]

    contract = _read_sync_object(base, ACTIVE_CONTRACT_REL, "active contract")
    fixture = _read_sync_object(base, ACTIVE_FIXTURE_REL, "active fixture")
    schema = _read_sync_object(base, ACTIVE_SCHEMA_REL, "active schema")

    contract["policy_version"] = policy["policy_version"]
    contract["policy_digest"] = digest
    canonical_documents = contract.get("canonical_documents")
    if not isinstance(canonical_documents, Mapping):
        raise PolicySyncError("active contract.canonical_documents must be an object")
    canonical_documents = copy.deepcopy(dict(canonical_documents))
    canonical_documents["policy"] = str(
        Path("policies/rca") / str(manifest["policy_path"])
    )
    contract["canonical_documents"] = canonical_documents

    rca05 = _find_contract_stage(contract, "RCA-05", [])
    if rca05 is None:
        raise PolicySyncError("active contract must contain exactly one RCA-05 stage")
    allowed_dispositions: list[str] = []
    for group in ("pass", "warning", "fail", "block", "non_material"):
        values = _path_get(policy, f"source_surface.dispositions.{group}")
        if isinstance(values, list):
            allowed_dispositions.extend(value for value in values if isinstance(value, str))
    rca05["allowed_node_dispositions"] = allowed_dispositions
    policy_verdicts = _path_get(policy, "verdict_mapping.verdicts")
    if isinstance(policy_verdicts, Mapping):
        contract["verdicts"] = copy.deepcopy(dict(policy_verdicts))
    policy_failures = _path_get(policy, "verdict_mapping.material_failure_verdicts")
    if isinstance(policy_failures, list):
        human_display = contract.get("human_repair_display")
        if not isinstance(human_display, Mapping):
            raise PolicySyncError("active contract.human_repair_display must be an object")
        human_display = copy.deepcopy(dict(human_display))
        human_display["include_only"] = [
            value for value in policy_failures if isinstance(value, str)
        ]
        contract["human_repair_display"] = human_display

    fixture["policy_version"] = policy["policy_version"]
    fixture["policy_digest"] = digest
    schema_properties = schema.get("properties")
    if not isinstance(schema_properties, Mapping):
        raise PolicySyncError("active schema.properties must be an object")
    policy_version_property = schema_properties.get("policy_version")
    if not isinstance(policy_version_property, Mapping):
        raise PolicySyncError("active schema.properties.policy_version must be an object")
    schema_properties = copy.deepcopy(dict(schema_properties))
    policy_version_property = copy.deepcopy(dict(policy_version_property))
    policy_version_property["const"] = policy["policy_version"]
    schema_properties["policy_version"] = policy_version_property
    schema["properties"] = schema_properties

    return (
        {
            Path("policies/rca/current.json"): manifest,
            ACTIVE_CONTRACT_REL: contract,
            ACTIVE_FIXTURE_REL: fixture,
            ACTIVE_SCHEMA_REL: schema,
        },
        digest,
    )


def _json_bytes(document: Mapping[str, Any]) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    temporary_fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    open_fd: int | None = temporary_fd
    try:
        with os.fdopen(temporary_fd, "wb") as handle:
            open_fd = None
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if open_fd is not None:
            os.close(open_fd)
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def _atomic_write_json(path: Path, document: Mapping[str, Any]) -> None:
    _atomic_write_bytes(path, _json_bytes(document))


def _sync_tree_relatives(manifest: Mapping[str, Any]) -> set[Path]:
    relatives = {
        Path("policies/rca/current.json"),
        ACTIVE_CONTRACT_REL,
        *LEGACY_CONTRACT_RELS,
        ACTIVE_SCHEMA_REL,
        ACTIVE_FIXTURE_REL,
        ACTIVE_DOC_REL,
        VERSIONED_DOC_REL,
    }
    relatives.add(Path("policies/rca") / str(manifest["policy_path"]))
    return relatives


def _preflight_sync(
    base: Path,
    documents: Mapping[Path, Mapping[str, Any]],
    manifest: Mapping[str, Any],
) -> None:
    try:
        with tempfile.TemporaryDirectory(prefix="evidenceprose-rca-sync-") as temporary:
            staging = Path(temporary)
            for relative in _sync_tree_relatives(manifest):
                source = base / relative
                target = staging / relative
                if not source.is_file():
                    raise PolicySyncError(f"cannot stage required surface {relative}")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            for relative, document in documents.items():
                _atomic_write_json(staging / relative, document)
            policy_errors = validate_current_policy(staging)
            surface_errors = validate_current_surfaces(staging)
            errors = policy_errors + surface_errors
            if errors:
                raise PolicySyncError("sync preflight failed: " + "; ".join(errors))
    except PolicySyncError:
        raise
    except OSError as exc:
        raise PolicySyncError(f"sync preflight could not stage surfaces: {exc}") from exc


def sync_surfaces(base_dir: Path | str | None = None) -> dict[str, Any]:
    """Synchronize policy-only digest/version mirrors atomically.

    The current manifest selects the active versioned policy.  This command
    permits only policy-version/content changes; identity, result-schema,
    contract and method changes require a separately reviewed migration.
    """

    base = Path(base_dir) if base_dir is not None else REPO_ROOT
    bundle = _load_current_bundle_unchecked(base)
    source_errors = _policy_only_source_errors(bundle)
    if source_errors:
        raise PolicySyncError("; ".join(source_errors))
    documents, digest = _build_sync_documents(base, bundle)
    _preflight_sync(base, documents, documents[Path("policies/rca/current.json")])

    originals = {
        relative: (base / relative).read_bytes() for relative in documents
    }
    try:
        for relative, document in documents.items():
            _atomic_write_json(base / relative, document)
        policy_errors = validate_current_policy(base)
        surface_errors = validate_current_surfaces(base)
        errors = policy_errors + surface_errors
        if errors:
            raise PolicySyncError("sync postflight failed: " + "; ".join(errors))
    except Exception as exc:
        for relative, content in originals.items():
            _atomic_write_bytes(base / relative, content)
        if isinstance(exc, PolicySyncError):
            raise
        raise PolicySyncError(f"sync write failed: {exc}") from exc

    policy = bundle["policy"]
    return {
        "status": "pass",
        "policy_id": policy["policy_id"],
        "policy_version": policy["policy_version"],
        "policy_sha256": digest,
        "updated_files": [str(relative) for relative in documents],
    }


def _version_summary(policy: Mapping[str, Any]) -> dict[str, str | None]:
    return {field: policy.get(field) for field in VERSION_FIELDS}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation result")
    parser.add_argument(
        "--emit",
        choices=("canonical-json", "digest", "bundle"),
        help="emit canonical policy material for runtime integration",
    )
    parser.add_argument(
        "--sync-surfaces",
        action="store_true",
        help="synchronize policy-only digest/version mirrors atomically",
    )
    parser.add_argument("--base-dir", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.sync_surfaces and args.emit:
        parser.error("--sync-surfaces cannot be combined with --emit")

    if args.sync_surfaces:
        try:
            result = sync_surfaces(args.base_dir)
        except (PolicyLoadError, PolicySyncError) as exc:
            payload = {"status": "fail", "errors": [str(exc)]}
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            else:
                print(str(exc))
            return 1
        if args.json:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            print("SYNCED " + ", ".join(result["updated_files"]))
        return 0

    try:
        bundle = load_current_bundle(args.base_dir)
        errors = validate_policy(bundle["policy"], bundle["manifest"])
        if bundle["manifest"].get("policy_sha256") != bundle["policy_sha256"]:
            _add(errors, "current policy manifest policy_sha256 does not match canonical policy digest")
        errors.extend(validate_current_surfaces(args.base_dir))
    except PolicyLoadError as exc:
        bundle = None
        errors = [str(exc)]

    status = "pass" if not errors else "fail"
    if args.emit == "canonical-json" and bundle is not None:
        print(bundle["canonical_policy_json"])
    elif args.emit == "digest" and bundle is not None:
        print(bundle["policy_sha256"])
    elif args.emit == "bundle" and bundle is not None:
        print(
            json.dumps(
                {
                    "status": status,
                    "policy": bundle["policy"],
                    "canonical_policy_json": bundle["canonical_policy_json"],
                    "policy_sha256": bundle["policy_sha256"],
                    "errors": errors,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    elif args.json:
        payload: dict[str, Any] = {"status": status, "errors": errors}
        if bundle is not None:
            payload.update(
                {
                    "policy_id": bundle["policy"].get("policy_id"),
                    "versions": _version_summary(bundle["policy"]),
                    "policy_sha256": bundle["policy_sha256"],
                    "canonical_policy_json": bundle["canonical_policy_json"],
                }
            )
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print("PASS" if not errors else "\n".join(errors))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
