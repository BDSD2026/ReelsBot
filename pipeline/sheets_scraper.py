"""
Google Sheets Story Reader — replaces the Reddit scraper.

Reads stories directly from a Google Sheet with columns:
  Column A: Title  ("AITA - Am i the asshole?" header, story titles below)
  Column B: Story  (full story body text)

Supports two fetch modes:
  1. Public sheet  → CSV export URL (no auth needed)
  2. Service account → gspread library (for private sheets)

Configure SHEETS_MODE in .env: "public" (default) or "service_account"
"""

import csv
import io
import hashlib
import logging
import requests
import re
from utils.config import config

log = logging.getLogger(__name__)


class GoogleSheetsScraper:
    def __init__(self):
        self.sheet_id = config.SHEETS_ID
        self.mode = config.SHEETS_MODE  # "public" or "service_account"

    # ── Public entry point ────────────────────────────────────────────

    def fetch_candidates(self, **kwargs) -> list[dict]:
        """
        Returns a list of story dicts in the same shape the rest of the
        pipeline expects (same keys as the old Reddit scraper output).
        """
        rows = self._fetch_rows()
        candidates = []

        for row in rows:
            title = row.get("title", "").strip()
            body = row.get("body", "").strip()

            if not title or not body:
                continue

            # Skip header-like rows
            if title.lower().startswith("aita - am i the asshole"):
                continue

            # Clean up body — remove mode annotations like "POO Mode Activated"
            body = self._clean_body(body)

            word_count = len(body.split())
            if word_count < config.MIN_WORDS:
                log.debug("Skipping '%s' — too short (%d words)", title[:50], word_count)
                continue

            # Generate a stable ID from the title so the DB dedup works
            story_id = hashlib.md5(title.encode()).hexdigest()[:10]

            candidates.append({
                "id": story_id,
                "title": title,
                "body": body,
                "score": word_count,          # use word count as proxy for "score"
                "num_comments": 0,
                "subreddit": "AITA",           # label for caption/thumbnail
                "url": f"https://docs.google.com/spreadsheets/d/{self.sheet_id}",
                "word_count": word_count,
                "upvote_ratio": 1.0,
            })

        log.info("  Loaded %d stories from Google Sheet", len(candidates))
        return candidates

    # ── Fetch rows ────────────────────────────────────────────────────

    def _fetch_rows(self) -> list[dict]:
        if self.mode == "service_account":
            return self._fetch_via_gspread()
        return self._fetch_via_csv()

    def _fetch_via_csv(self) -> list[dict]:
        """Fetch public sheet as CSV — no auth required."""
        url = (
            f"https://docs.google.com/spreadsheets/d/{self.sheet_id}"
            f"/export?format=csv&gid=0"
        )
        log.info("  Fetching sheet via CSV export...")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()

        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)

        if not rows:
            raise ValueError("Google Sheet is empty")

        # First row is the header — map column index → name
        # Expected: col 0 = title, col 1 = body
        results = []
        for row in rows[1:]:  # skip header
            if len(row) < 2:
                continue
            results.append({"title": row[0], "body": row[1]})

        return results

    def _fetch_via_gspread(self) -> list[dict]:
        """Fetch via gspread service account — works for private sheets."""
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            raise ImportError(
                "Install gspread and google-auth for service account mode:\n"
                "  pip install gspread google-auth"
            )

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = Credentials.from_service_account_file(
            config.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=scopes
        )
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(self.sheet_id).sheet1
        records = sheet.get_all_records()  # uses first row as header keys

        results = []
        for rec in records:
            # Flexible column name matching
            title = rec.get("AITA - Am i the asshole?") or rec.get("Title") or rec.get("title") or ""
            body = rec.get("Story") or rec.get("Body") or rec.get("story") or ""
            results.append({"title": title, "body": body})

        return results

    # ── Helpers ───────────────────────────────────────────────────────

    def _clean_body(self, text: str) -> str:
        """Strip Reddit/sheet annotations that shouldn't appear in video."""
        # Remove lines like "POO Mode Activated 💩" or "Not the A-hole POO Mode"
        lines = text.splitlines()
        cleaned = [
            line for line in lines
            if not re.search(r"poo mode|not the a-hole|asshole points|esh |nta |yta |nah ", line, re.IGNORECASE)
        ]
        return "\n".join(cleaned).strip()
