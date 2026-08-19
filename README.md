# EvidenceProse

[![Validate](https://github.com/hoiyu915-droid/EvidenceProse/actions/workflows/validate.yml/badge.svg)](https://github.com/hoiyu915-droid/EvidenceProse/actions/workflows/validate.yml)

EvidenceProse is an evidence-to-prose system for calibrated Traditional Chinese science explainers. It has two deliberately separate evidence lanes, one post-audit transform stage, and one read-only post-render audit lane:

- an **induction lane** that learns repeatable writing logic from reviewed examples without treating any polished article as a universal template;
- a **TA06-backed live prose lane** that accepts already-audited scientific truth, locks the reader target, drafts prose, audits semantic fidelity and reader outcomes, and emits the reader-facing delivery shell;
- a **Probe post-audit stage** that may merge or repair card JSON and strengthen the audited prose, then verifies real before/after diffs, immutable evidence assets, package coverage, and isolated-reader reconstruction;
- a **Rendered Card Audit (RCA) lane** that reads the final rendered image after generation, blind-reads what the reader actually receives, checks source-surface hallucinations and visual semantics against audited truth and the bound primary source, and emits a release verdict plus executable repair ticket without mutating TP03 or Probe.

The highest success criterion is reader understanding: after reading, a non-specialist should be able to tell what the evidence supports, how much confidence that support deserves, whom and which settings it applies to, and what causal or practical conclusion it cannot justify.

## Current status

- Induction samples: 7 (`S001`–`S007`)
- Processing-rule catalogue: 24 (`R001`–`R024`): 9 candidates, 1 conditional rule, 14 hypotheses
- Article-register catalogue: 5 (`V001`–`V005`), all hypotheses
- Batch result index: 7 (`B001`–`B007`)
- Recorded observations: 99; contamination notes: 20
- Audited companion cards: 36 (36/36 content-truth passes; 28/36 substantive render-fidelity passes)
- Stable induction generation rules: 0
- Live runtime contract: `EP_TA06_PROSE_RUNTIME v1.0`
- Probe transform contract: `EP_PROBE_POST_AUDIT_TRANSFORM v1.1`
- Rendered-card audit contract: `EP_RENDERED_CARD_AUDIT v1.2.0`
- Rendered-card audit result schema: `1.1.0`
- Rendered-card audit policy: selected by `policies/rca/current.json`
- Delivery-shell contract: `EP-SCIENCE-EXPLAINER-OUTPUT v0.1`
- Primary output language: Traditional Chinese

`R###` and `V###` rules are still induction evidence. None is production-authoritative merely because the live lane exists. The live lane is governed by TA06 scientific truth, the standalone reader contract, semantic preservation/no-add invariants, reader-outcome auditing, and the delivery shell. Probe is governed separately by the Claude audit, the same truth boundary, file-bound transform verification, and the isolated-reader gate.

## Live TA06-backed prose lane

```text
TA06 ta06_audit_packet
  -> ta06_prose_handoff
  -> standalone prose_reader_contract
  -> prose draft
  -> EP_PROSE_AUDIT_SIDECAR v1.0
       - semantic preservation / NO_ADD
       - numeric / denominator / comparator / timeframe fidelity
       - population / causal / uncertainty / evidence-role fidelity
       - headline / analogy / recommendation overclaim checks
       - relevant / findable / understandable / usable
       - zh-Hant warning-only lint
  -> optional card package + Claude audit findings
  -> Probe EP_PROBE_POST_AUDIT_TRANSFORM v1.1
       - card merge / repair and prose strengthening
       - computed before/after element diff
       - immutable evidence-asset hashing
       - package-level coverage
       - isolated-reader EvidenceQuiz
  -> EP-SCIENCE-EXPLAINER-OUTPUT v0.1
  -> runtime + delivery validation
```

A valid TA06 handoff is the scientific truth boundary. EvidenceProse does not silently redo source discovery in this lane. If the handoff is missing, blocked, internally inconsistent, or superseded by new evidence, route back to TA06 rather than guessing.

The canonical runtime specification is [docs/ta06_prose_runtime.md](docs/ta06_prose_runtime.md). The machine contract is [contracts/EP_TA06_PROSE_RUNTIME_CONTRACT_v1.0.json](contracts/EP_TA06_PROSE_RUNTIME_CONTRACT_v1.0.json).

### Standalone reader contract

Before drafting, the live lane records:

```text
audience
purpose
reader_question
intended_takeaway
forbidden_takeaway
central_claim
evidence_weight
limitations
applicability
misuse_boundaries
```

A local default is only a rendering target; it is never represented as a discovered fact about the user.

### Semantic hard gate

Every retained proposition must preserve material facts, numbers, units, denominators, comparators, conditions, population, setting, timeframe, uncertainty, causal strength, evidence role, attribution, and source layer.

Unsupported new facts, evidence-bearing numbers, sources, quotations, mechanisms, causal explanations, recommendations, thresholds, prescriptions, actors, deadlines, or broader applicability are forbidden.

Hard failures include association→causation, subgroup→whole population, pooled→subgroup estimate, proxy→clinical outcome, observational plateau→intervention threshold, exploratory subgroup→treatment ranking, short-term attrition→long-term adherence, analogy→demonstrated mechanism, practical meaning→recommendation, and a headline stronger than the body.

### Reader outcomes and zh-Hant lint

The completed draft is audited once on `relevant`, `findable`, `understandable`, and `usable`. These are audit axes, not four mandatory whole-article rewrite passes.

Traditional-Chinese lint for long sentences/paragraphs, `的` chains, vague pronouns, unnecessary code switching, passive voice, hedge stacks, and jargon density is warning-only. It cannot override scientific precision.

## Probe post-audit transform

Probe receives producer card JSON, Claude audit findings, and the audited prose. It may keep, patch, merge, recompose, or—when narrower repair cannot restore coherence—regenerate a card. It may reorder, compress, simplify, expand supported explanation, add supported bridges, strengthen rhetoric, and retitle the prose.

It may not create new scientific authority. In particular, Probe cannot add empirical claims or evidence-bearing numbers, strengthen causal or certainty language, erase material qualifiers, widen population or recommendation scope, mutate evidence assets, or certify its own reader outcome.

Version 1.1 adds three executable gates:

1. **computed transform diff** — the validator reads source and output card JSON, computes changes by stable `element_id`, and requires exact equality with the operation manifest;
2. **immutable evidence assets** — declared source plots, tables, and evidence images remain byte-identical; only recorded position, scale, or frame changes are allowed;
3. **isolated-reader EvidenceQuiz** — a reader that sees only the final article and cards must reconstruct all represented required claims and limits, while returning `NA` for unsupported prescriptions, mechanisms, thresholds, or other forbidden content.

The specification is [docs/probe_post_audit_transform.md](docs/probe_post_audit_transform.md). The canonical contract is [contracts/EP_PROBE_POST_AUDIT_TRANSFORM_CONTRACT_v1.1.json](contracts/EP_PROBE_POST_AUDIT_TRANSFORM_CONTRACT_v1.1.json). Version 1.0 remains validator-compatible but is superseded for new bundles.

## Rendered Card Audit

`EP_RENDERED_CARD_AUDIT v1.2.0` is the executable form of the post-upload substantive-render-fidelity layer. It runs after image generation and before release, and is deliberately read-only: it may read rendered images, final card specs/queues, audited truth, and bound primary sources, but it does not modify or reseal TP03 queues, edit images, dispatch generation, or rewrite Probe output. Its active versioned policy is selected by `policies/rca/current.json`; that current manifest is authoritative for the policy path, policy version and canonical digest. Its result schema is `1.1.0`.

RCA judges semantic equivalence rather than memorisation. Meaning-preserving paraphrase, translation, shortening, sentence restructuring, headings, and harmless labels are allowed. It separately audits `CONTENT_MEANING`, `SOURCE_SURFACE`, `VISUAL_SEMANTICS`, `CITATION_TRACEABILITY`, and warning-default `ENGINEERING_CONFORMANCE`. Source-defined terms, closed lists, taxonomies, category membership, ordered sequences, attribution layers, and material visual relations are protected against image-generation invention even when each individual word looks plausible.

Before comparison, RCA freezes a blind readback of the rendered image without showing the auditor the expected semantic packet, truth boundary, generation prompt, or sibling spec. This input isolation reduces confirmation bias but does not prove independence of model-family error. Same-family or unknown-family generator/auditor relationships are therefore recorded as correlated-model-error risk; high-stakes material cases require a secondary review before release.

Blocking cards use `FAIL_RENDER`, `FAIL_SPEC`, or `BLOCK_UNVERIFIABLE`. Every `FAIL_RENDER` / `FAIL_SPEC` carries an executable repair ticket. Substantial removal or recomposition also requires supported replacement material; the provisional 10% weighted-semantic threshold is an operator heuristic, not a validated scientific cutoff, and source/meaning structural triggers override it.

The specification is [docs/rendered_card_audit.md](docs/rendered_card_audit.md), byte-identical to [docs/rendered_card_audit_v1.2.md](docs/rendered_card_audit_v1.2.md). The active contract is [contracts/EP_RENDERED_CARD_AUDIT_CONTRACT_v1.2.json](contracts/EP_RENDERED_CARD_AUDIT_CONTRACT_v1.2.json). The current manifest is the authority for which versioned policy pack is active. For a policy-only rule change, edit that active policy JSON and its explicit mapping/regression cases, run `python3 scripts/validate_rca_policy.py --sync-surfaces`, then run the focused tests. The sync command updates the digest/version mirrors and rejects policy-id, contract, result-schema or method changes that require a full migration. Older v1.0/v1.1 contract snapshots are historical and superseded.

## Induction lane

The induction lane remains data-first:

```text
Reader decision + intended and forbidden takeaways
  -> Library search and primary-PDF binding
       (DOI -> exact title -> filename; supplementary files second; fallback last)
  -> reviewed source + provenance
  -> immutable sample
  -> observable writing decisions
  -> method-rule and voice-rule evidence
  -> candidate / conditional / contradicted rules
  -> contamination detection
  -> saturation and held-out reconstruction
  -> future rule promotion
```

A polished article is an observation sample, not a template to copy. The full protocol is [docs/induction_protocol.md](docs/induction_protocol.md).

## Repository layout

```text
contracts/
  EP_TA06_PROSE_RUNTIME_CONTRACT_v1.0.json
  EP_PROBE_POST_AUDIT_TRANSFORM_CONTRACT_v1.0.json
  EP_PROBE_POST_AUDIT_TRANSFORM_CONTRACT_v1.1.json
  EP_RENDERED_CARD_AUDIT_CONTRACT_v1.0.json
  EP_RENDERED_CARD_AUDIT_CONTRACT_v1.1.json
  EP_RENDERED_CARD_AUDIT_CONTRACT_v1.2.json

policies/rca/
  current.json
  policy_v1.3.0.json

data/
  registry.json
  rules/rules.json
  voice/voice_rules.json
  batch_results.json
  samples/S###/

docs/
  audit_standard.md
  induction_protocol.md
  probe_post_audit_transform.md
  rendered_card_audit.md
  rendered_card_audit_v1.2.md
  science_explainer_output_format.md
  ta06_prose_runtime.md
  terminology.md

fixtures/
  valid_ta06_prose_handoff.json
  valid_prose_reader_contract.json
  valid_prose_audit_sidecar.json
  20260815_demo-explainer.md
  valid_probe_post_audit_bundle.json
  legacy_valid_probe_post_audit_bundle_v1.0.json
  valid_rendered_card_audit.json
  rendered_card_audit/
    C01.png
  probe/
    source_cards.json
    output_cards.json
    source_article.md
    output_article.md
    assets_before/
    assets_after/

schemas/
  runtime/
    ta06_prose_handoff.schema.json
    prose_reader_contract.schema.json
    prose_audit_sidecar.schema.json
    probe_post_audit_bundle.schema.json
    probe_post_audit_bundle_v1.0.schema.json
    rendered_card_audit.schema.json
  registry.schema.json
  rule_catalog.schema.json
  rule.schema.json
  voice_rule_catalog.schema.json
  voice_rule.schema.json
  batch_results.schema.json
  sample.schema.json
  card_storyboard.schema.json

scripts/
  validate_rca_policy.py
  validate_registry.py
  validate_explainer_output.py
  validate_prose_runtime.py
  validate_probe_post_audit.py
  validate_rendered_card_audit.py
  probe_post_audit_common.py
  probe_post_audit_core.py
  probe_post_audit_artifacts.py
  probe_post_audit_quiz.py

templates/
  science_explainer.md

tests/
  test_registry.py
  test_explainer_output.py
  test_prose_runtime.py
  test_probe_post_audit.py
  test_rendered_card_audit.py
  test_rca_policy.py

.github/workflows/
  validate.yml
```

## Design principles

1. Preserve provenance before interpretation.
2. Keep scientific truth authority separate from prose authority.
3. Separate observed behaviour from proposed rules.
4. Separate evidence facts, author interpretation, explainer inference, gaps, and clinical positioning.
5. Record counterexamples and contamination; do not learn every polished sentence as a preferred rule.
6. Promote an induction rule only after independent support and held-out reconstruction.
7. Make limitations change the permitted conclusion instead of becoming a decorative disclaimer.
8. Treat reader-safe comprehension as the primary quality gate.
9. Name the exact outcome domain and denominator before translating a number into prose.
10. Keep processing method (`R###`) and article voice/register (`V###`) as separate induction layers.
11. In the live lane, preserve meaning before improving readability; precision wins on conflict.
12. Never invent missing action information for the sake of usability.
13. Keep internal audit artefacts separate from reader-facing citations.
14. Apply machine locks as science gates only when they protect a substantive interest and violation can materially change reader understanding.
15. Repair the smallest failed sentence or paragraph before attempting a wholesale rewrite.
16. Compute post-transform changes from artifacts instead of trusting a self-reported diff.
17. Keep evidence-bearing assets immutable; permit layout changes around them, not regeneration of them.
18. Test the final package through an isolated reader, including correct `NA` responses for unsupported content.
19. Audit the rendered card as a reader-visible artifact: wording freedom is allowed, but invented source structure, evidence-role upgrades, and misleading visual relations are not.
20. Keep post-render audit read-only; repair instructions route downstream or upstream without silently mutating TP03 or Probe.

## Reader-facing delivery format

The formal packaging contract is [docs/science_explainer_output_format.md](docs/science_explainer_output_format.md). New reader-facing artifacts use `YYYYMMDD_<slug>.md` and:

```text
# title
## 一句話總結
## 內容
## 引用來源
🟢/🟡/🔴 證據分級：...
> 最後更新：YYYYMMDD
```

Narrative detail inside `## 內容` remains evidence-driven and may use optional H3 subsections. Historical `data/samples/S###/article.md` files are immutable observations and are not retroactively rewritten.

Reader-facing output must not expose `filecite`, `turnNfileM`, Library/file IDs, sandbox/container paths, local PDF filenames, handoff digests, claim IDs, or other internal verification machinery.

## Validation

Run the full repository suite:

```bash
python -m unittest discover -s tests -v
python scripts/validate_registry.py --json
```

Validate a reader-facing shell:

```bash
python scripts/validate_explainer_output.py 20260815_example-topic.md
```

Validate a complete TA06-backed prose bundle:

```bash
python scripts/validate_prose_runtime.py \
  --handoff path/to/ta06_prose_handoff.json \
  --reader-contract path/to/prose_reader_contract.json \
  --audit-sidecar path/to/prose_audit_sidecar.json \
  --article 20260815_example-topic.md
```

Validate a Probe v1.1 transform bundle and its bound artifacts:

```bash
python scripts/validate_probe_post_audit.py \
  fixtures/valid_probe_post_audit_bundle.json --json
```

A passing prose-runtime validator proves that the bundle is correctly bound, its permission projection is consistent, all required semantic judgments are present and releasable, repairs are verified, reader-outcome axes do not fail, and the article satisfies the delivery shell. It does not prove scientific equivalence by string matching.

A passing Probe validator additionally proves that declared source/output files match their digests, computed element changes match the operation manifest, immutable assets remain byte-identical, package coverage is complete, and the isolated-reader record reconstructs the required final-package evidence structure. It does not replace Claude's semantic audit.

Validate the canonical rendered-card audit fixture:

```bash
python scripts/validate_rendered_card_audit.py \
  fixtures/valid_rendered_card_audit.json --json
```

Validate the active RCA policy pack and all synchronized contract, schema, fixture and documentation surfaces:

```bash
python3 scripts/validate_rca_policy.py --json
```

For a policy-only change, synchronize the current-manifest digest/version mirrors before running the tests:

```bash
python3 scripts/validate_rca_policy.py --sync-surfaces
python3 -m unittest tests/test_rca_policy.py -v
```

A passing RCA validator proves structural closure: image/source bindings and hashes, deduplication, verdict/repair-ticket closure, substantial-repair replacement requirements, cardset aggregation, correlated-model-error policy, and release-gate consistency. It does not itself decide whether the source interpretation or image semantics are scientifically correct; those judgments must already be recorded by the post-render auditor.

## Adding a reviewed induction sample

Treat an article, its interpretation record, rule receipts and batch summary as one atomic change. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Scope boundary

EvidenceProse supports a deliverable TA06-backed prose runtime for already-audited evidence packages, a bounded Probe post-audit transform stage, and a read-only rendered-card audit lane. Neither lane claims that the induction catalogue has reached saturation, and neither makes non-stable `R###` or `V###` rules production authority.

Source discovery and scientific re-audit remain upstream responsibilities. When scientific truth changes, return to TA06; when only reader-facing expression or package composition changes, keep the same truth boundary and rerun the relevant prose/Probe/RCA gates.
