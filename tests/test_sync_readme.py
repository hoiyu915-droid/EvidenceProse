from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.sync_readme import (  # noqa: E402
    REGISTRY_STATUS_END,
    REGISTRY_STATUS_START,
    REPOSITORY_LAYOUT_END,
    REPOSITORY_LAYOUT_START,
    SyncError,
    check,
    main,
    render_registry_status,
    render_repository_layout,
    replace_controlled_block,
)


class SyncReadmeTests(unittest.TestCase):
    def test_registry_status_is_derived_from_validated_counts(self) -> None:
        status = render_registry_status()
        self.assertIn("Induction samples: 7 (`S001`–`S007`)", status)
        self.assertIn("Processing-rule catalogue: 24 (`R001`–`R024`)", status)
        self.assertIn("9 candidates, 1 conditional rule, 14 hypotheses", status)
        self.assertIn("Audited companion cards: 36 (36/36 content-truth passes; 28/36", status)
        self.assertIn("Stable induction generation rules: 0; stable voice rules: 0", status)

    def test_replace_controlled_block_preserves_uncontrolled_text(self) -> None:
        source = f"before\n{REGISTRY_STATUS_START}\nstale\n{REGISTRY_STATUS_END}\nafter\n"
        updated = replace_controlled_block(
            source,
            REGISTRY_STATUS_START,
            REGISTRY_STATUS_END,
            "fresh",
        )
        self.assertEqual(
            updated,
            f"before\n{REGISTRY_STATUS_START}\nfresh\n{REGISTRY_STATUS_END}\nafter\n",
        )

    def test_replace_controlled_block_fails_closed_on_missing_or_duplicate_markers(self) -> None:
        with self.assertRaisesRegex(SyncError, "exactly one"):
            replace_controlled_block("no markers\n", REGISTRY_STATUS_START, REGISTRY_STATUS_END, "fresh")
        duplicate = (
            f"{REGISTRY_STATUS_START}\na\n{REGISTRY_STATUS_END}\n"
            f"{REGISTRY_STATUS_START}\nb\n{REGISTRY_STATUS_END}\n"
        )
        with self.assertRaisesRegex(SyncError, "exactly one"):
            replace_controlled_block(duplicate, REGISTRY_STATUS_START, REGISTRY_STATUS_END, "fresh")

    def test_checked_in_readme_is_synchronized(self) -> None:
        self.assertTrue(check())

    def test_repository_layout_is_deterministic_and_ignores_transient_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in (
                root / ".git",
                root / "data" / "samples" / "S001",
                root / "data" / "samples" / "S002",
                root / "docs",
                root / "scripts" / "__pycache__",
            ):
                path.mkdir(parents=True)
            (root / ".git" / "config").write_text("ignored", encoding="utf-8")
            (root / "data" / "samples" / "S001" / "article.md").write_text(
                "ignored", encoding="utf-8"
            )
            (root / "data" / "samples" / "S002" / "sample.json").write_text(
                "ignored", encoding="utf-8"
            )
            (root / "docs" / "z.md").write_text("z", encoding="utf-8")
            (root / "docs" / "a.md").write_text("a", encoding="utf-8")
            (root / "scripts" / "__pycache__" / "module.pyc").write_bytes(b"ignored")
            (root / "loose.pyc").write_bytes(b"ignored")
            (root / "README.md").write_text("readme", encoding="utf-8")

            self.assertEqual(
                render_repository_layout(root),
                "\n".join(
                    (
                        "```text",
                        "data/",
                        "  samples/",
                        "    S*/",
                        "docs/",
                        "  a.md",
                        "  z.md",
                        "scripts/",
                        "README.md",
                        "```",
                    )
                ),
            )

    def test_cli_check_detects_drift_and_write_repairs_only_the_controlled_block(self) -> None:
        source = (
            f"before\n{REGISTRY_STATUS_START}\nstale status\n{REGISTRY_STATUS_END}\n"
            f"middle\n{REPOSITORY_LAYOUT_START}\nstale layout\n{REPOSITORY_LAYOUT_END}\nafter\n"
        )
        expected = (
            f"before\n{REGISTRY_STATUS_START}\nfresh status\n{REGISTRY_STATUS_END}\n"
            f"middle\n{REPOSITORY_LAYOUT_START}\nfresh layout\n{REPOSITORY_LAYOUT_END}\nafter\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text(source, encoding="utf-8")
            with (
                patch("scripts.sync_readme.render_registry_status", return_value="fresh status"),
                patch("scripts.sync_readme.render_repository_layout", return_value="fresh layout"),
            ):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    self.assertEqual(main(["--check", "--root", str(root)]), 1)
                    self.assertEqual(main(["--write", "--root", str(root)]), 0)
                    self.assertEqual(main(["--check", "--root", str(root)]), 0)
            self.assertEqual((root / "README.md").read_text(encoding="utf-8"), expected)


if __name__ == "__main__":
    unittest.main()
