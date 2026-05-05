import asyncio
import os
import random
import time
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

MODE = os.getenv("MODE", "stable")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
APP_PORT = int(os.getenv("APP_PORT", "3000"))

# time.monotonic() is used (not time.time()) so uptime cannot go backward when
# the wall clock is corrected by NTP or set manually.
START_TIME = time.monotonic()

chaos_state: dict = {"mode": None, "duration": 0.0, "rate": 0.0}

app = FastAPI(title="swiftdeploy-app", version=APP_VERSION)


class ChaosRequest(BaseModel):
    mode: Literal["slow", "error", "recover"]
    duration: Optional[float] = Field(default=None, ge=0)
    rate: Optional[float] = Field(default=None, ge=0, le=1)


@app.middleware("http")
async def chaos_middleware(request: Request, call_next):
    # /chaos itself is exempt from chaos effects so an operator can always
    # recover when error-rate is 1.0 or slow-duration is huge.
    if request.url.path != "/chaos":
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
