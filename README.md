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

## Important limitation

This does not guarantee deadlines are correct. It flags changes and application-related text so you know what to check. Always click the official program page before applying.

## How to host it for free on GitHub Pages

1. Create a new GitHub repository, for example `program-tracker`.
2. Upload all files in this folder to the repository.
3. In GitHub, go to `Settings` → `Pages`.
4. Under **Build and deployment**, choose `Deploy from a branch`.
5. Choose branch `main` and folder `/root`.
6. Your site will appear at `https://YOUR-USERNAME.github.io/program-tracker/`.

## How to make it update automatically

1. In the GitHub repository, go to `Settings` → `Actions` → `General`.
2. Under **Workflow permissions**, choose `Read and write permissions`.
3. The included workflow file is `.github/workflows/update-tracker.yml`.
4. It runs daily and can also be started manually: `Actions` → `Update program tracker` → `Run workflow`.

## How to add a new program

Open `data/programs.json` and add another program object with company, program, priority, audience, stage, region, category, official_url, keywords, and notes.

## Best hosting option

Use **GitHub Pages** if you want auto-updates without paying. Netlify and Vercel are easier for hosting static sites, but GitHub Pages + GitHub Actions is the simplest free setup for daily automatic checks.
