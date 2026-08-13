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

Queue identity, `main_visual.required_objects`, `required_relations`, `citation_binding.render_policy`, layout instructions and similar JSON locks are recorded separately as engineering conformance. A lock becomes a science-communication gate only when both conditions are met:

1. it has an explicit protective purpose tied to factual accuracy, evidence weight, attribution, applicability, causal boundaries, data-bearing geometry or source traceability; and
2. violating it is sufficient to materially change reader understanding or prevent verification.

Otherwise the deviation is an engineering warning, not a quality failure. `render_policy: exact_once`, for example, is substantive when it prevents a citation from being omitted or misbound; it is not automatically substantive merely because a harmless duplicate or placement difference exists. Passing every engineering lock does not prove that the explainer is accurate, calibrated or useful.

## Historical text comparison

The former bidirectional `visible_text` whitelist may be retained as `historical_text_comparison`. It records only `equivalent` or `wording_divergence`, has no pass/fail status, and contributes nothing to the current science-communication verdict. Wording differences are not defects by themselves.
