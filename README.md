# Job Alerts via GitHub Actions

Scrapes LinkedIn Jobs for Product Data Scientist roles in the United States that
were posted within the last 24 hours, then emails you when new postings appear.
Company size is included when LinkedIn makes it available, but missing company
size does not exclude a job.

## How it works

1. A scheduled GitHub Actions workflow (`.github/workflows/scrape-jobs.yml`)
   runs twice daily at 00:00 and 12:00 UTC.
2. `main.py` launches a headless Chromium via Playwright, searches LinkedIn Jobs
   for `"Product data scientist"` in `"United States"` with LinkedIn's 24-hour
   posted-date filter, and collects job cards.
3. Jobs are filtered to titles containing both `"product"` and
   `"data scientist"`. Location is scoped by the LinkedIn search URL.
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
| `LINKEDIN_EMAIL`     | Optional LinkedIn login email for richer access       |
| `LINKEDIN_PASSWORD`  | Optional LinkedIn login password                      |

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
# Optional, for LinkedIn pages that require login:
export LINKEDIN_EMAIL="you@example.com"
export LINKEDIN_PASSWORD="your-linkedin-password"
python main.py
```

First local run will create `state/seen_jobs.json` and email you about every
current matching job. Subsequent runs will only email about *new* ones.

## Customizing

- **Change the role filter**: edit the `TITLE_REQUIRED_TERMS` constant in
  `main.py` and the LinkedIn `KEYWORDS` value in `scrapers/linkedin.py`.
- **Change LinkedIn scrape limits**: set `LINKEDIN_MAX_RESULTS` or
  `LINKEDIN_MAX_ENRICH` in the workflow or local environment.
- **Change the cron schedule**: edit the `cron:` line in
  `.github/workflows/scrape-jobs.yml`. The default
  `"0 0,12 * * *"` runs at 00:00 and 12:00 UTC.
