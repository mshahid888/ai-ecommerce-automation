# Shopify-Integration — Architektur, Stand, Einrichtung

**Phase 9, 2026-10-09. Status: Schnittstelle + simulierte Integration fertig.
Kein echter Shopify-Shop angebunden, kein Dev-Store, keine Credentials.**

## 1. Architektur

Alle Produkt-/Bestell-Lookups der Chat-Pipeline laufen über das
`StoreIntegration`-Interface — nie direkt gegen eine Datenbank oder API:

```
                      ┌───────────────────────────┐
                      │  Chat-Pipeline            │
                      │  (services/pipeline.py)   │
                      └─────────────┬─────────────┘
                                    │  get_order / search_products /
                                    │  get_product / list_orders /
                                    │  get_fulfillment  (StoreIntegration)
                    STORE_BACKEND   ▼
        ┌──────────────┬──────────────┴──────────────┬──────────────┐
        │  demo        │  shopify_simulated          │  shopify     │
        │  (Standard)  │                             │  (Skelett)   │
        ├──────────────┼─────────────────────────────┼──────────────┤
        │ DemoStore-   │ SimulatedShopifyAdapter     │ Shopify-     │
        │ Adapter      │  delegiert an den           │ Adapter      │
        │  ↕ dünne    │  Demo-Adapter, hängt         │  ↕ Admin API │
        │  Schicht um  │  Shopify-Metadaten an:      │  REST,       │
        │  die SQLite- │  gid://shopify/Order/…      │  X-Shopify-  │
        │  Repos       │  + simulated: True          │  Access-     │
        └──────────────┴─────────────────────────────┴──────────────┘
                        ▲                             ▲
                        │ gleiche Demo-Daten          │ wird NUR mit
                        │ gleiche kanonische Felder   │ SHOPIFY_SHOP_DOMAIN +
                                                      SHOPIFY_ADMIN_API_TOKEN
                                                      konstruiert
```

Kanonische Payloads (siehe `integrations/base.py`): `order_ref`,
`status`, `carrier`, `tracking_ref`, `eta_date`, `total_cents`,
`currency` — die Pipeline liest nur diese Felder. Zusatzfelder
(`shopify_id`, `simulated`) sind reine Metadaten.

## 2. Was funktioniert jetzt vs. was simuliert ist

| Baustein | Status | Beschreibung |
|---|---|---|
| `StoreIntegration`-Interface | ✅ fertig | `get_product`, `search_products`, `get_order`, `list_orders`, `get_fulfillment`; alle werfen `IntegrationError` bei Fehlern |
| `DemoStoreAdapter` | ✅ fertig | Dünne Schicht über den bestehenden SQLite-Demo-Shop; kein Verhaltenswechsel |
| `SimulatedShopifyAdapter` | ✅ fertig | Gleiche Demo-Daten, Shopify-förmige Antworten (`gid://shopify/Order/10482`, `simulated: True`) |
| `STORE_BACKEND`-Umschalter | ✅ fertig | `demo` (Standard) / `shopify_simulated`; Chat-Antworten unter beiden identisch (107 Tests grün) |
| Webhook-Endpunkt `POST /api/integrations/shopify/webhooks` | ✅ fertig, simuliert | HMAC-SHA256-Prüfung + Dedupe per `X-Shopify-Webhook-Id` + `audit_log`; ohne `SHOPIFY_WEBHOOK_SECRET` ehrliches 503 (`shopify_not_configured`) |
| `ShopifyAdapter` (echte Admin API) | 🟡 Skelett | Request/Response-Mapping gegen Shopify Admin API `2026-10` implementiert (Timeout 10 s, max. 2 Retries mit Backoff); **nie live getestet** |
| Dev-Store-Anbindung | ⬜ offen | Braucht Shahids Schritte aus §3 |

**Nichts hier ruft Shopify an.** Es gibt keine Credentials, keine
Netzwerkaufrufe in den Tests (urllib ist gemockt), keine Secrets in Commits.

## 3. Shahids exakte Voraussetzungen für einen Live-Dev-Store-Test

1. **Shopify-Partner-Konto** erstellen (kostenlos): https://partners.shopify.com
   — persönliches Konto, keine Kosten.
