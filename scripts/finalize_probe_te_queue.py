#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

PROJECTION_MARKER = "MINIMAL_RENDER_SPEC_JSON:\n"
MAX_PROMPT_CHARS = 18_000
RESEAL_CONTRACT = "EP_PROBE_TE_QUEUE_RESEAL_V1"
RENDERER_PROJECTION_RESEAL_CONTRACT = "EP_PROBE_RENDERER_PROJECTION_RESEAL_V1"
TE_PREFIX = "TE_"
STALE_TOKENS = (
    "content_truth_edit_unsealed",
    "STALE_AFTER_CONTENT_EDIT",
    "requires_reseal",
    "requires_reseal_after_content_edit",
    "reseal/recompile once at execution stage",
    "執行前一次性 recompile/reseal",
    "尚未 reseal",
)
DIRECT_REMARK = {
    "remark_version": "1.1-direct-dispatch",
    "audience": "GPT_WORK",
    "read_first": True,
    "instruction_zh_hant": [
        "此 JSON 是 current 直接執行 artifact；編譯時已封存完整執行權限，載入後沒有狀態轉換步驟。",
        "直接依 items.sequence 逐卡操作；每次只送目前卡的 items[n].imagegen_args，收到回傳並完成逐卡 QA，隨即輸出目前結果後才處理下一張。",
        "若 Python test／adapter 無法執行或失敗，只記錄診斷；不得修改已封存 queue，也不得把該工具失敗改寫成新的流程控制狀態。",
        "建立新圖卡使用 IMAGE_GENERATION；修改既有圖卡時使用 IMAGE_EDITOR 並以原圖為輸入，只改指定內容。",
    ],
    "direct_execution": {
        "authorization_model": "preauthorized_at_compile",
        "load_transition_required": False,
        "python_host_required": False,
        "python_test_required": False,
        "python_test_or_adapter_failure_is_blocking": False,
        "on_python_test_or_adapter_failure": "continue_from_this_json",
        "dispatch": "sequential",
        "default_output_mode": "per_card_immediate",
        "one_card_per_call": True,
        "send_field": "items[n].imagegen_args",
        "wait_for_current_result_before_next_call": True,
        "qa_each_card_before_next_call": True,
        "emit_current_result_immediately_before_next_call": True,
        "gallery_requires_explicit_request": True,
        "diagnostic_recording": {
            "required_before_continue": True,
            "field": "operator_diagnostics",
            "scope": "current_session_or_host_log",
            "sealed_queue_mutation_allowed": False,
        },
        "block_current_card_only_when": [
            "items[n].imagegen_args_missing_or_empty",
            "required_series_reference_image_missing",
            "required_source_image_for_edit_missing",
        ],
    },
    "initial_card_generation": {"mode": "IMAGE_GENERATION", "tool": "image_gen.imagegen"},
    "existing_card_modification": {
        "mode": "IMAGE_EDITOR",
        "use_existing_card_as_source_image": True,
        "regenerate_from_scratch": False,
        "preserve_unrequested_content": True,
    },
}


