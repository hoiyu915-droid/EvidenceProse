# Rendered Card Audit v1.2.0

Contract: `EP_RENDERED_CARD_AUDIT v1.2.0`
Method revision: `1.3-materiality-scope-and-role-binding`

Active policy pack, version and digest: resolved through `policies/rca/current.json`
Result schema: `1.1.0`
Surface checker: `python3 scripts/validate_rca_policy.py --json`

This revision keeps the v1.1 topology gate and v1.2 source-surface closure, then fixes a false-positive/false-negative pair exposed by the Roesler 2025 cardset:

- **false positive:** treating every non-verbatim renderer sentence as a scientific failure even when it is a source-supported, non-expansive explanation of an already authorised node;
- **false negative:** allowing source-supported words to pass when their placement, card scope, evidence-role attachment or grouping changes the model the reader sees.

## Non-negotiable rule

**Audit the scientific model the reader receives, not string identity and not topic plausibility.**

A material failure needs a material reader effect. A literal queue mismatch is not enough. Conversely, source support somewhere in the paper is not enough when the renderer imports the claim into the wrong card, wrong branch, wrong evidence role or wrong comparison slot.

## RCA-03 blind inventory

Freeze before comparison:

1. observed visual graph;
2. observed material content-node inventory;
3. visible evidence annotations and the claim nodes to which they appear attached;
4. visible grouping/role partitions when a card compares two or more positions.

A material content node is a reader-visible claim, number, category, example, mechanism, population, context, outcome, citation, evidence annotation or relationship whose presence/placement can change scientific understanding.

Do **not** split harmless wording variants into fake scientific nodes. Do split mixed clauses when different clauses need different support/scope dispositions.

## RCA-04 topology + role-partition reconciliation

Retain the existing edge-by-edge gate: source node, target node, direction, relation type, condition, branch parent, terminal state and path-level implication.

Add `role_partition_checks` for material comparisons/groupings. A card fails when supported content is placed so that required roles collapse or swap. Canonical example: if the left box is meant to represent Jung's inner-autonomous emphasis and the right box modern relationship/corrective-experience emphasis, repeating the same full two-sided sentence under both boxes is `collapsed_contrast`, not a harmless duplicate.

A harmless repeated label that does not change role, evidence weight or grouping is only an engineering/non-material warning.

## RCA-05 source-surface, scope and evidence-role closure

Every observed material node gets exactly one disposition.

Passing dispositions:

- `AUTHORIZED_AND_SUPPORTED`
- `SEMANTICALLY_EQUIVALENT_PARAPHRASE`
- `SOURCE_SUPPORTED_NONEXPANSIVE_ELABORATION`

`SOURCE_SUPPORTED_NONEXPANSIVE_ELABORATION` is allowed only when the text:

- is supported by the bound primary source;
- attaches to an already authorised semantic parent;
- adds no new claim, category/closed-set member, number, population/scope, mechanism, causal/directional relation or clinical implication;
- changes no attribution, evidence role or uncertainty;
- imports no sibling-card-specific claim;
- violates no queue lock with a material protective purpose.

Failing dispositions:

- `UNAUTHORIZED_AND_UNSUPPORTED`
- `SOURCE_SUPPORTED_BUT_OUT_OF_CARD_SCOPE`
- `MATERIAL_QUEUE_PROTECTIVE_LOCK_VIOLATION`

Blocking disposition:

- `AUTHORIZED_BUT_SOURCE_UNVERIFIABLE`

The old `SOURCE_SUPPORTED_BUT_NOT_QUEUE_AUTHORIZED` is deliberately rejected as ambiguous. It must be resolved into either non-expansive elaboration, out-of-card scope, or a material protective-lock violation.

### Evidence annotations are claim-bound

`evidence_annotation_checks` must reconcile both:

- evidence role (`CORE`, `INFERENCE`, `GAP`, `CONFLICT`); and
- which visible claim node the marker is attached to.

