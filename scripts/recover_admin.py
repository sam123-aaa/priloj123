import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from audit import log_transaction
from database import get_db
from services.admin_security import ensure_admin_security_schema
from supabase_auth import admin_request


def _create_auth_user(email: str, password: str, full_name: str):
    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {"full_name": full_name},
    }
    response = admin_request("/auth/v1/admin/users", method="POST", payload=payload)
    user = response.get("user") or response
    auth_user_id = user.get("id")
    if not auth_user_id:
        raise RuntimeError("Supabase did not return auth user id")
    return auth_user_id


def recover_admin(email: str, password: str, full_name: str, legacy_user_id: Optional[int]):
    email = email.strip().lower()
    with get_db() as conn:
        ensure_admin_security_schema(conn)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO roles (code, name)
            VALUES ('admin', 'Administrator')
            ON CONFLICT (code) DO NOTHING
            """
        )
        cur.execute("SELECT id FROM roles WHERE code = 'admin'")
        admin_role_id = cur.fetchone()["id"]

        cur.execute(
            """
            SELECT user_id, legacy_user_id
            FROM profiles
            WHERE email = %s
            LIMIT 1
            """,
            (email,),
        )
        profile = cur.fetchone()

        if profile:
            auth_user_id = profile["user_id"]
            resolved_legacy_id = profile["legacy_user_id"]
        else:
            if not password:
                raise RuntimeError("Password is required when the admin profile does not exist")
            auth_user_id = _create_auth_user(email, password, full_name)
            if legacy_user_id is None:
                cur.execute("SELECT COALESCE(MAX(legacy_user_id), 0) + 1 AS next_id FROM profiles")
                legacy_user_id = cur.fetchone()["next_id"]
            resolved_legacy_id = legacy_user_id
            cur.execute(
                """
                INSERT INTO profiles (user_id, legacy_user_id, email, full_name, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                """,
                (auth_user_id, resolved_legacy_id, email, full_name),
            )

        cur.execute(
            """
            UPDATE profiles
            SET is_active = TRUE,
                account_status_reason = 'Recovered from server CLI',
                account_status_updated_at = NOW()
            WHERE user_id = %s
            """,
            (auth_user_id,),
        )
        cur.execute("DELETE FROM user_roles WHERE user_id = %s", (auth_user_id,))
        cur.execute(
            """
            INSERT INTO user_roles (user_id, role_id)
            VALUES (%s, %s)
            ON CONFLICT (user_id, role_id) DO NOTHING
            """,
            (auth_user_id, admin_role_id),
        )
        log_transaction(
            conn,
            action="security_admin_recovered",
            endpoint="scripts/recover_admin.py",
            user_id=resolved_legacy_id,
            role_code="system",
            details={"email": email, "auth_user_id": str(auth_user_id)},
        )
    return resolved_legacy_id


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Recover or create an active admin account from the server only.")
    parser.add_argument("--email", default=os.getenv("RECOVER_ADMIN_EMAIL", "admin@gmail.com"))
    parser.add_argument("--password", default=os.getenv("RECOVER_ADMIN_PASSWORD", ""))
    parser.add_argument("--full-name", default=os.getenv("RECOVER_ADMIN_FULL_NAME", "Recovered Admin"))
    parser.add_argument("--legacy-user-id", type=int, default=None)
    args = parser.parse_args()

    legacy_user_id = recover_admin(args.email, args.password, args.full_name, args.legacy_user_id)
    print(f"admin recovered: email={args.email.strip().lower()} legacy_user_id={legacy_user_id}")


if __name__ == "__main__":
    main()
