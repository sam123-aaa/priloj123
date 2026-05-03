from datetime import datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from jose import JWTError, jwt

from auth import ALGORITHM, SECRET_KEY
from database import get_db
from rbac import require_any_role
from supabase_auth import get_auth_user

security = HTTPBearer()
_TOKEN_USER_CACHE = {}
_TOKEN_USER_CACHE_TTL = timedelta(minutes=15)


def cache_token_user(token: str, user: dict):
    _TOKEN_USER_CACHE[token] = {
        "expires_at": datetime.utcnow() + _TOKEN_USER_CACHE_TTL,
        "user": user,
    }


def _get_cached_token_user(token: str):
    cached = _TOKEN_USER_CACHE.get(token)
    if not cached:
        return None
    if cached["expires_at"] <= datetime.utcnow():
        _TOKEN_USER_CACHE.pop(token, None)
        return None
    return cached["user"]


def _load_user_by_auth_id(auth_user_id, email=None):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                p.legacy_user_id,
                r.code AS role
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            LEFT JOIN profiles p ON p.user_id = ur.user_id
            WHERE ur.user_id = %s
            ORDER BY CASE WHEN r.code = 'admin' THEN 0 ELSE 1 END, r.id
            LIMIT 1
            """,
            (auth_user_id,),
        )
        user = cur.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "user_id": user["legacy_user_id"],
        "auth_user_id": auth_user_id,
        "email": email,
        "role": user["role"],
        "role_code": user["role"],
    }


def _load_user_by_email(email):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                p.user_id AS auth_user_id,
                p.legacy_user_id,
                r.code AS role
            FROM profiles p
            JOIN user_roles ur ON ur.user_id = p.user_id
            JOIN roles r ON r.id = ur.role_id
            WHERE p.email = %s
            ORDER BY CASE WHEN r.code = 'admin' THEN 0 ELSE 1 END, r.id
            LIMIT 1
            """,
            (email,),
        )
        user = cur.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "user_id": user["legacy_user_id"],
        "auth_user_id": str(user["auth_user_id"]),
        "email": email,
        "role": user["role"],
        "role_code": user["role"],
    }


def _try_local_dev_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

    if payload.get("auth_provider") != "local_dev":
        return None
    if payload.get("token_type") not in {None, "access"}:
        raise HTTPException(status_code=401, detail="Refresh token cannot be used as access token")
    email = payload.get("email")
    if not email:
        return None
    return _load_user_by_email(email)


def get_user_from_token(token: str):
    local_user = _try_local_dev_token(token)
    if local_user:
        return local_user

    cached_user = _get_cached_token_user(token)
    if cached_user:
        return cached_user

    auth_user = get_auth_user(token)
    auth_user_id = auth_user.get("id")
    email = auth_user.get("email")
    if not auth_user_id:
        raise HTTPException(status_code=401, detail="Invalid Supabase token")

    user = _load_user_by_auth_id(auth_user_id, email=email)
    cache_token_user(token, user)
    return user


def get_current_user(credentials=Depends(security)):
    return get_user_from_token(credentials.credentials)


def require_role(*role_codes: str):
    def checker(user=Depends(get_current_user)):
        return require_any_role(user, set(role_codes))

    return checker
