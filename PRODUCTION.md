# RuffNeck Prospector – Production Deploy Guide

100% free-stack deployment for a small team (VPS or home server).

## 1. Requirements

- Docker + Docker Compose **or** Node 18+, Python 3.11+, Redis
- Free Supabase project (Postgres + Auth)
- Gmail account with App Password (SMTP + IMAP)
- Domain (optional) + Caddy/Nginx for HTTPS

## 2. Supabase

1. Create a project at https://supabase.com
2. Run `database/schema.sql` in the SQL Editor (full file)
3. Authentication → Providers → enable **Email**
4. Copy:
   - Project URL → `SUPABASE_URL`
   - `service_role` key → `SUPABASE_KEY` (backend only; never expose to browser)

## 3. Environment

Copy `.env.example` → `.env`:

```bash
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=eyJ...service_role...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=your_app_password
FROM_NAME=Your Agency
FROM_EMAIL=you@gmail.com
# Optional free enrichment
HUNTER_API_KEY=
# Optional Google CSE
GOOGLE_CSE_API_KEY=
GOOGLE_CSE_CX=
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
REDIS_URL=redis://redis:6379/0
```

## 4. Docker Compose (recommended)

```bash
docker compose up -d --build
```

Typical services: `api`, `worker`, `beat`, `redis`, `frontend`.

- API: port 8000  
- Frontend: port 3000  
- Beat: schedules sequences + reply checks  

## 5. Without Docker

```bash
# Redis
redis-server

# API
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Worker
celery -A app.tasks worker --loglevel=info

# Beat
celery -A app.tasks beat --loglevel=info

# Frontend
cd frontend && npm i && npm run build && npm start
```

## 6. Cron alternative (no Beat)

```bash
*/30 * * * * API_URL=https://api.yourdomain.com ./scripts/cron_recipes.sh sequences
*/20 * * * * API_URL=https://api.yourdomain.com ./scripts/cron_recipes.sh replies
0 8 * * *   API_URL=https://api.yourdomain.com ./scripts/cron_recipes.sh daily
```

## 7. HTTPS reverse proxy (Caddy example)

```
api.yourdomain.com {
  reverse_proxy localhost:8000
}
app.yourdomain.com {
  reverse_proxy localhost:3000
}
```

Set `NEXT_PUBLIC_API_URL=https://api.yourdomain.com` before building the frontend.

## 8. Security checklist

- [ ] Backend uses **service_role** key only on server
- [ ] RLS policies applied (schema.sql)
- [ ] Gmail App Password (not account password)
- [ ] Rate limits enabled (built-in)
- [ ] Suppression list in use for outbound
- [ ] Change default CORS origins from `*` when you have a fixed domain

## 9. Smoke test

```bash
./scripts/smoke_test.sh http://localhost:8000
```

## 10. First-run workflow

1. Open app → Sign up / Log in  
2. Team → create workspace → set active workspace  
3. Sequences → Seed Default Sequence  
4. Discover → run Daily or Competitors / Product demand  
5. Prospects → Verify Emails → Enroll in Sequence  
6. Ensure Beat/cron running for sends + reply checks  
