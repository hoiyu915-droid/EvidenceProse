from __future__ import annotations

from contextlib import redirect_stderr
import importlib.util
import io
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_explainer_output", ROOT / "scripts" / "validate_explainer_output.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
internal_marker_errors = MODULE.internal_marker_errors
english_gloss_errors = MODULE.english_gloss_errors
validate_text = MODULE.validate_text


VALID = """# 兩個 AI(人工智慧)真的比兩個人更有創意嗎？

## 一句話總結
在三項開放式任務中，雙 AI(人工智慧)迭代流程的新穎性與部分創造力結果較強，但研究沒有把代理數與迭代、回饋和停止規則拆開，因此不能把優勢單獨歸因於多代理本身。

## 內容

研究比較四套完整創作流程，而不是只操弄代理數。這使流程比較具有實務意義，但限制了機制推論。

### 內容完整性註記

原稿方法段有一處角色稱呼不一致；這是報告問題，不足以單獨推翻整組資料。

## 引用來源

Luan YL, Sun L, Kim YJ, Wang J, Xie X. 2026. AI-AI co-creation outperforms
human pairs in creative tasks. arXiv:2608.09023. 預印本。

🟡 證據分級：中等。具直接比較與量化評分，但目前是預印本，任務範圍有限，而且多個流程因素同時改變。

> 最後更新：20260813
"""


