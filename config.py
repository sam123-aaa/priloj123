import os

from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
ALLOWED_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
SECURITY_RATE_LIMIT_PER_MINUTE = int(os.getenv("SECURITY_RATE_LIMIT_PER_MINUTE", "120"))
