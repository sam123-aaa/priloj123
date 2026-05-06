import hmac
import json
import os

from fastapi import HTTPException

from audit import log_transaction
from supabase_auth import sign_in_with_password


PROTECTED_SECURITY_ACTIONS = {
    "admin_account_disabled": "security_last_admin_blocked",
    "admin_role_removed": "security_last_admin_blocked",
}


def ensure_admin_security_schema(conn):
    cur = conn.cursor()
    cur.execute("SELECT to_regclass('public.profiles') AS profiles_table")
    if not cur.fetchone()["profiles_table"]:
        return
    cur.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE")
    cur.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS account_status_reason TEXT NULL")
    cur.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS account_status_updated_at TIMESTAMP NULL")
    cur.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS role_updated_at TIMESTAMP NULL")


def _local_auth_passwords():
    try:
        return json.loads(os.getenv("LOCAL_AUTH_PASSWORDS", "{}"))
    except json.JSONDecodeError:
        return {}


def _normalize_email(email):
    return (email or "").strip().lower()


def _raise_security(conn, action, endpoint, user, details, status_code=403):
    log_transaction(
        conn,
        action=action,
        endpoint=endpoint,
        user_id=user.get("user_id"),
        role_code=user.get("role_code"),
        details=details,
    )
    conn.commit()
    raise HTTPException(status_code=status_code, detail="Forbidden")


def verify_admin_password(conn, admin_user, admin_password: str, endpoint: str):
    email = _normalize_email(admin_user.get("email"))
    if not email:
        _raise_security(conn, "security_admin_password_failed", endpoint, admin_user, {"reason": "missing_email"})

    local_password = _local_auth_passwords().get(email)
    if local_password and hmac.compare_digest(local_password, admin_password):
        return

    try:
        sign_in_with_password(email, admin_password)
        return
    except HTTPException:
        _raise_security(conn, "security_admin_password_failed", endpoint, admin_user, {"email": email})


def list_roles(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, code, name
        FROM roles
        ORDER BY CASE WHEN code = 'admin' THEN 0 ELSE 1 END, code
        """
    )
    return cur.fetchall()


def list_users(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            p.legacy_user_id AS id,
            p.user_id AS auth_user_id,
            p.email,
            p.full_name,
            COALESCE(p.is_active, TRUE) AS is_active,
            r.code AS role_code,
            r.name AS role_name,
            p.created_at
        FROM profiles p
        LEFT JOIN user_roles ur ON ur.user_id = p.user_id
        LEFT JOIN roles r ON r.id = ur.role_id
        ORDER BY CASE WHEN r.code = 'admin' THEN 0 ELSE 1 END, p.legacy_user_id
        """
    )
    return cur.fetchall()


def _get_user_by_legacy_id(conn, legacy_user_id: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            p.legacy_user_id,
            p.user_id AS auth_user_id,
            p.email,
            p.full_name,
            COALESCE(p.is_active, TRUE) AS is_active,
            r.code AS role_code
        FROM profiles p
        LEFT JOIN user_roles ur ON ur.user_id = p.user_id
        LEFT JOIN roles r ON r.id = ur.role_id
        WHERE p.legacy_user_id = %s
        LIMIT 1
        """,
        (legacy_user_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return row


def _active_admin_count(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(DISTINCT p.user_id) AS count
        FROM profiles p
        JOIN user_roles ur ON ur.user_id = p.user_id
        JOIN roles r ON r.id = ur.role_id
        WHERE r.code = 'admin'
          AND COALESCE(p.is_active, TRUE) = TRUE
        """
    )
    return cur.fetchone()["count"]


def _ensure_not_last_active_admin(conn, target_user, actor, endpoint, action):
    if target_user["role_code"] == "admin" and _active_admin_count(conn) <= 1:
        log_transaction(
            conn,
            action=PROTECTED_SECURITY_ACTIONS.get(action, "security_last_admin_blocked"),
            endpoint=endpoint,
            user_id=actor.get("user_id"),
            role_code=actor.get("role_code"),
            details={
                "target_user_id": target_user["legacy_user_id"],
                "target_email": target_user["email"],
                "blocked_action": action,
            },
        )
        conn.commit()
        raise HTTPException(status_code=409, detail="Last active admin cannot be changed")


def set_account_status(conn, target_user_id: int, is_active: bool, admin_password: str, reason: str, actor):
    endpoint = f"/api/users/{target_user_id}/account-status"
    verify_admin_password(conn, actor, admin_password, endpoint)
    target_user = _get_user_by_legacy_id(conn, target_user_id)

    if not is_active:
        _ensure_not_last_active_admin(conn, target_user, actor, endpoint, "admin_account_disabled")

    cur = conn.cursor()
    cur.execute(
        """
        UPDATE profiles
        SET is_active = %s,
            account_status_reason = %s,
            account_status_updated_at = NOW()
        WHERE legacy_user_id = %s
        RETURNING legacy_user_id AS id, email, is_active
        """,
        (is_active, reason, target_user_id),
    )
    row = cur.fetchone()
    log_transaction(
        conn,
        action="admin_account_status_changed",
        endpoint=endpoint,
        user_id=actor.get("user_id"),
        role_code=actor.get("role_code"),
        details={"target_user_id": target_user_id, "is_active": is_active, "reason": reason},
    )
    return row


def change_user_role(conn, target_user_id: int, role_code: str, admin_password: str, reason: str, actor):
    endpoint = f"/api/users/{target_user_id}/role"
    verify_admin_password(conn, actor, admin_password, endpoint)
    target_user = _get_user_by_legacy_id(conn, target_user_id)

    if str(target_user["auth_user_id"]) == str(actor.get("auth_user_id")) and role_code != "admin":
        log_transaction(
            conn,
            action="security_self_demote_blocked",
            endpoint=endpoint,
            user_id=actor.get("user_id"),
            role_code=actor.get("role_code"),
            details={"target_user_id": target_user_id, "requested_role": role_code},
        )
        conn.commit()
        raise HTTPException(status_code=409, detail="Admin cannot demote own account")

    if target_user["role_code"] == "admin" and role_code != "admin":
        _ensure_not_last_active_admin(conn, target_user, actor, endpoint, "admin_role_removed")

    cur = conn.cursor()
    cur.execute("SELECT id, code, name FROM roles WHERE code = %s", (role_code,))
    role = cur.fetchone()
    if not role:
        raise HTTPException(status_code=422, detail="Unknown role_code")

    cur.execute("DELETE FROM user_roles WHERE user_id = %s", (target_user["auth_user_id"],))
    cur.execute(
        """
        INSERT INTO user_roles (user_id, role_id)
        VALUES (%s, %s)
        ON CONFLICT (user_id, role_id) DO NOTHING
        """,
        (target_user["auth_user_id"], role["id"]),
    )
    cur.execute(
        """
        UPDATE profiles
        SET role_updated_at = NOW()
        WHERE legacy_user_id = %s
        """,
        (target_user_id,),
    )
    log_transaction(
        conn,
        action="admin_user_role_changed",
        endpoint=endpoint,
        user_id=actor.get("user_id"),
        role_code=actor.get("role_code"),
        details={"target_user_id": target_user_id, "role_code": role_code, "reason": reason},
    )
    return {
        "id": target_user_id,
        "email": target_user["email"],
        "role_code": role["code"],
        "role_name": role["name"],
    }
