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

REQUIRED_H2 = ("## 一句話總結", "## 內容", "## 引用來源")
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


def validate_text(text: str, *, filename: str) -> list[str]:
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

    for label, pattern in INTERNAL_REFERENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            errors.append(
                f"reader artifact exposes {label} at line {_line_number(text, match.start())}"
            )

    for match in LOCAL_PDF_RE.finditer(text):
        if not _looks_like_public_url_token(text, match.start(), match.end()):
            errors.append(
                "reader artifact exposes a bare/local PDF filename "
                f"{match.group(0)!r} at line {_line_number(text, match.start())}; "
                "use a public bibliographic identifier instead"
            )
            break

    return errors


def validate_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"cannot read file: {exc}"]
    return validate_text(text, filename=path.name)


def _iter_paths(values: Iterable[str]) -> list[Path]:
    return [Path(value) for value in values]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate EvidenceProse reader-facing explainer delivery format"
    )
    parser.add_argument("paths", nargs="+", help="Markdown delivery artifact(s) to validate")
    parser.add_argument("--json", action="store_true", help="emit machine-readable result")
    args = parser.parse_args(argv)

    reports = []
    for path in _iter_paths(args.paths):
        errors = validate_file(path)
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
