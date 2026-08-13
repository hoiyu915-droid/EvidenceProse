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

from scripts.validate_registry import ValidationError, validate  # noqa: E402


@contextmanager
def copied_registry() -> Path:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "EvidenceProse"
        shutil.copytree(ROOT / "data", root / "data")
        shutil.copytree(ROOT / "schemas", root / "schemas")
        yield root


def rewrite_json(path: Path, document: object) -> None:
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class RegistryTests(unittest.TestCase):
    def test_registry_is_internally_consistent(self) -> None:
        self.assertEqual(
            validate(),
            {
                "samples": 7,
                "observations": 99,
                "rules": 24,
                "stable_rules": 0,
                "voice_rules": 5,
                "stable_voice_rules": 0,
                "batches": 7,
                "artifact_receipts": 25,
                "cards": 36,
                "contamination_notes": 20,
                "historical_text_wording_divergences": 36,
                "content_truth_failures": 0,
                "render_fidelity_failures": 8,
                "reader_outcome_blocking_cards": 8,
            },
        )

    def test_sample_article_is_preserved(self) -> None:
        sample = json.loads((ROOT / "data/samples/S001/sample.json").read_text(encoding="utf-8"))
        article = (ROOT / sample["article_path"]).read_text(encoding="utf-8")
        self.assertIn("一年後約三分之二恢復正常", article)
        self.assertIn("OR 1.054", article)
        self.assertIn("最後更新：20260810", article)

    def test_second_sample_and_card_binding_are_preserved(self) -> None:
        sample = json.loads((ROOT / "data/samples/S002/sample.json").read_text(encoding="utf-8"))
        article = (ROOT / sample["article_path"]).read_text(encoding="utf-8")
        storyboard = json.loads((ROOT / sample["card_storyboard_path"]).read_text(encoding="utf-8"))
        self.assertIn("56項研究看斷貨", article)
        self.assertEqual(storyboard["canonical_queue"]["plan_id"], "TA07-20260810-010543-18237b69")
        self.assertEqual(storyboard["summary"]["historical_text_wording_divergence"], 6)
        self.assertTrue(all(card["content_truth_audit"]["status"] == "pass" for card in storyboard["cards"]))
        self.assertEqual(storyboard["summary"]["render_fidelity_failures"], 0)
        c01 = next(card for card in storyboard["cards"] if card["card_id"] == "C01")
        c05 = next(card for card in storyboard["cards"] if card["card_id"] == "C05")
        self.assertEqual(c01["render_fidelity_audit"]["status"], "pass")
        self.assertEqual(c05["render_fidelity_audit"]["status"], "pass")
        self.assertTrue(all(card.get("historical_text_comparison", {}).get("status") == "wording_divergence" for card in storyboard["cards"]))
        self.assertTrue(all(card["historical_text_comparison"]["gating"] is False for card in storyboard["cards"]))

    def test_narrative_review_does_not_invent_not_applicable_denominators(self) -> None:
        sample = json.loads((ROOT / "data/samples/S002/sample.json").read_text(encoding="utf-8"))
        profile = sample["study_profile"]
        self.assertIsNone(profile["total_participants"])
        self.assertIn("total_participants", profile["not_applicable_reasons"])

    def test_library_first_source_resolution_is_recorded_for_every_sample(self) -> None:
        for sample_id in json.loads((ROOT / "data/registry.json").read_text(encoding="utf-8"))["sample_ids"]:
            sample = json.loads((ROOT / f"data/samples/{sample_id}/sample.json").read_text(encoding="utf-8"))
            resolution = sample["source_resolution"]
            primary = [search for search in resolution["searches"] if search["target_kind"] == "source_pdf"]
            self.assertEqual([search["strategy"] for search in primary], ["doi", "exact_title", "filename"][: len(primary)])
            self.assertEqual(resolution["selected_pdf"]["sha256"], sample["source"]["pdf_sha256"])
            if resolution["selected_pdf"]["origin"] == "library":
                version_state = resolution["selected_pdf"]["version_state"]
                self.assertIn(version_state, {"recorded", "not_exposed"})
                if version_state == "recorded":
                    self.assertGreaterEqual(int(resolution["selected_pdf"]["version"]), 0)
                else:
                    self.assertIsNone(resolution["selected_pdf"]["version"])

    def test_unexposed_library_version_is_valid_when_null(self) -> None:
        with copied_registry() as root:
            path = root / "data/samples/S001/sample.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["source_resolution"]["selected_pdf"]["version_state"] = "not_exposed"
            document["source_resolution"]["selected_pdf"]["version"] = None
            rewrite_json(path, document)
            self.assertEqual(validate(root)["samples"], 7)

    def test_source_resolution_search_order_is_enforced(self) -> None:
        with copied_registry() as root:
            path = root / "data/samples/S001/sample.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            searches = document["source_resolution"]["searches"]
            searches[0], searches[1] = searches[1], searches[0]
            searches[0]["priority"], searches[1]["priority"] = 1, 2
            rewrite_json(path, document)
            with self.assertRaisesRegex(ValidationError, "search order must be DOI"):
                validate(root)

    def test_selected_source_digest_must_match_verified_pdf(self) -> None:
        with copied_registry() as root:
            path = root / "data/samples/S001/sample.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["source_resolution"]["selected_pdf"]["sha256"] = "0" * 64
            rewrite_json(path, document)
            with self.assertRaisesRegex(ValidationError, "does not match source pdf_sha256"):
                validate(root)

    def test_content_truth_and_render_fidelity_are_not_double_counted(self) -> None:
        for sample_id in ("S002", "S003", "S004", "S005", "S006", "S007"):
            storyboard = json.loads((ROOT / f"data/samples/{sample_id}/card_storyboard.json").read_text(encoding="utf-8"))
            self.assertTrue(all(card["content_truth_audit"]["status"] == "pass" for card in storyboard["cards"]))
        storyboard = json.loads((ROOT / "data/samples/S003/card_storyboard.json").read_text(encoding="utf-8"))
        c03 = next(card for card in storyboard["cards"] if card["card_id"] == "C03")
        self.assertEqual(c03["content_truth_audit"]["status"], "pass")
        self.assertEqual(c03["render_fidelity_audit"]["status"], "fail")

    def test_materiality_and_reader_contract_are_required(self) -> None:
        for sample_id in ("S002", "S003", "S004", "S005", "S006", "S007"):
            storyboard = json.loads((ROOT / f"data/samples/{sample_id}/card_storyboard.json").read_text(encoding="utf-8"))
            self.assertTrue(storyboard["audit_policy"]["materiality_test"]["gate_only_substantive"])
            self.assertFalse(storyboard["audit_policy"]["engineering_conformance_is_gate"])
            self.assertEqual(
                set(storyboard["reader_contract"]),
                {"central_claim", "evidence_weight", "limitations", "applicability", "misuse_boundaries"},
            )

    def test_reader_outcome_blocking_ids_follow_substantive_render_failures(self) -> None:
        expected = {
            "S002": [],
            "S003": ["C03"],
            "S004": ["C05"],
            "S005": ["C02", "C05"],
            "S006": ["C01", "C06"],
            "S007": ["C03", "C06"],
        }
        for sample_id, blocking_ids in expected.items():
            storyboard = json.loads((ROOT / f"data/samples/{sample_id}/card_storyboard.json").read_text(encoding="utf-8"))
            self.assertEqual(storyboard["summary"]["derived_reader_outcome"]["blocking_card_ids"], blocking_ids)

    def test_third_sample_preserves_model_and_source_discrepancies(self) -> None:
        sample = json.loads((ROOT / "data/samples/S003/sample.json").read_text(encoding="utf-8"))
        article = (ROOT / sample["article_path"]).read_text(encoding="utf-8")
        storyboard = json.loads((ROOT / sample["card_storyboard_path"]).read_text(encoding="utf-8"))
        self.assertIn("正文報告p=0.055,對應表格數值則為0.06", article)
        self.assertIn("流程圖(Fig. 2)標示高頻率組n=64", article)
        self.assertEqual(storyboard["canonical_queue"]["plan_id"], "TP_20260810_s44276_026_00246_6")
        self.assertEqual(storyboard["summary"]["content_truth_failures"], 0)
        self.assertEqual(storyboard["summary"]["render_fidelity_failures"], 1)
        c03 = next(card for card in storyboard["cards"] if card["card_id"] == "C03")
        self.assertEqual(c03["content_truth_audit"]["status"], "pass")
        self.assertEqual(c03["render_fidelity_audit"]["status"], "fail")
        self.assertIn("6", " ".join(c03["historical_text_comparison"]["differences"]))

    def test_domain_and_denominator_rules_remain_hypotheses(self) -> None:
        rules = {rule["rule_id"]: rule for rule in json.loads((ROOT / "data/rules/rules.json").read_text(encoding="utf-8"))["rules"]}
        self.assertEqual(rules["R012"]["status"], "hypothesis")
        self.assertEqual(rules["R013"]["status"], "hypothesis")

    def test_fourth_sample_preserves_proxy_and_render_boundaries(self) -> None:
        sample = json.loads((ROOT / "data/samples/S004/sample.json").read_text(encoding="utf-8"))
        article = (ROOT / sample["article_path"]).read_text(encoding="utf-8")
        storyboard = json.loads((ROOT / sample["card_storyboard_path"]).read_text(encoding="utf-8"))
        self.assertIn("這是一張「研究地圖」，不是效果大小排名", article)
        self.assertEqual(storyboard["canonical_queue"]["plan_id"], "JFA2_19_e70197")
        self.assertEqual(storyboard["summary"]["content_truth_failures"], 0)
        c05 = next(card for card in storyboard["cards"] if card["card_id"] == "C05")
        self.assertEqual(c05["content_truth_audit"]["status"], "pass")
        self.assertIn("158", " ".join(c05["render_fidelity_audit"]["violations"]))
        self.assertIn("142", " ".join(c05["render_fidelity_audit"]["violations"]))

    def test_fifth_sample_preserves_trace_and_visual_data_failures(self) -> None:
        sample = json.loads((ROOT / "data/samples/S005/sample.json").read_text(encoding="utf-8"))
        article = (ROOT / sample["article_path"]).read_text(encoding="utf-8")
        storyboard = json.loads((ROOT / sample["card_storyboard_path"]).read_text(encoding="utf-8"))
        self.assertIn("答案對，不代表整條證據鏈都對", article)
        self.assertIn("三個正交的схема軸", article)
        self.assertEqual(storyboard["canonical_queue"]["plan_id"], "TP_20260811_2608_07370")
        self.assertEqual(storyboard["summary"]["content_truth_failures"], 0)
        self.assertEqual(storyboard["summary"]["targeted_correction_ids"], ["C02", "C05"])
        c01 = next(card for card in storyboard["cards"] if card["card_id"] == "C01")
        c02 = next(card for card in storyboard["cards"] if card["card_id"] == "C02")
        c05 = next(card for card in storyboard["cards"] if card["card_id"] == "C05")
        self.assertEqual(c01["render_fidelity_audit"]["status"], "pass")
        self.assertEqual(c02["render_fidelity_audit"]["status"], "fail")
        self.assertEqual(c05["render_fidelity_audit"]["status"], "fail")
        self.assertIn("ICCV", " ".join(c05["render_fidelity_audit"]["violations"]))

    def test_sixth_sample_preserves_title_binding_and_measurement_failures(self) -> None:
        sample = json.loads((ROOT / "data/samples/S006/sample.json").read_text(encoding="utf-8"))
        article = (ROOT / sample["article_path"]).read_text(encoding="utf-8")
        storyboard = json.loads((ROOT / sample["card_storyboard_path"]).read_text(encoding="utf-8"))
        self.assertIn("體能表現如何預測老年人全因死亡率", article)
        self.assertIn("13,423", article)
        self.assertEqual(storyboard["canonical_queue"]["plan_id"], "TA07-20260812-014757-3db3a7b4")
        self.assertEqual(storyboard["summary"]["content_truth_failures"], 0)
        self.assertEqual(storyboard["summary"]["targeted_correction_ids"], ["C01", "C06"])
        c01 = next(card for card in storyboard["cards"] if card["card_id"] == "C01")
        c06 = next(card for card in storyboard["cards"] if card["card_id"] == "C06")
        self.assertIn("6分鐘", " ".join(c01["render_fidelity_audit"]["violations"]))
        self.assertIn("膝伸展", " ".join(c06["render_fidelity_audit"]["violations"]))

    def test_sixth_batch_adds_calibrated_quantitative_rules(self) -> None:
        rules = {rule["rule_id"]: rule for rule in json.loads((ROOT / "data/rules/rules.json").read_text(encoding="utf-8"))["rules"]}
        self.assertEqual(rules["R019"]["status"], "hypothesis")
        self.assertEqual(rules["R020"]["status"], "hypothesis")
        self.assertEqual(rules["R019"]["support"][0]["sample_id"], "S006")
        self.assertEqual(rules["R020"]["support"][0]["observation_ids"], ["O015"])

    def test_seventh_sample_preserves_subgroup_and_pathway_failures(self) -> None:
        sample = json.loads((ROOT / "data/samples/S007/sample.json").read_text(encoding="utf-8"))
        article = (ROOT / sample["article_path"]).read_text(encoding="utf-8")
        storyboard = json.loads((ROOT / sample["card_storyboard_path"]).read_text(encoding="utf-8"))
        self.assertIn("數位介入對膀胱過動症症狀與生活品質的效果", article)
        self.assertIn("7 項 RCT、544 人", article)
        self.assertEqual(storyboard["canonical_queue"]["plan_id"], "TA07-20260812-041247-175271ce")
        self.assertEqual(storyboard["summary"]["content_truth_failures"], 0)
        self.assertEqual(storyboard["summary"]["targeted_correction_ids"], ["C03", "C06"])
        for card_id in ("C02", "C04", "C05"):
            card = next(card for card in storyboard["cards"] if card["card_id"] == card_id)
            self.assertEqual(card["render_fidelity_audit"]["status"], "pass")
        c03 = next(card for card in storyboard["cards"] if card["card_id"] == "C03")
        c06 = next(card for card in storyboard["cards"] if card["card_id"] == "C06")
        self.assertIn("遠距照護", " ".join(c03["render_fidelity_audit"]["violations"]))
        self.assertIn("治療分線框架", " ".join(c06["render_fidelity_audit"]["violations"]))

    def test_historical_wording_divergence_does_not_gate_render_fidelity(self) -> None:
        storyboard = json.loads((ROOT / "data/samples/S007/card_storyboard.json").read_text(encoding="utf-8"))
        c01 = next(card for card in storyboard["cards"] if card["card_id"] == "C01")
        c05 = next(card for card in storyboard["cards"] if card["card_id"] == "C05")
        self.assertEqual(c01["render_fidelity_audit"]["status"], "pass")
        self.assertEqual(c05["render_fidelity_audit"]["status"], "pass")
        self.assertEqual(c01["historical_text_comparison"]["status"], "wording_divergence")
        self.assertEqual(c05["historical_text_comparison"]["status"], "wording_divergence")
        self.assertFalse(c01["historical_text_comparison"]["gating"])
        self.assertFalse(c05["historical_text_comparison"]["gating"])

    def test_historical_wording_comparison_cannot_become_a_gate(self) -> None:
        with copied_registry() as root:
            path = root / "data/samples/S007/card_storyboard.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["cards"][0]["historical_text_comparison"]["gating"] = True
            rewrite_json(path, document)
            with self.assertRaisesRegex(ValidationError, "historical wording comparison cannot be gating"):
                validate(root)

    def test_reader_outcome_blockers_must_match_substantive_render_failures(self) -> None:
        with copied_registry() as root:
            path = root / "data/samples/S003/card_storyboard.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["summary"]["derived_reader_outcome"]["blocking_card_ids"] = ["C01"]
            rewrite_json(path, document)
            with self.assertRaisesRegex(ValidationError, "reader blocking cards must equal substantive render failures"):
                validate(root)

    def test_seventh_batch_adds_subgroup_and_adherence_rules(self) -> None:
        rules = {rule["rule_id"]: rule for rule in json.loads((ROOT / "data/rules/rules.json").read_text(encoding="utf-8"))["rules"]}
        for rule_id in ("R021", "R022", "R023", "R024"):
            self.assertEqual(rules[rule_id]["status"], "hypothesis")
            self.assertEqual(rules[rule_id]["support"][0]["sample_id"], "S007")

    def test_method_and_voice_layers_are_recorded_separately(self) -> None:
        registry = json.loads((ROOT / "data/registry.json").read_text(encoding="utf-8"))
        batches = json.loads((ROOT / "data/batch_results.json").read_text(encoding="utf-8"))
        voice_rules = json.loads((ROOT / "data/voice/voice_rules.json").read_text(encoding="utf-8"))["rules"]
        self.assertEqual(registry["batch_ids"], ["B001", "B002", "B003", "B004", "B005", "B006", "B007"])
        self.assertEqual(registry["voice_rule_ids"], ["V001", "V002", "V003", "V004", "V005"])
        self.assertEqual([batch["sample_id"] for batch in batches["batches"]], ["S001", "S002", "S003", "S004", "S005", "S006", "S007"])
        self.assertTrue(all(rule["status"] == "hypothesis" for rule in voice_rules))
        self.assertNotIn("V001", registry["rule_ids"])

    def test_no_rule_is_prematurely_stable(self) -> None:
        rules = json.loads((ROOT / "data/rules/rules.json").read_text(encoding="utf-8"))["rules"]
        self.assertTrue(rules)
        self.assertFalse(any(rule["status"] == "stable" for rule in rules))

    def test_article_digest_detects_observed_prose_mutation(self) -> None:
        with copied_registry() as root:
            article_path = root / "data/samples/S001/article.md"
            article_path.write_text(article_path.read_text(encoding="utf-8") + "\nmutated\n", encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "article digest mismatch"):
                validate(root)

    def test_unregistered_sample_directory_is_rejected(self) -> None:
        with copied_registry() as root:
            shutil.copytree(root / "data/samples/S007", root / "data/samples/S008")
            with self.assertRaisesRegex(ValidationError, "do not exactly match sample directories"):
                validate(root)

    def test_rule_timestamp_cannot_predate_its_evidence(self) -> None:
        with copied_registry() as root:
            path = root / "data/rules/rules.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["rules"][0]["last_updated"] = "2026-08-10"
            rewrite_json(path, document)
            with self.assertRaisesRegex(ValidationError, "predates referenced evidence"):
                validate(root)

    def test_batch_contamination_ledger_cannot_drift(self) -> None:
        with copied_registry() as root:
            path = root / "data/batch_results.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["batches"][4]["contamination_note_ids"] = ["C001"]
            rewrite_json(path, document)
            with self.assertRaisesRegex(ValidationError, "contamination notes do not match"):
                validate(root)

    def test_batch_card_counts_must_match_storyboard(self) -> None:
        with copied_registry() as root:
            path = root / "data/batch_results.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["batches"][4]["companion_audit"]["content_truth_failures"] = 1
            rewrite_json(path, document)
            with self.assertRaisesRegex(ValidationError, "does not match storyboard"):
                validate(root)

    def test_complete_schema_catalog_is_present(self) -> None:
        self.assertEqual(
            {path.name for path in (ROOT / "schemas").glob("*.json")},
            {
                "batch_results.schema.json",
                "card_storyboard.schema.json",
                "registry.schema.json",
                "rule.schema.json",
                "rule_catalog.schema.json",
                "sample.schema.json",
                "voice_rule.schema.json",
                "voice_rule_catalog.schema.json",
            },
        )


if __name__ == "__main__":
    unittest.main()
