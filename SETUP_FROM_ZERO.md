# RuffNeck Prospector — Start to Finish Setup Guide

**Web app title:** RuffNeck Prospector  
**Short name:** RuffNeck  
**Icons:** `/favicon.svg`, `/icon-192.svg`, `/logo.svg` (in `frontend/public/`)

This guide takes you from an empty machine to a working system: discovery → pipeline → email → PDFs.

---

## Part A — Accounts (all free)

### 1. Supabase (database + auth)
1. Go to [https://supabase.com](https://supabase.com) and create a project.
2. Wait until the database is ready.
3. **Project Settings → API**
   - Copy **Project URL** → `SUPABASE_URL`
   - Copy **service_role** key → `SUPABASE_KEY` (server only; never put this in the browser)
4. **SQL Editor → New query**  
   Paste the full contents of `database/schema.sql` → **Run**.
5. **Authentication → Providers → Email** → Enable.

### 2. Gmail App Password (send + reply detection)
1. Google Account → **Security** → enable **2-Step Verification**.
2. **App passwords** → create one for “Mail”.
3. Copy the 16-character password → `SMTP_PASS`  
   Your Gmail address → `SMTP_USER`.

### 3. Optional free upgrades
| Key | Purpose |
|-----|---------|
| `GROQ_API_KEY` | Richer ebook / implementation guide text ([console.groq.com](https://console.groq.com)) |
| `HUNTER_API_KEY` | Stronger email verification (free tier) |
| `GOOGLE_CSE_API_KEY` + `GOOGLE_CSE_CX` | Google Custom Search (free quota) |

---

## Part B — Install on your computer

### Requirements
- Docker Desktop **or** (Python 3.11+, Node 18+, Redis)
- Git (optional)

### Option 1 — Docker (recommended)

```bash
# 1. Unzip the package and enter the folder
cd ruffneck-prospector

# 2. Environment
cp .env.example .env
# Edit .env with SUPABASE_URL, SUPABASE_KEY, SMTP_USER, SMTP_PASS
# NEXT_PUBLIC_API_URL=http://localhost:8000

# 3. Start
docker compose up -d --build

# 4. Open
# Frontend: http://localhost:3000
# API docs:  http://localhost:8000/docs
```

### Option 2 — Manual

```bash
cd ruffneck-prospector

# Redis (Ubuntu example)
# sudo apt install redis-server && redis-server

# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Optional browsers for LinkedIn/Maps-heavy scraping:
# playwright install chromium

cp ../.env.example ../.env   # edit as above

# Terminal 1 — API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Celery worker
celery -A app.tasks worker --loglevel=info

# Terminal 3 — Celery Beat (schedules sequences + reply checks)
celery -A app.tasks beat --loglevel=info

# Frontend
cd ../frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
# Open http://localhost:3000
```

### Smoke test
```bash
./scripts/smoke_test.sh http://localhost:8000
```

---

## Part C — First-run workflow (in the app)

### 1. Create your account
1. Open **http://localhost:3000/signup**
2. Register with email/password.
3. Log in at **/login**.

### 2. Load demo data (optional but recommended)
1. Home → **Load demo data**  
   **or** Pipeline → **Load demo**
2. Open **Pipeline** — you should see sample leads in stages.

### 3. Create a workspace (teams)
1. Go to **Team**
2. Create a workspace (e.g. “My Agency”)
3. Select it in the **Workspace** switcher (header)
4. Invite teammates by email if needed

### 4. Discover real leads
1. **Discover**
2. Try one of:
   - **Daily Discovery** (location + services)
   - **Any Product/Service** (e.g. “wedding photographer”, “Lagos”)
   - **Competitors / Lookalikes** (seed domain or company name)
   - **Google Maps** (local + “no website” preference)
   - **LinkedIn / Jobs**
3. Wait for the task to finish → leads appear under **Prospects**

### 5. Enrich & verify
1. **Prospects** → **Verify Emails** / **Auto-Enrich**
2. Optional: row **Tech** button for website stack detection

### 6. Work the pipeline
1. **Pipeline** — move cards across stages  
2. **Assign** — give a lead to a teammate  
3. **Log reply** or **Check Replies** (IMAP)  
4. **Timeline** — activity history  

### 7. Sequences (email outreach)
1. **Sequences** → **Seed Default Sequence**
2. On Prospects or Pipeline → **Enroll in Sequence**
3. **Process Due Steps** (or let Celery Beat run every 30 min)
4. Configure suppression list on the Sequences page

### 8. Documents (ebooks & guides)
1. **Create**
   - **Digital Ebook** — type a title → branded PDF  
   - **Implementation Guide** — consultation fields → step-by-step PDF  
2. Or on Pipeline → **Guide** (prefilled from the prospect)
3. Files are saved under **Assets**
4. **Email PDF** to the prospect (SMTP)

### 9. Chrome capture (optional)
1. Chrome → `chrome://extensions` → Developer mode → **Load unpacked**
2. Select `chrome-extension/`
3. Open a LinkedIn profile or Google Maps place → click extension → **Capture**

---

## Part D — Daily automation

### Celery Beat (already configured)
- Sequences every **30 minutes**
- Reply check every **20 minutes**

```bash
celery -A app.tasks beat --loglevel=info
```

### Cron alternative
```bash
*/30 * * * * API_URL=http://localhost:8000 /path/to/scripts/cron_recipes.sh sequences
*/20 * * * * API_URL=http://localhost:8000 /path/to/scripts/cron_recipes.sh replies
0 8 * * *   API_URL=http://localhost:8000 /path/to/scripts/cron_recipes.sh daily
```

---

## Part E — Production checklist

See **PRODUCTION.md** for TLS, Docker, and security.

Short list:
- [ ] Full `schema.sql` applied  
- [ ] `SUPABASE_KEY` = **service_role** on server only  
- [ ] Gmail App Password set  
- [ ] `NEXT_PUBLIC_API_URL` points to public API URL  
- [ ] Worker + Beat running  
- [ ] CORS tightened from `*` when you have a fixed domain  
- [ ] Suppression list used for real outbound  

---

## App identity (use these)

| Item | Value |
|------|--------|
| **Product name** | RuffNeck Prospector |
| **Browser tab title** | RuffNeck Prospector |
| **Theme color** | `#1e3a5f` |
| **Favicon** | `frontend/public/favicon.svg` |
| **Logo wordmark** | `frontend/public/logo.svg` |
| **App icon** | `frontend/public/icon-192.svg` |
| **Manifest** | `frontend/public/site.webmanifest` |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| API errors / empty data | Check `.env` Supabase URL + **service_role** key; re-run `schema.sql` |
| Emails not sending | App Password (not normal Gmail password); allow “less secure” is obsolete — use App Passwords |
| Reply check empty | Same Gmail credentials; IMAP enabled; run **Check Replies** once manually |
| Frontend can’t reach API | `NEXT_PUBLIC_API_URL=http://localhost:8000` and restart `npm run dev` |
| Scrape returns little | Normal for free sources; try Maps + Product demand + demo seed first |
| PDF generation slow | First run may call Groq if key set; without key uses templates (faster) |

---

## Mental model (end-to-end)

```
Sign up → Workspace → Discover / Chrome capture / Demo
    → Enrich + Verify + Tech
    → Pipeline (assign, stages)
    → Enroll sequence → Beat sends mail
    → Check replies → auto-pause + notify
    → Guide / Ebook → Assets → Email PDF
    → Won / Lost
```

You are done when: demo pipeline works, one real discovery run works, and one test email + one PDF send succeed.
