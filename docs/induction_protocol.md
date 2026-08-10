# Induction protocol

## Purpose

This protocol extracts repeatable writing logic from multiple completed science explainers. It does not summarize a single article into a premature universal template.

## Unit of observation

Every completed explainer becomes one immutable sample (`S###`). A sample contains:

- the exact observed article;
- source identity and verification state;
- study and topic characteristics;
- observable editorial decisions;
- evidence linking the sample to candidate rules;
- suspected technical errors or overclaims that must not be learned.

The article and the interpretation record are stored separately. Updating a rule never silently rewrites the observed article.

## Per-sample workflow

### 1. Bind the source

Record the paper identity, DOI or other stable identifier, source digest when available, verification state, and the date of analysis.

### 2. Describe before generalising

Record concrete writing decisions such as:

- section order;
- claim order;
- how numbers are contextualised;
- how pooled and single-study findings are separated;
- where mechanism enters the narrative;
- how limitations alter clinical positioning;
- what information is deliberately omitted.

Descriptions must be recoverable from an excerpt or a precise location in the sample.

### 3. Update rule evidence

For every candidate rule, classify the new sample as one of:

- `supports`: the behaviour is present under the stated conditions;
- `qualifies`: the behaviour is present but needs a narrower condition;
- `contradicts`: the sample supplies a genuine counterexample;
- `not_applicable`: the sample does not test the rule.

Absence is not automatically contradiction.

### 4. Detect contamination

Technically incorrect, unsupported, or overly strong sentences are recorded in `contamination_notes`. They remain part of the observed sample but cannot support a preferred writing rule.

Typical examples include confusing odds with risk, extending a treatment duration beyond the source, or treating zero observed heterogeneity as proof of identical effects.

### 5. Recalculate rule state

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

## Promotion gate

A rule may enter the generation contract only when all are true:

1. It has support from multiple independent samples.
2. Supporting samples are not merely rewrites of the same source or topic.
3. Counterexamples are resolved through an explicit condition or the rule is narrowed.
4. At least one held-out reconstruction benefits from the rule.
5. The rule does not encode a known contamination note.
6. Its required inputs can be represented in the evidence ledger.
7. Its output can be audited manually or by a validator.

## Repository readiness gate

The project is ready to implement a production writer when:

- recent samples add examples and conditions more often than new core rules;
- the invariant core is separable from study-design modules;
- a held-out evidence package can be turned into a comparable narrative plan without seeing its reference article;
- claim provenance survives from evidence input to final prose;
- validators can detect unsupported numbers, source-layer collapse, inference promotion, and clinical-positioning overreach;
- failures are reported as structured gaps rather than silently repaired by invention.

