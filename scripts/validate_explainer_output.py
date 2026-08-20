#!/usr/bin/env python3
"""Validate reader-facing EvidenceProse science-explainer delivery artifacts.

This validator checks the delivery shell only. It does not certify content truth,
evidence quality, applicability, causal boundaries, or reader comprehension.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable


FILENAME_RE = re.compile(r"^\d{8}_[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
UPDATE_RE = re.compile(r"^> 最後更新：(\d{8})$")
GRADE_RE = re.compile(r"^(🟢|🟡|🔴) 證據分級：(高|中等|低)。(.+)$")
GRADE_EMOJI = {"高": "🟢", "中等": "🟡", "低": "🔴"}
LOCAL_PDF_RE = re.compile(r"\b[A-Za-z0-9_.()\-]+\.pdf\b", re.IGNORECASE)
LATIN_SPAN_RE = re.compile(
    r"(?<![A-Za-zÀ-ÖØ-öø-ÿ0-9])"
    r"(?P<term>[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ0-9]*"
    r"(?:[-'][A-Za-zÀ-ÖØ-öø-ÿ0-9]+)*"
    r"(?:[ \t]+[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ0-9]*"
    r"(?:[-'][A-Za-zÀ-ÖØ-öø-ÿ0-9]+)*)*)"
    r"(?![A-Za-zÀ-ÖØ-öø-ÿ0-9])"
)
HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
PUBLIC_IDENTIFIER_TERMS = frozenset(
    {"DOI", "PMID", "PMCID", "ORCID", "arXiv"}
)
MEASUREMENT_UNITS = frozenset(
    {
        "g", "kg", "mg", "mL", "L", "mm", "cm", "m", "km",
        "ms", "s", "min", "h", "Hz", "J", "kJ", "kcal",
    }
)

REQUIRED_H2 = ("## 一句話總結", "## 內容", "## 引用來源")
DEFAULT_CONTENT_MAX_CHARACTERS = 4000
INTERNAL_REFERENCE_PATTERNS = (
    ("filecite marker", re.compile(r"filecite", re.IGNORECASE)),
    ("turn/file reference", re.compile(r"\bturn\d+file\d+\b", re.IGNORECASE)),
    ("internal file id", re.compile(r"\bfile_[0-9a-z]+\b", re.IGNORECASE)),
    ("sandbox path", re.compile(r"sandbox:/", re.IGNORECASE)),
    ("container path", re.compile(r"/mnt/data/", re.IGNORECASE)),
    ("internal library file id", re.compile(r"\blibrary_file_id\b", re.IGNORECASE)),
)


def _nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _looks_like_public_url_token(text: str, start: int, end: int) -> bool:
    line_start = text.rfind("\n", 0, start) + 1
    before = text[line_start:start]
    token_start = max(before.rfind(" "), before.rfind("\t")) + 1
    token = before[token_start:] + text[start:end]
    return token.startswith("https://") or token.startswith("http://")


def _non_whitespace_character_count(text: str) -> int:
    return sum(1 for character in text if not character.isspace())


def internal_marker_errors(text: str) -> list[str]:
    """Return reader-facing internal-reference leaks found in ``text``."""
    errors: list[str] = []
    for label, pattern in INTERNAL_REFERENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            errors.append(
                f"reader artifact exposes {label} at line {_line_number(text, match.start())}"
            )
    return errors


def _mask_preserving_newlines(value: str) -> str:
    return "".join("\n" if character == "\n" else " " for character in value)


def _reader_language_surface(text: str) -> str:
    """Mask citations and code while retaining reader-prose line offsets."""
    lines: list[str] = []
    inside_references = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == "> 最後更新：YYYYMMDD":
            lines.append(_mask_preserving_newlines(line))
            continue
        if stripped == "## 引用來源":
            inside_references = True
            lines.append(line)
            continue
        if inside_references and GRADE_RE.fullmatch(stripped):
            inside_references = False
        if inside_references:
            lines.append(_mask_preserving_newlines(line))
        else:
            lines.append(line)

    surface = "".join(lines)
    for pattern in (
        re.compile(r"```.*?```", re.DOTALL),
        re.compile(r"~~~.*?~~~", re.DOTALL),
        re.compile(r"`[^`\n]+`"),
        re.compile(r"https?://[^\s)>）]+", re.IGNORECASE),
    ):
        surface = pattern.sub(
            lambda match: _mask_preserving_newlines(match.group(0)),
            surface,
        )
    return surface


def _has_immediate_chinese_gloss(text: str, end: int) -> bool:
    if end >= len(text) or text[end] not in "(（":
        return False
    closing = ")" if text[end] == "(" else "）"
    close_index = text.find(closing, end + 1)
    if close_index == -1:
        return False
    return HAN_RE.search(text[end + 1 : close_index]) is not None


def _is_exempt_latin_span(text: str, match: re.Match[str]) -> bool:
    term = match.group("term")
    if term in PUBLIC_IDENTIFIER_TERMS:
        return True

    compact_words = term.split()
    if len(compact_words) == 1:
        token = compact_words[0]
        before = text[: match.start()].rstrip()
        after = text[match.end() :]
        if token in MEASUREMENT_UNITS and before:
            if before[-1].isdigit():
                return True
            if before[-1] in "/·" and any(
                character.isdigit() for character in before[-16:]
            ):
                return True
        if len(token) == 1 and re.match(r"\s*(?:[=<>≤≥]|[（(]?[0-9.])", after):
            return True

    looks_like_name = any(character.isupper() for character in term)
    if looks_like_name and re.match(
        r"\s*(?:等人|等|[（(]\d{4}[）)]|[，,]?\s*\d{4})",
        text[match.end() :],
    ):
        return True
    return False


def english_gloss_errors(text: str) -> list[str]:
    """Reject unglossed English in reader prose.

    English lexical spans must be followed immediately by a Chinese gloss, for
    example ``self-report(自陳)``. Bibliographic entries, URLs, code, public
    identifier labels, author-year attributions, statistical symbols, and
    number-bound measurement units are outside this reader-language rule.
    """
    surface = _reader_language_surface(text)
    errors: list[str] = []
    for match in LATIN_SPAN_RE.finditer(surface):
        if _is_exempt_latin_span(surface, match):
            continue
        if _has_immediate_chinese_gloss(surface, match.end()):
            continue
        errors.append(
            "reader-facing English requires an immediate Chinese gloss "
            f"at line {_line_number(surface, match.start())}: "
            f"{match.group('term')!r}; use English(中文)"
        )
    return errors


def validate_text(
    text: str,
    *,
    filename: str,
    allow_large_literature: bool = False,
    length_exception_reason: str | None = None,
    require_english_gloss: bool = True,
) -> list[str]:
    errors: list[str] = []

    if not FILENAME_RE.fullmatch(filename):
        errors.append(
            "filename must match YYYYMMDD_<lowercase-kebab-slug>.md"
        )

    lines = text.splitlines()
    nonempty = _nonempty_lines(text)
    if not nonempty:
        return errors + ["document is empty"]

    if not nonempty[0].startswith("# ") or nonempty[0].startswith("## "):
        errors.append("first non-empty line must be exactly one H1 reader-facing title")

    h1_lines = [line for line in lines if line.startswith("# ")]
    if len(h1_lines) != 1:
        errors.append("document must contain exactly one H1 title")

    h2_lines = [line.strip() for line in lines if line.startswith("## ")]
    if h2_lines != list(REQUIRED_H2):
        errors.append(
            "H2 sections must be exactly and in order: " + " -> ".join(REQUIRED_H2)
        )

    positions: dict[str, int] = {}
    for heading in REQUIRED_H2:
        occurrences = [i for i, line in enumerate(lines) if line.strip() == heading]
        if len(occurrences) != 1:
            errors.append(f"{heading} must appear exactly once")
        elif occurrences:
            positions[heading] = occurrences[0]

    if all(heading in positions for heading in REQUIRED_H2):
        summary_start = positions["## 一句話總結"] + 1
        content_start = positions["## 內容"]
        refs_start = positions["## 引用來源"]

        summary_lines = lines[summary_start:content_start]
        summary_text = "\n".join(summary_lines).strip()
        if not summary_text:
            errors.append("一句話總結 must not be empty")
        else:
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", summary_text) if p.strip()]
            if len(paragraphs) != 1:
                errors.append("一句話總結 must contain exactly one paragraph")
            if any(line.lstrip().startswith("#") for line in summary_lines):
                errors.append("一句話總結 must not contain nested headings")

        content_text = "\n".join(lines[content_start + 1 : refs_start]).strip()
        if not content_text:
            errors.append("內容 must not be empty")
        else:
            content_character_count = _non_whitespace_character_count(content_text)
            if content_character_count > DEFAULT_CONTENT_MAX_CHARACTERS:
                if not allow_large_literature:
                    errors.append(
                        "內容 exceeds the default 4000-character ceiling: "
                        f"{content_character_count} non-whitespace Unicode code points"
                    )
                elif (
                    not isinstance(length_exception_reason, str)
                    or not length_exception_reason.strip()
                ):
                    errors.append(
                        "large-literature length exception requires a non-empty reason"
                    )
            elif allow_large_literature:
                errors.append(
                    "large-literature length exception is unnecessary when 內容 is at or below "
                    "4000 characters"
                )

    grade_matches: list[tuple[int, re.Match[str]]] = []
    for index, line in enumerate(lines):
        match = GRADE_RE.fullmatch(line.strip())
        if match:
            grade_matches.append((index, match))

    if len(grade_matches) != 1:
        errors.append(
            "document must contain exactly one evidence-grade label in the form "
            "🟢/🟡/🔴 證據分級：高/中等/低。<rationale>"
        )
        grade_index = None
    else:
        grade_index, match = grade_matches[0]
        emoji, grade, rationale = match.groups()
        if GRADE_EMOJI[grade] != emoji:
            errors.append(f"evidence-grade emoji does not match grade {grade}")
        if not rationale.strip():
            errors.append("evidence-grade rationale must not be empty")

    update_matches = [
        (index, UPDATE_RE.fullmatch(line.strip()))
        for index, line in enumerate(lines)
        if UPDATE_RE.fullmatch(line.strip())
    ]
    if len(update_matches) != 1:
        errors.append("document must contain exactly one > 最後更新：YYYYMMDD footnote")
        update_index = None
    else:
        update_index, _ = update_matches[0]
        if nonempty[-1] != lines[update_index].strip():
            errors.append("最後更新 footnote must be the final non-empty line")

    if "## 引用來源" in positions and grade_index is not None:
        refs_heading_index = positions["## 引用來源"]
        if grade_index <= refs_heading_index:
            errors.append("evidence-grade label must appear after 引用來源")
        else:
            refs_text = "\n".join(lines[refs_heading_index + 1 : grade_index]).strip()
            if not refs_text:
                errors.append("引用來源 must contain at least one public bibliographic reference")

    if grade_index is not None and update_index is not None and update_index <= grade_index:
        errors.append("最後更新 footnote must appear after the evidence-grade label")

    errors.extend(internal_marker_errors(text))
    if require_english_gloss:
        errors.extend(english_gloss_errors(text))

    for match in LOCAL_PDF_RE.finditer(text):
        if not _looks_like_public_url_token(text, match.start(), match.end()):
            errors.append(
                "reader artifact exposes a bare/local PDF filename "
                f"{match.group(0)!r} at line {_line_number(text, match.start())}; "
                "use a public bibliographic identifier instead"
            )
            break

    return errors


def validate_file(
    path: Path,
    *,
    allow_large_literature: bool = False,
    length_exception_reason: str | None = None,
    require_english_gloss: bool = True,
) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"cannot read file: {exc}"]
    return validate_text(
        text,
        filename=path.name,
        allow_large_literature=allow_large_literature,
        length_exception_reason=length_exception_reason,
        require_english_gloss=require_english_gloss,
    )


def _iter_paths(values: Iterable[str]) -> list[Path]:
    return [Path(value) for value in values]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate EvidenceProse reader-facing explainer delivery format"
    )
    parser.add_argument("paths", nargs="+", help="Markdown delivery artifact(s) to validate")
    parser.add_argument("--json", action="store_true", help="emit machine-readable result")
    parser.add_argument(
        "--allow-large-literature",
        action="store_true",
        help="allow ## 內容 to exceed 4000 characters for a genuinely large literature base",
    )
    parser.add_argument(
        "--length-exception-reason",
        help="non-empty justification required with --allow-large-literature",
    )
    args = parser.parse_args(argv)

    if args.allow_large_literature and len(args.paths) > 1:
        parser.error("--allow-large-literature accepts exactly one path per invocation")
    if args.length_exception_reason and not args.allow_large_literature:
        parser.error("--length-exception-reason requires --allow-large-literature")

    reports = []
    for path in _iter_paths(args.paths):
        errors = validate_file(
            path,
            allow_large_literature=args.allow_large_literature,
            length_exception_reason=args.length_exception_reason,
        )
        reports.append(
            {
                "path": str(path),
                "status": "pass" if not errors else "fail",
                "errors": errors,
            }
        )

    ok = all(report["status"] == "pass" for report in reports)
    if args.json:
        json.dump(
            {"status": "pass" if ok else "fail", "files": reports},
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        for report in reports:
            print(f"{report['status'].upper()}: {report['path']}")
            for error in report["errors"]:
                print(f"  - {error}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
