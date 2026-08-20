# TA06-backed prose runtime

Contract: `EP_TA06_PROSE_RUNTIME v1.1`

Status: canonical production lane for evidence packages that have already passed TA06. This runtime does not promote any `R###` processing rule or `V###` article-register rule to stable status.

## Purpose

EvidenceProse has two different jobs and must not mix them:

1. the **induction lane** learns writing patterns from reviewed examples and still uses Library/PDF source binding under `docs/induction_protocol.md`;
2. the **live TA06 lane** receives already-audited scientific truth and turns it into reader-facing prose without silently re-auditing, strengthening, or inventing the evidence.

The live lane is:

```text
TA06 ta06_audit_packet
  -> ta06_prose_handoff
  -> standalone prose_reader_contract
  -> prose draft
  -> semantic audit sidecar
  -> reader-outcome audit
  -> EP-SCIENCE-EXPLAINER-OUTPUT v0.1
  -> delivery validation
```

If the TA06 handoff is missing, blocked, internally inconsistent, or superseded by new source material, stop the live lane and return to TA06. EvidenceProse must not repair scientific truth by guessing.

## Input authority

`schemas/runtime/ta06_prose_handoff.schema.json` defines the transport boundary. The handoff is a projection, not a second audit. It carries only the material needed for prose:

- TA06 audit identity, packet version and digest;
- reader context already known upstream;
- claims with `CORE / INFERENCE / GAP / CONFLICT`, permission, support state and source locators;
- evidence items, population and uncertainty;
- public citation identities;
- terminology and required qualifiers;
- numeric ledger entries;
- document permission, released claims, blocked claims and forbidden overclaims.

The full TA06 packet remains the scientific authority. The handoff digest and source packet digest exist to detect drift; they do not create new evidence.

## Standalone reader contract

Before drafting, create a `prose_reader_contract` using `schemas/runtime/prose_reader_contract.schema.json`.

Required fields are:

- `audience`;
- `purpose`;
- `reader_question`;
- `intended_takeaway`;
- `forbidden_takeaway`;
- `central_claim`;
- `evidence_weight`;
- `limitations`;
- `applicability`;
- `misuse_boundaries`.

`local_rendering_default` is permitted only as a writing target. It is never evidence about the actual user's profession, health, demographic identity, motivation, or literacy.

The reader contract may refine audience and purpose after TA06 because that does not change scientific truth. It may not broaden the evidence boundary.

## Writer authority

The writer may choose the title, order, paragraphing, optional H3 headings, transitions, meaning-preserving paraphrases and plain-language explanations.

An analogy is editorial freedom only when it is clearly non-empirical and cannot be read as the study's demonstrated mechanism.

The writer may not add unsupported:

- empirical facts or evidence-bearing numbers;
- dates, actors, organisations or deadlines;
- mechanisms or causal explanations;
- clinical or practical recommendations;
- thresholds, optimal prescriptions or rankings;
- quotations or sources;
- broader populations, settings, comparators or timeframes.

Readability never grants evidence authority.

## Semantic preservation

Every retained proposition preserves the material qualifiers attached to it, including:

- facts;
- numbers, units and denominators;
- comparators and conditions;
- population and setting;
- timeframe;
- uncertainty;
- causal strength;
- evidence role;
- attribution and source layer.

The following promotions are hard failures:

```text
association -> causation
possibility -> certainty
subgroup -> whole population
pooled estimate -> named subgroup estimate
proxy outcome -> clinical outcome
observational plateau -> intervention threshold
exploratory subgroup -> treatment ranking
short-term attrition -> long-term adherence
study-derived duration band -> optimal prescription
analogy -> demonstrated mechanism
practical meaning -> recommendation
headline -> stronger claim than body
```

When readability and precision conflict, precision wins.

## Draft audit

The semantic auditor reads the completed draft against the TA06 handoff and the reader contract and writes `EP_PROSE_AUDIT_SIDECAR v1.1`. Its current schema is `schemas/runtime/prose_audit_sidecar.schema.json`; the preserved v1.0 schema is `schemas/runtime/prose_audit_sidecar_v1.0.schema.json`.

The sidecar has two tracks.

### Hard semantic gate

All of these must pass:

- no loss;
- no unsupported additions;
- numeric, denominator, comparator and timeframe fidelity;
- population-scope fidelity;
- causal-strength and uncertainty fidelity;
- evidence-role, attribution and source-layer fidelity;
- required qualifiers present;
- forbidden overclaims absent;
- headline no stronger than body;
- analogy not presented as mechanism;
- practical meaning not upgraded to recommendation.

Any item recorded in `violations` with `severity: hard` also forces `final_gate.status: fail`; a bundle cannot declare a hard violation and release itself as passing.

