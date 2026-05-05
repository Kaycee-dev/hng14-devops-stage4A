# Architecture diagram (Mermaid)

```mermaid
flowchart LR
    Client[Client / browser / curl]
    Nginx[nginx:latest<br/>0.0.0.0:NGINX_PORT<br/>X-Deployed-By: swiftdeploy<br/>JSON 502/503/504]
    App[swift-deploy-1-node:latest<br/>FastAPI on uvicorn<br/>MODE = stable | canary<br/>Internal only - no host port]
    Volume[(swiftdeploy-logs<br/>named volume)]

    Client -->|HTTP| Nginx
    Nginx -->|upstream<br/>app_backend| App
    App -->|writes| Volume

    classDef internal stroke-dasharray: 4 4
    class App internal
```

The dashed border on the app node marks it as internal-only: it has no
`ports:` mapping in the rendered compose file. Every byte in or out
traverses nginx.
