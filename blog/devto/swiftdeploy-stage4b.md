---
title: "SwiftDeploy Stage 4B: Observability, Policy, and Audit"
published: false
tags: devops, opa, prometheus, docker
---

# SwiftDeploy Stage 4B: Observability, Policy, and Audit

Stage 4A built the deployment engine: a manifest, templates, Docker Compose,
Nginx, and a CLI that could deploy, promote, and tear down the stack. Stage 4B
adds the control loop around that engine.

The new version has three extra responsibilities:

- Eyes: `/metrics` exposes Prometheus text for requests, latency, mode, uptime,
  and chaos state.
- Brain: OPA owns every allow/deny decision for deploy and promote.
- Memory: `history.jsonl` records status/policy checks and `audit_report.md`
  renders the audit trail.

## Design

`manifest.yaml` is still the only manual configuration file. It now includes
OPA, policy thresholds, and observability paths. `swiftdeploy init` renders the
OPA sidecar into Compose and mounts `policies/` read-only.

The CLI is the enforcement point, not the policy brain. It collects host stats
or metrics, sends structured input to OPA, prints OPA's reason, and stops before
runtime mutation if OPA denies.

## Guardrails

The infrastructure policy denies deploy if disk free is below the manifest
threshold or CPU load is above the manifest threshold. The canary policy denies
promotion if error rate or p99 latency exceeds the manifest threshold.

The proof bundle includes:

- `02_predeploy_policy_denial.txt`: an intentionally impossible disk threshold
  blocks deploy.
- `06_promote_denied_under_chaos.txt`: canary error chaos blocks promotion.
- `08_opa_no_leakage.txt`: OPA is reachable on localhost but not through Nginx.

## Chaos

In canary mode, `/chaos` can inject slow responses or errors. `/metrics` remains
reachable during chaos so the policy loop can observe the failure instead of
going blind. The promote gate actively probes `/healthz` between metrics scrapes
so an idle canary still produces a measurable policy window.

## Audit

`swiftdeploy status --once` appends a JSONL record containing metrics and policy
compliance. `swiftdeploy audit` converts that raw history into
`audit_report.md`, including a timeline and policy violations.

## Lessons Learned

The important line is the boundary between policy and enforcement. If the CLI
checks thresholds directly, OPA becomes decoration. The defensible design is:
CLI gathers facts, OPA decides, CLI enforces and explains.
