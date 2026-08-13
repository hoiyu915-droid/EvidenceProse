from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.card_audit_edit import AuditEditError, apply_card_correction  # noqa: E402
from scripts.integrity_stage import (  # noqa: E402
    IntegrityStageError,
    reseal_storyboards,
    validate_stage,
)


@contextmanager
def copied_registry() -> Path:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "EvidenceProse"
        shutil.copytree(ROOT / "data", root / "data")
        shutil.copytree(ROOT / "schemas", root / "schemas")
        yield root


def rewrite_json(path: Path, document: object) -> None:
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class AuditSealBoundaryTests(unittest.TestCase):
    def test_repository_is_sealed_before_editing(self) -> None:
        self.assertEqual(validate_stage(ROOT, "seal")["samples"], 7)

    def test_two_character_content_edit_does_not_reseal_until_explicit_seal(self) -> None:
        with copied_registry() as root:
            storyboard_path = root / "data/samples/S002/card_storyboard.json"
            seals_path = root / "data/integrity_seals.json"
            seals_before = seals_path.read_bytes()
            storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
            card = storyboard["cards"][0]
            queue_digest_before = storyboard["canonical_queue"]["sha256"]
            image_digest_before = card["image_sha256"]

            visible_text = list(card["visible_text"])
            visible_text[0] = visible_text[0] + "修正"
            apply_card_correction(storyboard, card["card_id"], {"visible_text": visible_text})
            rewrite_json(storyboard_path, storyboard)

            self.assertEqual(seals_path.read_bytes(), seals_before)
            self.assertEqual(storyboard["canonical_queue"]["sha256"], queue_digest_before)
            self.assertEqual(card["image_sha256"], image_digest_before)
            self.assertEqual(validate_stage(root, "audit")["samples"], 7)

            with self.assertRaisesRegex(IntegrityStageError, "storyboard seal stale"):
                validate_stage(root, "seal")

            reseal_storyboards(root)
            self.assertNotEqual(seals_path.read_bytes(), seals_before)
            self.assertEqual(validate_stage(root, "seal")["samples"], 7)

    def test_audit_stage_tolerates_stale_queue_digest_but_seal_does_not(self) -> None:
        with copied_registry() as root:
            storyboard_path = root / "data/samples/S002/card_storyboard.json"
            storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
            storyboard["canonical_queue"]["sha256"] = "0" * 64
            rewrite_json(storyboard_path, storyboard)

            self.assertEqual(validate_stage(root, "audit")["samples"], 7)
            with self.assertRaisesRegex(IntegrityStageError, "canonical queue digest does not match receipt"):
                validate_stage(root, "seal")

    def test_content_editor_refuses_integrity_metadata(self) -> None:
        storyboard = json.loads(
            (ROOT / "data/samples/S002/card_storyboard.json").read_text(encoding="utf-8")
        )
        with self.assertRaisesRegex(AuditEditError, "non-content fields"):
            apply_card_correction(
                storyboard,
                "C01",
                {"image_sha256": "0" * 64},
            )

    def test_review_only_patch_is_not_a_content_correction(self) -> None:
        storyboard = json.loads(
            (ROOT / "data/samples/S002/card_storyboard.json").read_text(encoding="utf-8")
        )
        with self.assertRaisesRegex(AuditEditError, "content patch must be a non-empty object"):
            apply_card_correction(
                storyboard,
                "C01",
                {},
                audit_patch={
                    "content_truth_audit": {
                        "status": "fail",
                        "violations": ["needs wording correction"],
                    }
                },
            )


if __name__ == "__main__":
    unittest.main()
