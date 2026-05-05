#!/usr/bin/env python3
"""
Auto-update status/deadline signals for the Early-Career Program Tracker.

This version uses Playwright first, so it reads the visible page text after
JavaScript loads. If browser scraping fails, it falls back to requests +
BeautifulSoup.

Important behavior:
- New York / NYC deadline text is prioritized when multiple regions exist.
- Detected Deadline only uses real deadline-like text.
- Generic words like "first year" or "sophomore" are allowed as Auto Signal context
  but are never shown as the Detected Deadline.
"""

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS_PATH = ROOT / "data" / "programs.json"
HISTORY_PATH = ROOT / "data" / "status-history.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 program-tracker-bot/2.0; educational personal tracker"
}

# These patterns are allowed to become Detected Deadline.
DEADLINE_PATTERNS = [
    r"[^.\n]{0,160}(?:New York|NYC)[^.\n]{0,260}(?:deadline to apply|application deadline|deadline|apply by|applications? close|registration deadline|register by)[^.\n]{0,220}",
    r"[^.\n]{0,120}(?:deadline to apply|application deadline|deadline|apply by|applications? close|registration deadline|register by)[:\s\-–—]*[^.\n]{0,260}",
    r"(?:deadline to apply is|deadline is|apply by|applications? close(?:s)? on|registration deadline is)[^.\n]{0,260}",
    r"(?:Jan\.?|January|Feb\.?|February|Mar\.?|March|Apr\.?|April|May|Jun\.?|June|Jul\.?|July|Aug\.?|August|Sep\.?|Sept\.?|September|Oct\.?|October|Nov\.?|November|Dec\.?|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+20\d{2}[^.\n]{0,160}",
    r"\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan\.?|January|Feb\.?|February|Mar\.?|March|Apr\.?|April|May|Jun\.?|June|Jul\.?|July|Aug\.?|August|Sep\.?|Sept\.?|September|Oct\.?|October|Nov\.?|November|Dec\.?|December)\s+20\d{2}[^.\n]{0,160}",
]

# These are context signals only, not necessarily deadlines.
SIGNAL_PATTERNS = [
    r"applications? (?:are )?(?:now )?(?:open|closed)",
    r"accepting applications",
    r"deadline[^.\n]{0,180}",
    r"apply (?:now|by)[^.\n]{0,180}",
    r"registration deadline[^.\n]{0,180}",
    r"register by[^.\n]{0,180}",
    r"New York[^.\n]{0,220}",
    r"NYC[^.\n]{0,220}",
]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or " ").strip()


