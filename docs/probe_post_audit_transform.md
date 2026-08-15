# Probe post-audit transform

Contract: `EP_PROBE_POST_AUDIT_TRANSFORM v1.1`

Probe is the post-audit synthesis and repair layer. It receives producer card JSON, the Claude semantic audit, and the audited prose draft; it may merge or repair cards and strengthen the prose, but it does not become a second TA06 source-audit system.

## Position in the lane

```text
TA/TP producer
  -> initial card JSON
Claude
  -> semantic audit + science-explainer draft
Probe
  -> compare / diagnose / constrained transform
  -> merged or repaired card JSON
  -> strengthened science explainer
  -> file-bound transform record
isolated reader
  -> final-package EvidenceQuiz
validator
  -> computed diff + immutable-asset + reconstruction gate
```

The boundary is not whether Probe may rewrite. It may. The boundary is that rhetorical freedom must not create epistemic authority.

## What Probe may change

Probe may keep, patch, merge, recompose, and—only when narrower repair cannot restore coherence—regenerate a card. For prose it may reorder, compress, simplify, expand an already-supported explanation, add a supported bridge, strengthen rhetoric, or retitle.

Probe may not create a new empirical claim, evidence-bearing number, causal mechanism, broader population, recommendation, threshold, or stronger certainty merely because the result reads better.

The preferred transform order remains:

```text
KEEP -> PATCH -> MERGE -> RECOMPOSE -> REGENERATE
```

## Audit-driven repair

Every substantive card transform records:

- operation ID and kind;
- source and target card IDs;
- Claude finding IDs being addressed;
- claim IDs touched;
- expected changed element IDs;
- actual changed element IDs;
- whether scope expansion was explicitly authorized;
- a reason.

Stable `element_id` values are required across the before/after card JSON. A merge may move an element into a new card without renaming the element. This lets the validator distinguish a real content or presentation change from a container change.

## Computed transform diff

Version 1.0 trusted the transform record's `actual_changed_element_ids`. Version 1.1 reads the source and output card JSON and computes the changed element set itself.

For each stable element ID, the validator compares canonical JSON. Added, removed, or changed elements enter the computed diff. The computed set must exactly equal the union of operation-level `actual_changed_element_ids`.

This catches both directions of dishonesty or drift:

```text
artifact changed, operation forgot to declare it -> fail
operation claims an element changed, artifact did not change -> fail
```

The validator also binds:

- each source card ID to its canonical SHA-256 in `inputs.source_card_digests`;
- each output card ID to its canonical SHA-256 in `outputs.card_digests`;
- source and output article bytes to their declared SHA-256 values;
- the whole source/output card files to the diff manifest.

Artifact paths are relative to the bundle directory and may not escape it.

## Immutable evidence assets

Plots, tables, source images, and other evidence-bearing assets can be declared immutable. Probe may move, scale, or frame their presentation, but it may not redraw, regenerate, crop away meaning, or alter the asset bytes.

Each immutable asset records:

```text
asset_id
before_path / after_path
before_digest / after_digest
mutation_policy = byte_identical
regenerated = false
bound_claim_ids
referenced_by_element_ids
allowed_presentation_changes
actual_presentation_changes
status
```

The validator hashes both files. Their declared digests must match the files, the before/after bytes must be identical, `regenerated` must be false, presentation changes must stay inside the allow-list, and every referenced output element must bind to the same `asset_id`.

This keeps the evidence carrier immutable while leaving layout work inside Probe.

## Cross-card and package integrity

Probe is the first layer allowed to reason over the package as a package. It therefore checks:

1. **cross-card conflict** — cards bound to the same evidence disagree on number, direction, population, timeframe, uncertainty, or claim strength;
2. **package omission** — merge or reduction silently drops a material limitation, qualifier, or claim required for the reader outcome.

Coverage is bidirectional. Every `required_claim_id` must be represented or carry an explicit disposition (`out_of_scope`, `blocked_upstream`, or `deferred`). The semantic auditor, not Probe, decides which claims belong in the required set.

## Prose strengthening boundary

The article rewrite record preserves:

```text
new_claim_ids = []
removed_material_claim_ids = []
claim_strength_changed = false
```

Probe can make the explanation more direct, readable, vivid, or better ordered. It cannot convert association into causation, uncertainty into certainty, or practical meaning into recommendation.

## EvidenceQuiz: isolated-reader reconstruction

Version 1.1 adds a reader reconstruction gate. The assessor must be independent from Probe and see only the final article and cards:

```text
role = independent_isolated_reader
input_visibility = final_package_only
saw_truth_boundary = false
saw_claude_audit = false
saw_transform_record = false
```

The quiz is not a beauty score. It asks whether a reader can reconstruct the package's required evidence structure. The minimum categories are:

- central claim;
- limitation;
- causal boundary;
- applicability;
- misuse boundary.

A package may add evidence weight, evidence role, numeric context, population, or uncertainty questions.

For an `answerable` question, a passing record must include at least one reconstructed claim and visible support from an article snippet or output-card element. Article snippets are checked against the actual output article; card element IDs are checked against the actual output cards.

For a `should_be_na` question, the isolated reader must return `na` and cite no supporting claim or location. This is how the gate tests whether the final package accidentally invites an unsupported prescription, mechanism, threshold, or other forbidden inference.

The union of passing answerable questions must reconstruct every represented required claim.

## Hard guards

Version 1.1 requires:

```text
no_new_epistemic_content
claim_strength_preserved
numeric_fidelity
required_qualifiers_preserved
forbidden_overclaims_absent
cross_card_consistency
package_coverage_complete
article_card_alignment
edit_scope_respected
immutable_assets_preserved
artifact_diff_verified
reader_reconstruction_passed
```

Hard Claude findings must be `resolved`. Warning findings may be `accepted_warning` with a reason. Probe cannot self-certify a failed guard by writing `final_gate: pass`; the validator derives the expected gate.

## Validation

```bash
python scripts/validate_probe_post_audit.py \
  fixtures/valid_probe_post_audit_bundle.json
```

Machine-readable output:

```bash
python scripts/validate_probe_post_audit.py \
  fixtures/valid_probe_post_audit_bundle.json --json
```

The bundle's artifact paths are resolved relative to the bundle file. The canonical fixture therefore binds to `fixtures/probe/`.

The validator remains dependency-free. It verifies closure, bindings, package coverage, computed change scope, article rewrite invariants, immutable evidence assets, isolated-reader reconstruction, and final-gate consistency. It does not redo the semantic audit.

## Compatibility

The validator still accepts `contract_version: "1.0"` bundles. New production bundles use version 1.1 and `schemas/runtime/probe_post_audit_bundle.schema.json`. The preserved v1.0 schema is `schemas/runtime/probe_post_audit_bundle_v1.0.schema.json`.
