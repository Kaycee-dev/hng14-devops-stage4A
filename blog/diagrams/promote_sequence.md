# `swiftdeploy promote canary` sequence

```mermaid
sequenceDiagram
    participant CLI as swiftdeploy
    participant FS as manifest.yaml
    participant TR as Template renderer
    participant DC as docker compose
    participant N as nginx (running)
    participant A as app (recreated)
    participant H as /healthz via nginx

    CLI->>FS: regex edit services.mode -> "canary"
    FS-->>CLI: post-edit YAML parses (sanity check)
    CLI->>TR: init
    TR-->>FS: read
    TR->>FS: write nginx.conf, docker-compose.yml
    CLI->>DC: up -d --no-deps --force-recreate app
    DC->>A: stop, remove, create with MODE=canary
    Note right of N: nginx untouched - gateway stays up<br/>(502 for ~3s during recreate)
    DC->>A: start
    DC-->>A: healthcheck (urllib /healthz, 10s interval)
    A-->>DC: 200 OK
    loop poll up to 60s
        CLI->>H: GET /healthz
    end
    H-->>CLI: 200 + status=ok
    CLI->>H: GET /
    H-->>CLI: 200, body.mode=canary, X-Mode: canary
    CLI->>CLI: assert both signals -> [PASS] canary confirmed
```

The two-signal assertion (body.mode AND X-Mode header) is defense in depth:
either signal alone could be wrong if the X-Mode middleware or the / handler
were broken; together they prove the deployment is genuinely canary.
