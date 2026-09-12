# RuffNeck Prospector — Detailed Step-by-Step Implementation

Follow **in order**. At the end of each phase, do the **Checkpoint** before continuing.

**App name:** RuffNeck Prospector  
**Goal:** Running app at http://localhost:3000 with API at http://localhost:8000

---

# PHASE 0 — What you need (30 minutes)

## 0.1 Hardware / OS
- A computer with at least **8 GB RAM** (4 GB may work but will be slow)
- Windows 10/11, macOS, or Linux
- Stable internet

## 0.2 Software to install

### A. Docker path (easier if Docker works on your machine)
1. Install **Docker Desktop**: https://www.docker.com/products/docker-desktop/
2. Install → restart PC if asked → open Docker Desktop → wait until it says **Running**
3. Checkpoint: open a terminal and run:
   ```bash
   docker --version
   docker compose version
   ```
   You must see version numbers, not “command not found”.

### B. Manual path (if you prefer not to use Docker)
Install all of:
1. **Python 3.11+** — https://www.python.org/downloads/  
   - Windows: tick **“Add Python to PATH”** during install
2. **Node.js 18 or 20 LTS** — https://nodejs.org/
3. **Redis**
   - Windows: use Docker only for Redis, or Memurai, or WSL
   - Mac: `brew install redis` then `brew services start redis`
   - Ubuntu: `sudo apt update && sudo apt install redis-server`
4. Checkpoint:
   ```bash
   python3 --version    # or: python --version
   node --version
   npm --version
   redis-cli ping       # should reply PONG
   ```

## 0.3 Accounts (free)

| Account | Why | URL |
|---------|-----|-----|
| Supabase | Database + login | https://supabase.com |
| Gmail | Send email + detect replies | your Google account |
| Groq (optional) | Better PDF writing | https://console.groq.com |

---

# PHASE 1 — Supabase database (critical)

## 1.1 Create project
1. Go to https://supabase.com → **Start your project** / Sign in
2. **New organization** if asked (any name)
3. **New project**:
   - Name: `ruffneck` (or anything)
   - Database password: **save it in a password manager** (you rarely need it for this app)
   - Region: closest to you
4. Click **Create project** and wait 1–2 minutes until status is healthy

## 1.2 Copy API keys
1. Left sidebar → **Project Settings** (gear)
2. Click **API**
3. Copy and paste into a notepad temporarily:
   - **Project URL** → looks like `https://abcdefgh.supabase.co`
   - **service_role** key → long JWT starting with `eyJ...`  
     **Use the `service_role` secret, NOT the `anon` key.**  
     The backend needs service_role to run workers and bypass RLS safely on the server.

## 1.3 Run the database schema
1. Left sidebar → **SQL Editor**
2. Click **New query**
3. On your computer, open the file:
   ```
   ruffneck-prospector/database/schema.sql
   ```
4. Select **all** text (Ctrl+A) → Copy
5. Paste into the Supabase SQL Editor
6. Click **Run** (or Ctrl+Enter)
7. Checkpoint:
   - You should see **Success** (some “already exists” notices are OK if you re-run)
   - Left sidebar → **Table Editor** → you should see tables such as:
     - `prospects`
     - `workspaces`
     - `sequences`
     - `assets`
     - `notifications`
     - `suppressions`
     - `replies`
     - `prospect_activities`

## 1.4 Enable email login
1. Left sidebar → **Authentication** → **Providers**
2. Open **Email**
3. Ensure **Enable Email provider** is ON
4. For local testing, you may turn **Confirm email** OFF (so you can log in immediately without clicking a link)
5. Save

**Checkpoint Phase 1:** Tables visible + Email auth enabled + URL and service_role key saved.

---

# PHASE 2 — Gmail sending password

## 2.1 Turn on 2-Step Verification
1. Go to https://myaccount.google.com/security
2. Under **How you sign in to Google** → **2-Step Verification** → turn ON and finish setup

## 2.2 Create App Password
1. Same Security page → search **App passwords**  
   Direct: https://myaccount.google.com/apppasswords
2. App: **Mail** / Device: **Other** → name it `RuffNeck`
3. Click **Generate**
4. Copy the **16-character** password (spaces optional)
5. This is `SMTP_PASS` — **not** your normal Gmail password

**Checkpoint Phase 2:** You have Gmail address + 16-char app password.

---

# PHASE 3 — Project files and `.env`

## 3.1 Unzip the project
1. Unzip `ruffneck-prospector-v1.9.17-free.zip` (or your latest zip)
2. You should see a folder:
   ```
   ruffneck-prospector/
     backend/
     frontend/
     database/
     chrome-extension/
     scripts/
     .env.example
     docker-compose.yml
     SETUP_FROM_ZERO.md
     STEP_BY_STEP_IMPLEMENTATION.md
   ```
3. Open a terminal **inside** `ruffneck-prospector/`:
   ```bash
   cd path/to/ruffneck-prospector
   ```

