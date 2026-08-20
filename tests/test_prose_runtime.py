from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import validate_prose_runtime as runtime


FIXTURES = ROOT / "fixtures"


def load_json(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ProseRuntimeTests(unittest.TestCase):
    @staticmethod
    def with_content(article: str, content: str) -> str:
        before, remainder = article.split("## 內容\n", 1)
        _, after = remainder.split("## 引用來源", 1)
        return f"{before}## 內容\n\n{content}\n\n## 引用來源{after}"

    @staticmethod
    def lint_article(content: str, summary: str = "這是簡短摘要。") -> str:
        return (
            "# 測試標題\n\n"
            "## 一句話總結\n"
            f"{summary}\n\n"
            "## 內容\n\n"
            f"{content}\n\n"
            "## 引用來源\n\n"
            "Example Author. 2026. Example study. doi:10.1000/example\n"
        )

    @staticmethod
    def validate_fixture_with_sidecar(sidecar: dict):
        with tempfile.TemporaryDirectory() as tmp:
            sidecar_path = Path(tmp) / "prose_audit_sidecar.json"
            sidecar_path.write_text(
                json.dumps(sidecar, ensure_ascii=False), encoding="utf-8"
            )
            return runtime.validate_bundle(
                handoff_path=FIXTURES / "valid_ta06_prose_handoff.json",
                reader_path=FIXTURES / "valid_prose_reader_contract.json",
                sidecar_path=sidecar_path,
                article_path=FIXTURES / "20260815_demo-explainer.md",
            )

    def test_valid_fixture_passes(self):
        report = runtime.validate_bundle(
            handoff_path=FIXTURES / "valid_ta06_prose_handoff.json",
            reader_path=FIXTURES / "valid_prose_reader_contract.json",
            sidecar_path=FIXTURES / "valid_prose_audit_sidecar.json",
            article_path=FIXTURES / "20260815_demo-explainer.md",
        )
        self.assertEqual(report["status"], "pass", report["errors"])

    def test_permission_projection_is_fail_closed(self):
        handoff = load_json("valid_ta06_prose_handoff.json")
        handoff["permission"]["released_claim_ids"].remove("CLM002")
        errors = runtime.validate_handoff(handoff)
        self.assertTrue(any("released_claim_ids" in error for error in errors))

    def test_conditional_claim_requires_condition(self):
        handoff = load_json("valid_ta06_prose_handoff.json")
        handoff["claims"][1]["condition_if_any"] = ""
        errors = runtime.validate_handoff(handoff)
        self.assertTrue(any("condition_if_any" in error for error in errors))

    def test_reader_contract_must_bind_handoff_digest(self):
        handoff = load_json("valid_ta06_prose_handoff.json")
        reader = load_json("valid_prose_reader_contract.json")
        reader["handoff_digest"] = "0" * 64
        errors = runtime.validate_reader_contract(
            reader, handoff_digest=runtime.canonical_digest(handoff)
        )
        self.assertTrue(any("handoff_digest" in error for error in errors))

    def test_final_pass_rejected_when_hard_semantic_check_fails(self):
        handoff = load_json("valid_ta06_prose_handoff.json")
        reader = load_json("valid_prose_reader_contract.json")
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["semantic_guard"]["no_add"] = "fail"
        sidecar["final_gate"]["status"] = "pass"
        errors = runtime.validate_sidecar(
            sidecar,
            handoff_digest=runtime.canonical_digest(handoff),
            reader_digest=runtime.canonical_digest(reader),
            article_id=reader["article_id"],
        )
        self.assertTrue(any("final_gate.status must be fail" in error for error in errors))

    def test_every_hard_semantic_failure_is_wired_to_final_gate(self):
        handoff = load_json("valid_ta06_prose_handoff.json")
        reader = load_json("valid_prose_reader_contract.json")
        for check in runtime.HARD_CHECKS:
            with self.subTest(check=check):
                sidecar = load_json("valid_prose_audit_sidecar.json")
                sidecar["semantic_guard"][check] = "fail"
                sidecar["final_gate"]["status"] = "pass"
                errors = runtime.validate_sidecar(
                    sidecar,
                    handoff_digest=runtime.canonical_digest(handoff),
                    reader_digest=runtime.canonical_digest(reader),
                    article_id=reader["article_id"],
                )
                self.assertTrue(
                    any("final_gate.status must be fail" in error for error in errors)
                )

    def test_hard_violation_is_wired_to_final_gate(self):
        handoff = load_json("valid_ta06_prose_handoff.json")
        reader = load_json("valid_prose_reader_contract.json")
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["violations"] = [
            {
                "code": "NO_ADD",
                "severity": "hard",
                "location": "## 內容，第 1 段",
                "claim_id": "CLM001",
                "description": "Draft adds an unsupported mechanism.",
                "required_repair": "Remove the unsupported mechanism.",
            }
        ]
        sidecar["final_gate"]["status"] = "pass"
        errors = runtime.validate_sidecar(
            sidecar,
            handoff_digest=runtime.canonical_digest(handoff),
            reader_digest=runtime.canonical_digest(reader),
            article_id=reader["article_id"],
        )
        self.assertTrue(
            any("final_gate.status must be fail" in error for error in errors),
            errors,
        )

    def test_sidecar_shape_matches_schema_fail_closed_rules(self):
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["unexpected"] = True
        sidecar["lint_warnings"][0].pop("location")
        report = self.validate_fixture_with_sidecar(sidecar)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(
            any("unexpected fields" in error for error in report["errors"]),
            report["errors"],
        )
        self.assertTrue(
            any("location must be non-empty" in error for error in report["errors"]),
            report["errors"],
        )

    def test_reader_outcome_fail_blocks_release(self):
        handoff = load_json("valid_ta06_prose_handoff.json")
        reader = load_json("valid_prose_reader_contract.json")
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["reader_outcomes"]["understandable"]["status"] = "fail"
        sidecar["final_gate"]["status"] = "pass"
        errors = runtime.validate_sidecar(
            sidecar,
            handoff_digest=runtime.canonical_digest(handoff),
            reader_digest=runtime.canonical_digest(reader),
            article_id=reader["article_id"],
        )
        self.assertTrue(any("final_gate.status must be fail" in error for error in errors))

    def test_unverified_targeted_repair_blocks_release(self):
        handoff = load_json("valid_ta06_prose_handoff.json")
        reader = load_json("valid_prose_reader_contract.json")
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["targeted_repairs"] = [
            {
                "repair_id": "R1",
                "location": "## 內容，第 1 段",
                "status": "applied",
                "description": "補回時間範圍限定詞。",
            }
        ]
        sidecar["final_gate"]["status"] = "pass"
        errors = runtime.validate_sidecar(
            sidecar,
            handoff_digest=runtime.canonical_digest(handoff),
            reader_digest=runtime.canonical_digest(reader),
            article_id=reader["article_id"],
        )
        self.assertTrue(any("final_gate.status must be fail" in error for error in errors))

    def test_delivery_shell_errors_are_in_runtime_report(self):
        article = (FIXTURES / "20260815_demo-explainer.md").read_text(encoding="utf-8")
        article = article.replace("## 引用來源", "## Sources")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bad_article = tmp / "20260815_demo-explainer.md"
            bad_article.write_text(article, encoding="utf-8")
            report = runtime.validate_bundle(
                handoff_path=FIXTURES / "valid_ta06_prose_handoff.json",
                reader_path=FIXTURES / "valid_prose_reader_contract.json",
                sidecar_path=FIXTURES / "valid_prose_audit_sidecar.json",
                article_path=bad_article,
            )
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("article delivery" in error for error in report["errors"]))

    def test_runtime_blocks_unglossed_reader_facing_english(self):
        article = (FIXTURES / "20260815_demo-explainer.md").read_text(encoding="utf-8")
        article = article.replace("主要結果呈現有利方向", "self-report 結果呈現有利方向")
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["article_sha256"] = hashlib.sha256(article.encode("utf-8")).hexdigest()
        sidecar["delivery_length_exception"]["measured_characters"] = (
            runtime.content_character_count(article)
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            article_path = tmp / "20260815_demo-explainer.md"
            sidecar_path = tmp / "prose_audit_sidecar.json"
            article_path.write_text(article, encoding="utf-8")
            sidecar_path.write_text(
                json.dumps(sidecar, ensure_ascii=False), encoding="utf-8"
            )
            report = runtime.validate_bundle(
                handoff_path=FIXTURES / "valid_ta06_prose_handoff.json",
                reader_path=FIXTURES / "valid_prose_reader_contract.json",
                sidecar_path=sidecar_path,
                article_path=article_path,
            )
        self.assertEqual(report["status"], "fail")
        self.assertTrue(
            any(
                "reader-facing English requires an immediate Chinese gloss" in error
                for error in report["errors"]
            ),
            report["errors"],
        )

    def test_runtime_accepts_reader_facing_english_with_chinese_gloss(self):
        article = (FIXTURES / "20260815_demo-explainer.md").read_text(encoding="utf-8")
        article = article.replace(
            "主要結果呈現有利方向",
            "self-report(自陳)結果呈現有利方向",
        )
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["article_sha256"] = hashlib.sha256(article.encode("utf-8")).hexdigest()
        sidecar["delivery_length_exception"]["measured_characters"] = (
            runtime.content_character_count(article)
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            article_path = tmp / "20260815_demo-explainer.md"
            sidecar_path = tmp / "prose_audit_sidecar.json"
            article_path.write_text(article, encoding="utf-8")
            sidecar_path.write_text(
                json.dumps(sidecar, ensure_ascii=False), encoding="utf-8"
            )
            report = runtime.validate_bundle(
                handoff_path=FIXTURES / "valid_ta06_prose_handoff.json",
                reader_path=FIXTURES / "valid_prose_reader_contract.json",
                sidecar_path=sidecar_path,
                article_path=article_path,
            )
        self.assertEqual(report["status"], "pass", report["errors"])

    def test_runtime_enforces_4000_character_content_ceiling(self):
        article = (FIXTURES / "20260815_demo-explainer.md").read_text(encoding="utf-8")
        article = self.with_content(article, "研" * 4001)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "20260815_demo-explainer.md"
            path.write_text(article, encoding="utf-8")
            report = runtime.validate_bundle(
                handoff_path=FIXTURES / "valid_ta06_prose_handoff.json",
                reader_path=FIXTURES / "valid_prose_reader_contract.json",
                sidecar_path=FIXTURES / "valid_prose_audit_sidecar.json",
                article_path=path,
            )
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("4000-character ceiling" in error for error in report["errors"]))

    def test_runtime_allows_bound_large_literature_exception(self):
        article = (FIXTURES / "20260815_demo-explainer.md").read_text(encoding="utf-8")
        article = self.with_content(article, "研" * 4001)
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["delivery_length_exception"] = {
            "granted": True,
            "measured_characters": 4001,
            "ceiling": 4000,
            "reason": "Compression would remove material cross-study limits.",
        }
        sidecar["article_sha256"] = hashlib.sha256(article.encode("utf-8")).hexdigest()
        sidecar["lint_warnings"].append(
            {
                "category": "long_paragraph",
                "location": "## 內容，第 1 段",
                "message": "大型文獻說明形成超長段落。",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            path = tmp / "20260815_demo-explainer.md"
            sidecar_path = tmp / "prose_audit_sidecar.json"
            path.write_text(article, encoding="utf-8")
            sidecar_path.write_text(
                json.dumps(sidecar, ensure_ascii=False), encoding="utf-8"
            )
            report = runtime.validate_bundle(
                handoff_path=FIXTURES / "valid_ta06_prose_handoff.json",
                reader_path=FIXTURES / "valid_prose_reader_contract.json",
                sidecar_path=sidecar_path,
                article_path=path,
            )
        self.assertEqual(report["status"], "pass", report["errors"])

    def test_runtime_recomputes_sidecar_character_count(self):
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["delivery_length_exception"]["measured_characters"] += 1
        with tempfile.TemporaryDirectory() as tmp:
            sidecar_path = Path(tmp) / "prose_audit_sidecar.json"
            sidecar_path.write_text(
                json.dumps(sidecar, ensure_ascii=False), encoding="utf-8"
            )
            report = runtime.validate_bundle(
                handoff_path=FIXTURES / "valid_ta06_prose_handoff.json",
                reader_path=FIXTURES / "valid_prose_reader_contract.json",
                sidecar_path=sidecar_path,
                article_path=FIXTURES / "20260815_demo-explainer.md",
            )
        self.assertEqual(report["status"], "fail")
        self.assertTrue(
            any("must equal recomputed article count 141" in error for error in report["errors"])
        )

    def test_runtime_rejects_same_length_article_swap(self):
        article = (FIXTURES / "20260815_demo-explainer.md").read_text(encoding="utf-8")
        article = article.replace("主要", "次要", 1)
        self.assertNotEqual(
            article,
            (FIXTURES / "20260815_demo-explainer.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            runtime.content_character_count(article),
            runtime.content_character_count(
                (FIXTURES / "20260815_demo-explainer.md").read_text(encoding="utf-8")
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            article_path = Path(tmp) / "20260815_demo-explainer.md"
            article_path.write_text(article, encoding="utf-8")
            report = runtime.validate_bundle(
                handoff_path=FIXTURES / "valid_ta06_prose_handoff.json",
                reader_path=FIXTURES / "valid_prose_reader_contract.json",
                sidecar_path=FIXTURES / "valid_prose_audit_sidecar.json",
                article_path=article_path,
            )
        self.assertEqual(report["status"], "fail")
        self.assertTrue(
            any("does not match exact article bytes" in error for error in report["errors"])
        )

    def test_runtime_rejects_unnecessary_sidecar_exception(self):
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["delivery_length_exception"]["granted"] = True
        sidecar["delivery_length_exception"]["reason"] = "Not actually needed."
        with tempfile.TemporaryDirectory() as tmp:
            sidecar_path = Path(tmp) / "prose_audit_sidecar.json"
            sidecar_path.write_text(
                json.dumps(sidecar, ensure_ascii=False), encoding="utf-8"
            )
            report = runtime.validate_bundle(
                handoff_path=FIXTURES / "valid_ta06_prose_handoff.json",
                reader_path=FIXTURES / "valid_prose_reader_contract.json",
                sidecar_path=sidecar_path,
                article_path=FIXTURES / "20260815_demo-explainer.md",
            )
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("unnecessary" in error for error in report["errors"]))

    def test_legacy_sidecar_remains_valid_below_ceiling(self):
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["contract_version"] = "1.0"
        del sidecar["delivery_length_exception"]
        del sidecar["article_sha256"]
        with tempfile.TemporaryDirectory() as tmp:
            sidecar_path = Path(tmp) / "prose_audit_sidecar.json"
            sidecar_path.write_text(
                json.dumps(sidecar, ensure_ascii=False), encoding="utf-8"
            )
            report = runtime.validate_bundle(
                handoff_path=FIXTURES / "valid_ta06_prose_handoff.json",
                reader_path=FIXTURES / "valid_prose_reader_contract.json",
                sidecar_path=sidecar_path,
                article_path=FIXTURES / "20260815_demo-explainer.md",
            )
        self.assertEqual(report["status"], "pass", report["errors"])

    def test_legacy_sidecar_rejects_null_v11_only_fields(self):
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["contract_version"] = "1.0"
        sidecar["delivery_length_exception"] = None
        sidecar["article_sha256"] = None
        report = self.validate_fixture_with_sidecar(sidecar)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(
            any("must not contain article_sha256" in error for error in report["errors"])
        )
        self.assertTrue(
            any(
                "must not contain delivery_length_exception" in error
                for error in report["errors"]
            )
        )

    def test_legacy_sidecar_cannot_authorize_over_limit_article(self):
        article = (FIXTURES / "20260815_demo-explainer.md").read_text(encoding="utf-8")
        article = self.with_content(article, "研" * 4001)
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["contract_version"] = "1.0"
        del sidecar["delivery_length_exception"]
        del sidecar["article_sha256"]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            article_path = tmp / "20260815_demo-explainer.md"
            sidecar_path = tmp / "prose_audit_sidecar.json"
            article_path.write_text(article, encoding="utf-8")
            sidecar_path.write_text(
                json.dumps(sidecar, ensure_ascii=False), encoding="utf-8"
            )
            report = runtime.validate_bundle(
                handoff_path=FIXTURES / "valid_ta06_prose_handoff.json",
                reader_path=FIXTURES / "valid_prose_reader_contract.json",
                sidecar_path=sidecar_path,
                article_path=article_path,
            )
        self.assertEqual(report["status"], "fail")
        self.assertTrue(
            any("v1.0 cannot authorize" in error for error in report["errors"])
        )

    def test_runtime_argument_override_is_rejected(self):
        report = runtime.validate_bundle(
            handoff_path=FIXTURES / "valid_ta06_prose_handoff.json",
            reader_path=FIXTURES / "valid_prose_reader_contract.json",
            sidecar_path=FIXTURES / "valid_prose_audit_sidecar.json",
            article_path=FIXTURES / "20260815_demo-explainer.md",
            allow_large_literature=True,
            length_exception_reason="Unbound override.",
        )
        self.assertEqual(report["status"], "fail")
        self.assertTrue(
            any("must come from the bound audit sidecar" in error for error in report["errors"])
        )

    def test_runtime_cli_override_is_rejected(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            runtime.main(
                [
                    "--handoff",
                    str(FIXTURES / "valid_ta06_prose_handoff.json"),
                    "--reader-contract",
                    str(FIXTURES / "valid_prose_reader_contract.json"),
                    "--audit-sidecar",
                    str(FIXTURES / "valid_prose_audit_sidecar.json"),
                    "--article",
                    str(FIXTURES / "20260815_demo-explainer.md"),
                    "--allow-large-literature",
                ]
            )
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("must come from the audit sidecar", stderr.getvalue())

    def test_mechanical_lint_rules_recompute_all_five_categories(self):
        cases = {
            "long_sentence": self.lint_article("研" * 40 + "。"),
            "long_paragraph": self.lint_article("短句。" * 70),
            "de_chain": self.lint_article("研究方法的品質的判斷的依據清楚。"),
            "passive_voice": self.lint_article("資料受到限制。"),
            "hedge_stack": self.lint_article("結果可能有利，但也許仍不穩定。"),
        }
        for category, article in cases.items():
            with self.subTest(category=category):
                self.assertIn(
                    category,
                    runtime.computed_zh_hant_lint_categories(article),
                )

    def test_mechanical_lint_avoids_common_punctuation_and_short_prose(self):
        article = self.lint_article(
            "研究的結果顯示，不同的族群有不同的反應。"
            "棉被可以保暖。"
            "這份清單為研究所有資料的索引。"
            "結果可能有利。"
        )
        self.assertEqual(runtime.computed_zh_hant_lint_categories(article), set())

    def test_missing_recomputed_lint_category_warns_without_blocking(self):
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["lint_warnings"] = []
        report = self.validate_fixture_with_sidecar(sidecar)
        self.assertEqual(report["status"], "pass")
        self.assertTrue(
            any(
                "missing recomputed categories: ['long_sentence']" in error
                for error in report["warnings"]
            )
        )

    def test_uncomputed_mechanical_lint_category_warns_without_blocking(self):
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["lint_warnings"].append(
            {
                "category": "passive_voice",
                "location": "## 內容，第 1 段",
                "message": "自報但文章沒有可重算的被動語態。",
            }
        )
        report = self.validate_fixture_with_sidecar(sidecar)
        self.assertEqual(report["status"], "pass")
        self.assertTrue(
            any(
                "declares uncomputed categories: ['passive_voice']" in error
                for error in report["warnings"]
            )
        )

    def test_semantic_lint_categories_remain_human_audited(self):
        sidecar = load_json("valid_prose_audit_sidecar.json")
        sidecar["lint_warnings"].append(
            {
                "category": "vague_pronoun",
                "location": "## 內容，第 1 段",
                "message": "人工判斷此處指涉可能模糊。",
            }
        )
        report = self.validate_fixture_with_sidecar(sidecar)
        self.assertEqual(report["status"], "pass", report["errors"])


if __name__ == "__main__":
    unittest.main()
