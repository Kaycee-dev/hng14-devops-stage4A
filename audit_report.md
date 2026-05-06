# SwiftDeploy Audit Report

- Generated: `2026-05-06T17:01:37.106455+00:00`
- History records: `6`

## Timeline

| Time | Mode | Chaos | Req/s | Error Rate | P99 Latency |
|---|---|---|---:|---:|---:|
| 2026-05-06T17:00:45.854157+00:00 |  |  | 0.000 | 0.00% | 0.000s |
| 2026-05-06T17:00:50.149461+00:00 |  |  | 0.000 | 0.00% | 0.000s |
| 2026-05-06T17:01:03.811232+00:00 | stable | none | 2.000 | 0.00% | 0.010s |
| 2026-05-06T17:01:08.403921+00:00 | stable | none | 3.917 | 0.00% | 0.005s |
| 2026-05-06T17:01:21.635085+00:00 | canary | error | 4.568 | 100.00% | 0.005s |
| 2026-05-06T17:01:26.224122+00:00 | canary | none | 4.399 | 0.00% | 0.005s |

## Mode And Chaos Changes

- `2026-05-06T17:01:03.811232+00:00` mode=`stable` chaos=`none`
- `2026-05-06T17:01:21.635085+00:00` mode=`canary` chaos=`error`
- `2026-05-06T17:01:26.224122+00:00` mode=`canary` chaos=`none`

## Violations

- `2026-05-06T17:00:45.854157+00:00` `infrastructure` `deny`: infrastructure policy denied: 1 violation(s)
  - `disk_free_too_low`: disk free 121.588GB is below required 1e+06GB
- `2026-05-06T17:01:21.635085+00:00` `canary` `deny`: canary safety policy denied: 1 violation(s)
  - `error_rate_too_high`: error rate 1.0000 is above allowed 0.0100
