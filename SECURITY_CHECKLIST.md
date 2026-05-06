# Security checklist

This file is for the teacher review and for Burp Suite checks. The expected result is written next to each check.

## RBAC and admin actions

- `GET /api/users` with a non-admin token: `403`.
- `GET /api/roles` with a non-admin token: `403`.
- `POST /api/users/{id}/account-status` with a wrong `admin_password`: `403`.
- `POST /api/users/{id}/role` with a wrong `admin_password`: `403`.
- Try to disable or demote the last active admin: `409`.
- Try to demote your own admin account: `409`.

## Mass assignment

Send extra fields to write endpoints:

```json
{
  "is_admin": true,
  "owner_id": 1,
  "user_id": 1,
  "role_code": "admin"
}
```

Expected result: `422`. The server rejects unknown fields instead of silently ignoring them.

## IDOR

- Log in as a normal user.
- Change an id in Burp, for example `task_id`, `fault_id`, `recommendation_id`, `report job_id`.
- Expected result: `403` or `404`.
- Repeat the same request with an admin token. Expected result: normal access.
- Denied command attempts are written as `security_idor_denied` in `transactions`.

## XSS and CSS injection

Use these payloads in text fields such as recommendation text, quality notes, report title or names:

```text
<script>alert(1)</script>
<img src=x onerror=alert(1)>
<style>body{display:none}</style>
javascript:alert(1)
url(javascript:alert(1))
```

Expected result: `422` on API input. Existing frontend tables/cards escape text before inserting it into the DOM.

## CSRF

- Unsafe request with `Origin: https://evil.example`: `403`.
- Cookie request with `csrf_token` cookie but without `X-CSRF-Token`: `403`.
- Cookie request with matching cookie and header from `GET /csrf-token`: passes CSRF and then continues to normal auth/validation.
- Bearer token remains the main auth mode; browsers do not attach Bearer tokens automatically.

## SQL injection

Use payloads like:

```text
' OR '1'='1
1; DROP TABLE users;
```

Expected result: no SQL error leak and no extra data. SQL that uses user input is parameterized with `%s` or ORM parameters.

## RFI and LFI

Use unsafe file names:

```text
../../.env
..\..\Windows\win.ini
C:\Windows\win.ini
https://evil.example/payload
file:///etc/passwd
bad%00name.docx
```

Expected result: `400` or `422`. Report documents are fetched by UUID/job id and owner check, not by arbitrary path.

## Rate limit and observability

- Send more than `SECURITY_RATE_LIMIT_PER_MINUTE` requests per minute from the same IP and token user: `429`.
- `GET /observability/metrics` as non-admin: `403`.
- `GET /observability/hot-points` as admin: `200`.

## Server-only admin recovery

Run only on the server:

```bash
python scripts/recover_admin.py --email admin@gmail.com --password "NewPassword123!"
```

Expected result: an active admin role is restored or created and `security_admin_recovered` is written to audit.
