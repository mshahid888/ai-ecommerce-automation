# DEPLOYMENT.md — Public demo go-live guide

**Status (Phase 8, 2026-10-09):** all deployment CONFIGS are prepared and
committed. **Nothing is deployed yet.** There is no public URL. Go-live
requires Shahid's auth steps (see §8 — his exact checklist).

## 1. Target architecture

```
Visitor (browser)
   │  HTTPS
   ▼
Vercel (frontend, Next.js) ──► https://<backend-domain> (nginx, Hetzner)
        NEXT_PUBLIC_API_URL          │  reverse proxy → 127.0.0.1:8000
  (baked in at build time)          ▼
                            systemd → uvicorn (2 workers) → FastAPI app
                                                             │ SQLite (data/demo.db)
                                                             │ LLM_PROVIDER=mock (default)
```

Costs: **€0/month incremental** — Vercel free tier, existing Hetzner server,
SQLite, mock provider. Optional future: domain ≈ €12/yr. No paid service is
introduced by this guide.

## 2. Prerequisites

| # | Item | Status |
|---|---|---|
| 1 | Repo `mshahid888/ai-ecommerce-automation` on GitHub | ❌ NOT created — needs Shahid (see docs/GITHUB-SETUP.md) |
| 2 | Hetzner server access (`deploy@2.28.53.174`) from a machine Shahid controls | ❌ deploy key missing on this VM — needs Shahid |
| 3 | Vercel account connected to Shahid's GitHub | ❌ needs Shahid (OAuth) |
| 4 | Backend domain (e.g. `api-demo.example.com`) + DNS A-record → Hetzner IP + HTTPS cert (certbot) | ❌ needs Shahid |
| 5 | Real AI provider in demo | Not required — `LLM_PROVIDER=mock` default is zero-cost and deterministic |

## 3. Backend on Hetzner (step by step)

Assumes Ubuntu/Debian with nginx installed and Python 3.12 available.
Replace `/srv/ai-ecommerce-automation` if you prefer another path.

```bash
# 1. Clone
sudo mkdir -p /srv && sudo chown deploy:deploy /srv
git clone https://github.com/mshahid888/ai-ecommerce-automation.git /srv/ai-ecommerce-automation
cd /srv/ai-ecommerce-automation/backend

# 2. Virtualenv + deps
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Environment (REQUIRED: generate ADMIN_API_KEY)
cp .env.production.example .env.production
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # paste as ADMIN_API_KEY
nano .env.production   # fill: ADMIN_API_KEY, CORS_ORIGINS=<your vercel domain>
chmod 600 .env.production

# 4. Sanity boot (local bind only)
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
# in another shell:
curl -s http://127.0.0.1:8000/health
# stop with Ctrl-C when /health is ok
```

### 3.1 systemd (recommended)

```bash
sudo cp deploy/ecommerce-demo.service /etc/systemd/system/
sudo nano /etc/systemd/system/ecommerce-demo.service   # adjust paths/user if needed
sudo systemd-analyze verify /etc/systemd/system/ecommerce-demo.service
sudo systemctl daemon-reload
sudo systemctl enable --now ecommerce-demo.service
sudo systemctl status ecommerce-demo.service
journalctl -u ecommerce-demo.service -f   # watch startup; look for "Application startup complete"
curl -s http://127.0.0.1:8000/health
```

Notes:
- The unit runs `uvicorn --workers 2 --proxy-headers`. `--proxy-headers` is
  required so the app's per-IP rate limiter sees real client IPs behind nginx.
  It is safe only because the app binds 127.0.0.1.
- With 2 workers the in-memory rate limiter is per-worker (limits are
  approximate per worker). Acceptable for the demo; documented in
  docs/SECURITY.md §6.
- Alternative: gunicorn (`deploy/gunicorn.conf.py`) — add `gunicorn` to
  requirements on the server first, then:
  `.venv/bin/gunicorn -c deploy/gunicorn.conf.py app.main:app`
  Run either systemd+uvicorn OR gunicorn, not both.

### 3.2 nginx reverse proxy (example config)

```bash
sudo cp deploy/nginx-example.conf /etc/nginx/sites-available/ecommerce-demo
sudo nano /etc/nginx/sites-available/ecommerce-demo   # <<< REPLACE server_name + cert paths
sudo ln -s /etc/nginx/sites-available/ecommerce-demo /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
curl -s https://<your-backend-domain>/health
```

Caveats baked into the example config:
- Per-IP connection throttling (`limit_req`) at the edge complements the app
  limiter.
- `proxy_set_header X-Forwarded-For` + uvicorn `--proxy-headers` keeps
  per-IP rate limiting truthful.
- `proxy_read_timeout 60s` > `LLM_TIMEOUT_SECONDS` (default 15).

## 4. Frontend on Vercel (step by step)

1. Sign in to Vercel with GitHub as **mshahid888**, click **Add New → Project**,
   **Import** `mshahid888/ai-ecommerce-automation`.
2. Root Directory: leave at repo root — Vercel detects Next.js in `frontend/`?
   ⚠️ The repo is a monorepo. Set **Root Directory = `frontend`** in the
   project settings (Build & Development Settings). The included
   `frontend/vercel.json` pins build/install/output commands.
