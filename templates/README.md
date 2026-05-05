# Templates

These two files are the *intent* layer. The CLI's `init` command renders them
into `nginx.conf` and `docker-compose.yml` at the repo root using values from
`manifest.yaml`. Do not hand-edit the generated outputs; edit the manifest and
rerun `init`.

## Placeholder syntax

Placeholders use Python `string.Template` syntax: `${NAME}`. To emit a literal
`$` (e.g. nginx variables like `$request_time` or shell variables like
`$host`), the template uses `$$` which `string.Template` renders as a single
`$`.

## Required placeholders

The renderer supplies these from `manifest.yaml` plus the defaults documented
in `docs/stage4-control-plane/04_decisions_log.md` (D-009):

| Placeholder | Source | Default if missing |
|---|---|---|
| `SERVICE_IMAGE` | `services.image` | required |
| `SERVICE_PORT` | `services.port` | required |
| `MODE` | `services.mode` | `stable` |
| `APP_VERSION` | `services.version` | `1.0.0` |
| `RESTART_POLICY` | `services.restart_policy` | `unless-stopped` |
| `LOG_VOLUME` | `services.log_volume` | `swiftdeploy-logs` |
| `NGINX_IMAGE` | `nginx.image` | required |
| `NGINX_PORT` | `nginx.port` | required |
| `PROXY_TIMEOUT` | `nginx.proxy_timeout` | `30` |
| `ERROR_CONTACT` | `nginx.error_contact` | `ops@swiftdeploy.local` |
| `NETWORK_NAME` | `network.name` | required |
| `NETWORK_DRIVER` | `network.driver_type` | required |
