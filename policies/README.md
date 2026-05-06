# SwiftDeploy Policies

OPA loads every `.rego` file in this directory from the generated Compose
sidecar. Each policy owns one decision question:

- `swiftdeploy.infrastructure.decision` answers pre-deploy/status host safety.
- `swiftdeploy.canary.decision` answers pre-promote/status canary safety.

Threshold values are not hardcoded here. The CLI reads them from
`manifest.yaml` and passes them to OPA under `input.thresholds`.
