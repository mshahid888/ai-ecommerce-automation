# Phase 0 — Environment Audit & Architecture Report

**Date:** 2026-10-09
**Project:** AI E-Commerce Automation Platform (working title; final brand TBD)
**Status:** Audit complete. Phase 1 authorized.

---

## 1. Available repositories (mshahid888, verified via GitHub API)

15 repos total. No ecommerce-specific repo exists. Relevant:

| Repo | Visibility | Stack | Relevance |
|---|---|---|---|
| `ai-customer-support-automation` | public | Python stdlib only, n8n | Direct predecessor — highest reuse value |
| `pdfwandler-backend2` | private | FastAPI 0.109.1 + uvicorn + gunicorn | FastAPI skeleton pattern |
| `agri-ai-adviser` | public | FastAPI + OpenAI API, pytest/httpx | FastAPI + test pattern |
| `digitalwerk` | private | Next.js + React + Tailwind (lucide-react) | Frontend stack pattern |
| `pdfwandler-frontend2` | private | Next.js pages-router + TypeScript | Frontend pattern |

**Naming check:** no repo named `ai-ecommerce-automation` exists under mshahid888 → name is free. Globally ~50 repos share the name (irrelevant — GitHub names are per-user namespaced).

## 2. Existing reusable components

From `ai-customer-support-automation` (built 2026-10-08, 70 tests, stdlib-only):

- **`src/llm.py`** — `LLMProvider` abstract base, `MockLLMProvider` (deterministic, offline, clearly labeled demo), `OpenAICompatibleProvider` (stdlib urllib, temperature=0.0), `get_provider()` factory driven by `LLM_PROVIDER` env var. Keys from env only. → **port directly into the FastAPI backend.**
- **`src/classifier.py`** — strict LLM-JSON validation (intent enum, confidence 0–1, order-id regex `^\d{3,6}$`), `ALWAYS_HUMAN` policy set, confidence < 0.60 → human, `safe_fallback()` on any invalid output/provider failure. → **reuse logic; extend intent set + add German keyword rules.**
- **`src/validators.py`** — input caps (2000-char message, 64 KiB body), webhook-secret constant-time check. → **reuse.**
- **`src/responder.py`** — ticket structure (ID, intent, priority, 200-char summary, reason, status), answer safety regexes (API-key/private-key patterns), length caps. → **reuse shape; persist to DB.**
- **Test style** — 7 stdlib unittest files, scenario-driven (10 end-to-end pipeline scenarios incl. order-status, refund→escalate, unknown order, LLM outage). → **mirror with pytest + FastAPI TestClient.**
- **`data/orders.json` / `data/faqs.json`** — mock-data conventions (fictional shop "BrightHome Goods", tracking URLs → `example-carrier.local`). → **adapt to SQLite seed data.**

From `ai-admissions-assistant`: SQLite repository-layer pattern, `LLMProvider` protocol (mock + OpenAI impls), append-only audit log, per-project `.venv` convention.

## 3. Current architecture (new project — decided)

```
┌─ frontend/  Next.js 14+ App Router, TypeScript, Tailwind CSS
│             German UI. Pages: / (support chat), /dashboard, /tickets
│             No secrets in frontend code; backend URL via env.
│
│  HTTP/JSON
│
└─ backend/   Python 3.12, FastAPI + Pydantic, uvicorn
              Layered: api/ → services/ (pipeline) → ai/ (provider abstraction)
                       → rules/ (deterministic business logic) → db/ (SQLite repo layer)
              SQLite file DB; every business record carries store_id.
              Provider: mock (default) | openai_compatible | gemini (via connected credential)
```

Pipeline (deterministic, per brief §8): validate → classify intent → extract entities → apply business rules → authorized data lookup → select action → generate response → validate output → log events → update UI. The LLM never executes actions; it only classifies and drafts text. All lookups, policy checks, and writes are plain Python.

## 4. Existing AI-provider abstraction

Ported from `ai-customer-support-automation/src/llm.py`, plus a Gemini provider using the already-connected `custom.google-gemini` credential via the skill's `dynamic_credentials.py` helper (requests restricted to `generativelanguage.googleapis.com`; key never in chat, env, or files). Selection via `LLM_PROVIDER` env var; default `mock` for deterministic tests and zero-cost demo. Token/request limits enforced in config.

## 5. Existing test coverage

Predecessor: 70 tests passing (documented; suite not re-run here — read-only remote inspection). New project starts its own pytest suite in Phase 1 (health, provider contract, classifier validation, repo layer incl. store isolation, demo reset).

## 6. Existing deployment configuration

Essentially none on any inspected repo (no Dockerfile, no CI, no Vercel config). Predecessor's server binds `127.0.0.1:8000` — not public-ready. Deployment config is greenfield work in Phase 8.

## 7. Existing authentication / security components

Reusable: webhook-secret check, input-size caps, generic error responses (no stack-trace leaks), answer safety regexes. Missing (built in Phase 7): rate limiting, per-IP quotas, demo-data isolation enforcement, server-side API keys for admin endpoints, audit logging to DB.

## 8. Missing components (to be built)

FastAPI backend, SQLite persistence + repo layer, Next.js frontend (chat, timeline, dashboard, tickets), German intent rules, product catalogue + attributes, return-policy engine, multi-store schema, rate limiting/quotas, demo reset endpoint, Shopify adapter (interface + simulated), video/script + sales docs.

