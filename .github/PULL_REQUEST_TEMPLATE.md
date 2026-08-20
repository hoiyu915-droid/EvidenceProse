## What changed

<!-- Describe the registry, rule, schema, validator, or documentation change. -->

## Integrity checklist

- [ ] Observed article bytes and `article_sha256` agree.
- [ ] Source and artifact verification states are honest.
- [ ] Registry, rule, voice, batch, and contamination ledgers agree.
- [ ] Semantic and strict-render failures remain explicit.
- [ ] Rule-state changes satisfy `docs/induction_protocol.md`.
- [ ] `python3 -m unittest discover -s tests -v` passes.
- [ ] `python3 scripts/validate_registry.py --json` returns `status: pass`.
