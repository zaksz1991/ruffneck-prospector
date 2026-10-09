# RuffNeck Prospector v1.4 — 100% Free

Ultimate free multi-platform lead engine with one-click Daily Discovery, live status tracking, and setup wizard.

## Highlights
- **One-click “Run Daily Discovery”** – automatically searches all 6 services + LinkedIn + free job boards + optional Maps
- **Live task status** – frontend polls Celery and shows PENDING → SUCCESS/FAILURE with results summary
- **Setup wizard** – `python scripts/setup_wizard.py` walks you through free keys and Playwright
- LinkedIn, expanded job boards (RemoteOK, Remotive, Arbeitnow, Jobicy…), smarter Maps filters
- Multi-signal AI scoring, free email enrichment, Gmail sequences, local PDF/PPTX

## Platforms
linkedin • jobs • maps • google • instagram • twitter • reddit • youtube • tiktok • facebook

## Fastest start
```bash
# 1. Wizard (creates .env)
python scripts/setup_wizard.py

# 2. Database
# → Supabase SQL Editor → run database/schema.sql

# 3. Backend
cd backend
pip install -r requirements.txt
playwright install chromium   # if not done by wizard
uvicorn app.main:app --reload --port 8000
# other terminal:
celery -A app.tasks.celery_app worker --loglevel=info

# 4. Frontend
cd frontend && npm i && npm run dev
```
Open http://localhost:3000/discover → click **🚀 Run Daily Discovery**

## Key endpoints
- `POST /api/discover/daily` – one-click daily run
- `GET  /api/tasks/{task_id}` – status tracking
- `POST /api/discover/leads` – single service intent
- `POST /api/prospects/search` – any platform
- `POST /api/prospects/enrich` – free email enrichment

**$0 required.** MIT 2026

## Team / Shared Workspaces (v1.7)
- Create workspaces and invite members by email
- Assign prospects to a workspace for a shared pipeline
- `/team` page for management
- Run the latest `database/schema.sql` additions for `workspaces` and `workspace_members` tables

## Auth (v1.9)
- Supabase Auth powered signup / login
- Pages: `/login`, `/signup`
- Tokens stored in localStorage (`ruffneck_token`)
- Endpoints: `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/me`
- Enable Email auth in your Supabase project (Authentication → Providers → Email)
- For production, add RLS policies using `auth.uid()` and workspace membership

## Row Level Security (v1.9.1)
Basic RLS policies are included at the bottom of `database/schema.sql`.

**Important behavior:**
- Backend using **service_role** key bypasses RLS (Celery + FastAPI continue to work as before)
- Users authenticated via Supabase Auth only see:
  - Prospects / sequences in workspaces they belong to
  - Rows where `workspace_id IS NULL` (legacy / personal)
- `is_workspace_member()` helper checks membership by `user_id` or email

**To apply:**
1. Run the full (or new) section of `database/schema.sql` in Supabase SQL Editor
2. Keep using service_role key in backend `.env` for server-side jobs
3. For browser → Supabase direct calls, use anon key + user JWT

**Testing RLS:**
- Create two users
- Create a workspace and invite only user A
- Confirm user B cannot see that workspace’s prospects when querying with their JWT

## Any product or service demand (v1.9.4)
RuffNeck can find people who need **any** product or service online, not only digital services.

- Discover → **Any Product/Service** tab: type e.g. "solar panels", "wedding photographer", "tutors"
- Service Intent also includes: general demand, buying intent, hiring, local services, B2B, coaching, health, education, home, events, finance/legal
- API: `POST /api/discover/product-demand` with `{ "product_or_service": "...", "location": "..." }`
- Free search intent patterns: looking for / need a / recommend / where can I buy / anyone know

## Competitor / Lookalike discovery (v1.9.5)
- Discover → **Competitors / Lookalikes** tab
- Seed: company name or website (e.g. hubspot.com)
- Optional location + category for local Maps lookalikes
- Free methods: Google `related:`, "alternatives to", "competitors of", category search
- API: `POST /api/discover/competitors` `{ "seed": "acme.com", "location": "Lagos", "category": "agency" }`
- Leads tagged `competitor` / `lookalike` and flow into enrichment + pipeline

## Auto reply detection + Activity timeline (v1.9.6)
- Gmail IMAP reply polling: `POST /api/replies/check` (uses SMTP_USER + SMTP_PASS App Password)
- Matches replies to prospects by email → auto stage update, pause sequences, log activity
- `prospect_activities` table + `GET /api/prospects/{id}/activities`
- Pipeline: **Check Replies** button + **Timeline** on each card
- Sequences: **Check Inbox for Replies** button
- Activity logged on: sequence send, manual reply, auto-detected reply

