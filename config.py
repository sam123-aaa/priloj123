import os
import warnings

from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "local").strip().lower()
DEBUG = os.getenv("DEBUG", "0").strip().lower() in {"1", "true", "yes", "on", "debug"}
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
ALLOWED_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173,"
        "http://localhost,https://localhost,capacitor://localhost",
    ).split(",")
    if origin.strip()
]
SECURITY_RATE_LIMIT_PER_MINUTE = int(os.getenv("SECURITY_RATE_LIMIT_PER_MINUTE", "120"))
LOGIN_BRUTEFORCE_MAX_ATTEMPTS = int(os.getenv("LOGIN_BRUTEFORCE_MAX_ATTEMPTS", "5"))
LOGIN_BRUTEFORCE_BLOCK_SECONDS = int(os.getenv("LOGIN_BRUTEFORCE_BLOCK_SECONDS", "600"))
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", ",".join(ALLOWED_CORS_ORIGINS)).split(",")
    if origin.strip()
]
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "csrf_token")
CSRF_HEADER_NAME = os.getenv("CSRF_HEADER_NAME", "X-CSRF-Token")
CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "lax").lower()
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "0") == "1"


def _validate_security_config():
    if SECURITY_RATE_LIMIT_PER_MINUTE <= 0:
        raise ValueError("SECURITY_RATE_LIMIT_PER_MINUTE must be positive")
    if LOGIN_BRUTEFORCE_MAX_ATTEMPTS <= 0:
        raise ValueError("LOGIN_BRUTEFORCE_MAX_ATTEMPTS must be positive")
    if LOGIN_BRUTEFORCE_BLOCK_SECONDS <= 0:
        raise ValueError("LOGIN_BRUTEFORCE_BLOCK_SECONDS must be positive")
    if CSRF_COOKIE_SAMESITE not in {"strict", "lax", "none"}:
        raise ValueError("CSRF_COOKIE_SAMESITE must be strict, lax or none")
    if CSRF_COOKIE_SAMESITE == "none" and not CSRF_COOKIE_SECURE:
        raise ValueError("CSRF_COOKIE_SECURE=1 is required when CSRF_COOKIE_SAMESITE=none")

    if APP_ENV in {"production", "prod"}:
        if DEBUG:
            raise ValueError("DEBUG must be disabled in production")
        if not ALLOWED_CORS_ORIGINS:
            raise ValueError("ALLOWED_CORS_ORIGINS must be explicit in production")
        if "*" in ALLOWED_CORS_ORIGINS:
            raise ValueError("Wildcard CORS origin is forbidden in production")
        if any("localhost" in origin.lower() or "127.0.0.1" in origin for origin in ALLOWED_CORS_ORIGINS):
            raise ValueError("Localhost CORS origins are forbidden in production")
        local_secret = os.getenv("LOCAL_JWT_SECRET", "")
        weak_values = {"", "local_demo_secret_change_me", "change_me", "secret", "default"}
        if local_secret.strip().lower() in weak_values or len(local_secret.strip()) < 32:
            raise ValueError("LOCAL_JWT_SECRET must be strong in production")
    elif os.getenv("LOCAL_JWT_SECRET", "local_demo_secret_change_me") == "local_demo_secret_change_me":
        warnings.warn(
            "LOCAL_JWT_SECRET uses the local demo default. Set a strong secret outside local development.",
            RuntimeWarning,
            stacklevel=2,
        )


_validate_security_config()
