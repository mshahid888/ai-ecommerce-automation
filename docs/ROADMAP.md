# Roadmap — Future Expansion (Phase 11)

**Status:** Planning document only. **Nothing in this document is implemented.**
**Rule:** No module below starts before the current product has its first
paying pilot customer. This is a standing gate, not a suggestion.

**Date:** 2026-10-09 · Product state: Phases 0–10 done, 107 tests green.

This document is the honest future-expansion plan per the master brief §17.
It is written for Shahid (planning, sales conversations, effort scoping) and
for any future developer who will build these modules. It says what is worth
building, what it reuses, what blocks it, how much effort it costs, and —
equally important — what must **not** be built prematurely.

---

## 0. Standing gate (applies to every module below)

> **No future module is started until the current product (AI customer
> support + order lookup + returns triage + dashboard) has a first paying
> pilot customer on a real store backend.**

Reasons:

1. Future modules only make sense once real store data, real consent
   records, and a real operator exist to test against.
2. Building them on demo data would fabricate integration behavior that
   cannot be verified — the project rule "never claim what isn't verified"
   applies to roadmap code too.
3. The pilot produces the first store-specific evidence: which workflows the
   SME actually pays for, which is the best argument for what to build next.

When the gate opens, build modules **in the recommended sequence (§6)**,
one at a time, each verified before the next starts.

---

## Module A — Abandoned-cart recovery

### Problem it solves (SME owner perspective)

German SME shop owners lose a significant share of checkouts to abandoned
carts. A timely, polite reminder ("Ihre Bestellung wartet noch") recovers
revenue without extra staff. The owner does not want a black-box marketing
AI inventing discount offers or spamming customers — they want **controlled,
opt-in-safe, measurable** reminders.

### Proposed approach (reuses existing architecture)

- **Schema** (`backend/app/db/schema.sql`, `seed.py`, `repositories.py`):
  new store-scoped tables `carts`, `cart_items`, `consent_records`
  (marketing opt-in status per customer, timestamped, source-labeled),
  `reminder_sends` (who got what, when, which template, opt-out flag).
- **Integration** (`backend/app/integrations/base.py`): extend
  `StoreIntegration` with `get_abandoned_carts(since)` and
  `get_customer_consent(customer_id)`. Shopify adapter:
  `abandoned_checkouts` Admin API + customer `accepts_marketing` flag.
  WooCommerce adapter (Module D): pending orders via the REST API.
  The pipeline reads only the canonical shapes — never the raw API.
- **Rules** (`backend/app/rules/cart_rules.py`, new): eligibility in
  deterministic Python — cart age window (e.g. 1h < age < 72h), minimum cart
  value from `store_policies`, consent present, no prior reminder in window,
  customer not opted out. LLM never decides eligibility.
- **Content** (`backend/app/services/cart_pipeline.py`, new): reminder text
  comes **only from approved templates stored in `store_policies`**
  (fill slots: shop name, cart items, link) — no free-text generation of
  offers, prices, or discount codes by the AI.
- **Delivery tracking**: record `reminder_sends` rows; conversion attribution
  ("did this cart convert after the reminder?") only where the store backend
  supports checkout linking — mark attribution as *approximate* when it
  can't be verified.
- **API/ops** (`backend/app/api/ops.py` or new `api/carts.py`): opt-out
  endpoint (single click, no login), operator dashboard panel showing sends,
  opt-outs, attributed recoveries with the same honest-labeling as the
  existing dashboard (demo vs. measured).

### Prerequisites / gates

1. First paying pilot running (standing gate).
2. Store backend exposing abandoned carts + consent flags (Shopify dev store
   or WooCommerce test site).
