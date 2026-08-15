#!/usr/bin/env python3
"""Validate EvidenceProse Probe post-audit transform bundles.

v1.0 validates declared post-audit transform state. v1.1 additionally binds the
record to real article/card files, computes element-level diffs, protects
immutable evidence assets, and gates release on an isolated-reader EvidenceQuiz.
The validator does not redo TA06 source audit or Claude semantic judgment.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe_post_audit_artifacts import _validate_artifacts
from probe_post_audit_common import VERSIONS, _text
from probe_post_audit_core import _validate_core
from probe_post_audit_quiz import _validate_quiz


def validate_bundle(bundle: Any, *, base_dir: Path | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(bundle, dict):
        return ["bundle must be a JSON object"]
    version = bundle.get("contract_version")
    if version not in VERSIONS:
        return ["contract_version must be 1.0 or 1.1"]
    state = _validate_core(bundle, version, errors)
    artifact_failed = reader_failed = False
    if version == "1.1":
        artifacts = _validate_artifacts(bundle, base_dir, state, errors)
        artifact_failed = artifacts["failed"]
        reader_failed = _validate_quiz(bundle, state, artifacts, errors)

    guard = state["guard"]
    guards_pass = all(guard.get(check) == "pass" for check in state["guards"])
    findings_pass = all(
        isinstance(finding, dict)
        and (finding.get("severity") != "hard" or finding.get("status") == "resolved")
        for finding in state["findings"]
    )
    article = state["article"]
    article_pass = (
        article.get("new_claim_ids") == []
        and article.get("removed_material_claim_ids") == []
        and article.get("claim_strength_changed") is False
    )
    expected_gate = "pass" if (
        guards_pass and findings_pass and article_pass
        and not state["scope_error"] and not state["coverage_error"]
        and not artifact_failed and not reader_failed
    ) else "fail"
    final_gate = bundle.get("final_gate")
    if not isinstance(final_gate, dict):
        errors.append("final_gate must be an object")
    else:
        if final_gate.get("status") != expected_gate:
            errors.append(f"final_gate.status must be {expected_gate} from hard guards and transform state")
        if not _text(final_gate.get("rationale")):
            errors.append("final_gate.rationale must be non-empty")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    except OSError as exc:
        errors = [f"cannot read {args.bundle}: {exc}"]
        version = None
    except json.JSONDecodeError as exc:
        errors = [f"invalid JSON at {exc.lineno}:{exc.colno}: {exc.msg}"]
        version = None
    else:
        version = bundle.get("contract_version") if isinstance(bundle, dict) else None
        errors = validate_bundle(bundle, base_dir=args.bundle.resolve().parent)
    result = {
        "status": "pass" if not errors else "fail",
        "contract_version": version,
        "errors": errors,
    }
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    else:
        print(f"Probe post-audit bundle v{version}: PASS")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
