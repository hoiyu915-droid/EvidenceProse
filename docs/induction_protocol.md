# Induction protocol

## Purpose

This protocol extracts repeatable writing logic from multiple completed science explainers. Its target is not checklist compliance but reader-safe comprehension: a non-specialist should understand the evidence weight, limitations, applicability and causal or decision boundary. It does not summarize a single article into a premature universal template.

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

### 1. Define the reader decision

Before auditing sentences or cards, define:

- the question the reader should be able to answer;
- the intended takeaway;
- the forbidden takeaway or likely misuse;
- the evidence strength and robustness hierarchy;
- the limitations and applicability boundaries that must alter the conclusion;
- the causal, comparative and clinical ceiling.

These are the primary success criteria for the explainer. Store them in `card_storyboard.json` under `reader_contract` when rendered companions exist. For a prose-only sample, use them as review questions; the current sample schema does not yet persist a standalone reader contract. A clean checklist cannot compensate for a wrong or incomplete reader takeaway.

### 2. Find and bind the primary source

Search ChatGPT Library first. Resolve the existing primary paper in this order: DOI, exact article title, then filename. Search supplementary material only after the primary article and never silently substitute it for the main paper. Use an uploaded scratch copy or another fallback only after the primary PDF cannot be found in Library, and record the search result, fallback identity and verification state.

Record the paper identity, DOI or other stable identifier, source digest when available, verification state, and the date of analysis. Record the committed article digest separately; a later interpretive correction belongs in metadata or a new sample, not in a silent rewrite of the observed article.

When multiple render queues are supplied, bind cards to a queue before auditing them. Use exact title sequence and content identity, record both accepted and rejected queue digests, and never choose a queue merely because its topic is similar.

### 3. Audit content truth before upload

Compare the proposed explainer content with the primary source PDF. Verify not only numbers and direction, but also evidence strength, source layer, attribution, material limitations, applicability, causal structure and conclusion ceiling. Check whether omissions or emphasis would cause the reader to miss the intended takeaway or adopt a forbidden one.

The JSON queue records a planned expression of the content; it is not the authority for scientific truth.

### 4. Audit substantive render fidelity after upload

If cards or other rendered companions are present, read the rendered artifact as a reader would. Meaning-preserving paraphrase, abbreviation, synonymous wording, sentence restructuring and harmless explanatory labels pass. Fail only when the rendering materially changes evidence meaning, weight, attribution, scope, applicability, causal boundaries, a data-bearing visual relation or source traceability.

Use `audit_policy.engineering_conformance_track` to interpret JSON object, relation, citation and layout adherence separately from the scientific verdict. Enforce a lock as a science-communication gate only when its protective purpose covers factual accuracy, evidence weight, attribution, applicability, causal boundaries, data-bearing geometry or traceability, and the violation can materially alter reader understanding. Record that purpose in the relevant audit finding or correction when it matters; the current schema does not require a per-lock conformance ledger. Otherwise treat it as an engineering warning rather than a failure.

The former literal `visible_text` whitelist may be retained as `historical_text_comparison`, but it records only equivalence or wording divergence and has no pass/fail status. A wording difference alone is not evidence of lower quality.

A render-fidelity audit must inspect data-bearing geometry. A plotted point, scale position, arrow direction, relative size, ordering or colour encoding can contradict an otherwise correct text box. Conversely, decorative numbers, labels or objects do not fail merely because they were not listed in JSON; they fail only when they are plausibly read as evidence or alter the claim.

### 5. Describe method and voice before generalising

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

### 6. Update method and voice evidence separately

For every `R###` processing rule and `V###` voice rule, classify the new sample as one of:

- `supports`: the behaviour is present under the stated conditions;
- `qualifies`: the behaviour is present but needs a narrower condition;
- `contradicts`: the sample supplies a genuine counterexample;
- `not_applicable`: the sample does not test the rule.

Absence is not automatically contradiction.

The same sample may support a method rule while only qualifying a voice rule. Do not merge the two ledgers merely because they occur in the same paragraph.

### 7. Detect contamination

Technically incorrect, unsupported, or overly strong sentences are recorded in `contamination_notes`. They remain part of the observed sample but cannot support a preferred writing rule.

Typical examples include confusing odds with risk, extending a treatment duration beyond the source, or treating zero observed heterogeneity as proof of identical effects.

Ambiguous coefficient units and headline wording that suppresses a failed sensitivity analysis are also contamination candidates: polished phrasing is not allowed to flatten the source's robustness hierarchy.

### 8. Recalculate rule state

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
8. In a held-out reader check, the rule helps readers distinguish what is supported, uncertain, out of scope and non-causal without importing the reference article's wording.

For voice rules, the held-out reconstruction must preserve the evidence boundary without copying a sample's topic-specific vocabulary or persona. Machine auditability is an integrity control; it cannot substitute for this comprehension check.

## Repository readiness gate

The project is ready to implement a production writer when:

- recent samples add examples and conditions more often than new core rules;
- the invariant core is separable from study-design modules;
- a held-out evidence package can be turned into a comparable narrative plan without seeing its reference article;
- claim provenance survives from evidence input to final prose;
- validators can detect unsupported numbers, source-layer collapse, inference promotion, and clinical-positioning overreach;
- blinded readers can identify the intended takeaway, evidence weight, material limitations, applicability and forbidden takeaway;
- failures are reported as structured gaps rather than silently repaired by invention.

Validators remain necessary for structural integrity but are never sufficient evidence that the writer is production-ready.
