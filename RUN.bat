@echo off
setlocal

echo Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install dependencies.
  exit /b 1
)

echo Installing Playwright Chromium...
python -m playwright install chromium
if errorlevel 1 (
  echo Failed to install Playwright browser.
  exit /b 1
)

echo Starting web app at http://127.0.0.1:8000
python -m web_portal.web_app
