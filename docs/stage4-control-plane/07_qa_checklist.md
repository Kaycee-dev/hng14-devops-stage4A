# QA Checklist

## Governance

- [x] `AGENTS.md` exists and documents guardrails.
- [x] `CURRENT_TASK` exists.
- [x] `config/runtime_status.json` exists.
- [x] `docs/stage4-control-plane/` exists.
- [x] All task packets exist.
- [x] `scripts/control_plane_check.py` passes.
- [x] Governance evidence `E-001` is recorded.
- [x] No SwiftDeploy implementation files exist.

## Design

- [x] API stack decision is recorded (D-004).
- [x] CLI stack decision is recorded (D-005, D-006).
- [x] YAML parsing strategy is recorded (D-007).
- [x] Template rendering policy is recorded (D-008).
- [x] Manifest extension policy is recorded (D-009).
- [x] Healthcheck dependency strategy is recorded (D-010).
- [x] Stable/canary chaos behavior is recorded (D-011).
- [x] Port pre-flight strategy is recorded (D-012).
- [x] Nginx syntax check strategy is recorded (D-013).
- [x] Grader portability risks are recorded (D-014).

## Implementation

- [x] API endpoints work (E-003: 26/26 smoke + live uvicorn curl proof).
- [x] Docker image builds under 300 MB (E-004: 236 MB measured).
- [x] Nginx and Compose templates render from manifest (E-005: 27/27 token assertions, nginx -t passes, docker compose config passes).
- [x] `init` is idempotent (E-006: identical SHA256 across re-run and post-delete-rebuild).
- [x] `validate` covers all five checks (E-006: 4/5 PASS with conflict and exit 1; 5/5 PASS clean and exit 0).
- [x] `deploy` waits for health (E-007: live deploy reached `health ok at t=1s` through nginx).
- [x] `promote` handles canary and stable (E-007: both directions confirmed via body.mode AND X-Mode header).
- [x] `teardown --clean` removes generated configs (E-007: confirmed plus regenerate-from-deletion).

## Submission

- [x] README walkthrough complete (E-008: rewrite with architecture, prerequisites, quickstart, subcommand reference, manifest, endpoints, hardening, submission map).
- [x] Validate text capture saved (E-008: `blog/assets/proof_outputs/01_validate.txt` for 5/5 PASS; `00_validate_with_conflict.txt` for the failure mode).
- [x] Deploy text capture saved (E-008: `blog/assets/proof_outputs/02_deploy.txt`).
- [x] Promote plus `/healthz` text capture saved (E-008: `03_promote_canary.txt` and `04_promote_stable.txt`).
- [x] Generated config text capture saved (E-008: `05_generated_configs.txt` with full file contents and SHA256).
- [x] Nginx access log text capture saved (E-008: `06_nginx_access_log.txt`, brief-mandated format).
- [ ] Operator opens each `.txt` file in a terminal and screenshots for Google Drive (manual step).
- [ ] Google Drive folder link added to submission form.
- [ ] Submission form ready before `2026-05-05 11:59 WAT`.
