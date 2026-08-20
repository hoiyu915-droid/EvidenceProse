from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_rca_policy.py"
SPEC = importlib.util.spec_from_file_location("validate_rca_policy", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RcaPolicyTests(unittest.TestCase):
    def copy_surface_tree(self, base: Path) -> None:
        for relative in (
            Path("policies/rca/current.json"),
            Path("policies/rca/policy_v1.3.0.json"),
            MODULE.ACTIVE_CONTRACT_REL,
            *MODULE.LEGACY_CONTRACT_RELS,
            MODULE.ACTIVE_SCHEMA_REL,
            MODULE.ACTIVE_FIXTURE_REL,
            MODULE.ACTIVE_DOC_REL,
            MODULE.VERSIONED_DOC_REL,
        ):
            source = ROOT / relative
            target = base / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def test_current_policy_manifest_and_policy_are_synchronized(self):
        self.assertEqual(MODULE.validate_current_policy(ROOT), [])
        bundle = MODULE.load_current_bundle(ROOT)
        self.assertEqual(
            bundle["manifest"]["policy_sha256"],
            MODULE.policy_digest(bundle["policy"]),
        )
        self.assertNotIn("source_surface", bundle["manifest"])
        self.assertNotIn("topology", bundle["manifest"])
        self.assertNotIn("verdict_mapping", bundle["manifest"])

    def test_current_contract_schema_fixture_and_docs_are_synchronized(self):
        self.assertEqual(MODULE.validate_current_surfaces(ROOT), [])

    def test_versions_are_independent_and_current(self):
        policy = MODULE.load_current_policy(ROOT)
        self.assertEqual(policy["contract_version"], "1.2.0")
        self.assertEqual(policy["result_schema_version"], "1.1.0")
        self.assertEqual(policy["policy_version"], "1.3.0")
        self.assertEqual(
            policy["method_revision"], "1.3-materiality-scope-and-role-binding"
        )
        self.assertNotEqual(policy["contract_version"], policy["policy_version"])

    def test_method_revision_prefix_drift_is_fail_closed(self):
        policy = copy.deepcopy(MODULE.load_current_policy(ROOT))
        policy["method_revision"] = "1.2-wrong-policy-axis"
        errors = MODULE.validate_policy(policy)
        self.assertTrue(
            any("method_revision must begin with policy_version" in error for error in errors),
            errors,
        )

    def test_versioned_document_filename_drift_is_fail_closed(self):
        original = MODULE.VERSIONED_DOC_REL
        try:
            MODULE.VERSIONED_DOC_REL = Path("docs/rendered_card_audit_v9.9.md")
            errors = MODULE.validate_current_surfaces(ROOT)
        finally:
            MODULE.VERSIONED_DOC_REL = original
        self.assertTrue(
            any("document filename must match contract_version" in error for error in errors),
            errors,
        )

    def test_runtime_helpers_expose_canonical_json_and_digest(self):
        policy, digest = MODULE.get_current_policy(ROOT)
        canonical = MODULE.canonical_policy_json(policy)
        self.assertEqual(digest, MODULE.canonical_policy_digest(policy))
        self.assertEqual(
            canonical,
            json.dumps(
                policy,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
        self.assertTrue(canonical.startswith("{"))
        self.assertEqual(len(digest), 64)

    def test_required_set_deletion_is_fail_closed(self):
        policy = copy.deepcopy(MODULE.load_current_policy(ROOT))
        policy["source_surface"]["expansion_keys"] = []
        errors = MODULE.validate_policy(policy)
        self.assertTrue(any("expansion_keys must not be empty" in error for error in errors))

    def test_required_topology_status_deletion_is_fail_closed(self):
        policy = copy.deepcopy(MODULE.load_current_policy(ROOT))
        policy["topology"]["edge_statuses"]["fail"].remove("wrong_direction")
        errors = MODULE.validate_policy(policy)
        self.assertTrue(any("topology_status_to_axis_status" in error for error in errors))

    def test_new_policy_value_only_needs_json_and_mapping_update(self):
        policy = copy.deepcopy(MODULE.load_current_policy(ROOT))
        policy["topology"]["edge_statuses"]["fail"].append("new_policy_failure")
        policy["verdict_mapping"]["topology_status_to_axis_status"]["new_policy_failure"] = "fail"
        self.assertEqual(MODULE.validate_policy(policy), [])

    def test_conflicting_cross_topology_mapping_is_fail_closed(self):
        policy = copy.deepcopy(MODULE.load_current_policy(ROOT))
        policy["topology"]["relation_statuses"]["fail"].append("equivalent")
        errors = MODULE.validate_policy(policy)
        self.assertTrue(any("maps to both" in error for error in errors))

    def test_version_drift_is_fail_closed(self):
        policy = copy.deepcopy(MODULE.load_current_policy(ROOT))
        policy["result_schema_version"] = policy["contract_version"]
        errors = MODULE.validate_policy(policy)
        self.assertTrue(any("result_schema_version" in error for error in errors))

    def test_manifest_digest_drift_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            policy_dir = base / "policies" / "rca"
            policy_dir.mkdir(parents=True)
            source = MODULE.load_current_bundle(ROOT)
            (policy_dir / "policy_v1.3.0.json").write_text(
                source["canonical_policy_json"], encoding="utf-8"
            )
            manifest = copy.deepcopy(source["manifest"])
            manifest["policy_sha256"] = "0" * 64
            (policy_dir / "current.json").write_text(
                json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8"
            )
            errors = MODULE.validate_current_policy(base)
            self.assertTrue(any("digest" in error for error in errors))

    def test_policy_path_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            policy_dir = base / "policies" / "rca"
            policy_dir.mkdir(parents=True)
            source = MODULE.load_current_bundle(ROOT)
            outside = base / "outside"
            outside.mkdir()
            (outside / "policy_v1.3.0.json").write_text(
                source["canonical_policy_json"], encoding="utf-8"
            )
            (policy_dir / "linked").symlink_to(outside, target_is_directory=True)
            manifest = copy.deepcopy(source["manifest"])
            manifest["policy_path"] = "linked/policy_v1.3.0.json"
            (policy_dir / "current.json").write_text(
                json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8"
            )
            with self.assertRaisesRegex(MODULE.PolicyLoadError, "outside policies/rca"):
                MODULE.load_current_bundle(base)

    def test_malformed_mapping_values_fail_closed_without_type_error(self):
        policy = copy.deepcopy(MODULE.load_current_policy(ROOT))
        policy["verdict_mapping"]["axis_status_to_verdict"]["pass"] = []
        errors = MODULE.validate_policy(policy)
        self.assertTrue(
            any("axis_status_to_verdict" in error for error in errors),
            errors,
        )
        policy = copy.deepcopy(MODULE.load_current_policy(ROOT))
        policy["verdict_mapping"]["material_failure_verdicts"] = [[]]
        errors = MODULE.validate_policy(policy)
        self.assertTrue(
            any("material_failure_verdicts" in error for error in errors),
            errors,
        )

    def test_runtime_loader_rejects_manifest_digest_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            policy_dir = base / "policies" / "rca"
            policy_dir.mkdir(parents=True)
            source = MODULE.load_current_bundle(ROOT)
            (policy_dir / "policy_v1.3.0.json").write_text(
                source["canonical_policy_json"], encoding="utf-8"
            )
            manifest = copy.deepcopy(source["manifest"])
            manifest["policy_sha256"] = "0" * 64
            (policy_dir / "current.json").write_text(
                json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8"
            )
            with self.assertRaises(MODULE.PolicyLoadError):
                MODULE.load_current_bundle(base)
            with self.assertRaises(MODULE.PolicyLoadError):
                MODULE.get_current_policy(base)

    def test_active_contract_version_drift_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.copy_surface_tree(base)
            path = base / MODULE.ACTIVE_CONTRACT_REL
            contract = json.loads(path.read_text(encoding="utf-8"))
            contract["contract_version"] = "9.9.9"
            path.write_text(json.dumps(contract), encoding="utf-8")
            errors = MODULE.validate_current_surfaces(base)
            self.assertTrue(any("active contract.contract_version" in error for error in errors))

    def test_active_schema_version_drift_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.copy_surface_tree(base)
            path = base / MODULE.ACTIVE_SCHEMA_REL
            schema = json.loads(path.read_text(encoding="utf-8"))
            schema["properties"]["policy_version"]["const"] = "9.9.9"
            path.write_text(json.dumps(schema), encoding="utf-8")
            errors = MODULE.validate_current_surfaces(base)
            self.assertTrue(any("active schema.properties.policy_version" in error for error in errors))

    def test_active_schema_semantic_packet_binding_drift_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.copy_surface_tree(base)
            path = base / MODULE.ACTIVE_SCHEMA_REL
            schema = json.loads(path.read_text(encoding="utf-8"))
            semantic_packet = schema["$defs"]["semanticPacket"]
            semantic_packet["required"].remove("source_binding_digests")
            semantic_packet["properties"]["expected_evidence_annotation_inventory"]["items"]["$ref"] = "#/$defs/evidenceAnnotationInventoryItem"
            path.write_text(json.dumps(schema), encoding="utf-8")
            errors = MODULE.validate_current_surfaces(base)
            self.assertTrue(any("source_binding_digests" in error for error in errors))
            self.assertTrue(any("expected annotation definition" in error for error in errors))

    def test_active_contract_policy_rule_parity_drift_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.copy_surface_tree(base)
            path = base / MODULE.ACTIVE_CONTRACT_REL
            contract = json.loads(path.read_text(encoding="utf-8"))
            rca05 = next(
                stage
                for stage in contract["mandatory_audit_sop"]
                if stage.get("stage") == "RCA-05"
            )
            rca05["allowed_node_dispositions"].append("DRIFT")
            contract["verdicts"]["DRIFT"] = "drift"
            contract["human_repair_display"]["include_only"].append("DRIFT")
            path.write_text(json.dumps(contract), encoding="utf-8")
            errors = MODULE.validate_current_surfaces(base)
            self.assertTrue(any("allowed_node_dispositions" in error for error in errors))
            self.assertTrue(any("verdicts" in error for error in errors))
            self.assertTrue(any("include_only" in error for error in errors))

    def test_active_fixture_policy_digest_drift_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.copy_surface_tree(base)
            path = base / MODULE.ACTIVE_FIXTURE_REL
            fixture = json.loads(path.read_text(encoding="utf-8"))
            fixture["policy_digest"] = "0" * 64
            path.write_text(json.dumps(fixture), encoding="utf-8")
            errors = MODULE.validate_current_surfaces(base)
            self.assertTrue(any("active fixture.policy_digest" in error for error in errors))

    def test_active_contract_policy_digest_drift_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.copy_surface_tree(base)
            path = base / MODULE.ACTIVE_CONTRACT_REL
            contract = json.loads(path.read_text(encoding="utf-8"))
            contract["policy_digest"] = "0" * 64
            path.write_text(json.dumps(contract), encoding="utf-8")
            errors = MODULE.validate_current_surfaces(base)
            self.assertTrue(any("active contract.policy_digest" in error for error in errors))

    def test_active_document_alias_drift_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.copy_surface_tree(base)
            path = base / MODULE.ACTIVE_DOC_REL
            path.write_text(path.read_text(encoding="utf-8") + "\nDRIFT\n", encoding="utf-8")
            errors = MODULE.validate_current_surfaces(base)
            self.assertTrue(any("byte-identical" in error for error in errors))

    def test_sync_surfaces_round_trip_updates_policy_only_mirrors(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.copy_surface_tree(base)
            policy_path = base / "policies/rca/policy_v1.3.1.json"
            policy = json.loads(
                (base / "policies/rca/policy_v1.3.0.json").read_text(encoding="utf-8")
            )
            policy["policy_version"] = "1.3.1"
            policy["topology"]["edge_statuses"]["fail"].append("sync_only_failure")
            policy["verdict_mapping"]["topology_status_to_axis_status"]["sync_only_failure"] = "fail"
            policy_path.write_text(
                json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            manifest_path = base / "policies/rca/current.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["policy_path"] = "policy_v1.3.1.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            result = MODULE.sync_surfaces(base)
            self.assertEqual(result["status"], "pass")
            expected_digest = MODULE.policy_digest(policy)
            manifest = json.loads(
                (base / "policies/rca/current.json").read_text(encoding="utf-8")
            )
            contract = json.loads(
                (base / MODULE.ACTIVE_CONTRACT_REL).read_text(encoding="utf-8")
            )
            fixture = json.loads(
                (base / MODULE.ACTIVE_FIXTURE_REL).read_text(encoding="utf-8")
            )
            schema = json.loads(
                (base / MODULE.ACTIVE_SCHEMA_REL).read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["policy_version"], "1.3.1")
            self.assertEqual(manifest["policy_sha256"], expected_digest)
            self.assertEqual(contract["policy_version"], "1.3.1")
            self.assertEqual(contract["policy_digest"], expected_digest)
            self.assertEqual(
                contract["canonical_documents"]["policy"],
                "policies/rca/policy_v1.3.1.json",
            )
            self.assertEqual(fixture["policy_version"], "1.3.1")
            self.assertEqual(fixture["policy_digest"], expected_digest)
            self.assertEqual(
                schema["properties"]["policy_version"]["const"], "1.3.1"
            )
            self.assertEqual(MODULE.validate_current_policy(base), [])
            self.assertEqual(MODULE.validate_current_surfaces(base), [])

    def test_sync_surfaces_rejects_structural_version_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.copy_surface_tree(base)
            policy_path = base / "policies/rca/policy_v1.3.0.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["contract_version"] = "9.9.9"
            policy_path.write_text(
                json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            manifest_path = base / "policies/rca/current.json"
            before = manifest_path.read_bytes()
            with self.assertRaisesRegex(MODULE.PolicySyncError, "contract_version"):
                MODULE.sync_surfaces(base)
            self.assertEqual(manifest_path.read_bytes(), before)

    def test_cli_emits_digest(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--emit", "digest"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            MODULE.policy_digest(MODULE.load_current_policy(ROOT)),
        )


if __name__ == "__main__":
    unittest.main()
