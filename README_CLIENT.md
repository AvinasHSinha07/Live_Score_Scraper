# Client Package - LiveScore Stats Web App

This folder is standalone for running the web app.

## Included
- `main.py` (scraper logic)
- `web_portal/web_app.py` (Flask app)
- `web_portal/templates/index.html` (UI)
- `requirements.txt`
- `RUN.bat`

## Run (Windows)
1. Open this folder in terminal.
2. Run:
   `RUN.bat`
3. Open browser:
   `http://127.0.0.1:8000`

## What the app does
- Paste one URL -> downloads one team CSV
- Paste multiple URLs -> downloads one ZIP containing separate team CSV files

## Manual commands (alternative)
```powershell
pip install -r requirements.txt
python -m playwright install chromium
python -m web_portal.web_app
```

## Deploy on Render
This repo now includes `render.yaml`, so Render can auto-detect build/start settings.

1. Push this folder to GitHub (or your Git provider).
2. In Render, click **New +** -> **Blueprint**.
3. Connect your repo and select this project.
4. Render reads `render.yaml` and creates a Python web service.
5. Click **Apply** to deploy.

Render configuration used:
- Build command: `pip install -r requirements.txt`
- Start command: `PLAYWRIGHT_BROWSERS_PATH=/opt/render/project/src/.playwright-browsers python -m playwright install chromium && gunicorn web_portal.web_app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 300`
- Python version: `3.11.11`

Notes:
- The app automatically binds to Render's `PORT` environment variable.
- First deploy can take a bit longer because Playwright downloads Chromium.
- Browser binaries are installed on startup into `PLAYWRIGHT_BROWSERS_PATH` so they are always present at runtime.
- Runtime tuning is set via env vars in `render.yaml`:
   - `PLAYWRIGHT_BROWSERS_PATH=/opt/render/project/src/.playwright-browsers`
   - `SCRAPER_MAX_WORKERS=2`
   - `SCRAPER_MAX_MATCHES=4`
   - `SCRAPER_REQUEST_TIMEOUT_SECONDS=150`
   - `SCRAPER_CACHE_TTL_SECONDS=900`

Performance notes:
- Lower `SCRAPER_MAX_MATCHES` gives faster download responses.
- `SCRAPER_CACHE_TTL_SECONDS` speeds up repeated requests for the same URL.
- If requests are still too slow, set `SCRAPER_MAX_MATCHES=3`.

If you still get a 500 on download:
1. Open Render service logs.
2. Look for `Scrape failed during download request` and the stack trace below it.
3. Reduce `SCRAPER_MAX_WORKERS` to `2` and redeploy.
