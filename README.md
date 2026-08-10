# EvidenceProse

EvidenceProse is an evidence-to-prose research repository. It learns how calibrated Traditional Chinese science explainers are constructed from reviewed examples, records the supporting observations, and turns only stable patterns into generation and validation rules.

The project is deliberately data-first. A polished article is not treated as a template to copy. Each article is an observation sample that may support, qualify, contradict, or contaminate a candidate rule.

## Current status

- Phase: pattern induction
- Samples: 2 (`S001`–`S002`)
- Rule catalogue: 11 (`R001`–`R011`): 9 candidates, 1 conditional rule, 1 hypothesis
- Stable generation rules: 0
- Domains observed: clinical intervention meta-analysis and public-health systems narrative review
- Primary output language: Traditional Chinese

No candidate rule is production-authoritative yet.

## Core pipeline

```text
Reviewed article + source provenance
  -> sample record
  -> observable writing decisions
  -> rule evidence
  -> candidate / conditional / contradicted rules
  -> saturation and held-out reconstruction
  -> generation contract
  -> prose draft
  -> claim and calibration audit
```

## Repository layout

```text
data/
  registry.json               cumulative sample/rule registry
  rules/rules.json            candidate rule catalogue
  samples/S001/
    article.md                exact observed prose sample
    sample.json               provenance, observations and cautions
  samples/S002/
    article.md                second exact observed prose sample
    sample.json               source, artifact receipts and observations
    card_storyboard.json      queue binding plus semantic/strict render audit
docs/
  induction_protocol.md       how repeated examples update the model
  terminology.md              evidence and rule-state vocabulary
schemas/
  rule.schema.json
  sample.schema.json
scripts/
  validate_registry.py        dependency-free fail-closed validator
tests/
  test_registry.py
```

## Design principles

1. Preserve provenance before interpretation.
2. Separate observed behaviour from proposed rules.
3. Separate evidence facts, author interpretation, explainer inference, gaps, and clinical positioning.
4. Record counterexamples and contamination; do not learn every polished sentence as a preferred rule.
5. Promote a rule only after independent support and held-out reconstruction.
6. Make limitations change the permitted conclusion instead of leaving them as a decorative final paragraph.
7. Keep generation and validation contracts machine-readable.
8. Audit companion cards twice: once for source meaning and once for exact render-contract compliance.

## Validation

The current validator uses only the Python standard library:

```bash
python -m unittest discover -s tests -v
python scripts/validate_registry.py
```

## Scope boundary

EvidenceProse does not currently generate publication-ready articles. The first stage accumulates enough independent examples to distinguish invariant writing logic from topic-specific choices and accidental errors.
