# Rendered-card audit

Contract: `EP_RENDERED_CARD_AUDIT v1.1`  
Method revision: `1.3-semantic-surface-and-role-closure`

EvidenceProse audits the reader-visible artifact, not merely whether expected concepts appear. RCA is read-only with respect to TP03/Probe and must bind each image to the card that actually generated it before comparison.

## RCA-00 to RCA-03 — bind, source, expected packet, blind readback

1. Bind image → `card_id` → actual final queue/spec → primary source. Ambiguous identity is `BLOCK_UNVERIFIABLE`.
2. Build the expected packet from the final queue plus primary source: claims, evidence strength, causal ceiling, limitations, protected lists/taxonomies, semantic roles, evidence roles and material visual relations.
3. Blind-read the rendered image first. Freeze every material content node and every material edge before seeing the expected packet.

A material content node includes visible text, category, example, population, context, outcome, mechanism, number, citation, evidence marker or icon-label pair that can change scientific understanding. Do not collapse several concrete items into one vague theme.

## RCA-04 — visual topology closure

Every material observed edge gets one disposition and every expected relation gets one coverage result. Check source node, target node, direction, relation type, condition, branch parent, terminal state and path-level implication.

A directional arrow where the intended relation is non-directional is a failure. A correct paragraph cannot rescue a wrong branch, arrow, ordering or group topology. When a relation comes from a figure/table/taxonomy, inspect that source object directly.

## RCA-05 — semantic surface and role closure

Every material content node gets exactly one source-surface disposition. Literal `visible_text` is **not** a whitelist: wording may differ, and source-supported explanatory microcopy may be added when it merely restates or decomposes an already-authorized claim.

`SOURCE_SUPPORTED_EXPLANATORY_EXPANSION` may pass only when all are true:

- the node is explanatory microcopy, a definition or a descriptive label;
- the bound primary source supports it with an auditable locator;
- it is a restatement or explanatory decomposition of an already-authorized claim;
- it adds no new substantive claim, population, category, context, outcome, intervention, mechanism, number, citation, scope, evidence role or topology.

Specific categories/examples/populations/contexts/outcomes/interventions/mechanisms/numbers/citations/evidence-role markers and closed-set members never qualify merely because they are plausible or source-supported elsewhere. An extra scientific item requires actual authorization and primary-source support.

RCA also checks **role assignment**. If two boxes are meant to represent different positions but both receive the same combined paragraph, the text may be true yet the card still fails because the semantic roles are wrong. Evidence markers are semantic claims too: colour/shape/label must match the card and cardset evidence-role grammar; cross-card role drift is `FAIL_RENDER`.

If one rendered sentence contains both a supported paraphrase and a new unsupported clause, split it into separate material nodes. The supported half does not launder the unsupported half.

## RCA-06 to RCA-08 — verdict, cardset, repair

Per-card verdicts: `PASS`, `PASS_WITH_WARNINGS`, `FAIL_RENDER`, `FAIL_SPEC`, `BLOCK_UNVERIFIABLE`. PASS requires both topology closure and semantic-surface/role closure.

`FAIL_RENDER` means the upstream science/spec is sound but the rendered artifact materially changes meaning, topology, source surface, semantic role, evidence role or traceability. `FAIL_SPEC` means the render faithfully reflects a materially wrong upstream specification.

Cross-card audit checks contradictions, evidence-role drift, taxonomy drift, scope expansion and limitation coverage.

Every failed card gets an executable repair ticket. All user-facing repairs appear in one writing block beginning exactly with `imgedit`, followed by `[圖卡名稱]` sections in card order. Ordinary chat reports only verdict/count/card IDs.

## Canonical regressions from Roesler 2025

- C05: source-supported microcopy explaining replicability, causal-control and generalizability limits is allowed; absence from literal `visible_text` is not a defect by itself.
- C06: pasting the same combined paragraph into two boxes that should separately represent inner autonomous transformation and relationship-based change is a wrong-role assignment.
- C09: split mixed added text clause-by-clause; a supported causal-limit paraphrase may pass, while an unsupported added mechanism/influence claim does not inherit that pass.
- C01/C10: an unauthorized evidence marker is not decoration; evidence-role drift is substantive.
- C03: a directional arrow replacing a non-directional bridge is a topology failure even when all labels are correct.

The forbidden shortcuts are therefore symmetrical: **“it is not in `visible_text`, so fail it” is wrong; “it sounds plausible / is generally true, so pass it” is also wrong.**
