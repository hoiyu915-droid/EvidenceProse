# Contributing to EvidenceProse

EvidenceProse is an append-only observation registry before it is a writing system. A contribution must preserve the observed artifact, show how every induced rule traces back to it, and keep known failures visible. Perfect provenance and a green validator are still insufficient when the finished explainer leaves readers with the wrong idea about evidence weight, limitations, applicability, causality or permitted use.

## Before editing

1. Start from the current `main` branch and create a feature branch.
2. Read `docs/induction_protocol.md` and `docs/terminology.md`. If the change adds or validates a reader-facing delivery artifact, also read `docs/science_explainer_output_format.md`.
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

## Reader-facing delivery artifacts

Historical sample articles are evidence observations. Do not rewrite `data/samples/S###/article.md` merely to make an old sample match the current delivery shell.

For a new reader-facing science explainer delivery artifact:

1. Start from `templates/science_explainer.md`.
2. Name the file `YYYYMMDD_<lowercase-kebab-slug>.md`.
3. Keep the three H2 sections exactly and in order: `## 一句話總結`, `## 內容`, `## 引用來源`.
4. Put the evidence grade after the public references as a label, not a fourth H2 section: `🟢/🟡/🔴 證據分級：高/中等/低。<rationale>`.
5. Make `> 最後更新：YYYYMMDD` the final non-empty line.
6. Keep internal source-audit evidence out of the reader artifact. `filecite`, `turnNfileM`, `file_...`, Library/file IDs, queue receipts, sandbox/container paths and bare local PDF filenames are internal provenance, not public citations.
7. Use reader-resolvable bibliographic identity in `## 引用來源`: authors, year, title, venue/repository, and DOI/PMID/PMCID/arXiv or another stable public identifier when verified.
8. If the source contains a real reporting inconsistency that matters to interpretation, it may be described under an optional `### 內容完整性註記`; state what is inconsistent and what it does or does not invalidate.

The source PDF remains the authority for content-truth review even though its internal workspace filename must not appear in the delivered prose.

## Validate

Run the registry checks from the repository root:

```bash
python -m unittest discover -s tests -v
python scripts/validate_registry.py
python scripts/validate_registry.py --json
```

When a reader-facing delivery artifact is part of the change, also run:

```bash
python scripts/validate_explainer_output.py YYYYMMDD_<slug>.md
python scripts/validate_explainer_output.py --json YYYYMMDD_<slug>.md
```

The first two registry commands must exit zero. The registry JSON command must return `"status": "pass"`. The explainer-output validator must also exit zero for every new delivery artifact. Do not weaken a validator to make a new record pass; correct the record or document why the contract itself must change. Green structural validation certifies packaging and registry consistency, not reader comprehension or science-communication quality.

## Change the RCA policy

The current manifest `policies/rca/current.json` is authoritative for the active versioned policy path, policy version and digest. For a policy-only Rendered Card Audit rule change, edit the versioned policy JSON selected by that manifest, update its explicit status/disposition mappings and `tests/test_rca_policy.py` cases, then run:

```bash
python3 scripts/validate_rca_policy.py --sync-surfaces
python3 -m unittest tests/test_rca_policy.py -v
```

`--sync-surfaces` updates the current manifest digest/version, active contract/fixture policy mirrors, active schema policy-version constant and active contract policy path atomically, then validates the policy and surfaces. It refuses `policy_id`, `contract_version`, `result_schema_version` or `method_revision` changes; those are structural, method or contract migrations and must be updated manually with their schema/contract/docs/fixture changes. Raise `policy_version` for a decision-rule change, `result_schema_version` for a result-shape change, and `contract_version` only for an external contract change. Mark older contract snapshots superseded; do not silently edit their historical policy.

## Pull-request checklist

- [ ] The article bytes are preserved and `article_sha256` matches.
- [ ] Source verification and artifact receipts are honest and complete.
- [ ] Observation, contamination, rule, voice, and batch ledgers agree.
- [ ] A reader review confirms the intended evidence weight, limitations, applicability and causal/decision boundaries, including the forbidden takeaway.
- [ ] Content-truth and substantive render-fidelity failures remain visible; engineering-only deviations are not presented as science-communication failures.
- [ ] Any historical text comparison is clearly non-gating and has no pass/fail status.
- [ ] If a reader-facing delivery artifact is included, its public citation layer contains no inaccessible internal provenance tokens and `validate_explainer_output.py` passes.
- [ ] No rule was promoted without satisfying the documented gate.
- [ ] Unit tests and the fail-closed validator pass.
