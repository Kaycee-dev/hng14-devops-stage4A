# Blog And Diagram Plan

## Stage 4B Update

- Article draft: `blog/devto/swiftdeploy-stage4b.md`.
- Required additions: OPA sidecar architecture, metrics/status flow, policy decision flow, chaos failure capture, and audit report generation.
- Claims must be refreshed from Stage 4B proof outputs before manual publishing.
- Final Stage 4B diagram sources:
  - `blog/diagrams/stage4b_architecture.md`
  - `blog/diagrams/policy_gate_flow.md`

The dev.to article is prepared in the repo first and published manually after the final evidence exists.

## Draft

- Source: `blog/devto/swiftdeploy-stage4.md`
- Publish route: manual dev.to editor
- Publish condition: final proof gate closed and screenshots verified

## Article (final)

- Title: **SwiftDeploy: Building A Manifest-Driven Deployment Tool**
- Path: `blog/devto/swiftdeploy-stage4.md`
- Status: draft, `published: false` in front-matter
- Sections:
  1. Why this task is hard (idempotency + portability + interview defense)
  2. Architecture (mermaid)
  3. The manifest is the contract (mermaid: init pipeline)
  4. The five validate checks (table mapping each check to its implementation)
  5. Stable vs canary and the rolling restart (mermaid sequence; with the
     captured 502s during recreate as proof nginx stayed up)
  6. Chaos and the recovery escape hatch (mermaid state machine)
  7. Hardening summary (mermaid; image size 236 MB cited)
  8. Three real bugs I caught (Microsoft Store stub, heredoc path mismatch,
     yaml.safe_dump comment strip), each with the fix and the lesson
  9. Six interview questions pulled from the defense bank
  10. Reproducible proof bundle (the capture_evidence.sh script)
  11. What I would do with another week
  12. Closing

## Diagrams (final, all in mermaid)

| File | Diagram |
|---|---|
| `blog/diagrams/architecture.md` | client -> nginx -> app, app marked internal-only |
| `blog/diagrams/init_pipeline.md` | manifest + templates -> Python helper -> generated files (atomic write) |
| `blog/diagrams/promote_sequence.md` | regex edit -> init -> up -d --no-deps --force-recreate app -> health poll -> two-signal mode confirm |
| `blog/diagrams/chaos_state.md` | Off/Slow/Error states with transitions (canary mode); stable mode collapses to a single 403 response |
| `blog/diagrams/hardening_model.md` | image-side and runtime-side hardening side by side |

Mermaid was chosen over PNG because dev.to renders mermaid natively, the
source is editable forever, and there is no PNG export step that could
drift from the architecture.

## Asset Rules

- Diagrams must support real implementation claims.
- Screenshots must come from final local proof commands.
- Blog copy must not claim production readiness.
- Any future generated image must be relevant to the architecture, not decorative filler.
