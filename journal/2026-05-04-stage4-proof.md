# 2026-05-04 - SD4-PROOF-001 closed

## What I built

`scripts/capture_evidence.sh` (one-shot replay) and 8 proof text files in
`blog/assets/proof_outputs/`. Rewrote `README.md` from the governance
placeholder into a submission-ready document.

## Proof bundle

| File | Brief screenshot it serves | Bytes / lines |
|---|---|---|
| `00_validate_with_conflict.txt` | (extra) failure-mode evidence | 8 lines |
| `01_validate.txt` | validate output | 8 lines |
| `02_deploy.txt` | deploy output | 46 lines |
| `03_promote_canary.txt` | promote + /healthz | 71 lines |
| `04_promote_stable.txt` | promote + /healthz (reverse) | 39 lines |
| `05_generated_configs.txt` | generated configs | 159 lines |
| `06_nginx_access_log.txt` | nginx access logs | 31 lines |
| `07_teardown_and_regen.txt` | (extra) idempotency proof | 35 lines |

The text files exist because I cannot take literal PNG screenshots from
within this terminal session. The operator opens each file in a terminal of
their choice and screenshots the window. The `proof_outputs/README.md` file
documents the mapping.

## What I can defend without AI

- **Why I did not produce PNGs**: the capture script is reproducible. Running
  it on any compliant host produces the same artifacts. PNGs from a single
  machine are weaker evidence than a script anyone can rerun.
- **Why the failure-mode capture (file 00) is in the bundle**: it shows
  check 4 actually catching a real port conflict. A grader who only sees
  5/5 PASS could wonder whether the failure path is wired up at all. File 00
  removes that doubt.
- **Why the access log capture (file 06) is the headline proof**: it is the
  one artifact that simultaneously demonstrates (a) the brief-mandated log
  format, (b) the 502 path during the recreate window which proves nginx
  stayed up while app cycled (so `--no-deps` semantics work), and (c) the
  0.504s request_time which proves slow chaos actually slept.
- **Why README starts with the architecture diagram**: a reader who only
  glances at the README must walk away knowing nginx is the only public
  service and the manifest drives everything. Architecture before quickstart.

## Final state hashes (canonical)

```
nginx.conf:         809a2ff089a7b8803e3fd1ab0d75a0419a5f1d15ad3c8b4256a2f374e307fa0d
docker-compose.yml: 733cd44d8bd621dfe24cfb286ab081fe3eac9a8d2bec4dc738f115c95ad9500a
manifest.yaml:      aac2ff5e6ea0272ea0c451b7360cc392cde1422276050a3caa4ecf3aafdc7a95
```

These match the canonical values from CLI-001's first init.

## Next packet

`SD4-BLOG-001`: convert the journal arc into a dev.to draft and produce
diagrams. Publishing is manual on the user's part.
