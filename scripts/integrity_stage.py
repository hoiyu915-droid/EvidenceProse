#!/usr/bin/env python3
"""Separate audit/edit validation from explicit seal/execution integrity gates.

`audit` validates the registry on a temporary shadow copy whose *pure integrity*
metadata is normalized only inside the shadow. The working tree is never resealed
and stale digests therefore cannot block an editorial correction.

`seal` runs the original fail-closed registry validator against the real tree and
also verifies the independent storyboard seal ledger. `--reseal-storyboards` is
an explicit sealing action and is intentionally unavailable in audit mode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable

try:  # Script execution: python scripts/integrity_stage.py
    from validate_registry import ValidationError, validate as validate_registry
except ImportError:  # Test/module import: from scripts.integrity_stage import ...
    from scripts.validate_registry import ValidationError, validate as validate_registry


ROOT = Path(__file__).resolve().parents[1]
SEAL_LEDGER = Path("data/integrity_seals.json")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
GIT_BLOB_SHA1 = re.compile(r"^[a-f0-9]{40}$")


class IntegrityStageError(Exception):
    """Raised when a stage contract or integrity seal is invalid."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityStageError(f"cannot load {path}: {exc}") from exc


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_sha1(path: Path) -> str:
    """Return the Git blob object id for the file's exact current bytes."""

    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()  # noqa: S324 -- Git object identity


def _registry_storyboards(root: Path) -> dict[str, Path]:
    registry = _load_json(root / "data/registry.json")
    if not isinstance(registry, dict) or not isinstance(registry.get("sample_ids"), list):
        raise IntegrityStageError("registry sample_ids are unavailable")
    result: dict[str, Path] = {}
    for sample_id in registry["sample_ids"]:
        if not isinstance(sample_id, str):
            raise IntegrityStageError("registry contains a non-string sample id")
        sample_path = root / f"data/samples/{sample_id}/sample.json"
        sample = _load_json(sample_path)
        if not isinstance(sample, dict):
            raise IntegrityStageError(f"{sample_id} sample must be an object")
        storyboard_path = sample.get("card_storyboard_path")
        if storyboard_path is None:
            continue
        if not isinstance(storyboard_path, str) or not storyboard_path.strip():
            raise IntegrityStageError(f"{sample_id} card_storyboard_path is invalid")
        path = (root / storyboard_path).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError as exc:
            raise IntegrityStageError(f"{sample_id} storyboard escapes repository") from exc
        if not path.is_file():
            raise IntegrityStageError(f"{sample_id} storyboard is missing: {storyboard_path}")
        result[sample_id] = path
    return result


def build_storyboard_seal_ledger(root: Path) -> dict[str, Any]:
    root = root.resolve()
    entries = []
    for sample_id, path in sorted(_registry_storyboards(root).items()):
        entries.append(
            {
                "sample_id": sample_id,
                "path": path.relative_to(root).as_posix(),
                "git_blob_sha1": git_blob_sha1(path),
            }
        )
    return {
        "schema_version": "1.0",
        "algorithm": "git-blob-sha1",
        "storyboards": entries,
    }


def reseal_storyboards(root: Path = ROOT) -> dict[str, Any]:
    """Explicitly refresh only the repository-local storyboard seal ledger."""

    root = root.resolve()
    ledger = build_storyboard_seal_ledger(root)
    _write_json(root / SEAL_LEDGER, ledger)
    return ledger


