# EvidenceProse

[![Validate](https://github.com/hoiyu915-droid/EvidenceProse/actions/workflows/validate.yml/badge.svg)](https://github.com/hoiyu915-droid/EvidenceProse/actions/workflows/validate.yml)

EvidenceProse is an evidence-to-prose research repository. It learns how calibrated Traditional Chinese science explainers are constructed from reviewed examples, records the supporting observations, and turns only stable patterns into generation and validation rules.

The project is deliberately data-first. A polished article is not treated as a template to copy. Each article is an observation sample that may support, qualify, contradict, or contaminate a candidate rule.

## Current status

- Phase: pattern induction
- Samples: 5 (`S001`–`S005`)
- Processing-rule catalogue: 18 (`R001`–`R018`): 9 candidates, 1 conditional rule, 8 hypotheses
- Article-register catalogue: 5 (`V001`–`V005`), all hypotheses
- Batch result index: 5 (`B001`–`B005`), keeping method and voice findings separate
- Recorded observations: 68; contamination notes: 13
- Audited companion cards: 24 (4 semantic failures; 24 strict-render failures)
- Stable generation rules: 0
- Domains observed: clinical intervention meta-analysis, public-health systems narrative review, single-centre observational rehabilitation research, footwear scoping review, and scientific-QA benchmark development
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
  registry.json               canonical paths and ordered ID indexes
  rules/rules.json            processing-method rule catalogue (`R###`)
  voice/voice_rules.json      article-register rule catalogue (`V###`)
  batch_results.json          cumulative five-batch result index (`B###`)
  samples/S001/
    article.md                exact observed prose sample
    sample.json               provenance, article digest, observations and cautions
  samples/S002/
    article.md                second exact observed prose sample
    sample.json               source, artifact receipts and observations
    card_storyboard.json      queue binding plus semantic/strict render audit
  samples/S003/
    article.md                third exact observed prose sample
    sample.json               primary-study provenance and induced observations
    card_storyboard.json      two-track card audit with visual-data failure record
  samples/S004/
    article.md                fourth exact observed prose sample
    sample.json               scoping-review provenance and induced observations
    card_storyboard.json      title-bound queue audit with fabricated-reading record
  samples/S005/
    article.md                fifth exact observed prose sample
    sample.json               benchmark-paper provenance and induced observations
    card_storyboard.json      two-track audit of unauthorised text and visual-data fabrication
docs/
  batch_results.md            human-readable five-batch summary
  induction_protocol.md       how repeated examples update the model
  terminology.md              evidence, method/voice and rule-state vocabulary
schemas/
  registry.schema.json
  rule_catalog.schema.json
  rule.schema.json
  voice_rule_catalog.schema.json
  voice_rule.schema.json
  batch_results.schema.json
  sample.schema.json
  card_storyboard.schema.json
scripts/
  validate_registry.py        dependency-free fail-closed validator
tests/
  test_registry.py
.github/workflows/
  validate.yml                Python-version matrix validation
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
9. Name the exact outcome domain and denominator before translating a number into prose.
10. Keep the processing method (`R###`) and article voice/register (`V###`) as separate induction layers.

## Validation

The validator uses only the Python standard library. From the repository root:

```bash
python -m unittest discover -s tests -v
python scripts/validate_registry.py
python scripts/validate_registry.py --json
```

To validate a copied or unpacked repository from elsewhere:

```bash
python scripts/validate_registry.py --root /path/to/EvidenceProse
```

Validation is fail-closed across the whole registry. It checks immutable article digests, registered-versus-present samples, rule evidence links and dates, source and artifact receipts, queue binding, storyboard summaries, batch mirrors, contamination-note ledgers, ordered indexes, and schema-document integrity. Pull requests and pushes to `main` run the same checks in GitHub Actions.

## Adding a reviewed sample

Treat an article, its interpretation record, its rule receipts, and its batch summary as one atomic change. The exact ID allocation, digest, queue-audit and promotion checklist is in [CONTRIBUTING.md](CONTRIBUTING.md).

## Scope boundary

EvidenceProse does not currently generate publication-ready articles. The first stage accumulates enough independent examples to distinguish invariant writing logic from topic-specific choices and accidental errors.
