import json
import ssl
from datetime import timedelta

from config import REDIS_URL

try:
    import redis
except ModuleNotFoundError:
    redis = None


TASK_STATUS_TTL = timedelta(hours=24)


def _get_client():
    if redis is None:
        return None
    kwargs = {
        "decode_responses": True,
        "socket_connect_timeout": 20,
        "socket_timeout": 30,
        "retry_on_timeout": True,
        "health_check_interval": 0,
    }
    if REDIS_URL.startswith("rediss://"):
        kwargs["ssl_cert_reqs"] = ssl.CERT_NONE
    return redis.Redis.from_url(REDIS_URL, **kwargs)


def set_task_status(task_id: str, status: str, meta=None):
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(
            f"task-status:{task_id}",
            int(TASK_STATUS_TTL.total_seconds()),
            json.dumps({"task_id": task_id, "status": status, "meta": meta or {}}, ensure_ascii=False, default=str),
        )
    except Exception:
        return


def get_task_status(task_id: str):
    client = _get_client()
    if client is None:
        return None
    try:
        raw_value = client.get(f"task-status:{task_id}")
    except Exception:
        return None
    if not raw_value:
        return None
    return json.loads(raw_value)