2. **Dev-Store** anlegen: Partner-Dashboard → *Stores* → *Add store* →
   *Development store*. (Dev-Stores sind kostenlos, nicht übertragbar,
   keine echten Zahlungen.)
3. **Custom App** im Dev-Store anlegen: Store-Admin → *Apps* → *App- und
   Vertriebskanaleinstellungen* → *Apps entwickeln* → *App erstellen*.
4. **Minimale Scopes** vergeben (nur lesen, nichts schreiben):
   `read_orders`, `read_products`, `read_fulfillments`.
   Die App danach im Store **installieren** — erst dann wird das Token
   angezeigt.
5. **Token sicher ablegen**: `SHOPIFY_SHOP_DOMAIN=<shop>.myshopify.com` und
   `SHOPIFY_ADMIN_API_TOKEN=shpat_…` NUR in die Server-`.env` (Modus 0600,
   siehe `backend/.env.production.example`). Niemals committen, niemals
   ins Frontend.
6. **Webhook registrieren** (optional, Phase 9b): in der Custom App unter
   *Konfiguration* → *Webhooks* → HTTPS-Endpunkt
   `https://<backend-domain>/api/integrations/shopify/webhooks`,
   Topics `orders/create` + `orders/updated`. Das **Client Secret** der App
   als `SHOPIFY_WEBHOOK_SECRET` in die Server-`.env` legen. Danach:
   `SHOPIFY_API_VERSION=2026-10` prüfen (neueste stabile Version laut
   shopify.dev, Stand 2026-10-09).
7. **Verifikation**: mit mir zusammen einen Live-Test fahren —
   `get_order` gegen eine Testbestellung im Dev-Store, dann das
   Status-Mapping (fulfilled → shipped) und die Tracking-Felder gegen die
   echte Antwort prüfen.

## 4. Fehlerbehandlung (Berechtigungen, Ausfälle)

- **403 von Shopify** → `IntegrationError` mit explizitem Hinweis auf die
  fehlenden Scopes (`read_orders`, `read_products`, `read_fulfillments`)
  und die App-Installation. Die Pipeline antwortet dem Kunden ehrlich
  („Shop-Anbindung gestört") statt Daten zu erfinden.
- **429** → `Retry-After` wird respektiert (max. 10 s), danach Retry mit
  Backoff (0,5 s → 1 s), maximal 2 Retries.
- **Timeouts/Netzwerkfehler** → gleicher Retry-Pfad; danach ehrliche
  Fehlermeldung + `store_backend_error`-Event in der Timeline.
- **Webhook mit falscher Signatur** → 401, `audit_log`-Eintrag
  (`shopify_webhook_rejected`); **doppelte Webhook-ID** → 200
  (`duplicate`), keine Wiederverarbeitung.
- Tokens stehen nie in Logs, URLs oder Payloads — nur im
  `X-Shopify-Access-Token`-Header serverseitig.

## 5. Explizite Regel

> **Kein echter Shop wird ohne Shahids schriftliches Go angebunden.**
> Dev-Store zuerst. Keine echten Bestellungen anlegen, stornieren,
> erstatten oder ändern — die Adapter-Methoden sind lesend; Schreibzugriff
> ist für die erste Release bewusst nicht vorgesehen.

## 6. Offene Punkte (Phase 9b, nach dem Dev-Store)

- `fulfilled → shipped`-Mapping gegen echte Dev-Store-Antworten verifizieren
  (Shopify unterscheidet „versendet" vs. „zugestellt" nicht sauber).
- `eta_date` ist bei Shopify immer `None` (kein ETA-Feld) — Pipeline
  lässt die Lieferprognose ehrlich weg.
- Produkt-Attribute (z. B. `spuelmaschinengeeignet`) haben kein
  Shopify-Äquivalent im Basis-Payload → `{}` und ehrliche
  „keine Information"-Antwort; ggf. Metafields mappen.
- Webhook-Verarbeitung: derzeit nur Empfang + Protokollierung; echte
  Verarbeitung (z. B. Ticket bei `orders/updated`) erst nach Dev-Store-Test.
