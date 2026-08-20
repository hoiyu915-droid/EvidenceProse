# Terminology

Version labels are defined separately in [versioning.md](versioning.md); similar
numbers across contracts, policies, result schemas and artifact schemas do not
mean that those axes are interchangeable.

## Evidence layers

| Term | Meaning |
|---|---|
| Evidence fact | Directly reported or calculated result traceable to the verified source. |
| Pooled finding | Estimate produced by a synthesis across eligible independent datasets. |
| Single-study signal | Result from one included study; it must not inherit pooled authority. |
| Source-author interpretation | Interpretation explicitly made by the source authors. |
| Explainer inference | Reasoned bridge added by the explainer and visibly bounded as inference. |
| Evidence gap | Missing comparison, duration, population, measurement, or procedural definition that limits a conclusion. |
| Decision positioning | The clinical, policy, operational, or scientific action and claim boundary permitted by the total evidence. |
| Report-frequency count | The number of sources reporting a category; it may overlap across categories and is not automatically a prevalence, effect size, or importance ranking. |
| Outcome-domain specificity | The requirement to keep a supported subscale or domain result from expanding into an umbrella-outcome claim. |
| Observational unit | The entity counted in a denominator, such as participants, sessions, events, reasons, or reports. |

## Writing operations

| Term | Meaning |
|---|---|
| Decision question | A reader-facing question that reorganises source material around a clinical or scientific judgment. |
| Interpretive ceiling | The strongest conclusion that the evidence layer and design permit. |
| Paired brake | A boundary statement placed beside a favourable result to prevent overinterpretation. |
| Explanatory spine | One central tension or mechanism used to connect otherwise separate findings. |
| Source-layer preservation | Explicitly retaining whether a claim is pooled, single-study, source interpretation, or explainer inference. |
| Control-bearing limitation | A limitation that changes the conclusion, recommendation, or permitted wording. |
| Science-communication success | The primary outcome: a reasonable non-specialist can identify what is supported, its evidence weight, material limitations, applicable population/context, and the causal or practical conclusion that is not justified. |
| Reader-safe comprehension | A reader's mental model preserves the intended takeaway and rejects the forbidden takeaway without needing access to the internal checklist. |
| Artifact binding | The evidence-backed pairing of a rendered output with its canonical queue or specification to establish provenance. Binding enables audit but does not certify explanation quality. |
| Content truth | Pre-upload agreement between the proposed explainer content and the verified primary source, including facts, evidence strength, attribution, limitations, applicability, causal structure and conclusion ceiling. |
| Substantive render fidelity | Post-upload preservation of scientific meaning and reader boundaries across words and data-bearing visual relationships. Meaning-preserving paraphrase, abbreviation, restructuring and explanatory labels are allowed. |
| Engineering conformance | Adherence to queue, object, relation, citation and layout instructions. It becomes a substantive gate only when the instruction protects a named scientific or traceability interest and its violation can materially alter reader understanding. |
| Historical text comparison | The former bidirectional visible-text whitelist comparison. It may be retained for traceability, has no pass/fail status, and does not contribute to the science-communication verdict. |
| Visual data fidelity | Agreement between the source and data-bearing geometry such as point positions, trajectories, arrows, scales, colour encodings, and relative ordering. |

## Method and voice layers

| Term | Meaning |
|---|---|
| Processing method | The evidence-handling sequence used to decide what to include, how to order it, which source layer a claim belongs to, and where the interpretive ceiling lies. In the registry these are `R###` rules. |
| Article voice / register | The visible stance and sentence posture of the finished explainer: certainty calibration, attribution cues, boundary language, reader-facing density and degree of rhetorical heat. In the registry these are `V###` rules. |
| Voice rule | A descriptive hypothesis about article register. It is not a conversation persona, does not replace evidence provenance, and cannot override a study-design limitation. |
| Batch result | A compact record of one completed source-to-explainer cycle, keeping article result, processing-method finding, voice finding and companion-artifact audit separate. |

## Rule states

The canonical states are `hypothesis`, `candidate`, `conditional`, `stable`, `contradicted`, and `rejected`. Only `stable` rules may become unconditional generation requirements.
