# Proof Outputs

These plain-text captures are the source for the Google Drive screenshots
required by the Stage 4A brief. To produce a PNG: open the relevant `.txt`
file in a terminal (`less` or `cat`), then screenshot the terminal window.

| Brief screenshot | File | What it proves |
|---|---|---|
| validate output (all 5 PASS) | `01_validate.txt` | All 5 brief-mandated checks pass. exit 0. |
| deploy output | `02_deploy.txt` | Render -> compose up -> nginx waits for app `condition: service_healthy` -> health probe through nginx returns ok. Curl confirms `/` and `/healthz` (in stable mode initially). |
| promote canary + /healthz | `03_promote_canary.txt` | In-place mode flip in manifest, app-only recreate (`--no-deps`), `[PASS] canary confirmed: body.mode=canary AND X-Mode: canary header present`. Slow-chaos timing visible in curl. |
| promote stable + /healthz | `04_promote_stable.txt` | Reverse direction: body.mode=stable AND no X-Mode header. POST /chaos returns 403 with X-Deployed-By header still attached (proves nginx `always` qualifier). |
| Generated configs | `05_generated_configs.txt` | `manifest.yaml` (with comments preserved) + SHA256 of generated files + full `nginx.conf` and `docker-compose.yml`. Every value traces back to a manifest field. |
| Nginx access logs | `06_nginx_access_log.txt` | Brief-mandated format `$time_iso8601 \| $status \| ${request_time}s \| $upstream_addr \| $request`. Includes 502 entries during the recreate window (proves nginx held the gateway up while app cycled) and ~0.5s `request_time` on `/healthz` under slow chaos. |
| Teardown + regen | `07_teardown_and_regen.txt` | `teardown --clean` removes containers, network, named volume, AND generated configs. `init` regenerates byte-identical configs (idempotency proof). |

The earlier `00_validate_with_conflict.txt` (showing check 4 catching a
real port conflict) is no longer captured automatically — the manifest now
defaults to port 18080 which is unlikely to clash on a fresh host. The
"check 4 detects real conflicts" evidence is preserved in evidence ID E-006
in `docs/stage4-control-plane/05_evidence_log.md`.

## Reproducing on another host

```bash
git pull
docker build -t swiftdeploy-stage4a-app:1.0.0 .
bash scripts/capture_evidence.sh
```

The image tag must match the value in `manifest.yaml` (`services.image`)
or check 3 in `validate` will fail.