## 3.2 Create `.env`
```bash
# Mac/Linux
cp .env.example .env

# Windows (Command Prompt)
copy .env.example .env
```

## 3.3 Edit `.env` (use Notepad, VS Code, or nano)

Minimum required lines (fill with YOUR values):

```bash
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_KEY=eyJhbGciOi...YOUR_SERVICE_ROLE_KEY...

REDIS_URL=redis://redis:6379/0
# If running Redis on your machine without Docker, use:
# REDIS_URL=redis://localhost:6379/0

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=youremail@gmail.com
SMTP_PASS=abcd efgh ijkl mnop
FROM_NAME=RuffNeck Prospector
FROM_EMAIL=youremail@gmail.com

# Optional but recommended for better PDFs
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
```

Notes:
- For **Docker Compose**, keep `REDIS_URL=redis://redis:6379/0` (service name `redis`).
- For **manual** install, use `redis://localhost:6379/0`.
- Do not commit `.env` to public GitHub.

**Checkpoint Phase 3:** `.env` exists with real Supabase + SMTP values.

---

# PHASE 4A — Start with Docker

> Skip to Phase 4B if you are not using Docker.

## 4.1 Fix Redis URL for Docker
In `.env`:
```bash
REDIS_URL=redis://redis:6379/0
```

## 4.2 Start core services
From `ruffneck-prospector/`:
```bash
docker compose up -d --build redis backend worker
```

Wait 1–2 minutes on first build.

## 4.3 Check API is alive
Browser or terminal:
```bash
curl http://localhost:8000/health
```
Expected: JSON with `"status": "ok"` (or similar).

API docs: http://localhost:8000/docs

## 4.4 Start frontend (often outside Compose in this package)
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Windows PowerShell for env file:
```powershell
cd frontend
npm install
Set-Content -Path .env.local -Value "NEXT_PUBLIC_API_URL=http://localhost:8000"
npm run dev
```

Open: **http://localhost:3000**

## 4.5 Optional: Celery Beat (scheduled sends + reply checks)
If your `docker-compose.yml` has a `beat` service and it starts cleanly:
```bash
docker compose up -d beat
```
If Beat fails (depends on wrong service name), use **cron** later or run Beat manually on the host (Phase 4B step for Beat).

**Checkpoint Phase 4A:**
- http://localhost:8000/health works  
- http://localhost:3000 loads the RuffNeck UI  

---

# PHASE 4B — Start manually (no Docker)

## 4.1 Redis
```bash
redis-cli ping
# PONG
```
If not running, start Redis (see Phase 0).

## 4.2 Python backend
```bash
cd ruffneck-prospector/backend
python3 -m venv .venv

# Mac/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

Optional (LinkedIn/browser scrapers):
```bash
playwright install chromium
```

Ensure project root `.env` is readable. From `backend/` you can also:
```bash
# Mac/Linux
export $(grep -v '^#' ../.env | xargs)
```
Or run from project root with dotenv (app already loads `.env` if present).

Copy env next to backend if needed:
```bash
cp ../.env .env
```

Set Redis for local:
```bash
# in .env
REDIS_URL=redis://localhost:6379/0
```

**Terminal 1 — API:**
```bash
cd ruffneck-prospector/backend
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Worker:**
```bash
cd ruffneck-prospector/backend
source .venv/bin/activate
celery -A app.tasks worker --loglevel=info
```
If that fails, try:
```bash
celery -A app.tasks.celery_app worker --loglevel=info
```

**Terminal 3 — Beat (scheduler):**
```bash
cd ruffneck-prospector/backend
source .venv/bin/activate
celery -A app.tasks beat --loglevel=info
```

