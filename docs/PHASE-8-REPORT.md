# Phase 8 Report — Public demo deployment PREPARATION

**Date:** 2026-10-09 · **Commit:** (this phase) · **Status:** configs committed & verified locally. **Nothing deployed — there is no public URL.**

Phase 8 was scoped as preparation only: go-live needs Shahid's auth steps
(GitHub repo creation/push, Vercel connect, Hetzner backend, DNS+TLS), none
of which were available from this VM.

## 1. GitHub push — ATTEMPTED, blocked (documented)

- Re-attempted repo creation via the connected `github` CLI
  (`create_repository`, name `ai-ecommerce-automation`, public).
- Result: **403 `Resource not accessible by integration`** — identical to the
  Phase 1 attempt. The Muse GitHub-App installation is scoped to selected
  repositories and cannot create repos under `mshahid888`.
- `gh` on this VM is not logged in (`gh auth login` needs Shahid's
  interactive sign-in); no auth workaround was attempted, per scope.
- `docs/GITHUB-SETUP.md` updated with the Phase 8 attempt record, the local
  commit count, and the exact manual steps from his Mac (incl. the
  `ssh://git@github.com/...` remote form his global `url.insteadOf` requires).

## 2. Files added/changed (this phase)

| File | Purpose |
|---|---|
| `backend/deploy/ecommerce-demo.service` | systemd unit: uvicorn, 2 workers, bind 127.0.0.1:8000, `EnvironmentFile`, `--proxy-headers`, hardening flags |
| `backend/deploy/gunicorn.conf.py` | alternative process manager (2 UvicornWorkers, timeouts, `forwarded_allow_ips`) — add `gunicorn` to requirements if used |
| `backend/deploy/nginx-example.conf` | EXAMPLE nginx server block (marked as example): TLS, reverse proxy, edge rate-limit zone, security headers, real-IP forwarding |
| `backend/.env.production.example` | every backend env var documented (ADMIN_API_KEY, LLM_*, rate limits, CORS narrow note, DATABASE_URL, DEMO_MODE) — no real values |
| `frontend/vercel.json` | build/install/output commands; notes that `NEXT_PUBLIC_API_URL` must be set in the Vercel dashboard (build-time inlined) |
| `frontend/.env.production.example` | single frontend var documented |
| `frontend/.gitignore` | negation rules so committed env *templates* (`.env.example`, `.env.production.example`) are tracked; real `.env` files stay ignored |
| `docs/DEPLOYMENT.md` | full go-live guide: architecture, prerequisites, Hetzner backend steps, systemd, nginx, Vercel steps (Root Directory `frontend`), verification checklist, rollback, secret management, €0 cost table, **Shahid's exact action checklist**, honest limitations |
| `docs/GITHUB-SETUP.md` | Phase 8 attempt outcome recorded |
| `docs/PHASE-8-REPORT.md` | this file |

## 3. Verification results

- **Frontend:** `npm run build` with `NEXT_PUBLIC_API_URL=https://api-demo.example.com`
  → ✅ Compiled successfully (Next.js 16.4.0/Turbopack), TypeScript passed, all 7 routes generated (`/`, `/dashboard`, `/tickets`, `/tickets/[id]`).
- **Backend (production-like env, port 8125, fresh /tmp DB):**
  - `ADMIN_API_KEY` set, `CORS_ORIGINS=https://ai-ecommerce-automation.vercel.app`, `RATE_LIMIT_ENABLED=true`, `LLM_PROVIDER=mock`.
  - `GET /health` → 200 ✅
  - `POST /api/chat` "Wo bleibt meine Bestellung #10482?" → `order_status`, confidence 0.96, grounded German reply (DHL, DEMO-TRK-10482, demo-labeled) ✅
  - unknown order `#99999` → honest "nicht gefunden" + escalation offer ✅
  - `POST /api/demo/reset` without key → 401 ✅
  - `GET /api/dashboard/summary` → real counts (2 conversations, intents breakdown) ✅
  - `GET /api/events` → real workflow events with German labels ✅
  - CORS: evil origin gets no `access-control-allow-origin`; Vercel origin gets exactly its origin ✅
- **systemd:** `systemd-analyze verify` parses the unit cleanly; the only diagnostic is that `/srv/...` paths don't exist *on this VM* (expected — they target the Hetzner server). Syntax valid.
- **nginx:** no nginx on this VM for `-t`; the example block is syntax-checked by reading and follows standard directives; validation step is documented in DEPLOYMENT.md §3.2 (`nginx -t` on the server).
- **Tests:** full backend suite re-run → **86/86 passed** ✅
- **Secret scan:** only hits are `secrets.token_urlsafe(32)` key-*generation* instructions in docs/templates — no real secrets in any new file. Root `.gitignore` excludes `.env*`/`.admin_key`/`*.db`; only `.example` templates are committed.

## 4. Known limitations / caveats

- No public URL exists; do not claim one. Everything above was verified on localhost-equivalent conditions.
- In-memory rate limiter is per uvicorn worker (2 workers ≈ limits split); lost on restart. Fine for the demo.
- The GitHub identity on this VM remains read-only; push still needs Shahid (docs/GITHUB-SETUP.md).

## 5. Shahid's remaining actions for go-live (see docs/DEPLOYMENT.md §8)

1. Create repo `mshahid888/ai-ecommerce-automation` (public) + push from his Mac.
2. Give this VM the Hetzner deploy key (or run backend steps on the server himself).
3. Register backend domain, point DNS at Hetzner IP, run certbot.
4. On the server: set `ADMIN_API_KEY` (generated), narrow `CORS_ORIGINS` to the Vercel domain.
5. Vercel: import repo (Root Directory `frontend`), set `NEXT_PUBLIC_API_URL`, deploy.
6. Run DEPLOYMENT.md §5 verification checklist.
7. Decide the real AI provider for the demo (or keep mock).

## 6. Costs

€0/month incremental (Vercel free, existing Hetzner, SQLite, mock LLM). Optional domain ≈ €12/yr.
