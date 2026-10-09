# Phase 9 — Report: Shopify adapter interface + simulated integration

**Date:** 2026-10-09
**Commit:** Phase 9 (pending)
**Tests:** 107 passed (86 existing + 21 new), 0 failed

## What was built

1. **`StoreIntegration` interface** (`backend/app/integrations/base.py`) —
   the contract every store backend must satisfy: `get_product`,
   `search_products`, `get_order`, `list_orders`, `get_fulfillment`.
   All return plain dicts/None, all are store-scoped, all raise
   `IntegrationError` on failure. Canonical payload shapes documented in
   the module.
2. **`DemoStoreAdapter`** (`integrations/demo.py`) — thin wrapper around
   the EXISTING SQLite demo-store queries (`OrderRepository`,
   `order_rules.lookup_order` incl. raw→normalized reference logic,
   `product_rules` token ranking). Zero behavior change.
3. **`SimulatedShopifyAdapter`** (`integrations/shopify_simulated.py`) —
   serves the SAME demo data with Shopify-shaped metadata
   (`gid://shopify/Order/10482`, `shopify_name: "#10482"`,
   `simulated: True`). Delegates to the demo adapter, so canonical fields
   are identical by construction.
4. **`STORE_BACKEND=demo|shopify_simulated`** env switch (config.py,
   default `demo`; unknown values fall back to `demo`). The pipeline now
   reads products/orders ONLY through the adapter — no direct DB calls
   remain in `services/pipeline.py`.
5. **`ShopifyAdapter` skeleton** (`integrations/shopify.py`) — real
   Shopify Admin API mapping (REST; GraphQL noted in the docstring).
   Implemented against documented behavior: latest stable API version
   **2026-10** (shopify.dev versioning page, checked 2026-10-09),
   `X-Shopify-Access-Token` header, `GET /orders.json?name=#10482&status=any`,
   fulfillments for tracking. Constructed ONLY with
   `SHOPIFY_SHOP_DOMAIN` + `SHOPIFY_ADMIN_API_TOKEN` env vars (server-side
   only); helpful `IntegrationConfigError` otherwise. 10 s timeout, max 2
   retries with backoff, 429 honors `Retry-After`, 403 raises with explicit
   scope guidance (`read_orders`, `read_products`, `read_fulfillments`).
   **Never connected, never tested live.**
6. **Webhook endpoint** `POST /api/integrations/shopify/webhooks`
   (`app/api/integrations.py`): HMAC-SHA256 verification per Shopify docs
   (`webhooks.py`, constant-time compare) → 401 on failure; idempotency
   via `X-Shopify-Webhook-Id` (`shopify_webhook_events` table, new in
   schema.sql) → 200 `duplicate` without reprocessing; receipt written to
   `audit_log`. Marked SIMULATED: without `SHOPIFY_WEBHOOK_SECRET` it
   honestly returns 503 (`shopify_not_configured`).
7. **Honest backend-failure path in the pipeline**: `IntegrationError`
   → real `store_backend_error` timeline event (status `failed`) + German
   customer reply („Shop-Anbindung gestört") — no invented data.
8. **Docs**: `docs/SHOPIFY.md` (architecture diagram, works-now-vs-simulated
   table, Shahid's exact 7-step dev-store setup, permission-failure
   handling, the explicit no-real-store-without-written-go rule);
   `.env.production.example` documents all new env vars (empty placeholders).

## Files changed

- NEW `backend/app/integrations/{__init__,base,demo,shopify,shopify_simulated,webhooks}.py`
- NEW `backend/app/api/integrations.py`
- NEW `backend/tests/test_phase9_shopify.py` (21 tests)
- NEW `docs/SHOPIFY.md`
- EDIT `backend/app/services/pipeline.py` (adapter wiring + failure path)
- EDIT `backend/app/rules/product_rules.py` (`rank_products()`; `find_product` delegates — same result)
- EDIT `backend/app/config.py` (`STORE_BACKEND`, `SHOPIFY_*` settings)
- EDIT `backend/app/db/schema.sql` (`shopify_webhook_events` table)
- EDIT `backend/app/main.py` (router registration)
- EDIT `backend/.env.production.example` (new env vars)

## Tests executed (actual results)

`pytest tests/` → **107 passed** (was 86; +21 new), 0 failed, ~5 s.
New coverage in `test_phase9_shopify.py`:
- Parity: demo vs simulated return identical canonical payloads for
  order #10482, product AquaPure 750 (SKU + numeric-id lookup), product
  search ranking, fulfillment #10482 (and None for #10483, which has no
  tracking), `list_orders` sequence. Order-ref normalization (`010482`,
  ` #10482 `) preserved through the interface. Store isolation (other
  store → None/empty).
- Webhooks: locally-computed valid HMAC → 200 `received` + 1 audit row +
  1 dedupe row; tampered body/bad header/missing secret → False/401/503;
  duplicate webhook id → 200 `duplicate`, no second audit row; missing id
  → 400.
- Real adapter: missing env → `IntegrationConfigError` naming both vars
  + docs pointer (no network attempted); bad domain → error mentioning
  myshopify.com; with env set + monkeypatched `_http_get_json` → order
  mapping correct (order_ref/status/total_cents/shopify_id, eta None),
  token only in header never in URL; 403 → `IntegrationError` naming the
  required scopes.
- Chat E2E under both backends: order-status, product-question, and
  return-request replies are byte-identical (ticket IDs normalized).

Also smoke-tested: app boots with `STORE_BACKEND=shopify_simulated`,
`/api/chat` answers #10482 from demo data, webhook returns 503 when
unconfigured.

## Remaining issues

- `ShopifyAdapter` is untested against a real API (no dev store exists).
  Status mapping `fulfilled → shipped` and tracking fields need a live
  check (documented as Phase 9b in SHOPIFY.md §6).
- Shopify has no order-ETA field: `eta_date` is always None from the real
  adapter — by design, honestly omitted.
- Demo product attributes have no Shopify equivalent in the basic product
  payload → pipeline will answer „keine Information" until metafields are
  mapped.

## Security considerations

- No Shopify credentials exist anywhere; none created, none stored, none
  committed. `git diff` contains no token/secret values.
- Tokens (when they exist later) live only in server env / memory, travel
  only in the `X-Shopify-Access-Token` header, never in logs/URLs/payloads.
- Webhook HMAC uses constant-time compare; failures are audit-logged
  (`shopify_webhook_rejected`); `shopify_webhook_events` and `audit_log`
  are NOT wiped by the demo reset (integration evidence survives).
- Webhook POSTs carry no rate-limit rule in the ASGI middleware (not
  matched by any rule) — acceptable: Shopify webhooks are infrequent and
  authenticated by HMAC; body is capped at 64 KiB.

## Cost implications

€0. No paid services, no network calls in tests, stdlib-only HTTP.

## Deployment status

Not deployed (Phase 8 status unchanged: deployment configs prepared,
nothing live). New env vars are documented in `.env.production.example`
with empty placeholders; no action needed on the server.

## Next phase

Phase 10 (video demonstration + sales docs) — needs nothing from Phase 9
except the finished product. Phase 9b (live dev-store verification) is
blocked on Shahid's 7 steps in `docs/SHOPIFY.md` §3.
