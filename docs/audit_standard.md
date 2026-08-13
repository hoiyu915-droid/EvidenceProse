# Companion-card audit standard

EvidenceProse uses two independent verification layers. They answer different questions and must not be collapsed into one score.

## Layer 1: content truth (before upload)

Read the JSON-authorised card content against the verified source PDF. Check:

- numbers, units, denominators and direction;
- outcome domain, scope and population;
- uncertainty and evidence strength;
- causal versus associative wording;
- conclusion and clinical-positioning ceiling.

This layer is recorded as `content_truth_audit`.

## Layer 2: render fidelity (after upload)

Read the rendered image against the JSON specification at the level of meaning and material visual rules. The following are allowed when they preserve meaning and do not add an unsupported claim or number:

- reasonable paraphrase;
- abbreviation;
- synonymous wording;
- explanatory layout labels that do not change the evidence claim.

A card fails `render_fidelity_audit` only when one of these occurs:

1. meaning, direction, scope or uncertainty drifts;
2. a substantive claim or number is added without authorisation;
3. `main_visual.required_objects` or `required_relations` is violated;
4. a binding rule such as `citation_binding.render_policy: exact_once` is violated;
5. data-bearing geometry (point, arrow, scale, ordering or colour encoding) contradicts the authorised claim.

## Legacy literal check

The former bidirectional `visible_text` whitelist is stored as `legacy_exact_text_audit` when available. It is a diagnostic for historical comparison, not a pass/fail gate for render fidelity. A wording difference alone is never a failure under the current standard.
