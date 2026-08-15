import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "finalize_probe_te_queue.py"
SPEC = importlib.util.spec_from_file_location("finalize_probe_te_queue", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
FIXTURE = ROOT / "fixtures" / "probe_te_unsealed_queue.json"


class ProbeTEDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def finalize(
        self,
        value=None,
        name="TP_demo__combined_content_truth_edit_unsealed(2).json",
    ):
        return MODULE.reseal_queue(
            copy.deepcopy(value or self.raw), source_name=name
        )

    def test_unsealed_queue_autoreseals_to_te_direct_delivery(self):
        queue, name = self.finalize()
        self.assertEqual(name, "TE_demo__imagegen_queue.json")
        self.assertEqual(MODULE.validate_resealed_queue(queue, filename=name), [])
        self.assertEqual(queue["workflow_state"], "generate_authorized")
        self.assertTrue(queue["generation_authorized"])
        self.assertEqual(
            queue["preparation_attestation"]["artifact_phase"],
            "probe_resealed",
        )
        self.assertEqual(queue["content_truth_merge"]["status"], "SEALED")
        self.assertEqual(
            queue["probe_delivery"]["delivery_order"],
            ["science_explainer_textedit", "te_json_attachment"],
        )

    def test_reseal_recomputes_prompt_and_dependency_digests(self):
        queue, _ = self.finalize()
        first = queue["items"][0]
        second = queue["items"][1]
        self.assertEqual(
            first["prompt_char_count"], len(first["imagegen_args"]["prompt"])
        )
        self.assertEqual(
            first["imagegen_args_digest"],
            MODULE.canonical_digest(first["imagegen_args"]),
        )
        self.assertNotEqual(
            first["renderer_payload_digest"],
            self.raw["items"][0]["renderer_payload_digest"],
        )
        dep = second["series_reference_dependency"]
        self.assertEqual(
            dep["source_imagegen_args_digest"], first["imagegen_args_digest"]
        )
        self.assertEqual(
            dep["source_renderer_payload_digest"],
            first["renderer_payload_digest"],
        )
        self.assertEqual(
            dep["source_queue_item_identity_digest"],
            MODULE.queue_item_identity_digest(first),
        )

    def test_final_te_queue_contains_no_unsealed_control_tokens(self):
        queue, _ = self.finalize()
        serialized = json.dumps(queue, ensure_ascii=False, sort_keys=True)
        for token in MODULE.STALE_TOKENS:
            self.assertNotIn(token, serialized)

    def test_reseal_requires_no_user_confirmation(self):
        queue, _ = self.finalize()
        self.assertFalse(
            queue["probe_delivery"]["user_confirmation_required_for_reseal"]
        )
        self.assertTrue(
            queue["artifact_execution_contract"]["dispatch_immediately"]
        )

    def test_prompt_over_budget_fails_closed(self):
        raw = copy.deepcopy(self.raw)
        raw["items"][0]["imagegen_args"]["prompt"] += (
            "x" * MODULE.MAX_PROMPT_CHARS
        )
        with self.assertRaisesRegex(ValueError, "exceeds"):
            self.finalize(raw)

    def test_missing_series_dependency_fails_closed(self):
        raw = copy.deepcopy(self.raw)
        raw["items"][1].pop("series_reference_dependency")
        with self.assertRaisesRegex(
            ValueError, "series_reference_dependency missing"
        ):
            self.finalize(raw)

    def test_validator_rejects_wrong_prefix(self):
        queue, _ = self.finalize()
        errors = MODULE.validate_resealed_queue(queue, filename="TP_demo.json")
        self.assertIn("final JSON filename must start with TE_", errors)

    def test_validator_rejects_delivery_order_drift(self):
        queue, name = self.finalize()
        queue["probe_delivery"]["delivery_order"].reverse()
        queue.pop("queue_digest")
        queue["queue_digest"] = MODULE.canonical_digest(queue)
        errors = MODULE.validate_resealed_queue(queue, filename=name)
        self.assertIn("Probe delivery naming/order contract drift", errors)


if __name__ == "__main__":
    unittest.main()
