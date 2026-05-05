# SwiftDeploy Stage 4A Agent Notes

## Read Order

1. `task_details.md`
2. `stage4_forwarning.md`
3. `stage3_result_feedback.md`
4. `docs/stage4-control-plane/README.md`
5. `config/runtime_status.json`
6. `CURRENT_TASK`
7. The task packet named by `CURRENT_TASK`

## Operating Rules

- This repo is currently in governance-only mode.
- Do not create SwiftDeploy implementation files until `config/runtime_status.json` sets `implementation_allowed` to `true`.
- Forbidden during governance-only mode: `manifest.yaml`, `swiftdeploy`, `app/`, `templates/`, `Dockerfile`, `docker-compose.yml`, and `nginx.conf`.
- Every non-trivial slice must update the task packet, evidence log, decisions log when a lasting choice changes, QA checklist, defense bank, and same-day journal.
- Do not close a gate unless a matching evidence id exists in `docs/stage4-control-plane/05_evidence_log.md`.
- Do not copy Claude's suggested implementation blindly. Treat it as research input, validate each decision against the official brief, then implement only what can be defended.
- Keep generated artifacts distinct from source-of-truth files. The final project must prove that deleted generated configs can be recreated by `swiftdeploy init`.
- Any user-facing claim in `README.md`, blog drafts, or submission notes must match the current state in `config/runtime_status.json`.

## Code-With-Me Protocol

- Each future implementation slice starts with a short teach-back note: concept, design decision, expected behavior, and likely interview question.
- Each slice ends with proof: command output, screenshot plan or artifact path, and a plain-English explanation of what changed.
- Failures must be recorded. Debugging evidence is part of the defense trail.
- The operator must be able to explain the slice without relying on AI before the next implementation slice closes.