These judgments are semantic. The dependency-free validator checks that the audit artifact is complete, internally consistent and correctly bound to the handoff and reader contract; it does **not** pretend that string matching can prove scientific equivalence.

### Reader-outcome audit

Audit the finished draft once on four axes:

- `relevant`;
- `findable`;
- `understandable`;
- `usable`.

States are `pass`, `warning`, or `fail`.

These are audit axes, not four mandatory full-document rewrite passes. A failed axis blocks release because reader understanding is the project-level success criterion. A warning does not block release.

`usable` may clarify an already-supported implication or action. If actor, deadline, destination, threshold, prescription or next-step information is missing, record it in `missing_action_info`; do not fabricate it.

## Traditional-Chinese lint

The sidecar may record warnings for:

- long sentence;
- long paragraph;
- `的` chains;
- vague pronouns;
- unnecessary code switching;
- passive voice;
- stacked hedges;
- jargon density.

These are local review signals, not ISO requirements. They never block delivery by themselves and never justify a precision-reducing rewrite.

The runtime recomputes five deterministic categories from reader prose: `long_sentence` (at least 40 non-whitespace characters in one sentence), `long_paragraph` (at least 180 in one paragraph), `de_chain`, explicit `passive_voice`, and `hedge_stack`. If the sidecar's declared set for those five categories differs from the recomputed set, the validator emits a warning without changing the bundle status. `vague_pronoun`, `unnecessary_code_switching`, and `jargon_density` remain semantic review judgments. These thresholds are local heuristics, not language standards, and lint warnings do not block delivery by themselves.

## Article length

The reader-facing `## 內容` section defaults to no more than 4,000 non-whitespace Unicode code points. This is a ceiling, not a target: when the evidence base is small, the article should end naturally rather than being padded to approach 4,000 characters.

Exceed the ceiling only for a genuinely large literature base when compression would remove material claims, limitations, applicability boundaries, uncertainty, evidence roles, or causal limits. The exception is a bound audit fact, not a command-line permission. A v1.1 sidecar must include:

```json
{
  "article_sha256": "<lowercase SHA-256 of exact delivered UTF-8 bytes>",
  "delivery_length_exception": {
    "granted": true,
    "measured_characters": 4127,
    "ceiling": 4000,
    "reason": "Compression would remove material cross-study limitations."
  }
}
```

The v1.1 sidecar also binds `article_sha256`, computed over the exact delivered UTF-8 bytes. The validator rejects an article swap even when the replacement has the same length and lint categories. It recomputes `measured_characters` from that bound article and requires an exact match. `granted: true` requires both a count above 4,000 and a non-empty reason. At or below the ceiling, `granted` must be `false` and `reason` must be `null`. Runtime CLI overrides are rejected because they would not be visible in the bound bundle. This internal provenance remains outside the reader article and task JSON.

## Repair policy

Repair the smallest sentence or paragraph that fixes a hard failure. Do not automatically rewrite the whole article and risk destroying a good narrative structure.

A full rewrite is appropriate only when the user asks for it or when targeted repair cannot restore a coherent article.

After repair, rerun the semantic audit. A release with targeted repairs requires every recorded repair to be `verified`.

## Reader-facing projection

The public artifact follows `EP-SCIENCE-EXPLAINER-OUTPUT v0.1`:

```text
# title
## 一句話總結
## 內容
## 引用來源
🟢/🟡/🔴 證據分級：...
> 最後更新：YYYYMMDD
```

The audit sidecar, claim IDs, source locators, handoff digests, Library receipts and internal verification tokens stay internal.

## Validation

For a complete runtime bundle:

```bash
python3 scripts/validate_prose_runtime.py \
  --handoff path/to/ta06_prose_handoff.json \
  --reader-contract path/to/prose_reader_contract.json \
  --audit-sidecar path/to/prose_audit_sidecar.json \
  --article 20260815_topic.md
```

Machine-readable output adds `--json`.

For a justified large-literature exception, record the authorization in the bound v1.1 audit sidecar and run the same command. The validator checks transport graph integrity, digests, permission projection, semantic-gate consistency, repair state, reader-outcome state, recomputed length-exception provenance and the existing delivery shell. It does not replace the semantic auditor.

The validator continues to accept a v1.0 sidecar for an article at or below the ceiling. A v1.0 sidecar cannot authorize an over-limit release.

## R/V rule boundary

`R###` and `V###` remain induction artefacts until they meet the promotion gate in `docs/induction_protocol.md`.

The live runtime can consult non-stable R/V rules as editorial candidates, but a candidate or hypothesis may never:

- override a TA06 claim permission;
- erase a required qualifier;
- create a new empirical fact;
- become a hard release requirement merely because it appeared in prior samples.

This lets the production lane exist without pretending that the induction catalogue has already reached saturation.
