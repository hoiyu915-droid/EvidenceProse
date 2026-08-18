# Rendered Card Audit

Contract: `EP_RENDERED_CARD_AUDIT v1.0`

Rendered Card Audit (RCA) is the read-only post-render lane for EvidenceProse companion cards. It answers one question that producer JSON cannot answer by itself: **what did the finished image actually tell the reader?**

RCA sits after image generation and before release. It does not modify TP03, reseal generation queues, edit images, or generate replacements.

```text
audited truth / bound primary source
        +
final card specification
        +
rendered image
        |
        v
RCA-00 ingest + SHA-256 dedup
RCA-01 bind literature
RCA-02 build expected semantic packet
RCA-03 blind render readback  <-- freeze before expected semantics are shown
RCA-04 semantic comparison
RCA-05 per-card verdict
RCA-06 cross-card/package audit
RCA-07 release gate + repair tickets
```

## Authority boundaries

RCA keeps four authorities separate:

1. `audited_truth_boundary` controls the scientific claim ceiling.
2. the bound primary source controls source-defined terminology, lists, taxonomies, sequences and attribution;
3. the final card JSON/queue records editorial intent but is not scientific authority;
4. the rendered image is the authority for what a reader actually receives.

If the image conflicts with a sound truth/spec packet, the verdict is `FAIL_RENDER`. If the image faithfully renders an upstream scientific or source-structure error, the verdict is `FAIL_SPEC` and `failure_origin` routes the repair to `FINAL_CARD_SPEC`, `TRUTH_BOUNDARY`, `SOURCE_BINDING`, or `MIXED`.

## Text is semantic, not dictation

RCA does not grade memorisation. Meaning-preserving paraphrase, translation, sentence splitting/merging, reordering, shortening, explanatory headings and harmless labels are allowed. `historical_text_comparison` may record `wording_divergence`, but wording divergence alone cannot fail a card.

What must remain stable is the evidence model: claim identity, negation, direction, material magnitude, evidence strength, causal ceiling, uncertainty, population, setting, timeframe, comparator, material qualifiers, limitations, attribution, source layer, recommendation ceiling, source-defined set membership, source-defined order, and source-defined category membership.

## Source-surface fidelity

Image generators often hallucinate *structure* from individually plausible words. RCA therefore checks a source-sensitive ledger in addition to the central prose meaning.

Protected classes are:

- `CONTROLLED_TERM` — translation/paraphrase is allowed but concept identity cannot drift into a diagnosis, established mechanism, or stronger construct.
- `CLOSED_SET` — a source-defined list cannot gain invented members, silently lose a material member while pretending completeness, or change cardinality.
- `ORDERED_SEQUENCE` — a source-defined process cannot reverse or invent steps.
- `CATEGORY_MEMBERSHIP` — an item cannot be reassigned to a stronger or different source-defined category.
- `ATTRIBUTION_BINDING` — review synthesis, cited prior theory, author hypothesis and clinical implication remain distinct source layers.
- `MATERIAL_VISUAL_RELATION` — arrows, grouping, hierarchy, order, scale or colour that carry scientific meaning must stay inside the permitted relation.

Do not create a protected taxonomy merely because the paper mentions several related terms. The ledger protects structures that the source or audited truth actually establishes.

## Blind readback

RCA-03 sees the rendered card before it sees the expected semantic packet, truth boundary, generation prompt or sibling specification. It records the visible central message, apparent evidence strength, apparent causal structure, limitations, lists/categories/sequences and material visual relations. The readback is frozen before comparison.

This is input isolation, not proof of model-error independence. A generator and auditor from the same model family can share systematic mistakes.

## Audit axes

`CONTENT_MEANING` checks the scientific claim, direction, numbers, evidence strength, causal ceiling, uncertainty, scope, limitations and forbidden takeaways.

`SOURCE_SURFACE` checks terminology, list membership/cardinality, taxonomies, category membership, source attribution, evidence role, figure/table-derived structure and pseudo-precision.

