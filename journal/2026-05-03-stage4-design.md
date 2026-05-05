# 2026-05-03 - SD4-DESIGN-001 closed

## What I did

Locked the technology stack and rendering contract for SwiftDeploy before any
implementation file lands. Eleven decisions recorded (D-004 through D-014) in
`docs/stage4-control-plane/04_decisions_log.md`. Matching interview defenses
recorded in `08_interview_defense_bank.md`. Brief open-issues list resolved in
`01_brief_traceability.md`. Evidence logged as E-002.

## Why these decisions, in plain words

- **API on Python + FastAPI**: the chaos `slow` mode is literally "wait N
  seconds, then respond." `asyncio.sleep` does this without blocking other
  requests. Flask would need threads; Go would mean switching languages
  mid-stage.
- **CLI in Bash with Python heredocs**: the CLI mostly invokes other tools
  (`docker compose`, `nginx -t`, `curl`). Bash is the right shell for that. The
  parts where Bash is weak (parsing YAML, mutating a YAML field, rendering
  templates, probing a port) are delegated to short Python heredocs. Two halves,
  each easy to defend.
- **pyyaml as a documented prerequisite**: Python's stdlib has no YAML parser.
  A hand parser breaks on whitespace edge cases. README declares the dep.
- **`string.Template` for rendering**: stdlib, no escape hazards (sed cannot
  cleanly handle `:` and `/` in image strings), no third-party Jinja2 needed
  because we have no conditionals.
- **`/chaos` returns 403 in stable mode**: documents the policy. 404 would be
  ambiguous with a typo'd URL.
- **`X-Mode: canary` from middleware**: middleware applies to every response,
  including 4xx/5xx. Per-handler injection misses error paths.
- **Healthcheck via `python -c urllib.request.urlopen(...)`**: `curl` is not in
  `python:3.11-slim`. Apt-getting it adds a layer for one HTTP probe.
- **Port pre-flight via `socket.bind()`**: `ss`/`lsof` missing on this dev shell
  and on minimal Linux containers. Stdlib socket bind is portable and tests the
  same kernel path nginx uses.
- **`nginx -t` inside the same nginx image we ship**: same binary, same compile
  flags, same modules. Host nginx may not exist or may differ.

## What I probed on the dev host (and what it told me)

- `python3` does not exist as a real interpreter here (Microsoft Store stub).
  Drove D-006 (the CLI must resolve `python3 || python`).
- `pyyaml 6.0.3` is importable via `python -c "import yaml"`. Confirmed the
  pyyaml prerequisite is realistic.
- `ss`, `lsof`, `nc` all missing. Drove D-012 (`socket.bind()` probe).
- `curl` and bash 5.2 are present locally; Compose v2 plugin v5.1.2 confirmed.

## What I can defend in interview right now

- Why FastAPI vs Flask vs Go.
- Why bash vs pure Python for the CLI.
- Why pyyaml vs hand parser vs vendored micro-yaml.
- Why `string.Template` vs sed vs envsubst vs Jinja2.
- Why 403 (not 404) for `/chaos` in stable mode.
- Why middleware (not per-route) for the X-Mode header.
- Why urllib (not curl) for the in-container healthcheck.
- Why `socket.bind()` (not `ss`) for the port pre-flight check.
- Why containerized `nginx -t` (not host nginx) for syntax validation.

## Next packet

`SD4-APP-001`. Implementation_allowed flips to `true` after the checker passes
post-edit. The next teach-back will cover process uptime semantics, the chaos
state machine, and the X-Mode middleware contract.
