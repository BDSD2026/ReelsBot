# ReelsBot — GitHub Actions Setup
# Takes 5 minutes. Runs free forever. Everything in your browser.

## How it works
- Code lives in a GitHub repository (private, only you can see it)
- GitHub runs the pipeline automatically every day at 10 AM
- When done, your reel.mp4 + caption.txt appear as a downloadable "Artifact"
- You click download, post to Instagram manually

---

## Setup (5 minutes, all in browser)

### Step 1 — Create a GitHub account
Go to github.com → Sign up (free). Skip if you have one.

### Step 2 — Create a new private repository
1. github.com → click the + icon top right → New repository
2. Name it: reelsbot
3. Set to Private
4. Click Create repository

### Step 3 — Upload the code
1. On your new empty repo page, click "uploading an existing file"
2. Drag ALL files from the reelsbot_github folder into the upload area
   (include the .github folder — make sure hidden folders are visible)
3. Click "Commit changes"

### Step 4 — Add your Google credentials as a Secret
1. In your repo → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: GOOGLE_SERVICE_ACCOUNT_JSON
4. Value: open your service_account.json file, copy ALL the contents, paste here
5. Click "Add secret"

### Step 5 — Run it now (manually)
1. In your repo → click "Actions" tab
2. Click "ReelsBot — Generate Daily Reel" in the left sidebar
3. Click "Run workflow" → "Run workflow"
4. Watch it run — green steps = working, takes ~20 min for Veo 2

### Step 6 — Download your Reel
1. When the workflow shows a green ✓, click on the run
2. Scroll down to "Artifacts"
3. Click "reel-1-1" to download a zip
4. Unzip → reel.mp4 + thumbnail.jpg + caption.txt are inside

---

## Every day after setup
- Runs automatically at 10 AM UTC (3:30 PM IST)
- Go to Actions tab → latest run → Artifacts → download
- Or manually trigger anytime: Actions → Run workflow

## To change the schedule
Edit .github/workflows/reelsbot.yml → change the cron line:
  '0 10 * * *'  = 10 AM UTC daily  (3:30 PM IST)
  '0 4 * * *'   = 4 AM UTC daily   (9:30 AM IST)
  '30 3 * * *'  = 9 AM IST daily

## Add more stories
Just add rows to your Google Sheet — pipeline picks them up automatically.
