# Rendered Card Audit v1.1

Contract: `EP_RENDERED_CARD_AUDIT v1.1`  
Method revision: `1.2-topology-and-source-closure`  
Status: superseded by `EP_RENDERED_CARD_AUDIT v1.2`

This revision keeps the v1.1 topology gate and closes a second failure mode: a rendered card may communicate the right overall topic while quietly adding a plausible but unsupported population, category, example, outcome, mechanism or context. That added item can look harmless because it fits the theme. It is still a scientific addition and must be source-traceable.

## Non-negotiable rule

**Concept-level correctness does not excuse node-level invention.**

For every rendered card, the auditor must freeze a blind inventory of all material reader-visible content nodes before comparing with the queue/spec or literature. A material content node includes any visible text, category, example, icon-label pair, list member, population, context, outcome, number, citation, mechanism or relationship-type that can change the scientific meaning.

After comparison, every material node must have exactly one disposition. A PASS is illegal if even one material node is missing from this closure.

## RCA-03 blind inventory

Blind readback now freezes two things:

1. the observed visual graph; and
2. the observed content-node inventory.

Each material content node gets a stable `observed_node_id`. Do not merge several visible examples into one broad theme such as “diversity examples” or “clinical options”. If the card shows seven scientific categories, record seven scientific category nodes.

This is specifically designed to catch realistic hallucinations that are semantically compatible with the topic but absent from the bound source.

## RCA-05 source-surface node closure

For each observed material node, record:

- `queue_authorization_status` — whether the final queue/spec actually authorized this concrete item;
- `primary_source_support_status` — whether the bound primary source supports this concrete item;
- `source_locators` — page/section/figure/table or other auditable locator when supported;
- `disposition`;
- `materiality`;
- linked finding when the disposition is not passing.

Passing dispositions are `AUTHORIZED_AND_SUPPORTED` and `SEMANTICALLY_EQUIVALENT_PARAPHRASE`. `NON_MATERIAL_DECORATION` is permitted only for genuinely non-scientific decoration.

Material failure rules:

- `UNAUTHORIZED_AND_UNSUPPORTED` → `SOURCE_SURFACE=fail`, normally `FAIL_RENDER`.
- `SOURCE_SUPPORTED_BUT_NOT_QUEUE_AUTHORIZED` → `FAIL_RENDER` unless the queue explicitly allowed renderer-authored examples/categories.
- `AUTHORIZED_BUT_SOURCE_UNVERIFIABLE` → `BLOCK_UNVERIFIABLE` when material.
- missing disposition for a material node → closure failure; the card cannot PASS.
- extra member in a source-defined closed set → `FAIL_RENDER`.

A broad queue statement does not license arbitrary specific examples. “More diverse samples are needed” does not authorize every plausible underserved population. Likewise, support from adjacent literature cannot silently replace the bound primary source.

## Canonical regression: plausible unsourced category

On the Dewitte 2020 card about the narrow attachment-and-sex evidence base, a renderer added **“懷孕與產後脈絡”** alongside supported categories such as sexual minority groups, different cultures/ethnicities, CNM, casual sex and broader outcome/relationship contexts.

The extra pregnancy/postpartum item is plausible in the wider attachment literature, but that is irrelevant here. If the final queue did not authorize it and Dewitte 2020 does not support it, the node must be dispositioned `UNAUTHORIZED_AND_UNSUPPORTED` and the card must be `FAIL_RENDER`.

The auditor may not clear the card by saying “the overall diversity message is correct”. That is exactly the shortcut this revision forbids.

## Execution rule

The audit sequence remains RCA-00 through RCA-08. RCA-04 topology closure and RCA-05 source-surface node closure are independent mandatory gates. Finding a topology failure early does not permit the auditor to stop checking the remaining cards or skip node-level source closure.

A per-card PASS therefore requires all of the following:

- all substantive axes pass;
- every material observed edge is dispositioned;
- every expected material relation is covered;
- every material observed content node is dispositioned;
- every source-defined closed-set member is checked;
- no material node relies on topic plausibility instead of queue authorization and primary-source support.

## Human repair output

The existing output rule remains unchanged. All `FAIL_RENDER` / `FAIL_SPEC` repairs go into one writing block beginning exactly with:

```text
imgedit
```

Outside the block, report only verdict/count/card IDs.
