# Chaos state machine (canary mode only)

```mermaid
stateDiagram-v2
    [*] --> Off: process start

    Off --> Slow: POST /chaos<br/>{mode: slow, duration: N}
    Off --> Error: POST /chaos<br/>{mode: error, rate: 0..1}

    Slow --> Off: POST /chaos<br/>{mode: recover}
    Slow --> Error: POST /chaos<br/>{mode: error, rate: 0..1}
    Slow --> Slow: POST /chaos<br/>{mode: slow, duration: M}

    Error --> Off: POST /chaos<br/>{mode: recover}
    Error --> Slow: POST /chaos<br/>{mode: slow, duration: N}
    Error --> Error: POST /chaos<br/>{mode: error, rate: r'}

    state "Off (no chaos)" as Off
    state "Slow (sleep N s on every non-/chaos request)" as Slow
    state "Error (return 500 with probability rate)" as Error
```

In stable mode every transition above is replaced by a single response: 403
with `{"detail": "chaos disabled in stable mode"}`. The state machine never
moves.

The `/chaos` endpoint itself is exempt from chaos effects so that an
operator can always recover from rate=1.0 or duration=10000.
