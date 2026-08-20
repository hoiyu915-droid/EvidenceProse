# Version axes and migration rules

EvidenceProse uses several independent version axes. Numeric similarity does not
make two axes interchangeable, and a validator must not infer one version from
another unless an invariant below explicitly requires it.

## RCA axes

| Axis | Governs | Canonical authority | Required synchronization | Migration boundary |
|---|---|---|---|---|
| `contract_version` | The RCA audit envelope, mandatory procedure, required bindings, verdict and repair-ticket contract. | Active `EP_RENDERED_CARD_AUDIT` contract, mirrored by the active policy and `policies/rca/current.json`. | Active contract, policy, manifest, result-schema const and canonical fixture must agree. The versioned specification filename uses the same `major.minor`. | Any change requires a full contract migration, new versioned contract/specification surfaces and compatible validator changes. |
| `result_schema_version` | The shape and interpretation of an RCA result artifact. | `schemas/runtime/rendered_card_audit.schema.json`, mirrored by the active policy and manifest. | Policy, manifest, active contract, schema const and canonical fixture must agree. | A shape or result-semantics change requires a schema migration and updated fixtures/consumers. It does not imply a contract or policy version. |
| `policy_version` | The versioned set of RCA dispositions, topology statuses, mappings and policy decisions. | The policy JSON selected by `policies/rca/current.json`. | Selected policy, manifest, active contract, result-schema const and canonical fixture must agree; the manifest digest must identify the canonical policy bytes. | A policy-only patch within the current method family may use `--sync-surfaces`. A policy major/minor change also changes the method prefix and therefore requires a reviewed migration. |
| `method_revision` | The named audit-method family used to interpret and apply the policy. | Active policy, mirrored by the manifest and active RCA surfaces. | It must start with `<policy major>.<policy minor>-`; all active surfaces must carry the same complete string. | A change is not policy-only and requires a full migration review. |
| `manifest_version` | The shape and loader semantics of `policies/rca/current.json` itself. | `policies/rca/current.json` plus the manifest loader in `validate_rca_policy.py`. | It is independent of all policy and RCA artifact versions. The manifest key set and loader must agree. | A change requires a manifest-loader migration; `--sync-surfaces` must not perform it. |

`policy_sha256` / `policy_digest` are identities, not version axes. They bind the
selected canonical policy content and must change whenever those bytes change,
even when only the patch component of `policy_version` changes.

The active unversioned RCA document is a canonical alias and must remain
byte-identical to the active versioned document. Historical contract snapshots
and the documents they reference remain historical surfaces; policy-only sync
does not relocate or rewrite them.

## Artifact schema and delivery versions

Artifact schemas belong to their own lane. They do not inherit an RCA version
and must be read from the artifact's declared contract/schema field.

| Artifact or surface | Current version | Meaning |
|---|---:|---|
| TA06 prose runtime | `EP_TA06_PROSE_RUNTIME v1.1.1` | Binding and validation rules for a complete prose bundle. Patch 1.1.1 adds the reader-facing English-to-Chinese gloss gate without changing the sidecar shape. v1.0 is a superseded historical contract. |
| Prose audit sidecar | `contract_version: 1.1` | Current audit-sidecar shape, including auditable delivery-length decisions. `prose_audit_sidecar_v1.0.schema.json` preserves the former shape. |
| Probe post-audit bundle | `contract_version: 1.1` | File-bound post-audit transform, computed diff, immutable assets, coverage and isolated-reader record. v1.0 remains a legacy input schema. |
| Portable image-generation queue consumed by TE finalization | `schema_version: 1.3` | Upstream queue artifact shape accepted by `finalize_probe_te_queue.py`. |
| Probe TE delivery | `EP_PROBE_TE_DELIVERY v1.0` | Finalization, `TE_` namespace and delivery-order contract. It does not rename or replace the queue's own schema version. |
| Reader-facing delivery shell | `EP-SCIENCE-EXPLAINER-OUTPUT v0.2` | Markdown filename, section, citation surface and immediate English-to-Chinese gloss contract. |

Changing an artifact schema requires updating its schema/contract, validator,
fixtures and consumers together. It does not automatically bump RCA policy,
RCA result schema or the reader-facing delivery shell.

## Allowed update paths

### Policy-only patch

1. Keep `policy_id`, `contract_version`, `result_schema_version` and
   `method_revision` unchanged.
2. Change the selected policy content and its patch-level `policy_version`.
3. Update explicit mappings and regression cases.
4. Run `python3 scripts/validate_rca_policy.py --sync-surfaces`.
5. Run the focused RCA tests and the full repository suite.

The sync command updates policy selection/digest mirrors. It is not authorized
to migrate contracts, result schemas, methods, manifest shape or historical
surfaces.

### Full migration

A change to contract structure, result shape, policy major/minor family,
method revision or manifest structure is a full migration. Create or update the
appropriate versioned surfaces, migrate fixtures and consumers, add explicit
compatibility tests, and review the authority graph before changing the active
aliases or manifest.

## Executable invariants

`scripts/validate_rca_policy.py` enforces, among the other surface checks:

- the active versioned RCA document filename version equals
  `contract_version` major.minor;
- `method_revision` begins with `policy_version` major.minor;
- manifest and active surfaces mirror the selected policy and canonical digest;
- the active unversioned and versioned RCA documents are byte-identical.
