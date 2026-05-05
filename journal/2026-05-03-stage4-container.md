# 2026-05-03 - SD4-CONTAINER-001 closed

## What I built

`Dockerfile` and `.dockerignore`. Built `swift-deploy-1-node:latest`. Confirmed
236 MB on `docker images`, ran the container, hit `/` and `/healthz`, watched
the in-container HEALTHCHECK pass three times in a row.

## Numbers worth knowing

- Image size: 236 MB. Cap is 300 MB. Headroom: 64 MB.
- UID/GID inside container: 10001 / 10001 (`appuser`). Non-root.
- Python: 3.11.15 (matches the `python:3.11-slim` base).
- HEALTHCHECK ExitCode: 0 across multiple intervals using stdlib urllib.

## What I can defend without AI

- **Why slim and not alpine**: uvloop/httptools wheels are glibc-only. Alpine
  would force a from-source compile that can balloon the image and add a build
  toolchain layer.
- **Why requirements.txt is COPY'd before the source**: Docker layer cache.
  Editing `main.py` then rebuilding skips the pip step entirely.
- **Why `--no-cache-dir`**: pip's wheel cache is per-layer in Docker and never
  reused — caching it just bakes ~30 MB of unused tarballs into the image.
- **Why `cap_drop: ALL` is NOT in the Dockerfile**: capabilities are a runtime
  property of the container, not a build-time property. That decision goes in
  the Compose template (next packet).
- **Why uid 10001 explicitly, not `useradd -r`**: high UID dodges collisions
  with bind-mounted paths owned by low-numbered host users; also documents
  intent rather than relying on whatever number `-r` picks.
- **Why no `EXPOSE` in the Dockerfile / no host port mapping in this packet**:
  the brief forbids exposing the app port directly. The container listens on
  3000 internally; only nginx publishes a host port. Compose enforces that.

## What broke and how I fixed it

- First build: `useradd warning: appuser's uid 10001 is greater than SYS_UID_MAX 999`.
  Caused by `--system` plus an explicit high UID — `--system` expects a UID
  under 1000. I dropped `--system` and used `groupadd --gid 10001` +
  `useradd --uid 10001 --gid 10001`. Warning gone, behavior identical.
  This is a small thing but it'd be embarrassing on a screenshot.

## What I did NOT do

- No Compose file. No nginx.conf. No CLI. No `cap_drop: ALL` directive (that
  belongs in the Compose template).

## Next packet

`SD4-TEMPLATE-001`: write `templates/nginx.conf.tmpl` and
`templates/docker-compose.tmpl`. These are the *intent* files that the CLI's
`init` will render into `nginx.conf` and `docker-compose.yml` from the
manifest.
