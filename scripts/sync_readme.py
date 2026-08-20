#!/usr/bin/env python3
"""Synchronize machine-derived README blocks with validated repository data."""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_registry import ValidationError, validate  # noqa: E402


REGISTRY_STATUS_START = "<!-- BEGIN sync_readme:registry-status -->"
REGISTRY_STATUS_END = "<!-- END sync_readme:registry-status -->"
REPOSITORY_LAYOUT_START = "<!-- BEGIN sync_readme:repository-layout -->"
REPOSITORY_LAYOUT_END = "<!-- END sync_readme:repository-layout -->"

IGNORED_DIRECTORY_NAMES = frozenset({".git", "__pycache__"})

STATE_LABELS = {
    "hypothesis": ("hypothesis", "hypotheses"),
    "candidate": ("candidate", "candidates"),
    "conditional": ("conditional rule", "conditional rules"),
    "stable": ("stable rule", "stable rules"),
    "contradicted": ("contradicted rule", "contradicted rules"),
    "rejected": ("rejected rule", "rejected rules"),
}
STATE_ORDER = ("candidate", "conditional", "hypothesis", "stable", "contradicted", "rejected")


class SyncError(Exception):
    """Raised when a controlled README block cannot be synchronized safely."""


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncError(f"cannot load {path}: {exc}") from exc


def id_span(identifiers: object, label: str) -> str:
    if not isinstance(identifiers, list) or not identifiers:
        raise SyncError(f"{label} must be a non-empty array")
    if not all(isinstance(identifier, str) and identifier for identifier in identifiers):
        raise SyncError(f"{label} must contain non-empty strings")
    if len(identifiers) == 1:
        return f"`{identifiers[0]}`"
    return f"`{identifiers[0]}`–`{identifiers[-1]}`"


def status_summary(states: Counter[str]) -> str:
    parts: list[str] = []
    for state in STATE_ORDER:
        count = states[state]
        if count:
            singular, plural = STATE_LABELS[state]
            parts.append(f"{count} {singular if count == 1 else plural}")
    return ", ".join(parts)


def render_registry_status(root: Path = ROOT) -> str:
    """Render the README status lines only after the registry passes validation."""

    root = root.resolve()
    counts = validate(root)
    registry = load_json(root / "data/registry.json")
    if not isinstance(registry, dict):
        raise SyncError("data/registry.json must contain an object")

    rules_document = load_json(root / str(registry["rules_path"]))
    voice_document = load_json(root / str(registry["voice_rules_path"]))
    if not isinstance(rules_document, dict) or not isinstance(rules_document.get("rules"), list):
        raise SyncError("processing-rule catalogue must contain a rules array")
    if not isinstance(voice_document, dict) or not isinstance(voice_document.get("rules"), list):
        raise SyncError("article-register catalogue must contain a rules array")

    rule_states = Counter(rule.get("status") for rule in rules_document["rules"] if isinstance(rule, dict))
    voice_states = Counter(rule.get("status") for rule in voice_document["rules"] if isinstance(rule, dict))
    sample_span = id_span(registry.get("sample_ids"), "registry sample_ids")
    rule_span = id_span(registry.get("rule_ids"), "registry rule_ids")
    voice_span = id_span(registry.get("voice_rule_ids"), "registry voice_rule_ids")
    batch_span = id_span(registry.get("batch_ids"), "registry batch_ids")

    voice_summary = status_summary(voice_states)
    if len([count for count in voice_states.values() if count]) == 1:
        voice_summary = f"all {next(iter(voice_states.values()))} {next(iter(voice_states))} rules"
        if next(iter(voice_states)) == "hypothesis":
            voice_summary = "all hypotheses"

    content_truth_passes = counts["cards"] - counts["content_truth_failures"]
    render_fidelity_passes = counts["cards"] - counts["render_fidelity_failures"]
    lines = [
        f"- Induction samples: {counts['samples']} ({sample_span})",
        (
            f"- Processing-rule catalogue: {counts['rules']} ({rule_span}): "
            f"{status_summary(rule_states)}"
        ),
        f"- Article-register catalogue: {counts['voice_rules']} ({voice_span}), {voice_summary}",
        f"- Batch result index: {counts['batches']} ({batch_span})",
        (
            f"- Recorded observations: {counts['observations']}; "
            f"contamination notes: {counts['contamination_notes']}"
        ),
        (
            f"- Audited companion cards: {counts['cards']} "
            f"({content_truth_passes}/{counts['cards']} content-truth passes; "
            f"{render_fidelity_passes}/{counts['cards']} substantive render-fidelity passes)"
        ),
        (
            f"- Stable induction generation rules: {counts['stable_rules']}; "
            f"stable voice rules: {counts['stable_voice_rules']}"
        ),
    ]
    return "\n".join(lines)


