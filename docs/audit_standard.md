# Science-explainer and companion-card audit standard

EvidenceProse treats science-communication success as the highest criterion. A successful explainer lets a reasonable non-specialist recover five things without being misled:

1. what the evidence actually supports;
2. how much confidence that support deserves;
3. the material limitations and uncertainty;
4. the population and context to which it applies;
5. the causal, comparative and practical conclusions it does not justify.

Source agreement, JSON conformance and registry validation are necessary controls for different parts of the workflow, but none is sufficient proof of communication quality. The two verification layers below must remain separate.

## Source discovery and binding

Before either layer, search ChatGPT Library for the existing primary article and bind it by the first successful key:

1. DOI;
2. exact article title;
3. filename.

Search supplementary material only after the primary article and never substitute it silently for the main paper. Use an uploaded scratch copy or another fallback only when the primary PDF cannot be located in Library; record the failed Library search, the fallback identity and its verification state.

## Workflow stages: audit/edit versus execution/seal

Content review and integrity sealing are separate stages. Treat the canonical storyboard as editable working content until the review is finished; treat digests, receipts and attestations as sealing metadata that becomes gating only when the artifact is prepared for execution, handoff or archival.

### Audit/edit stage

When a content-truth review finds a substantive wording or visual problem, correct the canonical JSON content directly. Do not stop at a `required_correction`, review comment or violation string while leaving the canonical content wrong.

Content-bearing fields include the current storyboard fields `title`, `visible_text`, `allowed_visible_numbers`, `main_visual_scene` and `reader_contract`. If a richer downstream contract also carries the same meaning in `main_visual`, `required_relations`, `scene`, `prompt`, `canonical_text` or another semantic mirror, update every mirror that actually exists in that contract in the same audit correction. Do not invent absent schema fields merely to satisfy this rule.

Pure integrity metadata is not part of an audit correction. Do not recompute or rewrite `*_sha256`, `*_digest`, queue/renderer/imagegen digests, attestation digests, prompt character counts, artifact receipts, or `data/integrity_seals.json` while content is still being edited.

Use:

```bash
python scripts/integrity_stage.py --stage audit --json
```

The audit validator checks JSON syntax and the registry's substantive structural/semantic contracts on a temporary shadow copy. Pure integrity metadata is normalized only inside that disposable shadow so a stale digest or stale queue binding cannot block a content correction. The working tree is not resealed.

`scripts/card_audit_edit.py` is the canonical helper for machine-applied corrections. It requires a content patch, permits audit annotations only alongside a real content edit, and refuses any mutation of integrity keys.

Example:

```bash
python scripts/card_audit_edit.py data/samples/S999/card_storyboard.json \
  --card C03 \
  --content-json '{"visible_text":["兩種 AI-AI 差異未達統計顯著，不代表數值相等"]}'
```

A correction of this kind must not trigger queue recompilation or resealing merely because a few characters changed.

### Execution/seal stage

Only after content is stable should the workflow refresh sealing metadata and run the final integrity gate. For the repository-local storyboard seal, use:

```bash
python scripts/integrity_stage.py --stage seal --reseal-storyboards --json
```

Then run the seal gate without mutation:

```bash
python scripts/integrity_stage.py --stage seal --json
```

The seal stage still runs the original fail-closed registry validator. Queue, image and other external artifact digests are not fabricated by EvidenceProse when the corresponding artifact bytes are absent from the repository; execution/handoff must supply or recompute those authoritative digests before the final gate can pass. Moving the gate later must never mean weakening it.

`data/integrity_seals.json` is deliberately separate from the canonical storyboard content. It records the Git blob identity of each sealed storyboard. An audit edit may leave this ledger stale. Seal validation must fail until an explicit reseal refreshes it.

## Layer 1: content truth (before upload)

Read the proposed article or card content against the bound primary PDF. The JSON queue may record editorial intent, but it is not the scientific authority. Check:

- numbers, units, denominators and direction;
- outcome domain, evidence layer and attribution;
- study design, evidence strength and robustness hierarchy;
- material limitations and uncertainty;
- population, setting, duration and other applicability boundaries;
- causal versus associative wording;
- comparative, clinical and decision-positioning ceiling;
- intended takeaway and forbidden takeaway, including important omissions that would change either one.

This layer is recorded as `content_truth_audit`. A card does not pass merely because every listed sentence appears in the source: it fails when the selection, omission, emphasis or framing gives the reader a materially wrong evidence model.

If the audit finds a correctable defect in canonical content, the audit result and the canonical content must converge in the same audit/edit stage. A failure record may remain temporarily while a correction is being prepared, but the workflow must not treat a review comment as a substitute for correcting the content object that will actually be rendered.

## Layer 2: substantive render fidelity (after upload)

Read the rendered artifact as a reader would. Decide whether its words and visual relationships preserve the content-truth judgment and communicate the intended evidence boundary. The following are editorial freedom when they preserve meaning:

- reasonable paraphrase, abbreviation and synonymous wording;
- splitting, merging, reordering or shortening sentences;
- explanatory headings, labels and layout structure;
- decorative elements and non-data-bearing geometry.

A card fails `render_fidelity_audit` only when the rendering can materially change reader understanding, for example when it:

1. changes meaning, direction, magnitude, scope, evidence strength or uncertainty;
2. adds an unsupported empirical claim or a number presented as evidence;
3. promotes an inference into a finding, loses attribution, or changes pooled evidence into a subgroup or single-study claim;
4. expands applicability or implies causation, equivalence, superiority, safety or clinical action beyond the source;
5. uses data-bearing geometry—point position, arrow, scale, ordering, size or colour—to contradict or exaggerate the evidence;
6. breaks source traceability in a way that prevents the claim from being checked.

## Engineering conformance

Queue identity, `main_visual.required_objects`, `required_relations`, `citation_binding.render_policy`, layout instructions and similar JSON locks are interpreted through `audit_policy.engineering_conformance_track`, separately from the scientific verdict. A lock becomes a science-communication gate only when both conditions are met:

1. it has an explicit protective purpose tied to factual accuracy, evidence weight, attribution, applicability, causal boundaries, data-bearing geometry or source traceability; and
2. violating it is sufficient to materially change reader understanding or prevent verification.

Record the protective purpose in the relevant finding or correction when it is material; the current schema does not require a separate per-lock ledger. Otherwise the deviation is an engineering warning, not a quality failure. `render_policy: exact_once`, for example, is substantive when it prevents a citation from being omitted or misbound; it is not automatically substantive merely because a harmless duplicate or placement difference exists. Passing every engineering lock does not prove that the explainer is accurate, calibrated or useful.

Engineering conformance must also respect the stage boundary above: a stale seal is an execution-integrity defect, not a reason to prevent an editor from correcting a scientifically wrong sentence.

## Historical text comparison

The former bidirectional `visible_text` whitelist may be retained as `historical_text_comparison`. It records only `equivalent` or `wording_divergence`, has no pass/fail status, and contributes nothing to the current science-communication verdict. Wording differences are not defects by themselves.
