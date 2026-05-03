import json
import logging

logger = logging.getLogger("maintenance.audit")


def log_transaction(conn, action: str, endpoint: str, user_id=None, role_code=None, details=None):
    payload = json.dumps(details or {}, ensure_ascii=False, default=str)
    logger.info(
        "audit action=%s endpoint=%s user_id=%s role_code=%s details=%s",
        action,
        endpoint,
        user_id,
        role_code,
        payload,
    )

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO transactions (user_id, role_code, action, endpoint, details)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        """,
        (
            user_id,
            role_code,
            action,
            endpoint,
            payload,
        ),
    )
