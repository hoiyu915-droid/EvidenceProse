# Science explainer output format

Contract: `EP-SCIENCE-EXPLAINER-OUTPUT v0.1`

Status: delivery-shell contract. This defines how a reader-facing Traditional Chinese science explainer is packaged after its evidence content has been reviewed. It is not a generation rule and does not promote any `R###` or `V###` rule to stable status.

## Why this exists

The observed sample articles already show a recurring delivery shell, but the repository did not previously define that shell as a formal contract. As a result, otherwise accurate explainers could drift in section order, citation exposure, evidence-grade placement, filename convention, or update notation.

This contract formalises the delivery format without rewriting historical observation samples. Files under `data/samples/S###/article.md` remain immutable observations and do not need to be retrofitted to this contract.

## Canonical filename

New reader-facing delivery artifacts use:

```text
YYYYMMDD_<slug>.md
```

Rules:

- the date is the delivery date in the project timezone;
- `<slug>` uses lowercase ASCII letters, digits, and hyphens only;
- use one underscore between date and slug;
- do not put spaces, version suffixes, source filenames, or internal file IDs in the delivery filename.

Example:

```text
20260813_ai-ai-cocreation-creativity.md
```

## Canonical document order

A compliant delivery has exactly three required reader sections, followed by one evidence-grade label and one update footnote:

```markdown
# <reader-facing title>

## 一句話總結
<one paragraph that states the supported conclusion and its most important boundary>

## 內容
<reader-facing narrative; optional H3 subsections are allowed>

## 引用來源
<public, reader-resolvable bibliographic reference or references>

🟡 證據分級：中等。<why this evidence deserves this weight>

> 最後更新：YYYYMMDD
```

The required order is:

1. title;
2. `## 一句話總結`;
3. `## 內容`;
4. `## 引用來源`;
5. evidence-grade label;
6. final update footnote.

Do not create a fourth required H2 section for evidence grade. The evidence grade is a delivery label, not a parallel content section.

## One-sentence summary

`## 一句話總結` contains one paragraph. It should let a reader recover both:

- the main finding that the evidence actually supports; and
- the most important limitation, uncertainty, applicability boundary, or causal/comparative ceiling needed to prevent a predictable misuse.

A summary that contains the headline result but suppresses the limitation that changes the permitted conclusion is incomplete even when every number is technically correct.

## Content

`## 內容` is narrative-first rather than checklist-first. It may use H3 subsections when they help a reader follow the evidence, but a fixed internal subsection list is not required.

The content should preserve the source hierarchy:

- distinguish pooled findings from single-study signals;
- distinguish direct observations from author interpretation and explainer inference;
- keep task-, subgroup-, population-, setting-, and outcome-specific boundaries visible;
- make material limitations change the conclusion rather than appear as decorative caveats;
- do not convert non-significance into equality;
- do not convert association into causation;
- do not convert a comparison between complete workflows into a mechanism claim about one component unless that component was isolated.

When the primary source contains a real reporting inconsistency that matters for trust or interpretation but does not invalidate the whole result, it may be recorded under an optional H3 such as `### 內容完整性註記`. The note must describe the inconsistency and its consequence without inflating it into a broader failure.

## Reader-facing citations are separate from internal audit evidence

The internal source-audit chain and the reader-facing citation layer are different artifacts.

Internal review may use Library file IDs, source-PDF filenames, exact line references, `filecite`, queue receipts, digests, or other provenance machinery. None of those are meaningful to a reader who does not have access to the internal workspace.

A delivered explainer must therefore never expose internal-only references such as:

- `filecite` markers;
- `turnNfileM` references;
- `file_...` IDs;
- `sandbox:/...` or `/mnt/data/...` paths;
- container paths;
- bare local PDF filenames such as `2608.09023v1.pdf`.

Use the primary PDF internally to verify the prose, but strip the internal verification token from the reader artifact.

## Public citation requirements

`## 引用來源` contains reader-resolvable public bibliographic identity. Prefer, when available:

- authors;
- year;
- article title;
- journal, proceedings venue, repository, or publisher;
- DOI, PMID, PMCID, arXiv identifier, or another stable public identifier.

For a preprint, identify it as a preprint and use the stable repository identifier, for example `arXiv:2608.09023`, rather than a local filename such as `2608.09023v1.pdf`.

If no stable public locator can be verified, give the bibliographic identity that is actually supported and state that no stable public identifier was verified. Never substitute an internal filename for a public citation.

Inline author-year attribution may be used inside `## 內容` when it materially helps distinguish source layers, but the default reader experience should not be cluttered with internal line-level verification markers.

## Evidence-grade label

The delivery grade is a reader-facing summary of evidence weight. It is not automatically the same thing as a source-reported GRADE rating and must not silently borrow the authority of GRADE unless the source actually used it.

Allowed labels are:

- `🟢 證據分級：高。...`
- `🟡 證據分級：中等。...`
- `🔴 證據分級：低。...`

The rationale is mandatory and should name the factors that actually change confidence, such as study design, replication, sample size, risk of bias, precision, heterogeneity, directness, publication status, sensitivity analyses, or unresolved confounding.

The grade is not a reward for polished prose. A well-written preprint can still deserve a low or medium evidence grade.

## Final update footnote

The final non-empty line is:

```text
> 最後更新：YYYYMMDD
```

This date records the reader-facing artifact update, not the source publication date and not the date an internal PDF was uploaded.

## Structural validation versus science quality

The output-format validator checks packaging: filename, required section order, evidence-grade form, update footnote, and accidental exposure of internal citation tokens.

Passing that validator does not prove the explainer is scientifically correct. Content truth, evidence weight, applicability, causal boundaries, reader-safe comprehension, and source fidelity remain separate review gates under `docs/audit_standard.md` and `docs/induction_protocol.md`.

Conversely, a scientifically accurate draft can still fail the delivery contract if it exposes inaccessible internal citations or cannot be ingested by the downstream pipeline.
