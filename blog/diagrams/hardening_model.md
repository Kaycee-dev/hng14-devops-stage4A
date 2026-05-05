# Container hardening model

```mermaid
flowchart TB
    subgraph Image[Image: swift-deploy-1-node:latest]
        Base[python:3.11-slim<br/>~150 MB base]
        Deps[fastapi + uvicorn[standard] + pyyaml<br/>~86 MB]
        Code[app/ source<br/>~30 KB]
        User[appuser uid/gid 10001<br/>no-create-home<br/>shell=nologin]
        HC[HEALTHCHECK:<br/>python -c urllib.urlopen /healthz]
    end

    subgraph Runtime[Runtime: docker compose]
        UB[user: 10001:10001]
        CD[cap_drop: ALL]
        CA[nginx adds back:<br/>CHOWN, SETUID,<br/>SETGID, NET_BIND_SERVICE]
        SO[security_opt:<br/>no-new-privileges:true]
        NP[app: no ports: mapping<br/>nginx publishes only NGINX_PORT]
    end

    Image --> Runtime
```

Each runtime hardening directive stacks on the image-level non-root user.
Final image size: 236 MB (under the 300 MB cap).
