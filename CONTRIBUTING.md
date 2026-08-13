# Contributing to EvidenceProse

EvidenceProse is an append-only observation registry before it is a writing system. A contribution must preserve the observed artifact, show how every induced rule traces back to it, and keep known failures visible.

## Before editing

1. Start from the current `main` branch and create a feature branch.
2. Read `docs/induction_protocol.md` and `docs/terminology.md`.
3. Allocate the next ordered `S###` and `B###` identifiers. Never reuse an identifier from a removed or rejected record.
4. Reuse an existing `R###` or `V###` only when the new observation actually tests that rule. Absence is not contradiction.

## Add one sample atomically

Create `data/samples/S###/article.md` with the exact reviewed prose and `sample.json` with:

- a stable source identifier and honest verification state;
- the SHA-256 digest of the source PDF when full text was checked;
- `article_sha256`, calculated from the committed `article.md` bytes;
- a study profile whose null denominators have explicit not-applicable reasons;
- observations with precise, recoverable evidence locations;
- every suspected overclaim or technical error in `contamination_notes`.

Generate the article digest with:

```bash
sha256sum data/samples/S###/article.md
```

On macOS, `shasum -a 256` produces the same digest format.

If rendered cards are part of the sample, also add `card_storyboard.json`. Bind the rendered set to the canonical queue by title and content identity before auditing. Record source, canonical queue, rejected alternative queue, and rendered-cardset receipts in `artifact_receipts`. Keep these verdicts separate:

- `content_truth_audit`: pre-upload comparison of claims, numbers, direction, scope, uncertainty, causal structure and conclusion wording against the source PDF;
- `render_fidelity_audit`: post-upload comparison of the rendered card with the JSON specification. Meaning-preserving paraphrase, abbreviation and synonymous wording pass; material claim/number additions, required visual-relation violations and citation-binding violations fail;
- `legacy_exact_text_audit`: optional historical literal-text diagnostic, retained for traceability but not used as the render-fidelity gate.

## Update the ledgers

In the same change:

1. Add the sample and batch IDs to `data/registry.json` in order.
2. Add the batch mirror to `data/batch_results.json`, including all contamination-note IDs and exact storyboard counts.
3. Add support, qualification, or counterexample receipts to method rules in `data/rules/rules.json`.
4. Update article-register evidence separately in `data/voice/voice_rules.json`.
5. Set catalogue and rule `last_updated` dates no earlier than the newest evidence they reference.
6. Update `docs/batch_results.md` and README status counts when the cumulative totals change.

Do not promote a rule merely because several samples share wording. The promotion gate in `docs/induction_protocol.md` still requires independent support, resolved counterexamples, held-out reconstruction, representable inputs, and an auditable output.

## Validate

Run all three commands from the repository root:

```bash
python -m unittest discover -s tests -v
python scripts/validate_registry.py
python scripts/validate_registry.py --json
```

The first two commands must exit zero. The JSON command must return `"status": "pass"`. Do not weaken a validator to make a new record pass; correct the record or document why the contract itself must change.

## Pull-request checklist

- [ ] The article bytes are preserved and `article_sha256` matches.
- [ ] Source verification and artifact receipts are honest and complete.
- [ ] Observation, contamination, rule, voice, and batch ledgers agree.
- [ ] Content-truth and render-fidelity failures remain visible; any legacy literal-text diagnostic is clearly non-gating.
- [ ] No rule was promoted without satisfying the documented gate.
- [ ] Unit tests and the fail-closed validator pass.
