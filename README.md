# Job Alerts via GitHub Actions

Scrapes Data Scientist roles from JPMC and Mastercard career sites four times a
day and emails you when new US-based postings appear.

## How it works

1. A scheduled GitHub Actions workflow (`.github/workflows/scrape-jobs.yml`)
   runs every 6 hours.
2. `main.py` launches a headless Chromium via Playwright, hits each company's
   search page, and collects job cards.
3. Jobs are filtered to titles containing `"data scientist"` AND a US location.
4. New postings (ones whose `job_id` is not already in `state/seen_jobs.json`)
   trigger an email via Gmail SMTP.
5. The updated `state/seen_jobs.json` is committed back to the repo so the next
   run knows what we've already seen.

## Setup

### 1. Push this folder to GitHub

```bash
cd git_actions
git add .
git commit -m "Initial commit: job scraper"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

### 2. Create a Gmail App Password

1. Enable 2-Step Verification on your Google account.
2. Go to <https://myaccount.google.com/apppasswords>.
3. Generate a new app password (pick "Mail" / "Other"). Copy the 16-character
   string.

### 3. Add GitHub Secrets

In your repo, go to **Settings > Secrets and variables > Actions > New
repository secret** and add:

| Name                 | Value                                                 |
| -------------------- | ----------------------------------------------------- |
| `EMAIL_SENDER`       | The Gmail address that will send alerts               |
| `EMAIL_APP_PASSWORD` | The 16-character Gmail app password from step 2       |
| `EMAIL_RECIPIENT`    | Where alerts should go (can be the same as `SENDER`)  |

### 4. First run

Trigger a manual run from **Actions > Scrape Jobs > Run workflow** to verify
everything works before you wait on the cron schedule.

## Local development

```bash
cd git_actions
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium

export EMAIL_SENDER="you@gmail.com"
export EMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export EMAIL_RECIPIENT="you@gmail.com"
python main.py
```

First local run will create `state/seen_jobs.json` and email you about every
current matching job. Subsequent runs will only email about *new* ones.

## Customizing

- **Add more companies**: create a new file in `scrapers/` following
  `scrapers/jpmc.py` as a template, then import and call it in `main.py`.
- **Change the role**: edit the `TITLE_KEYWORDS` constant in `main.py`.
- **Change the cron schedule**: edit the `cron:` line in
  `.github/workflows/scrape-jobs.yml`. The default
  `"0 0,6,12,18 * * *"` runs at 00:00, 06:00, 12:00, 18:00 UTC.