Enable IMAP for Gmail: Google Account → Security → App Passwords (same as SMTP).
Schedule: run Celery task `check_replies` every 15–30 min via Beat/cron.

## Suppression list (v1.9.7)
- Table `suppressions` – emails that must never receive sequence mail
- Sequence processor skips suppressed addresses
- Auto-add when reply contains STOP / UNSUBSCRIBE / remove me (manual or IMAP)
- Sequence emails include opt-out footer
- API: GET/POST `/api/suppressions`, DELETE `/api/suppressions/{email}`
- UI: Sequences page → Suppression list

## Scheduling & lead assignment (v1.9.8)
### Celery Beat
- Config: `backend/app/celeryconfig.py`
- Sequences every 30 min, reply check every 20 min
- Start: `celery -A app.tasks beat --loglevel=info`
- Optional daily discovery cron entry (commented in config)

### Cron alternative
```bash
*/30 * * * * API_URL=http://localhost:8000 ./scripts/cron_recipes.sh sequences
*/20 * * * * API_URL=http://localhost:8000 ./scripts/cron_recipes.sh replies
0 8 * * *   API_URL=http://localhost:8000 ./scripts/cron_recipes.sh daily
```

### Assign leads
- Pipeline card → **Assign** → enter teammate name/email
- Column `prospects.assigned_to`
- API: `POST /api/prospects/assign` `{ "prospect_ids": ["..."], "assigned_to": "alex@agency.com" }`

## Notifications + tech detection (v1.9.9)
- In-app notifications (`notifications` table) for positive replies and high-score leads
- Bell icon in header; mark all read
- API: `GET /api/notifications`, `POST /api/notifications/read`
- Free website tech detection (WordPress, Wix, Shopify, etc.) + pitch hints
- Auto-runs on Maps/Google/competitor inserts when a URL exists
- Manual: `POST /api/prospects/{id}/detect-tech` or `POST /api/tech/detect?url=`

## Auth hardening + rate limits (v1.9.10)
- `frontend/lib/api.ts` – `apiFetch()` attaches Bearer token from login
- Prospects + Pipeline pages use `apiFetch` for API calls
- In-memory rate limits on discover/search/sequences/replies/tech (per IP)
- Prospects table: **Tech** action runs website stack detection
- Dashboard: Logout clears session

## v1.9.11
- Remaining UI pages use `apiFetch` (Discover, Sequences, Analytics, Team, Notifications)
- `PRODUCTION.md` – deploy guide (Docker, bare metal, TLS, security checklist)
- `scripts/smoke_test.sh` – quick API health check

## Create: Ebooks & Implementation Guides (v1.9.12)
- **Create** page (`/create`)
- **Branded ebook PDF**: type a title (+ subtitle, brand, accent color) → download full PDF
- **Implementation guide**: enter post-consultation business details → step-by-step PDF plan
- APIs: `POST /api/generate/ebook`, `POST /api/generate/implementation-guide` (return PDF file)
- Content: Groq free tier if `GROQ_API_KEY` set; otherwise solid templates

## Asset library + Guide from prospect (v1.9.13)
- Generated ebooks/guides saved under `backend/storage/assets` + `assets` table
- **Assets** page (`/assets`) – list/filter/download
- API: `GET /api/assets`, `GET /api/assets/{id}/download`
- Pipeline card → **Guide** – prefilled implementation guide from prospect → PDF + linked asset

## Email PDF assets (v1.9.14)
- `POST /api/assets/{id}/send` – email saved PDF via Gmail SMTP (attachment)
- Assets page → **Email PDF** (prompt for address or use linked prospect)
- Pipeline → Guide → after generate, optional "Email PDF to prospect"
- Respects suppression list; logs activity + moves stage to contacted

## Demo seed data (v1.9.15)
- `POST /api/demo/seed` – loads 8 sample prospects (maps, LinkedIn, jobs, demand, competitors)
- `DELETE /api/demo/seed` – removes demo rows only (`data_source=demo_seed`)
- UI: **Load demo data** on home + **Load demo** on Pipeline
- Safe to re-run; replaces previous demo rows

## Branding & full setup (v1.9.16)
- **App title:** RuffNeck Prospector
- Icons: `frontend/public/favicon.svg`, `icon-192.svg`, `logo.svg`, `site.webmanifest`
- Next.js metadata + theme color `#1e3a5f`
- **Start-to-finish guide:** [SETUP_FROM_ZERO.md](./SETUP_FROM_ZERO.md)