def check_storyboard_seals(root: Path = ROOT) -> None:
    root = root.resolve()
    seal_path = root / SEAL_LEDGER
    if not seal_path.is_file():
        raise IntegrityStageError(f"seal ledger is missing: {SEAL_LEDGER.as_posix()}")
    ledger = _load_json(seal_path)
    if not isinstance(ledger, dict) or set(ledger) != {"schema_version", "algorithm", "storyboards"}:
        raise IntegrityStageError("seal ledger has invalid top-level fields")
    if ledger.get("schema_version") != "1.0":
        raise IntegrityStageError("seal ledger schema_version must be 1.0")
    if ledger.get("algorithm") != "git-blob-sha1":
        raise IntegrityStageError("seal ledger algorithm must be git-blob-sha1")
    raw_entries = ledger.get("storyboards")
    if not isinstance(raw_entries, list):
        raise IntegrityStageError("seal ledger storyboards must be an array")

    expected = _registry_storyboards(root)
    seen: set[str] = set()
    for entry in raw_entries:
        if not isinstance(entry, dict) or set(entry) != {"sample_id", "path", "git_blob_sha1"}:
            raise IntegrityStageError("seal ledger contains an invalid storyboard entry")
        sample_id = entry.get("sample_id")
        if not isinstance(sample_id, str) or sample_id in seen:
            raise IntegrityStageError("seal ledger has duplicate or invalid sample_id")
        seen.add(sample_id)
        if sample_id not in expected:
            raise IntegrityStageError(f"seal ledger references unknown storyboard {sample_id}")
        expected_path = expected[sample_id].relative_to(root).as_posix()
        if entry.get("path") != expected_path:
            raise IntegrityStageError(f"{sample_id} seal path does not match registry")
        digest = entry.get("git_blob_sha1")
        if not isinstance(digest, str) or GIT_BLOB_SHA1.fullmatch(digest) is None:
            raise IntegrityStageError(f"{sample_id} storyboard seal is invalid")
        actual = git_blob_sha1(expected[sample_id])
        if actual != digest:
            raise IntegrityStageError(
                f"{sample_id} storyboard seal stale: expected {digest}, current {actual}; "
                "run explicit seal/reseal only after audit edits are complete"
            )

    missing = set(expected) - seen
    if missing:
        raise IntegrityStageError(f"seal ledger is missing storyboards: {sorted(missing)}")


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _safe_sha(value: Any, fallback: str | None = None) -> str:
    if _valid_sha256(value):
        return value
    if fallback is not None and _valid_sha256(fallback):
        return fallback
    return "0" * 64


def _normalize_integrity_for_audit_shadow(root: Path) -> None:
    """Repair pure integrity metadata only in a temporary audit-validation copy.

    This deliberately does not repair source-search identity, scientific content,
    audit statuses, summary counts, rule receipts, or reader-outcome semantics.
    """

    registry = _load_json(root / "data/registry.json")
    sample_ids = registry.get("sample_ids", []) if isinstance(registry, dict) else []
    if not isinstance(sample_ids, list):
        return

    for sample_id in sample_ids:
        if not isinstance(sample_id, str):
            continue
        sample_path = root / f"data/samples/{sample_id}/sample.json"
        sample = _load_json(sample_path)
        if not isinstance(sample, dict):
            continue

        article_path_value = sample.get("article_path")
        if isinstance(article_path_value, str):
            article_path = root / article_path_value
            if article_path.is_file():
                sample["article_sha256"] = _sha256_file(article_path)

        source = sample.get("source")
        pdf_digest = None
        if isinstance(source, dict):
            verification_state = source.get("verification_state")
            if verification_state in {"full_text", "full_text_audited"}:
                source["pdf_sha256"] = _safe_sha(source.get("pdf_sha256"))
            elif "pdf_sha256" in source:
                source["pdf_sha256"] = _safe_sha(source.get("pdf_sha256"))
            if _valid_sha256(source.get("pdf_sha256")):
                pdf_digest = source["pdf_sha256"]

        source_resolution = sample.get("source_resolution")
        if isinstance(source_resolution, dict):
            selected_pdf = source_resolution.get("selected_pdf")
            if isinstance(selected_pdf, dict) and pdf_digest is not None:
                selected_pdf["sha256"] = pdf_digest

        receipts = sample.get("artifact_receipts")
        if isinstance(receipts, list):
            for receipt in receipts:
                if not isinstance(receipt, dict):
                    continue
                if receipt.get("kind") == "source_pdf" and pdf_digest is not None:
                    receipt["sha256"] = pdf_digest
                elif "sha256" in receipt:
                    receipt["sha256"] = _safe_sha(receipt.get("sha256"))

        storyboard_path_value = sample.get("card_storyboard_path")
        if isinstance(storyboard_path_value, str):
            storyboard_path = root / storyboard_path_value
            storyboard = _load_json(storyboard_path)
            if isinstance(storyboard, dict):
                receipt_list = receipts if isinstance(receipts, list) else []
                canonical_receipts = [
                    receipt
                    for receipt in receipt_list
                    if isinstance(receipt, dict) and receipt.get("kind") == "canonical_render_queue"
                ]
                canonical = storyboard.get("canonical_queue")
                if isinstance(canonical, dict) and canonical_receipts:
                    receipt = canonical_receipts[0]
                    if isinstance(receipt.get("filename"), str):
                        canonical["filename"] = receipt["filename"]
                    canonical["sha256"] = _safe_sha(receipt.get("sha256"))

                alternate_receipts = [
                    receipt
                    for receipt in receipt_list
                    if isinstance(receipt, dict) and receipt.get("kind") == "alternate_render_queue"
                ]
                rejected = storyboard.get("rejected_queue")
                if isinstance(rejected, dict) and alternate_receipts:
                    matching = [
                        receipt
                        for receipt in alternate_receipts
                        if receipt.get("filename") == rejected.get("filename")
                    ]
                    receipt = matching[0] if matching else alternate_receipts[0]
                    if isinstance(receipt.get("filename"), str):
                        rejected["filename"] = receipt["filename"]
                    rejected["sha256"] = _safe_sha(receipt.get("sha256"))

                cards = storyboard.get("cards")
                if isinstance(cards, list):
                    for card in cards:
                        if isinstance(card, dict) and "image_sha256" in card:
                            card["image_sha256"] = _safe_sha(card.get("image_sha256"))
                _write_json(storyboard_path, storyboard)

        _write_json(sample_path, sample)


