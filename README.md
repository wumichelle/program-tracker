# Early-Career Program Tracker Website

This is a small website for tracking quant finance, trading, fintech, software engineering, and women-in-STEM programs for an incoming first-year student starting university in September 2026.

## What it does

- Shows all tracked programs in a searchable table.
- Groups programs by priority: Must track, Also track, Bonus / resume-building.
- Stores official URLs in `data/programs.json`.
- Uses `scripts/update_status.py` to check official pages for deadline/application/status signals.
- Saves monitoring results into `data/status-history.json`.
- Can be hosted free on GitHub Pages.
- Can auto-update daily using GitHub Actions.

## Important!!

This might not have the correct deadlines. It flags changes and application-related text so you know what to check. Always click the official program page before applying.
