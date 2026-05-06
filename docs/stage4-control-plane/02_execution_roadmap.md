# Execution Roadmap

Work proceeds by task packet. A packet is not closed until implementation, evidence, tests, and defense notes all match the packet's `done_when`.

| Packet | Goal | Gate |
|---|---|---|
| `SD4-GOV-001` | Create governance scaffold and control-plane checker | Governance |
| `SD4-DESIGN-001` | Finalize stack choices, manifest shape, config-generation approach, and validation policy | Design |
| `SD4-APP-001` | Build API service behavior for stable/canary, health, root, and chaos | Implementation |
| `SD4-CONTAINER-001` | Build lightweight hardened container image | Implementation |
| `SD4-TEMPLATE-001` | Build Nginx and Compose templates | Implementation |
| `SD4-CLI-001` | Implement `init` and `validate` | Implementation |
| `SD4-CLI-002` | Implement `deploy`, `promote`, and `teardown` | Implementation |
| `SD4-PROOF-001` | Run end-to-end proof, collect screenshots, and finish README | Proof |
| `SD4-BLOG-001` | Prepare dev.to article and diagrams for manual publishing | Blog |

## Stage 4B Packet Sequence

| Packet | Goal | Gate |
|---|---|---|
| `SD4B-GOV-001` | Extend the control plane for observability, policy, audit, and blog work | Stage 4B Governance |
| `SD4B-DESIGN-001` | Settle metrics, OPA, policy threshold, CLI helper, status, and audit design | Stage 4B Design |
| `SD4B-METRICS-001` | Add Prometheus `/metrics` and smoke coverage | Stage 4B Implementation |
| `SD4B-POLICY-001` | Add Rego policies, manifest thresholds, and OPA Compose rendering | Stage 4B Implementation |
| `SD4B-CLI-001` | Add OPA-gated deploy/promote, `status`, and `audit` | Stage 4B Implementation |
| `SD4B-PROOF-001` | Refresh proof outputs for policy gates, status, audit, and no-leakage checks | Stage 4B Proof |
| `SD4B-BLOG-001` | Update the technical article and diagrams for Stage 4B | Stage 4B Blog |

## Packet Rules

- Each packet starts with a teach-back explanation before edits.
- Each packet records decisions and evidence in the same cycle.
- Each packet updates the defense bank with questions that match the code just written.
- Implementation packets remain blocked until the design gate closes.
