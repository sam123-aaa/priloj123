from typing import List, Optional

import json
import logging
import os
import time
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from psycopg2 import OperationalError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from jose import JWTError, jwt

from audit import log_transaction
from auth import ALGORITHM, SECRET_KEY, create_local_auth_token, create_local_refresh_token
from config import (
    ALLOWED_CORS_ORIGINS,
    CSRF_COOKIE_NAME,
    CSRF_COOKIE_SAMESITE,
    CSRF_COOKIE_SECURE,
    CSRF_HEADER_NAME,
    CSRF_TRUSTED_ORIGINS,
    SECURITY_RATE_LIMIT_PER_MINUTE,
)
from database import get_db
from dependencies import cache_token_user, get_user_from_token, normalize_bearer_token, require_role
from logging_config import setup_logging
from observability import check_rate_limit, hot_points_snapshot, metrics_snapshot, record_count, record_request
from orm import get_session
from schemas import (
    BffReportCommandData,
    DelayedReportData,
    FaultConfirmData,
    LoginData,
    MeasurementData,
    PlanData,
    QualityCheckData,
    RecommendationData,
    RefreshTokenData,
    ReportData,
    AccountStatusData,
    RoleChangeData,
    TaskResultData,
)
from supabase_auth import refresh_session, sign_in_with_password
from services.commands import (
    EntityNotFoundError,
    InvalidStatusTransitionError,
    MaintenanceTaskStatus,
    confirm_faults as confirm_faults_command,
    create_plan_with_tasks,
    create_quality_check,
    create_recommendation,
    enqueue_report,
    resolve_report_type,
    transition_task_status,
)
from services.queries import (
    get_desktop_monitoring,
    get_dispatcher_recommendations,
    get_faults_for_user,
    get_measurement_components,
    get_mobile_tasks,
    get_quality_tasks,
    get_recent_report_jobs,
    get_report_document,
    get_report_status,
    get_report_templates,
    get_tasks_for_mechanic,
    get_transactions,
    get_web_dashboard,
)
from services.cache import cached_read, invalidate_read_cache, read_cache_stats
from services.admin_security import (
    change_user_role,
    ensure_admin_security_schema,
    list_roles,
    list_users,
    set_account_status,
)
from services.security import generate_csrf_token, safe_download_filename, verify_csrf_request
from services.login_protection import login_key, login_protection_service
from task_status import get_task_status
import workers  # noqa: F401

