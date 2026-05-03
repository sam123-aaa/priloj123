import os
from datetime import datetime, timedelta

from jose import jwt

SECRET_KEY = os.getenv("LOCAL_JWT_SECRET", "local_demo_secret_change_me")
ALGORITHM = "HS256"
LOCAL_ACCESS_TOKEN_TTL_MINUTES = int(os.getenv("LOCAL_ACCESS_TOKEN_TTL_MINUTES", "60"))
LOCAL_REFRESH_TOKEN_TTL_DAYS = int(os.getenv("LOCAL_REFRESH_TOKEN_TTL_DAYS", "7"))


def create_token(user):
    payload = {
        "user_id": user["id"],
        "exp": datetime.utcnow() + timedelta(hours=8),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_local_auth_token(user):
    payload = {
        "auth_provider": "local_dev",
        "token_type": "access",
        "email": user["email"],
        "user_id": user["user_id"],
        "role": user["role"],
        "exp": datetime.utcnow() + timedelta(minutes=LOCAL_ACCESS_TOKEN_TTL_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_local_refresh_token(user):
    payload = {
        "auth_provider": "local_dev",
        "token_type": "refresh",
        "email": user["email"],
        "user_id": user["user_id"],
        "role": user["role"],
        "exp": datetime.utcnow() + timedelta(days=LOCAL_REFRESH_TOKEN_TTL_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
