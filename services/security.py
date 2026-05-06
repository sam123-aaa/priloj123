import posixpath
import secrets
from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import urlparse

from fastapi import HTTPException, Request


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
BLOCKED_FILE_SCHEMES = {"http", "https", "file", "ftp"}


def generate_csrf_token():
    return secrets.token_urlsafe(32)


def _origin_from_referer(value: str):
    parsed = urlparse(value or "")
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def verify_csrf_request(request: Request, trusted_origins, cookie_name: str, header_name: str):
    if request.method.upper() not in UNSAFE_METHODS:
        return

    origin = request.headers.get("origin")
    referer_origin = _origin_from_referer(request.headers.get("referer"))
    request_origin = origin or referer_origin
    api_origin = f"{request.url.scheme}://{request.url.netloc}"
    if request_origin and request_origin != api_origin and request_origin not in trusted_origins:
        raise HTTPException(status_code=403, detail="CSRF origin check failed")

    if request.headers.get("authorization"):
        return

    csrf_cookie = request.cookies.get(cookie_name)
    if not csrf_cookie:
        return

    csrf_header = request.headers.get(header_name)
    if not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=403, detail="CSRF token mismatch")


def safe_download_filename(filename: str, default: str = "download.bin"):
    value = (filename or default).strip() or default
    parsed = urlparse(value)
    if parsed.scheme.lower() in BLOCKED_FILE_SCHEMES:
        raise HTTPException(status_code=400, detail="Remote file references are not allowed")
    if "\x00" in value or ".." in PurePosixPath(value).parts or ".." in PureWindowsPath(value).parts:
        raise HTTPException(status_code=400, detail="Unsafe file path")
    if PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute():
        raise HTTPException(status_code=400, detail="Absolute file paths are not allowed")

    filename_only = posixpath.basename(value.replace("\\", "/"))
    if not filename_only or filename_only in {".", ".."}:
        raise HTTPException(status_code=400, detail="Unsafe file name")
    return "".join(char if char.isalnum() or char in "._- " else "_" for char in filename_only)
