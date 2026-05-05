#!/usr/bin/env python3
"""
Update official-page status and deadline signals for the Early-Career Program Tracker.
"""

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS_PATH = ROOT / "data" / "programs.json"
HISTORY_PATH = ROOT / "data" / "status-history.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 program-tracker-bot/1.1; educational personal tracker"
}

DEADLINE_PATTERNS = [
    r"(application deadline|deadline|apply by|applications? close|registration deadline|register by)[:\s\-–—]*[^.\n]{0,180}",
    r"(jan\.?|january|feb\.?|february|mar\.?|march|apr\.?|april|may|jun\.?|june|jul\.?|july|aug\.?|august|sep\.?|sept\.?|september|oct\.?|october|nov\.?|november|dec\.?|december)\s+\d{1,2},?\s+20\d{2}[^.\n]{0,100}",
    r"\d{1,2}\s+(jan\.?|january|feb\.?|february|mar\.?|march|apr\.?|april|may|jun\.?|june|jul\.?|july|aug\.?|august|sep\.?|sept\.?|september|oct\.?|october|nov\.?|november|dec\.?|december)\s+20\d{2}[^.\n]{0,100}",
]

SIGNAL_PATTERNS = [
    r"application deadline[:\s]+[^.\n]{0,160}",
    r"applications? (are )?(now )?(open|closed)",
    r"apply (now|by)[^.\n]{0,160}",
    r"deadline[:\s]+[^.\n]{0,160}",
    r"registration deadline[:\s]+[^.\n]{0,160}",
    r"register by[^.\n]{0,160}",
    r"first[- ]year[^.\n]{0,120}",
    r"sophomore[^.\n]{0,120}",
]


def clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)


def unique_matches(matches):
    seen = set()
    output = []
    for match in matches:
        cleaned = re.sub(r"\s+", " ", match).strip()
        normalized = cleaned.lower()
        if cleaned and normalized not in seen:
            seen.add(normalized)
            output.append(cleaned)
    return output


def extract_deadline(text: str):
    matches = []
    for pattern in DEADLINE_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            matches.append(match.group(0)[:220])
    matches = unique_matches(matches)
    return matches[0] if matches else ""


def extract_signals(text: str, keywords):
    matches = []
    lower_text = text.lower()

    for pattern in SIGNAL_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            matches.append(match.group(0)[:200])

    for keyword in keywords or []:
        keyword_lower = keyword.lower()
        if keyword_lower and keyword_lower in lower_text:
            index = lower_text.find(keyword_lower)
            snippet = text[max(0, index - 70): index + 170]
            matches.append(snippet)

    return unique_matches(matches)[:8]


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
        "changed": False,
        "status_text": "",
        "deadline_text": "",
        "latest_match": "",
        "signals": [],
        "error": "",
    }

    try:
        response = requests.get(url, headers=HEADERS, timeout=25)
        record["http_status"] = response.status_code
        response.raise_for_status()

        text = clean_text(response.text)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        old_digest = previous.get(url, {}).get("content_hash")

        record["content_hash"] = digest
        record["changed"] = bool(old_digest and old_digest != digest)
        record["ok"] = True

        deadline_text = extract_deadline(text)
        signals = extract_signals(text, program.get("keywords", []))
        record["deadline_text"] = deadline_text
        record["signals"] = signals
        record["latest_match"] = deadline_text or (signals[0] if signals else "")

        lower_text = text.lower()
        if "applications are now closed" in lower_text or "applications closed" in lower_text:
            record["status_text"] = "Applications may be closed"
        elif deadline_text:
            record["status_text"] = "Deadline signal found"
        elif "application deadline" in lower_text or "apply now" in lower_text or "apply by" in lower_text:
            record["status_text"] = "Application/deadline signal found"
        elif record["changed"]:
            record["status_text"] = "Page changed since last check"
        else:
            record["status_text"] = "No clear application signal"

    except Exception as error:
        record["error"] = str(error)[:300]
        old_record = previous.get(url)
        if old_record:
            record["content_hash"] = old_record.get("content_hash")
            record["deadline_text"] = old_record.get("deadline_text", "")

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
            print(f"{record['company']} - {record['program']}: {record['status_text']}")
            time.sleep(1.2)

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