## 4.3 Frontend
**Terminal 4:**
```bash
cd ruffneck-prospector/frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Open **http://localhost:3000**

**Checkpoint Phase 4B:** Same as 4A — health + UI.

---

# PHASE 5 — First login and demo data

## 5.1 Sign up
1. Open http://localhost:3000/signup  
2. Enter name, email, password (min 6 characters)  
3. Submit  
4. If it says “confirm email”, either:
   - Check inbox, or  
   - In Supabase turn off **Confirm email**, then sign up again / login  

## 5.2 Log in
http://localhost:3000/login

## 5.3 Load demo data
1. On home, click **Load demo data**  
   OR go to **Pipeline** → **Load demo**
2. Wait for the alert: loaded N prospects  
3. Open **Pipeline**

**Checkpoint Phase 5:** You see cards in columns (New, Contacted, Replied, etc.). On a phone-width screen you see stage pills.

If empty:
- API not running → start backend  
- Supabase key wrong → fix `.env`, restart backend  
- Schema not applied → re-run `schema.sql`  
- Browser console / Network tab: failed calls to `localhost:8000`

---

# PHASE 6 — Core features smoke test

Do these in order; each should work with demo data.

## 6.1 Prospects
1. Open **Prospects**  
2. You should see a table of leads  
3. Click **Verify Emails** (optional)  
4. Click **Export to Excel** → a file downloads  

## 6.2 Pipeline actions
On any card:
1. Move stage with **→ contacted** (or similar)  
2. **Timeline** → may be empty until activity exists  
3. **Assign** → type your name/email  
4. **Guide** → fill/adjust form → **Generate & download PDF**  
5. **Audit** → works best if prospect has a website URL; demo Maps leads may need a real URL  

## 6.3 Sequences
1. **Sequences** → **Seed Default Sequence**  
2. Back to **Prospects** → **Enroll in Sequence…** → pick the default  
3. **Sequences** → **Process Due Steps (sends emails)**  
4. Check Gmail **Sent** folder (only works if SMTP is correct)  

If send skipped: read API logs for “SMTP not configured”.

## 6.4 Check replies
1. Pipeline or Sequences → **Check Replies** / **Check Inbox for Replies**  
2. Requires same Gmail App Password (IMAP)

## 6.5 Create documents
1. **Create** → **Digital Ebook** → enter a title → generate PDF  
2. **Create** → **Implementation Guide** → business name + notes → PDF  
3. **Create** → **Website Audit** → `https://example.com` → PDF  
4. **Assets** → see saved files → **Download** / **Email PDF**

## 6.6 Workspace
1. **Team** → create workspace “My Agency”  
2. Header **Workspace** switcher → select it  
3. New discoveries will tag that workspace when supported  

**Checkpoint Phase 6:** At least: demo pipeline visible, one PDF downloaded, enroll sequence UI works. Email send if SMTP is set.

---

# PHASE 7 — Real discovery (optional same day)

1. **Discover** → **Google Maps** or **Any Product/Service**  
2. Enter something real (e.g. product `plumber`, location your city)  
3. Submit and wait (worker must be running)  
4. Refresh **Prospects**  

If nothing appears:
- Worker not running (most common)
- Free search returned few results — try broader keywords  
- Rate limit — wait a minute and retry  

---

# PHASE 8 — Chrome extension (optional)

1. Chrome → `chrome://extensions`  
2. Enable **Developer mode**  
3. **Load unpacked** → select folder:
   ```
   ruffneck-prospector/chrome-extension
   ```
4. Pin the extension  
5. Open a public LinkedIn profile or Google Maps business  
6. Click extension → set API URL `http://localhost:8000` → **Capture**  
7. Check **Prospects**

---

# PHASE 9 — Daily use routine

**Every morning (or automated):**
1. Discover / Daily discovery  
2. Auto-enrich + Verify emails  
3. Enroll good leads in sequence  
4. Process due steps (or rely on Beat)  
5. Check replies  
6. For hot leads: Guide or Audit → Email PDF  

**Automation without Beat:**
```bash
# crontab -e  (Mac/Linux)
*/30 * * * * curl -s -X POST http://localhost:8000/api/sequences/process
*/20 * * * * curl -s -X POST http://localhost:8000/api/replies/check
```

---

# TROUBLESHOOTING MAP

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Page loads but no data | API down or wrong `NEXT_PUBLIC_API_URL` | Start API; set `.env.local` to `http://localhost:8000`; restart `npm run dev` |
| CORS errors in browser | API not running / wrong origin | Confirm API on 8000; restart backend |
| Signup fails | Email confirm required / auth disabled | Supabase Auth → Email → disable confirm for dev |
| “Invalid API key” | Used `anon` key | Put **service_role** in `SUPABASE_KEY` |
| Tables missing | Schema not run | Re-run `database/schema.sql` |
| Demo seed fails | API/DB connection | Test `/health`; check Supabase URL/key |
| Scrape/discover never finishes | Worker not running | Start Celery worker |
| Emails not sending | Wrong password | Gmail **App Password**, not account password |
| PDF generates empty/simple | No Groq key | Optional: add `GROQ_API_KEY`; templates still work |
| Port 8000 in use | Another app | Stop other process or change port |
| Docker build fails | Docker not running | Start Docker Desktop |
| `celery` command not found | venv not activated | `source .venv/bin/activate` then retry |

---

# ORDER CHEAT SHEET

```
1. Install Docker OR Python+Node+Redis
2. Create Supabase → run schema.sql → enable Email auth
3. Create Gmail App Password
4. Unzip project → copy .env.example to .env → fill keys
5. Start Redis + API + Worker (+ Beat)
6. Start frontend (npm run dev)
7. Sign up → Load demo data → open Pipeline
8. Test Sequences SMTP + Create PDF + Assets
9. Run one real Discover
10. Optional: Chrome extension
```

You are **fully implemented** when:
- [ ] http://localhost:3000 works  
- [ ] Demo pipeline shows cards  
- [ ] Worker processes tasks  
- [ ] One PDF downloads  
- [ ] One test email sends (SMTP)  

Stop there and use the product for a week before changing more code.
