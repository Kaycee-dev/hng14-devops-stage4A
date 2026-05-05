# `swiftdeploy init` rendering pipeline

```mermaid
flowchart LR
    M[manifest.yaml<br/>single source of truth]
    Tn[templates/nginx.conf.tmpl<br/>$\{VAR\} placeholders]
    Tc[templates/docker-compose.tmpl<br/>$\{VAR\} placeholders]
    R{{Python helper:<br/>yaml.safe_load + defaults<br/>+ string.Template.safe_substitute}}
    Nout[nginx.conf<br/>generated, atomic write]
    Cout[docker-compose.yml<br/>generated, atomic write]

    M --> R
    Tn --> R
    Tc --> R
    R --> Nout
    R --> Cout
```

Atomic write = render to a temp file in the same directory, then
`os.replace` to the final name. A crash mid-render leaves the previous
version (if any) untouched.
