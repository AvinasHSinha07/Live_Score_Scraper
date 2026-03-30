import asyncio
import csv
import io
import os
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, List

from flask import Flask, Response, render_template, request

# Allow running this file from inside web_portal/ while importing ../main.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import main as scraper

app = Flask(__name__, template_folder="templates")


def parse_urls(raw_text: str) -> List[str]:
    urls = []
    for line in (raw_text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^https?://", line, flags=re.IGNORECASE):
            urls.append(line)
    return urls


def rows_to_csv_bytes(rows: List[dict]) -> bytes:
    if not rows:
        return b""

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


async def run_scrape(team_urls: List[str]) -> Dict[str, List[dict]]:
    worker_count = max(1, int(os.environ.get("SCRAPER_MAX_WORKERS", str(scraper.MAX_WORKERS))))
    match_limit = max(1, int(os.environ.get("SCRAPER_MAX_MATCHES", str(scraper.MAX_MATCHES))))
    sem = asyncio.Semaphore(worker_count)
    output: Dict[str, List[dict]] = {}

    async with scraper.async_playwright() as p:
        browser = await p.chromium.launch(
            headless=scraper.HEADLESS,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context()

        for team_url in team_urls:
            team_name = scraper.get_team_name_from_url(team_url)
            team_id = scraper.get_team_id_from_url(team_url)

            listing_page = await context.new_page()
            match_urls = await scraper.collect_recent_match_urls(
                listing_page,
                team_url,
                match_limit,
            )
            await listing_page.close()

            if not match_urls:
                output[team_name] = []
                continue

            async def scrape_worker(match_url: str):
                async with sem:
                    page = await context.new_page()
                    try:
                        result = await scraper.scrape_match_data(
                            page,
                            match_url,
                            target_team_id=team_id,
                            target_team_label=team_name,
                        )
                        if not result:
                            return None
                        _, stats_row, _ = result
                        return stats_row
                    finally:
                        await page.close()

            results = await asyncio.gather(*[scrape_worker(url) for url in match_urls])
            output[team_name] = [r for r in results if r]

        await browser.close()

    return output


def build_zip_from_team_rows(team_rows: Dict[str, List[dict]]) -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for team_name, rows in team_rows.items():
            if not rows:
                continue
            file_name = f"{team_name}_stats.csv"
            zf.writestr(file_name, rows_to_csv_bytes(rows))
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html")

    team_urls = parse_urls(request.form.get("team_urls", ""))
    if not team_urls:
        return render_template("index.html", error="Please paste at least one valid team results URL.")

    try:
        scraped = asyncio.run(run_scrape(team_urls))
    except Exception as exc:
        app.logger.exception("Scrape failed during download request")
        error_text = str(exc).strip() or exc.__class__.__name__
        return render_template(
            "index.html",
            error=(
                "Failed to collect data right now. "
                f"Details: {error_text[:300]}"
            ),
        )

    non_empty = {team: rows for team, rows in scraped.items() if rows}

    if not non_empty:
        return render_template("index.html", error="No match stats found for the provided URL(s).")

    # One URL => one CSV. Multiple URLs => one ZIP with separate CSV files.
    if len(team_urls) == 1 and len(non_empty) == 1:
        team_name, rows = next(iter(non_empty.items()))
        file_name = f"{team_name}_stats.csv"
        return Response(
            rows_to_csv_bytes(rows),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={file_name}"},
        )

    zip_bytes = build_zip_from_team_rows(non_empty)
    return Response(
        zip_bytes,
        mimetype="application/zip",
        headers={"Content-Disposition": "attachment; filename=team_stats_files.zip"},
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)
