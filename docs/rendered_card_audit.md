# Rendered Card Audit

Contract: `EP_RENDERED_CARD_AUDIT v1.0`  
Method revision: `1.1-topology-gated`

Rendered Card Audit (RCA) is the read-only post-render lane for EvidenceProse companion cards. Its question is not “did the renderer reproduce the requested words?” but **“what scientific model did the finished image make a reader see?”**

The v1.1 method revision closes a specific failure mode: a card may contain every correct term and even a correct explanatory sentence while its arrows, branch origin, grouping or terminal state communicate the opposite model. Such a card must fail.

## Non-negotiable audit rule

**Concept presence is not visual fidelity.** Seeing all expected nouns on the card is never sufficient. A material relation must be audited as a relation: source node, target node, direction, relation type, branch condition, branch parent, terminal/non-terminal behavior and path-level implication.

If any one of those materially changes the reader’s causal/evidential model, `VISUAL_SEMANTICS = fail` even if all visible prose is correct.

## Mandatory execution order

The following sequence is normative. An auditor may add notes, but may not skip, merge away or reorder a gate in a way that hides its evidence.

### RCA-00 — ingest, bind, deduplicate

Bind every rendered asset to a stable `card_id`; compute/verify SHA-256; deduplicate byte-identical images. If card identity is ambiguous, stop that card as `BLOCK_UNVERIFIABLE` rather than guessing from topic similarity.

### RCA-01 — bind and inspect literature

Bind the primary source before adjudicating source structure. Search/bind using the existing EvidenceProse source policy. When a card reproduces or paraphrases a figure, table, taxonomy, ordered process or branch model, inspect **the figure/table itself plus caption and surrounding context**. Remembered body prose is not enough.

### RCA-02 — build the expected semantic + structure packet

Record the claim ceiling, evidence strength, limitations, applicability and forbidden takeaways. Separately extract source-defined terms, closed lists, categories, order, attribution and the **expected visual graph**.

The expected graph must include, where material:

- nodes and their epistemic roles;
- allowed relations;
- branch points and branch conditions;
- terminal or deactivated states;
- relations that are explicitly forbidden;
- whether a path is causal, associative, conditional, moderating or only hypothetical.

Do not manufacture a taxonomy or graph merely because related words appear near each other in the paper.

### RCA-03 — blind render readback and freeze

Before the expected packet is revealed, inspect only the rendered image. Extract:

- all reader-visible material text/numbers/citations;
- every material node;
- every material edge with **from-node, to-node, direction, relation type, visual encoding and condition as read**;
- every apparent branch point;
- apparent terminal/non-terminal behavior;
- grouping, hierarchy, sequence, size/scale, colour and uncertainty semantics;
- the central message, apparent evidence strength and causal structure.

Freeze this observed graph and bind it by canonical JSON SHA-256. The post-comparison record must use the same digest.

### RCA-04 — topology reconciliation (mandatory edge-by-edge gate)

After the expected packet is revealed, reconcile in this order:

1. **Observed-edge closure:** every observed material edge receives exactly one disposition.
2. **Expected-relation closure:** every expected material relation receives exactly one coverage result.
3. **Source-node check:** did the arrow/line start from the scientifically correct parent?
4. **Target-node check:** did it end at the correct target?
5. **Direction check:** is direction reversible, one-way, bidirectional or unordered as supported?
6. **Relation-type check:** causal vs association vs modifier vs sequence vs membership vs gap.
7. **Condition check:** if the edge only applies under a condition, is that condition attached to the correct branch?
8. **Branch-parent check:** do alternatives branch from the correct node, or has a later success/failure state been turned into the branch parent?
9. **Terminal-state check:** if the source says a state terminates/deactivates a process, does the render improperly continue a material path from it?
10. **Path-level implication:** can individually plausible edges combine into an unsupported causal chain/taxonomy?
11. **Text–visual consistency:** does the image geometry contradict the card’s own explanatory text?

Any material `wrong_source_node`, `wrong_target_node`, `wrong_direction`, `wrong_condition`, `wrong_relation_type`, `unsupported_relation`, material omission/distortion, failed branch check, failed terminal check, or text–visual contradiction makes `VISUAL_SEMANTICS = fail`. An unresolvable material relation makes it `unverifiable`.

