import logging
import threading
import time
from collections import defaultdict, deque
from typing import Dict, Optional, Tuple

from fastapi import Request

logger = logging.getLogger("maintenance.observability")

_REQUEST_LOCK = threading.Lock()
_REQUEST_COUNTS = defaultdict(int)
_REQUEST_ERRORS = defaultdict(int)
_REQUEST_DURATIONS_MS = defaultdict(float)
_REQUEST_RECORD_COUNTS = defaultdict(int)
_RECENT_REQUESTS = deque(maxlen=100)
_RATE_LIMIT_STATE = defaultdict(deque)


def record_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    records_count: Optional[int] = None,
):
    key = (method.upper(), path)
    with _REQUEST_LOCK:
        _REQUEST_COUNTS[key] += 1
        _REQUEST_DURATIONS_MS[key] += duration_ms
        if status_code >= 400:
            _REQUEST_ERRORS[key] += 1
        if records_count is not None:
            _REQUEST_RECORD_COUNTS[key] += records_count
        _RECENT_REQUESTS.append(
            {
                "method": method.upper(),
                "path": path,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2),
                "records_count": records_count,
                "created_at": time.time(),
            }
        )


def record_count(payload) -> Optional[int]:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                return len(value)
    return None


def metrics_snapshot():
    with _REQUEST_LOCK:
        endpoints = []
        for key, count in sorted(_REQUEST_COUNTS.items()):
            method, path = key
            total_duration = _REQUEST_DURATIONS_MS[key]
            endpoints.append(
                {
                    "method": method,
                    "path": path,
                    "requests": count,
                    "errors": _REQUEST_ERRORS[key],
                    "avg_duration_ms": round(total_duration / count, 2) if count else 0,
                    "records_observed": _REQUEST_RECORD_COUNTS[key],
                }
            )
        return {
            "endpoints": endpoints,
            "recent_requests": list(_RECENT_REQUESTS),
        }


def hot_points_snapshot(limit: int = 10):
    snapshot = metrics_snapshot()["endpoints"]
    return sorted(
        snapshot,
        key=lambda item: (item["errors"], item["avg_duration_ms"], item["requests"]),
        reverse=True,
    )[:limit]


def check_rate_limit(request: Request, limit_per_minute: int) -> Tuple[bool, int]:
    if limit_per_minute <= 0:
        return True, limit_per_minute

    client_host = request.client.host if request.client else "unknown"
    key = (client_host, request.url.path)
    now = time.monotonic()
    window_start = now - 60
    bucket = _RATE_LIMIT_STATE[key]
    while bucket and bucket[0] < window_start:
        bucket.popleft()

    if len(bucket) >= limit_per_minute:
        return False, 0

    bucket.append(now)
    return True, limit_per_minute - len(bucket)
