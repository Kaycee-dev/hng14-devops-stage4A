from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SAMPLE_RE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?\s+([-+0-9.eE]+|NaN|\+Inf|-Inf)")
LABEL_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:\\.|[^"\\])*)"')


@dataclass
class MetricSnapshot:
    timestamp: float
    counters: dict[tuple[str, str, str], float]
    buckets: dict[tuple[str, str, str], float]
    gauges: dict[str, float]

    def to_json(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "counters": ["|".join(key) + f"|{value}" for key, value in self.counters.items()],
            "buckets": ["|".join(key) + f"|{value}" for key, value in self.buckets.items()],
            "gauges": self.gauges,
        }


def unescape_label(value: str) -> str:
    return value.replace(r"\"", '"').replace(r"\n", "\n").replace(r"\\", "\\")


def parse_labels(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    return {key: unescape_label(value) for key, value in LABEL_RE.findall(raw)}


def parse_prometheus(text: str, timestamp: float | None = None) -> MetricSnapshot:
    counters: dict[tuple[str, str, str], float] = {}
    buckets: dict[tuple[str, str, str], float] = {}
    gauges: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = SAMPLE_RE.match(line)
        if not match:
            continue
        name, raw_labels, raw_value = match.groups()
        value = float(raw_value)
        labels = parse_labels(raw_labels)
        if name == "http_requests_total":
            counters[
                (
                    labels.get("method", ""),
                    labels.get("path", ""),
                    labels.get("status_code", ""),
                )
            ] = value
        elif name == "http_request_duration_seconds_bucket":
            buckets[
                (
                    labels.get("method", ""),
                    labels.get("path", ""),
                    labels.get("le", ""),
                )
            ] = value
        elif name in {"app_uptime_seconds", "app_mode", "chaos_active"}:
            gauges[name] = value
    return MetricSnapshot(timestamp or time.time(), counters, buckets, gauges)


def scrape_metrics(nginx_port: str | int, timeout: float = 5.0) -> MetricSnapshot:
    url = f"http://127.0.0.1:{nginx_port}/metrics"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return parse_prometheus(body)


def load_recent_history(history_file: Path, window_seconds: int) -> list[dict[str, Any]]:
    if not history_file.is_file():
        return []
    cutoff = time.time() - window_seconds
    records: list[dict[str, Any]] = []
    for line in history_file.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if float(record.get("timestamp", 0)) >= cutoff:
            records.append(record)
    return records


def histogram_quantile(q: float, buckets: dict[str, float]) -> float:
    parsed: list[tuple[float, float]] = []
    inf_count = 0.0
    for le, count in buckets.items():
        if le == "+Inf":
            inf_count = count
        else:
            parsed.append((float(le), count))
    parsed.sort(key=lambda item: item[0])
    total = inf_count or (parsed[-1][1] if parsed else 0.0)
    if total <= 0:
        return 0.0
    target = q * total
    prev_bound = 0.0
    prev_count = 0.0
    for upper, count in parsed:
        if count >= target:
            bucket_count = count - prev_count
            if bucket_count <= 0:
                return upper
            fraction = (target - prev_count) / bucket_count
            return prev_bound + (upper - prev_bound) * fraction
        prev_bound = upper
        prev_count = count
    return parsed[-1][0] if parsed else 0.0


def summarize_snapshots(first: MetricSnapshot | None, last: MetricSnapshot) -> dict[str, Any]:
    elapsed = max(0.0, last.timestamp - first.timestamp) if first else 0.0

    total_requests = 0.0
    error_requests = 0.0
    for key, last_value in last.counters.items():
        first_value = first.counters.get(key, 0.0) if first else 0.0
        delta = max(0.0, last_value - first_value)
        total_requests += delta
        status = key[2]
        if status.startswith("5"):
            error_requests += delta

    aggregate_buckets: dict[str, float] = {}
    for (_method, _path, le), last_value in last.buckets.items():
        first_value = first.buckets.get((_method, _path, le), 0.0) if first else 0.0
        aggregate_buckets[le] = aggregate_buckets.get(le, 0.0) + max(0.0, last_value - first_value)

    app_mode = int(last.gauges.get("app_mode", 0))
    chaos_value = int(last.gauges.get("chaos_active", 0))
    chaos_name = {0: "none", 1: "slow", 2: "error"}.get(chaos_value, "unknown")
    return {
        "window_seconds": round(elapsed, 3),
        "total_requests": int(total_requests),
        "error_requests": int(error_requests),
        "req_per_second": (total_requests / elapsed) if elapsed > 0 else total_requests,
        "error_rate": (error_requests / total_requests) if total_requests > 0 else 0.0,
        "p99_latency_seconds": histogram_quantile(0.99, aggregate_buckets),
        "mode": "canary" if app_mode == 1 else "stable",
        "chaos": chaos_name,
        "app_uptime_seconds": last.gauges.get("app_uptime_seconds", 0.0),
    }
