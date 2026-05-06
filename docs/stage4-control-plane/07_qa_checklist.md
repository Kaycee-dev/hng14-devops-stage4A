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

## Stage 4B

- [x] Stage 4B task packets exist (E-011).
- [x] Stage 4B design decisions are recorded (E-012).
- [x] `/metrics` exposes request, latency, uptime, mode, and chaos metrics (E-013).
- [x] OPA sidecar is generated in Compose and isolated from Nginx ingress (E-014).
- [x] Infrastructure policy blocks deploy on low disk or high CPU in Rego tests (E-014).
- [x] Canary policy blocks promote on high error rate or high p99 latency in Rego tests (E-014).
- [x] `status` writes `history.jsonl` and shows policy compliance (E-015).
- [x] `audit` writes clean GitHub Markdown (E-015).
- [x] Stage 4B proof outputs are refreshed (E-016).
- [x] Stage 4B article draft is updated from evidence (E-017).

## Stage 4B Grading-Prep Audit Remediation

- [x] All Stage 4B files committed to git — no untracked implementation files remain (E-018, commit 0ee50e4).
- [x] `PYTHONUNBUFFERED=1` added to `scripts/capture_evidence.sh`; proof outputs re-captured showing correct event order (E-019).
- [x] CPU policy denial proof captured as `12_cpu_policy_denial.txt` — Windows adaptation uses threshold `-1.0` so `cpu_load=0.0 > -1.0` fires the deny rule (E-020).
- [x] Nginx access log proof captured as `13_nginx_access_log.txt` — mandated `$time_iso8601 | $status | ${request_time}s | $upstream_addr | $request` format verified (E-021).
- [x] Blog article expanded with ARCHITECTURE (Mermaid diagram), DESIGN (manifest/template flow), GUARDRAILS (Rego snippet + input construction), CHAOS (verbatim terminal output), REPLICATION (10 steps), LESSONS LEARNED (4 lessons) (E-022).
- [x] 30-second pre-promote window trade-off documented in README NOTE, blog lesson (b), interview defense bank Q72, and decisions log D-025 (E-023).
- [ ] Blog article published on Dev.to (manual operator step).
- [ ] Public repo pushed (manual operator step).
- [ ] Submission form submitted before 2026-05-08 11:59 WAT (manual operator step).