3. **Legal review before any pilot send.** German B2C marketing emails are
   governed by consent rules (notably the opt-in requirement for electronic
   advertising). Open questions the project cannot answer itself:
   - Which legal basis applies to *cart reminders* specifically
     (prior consent vs. "berechtigtes Interesse" vs. exception for existing
     customers)? This is genuinely contested territory.
   - What counts as a valid opt-out mechanism and proof trail for a
     small shop?
   
   **No claim is made that the module as designed is legally compliant.**
   Before any pilot store sends a single reminder, a qualified
   legal advisor must sign off the consent flow and templates. The
   architecture supports this (consent records, opt-out endpoint, approved
   templates, audit trail) — the compliance judgment does not come from
   the software.

### Effort

~4–6 focused work blocks (after Module D integration exists:
+1–2 blocks if the store adapter must be built in parallel).

### What must NOT be built prematurely

- **No LLM-written marketing copy.** Approved templates + slot filling
  only. Free-text offer generation is a fabrication and liability risk.
- **No automatic discount codes.** A discount is a business decision; it
  requires explicit merchant authorization per campaign (see Module C
  gating philosophy).
- **No SMS/WhatsApp/phone reminders** without a separate, explicit opt-in
  per channel.
- **No "AI predicts which customers will convert"** scoring model before
  simple rule-based reminders prove value.
- **No cross-store learning** ("your customers behave like store X's") —
  violates the store-isolation principle already enforced in
  `db/repositories.py`.

---

## Module B — Inventory alerts

### Problem it solves (SME owner perspective)

Small shops discover stockouts too late — a product sells out, customers
order anyway or leave. Owners want a simple "Warn mich, wenn X unter Y
Stück fällt" that respects their thresholds, without an AI that *orders*
or *reserves* stock on its own.

### Proposed approach (reuses existing architecture)

- **Schema**: new store-scoped tables `stock_snapshots` (periodic readings)
  and `inventory_thresholds` (sku → warn_level, stored in or alongside
  `store_policies`); repository functions in `db/repositories.py` reuse the
  existing store-isolation pattern.
- **Integration**: extend `StoreIntegration` with
  `get_stock(sku_or_id) -> int | None` and `list_stock_below(threshold)`.
  Both Shopify (inventory levels) and WooCommerce (stock_quantity) expose
  this via their REST APIs.
- **Rules** (`backend/app/rules/inventory_rules.py`, new): deterministic
  threshold checks — current stock ≤ threshold → alert. Anomaly detection
  starts with simple statistics (e.g. sudden 3σ drop vs. 30-day average),
  clearly labeled as heuristics — **no ML model in v1**.
- **Execution**: a scheduled job (cron on the Hetzner host; the project has
  no scheduler infrastructure, and adding Redis/Celery for this is
  overkill — a cron + the existing SQLite is the honest design).
- **Notification**: alerts go to the **operator dashboard** (new panel in
  `services/dashboard.py` + frontend) and create tickets of type
  `inventory_alert` — not customer-facing messages. Optional: email to the
  operator via the store's own address once pilot customers exist.

### Prerequisites / gates

1. First paying pilot (standing gate).
2. Store backend with readable stock levels + per-store operator contact
   configuration (who gets the alert).
3. No legal gate beyond data handling, but: alert history must respect the
   existing audit-log conventions.

### Effort

~3–4 focused work blocks.

### What must NOT be built prematurely

- **Hard rule: alerts only. Never automatic inventory changes.** No stock
  writes, no reservations, no purchase-order creation, no "reorder from
  supplier" automation. Any *action* on inventory requires the explicit
  authorization gating designed for Module C — it is not part of Module B.
- **No real-time monitoring.** Polling (e.g. hourly cron) is correct for
  SME scale; "real-time" requires infrastructure the product deliberately
  avoids (see §7).
- **No ML anomaly detection** until threshold alerts are used by real
  operators and the false-positive rate is measured.
- **No customer-facing "only 2 left!" scarcity messaging** generated by the
  system — that's a merchant decision, not an alert module's job.

---

## Module C — Order processing (exception flagging + authorized actions)

### Problem it solves (SME owner perspective)

