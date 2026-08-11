# Induction protocol

## Purpose

This protocol extracts repeatable writing logic from multiple completed science explainers. It does not summarize a single article into a premature universal template.

## Unit of observation

Every completed explainer becomes one immutable sample (`S###`). A sample contains:

- the exact observed article;
- a SHA-256 digest that makes later article mutation detectable;
- source identity and verification state;
- study and topic characteristics;
- observable editorial decisions;
- evidence linking the sample to candidate rules;
- a separate article-register observation so processing method and visible voice are not learned as one undifferentiated style;
- suspected technical errors or overclaims that must not be learned.
- receipts for any source PDF, alternative queues, canonical render queue, and rendered companion artifacts used in the analysis.

The article and the interpretation record are stored separately. Updating a rule never silently rewrites the observed article.

## Per-sample workflow

### 1. Bind the source

Record the paper identity, DOI or other stable identifier, source digest when available, verification state, and the date of analysis. Record the committed article digest separately; a later interpretive correction belongs in metadata or a new sample, not in a silent rewrite of the observed article.

When multiple render queues are supplied, bind cards to a queue before auditing them. Use exact title sequence and content identity, record both accepted and rejected queue digests, and never choose a queue merely because its topic is similar.

### 2. Audit companion artifacts on two tracks

If cards or other rendered companions are present, keep two verdicts separate:

- semantic fidelity: whether claims, scope, uncertainty and causal structure remain faithful to the source;
- strict render compliance: whether every visible string and number is authorised by the canonical queue.

Scene descriptions authorise objects and composition, not extra visible labels. A semantically sensible label still fails a `no_unlisted_visible_text` contract when it is absent from the authorised list.

A semantic audit must also inspect data-bearing geometry. A plotted point, scale position, arrow direction, or colour encoding can contradict an otherwise correct text box; such a card fails semantic fidelity even if every prose claim is accurate.

### 3. Describe method and voice before generalising

Record concrete writing decisions such as:

- section order;
- claim order;
- how numbers are contextualised;
- how pooled and single-study findings are separated;
- where mechanism enters the narrative;
- how limitations alter clinical positioning;
- what information is deliberately omitted.

Record the visible article register separately, including:

- how certainty is calibrated in the same paragraph as a result;
- whether a claim is attributed to the review, one study, the authors, or the explainer;
- whether headings address reader questions and translate technical terms into plain language;
- whether the prose is dense, promotional, alarmist, neutral, or explicitly boundary-bearing.

Descriptions must be recoverable from an excerpt or a precise location in the sample.

### 4. Update method and voice evidence separately

For every `R###` processing rule and `V###` voice rule, classify the new sample as one of:

- `supports`: the behaviour is present under the stated conditions;
- `qualifies`: the behaviour is present but needs a narrower condition;
- `contradicts`: the sample supplies a genuine counterexample;
- `not_applicable`: the sample does not test the rule.

Absence is not automatically contradiction.

The same sample may support a method rule while only qualifying a voice rule. Do not merge the two ledgers merely because they occur in the same paragraph.

### 5. Detect contamination

Technically incorrect, unsupported, or overly strong sentences are recorded in `contamination_notes`. They remain part of the observed sample but cannot support a preferred writing rule.

Typical examples include confusing odds with risk, extending a treatment duration beyond the source, or treating zero observed heterogeneity as proof of identical effects.

Ambiguous coefficient units and headline wording that suppresses a failed sensitivity analysis are also contamination candidates: polished phrasing is not allowed to flatten the source's robustness hierarchy.

### 6. Recalculate rule state

Rule maturity states are:

```text
hypothesis -> candidate -> conditional -> stable
                         \-> contradicted
                         \-> rejected
```

- `hypothesis`: observed in one sample or proposed from analysis.
- `candidate`: independently supported but not yet tested broadly.
- `conditional`: repeatable only under explicit study or audience conditions.
- `stable`: survived varied samples and held-out reconstruction.
- `contradicted`: a material counterexample remains unresolved.
- `rejected`: evidence shows the proposed rule should not govern generation.

No fixed sample count automatically creates a stable rule.

## Registry integrity

A sample addition is atomic across the sample record, immutable article digest, rule receipts, voice receipts, cumulative batch result and ordered registry indexes. Dates in a rule catalogue cannot predate evidence cited by that rule. Storyboard counts and failure IDs must be derived from the card records rather than copied from memory.

The dependency-free validator is the executable form of these structural constraints. It deliberately rejects unregistered sample directories, stale catalogues, broken artifact or queue bindings, batch mirrors that drift from their sample, and contamination notes that disappear between ledgers.

## Promotion gate

A rule may enter the generation contract only when all are true:

1. It has support from multiple independent samples.
2. Supporting samples are not merely rewrites of the same source or topic.
3. Counterexamples are resolved through an explicit condition or the rule is narrowed.
4. At least one held-out reconstruction benefits from the rule.
5. The rule does not encode a known contamination note.
6. Its required inputs can be represented in the evidence ledger.
7. Its output can be audited manually or by a validator.

For voice rules, the held-out reconstruction must preserve the evidence boundary without copying a sample's topic-specific vocabulary or persona.

## Repository readiness gate

The project is ready to implement a production writer when:

- recent samples add examples and conditions more often than new core rules;
- the invariant core is separable from study-design modules;
- a held-out evidence package can be turned into a comparable narrative plan without seeing its reference article;
- claim provenance survives from evidence input to final prose;
- validators can detect unsupported numbers, source-layer collapse, inference promotion, and clinical-positioning overreach;
- failures are reported as structured gaps rather than silently repaired by invention.