**Forbidden shortcut:** “the expected concepts are all present” is not a valid topology audit and must never be used to clear a card.

### RCA-05 — content + source-surface reconciliation

Only after the topology gate, check semantic-equivalence prose, numbers, evidence strength, causal ceiling, limitations, applicability, citation traceability, and source-defined terminology/list/cardinality/category/order/attribution. Wording may differ freely when meaning is preserved.

### RCA-06 — per-card verdict

- `PASS`: all substantive axes pass and mandatory topology closure is complete.
- `PASS_WITH_WARNINGS`: only non-material deviations remain.
- `FAIL_RENDER`: expected science/spec is sound, but the rendered image materially miscommunicates it.
- `FAIL_SPEC`: render is faithful to a materially wrong upstream spec/truth/source binding.
- `BLOCK_UNVERIFIABLE`: a material relation/source/identity cannot be checked without guessing.

A text-correct / arrow-wrong card is `FAIL_RENDER`, not a warning.

### RCA-07 — cross-card/package audit

Check cross-card numbers/direction, evidence role, taxonomy, scope, limitations, citation/source layer and package coverage. `cardset_audit.status` is separate from per-card verdicts.

### RCA-08 — repair ticket + human repair display

Every `FAIL_RENDER` and `FAIL_SPEC` gets an executable repair ticket using the smallest sufficient operations: `REMOVE`, `REPLACE`, `RELABEL`, `REWIRE`, `RECOMPOSE`.

Every failure also gets `human_repair_text`, regardless of whether the change is below 10%. The 10% weighted-semantic fraction only decides whether supported replacement material is mandatory; it does **not** decide whether the user gets an editable repair instruction.

A structural trigger (for example a central visual graph rewire) is substantial even below 10%. Substantial repair must include source-supported replacement material when a reader-facing content hole would otherwise remain.

## Writing-block projection — exact host format

When one or more cards are `FAIL_RENDER` / `FAIL_SPEC`, the human repair instructions are shown in **exactly one ChatGPT writing block**. The first line is exactly:

```text
imgedit
```

Then each failed card appears once, in card order:

```text
imgedit
[圖卡名稱]
修改內容

[圖卡名稱n]
修改內容
```

Rules:

- `imgedit` is the first line of the writing block, not a chat label outside it.
- `[圖卡名稱]` is the actual reader-facing card title in square brackets.
- Include only `FAIL_RENDER` and `FAIL_SPEC` cards.
- Put all failed cards in the same writing block.
- Modification wording needs semantic correctness, not verbatim source/queue wording.
- Outside the writing block, ordinary chat may report only counts/verdict/card IDs; do not duplicate the repair body.
- If there are no failed cards, do not emit an empty repair writing block.

Canonical projection template: `templates/rendered_card_audit_repair_block.txt`.

## Regression: C02 wrong branch source

For the Dewitte attachment card “威脅來時，依附系統怎麼分岔？”, the render placed outgoing hyperactivation/deactivation arrows on the “支持可得／安全感上升” node. The source model and the card’s own prose place those strategies under **persistent insecurity / unavailable or unresponsive attachment figure** instead. Security increase terminates/deactivates the attachment alarm; it is not the parent of the two insecurity strategies.

This is a canonical `FAIL_RENDER` even though the terms “過度活化”, “去活化”, “安全感上升” and the sentence “持續不安時…” are all present and individually correct. The structural regression is encoded in `tests/test_rendered_card_audit.py`. The test deliberately records `wrong_source_node` and verifies that a PASS becomes structurally illegal; the Python validator still does not claim to infer the pixels itself.

## Correlated-model risk

Blind input isolation reduces confirmation bias but does not prove model-family independence. Same-family/unknown-family risk remains material under the existing RCA policy; high-stakes material cases require secondary review before release.

## Validation

```bash
python scripts/validate_rendered_card_audit.py fixtures/valid_rendered_card_audit.json --json
python -m unittest tests/test_rendered_card_audit.py -v
```

A green validator proves closure of the declared audit record, not the scientific correctness of the auditor’s judgments. The scientific/multimodal auditor still has to perform the source and image reading; the validator prevents that judgment from being reduced to “all the words looked right.”
