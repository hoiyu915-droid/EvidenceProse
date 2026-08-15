# Probe post-audit transform

Contract: `EP_PROBE_POST_AUDIT_TRANSFORM v1.0`

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
  -> EP_PROBE_POST_AUDIT_TRANSFORM record
  -> deterministic transform gate
```

The important boundary is not whether Probe may rewrite. It may. The boundary is that **rhetorical freedom must not create epistemic authority**.

## What Probe is allowed to do

Probe may keep, patch, merge, recompose, and—only when narrower repair cannot restore coherence—regenerate a card. For prose it may reorder, compress, simplify, expand an already-supported explanation, add a supported bridge, strengthen rhetoric, or retitle.

Probe may not create a new empirical claim, evidence-bearing number, causal mechanism, broader population, recommendation, threshold, or stronger certainty merely because the result reads better.

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

The preferred transform order is:

```text
KEEP -> PATCH -> MERGE -> RECOMPOSE -> REGENERATE
```

This is a locality preference, not a ban on rewrite. A full regeneration is legal when the narrower forms cannot produce a coherent final artifact, but its wider change scope must be explicit.

## Cross-card and package integrity

Probe is the first layer allowed to reason over the package as a package. It therefore checks two classes of failure that are easy to miss upstream:

1. **cross-card conflict** — two cards bound to the same evidence disagree on number, direction, population, timeframe, uncertainty, or claim strength;
2. **package omission** — the merged/reduced package silently drops a material limitation, qualifier, or claim that was required for the reader outcome.

Coverage is bidirectional. A final package must account for every `required_claim_id` either by representing it or by recording an explicit disposition (`out_of_scope`, `blocked_upstream`, or `deferred`). Disposition is not permission to hide a material limitation; the semantic auditor decides what belongs in the required set.

## Prose strengthening boundary

The article rewrite record exposes three invariants:

```text
new_claim_ids = []
removed_material_claim_ids = []
claim_strength_changed = false
```

This permits stronger writing without stronger science. Probe can make the explanation more direct, readable, vivid, or better ordered, but it cannot convert association into causation, uncertainty into certainty, or practical meaning into recommendation.

## Edit locality

For every operation, `actual_changed_element_ids` is compared with `expected_changed_element_ids`. Any unexpected change is a hard failure unless `scope_expansion_authorized` is true.

This is deliberately simpler than a full visual dependency graph. It captures the useful part of edit-locality control without forcing TA/TP to carry another graph or schema.

## Hard guards

Release requires all of the following to pass:

- no new epistemic content;
- claim strength preserved;
- numeric fidelity;
- required qualifiers preserved;
- forbidden overclaims absent;
- cross-card consistency;
- package coverage complete;
- article/card alignment;
- edit scope respected.

Hard Claude findings must be `resolved`. Warning findings may be `accepted_warning` with a reason. Probe never self-certifies a failed hard guard by writing `final_gate: pass`; the validator derives the expected gate from the transform record.

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

The validator is dependency-free and intentionally does not redo the semantic audit. It verifies closure, bindings, coverage, change scope, article rewrite invariants, declared hard guards, and final-gate consistency.
