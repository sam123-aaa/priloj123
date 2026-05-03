Clients are split by platform and business role:

- `web/`
  Manager web client for dashboard and report templates.
- `mobile_kivy/`
  Mobile client on Kivy for metrologist, mechanic, quality engineer.
- `desktop_pyside/`
  Desktop client on PySide6 for tech expert and dispatcher specialist.

All clients use the same FastAPI backend and Supabase database.
