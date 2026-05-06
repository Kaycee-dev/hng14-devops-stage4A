# SwiftDeploy Audit Report

- Generated: `2026-05-06T18:37:17.008259+00:00`
- History records: `6`

## Timeline

| Time | Mode | Chaos | Req/s | Error Rate | P99 Latency |
|---|---|---|---:|---:|---:|
| 2026-05-06T18:36:54.646135+00:00 |  |  | 0.000 | 0.00% | 0.000s |
| 2026-05-06T18:36:55.572779+00:00 |  |  | 0.000 | 0.00% | 0.000s |
| 2026-05-06T18:37:02.816576+00:00 | stable | none | 2.000 | 0.00% | 0.005s |
| 2026-05-06T18:37:04.856452+00:00 | stable | none | 4.721 | 0.00% | 0.005s |
| 2026-05-06T18:37:10.281061+00:00 | canary | error | 4.469 | 100.00% | 0.005s |
| 2026-05-06T18:37:12.421629+00:00 | canary | none | 4.519 | 0.00% | 0.005s |

## Mode And Chaos Changes

- `2026-05-06T18:37:02.816576+00:00` mode=`stable` chaos=`none`
- `2026-05-06T18:37:10.281061+00:00` mode=`canary` chaos=`error`
- `2026-05-06T18:37:12.421629+00:00` mode=`canary` chaos=`none`

## Violations

- `2026-05-06T18:36:54.646135+00:00` `infrastructure` `deny`: infrastructure policy denied: 1 violation(s)
  - `disk_free_too_low`: disk free 121.359GB is below required 1e+06GB
- `2026-05-06T18:37:10.281061+00:00` `canary` `deny`: canary safety policy denied: 1 violation(s)
  - `error_rate_too_high`: error rate 1.0000 is above allowed 0.0100