def canonical_digest(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def extract_projection(prompt: str) -> Mapping[str, Any]:
    if PROJECTION_MARKER not in prompt:
        raise ValueError("imagegen prompt is missing MINIMAL_RENDER_SPEC_JSON")
    body = prompt.split(PROJECTION_MARKER, 1)[1]
    value, _end = json.JSONDecoder().raw_decode(body)
    if not isinstance(value, Mapping):
        raise ValueError("MINIMAL_RENDER_SPEC_JSON must decode to an object")
    return value


def queue_item_identity_digest(item: Mapping[str, Any]) -> str:
    return canonical_digest(
        {
            "sequence": item["sequence"],
            "card_id": item["card_id"],
            "imagegen_args_digest": item["imagegen_args_digest"],
            "renderer_payload_digest": item["renderer_payload_digest"],
        }
    )


def resealed_renderer_digest(
    item: Mapping[str, Any], projection: Mapping[str, Any]
) -> str:
    return canonical_digest(
        {
            "contract": RENDERER_PROJECTION_RESEAL_CONTRACT,
            "card_id": item["card_id"],
            "upstream_renderer_payload_digest": item.get("renderer_payload_digest"),
            "minimal_render_spec": projection,
        }
    )


def _update_dependency(
    dep: Mapping[str, Any], first: Mapping[str, Any]
) -> dict[str, Any]:
    result = copy.deepcopy(dict(dep))
    result["source_imagegen_args_digest"] = first["imagegen_args_digest"]
    result["source_renderer_payload_digest"] = first["renderer_payload_digest"]
    result["source_queue_item_identity_digest"] = queue_item_identity_digest(first)
    result.pop("dependency_digest", None)
    result["dependency_digest"] = canonical_digest(result)
    return result


def _te_name(source_name: str) -> str:
    name = Path(source_name).name
    stem = re.sub(r"^(TP_|TZ01_|tz_)", "", name)
    stem = re.sub(
        r"__combined_content_truth_edit_unsealed(?:\(\d+\))?\.json$",
        "__imagegen_queue.json",
        stem,
    )
    if not stem.endswith(".json"):
        stem += ".json"
    return TE_PREFIX + stem


def reseal_queue(
    raw: Mapping[str, Any], *, source_name: str = "queue.json"
) -> tuple[dict[str, Any], str]:
    q = copy.deepcopy(dict(raw))
    if (
        q.get("artifact_type") != "portable_imagegen_queue"
        or q.get("schema_version") != "1.3"
    ):
        raise ValueError(
            "Probe TE reseal requires portable_imagegen_queue schema 1.3"
        )
    items = q.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("queue items must be a non-empty array")

    upstream_queue_digest = str(q.get("queue_digest") or "")
    renderer_lineage: list[dict[str, str]] = []
    normalized_items: list[dict[str, Any]] = []
    for expected, raw_item in enumerate(items, start=1):
        if not isinstance(raw_item, Mapping):
            raise ValueError(f"items[{expected - 1}] must be an object")
        item = copy.deepcopy(dict(raw_item))
        if item.get("sequence") != expected or not str(
            item.get("card_id") or ""
        ).strip():
            raise ValueError("item sequence/card_id drift")
        args = item.get("imagegen_args")
        if (
            not isinstance(args, Mapping)
            or not isinstance(args.get("prompt"), str)
            or not args["prompt"].strip()
        ):
            raise ValueError(f"{item['card_id']}: imagegen_args.prompt missing")
        prompt = args["prompt"]
        if len(prompt) > MAX_PROMPT_CHARS:
            raise ValueError(
                f"{item['card_id']}: prompt exceeds {MAX_PROMPT_CHARS} chars"
            )
        projection = extract_projection(prompt)
        if str(projection.get("card_id") or "") != item["card_id"]:
            raise ValueError(f"{item['card_id']}: prompt card_id drift")
        upstream_renderer = str(item.get("renderer_payload_digest") or "")
        item["prompt_char_count"] = len(prompt)
        item["imagegen_args_digest"] = canonical_digest(dict(args))
        item["renderer_payload_digest"] = resealed_renderer_digest(item, projection)
        renderer_lineage.append(
            {
                "card_id": item["card_id"],
                "upstream_renderer_payload_digest": upstream_renderer,
                "resealed_renderer_payload_digest": item["renderer_payload_digest"],
            }
        )
        normalized_items.append(item)

    first = normalized_items[0]
    first.pop("series_reference_dependency", None)
    for item in normalized_items[1:]:
        dep = item.get("series_reference_dependency")
        if not isinstance(dep, Mapping):
            raise ValueError(
                f"{item['card_id']}: series_reference_dependency missing"
            )
        item["series_reference_dependency"] = _update_dependency(dep, first)
    q["items"] = normalized_items

    q["workflow_state"] = "generate_authorized"
    q["generation_authorized"] = True
    q["REMARK"] = copy.deepcopy(DIRECT_REMARK)
    att = q.get("preparation_attestation")
    if not isinstance(att, Mapping):
        raise ValueError("preparation_attestation missing")
    att = copy.deepcopy(dict(att))
    att["status"] = "PASS"
    att["artifact_phase"] = "probe_resealed"
    att["dispatch_authorized"] = True
    q["preparation_attestation"] = att
    source_binding = q.get("source_binding")
    if not isinstance(source_binding, Mapping):
        raise ValueError("source_binding missing")
    source_binding = copy.deepcopy(dict(source_binding))
    source_binding["artifact_digest"] = canonical_digest(att)
    q["source_binding"] = source_binding

    handoff = q.get("portable_handoff")
    if not isinstance(handoff, Mapping):
        raise ValueError("portable_handoff missing")
    handoff = copy.deepcopy(dict(handoff))
    handoff["cross_session_ready"] = "direct"
    handoff["authorization_model"] = "preauthorized_at_compile"
    handoff["load_transition_required"] = False
    handoff["dispatch_start_sequence"] = 1
    q["portable_handoff"] = handoff

    exec_contract = q.get("artifact_execution_contract")
    if not isinstance(exec_contract, Mapping):
        raise ValueError("artifact_execution_contract missing")
    exec_contract = copy.deepcopy(dict(exec_contract))
    exec_contract["authorization_model"] = "preauthorized_at_compile"
    exec_contract["generation_authorized"] = True
    exec_contract["load_transition_required"] = False
    exec_contract["second_confirmation_required"] = False
    exec_contract["dispatch_immediately"] = True
    q["artifact_execution_contract"] = exec_contract

    merge = q.get("content_truth_merge")
    if isinstance(merge, Mapping):
        merge = copy.deepcopy(dict(merge))
        merge["status"] = "SEALED"
        merge.pop("integrity_note", None)
        merge["reseal_contract"] = RESEAL_CONTRACT
        merge["renderer_digest_semantics"] = (
            "final minimal-render-spec projection + upstream renderer digest"
        )
        q["content_truth_merge"] = merge

    q["probe_delivery"] = {
        "contract_version": "1.0",
        "status": "SEALED_DIRECT",
        "json_prefix": TE_PREFIX,
        "delivery_order": [
            "science_explainer_textedit",
            "te_json_attachment",
        ],
        "intermediate_unsealed_delivery_allowed": False,
        "auto_reseal_required_after_content_edit": True,
        "user_confirmation_required_for_reseal": False,
        "upstream_queue_digest": upstream_queue_digest,
        "renderer_lineage": renderer_lineage,
    }
    q.pop("queue_digest", None)
    q["queue_digest"] = canonical_digest(q)
    return q, _te_name(source_name)


def validate_resealed_queue(
    q: Mapping[str, Any], *, filename: str | None = None
) -> list[str]:
    errors: list[str] = []
    if filename is not None and not Path(filename).name.startswith(TE_PREFIX):
        errors.append("final JSON filename must start with TE_")
    if (
        q.get("workflow_state") != "generate_authorized"
        or q.get("generation_authorized") is not True
    ):
        errors.append("queue is not generate_authorized")
    att = (
        q.get("preparation_attestation")
        if isinstance(q.get("preparation_attestation"), Mapping)
        else {}
    )
    if att.get("status") != "PASS" or att.get("dispatch_authorized") is not True:
        errors.append("preparation_attestation is not dispatch-authorized")
    if att.get("artifact_phase") != "probe_resealed":
        errors.append(
            "preparation_attestation.artifact_phase must be probe_resealed"
        )
    handoff = (
        q.get("portable_handoff")
        if isinstance(q.get("portable_handoff"), Mapping)
        else {}
    )
    if handoff.get("cross_session_ready") != "direct":
        errors.append("portable_handoff is not direct")
    contract = (
        q.get("artifact_execution_contract")
        if isinstance(q.get("artifact_execution_contract"), Mapping)
        else {}
    )
    if (
        contract.get("generation_authorized") is not True
        or contract.get("dispatch_immediately") is not True
    ):
        errors.append("artifact_execution_contract is not immediately dispatchable")
    delivery = (
        q.get("probe_delivery")
        if isinstance(q.get("probe_delivery"), Mapping)
        else {}
    )
    if delivery.get("json_prefix") != TE_PREFIX or delivery.get(
        "delivery_order"
    ) != ["science_explainer_textedit", "te_json_attachment"]:
        errors.append("Probe delivery naming/order contract drift")
    digest_input = copy.deepcopy(dict(q))
    expected = digest_input.pop("queue_digest", None)
    if canonical_digest(digest_input) != expected:
        errors.append("queue_digest mismatch")
    items = q.get("items")
    if not isinstance(items, list) or not items:
        errors.append("items missing")
        return errors
    for expected_seq, item in enumerate(items, start=1):
        if not isinstance(item, Mapping):
            errors.append(f"items[{expected_seq - 1}] invalid")
            continue
        args = (
            item.get("imagegen_args")
            if isinstance(item.get("imagegen_args"), Mapping)
            else {}
        )
        prompt = args.get("prompt")
        if not isinstance(prompt, str):
            errors.append(f"{item.get('card_id')}: prompt missing")
            continue
        if item.get("prompt_char_count") != len(prompt):
            errors.append(f"{item.get('card_id')}: prompt_char_count mismatch")
        if item.get("imagegen_args_digest") != canonical_digest(dict(args)):
            errors.append(f"{item.get('card_id')}: imagegen_args_digest mismatch")
        try:
            projection = extract_projection(prompt)
        except Exception as exc:
            errors.append(f"{item.get('card_id')}: projection invalid: {exc}")
        else:
            if str(projection.get("card_id") or "") != item.get("card_id"):
                errors.append(f"{item.get('card_id')}: projection card_id drift")
    if len(items) > 1:
        first = items[0]
        first_identity = queue_item_identity_digest(first)
        for item in items[1:]:
            dep = item.get("series_reference_dependency")
            if not isinstance(dep, Mapping):
                errors.append(f"{item.get('card_id')}: dependency missing")
                continue
            body = copy.deepcopy(dict(dep))
            dep_digest = body.pop("dependency_digest", None)
            if canonical_digest(body) != dep_digest:
                errors.append(f"{item.get('card_id')}: dependency_digest mismatch")
            if dep.get("source_imagegen_args_digest") != first.get(
                "imagegen_args_digest"
            ):
                errors.append(f"{item.get('card_id')}: source imagegen digest drift")
            if dep.get("source_renderer_payload_digest") != first.get(
                "renderer_payload_digest"
            ):
                errors.append(f"{item.get('card_id')}: source renderer digest drift")
            if dep.get("source_queue_item_identity_digest") != first_identity:
                errors.append(f"{item.get('card_id')}: source identity digest drift")
    serialized = json.dumps(q, ensure_ascii=False, sort_keys=True)
    for token in STALE_TOKENS:
        if token in serialized:
            errors.append(f"stale/unsealed token remains in final TE queue: {token}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    output, name = reseal_queue(raw, source_name=args.input.name)
    errors = validate_resealed_queue(output, filename=name)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 2
    if args.check:
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "output_name": name,
                    "queue_digest": output["queue_digest"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    out_dir = args.output_dir or args.input.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
