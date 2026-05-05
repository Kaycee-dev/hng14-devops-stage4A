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

## Packet Rules

- Each packet starts with a teach-back explanation before edits.
- Each packet records decisions and evidence in the same cycle.
- Each packet updates the defense bank with questions that match the code just written.
- Implementation packets remain blocked until the design gate closes.

