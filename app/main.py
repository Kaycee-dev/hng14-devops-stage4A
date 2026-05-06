import asyncio
import os
import random
import time
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

MODE = os.getenv("MODE", "stable")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
APP_PORT = int(os.getenv("APP_PORT", "3000"))

# time.monotonic() is used (not time.time()) so uptime cannot go backward when
# the wall clock is corrected by NTP or set manually.
START_TIME = time.monotonic()

chaos_state: dict = {"mode": None, "duration": 0.0, "rate": 0.0}

# Prometheus client default histogram buckets. Kept explicit so the operator can
# explain exactly how P99 is derived from the exported cumulative buckets.
METRIC_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    2.5,
    5.0,
    7.5,
    10.0,
)

metrics_lock = Lock()
http_requests_total: defaultdict[tuple[str, str, str], int] = defaultdict(int)
http_request_duration_buckets: defaultdict[tuple[str, str], list[int]] = defaultdict(
    lambda: [0 for _ in METRIC_BUCKETS]
)
http_request_duration_sum: defaultdict[tuple[str, str], float] = defaultdict(float)
http_request_duration_count: defaultdict[tuple[str, str], int] = defaultdict(int)

app = FastAPI(title="swiftdeploy-app", version=APP_VERSION)


class ChaosRequest(BaseModel):
    mode: Literal["slow", "error", "recover"]
    duration: Optional[float] = Field(default=None, ge=0)
    rate: Optional[float] = Field(default=None, ge=0, le=1)


@app.middleware("http")
async def chaos_middleware(request: Request, call_next):
    # /chaos itself is exempt so an operator can recover when error-rate is 1.0.
    # /metrics is also exempt so the policy/status loop can observe degradation.
    if request.url.path not in ("/chaos", "/metrics"):
        active = chaos_state["mode"]
        if active == "slow" and chaos_state["duration"] > 0:
            await asyncio.sleep(chaos_state["duration"])
        elif active == "error" and chaos_state["rate"] > 0:
            if random.random() < chaos_state["rate"]:
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "chaos error injected",
                        "rate": chaos_state["rate"],
                    },
                )
    return await call_next(request)


@app.middleware("http")
async def mode_middleware(request: Request, call_next):
    # Registered after chaos_middleware so this is the outer wrapper: it sees
    # the final response (including chaos-injected 500s) and stamps X-Mode on
    # every canary response.
    response = await call_next(request)
    if MODE == "canary":
        response.headers["X-Mode"] = "canary"
    return response


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    started = time.monotonic()
    status_code = 500
    response = await call_next(request)
    status_code = response.status_code

    # Do not count scrape traffic as application throughput; otherwise the
    # status command would create the traffic it is trying to measure.
    if request.url.path != "/metrics":
        observe_http_request(
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration=time.monotonic() - started,
        )
    return response


def observe_http_request(method: str, path: str, status_code: int, duration: float) -> None:
    method = method.upper()
    status = str(status_code)
    request_key = (method, path, status)
    duration_key = (method, path)
    with metrics_lock:
        http_requests_total[request_key] += 1
        http_request_duration_sum[duration_key] += duration
        http_request_duration_count[duration_key] += 1
        bucket_counts = http_request_duration_buckets[duration_key]
        for index, bucket in enumerate(METRIC_BUCKETS):
            if duration <= bucket:
                bucket_counts[index] += 1


def escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def chaos_active_value() -> int:
    active = chaos_state["mode"]
    if active == "slow":
        return 1
    if active == "error":
        return 2
    return 0


def prometheus_metrics() -> str:
    with metrics_lock:
        request_items = sorted(http_requests_total.items())
        duration_items = sorted(http_request_duration_count.items())
        bucket_snapshot = {
            key: list(value) for key, value in http_request_duration_buckets.items()
        }
        sum_snapshot = dict(http_request_duration_sum)

    lines = [
        "# HELP http_requests_total Total HTTP requests by method, path, and status code.",
        "# TYPE http_requests_total counter",
    ]
    for (method, path, status_code), count in request_items:
        labels = (
            f'method="{escape_label(method)}",'
            f'path="{escape_label(path)}",'
            f'status_code="{escape_label(status_code)}"'
        )
        lines.append(f"http_requests_total{{{labels}}} {count}")

    lines.extend(
        [
            "# HELP http_request_duration_seconds HTTP request latency histogram in seconds.",
            "# TYPE http_request_duration_seconds histogram",
        ]
    )
    for (method, path), count in duration_items:
        base_labels = f'method="{escape_label(method)}",path="{escape_label(path)}"'
        bucket_counts = bucket_snapshot[(method, path)]
        for bucket, count in zip(METRIC_BUCKETS, bucket_counts):
            lines.append(
                f'http_request_duration_seconds_bucket{{{base_labels},le="{bucket:g}"}} {count}'
            )
        count = http_request_duration_count[(method, path)]
        lines.append(
            f'http_request_duration_seconds_bucket{{{base_labels},le="+Inf"}} {count}'
        )
        lines.append(
            f"http_request_duration_seconds_sum{{{base_labels}}} {sum_snapshot[(method, path)]:.9f}"
        )
        lines.append(f"http_request_duration_seconds_count{{{base_labels}}} {count}")

    lines.extend(
        [
            "# HELP app_uptime_seconds Process uptime in seconds.",
            "# TYPE app_uptime_seconds gauge",
            f"app_uptime_seconds {time.monotonic() - START_TIME:.3f}",
            "# HELP app_mode Current deployment mode, stable=0 and canary=1.",
            "# TYPE app_mode gauge",
            f"app_mode {1 if MODE == 'canary' else 0}",
            "# HELP chaos_active Current chaos state, none=0 slow=1 error=2.",
            "# TYPE chaos_active gauge",
            f"chaos_active {chaos_active_value()}",
        ]
    )
    return "\n".join(lines) + "\n"


@app.get("/")
async def root():
    return {
        "message": "swiftdeploy app online",
        "mode": MODE,
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/healthz")
async def healthz():
    return {
        "status": "ok",
        "uptime": round(time.monotonic() - START_TIME, 3),
    }


@app.get("/metrics")
async def metrics():
    return Response(
        content=prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.post("/chaos")
async def chaos(request: Request):
    # Mode check runs before body parsing so the stable-mode 403 is the
    # authoritative answer, not an accidental 422 from missing fields.
    if MODE != "canary":
        raise HTTPException(status_code=403, detail="chaos disabled in stable mode")

    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="chaos requires a JSON body")
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="chaos body must be a JSON object")

    try:
        payload = ChaosRequest(**raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid chaos payload: {exc}")

    if payload.mode == "slow":
        if payload.duration is None:
            raise HTTPException(status_code=400, detail="slow requires 'duration'")
        chaos_state.update(
            {"mode": "slow", "duration": float(payload.duration), "rate": 0.0}
        )
    elif payload.mode == "error":
        if payload.rate is None:
            raise HTTPException(status_code=400, detail="error requires 'rate'")
        chaos_state.update(
            {"mode": "error", "duration": 0.0, "rate": float(payload.rate)}
        )
    else:  # recover
        chaos_state.update({"mode": None, "duration": 0.0, "rate": 0.0})

    return {"chaos": dict(chaos_state)}