def _check_all_json_syntax(root: Path) -> None:
    for path in sorted(root.rglob("*.json")):
        _load_json(path)


def validate_stage(root: Path = ROOT, stage: str = "seal") -> dict[str, int]:
    """Validate one workflow stage without silently moving the stage boundary."""

    root = root.resolve()
    if stage not in {"audit", "seal"}:
        raise IntegrityStageError(f"unknown stage: {stage}")
    _check_all_json_syntax(root)

    if stage == "seal":
        try:
            counts = validate_registry(root)
        except ValidationError as exc:
            raise IntegrityStageError(str(exc)) from exc
        check_storyboard_seals(root)
        return counts

    with tempfile.TemporaryDirectory() as directory:
        shadow = Path(directory) / "EvidenceProse"
        shutil.copytree(
            root,
            shadow,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
        )
        _normalize_integrity_for_audit_shadow(shadow)
        try:
            return validate_registry(shadow)
        except ValidationError as exc:
            raise IntegrityStageError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    parser.add_argument("--stage", choices=("audit", "seal"), default="seal")
    parser.add_argument(
        "--reseal-storyboards",
        action="store_true",
        help="explicitly refresh repository-local storyboard seals before seal validation",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.reseal_storyboards and args.stage != "seal":
        message = "--reseal-storyboards is allowed only in the explicit seal stage"
        if args.json:
            print(json.dumps({"status": "fail", "stage": args.stage, "error": message}, ensure_ascii=False))
        else:
            print(f"FAIL: {message}")
        return 1

    try:
        if args.reseal_storyboards:
            reseal_storyboards(args.root)
        counts = validate_stage(args.root, args.stage)
    except IntegrityStageError as exc:
        if args.json:
            print(
                json.dumps(
                    {"status": "fail", "stage": args.stage, "error": str(exc)},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            print(f"FAIL [{args.stage}]: {exc}")
        return 1

    if args.json:
        print(
            json.dumps(
                {"status": "pass", "stage": args.stage, "counts": counts},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        print(f"PASS [{args.stage}]: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
