# Rendered Card Audit v1.2

Contract: `EP_RENDERED_CARD_AUDIT v1.2`  
Method revision: `1.3-queue-diff-test-identity`

This revision keeps the v1.1 topology gate and source-surface closure, then closes four failures observed in production: a scientific-term typo that escaped semantic review, source-supported sibling text leaking into the wrong card, invented instrument/construct abbreviations, and a moderation test being drawn as a direct association. It also treats renderer-authored framing such as an added “core question” as material when it changes what the reader thinks the study tested.

## Non-negotiable rule

A rendered card must pass **four independent closures**:

1. visual-topology closure;
2. queue-surface authorization closure;
3. primary-source surface closure;
4. statistical/test-identity closure.

Source support does not authorize renderer-added content. Queue authorization does not prove source support. Correct words do not rescue wrong topology. A plausible diagram does not rescue the wrong statistical relation.

## RCA-00 — bind exact image, card and generating queue item

Bind each rendered image to the queue item that actually generated it. Do not compare an old render against a later repaired or merged queue. Record `card_id`, image hash, queue digest, item digest and source binding. Ambiguous identity is `BLOCK_UNVERIFIABLE`.

## RCA-01 — bind and inspect the primary source

Use the EvidenceProse source-binding order: DOI, exact title, then verified filename/bibliography. The primary paper is the scientific authority. For figure/table/taxonomy/ordered-process claims, inspect the source surface itself plus caption/context.

## RCA-02 — build the expected packet before seeing the render comparison

From the exact generating queue item and bound source, build four inventories:

- `authorized_surface_inventory`: every authorized reader-visible title, sentence, label, number, citation, abbreviation and scientific term for this card;
- `protected_term_inventory`: construct names, instrument names/abbreviations, outcome labels, statistical operators, source-defined categories and numbers whose corruption changes scientific meaning;
- `expected_visual_graph`: nodes, edges, direction, branch conditions, terminal states and forbidden relations;
- `expected_test_identity`: for every material statistical relation, record operands, operator, outcome, conditioning/model context and evidence state.

Allowed statistical operators include `direct_association`, `moderation_interaction`, `three_way_interaction`, `mediation`, `causal_effect`, `group_comparison`, `sequence`, `membership`, `hypothesis_only` and `author_speculation`.

A moderation term such as `attachment × SIS1 -> arousal` is not equivalent to `attachment -> SIS1`. The operands may be the same words while the tested relation is different.

## RCA-03 — blind readback and atomic freeze

Inspect the rendered image before revealing the expected packet. Freeze:

- every material visible text span, including headings, callouts, questions, footer notes and abbreviations;
- every material scientific node and icon-label pair;
- every material edge with source, target, direction, visual encoding and relation type as a reader would infer it;
- every apparent statistical/test relation;
- central research question, apparent evidence strength, causal structure, limitations and clinical/practical framing.

Do not merge several visible items into one theme. A footer sentence is still a node. A parenthetical abbreviation is still a node. A renderer-authored heading such as “核心問題” is still a node if it changes study framing.

## RCA-04 — topology + test-identity reconciliation

Perform the existing edge-by-edge topology closure, then perform test-identity closure.

For each material observed relation record:

- `observed_relation_id`;
- `observed_operands`;
- `observed_operator`;
- `observed_outcome`;
- `observed_conditioning_context`;
- matched expected relation/test id;
- disposition.

Fail when the render substitutes one test identity for another, including:

- moderation/interaction drawn as a direct association;
- three-way interaction reduced to a two-variable relation;
- association drawn as causation;
- author speculation drawn as an observed mechanism;
- a null interaction drawn as null direct associations between its component variables.

`wrong_test_identity` is a material `VISUAL_SEMANTICS` failure and normally `FAIL_RENDER` when the upstream spec is sound.

## RCA-05 — mandatory queue-surface diff

After blind freeze, compare **every observed material content node** against the exact current card’s authorized surface inventory before consulting sibling cards.

Each observed node receives one queue authorization status:

