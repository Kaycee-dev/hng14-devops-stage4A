# 2026-05-03 - SD4-TEMPLATE-001 closed

## What I built

`templates/nginx.conf.tmpl`, `templates/docker-compose.tmpl`, and a short
`templates/README.md` that documents the placeholder contract. No generated
files yet — those land in CLI-001.

## Numbers worth knowing

- 27/27 token assertions PASS on rendered nginx + compose.
- `nginx -t` against the rendered nginx.conf via `docker run nginx:latest` -> `syntax is ok`, `test is successful`, exit 0.
- `docker compose config --quiet` against the rendered compose -> exit 0.
- Confirmed `app` service has NO `ports:` key (brief mandate).

## What I can defend without AI

- **Why `${VAR}` placeholders, not Jinja2**: zero conditional rendering needs;
  `string.Template.safe_substitute` is stdlib and exact.
- **Why `$$` in the template**: Python `string.Template` treats `$$` as a
  literal `$`. The brief's log format requires the literal nginx variable
  `${request_time}` (with braces, to disambiguate the trailing `s`), so the
  template stores `$${request_time}s`. Same escape used for `$$host`,
  `$$remote_addr`, `$$proxy_add_x_forwarded_for`, `$$scheme`.
- **Why `add_header ... always;`**: without `always`, nginx only adds the
  header on 2xx/3xx; the JSON 502/503/504 bodies would not carry X-Deployed-By
  otherwise. The brief implies "every response," so `always` is required.
- **Why `error_page 502 = @err502;` with the `=`**: the `=` lets our named
  location's `return 502` set the actual response status, instead of being
  ignored in favor of the upstream's original code.
- **Why no `ports:` on the app service**: brief mandate. All traffic flows
  through nginx so the proxy contract (X-Deployed-By, X-Mode forwarding,
  access log format, JSON error bodies) actually applies.
- **Why `cap_drop: ALL` plus `cap_add` for nginx**: nginx forks workers and
  drops them to the `nginx` user — requires SETUID, SETGID, NET_BIND_SERVICE,
  and CHOWN for the worker pidfile. Drop everything, then add back the exact
  four needed.
- **Why the named log volume is on `app` only, not nginx**: the upstream
  `nginx:latest` image symlinks `/var/log/nginx/access.log` to `/dev/stdout`.
  Mounting a real volume over that breaks `docker compose logs nginx`, which
  is exactly what the grader will screenshot.

## What surprised me

- Running `nginx:latest nginx -t` triggers the upstream entrypoint script
  (`docker-entrypoint.sh`) which runs `10-listen-on-ipv6-by-default.sh` and
  appears to mutate the conf even when mounted `:ro`. For the validate
  screenshot in CLI-001, I'll bypass with `--entrypoint nginx ... -t -q` so
  the output is just the success line.

## What I did NOT do

- No `manifest.yaml` (CLI-001).
- No `swiftdeploy` script (CLI-001).
- No actual generated `nginx.conf` or `docker-compose.yml` at the repo root.

## Next packet

`SD4-CLI-001`: write `manifest.yaml` and the `swiftdeploy` Bash script with
`init` and `validate`. Prove init is idempotent (deletes regenerate
identically) and validate runs all five required checks.