A valid colour used on the wrong claim is a material failure. A card-level `CORE` convention does not authorise a `CORE` marker under every theory category. Likewise a `CONFLICT` marker on a GAP-only card is evidence-role drift.

### Queue locks are not automatic science failures

`visible_text`, `provided_text_verbatim`, `no_unlisted_visible_text`, geometry locks and similar renderer constraints stay in `ENGINEERING_CONFORMANCE` unless their explicit protective purpose is scientific and their violation materially changes reader understanding or prevents verification.

Do not write a scientific finding whose only reason is “this sentence was not in visible_text”. Identify the actual material change: new claim, new category, scope expansion, wrong attribution, wrong evidence role, unsupported relation, etc. If there is no such change and the source-supported explanation is non-expansive, it passes the science lane.

### Card scope is narrower than paper scope

A claim may be source-supported and still fail the current card when it belongs to a different card function. This is `SOURCE_SUPPORTED_BUT_OUT_OF_CARD_SCOPE`.

Canonical example: on an SDA dream-agency card, importing a sibling card's therapeutic-relationship mechanism into an added “research boundary” sentence changes the card's function. The fact that the paper discusses therapeutic relationship elsewhere does not authorise that sibling-specific claim here.

## Mixed-clause repair

When one visible box contains clauses with different dispositions, split them before verdict and repair. Preserve supported clauses where possible; remove/replace only the failing clause. Do not delete a whole box because one segment is unsupported.

## Roesler 2025 regression suite

The following behaviours are now canonical regressions:

1. **Supported non-expansive explanation:** model-description prose supported by Roesler and attached to the same authorised model node must not fail solely for non-verbatim queue wording.
2. **Role-partition collapse:** duplicating the same two-sided mechanism sentence under both comparison boxes fails even though all words are supported.
3. **Sibling semantic bleed:** source-supported therapeutic-relationship content imported into the SDA card fails as out-of-card scope.
4. **Evidence-role mismatch:** a `CONFLICT` marker on a GAP-only child-motif card fails.
5. **Evidence-marker wrong binding:** `CORE` markers attached to each of four theory categories fail when the evidence role was only card-level/framework-level.
6. **Wrong arrow direction:** a speculative bridge rendered with a directional arrow remains a topology failure.
7. **Harmless duplicate label:** redundant “缺口” presentation that changes no binding or weight is warning-only.

## PASS gate

A per-card `PASS` requires:

- all substantive axes pass;
- all observed material edges dispositioned;
- all expected material relations covered;
- all material branch/terminal/role-partition checks complete;
- all observed material content nodes dispositioned;
- all material evidence annotations checked;
- no topic-plausibility shortcut;
- no literal queue-whitelist shortcut;
- materially mixed-support clauses split before disposition.

## Human repair output

All `FAIL_RENDER` / `FAIL_SPEC` repairs remain in one writing block beginning exactly with:

```text
imgedit
```

Repair the smallest failed region. Outside the block, report only verdict/count/card IDs.

## Frequent policy changes

Frequent RCA rule changes belong in the active policy pack, not in duplicated validator constants. The current manifest `policies/rca/current.json` is authoritative for the active versioned policy path, policy version and digest. Edit that policy JSON, update the disposition/status-to-verdict mapping and focused regression cases, run `python3 scripts/validate_rca_policy.py --sync-surfaces`, then run the focused tests. The sync command updates the policy-only mirrors atomically and rejects policy-id, contract, result-schema or method changes that require a full migration. The checker verifies the current pointer, canonical policy digest, active contract/schema/fixture version fields, and byte-identical parity between this active alias and `docs/rendered_card_audit_v1.2.md`.

Raise `policy_version` for a policy-only decision change. Raise `result_schema_version` when the result JSON shape changes, and raise `contract_version` only when the external RCA contract changes. Historical contract snapshots remain immutable records and must be marked superseded when a newer active contract exists.
