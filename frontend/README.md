Frontend is intentionally static so it can be uploaded with FileZilla.

Files:
- `index.html` entry page
- `web.html` dashboard/report client
- `mobile.html` field-work client
- `desktop.html` monitoring client
- `app.js` shared logic
- `styles.css` shared styles

Configuration:
- open `index.html`
- set backend URL, for local demo: `http://127.0.0.1:8000`
- the value is stored in browser `localStorage`

Deployment:
- upload the whole `frontend/` folder to static hosting
- keep FastAPI deployed separately
- backend must allow CORS for the hosting domain