class ExplainerOutputFormatTests(unittest.TestCase):
    @staticmethod
    def with_content(content: str) -> str:
        before, remainder = VALID.split("## 內容\n", 1)
        _, after = remainder.split("## 引用來源", 1)
        return f"{before}## 內容\n\n{content}\n\n## 引用來源{after}"

    def test_valid_delivery_passes(self) -> None:
        self.assertEqual(
            validate_text(VALID, filename="20260813_ai-ai-cocreation-creativity.md"),
            [],
        )

    def test_filename_is_canonical(self) -> None:
        errors = validate_text(VALID, filename="AI AI prose final.md")
        self.assertTrue(any("filename must match" in error for error in errors))

    def test_required_h2_order_is_fixed(self) -> None:
        broken = VALID.replace(
            "## 一句話總結\n在三項開放式任務中",
            "## 內容\n在三項開放式任務中",
            1,
        ).replace("## 內容\n\n研究比較", "## 一句話總結\n\n研究比較", 1)
        errors = validate_text(
            broken, filename="20260813_ai-ai-cocreation-creativity.md"
        )
        self.assertTrue(any("H2 sections must be exactly" in error for error in errors))

    def test_internal_filecite_is_rejected(self) -> None:
        broken = VALID.replace(
            "研究比較四套完整創作流程",
            "研究比較四套完整創作流程 fileciteturn44file0",
        )
        errors = validate_text(
            broken, filename="20260813_ai-ai-cocreation-creativity.md"
        )
        self.assertTrue(any("filecite marker" in error for error in errors))
        self.assertTrue(any("turn/file reference" in error for error in errors))

    def test_bare_local_pdf_filename_is_rejected(self) -> None:
        broken = VALID.replace(
            "arXiv:2608.09023. 預印本。",
            "2608.09023v1.pdf",
        )
        errors = validate_text(
            broken, filename="20260813_ai-ai-cocreation-creativity.md"
        )
        self.assertTrue(any("bare/local PDF filename" in error for error in errors))

    def test_reader_facing_english_requires_immediate_chinese_gloss(self) -> None:
        broken = VALID.replace("研究比較四套完整創作流程", "研究採用 self-report 設計")
        errors = validate_text(
            broken, filename="20260813_ai-ai-cocreation-creativity.md"
        )
        self.assertTrue(
            any("'self-report'; use English(中文)" in error for error in errors),
            errors,
        )

    def test_title_and_every_repeated_occurrence_require_glosses(self) -> None:
        title_broken = VALID.replace(
            "# 兩個 AI(人工智慧)真的比兩個人更有創意嗎？",
            "# self-report 研究能告訴我們甚麼？",
        )
        repeated_broken = VALID.replace(
            "研究比較四套完整創作流程",
            "self-report(自陳)研究比較四套流程，第二次 self-report 仍須解釋",
        )
        self.assertTrue(any("self-report" in item for item in english_gloss_errors(title_broken)))
        self.assertEqual(
            sum("self-report" in item for item in english_gloss_errors(repeated_broken)),
            1,
        )

    def test_reader_facing_english_with_chinese_gloss_passes(self) -> None:
        article = VALID.replace(
            "研究比較四套完整創作流程",
            "研究採用 self-report(自陳)與 cross-sectional SEM(橫斷面結構方程模型)",
        )
        self.assertEqual(
            validate_text(
                article, filename="20260813_ai-ai-cocreation-creativity.md"
            ),
            [],
        )

    def test_full_width_chinese_gloss_is_accepted(self) -> None:
        article = VALID.replace("研究比較四套完整創作流程", "研究採用 trust（信任）量表")
        self.assertEqual(english_gloss_errors(article), [])

    def test_gloss_must_be_immediate_and_contain_chinese(self) -> None:
        spaced = VALID.replace("研究比較四套完整創作流程", "研究採用 trust (信任)量表")
        english_only = VALID.replace(
            "研究比較四套完整創作流程", "研究採用 trust(confidence)量表"
        )
        self.assertTrue(english_gloss_errors(spaced))
        self.assertTrue(english_gloss_errors(english_only))

    def test_bibliography_code_url_and_public_identifiers_are_exempt(self) -> None:
        article = VALID.replace(
            "研究比較四套完整創作流程",
            "Rösler 等人在 `model_name` 中記錄 n=384、70 kg 與 30 mL/min，詳見 DOI 與 https://example.org/path",
        )
        self.assertEqual(english_gloss_errors(article), [])

    def test_scientific_acronym_is_not_mistaken_for_an_exempt_identifier(self) -> None:
        broken = VALID.replace("研究比較四套完整創作流程", "研究使用 SEM 分析")
        self.assertTrue(any("'SEM'" in item for item in english_gloss_errors(broken)))

    def test_english_in_evidence_grade_rationale_requires_gloss(self) -> None:
        broken = VALID.replace("具直接比較與量化評分", "self-report 設計具直接比較與量化評分")
        errors = validate_text(
            broken, filename="20260813_ai-ai-cocreation-creativity.md"
        )
        self.assertTrue(any("self-report" in error for error in errors), errors)

    def test_grade_emoji_must_match_grade(self) -> None:
        broken = VALID.replace("🟡 證據分級：中等。", "🟢 證據分級：中等。")
        errors = validate_text(
            broken, filename="20260813_ai-ai-cocreation-creativity.md"
        )
        self.assertTrue(any("emoji does not match" in error for error in errors))

    def test_update_footnote_is_final(self) -> None:
        broken = VALID + "\n額外尾巴\n"
        errors = validate_text(
            broken, filename="20260813_ai-ai-cocreation-creativity.md"
        )
        self.assertTrue(any("final non-empty line" in error for error in errors))

    def test_content_over_4000_characters_is_rejected_by_default(self) -> None:
        article = self.with_content("研" * 4001)
        errors = validate_text(
            article, filename="20260813_ai-ai-cocreation-creativity.md"
        )
        self.assertTrue(any("4000-character ceiling" in error for error in errors))

    def test_large_literature_exception_requires_reason(self) -> None:
        article = self.with_content("研" * 4001)
        errors = validate_text(
            article,
            filename="20260813_ai-ai-cocreation-creativity.md",
            allow_large_literature=True,
        )
        self.assertTrue(any("requires a non-empty reason" in error for error in errors))

    def test_large_literature_exception_with_reason_passes(self) -> None:
        article = self.with_content("研" * 4001)
        errors = validate_text(
            article,
            filename="20260813_ai-ai-cocreation-creativity.md",
            allow_large_literature=True,
            length_exception_reason="Compression would remove material cross-study limits.",
        )
        self.assertEqual(errors, [])

    def test_unnecessary_large_literature_exception_is_rejected(self) -> None:
        errors = validate_text(
            VALID,
            filename="20260813_ai-ai-cocreation-creativity.md",
            allow_large_literature=True,
            length_exception_reason="Not actually needed.",
        )
        self.assertTrue(any("exception is unnecessary" in error for error in errors))

    def test_shipped_template_has_no_internal_markers(self) -> None:
        text = (ROOT / "templates" / "science_explainer.md").read_text(encoding="utf-8")
        errors = validate_text(text, filename="20260101_placeholder.md")
        self.assertEqual(
            errors,
            ["document must contain exactly one > 最後更新：YYYYMMDD footnote"],
        )

    def test_reader_facing_fixtures_have_no_internal_markers(self) -> None:
        fixture_paths = sorted((ROOT / "fixtures").glob("*.md"))
        self.assertTrue(fixture_paths)
        for path in fixture_paths:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertEqual(internal_marker_errors(text), [])

    def test_large_literature_exception_rejects_multiple_paths(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            MODULE.main(
                [
                    "--allow-large-literature",
                    "--length-exception-reason",
                    "Genuinely large literature base.",
                    "first.md",
                    "second.md",
                ]
            )
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("accepts exactly one path", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