3. Environment Variables (Production): add
   `NEXT_PUBLIC_API_URL = https://<your-backend-domain>`
   (no trailing slash). This is baked in at build time — set it BEFORE the
   first deploy.
4. Click **Deploy**. When it turns green, open the URL and check:
   - landing/chat page renders with the demo banner,
   - typing "Wo bleibt meine Bestellung #10482?" returns a grounded answer,
   - the workflow timeline shows real events,
   - `/dashboard` loads with demo counts.

## 5. Verification checklist (run after both halves are up)

```bash
# Backend direct
curl -s http://127.0.0.1:8000/health
# Backend through nginx/TLS
curl -s https://<backend-domain>/health
# One chat call (mock provider — deterministic, free)
curl -s -X POST https://<backend-domain>/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Wo bleibt meine Bestellung #10482?"}' | head -c 400
# CORS check: origin must be your Vercel domain
curl -s -o /dev/null -w '%{http_code}' https://<backend-domain>/api/ops/summary \
  -H 'Origin: https://<vercel-domain>'
# Abuse spot-checks (expect 400 / 401 / 429 in German)
curl -s -X POST https://<backend-domain>/api/demo/reset -w '\n%{http_code}\n'   # expect 401
```

Browser checklist:
- [ ] Chat answers order #10482 from real demo data (status: versandt, DHL).
- [ ] Product question answered only from the catalog; missing info → honest
      "not available" + escalation offer.
- [ ] Return request walks through info-gathering → policy check → ticket.
- [ ] Timeline events match executed backend operations (no phantom events).
- [ ] Reset button works only with the admin key; demo data restores.
- [ ] Mobile layout renders (responsive check).
- [ ] Demo indicator ("Demo", fictional data) visible on every page.

## 6. Rollback

Backend (systemd):
```bash
sudo systemctl stop ecommerce-demo.service
cd /srv/ai-ecommerce-automation
git log --oneline -5                     # pick the previous known-good commit
git checkout <previous-commit>          # detached HEAD — deliberate, see below
sudo systemctl start ecommerce-demo.service
curl -s http://127.0.0.1:8000/health
```
To return to the newest code: `git checkout main && git pull && sudo systemctl restart ecommerce-demo.service`.

Frontend (Vercel): Dashboard → Deployments → select the previous green
deployment → **⋯ → Promote to Production** (instant rollback, no rebuild).

## 7. Secret management

- All secrets live in server-side env (`/srv/ai-ecommerce-automation/backend/.env.production`, mode 0600).
  Root `.gitignore` excludes `.env*` — the `.example` templates are the only
  env files committed, and they contain NO real values.
- `ADMIN_API_KEY`: generate with `secrets.token_urlsafe(32)`; set as env var
  in production (preferred over the auto-generated `data/.admin_key` file,
  which is a fallback for local dev only).
- LLM keys: never in frontend code; only via backend env. The demo ships with
  `LLM_PROVIDER=mock` so no key is needed at all.
- Before every release: `git diff --cached | grep -iE 'key|token|secret|password'` must return nothing real.

## 8. Shahid's exact action checklist (nothing assumed)

- [ ] **A.** Create the GitHub repo (github.com/new or Mac terminal):
      name `ai-ecommerce-automation`, public — exact steps in docs/GITHUB-SETUP.md.
- [ ] **B.** Push the local project from a machine with push access (his Mac):
      `git remote add origin ssh://git@github.com/mshahid888/ai-ecommerce-automation.git`
      (Mac needs the `ssh://` form because of his global `url.insteadOf` setting),
      then `git push -u origin main`.
- [ ] **C.** Give this VM Hetzner access (deploy key) OR run the backend steps
      in §3 himself on the server.
- [ ] **D.** Register a backend domain, point DNS at the Hetzner IP, run
      certbot, and paste the real domain into `nginx-example.conf` + Vercel env.
- [ ] **E.** In `.env.production` on the server: generate + set `ADMIN_API_KEY`,
      set `CORS_ORIGINS` to the real Vercel domain only.
- [ ] **F.** Vercel: import the repo (Root Directory `frontend`), set
      `NEXT_PUBLIC_API_URL` (Production) to the backend domain, deploy.
- [ ] **G.** Run the verification checklist in §5 (health, chat smoke test,
      dashboard, 401 on unauthenticated reset).
- [ ] **H.** Decide the real AI provider for the demo (Gemini via existing
      credential, OpenAI-compatible key, or stay on mock).

## 9. Known Phase 8 limitations (honest)

- No public URL exists until §8 is done — do not announce one.
- In-memory rate limiter is per uvicorn worker (2 workers ≈ limits split);
  lost on restart. Fine for a demo, not for paid production.
- The GitHub `mshahid888` identity on this VM is read-only (GitHub App
  installation scope); repo creation/push from here is impossible — documented
  in docs/GITHUB-SETUP.md.
- `npm run build` was verified locally (see docs/PHASE-8-REPORT.md); the
  production Vercel build will be the first build against the real backend URL.
- Security baseline is a demo baseline — see docs/SECURITY.md §1 "Explizit
  NICHT geschützt". Not certified for real customer data.
