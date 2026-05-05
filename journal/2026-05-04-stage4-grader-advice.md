# 2026-05-04 - Grader-advice compliance pass

## What changed

Two pieces of channel advice landed after all seven packets had closed:

1. Generated files in the repo root, not a `generated/` subfolder. Dockerfile
   in the repo root. (We were already compliant; verified with `git status`.)
2. Image name should be unique per submission. Port can be any value.
   (We were using the brief's examples; updated.)

## Concrete edits

| File | Change |
|---|---|
| `manifest.yaml` | `services.image` -> `swiftdeploy-stage4a-app:1.0.0`; `nginx.port` -> `18080`. Re-rendered. |
| `nginx.conf` (generated) | Now has `listen 18080;`. |
| `docker-compose.yml` (generated) | Image and `18080:18080` host mapping reflect the manifest. |
| `README.md` | Quickstart, manifest field table, and reproduction example use the new tag and port. |
| `scripts/capture_evidence.sh` | Removed the temporary 8080->18080 port-flip dance. Now reads `nginx.port` from the manifest and threads it through every curl. |
| `blog/assets/proof_outputs/00_validate_with_conflict.txt` | Removed (obsolete; manifest no longer defaults to 8080). |
| `blog/assets/proof_outputs/README.md` | File map updated; reproduction example uses new tag. |
| `docs/stage4-control-plane/04_decisions_log.md` | Added D-015 (rationale for the rename and port choice). |
| `docs/stage4-control-plane/05_evidence_log.md` | Added E-010 (compliance audit + queued rebuild). |

## New canonical hashes

```
manifest.yaml       361d626eae9b953ef7e34dbc60398eaae99f8af395991e150ed0a25757719eaa
nginx.conf          8ceedb2e5c67a8887172a8bc14db977d0c47a783db33e5219e806a238b65c0f3
docker-compose.yml  f4e79d67075b95d0a576fd2a2abf680a3dfae9845d00965d57cbc3a4cdb2087d
```

## What I can defend without AI

- "I changed the image name *because the grader said to*. The decision is
  documented in D-015 with alternatives considered. I did not need to change
  any code; the rename is pure manifest data — that is exactly the contract
  the rest of the build is built on."
- "Port 18080 is high enough to dodge common dev-box collisions (Apache often
  holds 8080) and high enough to avoid IANA-reserved ranges. The same script
  works at any port; this is a manifest value, not a constant."

## Operator step queued

Docker Desktop was offline when this compliance pass ran, so the rebuild
and recapture have to happen on the operator's machine before the final
GitHub push:

```bash
docker build -t swiftdeploy-stage4a-app:1.0.0 .
bash scripts/capture_evidence.sh
git add -A
git commit -m "Stage 4A SwiftDeploy submission"
git push
```

## Submission status

- Code, configs, and docs reflect the grader's advice.
- Proof bundle text files exist; they need refreshing to show the new image
  and port. The capture script does that in one command.
- All seven packets remain closed.
- Submission gate stays `ready_for_operator_handoff`.