def _layout_entries(directory: Path, relative: Path, depth: int) -> list[str]:
    """Return a stable, indented filesystem tree below ``directory``."""

    try:
        entries = [
            entry
            for entry in directory.iterdir()
            if entry.name not in IGNORED_DIRECTORY_NAMES and entry.suffix != ".pyc"
        ]
    except OSError as exc:
        raise SyncError(f"cannot inspect repository layout at {directory}: {exc}") from exc

    entries.sort(key=lambda entry: (not entry.is_dir(), entry.name))
    lines: list[str] = []
    indent = "  " * depth
    collapsed_samples = False
    for entry in entries:
        entry_relative = relative / entry.name
        is_sample = (
            relative == Path("data/samples")
            and entry.is_dir()
            and entry.name.startswith("S")
        )
        if is_sample:
            if not collapsed_samples:
                lines.append(f"{indent}S*/")
                collapsed_samples = True
            continue
        if entry.is_dir():
            lines.append(f"{indent}{entry.name}/")
            lines.extend(_layout_entries(entry, entry_relative, depth + 1))
        else:
            lines.append(f"{indent}{entry.name}")
    return lines


def render_repository_layout(root: Path = ROOT) -> str:
    """Render the checked-out repository tree without transient Python metadata."""

    root = root.resolve()
    if not root.is_dir():
        raise SyncError(f"repository root is not a directory: {root}")
    lines = _layout_entries(root, Path(), 0)
    return "```text\n" + "\n".join(lines) + "\n```"


def replace_controlled_block(text: str, start: str, end: str, body: str) -> str:
    if text.count(start) != 1 or text.count(end) != 1:
        raise SyncError(f"README must contain exactly one {start!r} / {end!r} marker pair")
    prefix, remainder = text.split(start, 1)
    current, suffix = remainder.split(end, 1)
    if not current.startswith("\n") or not current.endswith("\n"):
        raise SyncError(f"controlled block {start!r} must put its markers on separate lines")
    return f"{prefix}{start}\n{body.rstrip()}\n{end}{suffix}"


def expected_readme(root: Path = ROOT) -> str:
    readme_path = root / "README.md"
    try:
        current = readme_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SyncError(f"cannot read {readme_path}: {exc}") from exc
    with_status = replace_controlled_block(
        current,
        REGISTRY_STATUS_START,
        REGISTRY_STATUS_END,
        render_registry_status(root),
    )
    return replace_controlled_block(
        with_status,
        REPOSITORY_LAYOUT_START,
        REPOSITORY_LAYOUT_END,
        render_repository_layout(root),
    )


def check(root: Path = ROOT) -> bool:
    readme_path = root / "README.md"
    current = readme_path.read_text(encoding="utf-8")
    expected = expected_readme(root)
    if current == expected:
        return True
    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        expected.splitlines(keepends=True),
        fromfile="README.md (current)",
        tofile="README.md (expected)",
    )
    sys.stderr.writelines(diff)
    return False


def write(root: Path = ROOT) -> bool:
    readme_path = root / "README.md"
    current = readme_path.read_text(encoding="utf-8")
    expected = expected_readme(root)
    if current == expected:
        return False
    readme_path.write_text(expected, encoding="utf-8")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="fail if a controlled README block has drifted")
    mode.add_argument("--write", action="store_true", help="rewrite only controlled README blocks")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (defaults to this checkout)")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.check:
            if check(args.root):
                print("PASS: README controlled blocks are synchronized")
                return 0
            print("FAIL: README controlled blocks have drifted; run scripts/sync_readme.py --write", file=sys.stderr)
            return 1
        changed = write(args.root)
    except (OSError, KeyError, SyncError, ValidationError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print("UPDATED: README controlled blocks" if changed else "UNCHANGED: README controlled blocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