- `exact_authorized`;
- `authorized_semantic_paraphrase`;
- `not_authorized`;
- `authorization_unverifiable`.

Then classify any extra material node:

- source-supported but not authorized -> `SOURCE_SUPPORTED_BUT_NOT_QUEUE_AUTHORIZED` -> `FAIL_RENDER`, unless that exact card explicitly permits renderer-authored material;
- not authorized and not source-supported -> `UNAUTHORIZED_AND_UNSUPPORTED` -> `FAIL_RENDER`;
- authorization unverifiable -> `BLOCK_UNVERIFIABLE` when material.

**Sibling leakage rule:** content authorized on C02/C04 is not automatically authorized on C06. Topic relevance and primary-source support do not cure cross-card leakage.

**Framing rule:** renderer-added labels/questions such as “核心問題”, “臨床結論”, “治療依據” or equivalent are material whenever they change what the reader thinks the study asked, tested, established or recommends. They cannot be dismissed as harmless layout copy.

## RCA-06 — protected-term and source-surface closure

Now compare each observed node with the primary source.

Protected scientific terms are checked at token/construct level, not only broad semantic level. A typo, substitution or invented abbreviation fails when it changes or corrupts a construct, instrument, outcome or source-defined label. Examples:

- `表現失敗相關性抑制` rendered as a corrupted scientific term is `FAIL_RENDER`;
- `ECR` rendered as invented `AAS` is `FAIL_RENDER` unless the bound source and queue authorize AAS;
- a wrong number/unit/denominator/direction is material even if the surrounding sentence is broadly correct.

Ordinary orthographic variation remains editorial freedom when it does not change a protected term or reader interpretation.

Every source-supported node needs an auditable source locator. Adjacent literature cannot silently replace the bound primary source.

## RCA-07 — verdict gate

`PASS` is illegal unless all of the following are true:

- topology closure complete;
- test-identity closure complete;
- queue-surface authorization closure complete;
- source-surface closure complete;
- protected-term check complete;
- all substantive axes pass;
- no material renderer-authored framing changes the study question/evidence role;
- no sibling-card content leakage remains.

`PASS_WITH_WARNINGS` is reserved for genuinely non-material deviations.

## RCA-08 — cross-card/package sweep

After every card has an individual verdict, run a second package sweep specifically for:

- duplicated scientific text that appears on a card where it was not authorized;
- construct/abbreviation drift across cards;
- direct-association versus interaction identity drift;
- outcome drift between desire and arousal;
- citation/source-layer drift;
- limitations that migrate into the wrong card and alter its evidence role.

Cross-card duplication does not retroactively authorize a node.

## RCA-09 — repair ticket and user projection

Every `FAIL_RENDER` or `FAIL_SPEC` receives the smallest executable repair. All failed-card repair text is projected into one writing block beginning exactly with `imgedit`. Do not duplicate repair prose outside the block.

## Canonical regressions from attachment-excitation cardset

These cases are normative regression tests for this method:

1. **C03 protected-term corruption** — `表現失敗相關性抑制` rendered with a corrupted term must fail even though the intended sentence remains guessable.
2. **C05 wrong test identity** — null attachment × SES/SIS1 moderation drawn as null direct `attachment -> SES/SIS1` relations must fail. This is topology plus test-identity failure.
3. **C06 sibling leakage** — a FSFI/IIEF measurement note supported by the paper but not authorized on C06 must fail as `SOURCE_SUPPORTED_BUT_NOT_QUEUE_AUTHORIZED`.
4. **C07 invented abbreviation** — `AAS` must fail when the queue/source specify ECR and do not authorize AAS.
5. **C08 renderer-authored framing** — an added “核心問題” about diagnostic/treatment effectiveness must fail when the study did not test diagnostic accuracy or treatment efficacy, even if the card later warns that such evidence is absent.

## Validation principle

Validators can prove that the auditor completed these closures; they cannot infer pixels or scientific truth. A green validator therefore means “the required comparisons were explicitly performed and internally consistent”, not “the image is scientifically correct by automation alone”.
