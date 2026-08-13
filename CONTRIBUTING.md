# Contributing to EvidenceProse

EvidenceProse is an append-only observation registry before it is a writing system. A contribution must preserve the observed artifact, show how every induced rule traces back to it, and keep known failures visible. Perfect provenance and a green validator are still insufficient when the finished explainer leaves readers with the wrong idea about evidence weight, limitations, applicability, causality or permitted use.

## Before editing

1. Start from the current `main` branch and create a feature branch.
2. Read `docs/induction_protocol.md` and `docs/terminology.md`.
3. Allocate the next ordered `S###` and `B###` identifiers. Never reuse an identifier from a removed or rejected record.
4. Reuse an existing `R###` or `V###` only when the new observation actually tests that rule. Absence is not contradiction.

## Add one sample atomically

Search ChatGPT Library before using an uploaded scratch copy or an external fallback. Bind the existing primary article by the first successful key in this order: DOI, exact article title, then filename. Supplementary material is secondary and must not silently replace the primary paper. Use a fallback only after the primary PDF cannot be found in Library, and record that search outcome honestly.

Create `data/samples/S###/article.md` with the exact reviewed prose and `sample.json` with:

- a stable source identifier and honest verification state;
- the SHA-256 digest of the source PDF when full text was checked;
- `article_sha256`, calculated from the committed `article.md` bytes;
- a study profile whose null denominators have explicit not-applicable reasons;
- observations with precise, recoverable evidence locations;
- every suspected overclaim or technical error in `contamination_notes`.

When rendered companions are present, record the reader decision in `card_storyboard.json` under `reader_contract`: the central claim and intended takeaway, evidence weight, material limitations, applicable population/context, and causal or decision misuse boundaries. For a prose-only sample, apply the same questions during review; the current sample schema does not yet store a standalone reader contract.

Generate the article digest with:

```bash
sha256sum data/samples/S###/article.md
```

On macOS, `shasum -a 256` produces the same digest format.

If rendered cards are part of the sample, also add `card_storyboard.json`. Bind the rendered set to the canonical queue by title and content identity before auditing. Record source, canonical queue, rejected alternative queue, and rendered-cardset receipts in `artifact_receipts`. Keep these assessments separate:

- `content_truth_audit`: pre-upload comparison of the proposed explainer content against the primary source PDF, including claims, numbers, direction, evidence strength, limitations, applicability, causal structure and conclusion ceiling;
- `render_fidelity_audit`: post-upload assessment of whether the rendering preserves that scientific meaning and reader boundary. Paraphrase, abbreviation, reordering, restructuring and harmless explanatory labels are allowed;
- `audit_policy.engineering_conformance_track`: the policy for interpreting queue, object, relation and citation-binding adherence. A deviation becomes a substantive failure only when the lock protects factual accuracy, evidence weight, attribution, applicability, causal boundaries, data-bearing geometry or traceability, and the violation can alter reader understanding;
- `historical_text_comparison`: optional wording comparison retained for traceability, with no current pass/fail status or quality-gate role.

When adjudicating a lock, identify its substantive protective purpose in the audit finding or correction when one exists. The current schema records the governing policy rather than a mandatory per-lock ledger. Do not promote a typography, wording, layout or decorative mismatch into a science-communication failure merely because it differs from JSON.

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

The first two commands must exit zero. The JSON command must return `"status": "pass"`. Do not weaken a validator to make a new record pass; correct the record or document why the contract itself must change. This green result certifies registry structure, not reader comprehension or science-communication quality.

## Pull-request checklist

- [ ] The article bytes are preserved and `article_sha256` matches.
- [ ] Source verification and artifact receipts are honest and complete.
- [ ] Observation, contamination, rule, voice, and batch ledgers agree.
- [ ] A reader review confirms the intended evidence weight, limitations, applicability and causal/decision boundaries, including the forbidden takeaway.
- [ ] Content-truth and substantive render-fidelity failures remain visible; engineering-only deviations are not presented as science-communication failures.
- [ ] Any historical text comparison is clearly non-gating and has no pass/fail status.
- [ ] No rule was promoted without satisfying the documented gate.
- [ ] Unit tests and the fail-closed validator pass.
