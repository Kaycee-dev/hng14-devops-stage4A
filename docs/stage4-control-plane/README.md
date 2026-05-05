# Stage 4A Control Plane

This directory is the operating system for the SwiftDeploy task. It exists to prevent shallow implementation, stale proof claims, and interview answers that cannot be defended.

## How To Resume

1. Read `config/runtime_status.json`.
2. Confirm `CURRENT_TASK` matches `current_packet`.
3. Open the matching file in `docs/stage4-control-plane/task-packets/`.
4. Run `python scripts/control_plane_check.py`.
5. Continue only within the scope of the active packet.

## Documents

- `01_brief_traceability.md`: maps the official task to future proof.
- `02_execution_roadmap.md`: ordered work packets.
- `03_code_with_me_protocol.md`: teach-back rules.
- `04_decisions_log.md`: decisions, alternatives, rationale, and defense notes.
- `05_evidence_log.md`: command outputs, artifacts, failures, and proof.
- `06_test_strategy.md`: validation gates.
- `07_qa_checklist.md`: final submission checklist.
- `08_interview_defense_bank.md`: questions to rehearse.
- `09_blog_and_diagram_plan.md`: dev.to article and diagram workflow.

## Current Rule

Implementation is not allowed yet. The design packet must close first.

