# Probe TE delivery

Contract: `EP_PROBE_TE_DELIVERY v1.0`

Probe may use an unsealed state while it is comparing cards, applying Claude findings, merging content, or strengthening the science explainer. That state is an implementation detail. It is never a user-facing deliverable.

The final publication order is fixed:

```text
science explainer textedit box
-> TE_*.json attachment
```

Nothing is inserted between those two surfaces in the normal delivery path.

## Why this exists

A content edit invalidates prompt-length and digest bindings. The old failure mode emitted a queue with `content_truth_edit_unsealed`, `STALE_AFTER_CONTENT_EDIT`, `requires_reseal`, and disabled dispatch, while also telling a future session to recompile/reseal it. That pushed Probe's own finalization obligation onto the user or the next session.

The corrected rule is simple: stale-after-edit is a recoverable internal state, not a terminal state. Probe must finalize it before delivery.

## Finalization

`scripts/finalize_probe_te_queue.py` accepts a Probe-edited `portable_imagegen_queue` schema 1.3 and performs one deterministic finalization pass.

It preserves the final `imagegen_args.prompt` bytes, then recomputes:

- `prompt_char_count`;
- `imagegen_args_digest`;
- a domain-separated post-audit `renderer_payload_digest` bound to the final `MINIMAL_RENDER_SPEC_JSON` plus the upstream renderer digest;
- the C01 queue-item identity;
- every dependent card's C01 source bindings and `dependency_digest`;
- the modified preparation-attestation source binding;
- `queue_digest`.

The original renderer digest remains in `probe_delivery.renderer_lineage`, so the post-audit digest is not pretending to be the untouched upstream TP renderer artifact.

The lifecycle surface is then restored to direct execution:

```text
workflow_state = generate_authorized
generation_authorized = true
preparation_attestation.status = PASS
preparation_attestation.artifact_phase = probe_resealed
preparation_attestation.dispatch_authorized = true
portable_handoff.cross_session_ready = direct
artifact_execution_contract.authorization_model = preauthorized_at_compile
artifact_execution_contract.dispatch_immediately = true
```

`content_truth_merge` remains as provenance, but its status becomes `SEALED`. Its stale/reseal instruction is removed.

## No second user chore

Resealing does not require a new user command or confirmation. Probe already has authority to transform the package; finalization is part of completing that transform.

It fails closed only when deterministic finalization is impossible: malformed/missing items, missing prompt, prompt above 18,000 characters, missing or malformed `MINIMAL_RENDER_SPEC_JSON`, wrong card binding, or a missing required series dependency.

A Python test or adapter problem by itself is not a reason to serialize an unsealed artifact and ask the user to repair it.

## Naming

Every final Probe JSON uses the `TE_` prefix. `TE_` is the EvidenceProse/TextEdit final-output namespace. It does not rename TA/TP's own producer artifacts.

Example:

```text
TP_20260815_2602_01637__combined_content_truth_edit_unsealed(2).json
-> TE_20260815_2602_01637__imagegen_queue.json
```

## Validation

```bash
python3 scripts/finalize_probe_te_queue.py \
  path/to/content_truth_edit_unsealed.json \
  --output-dir path/to/output
```

Check without writing:

```bash
python3 scripts/finalize_probe_te_queue.py \
  path/to/content_truth_edit_unsealed.json --check
```

A valid final queue contains no unsealed lifecycle tokens, is `generate_authorized`, carries a valid recomputed queue digest, and records:

```text
probe_delivery.json_prefix = TE_
probe_delivery.delivery_order = [science_explainer_textedit, te_json_attachment]
probe_delivery.user_confirmation_required_for_reseal = false
```