def get_visible_text_with_browser(url: str) -> str:
    """Read text as a real browser would, after JS rendering."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1440, "height": 1200},
        )
        page.goto(url, wait_until="networkidle", timeout=70000)

        # Give slow client-rendered content one more moment.
        page.wait_for_timeout(2500)

        # Try clicking obvious expanders only if they exist.
        # This is conservative to avoid clicking application buttons.
        for label in ["View more", "See more", "Show more", "More"]:
            try:
                locator = page.get_by_text(label, exact=False)
                if locator.count() > 0:
                    locator.first.click(timeout=1500)
                    page.wait_for_timeout(1000)
            except Exception:
                pass

        text = page.locator("body").inner_text(timeout=40000)
        browser.close()
        return normalize_text(text)


def get_text_with_requests(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    return normalize_text(soup.get_text(" ", strip=True))


def get_page_text(url: str):
    """Return tuple: visible text, method used, error if any."""
    try:
        return get_visible_text_with_browser(url), "playwright", ""
    except Exception as browser_error:
        try:
            return get_text_with_requests(url), "requests_fallback", str(browser_error)[:300]
        except Exception as requests_error:
            raise RuntimeError(
                f"Playwright failed: {browser_error}; requests fallback failed: {requests_error}"
            )


def unique_matches(matches):
    seen = set()
    output = []
    for match in matches:
        cleaned = normalize_text(str(match))
        normalized = cleaned.lower()
        if cleaned and normalized not in seen:
            seen.add(normalized)
            output.append(cleaned)
    return output


def extract_deadline_candidates(text: str):
    matches = []
    for pattern in DEADLINE_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            matches.append(match.group(0)[:420])
    return unique_matches(matches)


def looks_like_real_deadline(candidate: str) -> bool:
    text = candidate.lower()

    deadline_words = [
        "deadline",
        "apply by",
        "deadline to apply",
        "applications close",
        "application deadline",
        "registration deadline",
        "register by",
    ]

    month_words = [
        "january", "jan", "february", "feb", "march", "mar", "april", "apr",
        "may", "june", "jun", "july", "jul", "august", "aug", "september",
        "sept", "sep", "october", "oct", "november", "nov", "december", "dec",
    ]

    has_deadline_word = any(word in text for word in deadline_words)
    has_date = any(month in text for month in month_words) and re.search(r"\d{1,2}", text)

    return bool(has_deadline_word and has_date)


def choose_best_deadline(candidates):
    real_candidates = [c for c in candidates if looks_like_real_deadline(c)]

    if not real_candidates:
        return "", ""

    # Prioritize New York/NYC.
    for candidate in real_candidates:
        lowered = candidate.lower()
        if "new york" in lowered or "nyc" in lowered:
            return candidate, candidate

    return real_candidates[0], ""


def extract_signals(text: str, keywords):
    matches = []

    for pattern in SIGNAL_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            matches.append(match.group(0)[:320])

    lower_text = text.lower()
    for keyword in keywords or []:
        keyword_lower = str(keyword).lower()
        if keyword_lower and keyword_lower in lower_text:
            index = lower_text.find(keyword_lower)
            snippet = text[max(0, index - 90): index + 230]
            matches.append(snippet)

    return unique_matches(matches)[:10]


def fetch_one(program, previous):
    url = program.get("official_url", "").strip()
    if not url:
        return None

    record = {
        "company": program.get("company"),
        "program": program.get("program"),
        "url": url,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "ok": False,
        "http_status": None,
        "method": "",
        "changed": False,
        "status_text": "",
        "deadline_text": "",
        "ny_deadline_text": "",
        "latest_match": "",
        "signals": [],
        "error": "",
    }

    try:
        text, method, method_warning = get_page_text(url)
        record["method"] = method
        if method_warning:
            record["error"] = f"Browser fallback note: {method_warning}"

        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        old_digest = previous.get(url, {}).get("content_hash")

        record["content_hash"] = digest
        record["changed"] = bool(old_digest and old_digest != digest)
        record["ok"] = True

        deadline_candidates = extract_deadline_candidates(text)
        deadline_text, ny_deadline_text = choose_best_deadline(deadline_candidates)
        signals = extract_signals(text, program.get("keywords", []))

        record["deadline_text"] = deadline_text
        record["ny_deadline_text"] = ny_deadline_text
        record["signals"] = signals
        record["latest_match"] = signals[0] if signals else ""

        lower_text = text.lower()
        if "applications are now closed" in lower_text or "applications closed" in lower_text:
            record["status_text"] = "Applications may be closed"
        elif deadline_text:
            record["status_text"] = "Deadline signal found"
        elif "accepting applications" in lower_text or "apply now" in lower_text:
            record["status_text"] = "Application signal found"
        elif record["changed"]:
            record["status_text"] = "Page changed since last check"
        else:
            record["status_text"] = "No clear application signal"

    except Exception as error:
        record["error"] = str(error)[:500]
        old_record = previous.get(url)
        if old_record:
            record["content_hash"] = old_record.get("content_hash")
            record["deadline_text"] = old_record.get("deadline_text", "")
            record["ny_deadline_text"] = old_record.get("ny_deadline_text", "")
            record["latest_match"] = old_record.get("latest_match", "")

    return record


def main():
    data = json.loads(PROGRAMS_PATH.read_text(encoding="utf-8"))

    try:
        previous = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        previous = {}

    new_history = {}

    for program in data.get("programs", []):
        record = fetch_one(program, previous)
        if record:
            new_history[program["official_url"]] = record
            print(
                f"{record['company']} - {record['program']}: "
                f"{record['status_text']} | {record.get('deadline_text') or 'no deadline'}"
            )
            time.sleep(1.0)

    HISTORY_PATH.write_text(
        json.dumps(new_history, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    PROGRAMS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
