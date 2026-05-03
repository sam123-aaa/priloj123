import ssl

from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

try:
    from celery import Celery
except ModuleNotFoundError:
    Celery = None


def create_celery_app():
    if Celery is None:
        raise RuntimeError("Package 'celery' is required for background queue support")

    app = Celery(
        "maintenance_system",
        broker=CELERY_BROKER_URL,
        backend=CELERY_RESULT_BACKEND,
    )
    ssl_options = None
    if CELERY_BROKER_URL.startswith("rediss://") or CELERY_RESULT_BACKEND.startswith("rediss://"):
        ssl_options = {"ssl_cert_reqs": ssl.CERT_NONE}

    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        broker_connection_retry=True,
        broker_connection_retry_on_startup=True,
        broker_connection_max_retries=None,
        broker_pool_limit=1,
        broker_heartbeat=0,
        broker_transport_options={
            "health_check_interval": 0,
            "socket_keepalive": True,
            "socket_connect_timeout": 20,
            "socket_timeout": 30,
            "retry_on_timeout": True,
            "visibility_timeout": 3600,
        },
        result_backend_always_retry=True,
        redis_backend_health_check_interval=0,
        result_backend_transport_options={
            "socket_connect_timeout": 20,
            "socket_timeout": 30,
            "retry_on_timeout": True,
            "visibility_timeout": 3600,
        },
    )
    if ssl_options:
        app.conf.broker_use_ssl = ssl_options
        app.conf.redis_backend_use_ssl = ssl_options
    return app


celery_app = create_celery_app() if Celery is not None else None
