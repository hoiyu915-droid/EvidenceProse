import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_probe_post_audit.py"
SPEC = importlib.util.spec_from_file_location("validate_probe_post_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ProbePostAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(
            (ROOT / "fixtures" / "valid_probe_post_audit_bundle.json").read_text(
                encoding="utf-8"
            )
        )
        cls.legacy_fixture = json.loads(
            (
                ROOT
                / "fixtures"
                / "legacy_valid_probe_post_audit_bundle_v1.0.json"
            ).read_text(encoding="utf-8")
        )

    def validate(self, bundle):
        return MODULE.validate_bundle(
            copy.deepcopy(bundle), base_dir=ROOT / "fixtures"
        )

    def copied_fixture(self):
        temporary = tempfile.TemporaryDirectory()
        fixture_root = Path(temporary.name) / "fixtures"
        shutil.copytree(ROOT / "fixtures", fixture_root)
        bundle = json.loads(
            (fixture_root / "valid_probe_post_audit_bundle.json").read_text(
                encoding="utf-8"
            )
        )
        return temporary, fixture_root, bundle

    def test_valid_v11_fixture_passes(self):
        self.assertEqual(self.validate(self.fixture), [])

    def test_legacy_v10_fixture_remains_valid(self):
        self.assertEqual(
            MODULE.validate_bundle(copy.deepcopy(self.legacy_fixture)), []
        )

    def test_hard_finding_cannot_be_accepted_warning(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["audit_findings"][0]["status"] = "accepted_warning"
        errors = self.validate(bundle)
        self.assertTrue(
            any("hard finding A017 must be resolved" in error for error in errors)
        )

    def test_unexpected_edit_scope_fails(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["operations"][0]["actual_changed_element_ids"].append(
            "C99.decorative_chart"
        )
        errors = self.validate(bundle)
        self.assertTrue(any("outside declared scope" in error for error in errors))

    def test_required_claim_cannot_disappear(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["coverage"]["represented_claim_ids"].remove("LIM_03")
        errors = self.validate(bundle)
        self.assertTrue(
            any(
                "required claims lack representation or disposition" in error
                for error in errors
            )
        )

    def test_article_rewrite_cannot_add_claim(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["article_rewrite"]["new_claim_ids"] = ["CLM_NEW"]
        errors = self.validate(bundle)
        self.assertTrue(
            any("new_claim_ids must be empty" in error for error in errors)
        )

    def test_pass_gate_must_match_failed_guard(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["semantic_guard"]["numeric_fidelity"] = "fail"
        errors = self.validate(bundle)
        self.assertTrue(
            any("final_gate.status must be fail" in error for error in errors)
        )

    def test_computed_diff_catches_undeclared_change(self):
        temporary, fixture_root, bundle = self.copied_fixture()
        self.addCleanup(temporary.cleanup)
        output_path = fixture_root / "probe" / "output_cards.json"
        output = json.loads(output_path.read_text(encoding="utf-8"))
        output["cards"][0]["elements"][4]["text"] += " 未宣告改動。"
        output_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        errors = MODULE.validate_bundle(bundle, base_dir=fixture_root)
        self.assertTrue(
            any(
                "computed artifact diff contains undeclared changed elements"
                in error
                for error in errors
            )
        )

    def test_card_digest_must_bind_actual_source_artifact(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["inputs"]["source_card_digests"]["C01"] = "0" * 64
        errors = self.validate(bundle)
        self.assertTrue(
            any(
                "does not match source artifact" in error for error in errors
            )
        )

    def test_immutable_asset_byte_mutation_fails(self):
        temporary, fixture_root, bundle = self.copied_fixture()
        self.addCleanup(temporary.cleanup)
        asset_path = (
            fixture_root
            / "probe"
            / "assets_after"
            / "evidence_plot.svg"
        )
        asset_path.write_text(
            asset_path.read_text(encoding="utf-8") + "\n<!-- mutation -->\n",
            encoding="utf-8",
        )
        errors = MODULE.validate_bundle(bundle, base_dir=fixture_root)
        self.assertTrue(
            any("immutable asset bytes changed" in error for error in errors)
        )

    def test_immutable_asset_cannot_be_regenerated(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["artifact_verification"]["immutable_assets"][0][
            "regenerated"
        ] = True
        errors = self.validate(bundle)
        self.assertTrue(any(".regenerated must be false" in error for error in errors))

    def test_reader_must_be_isolated_from_probe(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["reader_reconstruction"]["assessor"][
            "independent_from_probe"
        ] = False
        errors = self.validate(bundle)
        self.assertTrue(
            any("independent_from_probe must be true" in error for error in errors)
        )

    def test_reader_quiz_requires_minimum_categories(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["reader_reconstruction"]["required_categories"].remove(
            "causal_boundary"
        )
        errors = self.validate(bundle)
        self.assertTrue(
            any("lacks minimum categories" in error for error in errors)
        )

    def test_answerable_reader_question_requires_package_support(self):
        bundle = copy.deepcopy(self.fixture)
        question = bundle["reader_reconstruction"]["questions"][0]
        question["supporting_article_snippets"] = []
        question["supporting_card_element_ids"] = []
        errors = self.validate(bundle)
        self.assertTrue(
            any("must cite final-package support" in error for error in errors)
        )

    def test_should_be_na_question_cannot_be_answered(self):
        bundle = copy.deepcopy(self.fixture)
        question = bundle["reader_reconstruction"]["questions"][-1]
        question["observed_answerability"] = "answered"
        errors = self.validate(bundle)
        self.assertTrue(
            any(
                "should be NA but isolated reader produced an answer" in error
                for error in errors
            )
        )

    def test_reader_must_reconstruct_every_required_claim(self):
        bundle = copy.deepcopy(self.fixture)
        for question in bundle["reader_reconstruction"]["questions"]:
            question["reconstructed_claim_ids"] = [
                claim_id
                for claim_id in question["reconstructed_claim_ids"]
                if claim_id != "CLM_22"
            ]
        errors = self.validate(bundle)
        self.assertTrue(
            any(
                "failed to reconstruct required claims" in error
                for error in errors
            )
        )

    def test_article_snippet_must_exist_in_final_article(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["reader_reconstruction"]["questions"][0][
            "supporting_article_snippets"
        ] = ["這句根本不在文章裡"]
        errors = self.validate(bundle)
        self.assertTrue(
            any("snippet is absent from output article" in error for error in errors)
        )

    def test_reader_failure_forces_final_gate_failure(self):
        bundle = copy.deepcopy(self.fixture)
        bundle["reader_reconstruction"]["questions"][0]["status"] = "fail"
        bundle["reader_reconstruction"]["status"] = "fail"
        errors = self.validate(bundle)
        self.assertTrue(
            any("final_gate.status must be fail" in error for error in errors)
        )


if __name__ == "__main__":
    unittest.main()