setup_logging()
logger = logging.getLogger("maintenance.api")
app = FastAPI(docs_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _rate_limit_subject(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return "anonymous"
    token = normalize_bearer_token(authorization.split(" ", 1)[1])
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        try:
            payload = jwt.get_unverified_claims(token)
        except JWTError:
            return "invalid-token"
    return str(payload.get("sub") or payload.get("email") or "bearer-token")


def _content_security_policy(path: str) -> str:
    if path == "/docs":
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://fastapi.tiangolo.com; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'"
        )
    return (
        "default-src 'none'; "
        "connect-src 'self'; "
        "img-src 'self' data:; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )


@app.middleware("http")
async def security_and_metrics_middleware(request: Request, call_next):
    try:
        verify_csrf_request(request, CSRF_TRUSTED_ORIGINS, CSRF_COOKIE_NAME, CSRF_HEADER_NAME)
    except HTTPException as exc:
        record_request(request.method, request.url.path, exc.status_code, 0)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    allowed, remaining = check_rate_limit(request, SECURITY_RATE_LIMIT_PER_MINUTE, _rate_limit_subject(request))
    if not allowed:
        record_request(request.method, request.url.path, 429, 0)
        return JSONResponse(
            {"detail": "Too many requests"},
            status_code=429,
            headers={"Retry-After": "60"},
        )

    started_at = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = (time.perf_counter() - started_at) * 1000
        record_request(request.method, request.url.path, status_code, duration_ms)
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%.2f rate_remaining=%s",
            request.method,
            request.url.path,
            status_code,
            duration_ms,
            remaining,
        )
        if "response" in locals():
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
            response.headers["Content-Security-Policy"] = _content_security_policy(request.url.path)
            if request.url.path in {"/login", "/auth/refresh"}:
                response.headers["Cache-Control"] = "no-store"
                response.headers["Pragma"] = "no-cache"
            response.headers["X-RateLimit-Limit"] = str(SECURITY_RATE_LIMIT_PER_MINUTE)
            response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
            response.headers["X-Request-Duration-Ms"] = f"{duration_ms:.2f}"


def _cached_query(name, user, loader):
    key = (name, user.get("role_code"), user.get("user_id"))
    payload = cached_read(key, loader)
    record_request("CACHE", name, 200, 0, record_count(jsonable_encoder(payload)))
    return payload


@app.on_event("startup")
async def ensure_report_document_storage():
    try:
        with get_db() as conn:
            ensure_admin_security_schema(conn)
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS report_documents (
                    job_id UUID PRIMARY KEY REFERENCES report_read_model(job_id) ON DELETE CASCADE,
                    owner_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    file_name TEXT NOT NULL DEFAULT 'report.docx',
                    content_type TEXT NOT NULL DEFAULT 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    html_content TEXT NOT NULL,
                    file_content BYTEA NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute("ALTER TABLE report_documents ADD COLUMN IF NOT EXISTS file_name TEXT NOT NULL DEFAULT 'report.docx'")
            cur.execute(
                """
                ALTER TABLE report_documents
                ALTER COLUMN content_type
                SET DEFAULT 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                """
            )
            cur.execute("ALTER TABLE report_documents ADD COLUMN IF NOT EXISTS file_content BYTEA NULL")
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_report_documents_owner_id
                ON report_documents(owner_id)
                """
            )
    except OperationalError:
        pass


@app.exception_handler(OperationalError)
async def postgres_operational_error_handler(_request, exc):
    return JSONResponse(
        {"detail": f"Supabase Postgres unavailable: {str(exc).splitlines()[0]}"},
        status_code=503,
    )


def _local_auth_passwords():
    raw = os.getenv("LOCAL_AUTH_PASSWORDS", "{}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _normalize_local_auth_email(email: str):
    aliases = {
        "temp-mectrolog@example.com": "temp-metrologist@example.com",
        "temp-metrolog@example.com": "temp-metrologist@example.com",
        "metrolog@example.com": "temp-metrologist@example.com",
    }
    return aliases.get((email or "").strip().lower(), (email or "").strip().lower())


def _login_with_local_fallback(data: LoginData, reason: str):
    if os.getenv("ALLOW_LOCAL_AUTH_FALLBACK", "0") != "1":
        raise HTTPException(status_code=503, detail=reason)

    email = _normalize_local_auth_email(data.email)
    password = _local_auth_passwords().get(email)
    if not password or password != data.password:
        raise HTTPException(status_code=401, detail="Invalid login credentials")

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                p.user_id AS auth_user_id,
                p.legacy_user_id,
                COALESCE(p.is_active, TRUE) AS is_active,
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
        if not user["is_active"]:
            raise HTTPException(status_code=403, detail="Account is disabled")

        token_payload = {
            "email": email,
            "user_id": user["legacy_user_id"],
            "role": user["role"],
        }
        log_transaction(
            conn,
            action="login_success_local_fallback",
            endpoint="/login",
            user_id=user["legacy_user_id"],
            role_code=user["role"],
            details={"email": email, "input_email": data.email, "reason": reason},
        )
        return {
            "access_token": create_local_auth_token(token_payload),
            "refresh_token": create_local_refresh_token(token_payload),
            "token_type": "bearer",
            "role": user["role"],
            "auth_mode": "local_fallback",
        }


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    swagger_ui = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "displayRequestDuration": True,
            "docExpansion": "none",
        },
    )
    html = swagger_ui.body.decode("utf-8")
    html = html.replace(
        "</head>",
        """
<style>
  .curl-command,
  .curl-command + div,
  .responses-wrapper .responses-table:not(.live-responses-table),
  .responses-wrapper .model-example,
  .responses-wrapper .models-wrapper,
  .responses-wrapper .opblock-section-header + div > p,
  .responses-inner > h4:nth-of-type(2),
  .response-col_status,
  .response-col_links {
    display: none !important;
  }

  .live-responses-table .response-col_status,
  .live-responses-table .response-col_links {
    display: table-cell !important;
  }
</style>
</head>
""",
    )
    return HTMLResponse(html)


@app.get("/csrf-token", tags=["Security"])
async def csrf_token():
    token = generate_csrf_token()
    response = JSONResponse(
        {
            "csrf_token": token,
            "header_name": CSRF_HEADER_NAME,
            "cookie_name": CSRF_COOKIE_NAME,
        }
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=CSRF_COOKIE_SECURE,
        samesite=CSRF_COOKIE_SAMESITE,
        max_age=3600,
    )
    return response


@app.get("/observability/metrics", tags=["Observability"])
async def observability_metrics(user=Depends(require_role("admin"))):
    return {
        "requests": metrics_snapshot(),
        "read_cache": read_cache_stats(),
        "user": {"user_id": user["user_id"], "role_code": user["role_code"]},
    }


@app.get("/observability/hot-points", tags=["Observability"])
async def observability_hot_points(limit: int = Query(10, ge=1, le=50), user=Depends(require_role("admin"))):
    return {
        "hot_points": hot_points_snapshot(limit),
        "tracked_areas": ["GET list queries", "command endpoints", "worker report generation"],
    }


@app.get("/api/users", tags=["Admin Security"])
async def api_users(user=Depends(require_role("admin"))):
    with get_db() as conn:
        rows = list_users(conn)
        log_transaction(
            conn,
            action="admin_users_viewed",
            endpoint="/api/users",
            user_id=user["user_id"],
            role_code=user["role_code"],
            details={"count": len(rows)},
        )
        return rows


@app.get("/api/roles", tags=["Admin Security"])
async def api_roles(user=Depends(require_role("admin"))):
    with get_db() as conn:
        return list_roles(conn)


@app.post("/api/users/{user_id}/account-status", tags=["Admin Security"])
async def api_set_account_status(
    data: AccountStatusData,
    user_id: int = Path(..., gt=0),
    user=Depends(require_role("admin")),
):
    with get_db() as conn:
        return set_account_status(conn, user_id, data.is_active, data.admin_password, data.reason, user)


@app.post("/api/users/{user_id}/role", tags=["Admin Security"])
async def api_change_user_role(
    data: RoleChangeData,
    user_id: int = Path(..., gt=0),
    user=Depends(require_role("admin")),
):
    with get_db() as conn:
        return change_user_role(conn, user_id, data.role_code, data.admin_password, data.reason, user)


@app.post("/login", tags=["Auth"])#№А
async def login(data: LoginData, request: Request):
    protection_key = login_key(data.email, request.client.host if request.client else "unknown")
    blocked_seconds = login_protection_service.check_blocked_seconds(protection_key)
    if blocked_seconds > 0:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Try again in {blocked_seconds} seconds.",
        )

    try:
        try:
            auth_result = sign_in_with_password(data.email, data.password)
        except HTTPException as exc:
            if exc.status_code in {400, 401, 503}:
                response = _login_with_local_fallback(data, str(exc.detail))
                login_protection_service.register_success(protection_key)
                return response
            raise
        auth_user = auth_result.get("user") or {}
        auth_user_id = auth_user.get("id")
        if not auth_user_id:
            raise HTTPException(status_code=401, detail="Supabase Auth login failed")

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    r.code AS role
                FROM user_roles ur
                JOIN roles r ON r.id = ur.role_id
                WHERE ur.user_id = %s
                ORDER BY CASE WHEN r.code = 'admin' THEN 0 ELSE 1 END, r.id
                LIMIT 1
                """,
                (auth_user_id,),
            )
            role_row = cur.fetchone()

            if not role_row:
                log_transaction(
                    conn,
                    action="login_failed",
                    endpoint="/login",
                    details={"email": data.email, "reason": "role_not_found", "auth_user_id": auth_user_id},
                )
                raise HTTPException(403, "Роль пользователя не назначена")

            cur.execute(
                """
                SELECT legacy_user_id, COALESCE(is_active, TRUE) AS is_active
                FROM profiles
                WHERE user_id = %s
                """,
                (auth_user_id,),
            )
            profile = cur.fetchone()
            if profile and not profile["is_active"]:
                raise HTTPException(status_code=403, detail="Account is disabled")
            legacy_user_id = profile["legacy_user_id"] if profile else None

            log_transaction(
                conn,
                action="login_success",
                endpoint="/login",
                user_id=legacy_user_id,
                role_code=role_row["role"],
                details={"email": data.email, "role_code": role_row["role"], "auth_user_id": auth_user_id},
            )
            cache_token_user(
                auth_result["access_token"],
                {
                    "user_id": legacy_user_id,
                    "auth_user_id": auth_user_id,
                    "email": data.email,
                    "role": role_row["role"],
                    "role_code": role_row["role"],
                },
            )

            login_protection_service.register_success(protection_key)
            return {
                "access_token": auth_result["access_token"],
                "refresh_token": auth_result.get("refresh_token"),
                "token_type": "bearer",
                "role": role_row["role"],
            }
    except HTTPException as exc:
        if exc.status_code in {400, 401, 403}:
            login_protection_service.register_failure(protection_key)
        raise


@app.post("/auth/refresh", tags=["Auth"])
async def refresh_auth_token(data: RefreshTokenData):
    try:
        payload = jwt.decode(data.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        payload = None

    if payload and payload.get("auth_provider") == "local_dev":
        if payload.get("token_type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        token_payload = {
            "email": payload["email"],
            "user_id": payload["user_id"],
            "role": payload["role"],
        }
        return {
            "access_token": create_local_auth_token(token_payload),
            "refresh_token": create_local_refresh_token(token_payload),
            "token_type": "bearer",
            "role": payload["role"],
            "auth_mode": "local_fallback",
        }

    auth_result = refresh_session(data.refresh_token)
    auth_user = auth_result.get("user") or {}
    auth_user_id = auth_user.get("id")
    if auth_user_id:
        cache_token_user(
            auth_result["access_token"],
            {
                "auth_user_id": auth_user_id,
                "email": auth_user.get("email"),
                **get_user_from_token(auth_result["access_token"]),
            },
        )
    return {
        "access_token": auth_result["access_token"],
        "refresh_token": auth_result.get("refresh_token", data.refresh_token),
        "token_type": "bearer",
    }


def _collect_measurements_command(conn, data: List[MeasurementData], user, endpoint: str):
    cur = conn.cursor()
    created_faults = 0
    measurement_ids = []

    for measurement in data:
        cur.execute(
            """
            INSERT INTO measurements
            (component_id, parameter_name, value, unit, measured_at, recorded_by, owner_id)
            VALUES (%s, %s, %s, %s, NOW(), %s, %s)
            RETURNING id
            """,
            (
                measurement.component_id,
                measurement.parameter_name,
                measurement.value,
                measurement.unit,
                user["user_id"],
                user["user_id"],
            ),
        )
        measurement_id = cur.fetchone()["id"]
        measurement_ids.append(measurement_id)

        cur.execute(
            """
            SELECT min_value, max_value
            FROM operation_norms
            WHERE component_id = %s AND parameter_name = %s
            """,
            (measurement.component_id, measurement.parameter_name),
        )
        norm = cur.fetchone()

        if norm and (measurement.value < norm["min_value"] or measurement.value > norm["max_value"]):
            cur.execute(
                """
                INSERT INTO faults
                (component_id, measurement_id, description, severity, detected_at, owner_id)
                VALUES (%s, %s, %s, %s, NOW(), %s)
                """,
                (
                    measurement.component_id,
                    measurement_id,
                    "Отклонение",
                    "high",
                    user["user_id"],
                ),
            )
            created_faults += 1

    log_transaction(
        conn,
        action="metrolog_data_collected",
        endpoint=endpoint,
        user_id=user["user_id"],
        role_code=user["role_code"],
        details={"measurements_count": len(data), "created_faults": created_faults},
    )
    invalidate_read_cache()
    return {"status": "ok", "measurement_ids": measurement_ids, "created_faults": created_faults}


@app.post("/metrolog/collect-data", tags=["Metrolog"])
async def collect_data(data: List[MeasurementData], user=Depends(require_role("metrologist", "admin"))):
    with get_db() as conn:
        return _collect_measurements_command(conn, data, user, "/metrolog/collect-data")


@app.get("/expert/faults", tags=["Expert"])
async def expert_faults(user=Depends(require_role("tech_expert", "admin"))):
    with get_db() as conn:
        rows = _cached_query("expert_faults", user, lambda: get_faults_for_user(conn, user))
        log_transaction(
            conn,
            action="expert_faults_viewed",
            endpoint="/expert/faults",
            user_id=user["user_id"],
            role_code=user["role_code"],
            details={"faults_count": len(rows)},
        )
        return rows


@app.post("/expert/confirm", tags=["Expert"])
async def confirm_faults(data: FaultConfirmData, user=Depends(require_role("tech_expert", "admin"))):
    with get_db() as conn:
        result = confirm_faults_command(conn, data.fault_ids, data.action, user)
        log_transaction(
            conn,
            action="expert_faults_confirmed",
            endpoint="/expert/confirm",
            user_id=user["user_id"],
            role_code=user["role_code"],
            details={"fault_ids": data.fault_ids, "status": result["fault_status"]},
        )
        return result


@app.post("/expert/recommendation", tags=["Expert"])
async def create_rec(data: RecommendationData, user=Depends(require_role("tech_expert", "admin"))):
    with get_db() as conn:
        result = create_recommendation(
            conn,
            fault_id=data.fault_id,
            recommendation_text=data.recommendation_text,
            priority=data.priority,
            user=user,
        )
        log_transaction(
            conn,
            action="expert_recommendation_created",
            endpoint="/expert/recommendation",
            user_id=user["user_id"],
            role_code=user["role_code"],
            details={"fault_id": data.fault_id, "priority": data.priority},
        )
        return result


@app.post("/specialist/create-plan", tags=["Specialist"])
async def create_plan(data: PlanData, user=Depends(require_role("dispatcher_specialist", "admin"))):
    with get_session() as session:
        try:
            result = create_plan_with_tasks(session, data.recommendation_ids, data.planned_date, user)
        except EntityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return result


@app.get("/specialist/recommendations", tags=["Specialist"])
async def dispatcher_recommendations(user=Depends(require_role("dispatcher_specialist", "admin"))):
    with get_session() as session:
        return _cached_query("specialist_recommendations", user, lambda: get_dispatcher_recommendations(session, user))


@app.get("/mechanic/tasks", tags=["Mechanic"])
async def mechanic_tasks(user=Depends(require_role("mechanic", "admin"))):
    with get_db() as conn:
        rows = _cached_query("mechanic_tasks", user, lambda: get_tasks_for_mechanic(conn, user))
        log_transaction(
            conn,
            action="mechanic_tasks_viewed",
            endpoint="/mechanic/tasks",
            user_id=user["user_id"],
            role_code=user["role_code"],
            details={"tasks_count": len(rows)},
        )
        return rows


@app.post("/mechanic/start/{task_id}", tags=["Mechanic"])
async def start_task(task_id: int = Path(..., gt=0), user=Depends(require_role("mechanic", "admin"))):
    with get_session() as session:
        try:
            return transition_task_status(session, task_id, MaintenanceTaskStatus.ACTIVE.value, user)
        except EntityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidStatusTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/mechanic/finish/{task_id}", tags=["Mechanic"])
async def finish_task(data: TaskResultData, task_id: int = Path(..., gt=0), user=Depends(require_role("mechanic", "admin"))):
    with get_session() as session:
        try:
            return transition_task_status(
                session,
                task_id,
                MaintenanceTaskStatus.COMPLETED.value,
                user,
                result=data.result,
            )
        except EntityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidStatusTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/mechanic/cancel/{task_id}", tags=["Mechanic"])
async def cancel_task(task_id: int = Path(..., gt=0), user=Depends(require_role("mechanic", "admin"))):
    with get_session() as session:
        try:
            return transition_task_status(session, task_id, MaintenanceTaskStatus.CANCELLED.value, user)
        except EntityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidStatusTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/quality/check/{task_id}", tags=["Quality"])
async def check(data: QualityCheckData, task_id: int = Path(..., gt=0), user=Depends(require_role("quality_engineer", "admin"))):
    with get_db() as conn:
        result = create_quality_check(conn, task_id, data.status, data.notes, user)
        log_transaction(
            conn,
            action="quality_check_created",
            endpoint=f"/quality/check/{task_id}",
            user_id=user["user_id"],
            role_code=user["role_code"],
            details={"task_id": task_id, "status": data.status},
        )
        return result


@app.get("/quality/tasks", tags=["Quality"])
async def quality_tasks(user=Depends(require_role("quality_engineer", "admin"))):
    with get_session() as session:
        return _cached_query("quality_tasks", user, lambda: get_quality_tasks(session, user))


@app.post("/reports/generate", tags=["Reports"])
async def generate_report(data: ReportData, user=Depends(require_role("manager", "admin"))):
    with get_db() as conn:
        try:
            report_type = resolve_report_type(conn, report_type=data.report_type, template_id=data.template_id)
            return enqueue_report(conn, report_type, user, delay_seconds=0)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/reports/generate-delayed", tags=["Reports"])
async def generate_report_delayed(data: DelayedReportData, user=Depends(require_role("manager", "admin"))):
    with get_db() as conn:
        try:
            report_type = resolve_report_type(conn, report_type=data.report_type, template_id=data.template_id)
            return enqueue_report(conn, report_type, user, delay_seconds=data.delay_seconds)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/reports/templates", tags=["Reports"])
async def report_templates(user=Depends(require_role("manager", "admin"))):
    with get_db() as conn:
        return _cached_query("report_templates", user, lambda: get_report_templates(conn, user))


@app.get("/reports/status/{task_id}", tags=["Reports"])
async def report_status(task_id: UUID, user=Depends(require_role("manager", "admin"))):
    task_id_value = str(task_id)
    redis_status = get_task_status(task_id_value)
    with get_db() as conn:
        read_model = get_report_status(conn, task_id_value, user)
        if not redis_status and not read_model:
            raise HTTPException(status_code=404, detail="Задача не найдена")
        return {"queue": redis_status, "read_model": read_model}


@app.get("/reports/jobs", tags=["Reports"])
async def report_jobs(
    limit: int = Query(20, ge=1, le=100),
    user=Depends(require_role("manager", "admin")),
):
    with get_db() as conn:
        key = ("report_jobs", user.get("role_code"), user.get("user_id"), limit)
        return _cached_query(key, user, lambda: get_recent_report_jobs(conn, user, limit=limit))


@app.get("/reports/document/{task_id}", tags=["Reports"])
async def report_document(
    task_id: UUID,
    token: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    access_token = token
    if not access_token and authorization and authorization.lower().startswith("bearer "):
        access_token = authorization.split(" ", 1)[1]
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    access_token = normalize_bearer_token(access_token)

    user = get_user_from_token(access_token)
    if user["role_code"] not in {"manager", "admin"}:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    task_id_value = str(task_id)
    with get_db() as conn:
        document = get_report_document(conn, task_id_value, user)
        if not document:
            raise HTTPException(status_code=404, detail="Документ отчёта ещё не сформирован")
        file_content = document.get("file_content")
        if file_content is None:
            raise HTTPException(status_code=404, detail="DOCX-файл ещё не сформирован")
        file_name = safe_download_filename(document.get("file_name"), "report.docx")
        return Response(
            content=bytes(file_content),
            media_type=document["content_type"],
            headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
        )


@app.get("/transactions", tags=["Transactions"])
async def transactions(
    limit: int = Query(50, ge=1, le=500),
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    user=Depends(require_role("admin")),
):
    with get_db() as conn:
        rows = get_transactions(conn, user, limit, user_id=user_id, action=action)
        log_transaction(
            conn,
            action="transactions_viewed",
            endpoint="/transactions",
            user_id=user["user_id"],
            role_code=user["role_code"],
            details={"limit": limit, "filter_user_id": user_id, "filter_action": action},
        )
        return rows


@app.get("/bff/web/dashboard", tags=["BFF"])
async def bff_web_dashboard(user=Depends(require_role("admin", "dispatcher_specialist", "manager"))):
    with get_db() as conn:
        return _cached_query("bff_web_dashboard", user, lambda: get_web_dashboard(conn, user))


@app.get("/bff/web/manager-home", tags=["BFF Web"])
async def bff_web_manager_home(user=Depends(require_role("manager", "admin"))):
    with get_db() as conn:
        return _cached_query("bff_web_manager_home", user, lambda: {
            "dashboard": get_web_dashboard(conn, user),
            "templates": get_report_templates(conn, user),
            "recent_reports": get_recent_report_jobs(conn, user),
        })


@app.get("/bff/web/reports", tags=["BFF Web"])
async def bff_web_reports(
    limit: int = Query(20, ge=1, le=100),
    user=Depends(require_role("manager", "admin")),
):
    with get_db() as conn:
        key = ("bff_web_reports", user.get("role_code"), user.get("user_id"), limit)
        return _cached_query(key, user, lambda: {
            "reports": get_recent_report_jobs(conn, user, limit=limit),
        })


@app.post("/bff/web/reports/generate", tags=["BFF Web"])
async def bff_web_generate_report(data: BffReportCommandData, user=Depends(require_role("manager", "admin"))):
    with get_db() as conn:
        try:
            report_type = resolve_report_type(conn, report_type=data.report_type, template_id=data.template_id)
            command_result = enqueue_report(conn, report_type, user, delay_seconds=data.delay_seconds)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return {
            "command": command_result,
            "query": {
                "status": {
                    "queue": get_task_status(command_result["task_id"]),
                    "read_model": get_report_status(conn, command_result["task_id"], user),
                },
                "recent_reports": get_recent_report_jobs(conn, user),
                "dashboard": get_web_dashboard(conn, user),
                "templates": get_report_templates(conn, user),
            },
        }


@app.get("/bff/mobile/tasks", tags=["BFF"])
async def bff_mobile_tasks(user=Depends(require_role("mechanic", "admin"))):
    with get_db() as conn:
        return _cached_query("bff_mobile_tasks", user, lambda: get_mobile_tasks(conn, user))


@app.post("/bff/mobile/metrolog/measurements", tags=["BFF Mobile"])
async def bff_mobile_collect_measurements(
    data: List[MeasurementData],
    user=Depends(require_role("metrologist", "admin")),
):
    with get_db() as conn:
        command_result = _collect_measurements_command(conn, data, user, "/bff/mobile/metrolog/measurements")
        return {
            "command": command_result,
            "query": {
                "components": get_measurement_components(conn, user),
            },
        }


def _mobile_task_response(command_result, user):
    with get_db() as conn:
        tasks = get_mobile_tasks(conn, user)
    with get_session() as session:
        quality_tasks = get_quality_tasks(session, user) if user["role_code"] == "admin" else []
    return {
        "command": command_result,
        "query": {
            "tasks": tasks,
            "quality_tasks": quality_tasks,
        },
    }


@app.post("/bff/mobile/mechanic/tasks/{task_id}/start", tags=["BFF Mobile"])
async def bff_mobile_start_task(task_id: int = Path(..., gt=0), user=Depends(require_role("mechanic", "admin"))):
    with get_session() as session:
        try:
            command_result = transition_task_status(session, task_id, MaintenanceTaskStatus.ACTIVE.value, user)
        except EntityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidStatusTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _mobile_task_response(command_result, user)


@app.post("/bff/mobile/mechanic/tasks/{task_id}/finish", tags=["BFF Mobile"])
async def bff_mobile_finish_task(
    data: TaskResultData,
    task_id: int = Path(..., gt=0),
    user=Depends(require_role("mechanic", "admin")),
):
    with get_session() as session:
        try:
            command_result = transition_task_status(
                session,
                task_id,
                MaintenanceTaskStatus.COMPLETED.value,
                user,
                result=data.result,
            )
        except EntityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidStatusTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _mobile_task_response(command_result, user)


@app.post("/bff/mobile/mechanic/tasks/{task_id}/cancel", tags=["BFF Mobile"])
async def bff_mobile_cancel_task(task_id: int = Path(..., gt=0), user=Depends(require_role("mechanic", "admin"))):
    with get_session() as session:
        try:
            command_result = transition_task_status(session, task_id, MaintenanceTaskStatus.CANCELLED.value, user)
        except EntityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidStatusTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _mobile_task_response(command_result, user)


@app.post("/bff/mobile/quality/tasks/{task_id}/check", tags=["BFF Mobile"])
async def bff_mobile_quality_check(
    data: QualityCheckData,
    task_id: int = Path(..., gt=0),
    user=Depends(require_role("quality_engineer", "admin")),
):
    with get_db() as conn:
        command_result = create_quality_check(conn, task_id, data.status, data.notes, user)
        log_transaction(
            conn,
            action="quality_check_created",
            endpoint=f"/bff/mobile/quality/tasks/{task_id}/check",
            user_id=user["user_id"],
            role_code=user["role_code"],
            details={"task_id": task_id, "status": data.status},
        )
    with get_session() as session:
        return {
            "command": command_result,
            "query": {
                "quality_tasks": get_quality_tasks(session, user),
            },
        }


@app.get("/bff/mobile/quality/tasks", tags=["BFF Mobile"])
async def bff_mobile_quality_tasks(user=Depends(require_role("quality_engineer", "admin"))):
    with get_session() as session:
        return _cached_query("bff_mobile_quality_tasks", user, lambda: get_quality_tasks(session, user))


@app.get("/bff/mobile/components", tags=["BFF"])
async def bff_mobile_components(user=Depends(require_role("metrologist", "admin"))):
    with get_db() as conn:
        return _cached_query("bff_mobile_components", user, lambda: get_measurement_components(conn, user))


@app.get("/bff/desktop/monitoring", tags=["BFF"])
async def bff_desktop_monitoring(user=Depends(require_role("admin", "tech_expert", "dispatcher_specialist"))):
    with get_db() as conn:
        return _cached_query("bff_desktop_monitoring", user, lambda: get_desktop_monitoring(conn, user))


@app.post("/bff/desktop/expert/faults/confirm", tags=["BFF Desktop"])
async def bff_desktop_confirm_faults(data: FaultConfirmData, user=Depends(require_role("tech_expert", "admin"))):
    with get_db() as conn:
        command_result = confirm_faults_command(conn, data.fault_ids, data.action, user)
        log_transaction(
            conn,
            action="expert_faults_confirmed",
            endpoint="/bff/desktop/expert/faults/confirm",
            user_id=user["user_id"],
            role_code=user["role_code"],
            details={"fault_ids": data.fault_ids, "status": command_result["fault_status"]},
        )
        return {
            "command": command_result,
            "query": {
                "faults": get_faults_for_user(conn, user),
                "monitoring": get_desktop_monitoring(conn, user),
            },
        }


@app.post("/bff/desktop/expert/recommendations", tags=["BFF Desktop"])
async def bff_desktop_create_recommendation(
    data: RecommendationData,
    user=Depends(require_role("tech_expert", "admin")),
):
    with get_db() as conn:
        command_result = create_recommendation(
            conn,
            fault_id=data.fault_id,
            recommendation_text=data.recommendation_text,
            priority=data.priority,
            user=user,
        )
        log_transaction(
            conn,
            action="expert_recommendation_created",
            endpoint="/bff/desktop/expert/recommendations",
            user_id=user["user_id"],
            role_code=user["role_code"],
            details={"fault_id": data.fault_id, "priority": data.priority},
        )
        return {
            "command": command_result,
            "query": {
                "faults": get_faults_for_user(conn, user),
                "monitoring": get_desktop_monitoring(conn, user),
            },
        }


@app.post("/bff/desktop/dispatcher/plans", tags=["BFF Desktop"])
async def bff_desktop_create_plan(data: PlanData, user=Depends(require_role("dispatcher_specialist", "admin"))):
    with get_session() as session:
        try:
            command_result = create_plan_with_tasks(session, data.recommendation_ids, data.planned_date, user)
        except EntityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    with get_db() as conn:
        with get_session() as session:
            recommendations = get_dispatcher_recommendations(session, user)
        return {
            "command": command_result,
            "query": {
                "recommendations": recommendations,
                "monitoring": get_desktop_monitoring(conn, user),
            },
        }
