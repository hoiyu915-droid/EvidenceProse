from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_explainer_output", ROOT / "scripts" / "validate_explainer_output.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
validate_text = MODULE.validate_text


VALID = """# 兩個 AI 真的比兩個人更有創意嗎？

## 一句話總結
在三項開放式任務中，雙 AI 迭代流程的新穎性與部分創造力結果較強，但研究沒有把代理數與迭代、回饋和停止規則拆開，因此不能把優勢單獨歸因於多代理本身。

## 內容

研究比較四套完整創作流程，而不是只操弄代理數。這使流程比較具有實務意義，但限制了機制推論。

### 內容完整性註記

原稿方法段有一處角色稱呼不一致；這是報告問題，不足以單獨推翻整組資料。

## 引用來源

Luan YL, Sun L, Kim YJ, Wang J, Xie X. 2026. AI-AI co-creation outperforms human pairs in creative tasks. arXiv:2608.09023. 預印本。

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


if __name__ == "__main__":
    unittest.main()