`VISUAL_SEMANTICS` checks arrows, grouping, order, hierarchy, size, scale, axes, colour, uncertainty depiction and attribution by layout.

`CITATION_TRACEABILITY` checks source identity and whether material claims remain traceable. Harmless duplicate placement is a warning; wrong or unbound source identity is material.

`ENGINEERING_CONFORMANCE` records size, typography, layout, extra wording, style locks and similar production deviations. It is warning-only unless the deviation materially changes scientific understanding or prevents verification, in which case it is escalated to the substantive axis it actually harms.

## Verdicts

- `PASS` — all substantive axes and engineering conformance pass.
- `PASS_WITH_WARNINGS` — only non-material deviations remain.
- `FAIL_RENDER` — expected science/spec is acceptable but the final image materially changes or invents meaning, source structure, visual semantics or traceability.
- `FAIL_SPEC` — the render reflects a materially wrong or unsupported upstream specification/truth/source binding.
- `BLOCK_UNVERIFIABLE` — a necessary source, card identity, rendered element or traceability link cannot be verified without guessing.

`cardset_audit.status` is deliberately separate from per-card verdicts. It covers only cross-card conflicts and package coverage. A single failed card therefore does not automatically make `cardset_audit.status = FAIL`; the top-level `release_gate` aggregates both layers.

## Correlated-model error

Blind input isolation prevents answer leakage but does not make same-family model errors independent.

RCA derives:

```text
different_family -> material_to_run = false
same_family      -> material_to_run = true
unknown           -> material_to_run = true
```

If correlated-model risk is material on a high-stakes cardset, a secondary review is required. High stakes include causal ceilings, forbidden takeaways, clinical/safety boundaries, evidence-strength decisions, and source-defined structures whose hallucination would materially alter interpretation. Until that review agrees on the material axes, the release ceiling is `BLOCKED`.

For non-high-stakes cardsets, material correlated-model risk does not force a second reviewer but caps release at `PASS_WITH_WARNINGS`.

## Repair tickets

Every `FAIL_RENDER` and `FAIL_SPEC` requires an executable repair ticket. The allowed operations are:

```text
REMOVE
REPLACE
RELABEL
REWIRE
RECOMPOSE
```

The ticket states what to keep, remove, replace, rewire and not touch, plus the acceptance test and minimal recheck axes.

A substantial change is triggered by a source/meaning structural trigger or by the provisional 10% weighted-semantic heuristic when the card has enough semantic mass (`total_semantic_weight >= 10`). On very small cards, the percentage is ignored and structural triggers decide. The 10% threshold is an operator heuristic, not an empirically validated standard; it must be calibrated against at least 30 real repair cases before being treated as stable.

When a substantial remove/recompose creates a reader-facing content gap, supported replacement material is mandatory. Its source priority is audited truth/Probe content, then the bound primary source, then a semantic-preserving explainer paraphrase. If no supported material exists, record `BLOCKED_NO_SUPPORTED_MATERIAL`; do not invent filler.

The user-facing repair report should show substantial replacement prose in an editable writing-block/text-edit surface. The JSON stores the same text as `replacement_material.text` for traceability.

## Recheck

Unchanged images with unchanged hashes and source bindings retain their prior audit. After repair, re-audit the changed card on the implicated axes, rerun citation traceability, and run a lightweight cross-card check for touched claims/terms. Full cardset re-audit is required when the truth boundary, source binding, shared taxonomy/terminology, shared material numbers, or package coverage changes.

## Validation

```bash
python scripts/validate_rendered_card_audit.py \
  fixtures/valid_rendered_card_audit.json --json
```

The validator checks closure, hashes, deduplication, repair-ticket requirements, substantial-change replacement rules, cardset aggregation, `FAIL_SPEC.failure_origin`, methodological-risk derivation and release-gate consistency. It does **not** decide whether the science or image semantics are correct; those judgments must already be recorded by the auditor.
