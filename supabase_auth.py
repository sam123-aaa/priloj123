import json
import os

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def _session():
    retry = Retry(
        total=1,
        connect=1,
        read=1,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST", "PATCH", "PUT", "DELETE"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.trust_env = False
    return session


def _json_request(url, method="GET", payload=None, token=None, apikey=None):
    headers = {
        "Content-Type": "application/json",
        "apikey": apikey or SUPABASE_ANON_KEY,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = _session().request(
            method=method,
            url=url,
            headers=headers,
            json=payload,
            timeout=(3, 8),
            verify=False,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail=f"Supabase Auth unavailable: {exc}") from exc

    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text or response.reason
        raise HTTPException(status_code=response.status_code, detail=detail)

    try:
        return response.json() if response.text else {}
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Supabase Auth returned invalid JSON") from exc


def sign_in_with_password(email: str, password: str):
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(status_code=500, detail="Supabase Auth is not configured")
    return _json_request(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        method="POST",
        payload={"email": email, "password": password},
        apikey=SUPABASE_ANON_KEY,
    )


def refresh_session(refresh_token: str):
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(status_code=500, detail="Supabase Auth is not configured")
    return _json_request(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
        method="POST",
        payload={"refresh_token": refresh_token},
        apikey=SUPABASE_ANON_KEY,
    )


def get_auth_user(access_token: str):
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(status_code=500, detail="Supabase Auth is not configured")
    return _json_request(
        f"{SUPABASE_URL}/auth/v1/user",
        method="GET",
        token=access_token,
        apikey=SUPABASE_ANON_KEY,
    )


def admin_request(path: str, method="GET", payload=None):
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Supabase service role key is not configured")
    return _json_request(
        f"{SUPABASE_URL}{path}",
        method=method,
        payload=payload,
        token=SUPABASE_SERVICE_ROLE_KEY,
        apikey=SUPABASE_SERVICE_ROLE_KEY,
    )
