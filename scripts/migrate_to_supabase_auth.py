import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_db
from supabase_auth import admin_request


PASSWORDS = {
    "temp-admin@example.com": "Admin123!",
    "temp-manager@example.com": "Manager123!",
    "temp-metrologist@example.com": "Metrologist123!",
    "temp-mechanic@example.com": "Mechanic123!",
    "temp-quality@example.com": "Quality123!",
    "temp-techexpert@example.com": "Expert123!",
    "temp-dispatcher@example.com": "Dispatch123!",
    "admin@example.com": "Admin123!",
    "manager@example.com": "Manager123!",
    "metrolog@example.com": "Metrologist123!",
    "mechanic@example.com": "Mechanic123!",
    "quality@example.com": "Quality123!",
    "techexpert@example.com": "Expert123!",
    "specialist@example.com": "Dispatch123!",
}


def load_legacy_users() -> List[dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT au.id AS legacy_user_id, au.email, au.full_name, r.code AS role
            FROM auth_users au
            JOIN user_roles ur ON ur.user_id = au.id
            JOIN roles r ON r.id = ur.role_id
            ORDER BY au.id
            """
        )
        return cur.fetchall()


def list_auth_users() -> Dict[str, dict]:
    result = admin_request("/auth/v1/admin/users?per_page=1000")
    users = result.get("users", result if isinstance(result, list) else [])
    return {item["email"].lower(): item for item in users if item.get("email")}


def ensure_auth_user(email: str, password: str, existing: Dict[str, dict]) -> dict:
    current = existing.get(email.lower())
    if not current:
        current = admin_request(
            "/auth/v1/admin/users",
            method="POST",
            payload={
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"source": "python_project_demo"},
            },
        )
    else:
        current = admin_request(
            f"/auth/v1/admin/users/{current['id']}",
            method="PUT",
            payload={
                "password": password,
                "email_confirm": True,
                "user_metadata": {"source": "python_project_demo"},
            },
        )
    existing[email.lower()] = current
    return current


def apply_public_auth_schema(assignments: List[dict]):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                user_id UUID PRIMARY KEY,
                legacy_user_id INTEGER UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                full_name TEXT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS roles (
                id SERIAL PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL
            );

            INSERT INTO roles (code, name)
            VALUES
                ('dispatcher_specialist', 'Специалист по диспетчеризации'),
                ('metrologist', 'Метролог'),
                ('quality_engineer', 'Инженер контроля качества'),
                ('manager', 'Менеджер'),
                ('mechanic', 'Механик'),
                ('tech_expert', 'Техник-эксперт'),
                ('admin', 'Администратор')
            ON CONFLICT (code) DO UPDATE
            SET name = EXCLUDED.name;

            DROP VIEW IF EXISTS users;
            DROP TABLE IF EXISTS user_roles CASCADE;

            CREATE TABLE user_roles (
                user_id UUID NOT NULL,
                role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, role_id)
            );
            """
        )

        for item in assignments:
            cur.execute(
                """
                INSERT INTO profiles (user_id, legacy_user_id, email, full_name, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                ON CONFLICT (user_id) DO UPDATE
                SET legacy_user_id = EXCLUDED.legacy_user_id,
                    email = EXCLUDED.email,
                    full_name = EXCLUDED.full_name,
                    is_active = TRUE
                """,
                (item["auth_user_id"], item["legacy_user_id"], item["email"], item.get("full_name")),
            )
            cur.execute(
                """
                INSERT INTO user_roles (user_id, role_id)
                SELECT %s, id
                FROM roles
                WHERE code = %s
                ON CONFLICT (user_id, role_id) DO NOTHING
                """,
                (item["auth_user_id"], item["role"]),
            )

        cur.execute(
            """
            ALTER TABLE measurements ADD COLUMN IF NOT EXISTS recorded_by_auth_id UUID;
            ALTER TABLE measurements ADD COLUMN IF NOT EXISTS owner_auth_id UUID;
            ALTER TABLE faults ADD COLUMN IF NOT EXISTS confirmed_by_auth_id UUID;
            ALTER TABLE faults ADD COLUMN IF NOT EXISTS owner_auth_id UUID;
            ALTER TABLE maintenance_recommendations ADD COLUMN IF NOT EXISTS created_by_auth_id UUID;
            ALTER TABLE maintenance_recommendations ADD COLUMN IF NOT EXISTS owner_auth_id UUID;
            ALTER TABLE maintenance_plan ADD COLUMN IF NOT EXISTS created_by_auth_id UUID;
            ALTER TABLE maintenance_plan ADD COLUMN IF NOT EXISTS owner_auth_id UUID;
            ALTER TABLE maintenance_tasks ADD COLUMN IF NOT EXISTS mechanic_auth_id UUID;
            ALTER TABLE maintenance_tasks ADD COLUMN IF NOT EXISTS owner_auth_id UUID;
            ALTER TABLE quality_checks ADD COLUMN IF NOT EXISTS inspector_auth_id UUID;
            ALTER TABLE quality_checks ADD COLUMN IF NOT EXISTS owner_auth_id UUID;
            ALTER TABLE reports ADD COLUMN IF NOT EXISTS created_by_auth_id UUID;
            ALTER TABLE reports ADD COLUMN IF NOT EXISTS owner_auth_id UUID;
            ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS owner_auth_id UUID;
            ALTER TABLE report_read_model ADD COLUMN IF NOT EXISTS owner_auth_id UUID;
            ALTER TABLE transactions ADD COLUMN IF NOT EXISTS auth_user_id UUID;

            UPDATE measurements m SET recorded_by_auth_id = p.user_id
            FROM profiles p WHERE m.recorded_by = p.legacy_user_id AND m.recorded_by_auth_id IS NULL;
            UPDATE measurements m SET owner_auth_id = p.user_id
            FROM profiles p WHERE m.owner_id = p.legacy_user_id AND m.owner_auth_id IS NULL;
            UPDATE faults f SET confirmed_by_auth_id = p.user_id
            FROM profiles p WHERE f.confirmed_by = p.legacy_user_id AND f.confirmed_by_auth_id IS NULL;
            UPDATE faults f SET owner_auth_id = p.user_id
            FROM profiles p WHERE f.owner_id = p.legacy_user_id AND f.owner_auth_id IS NULL;
            UPDATE maintenance_recommendations mr SET created_by_auth_id = p.user_id
            FROM profiles p WHERE mr.created_by = p.legacy_user_id AND mr.created_by_auth_id IS NULL;
            UPDATE maintenance_recommendations mr SET owner_auth_id = p.user_id
            FROM profiles p WHERE mr.owner_id = p.legacy_user_id AND mr.owner_auth_id IS NULL;
            UPDATE maintenance_plan mp SET created_by_auth_id = p.user_id
            FROM profiles p WHERE mp.created_by = p.legacy_user_id AND mp.created_by_auth_id IS NULL;
            UPDATE maintenance_plan mp SET owner_auth_id = p.user_id
            FROM profiles p WHERE mp.owner_id = p.legacy_user_id AND mp.owner_auth_id IS NULL;
            UPDATE maintenance_tasks mt SET mechanic_auth_id = p.user_id
            FROM profiles p WHERE mt.mechanic_id = p.legacy_user_id AND mt.mechanic_auth_id IS NULL;
            UPDATE maintenance_tasks mt SET owner_auth_id = p.user_id
            FROM profiles p WHERE mt.owner_id = p.legacy_user_id AND mt.owner_auth_id IS NULL;
            UPDATE quality_checks qc SET inspector_auth_id = p.user_id
            FROM profiles p WHERE qc.inspector_id = p.legacy_user_id AND qc.inspector_auth_id IS NULL;
            UPDATE quality_checks qc SET owner_auth_id = p.user_id
            FROM profiles p WHERE qc.owner_id = p.legacy_user_id AND qc.owner_auth_id IS NULL;
            UPDATE reports r SET created_by_auth_id = p.user_id
            FROM profiles p WHERE r.created_by = p.legacy_user_id AND r.created_by_auth_id IS NULL;
            UPDATE reports r SET owner_auth_id = p.user_id
            FROM profiles p WHERE r.owner_id = p.legacy_user_id AND r.owner_auth_id IS NULL;
            UPDATE background_jobs bj SET owner_auth_id = p.user_id
            FROM profiles p WHERE bj.owner_id = p.legacy_user_id AND bj.owner_auth_id IS NULL;
            UPDATE report_read_model rrm SET owner_auth_id = p.user_id
            FROM profiles p WHERE rrm.owner_id = p.legacy_user_id AND rrm.owner_auth_id IS NULL;
            UPDATE transactions t SET auth_user_id = p.user_id
            FROM profiles p WHERE t.user_id = p.legacy_user_id AND t.auth_user_id IS NULL;

            DROP VIEW IF EXISTS users;
            DROP TABLE IF EXISTS auth_users CASCADE;

            CREATE VIEW users AS
            SELECT
                p.legacy_user_id AS id,
                p.email,
                p.full_name,
                r.code AS role,
                p.created_at
            FROM profiles p
            LEFT JOIN user_roles ur ON ur.user_id = p.user_id
            LEFT JOIN roles r ON r.id = ur.role_id;
            """
        )


def main():
    legacy_users = load_legacy_users()
    auth_users = list_auth_users()
    assignments = []
    for legacy_user in legacy_users:
        email = legacy_user["email"]
        password = PASSWORDS.get(email, "Password123!")
        auth_user = ensure_auth_user(email, password, auth_users)
        assignments.append(
            {
                "legacy_user_id": legacy_user["legacy_user_id"],
                "email": email,
                "full_name": legacy_user.get("full_name"),
                "role": legacy_user["role"],
                "auth_user_id": auth_user["id"],
            }
        )

    apply_public_auth_schema(assignments)
    print(json.dumps(assignments, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