## 9. Integration risks

1. **German demo without a real LLM misclassifies** — predecessor's mock matches English keywords only ("Hallo, wo bleibt meine Bestellung #10482?" → unknown → human). Mitigation: German mock rules in Phase 3, or Gemini provider for the demo.
2. **Prompt injection via customer messages** — mitigated by validators + output safety checks + "LLM never executes actions" architecture.
3. **Public-demo abuse** — no rate limiting exists yet; Phase 7 builds it before Phase 8.
4. **Order-ID plausibility** — demo IDs must stay clearly fictional; tracking references labeled as demo.
5. **Scope creep into future modules** (carts, inventory, WooCommerce) — hard-gated to Phase 11.
6. **Brand/trademark** — "ShopFlow AI" rejected (see §11); final brand deferred to pre-launch.

## 10. Recommended repository strategy

**New repo `mshahid888/ai-ecommerce-automation` (public, matching the predecessor).** Do not fork or mutate `ai-customer-support-automation` — keep it intact as the public portfolio reference. Port its `llm.py` / `classifier.py` / `validators.py` logic into the FastAPI backend. Monorepo layout: `backend/`, `frontend/`, `docs/`.

## 11. Brand decision

| Candidate | Verdict |
|---|---|
| "ShopFlow AI" | ❌ REJECTED — crowded in AI×ecommerce; `shopflow.ai` is a parked premium domain; near-identical GitHub concept repo exists |
| "ShopPilot AI" | ❌ REJECTED — a Shopify App Store product named "ShopPilot - AI Chat & Support" does order/shipping/return queries (direct competitor) |
| "BestellPilot" | ⚠️ No direct collision found (unrelated hits only); still needs DPMA/EUIPO trademark check before commercial use |

**Decision:** defer final brand until pre-launch. Code uses a neutral working title; repo name stays generic.

## 12. Phase breakdown with acceptance criteria

| Phase | Deliverable | Acceptance |
|---|---|---|
| 1 | Repo + skeleton: FastAPI+SQLite backend, Next.js frontend init, provider abstraction port, tests | `uvicorn` boots, `/health` ok, pytest green, `npm run build` ok |
| 2 | Demo store seed + German customer-support chat UI | Visitor can open page, no account; demo indicator visible |
| 3 | German intent classification (mock rules + real provider hook) | "Wo bleibt meine Bestellung #10482?" → order_status, #10482 extracted |
| 4 | Order lookup + product Q&A from approved catalog | Answers use only verified data; missing info → honest "not available" + escalation offer |
| 5 | Returns triage: collect → policy check → ticket; human handoff | Info-gathering vs eligibility vs authorization clearly separated; no real refunds possible |
| 6 | Ops dashboard + real event timeline | Every timeline event corresponds to an executed backend operation |
| 7 | Rate limits, quotas, input hardening, full test suite | Abuse scenarios tested: enumeration attempts, oversized input, provider failure |
| 8 | Public demo deploy | URL verified live; or exact blockers documented |
| 9 | Shopify adapter interface + simulated integration | No real store touched; dev-store steps documented |
| 10 | 60–90s German video script + sales docs | Script matches the actual product, nothing invented |
| 11 | Roadmap doc (WooCommerce, carts, inventory) | Doc only — no implementation |

Each phase ends with: what was built, files changed, tests run with actual results, remaining issues, security notes, cost impact, deploy status, next phase.

## 13. Estimated effort

~14–19 focused work blocks total (Phases 1–7: ~12–15; 8–11: ~2–4). Calendar time is dominated by Shahid's auth steps for deployment (Phase 8) and Shopify (Phase 9).

## 14. Expected recurring costs

**€0 incremental.** Vercel free tier, existing Hetzner server, SQLite, mock provider. Gemini via existing credential (usage-based, negligible for demo). Optional: domain ~€12/yr. No paid service is introduced without his explicit approval.

## 15. Required credentials / his actions

| Needed for | Action by Shahid | Blocking? |
|---|---|---|
| GitHub push from this VM | `gh` login or provision GitHub SSH key here (his Mac has `id_github_muse`) | Phase 1 push — else local git + manual steps |
| Public demo (frontend) | Vercel OAuth connect | Phase 8 |
| Public demo (backend) | Hetzner `deploy` key for this VM (or add this VM's key to server) | Phase 8 |
| Real AI in demo | Choose provider (Gemini credential exists; or provide OpenAI key via Secure Vault) | No — mock default |
| Phase 9 | Shopify Partner account + free dev store | Phase 9 only |

## 16. Definition of done (v1)

Per brief §20: reliable start; German support UI works; visitor submits order-status inquiry; system looks up simulated order; response uses real demo order data; product questions use catalog data; returns follow deterministic policy; tickets creatable; escalation works; timeline reflects real events; honest errors; demo isolation; usage limits; automated tests; complete docs; verified deploy or documented blockers; video script matches product.

---

## Appendix: demo data plan (fictional)

- Store: "Muster-Shop GmbH" (clearly labeled demo)
- Orders: #10482 (shipped, DHL, fictional tracking ref, fictional delivery date), plus processing/delivered/delayed examples
- Products: incl. Trinkflasche with `spülmaschinengeeignet: ja` attribute (brief scenario B)
- Customers: fictional names, no real PII