Order processing (address corrections, cancellations within the legal
window, partial refunds, fulfillment exceptions) eats staff time but is
**money-moving and legally consequential**. The owner wants an assistant
that prepares everything and flags exceptions, and executes only what was
explicitly approved — never autonomous cancellations or refunds.

### Proposed approach (reuses existing architecture)

- **Schema**: new `order_actions` table (proposed action, payload,
  status: `proposed` → `approved`/`rejected` → `executed`, approver,
  audit trail) + extend `tickets` for an "awaiting approval" state.
- **Pipeline extension** (`backend/app/services/pipeline.py` pattern, new
  `services/order_action_pipeline.py`): **propose → human approves →
  execute → audit.** The LLM extracts intent and parameters (e.g. "change
  shipping address to X"); deterministic `rules/order_actions.py` validates
  (address format, order still unshipped, within policy window); the action
  is **never executed at proposal time**.
- **Authorization gates**: operator approval via `api/ops.py` endpoint
  requiring the existing admin-key mechanism (or per-operator auth when
  Module E exists); allowlist of executable actions per store in
  `store_policies` (e.g. `address_change: allowed`, `refund: requires_owner`,
  `cancel: disabled`); dry-run mode executes against a simulated adapter
  first. Every executed action writes an `audit_log` row.
- **Refunds**: structurally supported in the schema but the code **cannot
  execute a real refund** until a store-specific, legally reviewed
  integration exists and the pilot merchant signs a written authorization
  procedure. The demo separation from the current returns triage
  (info-gathering vs. authorization vs. execution) is kept and extended.

### Prerequisites / gates

1. First paying pilot (standing gate) — plus **that pilot merchant's
   explicit written request** for order actions.
2. Operator approval UI + audit trail verified end-to-end against a
   simulated adapter *before* any live action is possible.
3. Legal review of which actions may be automated at all under German
   consumer law (cancellation windows, refund obligations). The system
   enforces merchant policy; it does **not** interpret consumer rights —
   the same rule the current returns module follows.

### Effort

~5–7 focused work blocks (the largest module; half of it is authorization
and audit infrastructure).

### What must NOT be built prematurely

- **No autonomous cancellations, refunds, or address changes.** Ever. The
  propose → approve → execute → audit chain is the entire point of the
  module.
- **No bulk operations** (e.g. "cancel all delayed orders") — batch actions
  multiply the blast radius; each action gets its own approval until a
  pilot merchant explicitly demands and signs off batching.
- **No write-back to a store before** the approval UI, audit trail, and
  simulated-adapter dry-run all exist and pass tests.
- **No "AI decides the refund amount"** — amounts come from store policy
  math or operator input, never from an LLM response.

---

## Module D — WooCommerce adapter

### Problem it solves (SME owner perspective)

A large share of German SME shops run WooCommerce, not Shopify. The same
product — AI support, order lookup, returns triage — should work for them
without rebuilding the application. The owner just connects their store;
the workflows stay identical.

### Proposed approach (reuses existing architecture)

- **Same `StoreIntegration` interface** (`backend/app/integrations/base.py`).
  New `integrations/woocommerce.py` mapping the canonical shapes:
  - products → WooCommerce REST API `products` (search, attributes),
  - orders → `orders` (lookup by ID/reference),
  - fulfillment → order `meta_data` / shipment-tracking plugins where
    present (`None` when absent — honest, as today),
  - stock → `stock_quantity` (also feeds Module B),
  - abandoned carts → pending orders + cart REST endpoints (feeds
    Module A).
- **Webhooks** (`backend/app/integrations/webhooks.py` pattern from the
  Shopify adapter): WooCommerce webhook signature verification, dedupe,
  honest 503 without a configured secret — the same security posture as
  Phase 9.
- **Zero business-logic duplication.** `services/pipeline.py`,
  `services/classification.py`, `rules/`, `db/repositories.py` are reused
  untouched. If a WooCommerce-specific behavior is needed, it lives in the
  adapter's mapping code, never as a fork of the pipeline.
- **API/UI**: store-backend selection (`STORE_BACKEND=woocommerce`,
  credentials in `integration_credentials`, server-side only — per the
  existing rule that tokens never leave the server and are never committed).

### Prerequisites / gates

1. First paying pilot (standing gate) — ideally the first WooCommerce
   customer; otherwise a WooCommerce test site (free local install or a
   staging subdomain).
2. WooCommerce REST API credentials (consumer key/secret) for the test
   store; webhook secret for event verification.
3. Modules A/B/C consume the WooCommerce adapter's cart/stock methods —
   building D before them is fine; building them without a testable
   adapter is not.

### Effort

~3–4 focused work blocks.

### What must NOT be built prematurely

- **No WooCommerce-specific pipeline fork.** One pipeline, one rule set;
  the adapter maps data, nothing more.
- **No WordPress/PHP plugin.** The product stays API-side; maintaining a
  plugin is a separate product with its own release/update/support burden.
- **No automatic "import all products/orders" migration tool** before a
  customer needs it.
- **No second integration interface.** If the `StoreIntegration` contract
  needs a method for WooCommerce, that method is added to the shared
  contract with a documented fallback (`None`) — not a parallel interface.

---

## Module E — Multi-store management

### Problem it solves (SME owner perspective)

This is not for the store owner — it's for **Shahid as the product
operator** (and later, for agency use): onboarding a second, third, tenth
store without editing code or env files. Each store gets its own policies,
credentials, quotas, and operator access, with the existing store-isolation
guarantees kept intact.

### Proposed approach (reuses existing architecture)

- The data model already supports it: `stores`, `store_policies`,
  `integration_credentials` exist; `db/repositories.py` enforces
  `store_id` isolation in every query (tested in Phase 7).
- **Admin UI** (new frontend section, behind the existing admin-key
  mechanism or per-operator auth): store onboarding wizard
  (create store → store credentials → configure policies → connect
  backend → seed/verify), per-store policy editor (return window,
  shipping info, rate limits, allowed actions), credential rotation
  (write-only UI; secrets never displayed, same rule as today).
- **Operational controls**: per-store AI quota and rate limits (extend
  `ai/quota.py` and `security/`), per-store feature flags
  (which modules are enabled for this store), per-store audit view.
- **Operator roles**: minimal viable — `owner` (everything) vs `support`
  (tickets, timeline, no credentials/policies) — built only when a
  customer asks for staff access.

### Prerequisites / gates

1. First paying pilot (standing gate) — concretely, Module E becomes
   **necessary at the second store**. One store can be configured by hand;
   two stores justify the admin UI.
2. Real operator-auth requirement (per-user logins) — until then, the
   existing admin-key mechanism is sufficient.

### Effort

~5–8 focused work blocks (admin UI is the bulk).

### What must NOT be built prematurely

- **No billing/subscription system** before there are paying customers
  asking for self-service plans. Invoicing stays manual (or via existing
  accounting tools) until volume justifies it.
- **No SSO/OAuth login system** before a customer requires staff accounts.
- **No microservices split.** The single deployable FastAPI app is correct
  at this scale; splitting it is an operations burden, not a feature
  (see §7).
- **No "marketplace/app-store" packaging** (Shopify App Store listing,
  WooCommerce marketplace) — that's a distribution decision with review,
  fee, and support implications, not an engineering task for this phase.

---

## 6. Recommended sequence (argued from SME value)

| Order | Module | Why this position |
|---|---|---|
| 1 | **A — Abandoned-cart recovery** | Direct, measurable **revenue**. The easiest story to sell ("we recover X carts"), demoable on the pilot store, and it exercises the consent/template infrastructure that makes the product look professionally built. Legal review is the honest cost — budget it. |
| 2 | **D — WooCommerce adapter** | **Market expansion** with the same code: the whole product becomes sellable to the large WooCommerce segment of German SMEs. Also unblocks A and B for those stores. Highest value-per-effort after A. |
| 3 | **E — Multi-store management** | Becomes **necessary at the second store**. Not valuable before (one store can be configured manually); painful to lack after. Build it when onboarding store #2, not before. |
| 4 | **B — Inventory alerts** | Operational hygiene — valuable, but SMEs buy revenue first. Needs operator roles/notifications, which E provides. |
| 5 | **C — Order processing** | **Last.** Money-moving actions carry the highest risk and require the most trust. Sell it only after the pilot relationship proves the product is reliable — the propose → approve → execute chain is worthless without that trust. |

**Principle:** sell revenue first (A), then reach (D), then operations
(E, B), and money-moving automation only after trust is earned (C).

---

## 7. Not on the roadmap (explicitly excluded, with reasons)

| Excluded | Reason |
|---|---|
| **n8n dependency** | Visual workflow orchestration adds hosting, versioning, and debugging burden. The explicit Python pipeline (`services/pipeline.py`) is testable, versioned in git, and sufficient. Revisit only if a customer needs a *visual* editor — nobody has asked. |
| **Vector database / embeddings search** | Product Q&A is deterministic attribute lookup (`rules/product_rules.py`); it is correct by construction. Semantic search is a nice-to-have for very large catalogs and brings hosting cost + hallucination surface. Not justified. |
| **Microservices** | One FastAPI deployable + one Next.js frontend is operable by a solo founder on existing infrastructure. Splitting multiplies deployment, monitoring, and failure modes with zero SME-facing benefit. |
| **Mobile apps (iOS/Android)** | The responsive web UI covers operator and customer use. Native apps add two release pipelines, store reviews, and maintenance for no demonstrated demand. |
| **Redis / message queues / PostgreSQL** | SQLite + cron cover the current and planned scale. Introduce them when a measured bottleneck demands it — not in anticipation of one. |
| **On-device / self-hosted LLM** | The provider abstraction (`ai/providers.py`) already supports swapping providers; self-hosting is a cost and ops decision for much later, if ever. |
| **Multi-language UI** | The product is positioned for German SMEs; the architecture keeps strings separable so a second language can be added when a customer pays for it. |
| **Marketplace listings / app-store packaging** | Distribution and pricing decisions, not engineering. Revisit after several direct pilots. |

**Anti-scope-creep rule:** any proposal not in this document must answer —
*which paying customer asked for it, and what does it displace in the
sequence above?* — before it enters the roadmap.

---

## 8. Cost implications

All modules are designed for the existing cost envelope: Vercel frontend
(free tier), the existing Hetzner backend, SQLite, and cron. Incremental
costs per module:

- **A:** AI usage for classification of reminder eligibility — negligible
  (deterministic rules, templates); email sending via the merchant's own
  provider (their cost, not ours).
- **B:** cron job — €0; notification email via merchant's provider.
- **C:** none beyond existing hosting; legal review is a **one-time
  professional fee**, not infrastructure.
- **D:** €0 (test store is free).
- **E:** €0.

**No module introduces a paid SaaS dependency.** Any paid dependency
requires Shahid's explicit approval per the standing cost rule.

---

## 9. How to open a future module (process)

When the standing gate is met and a module is chosen:

1. Write a module brief (problem, approach, file-level plan, gates) —
   this document is the starting template.
2. Extend the `StoreIntegration` contract and schema **before** business
   logic; keep every change store-scoped.
3. Build behind the existing test conventions: deterministic mock-first
   tests in `backend/tests/` (target: same green-bar discipline as the
   current 107 tests).
4. Update the three-zone feature list (`docs/sales/01-feature-list.md`):
   anything not verified stays out of "Verfügbar".
5. For A and C: complete the legal review **before** pilot activation,
   and document the open questions and the review outcome honestly.

---

*Phase 11 complete: roadmap documented, no code changed. All modules gated
on the first paying pilot.*
