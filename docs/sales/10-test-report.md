# Testbericht — AI E-Commerce Automation

**Stand:** 2026-10-09 · Commit `dbb1108` (Phase 9) · Suite heute erneut
ausgeführt: **107/107 grün** (Python 3.12, pytest, isolierte Temp-DBs via
`dependency_overrides` — keine echten Netzwerk-Calls in den Tests).

Dieser Bericht nennt nur Ergebnisse, die tatsächlich gelaufen sind.

---

## 1. Automatisierte Suite — 107/107 bestanden

| Testdatei | Anzahl | Abdeckung |
|---|---|---|
| `test_health.py` | 2 | `GET /health`: Status + konfigurierter LLM-Provider |
| `test_provider_contract.py` | 6 | Provider-Vertrag: Mock deterministisch/offline; echte Provider nur mit Key; Token-Limits |
| `test_validators.py` | 6 | Input-Caps (2000 Zeichen, 64 KiB Body), leere/Whitespace-Nachrichten → 400, keine Stack-Trace-Leaks |
| `test_repos.py` | 3 | Repository-Schicht inkl. **Store-Isolation** (`store_id` in jeder Abfrage) |
| `test_chat_pipeline.py` | 12 | Chat-Pipeline Ende-zu-Ende: alle 4 Demo-Szenarien, unbekannte Bestellung, Timeline-Events entsprechen echten Operationen |
| `test_demo_reset.py` | 4 | Demo-Reset stellt nur Demo-Daten wieder her; Audit-Log überlebt |
| `test_phase3_classification.py` | 29 | 11 Intents (deutsche Keyword-Regeln), Konfidenz-Kalibrierung, Eskalations-Policy (ALWAYS_HUMAN, Schwelle 0,6), strikte Klassifikations-Validierung inkl. Stub-Provider-Fallbacks, deutsche Edge Cases |
| `test_phase6_ops.py` | 5 | Dashboard-Summary (echte DB-Zähler), Ticket-Detail, Unterhaltungen, Store-Isolation der Ops-Endpunkte |
| `test_phase7_security.py` | 19 | Abuse-Szenarien (Details §3) |
| `test_phase9_shopify.py` | 21 | `StoreIntegration`-Interface, `DemoStoreAdapter`, `SimulatedShopifyAdapter` (identische deutsche Antworten unter `demo` und `shopify_simulated`), Webhook-HMAC (gültig → 200, falsch → 401, Duplikat → 200 „duplicate"), `ShopifyAdapter`-Skelett (keine echten Netzwerk-Calls — urllib gemockt) |

**Nicht abgedeckt / manuell:** Frontend (nur `npm run build` + `npm run
lint`, keine Browser-E2E-Tests), echte KI-Provider im Dauerbetrieb,
echte Shopify-API (Skelett nie live getestet).

## 2. Live-Verifikation — Backend-Instanz, 2026-10-09

Frisch gestartete `uvicorn`-Instanz (Port 8130, frische Demo-DB,
`LLM_PROVIDER=mock`, Rate-Limiting aus für die Szenario-Aufnahme).
Alle folgenden Ergebnisse sind echte Antworten des Systems:

| # | Request | Ergebnis |
|---|---|---|
| 1 | `GET /health` | 200, `{"status":"ok","llm_provider":"mock","demo_mode":true}` |
| 2 | `POST /api/chat` „Hallo, wo bleibt meine Bestellung #10482?" | 200 · Intent `order_status`, Konfidenz 0,96 · Antwort: versendet, DHL, DEMO-TRK-10482, ETA 14.10.2026, 34,99 € · 7 Timeline-Events (empfangen → klassifiziert → Bestellnummer extrahiert → Bestellung geprüft → Regeln angewendet → Antwort erstellt → protokolliert) |
| 3 | `POST /api/chat` „Ist diese Trinkflasche spülmaschinengeeignet?" | 200 · Intent `product_question`, Konfidenz 0,94 · Antwort: „Ja, AquaPure 750 — spülmaschinengeeignet: ja. (Angaben aus dem Produktkatalog des Demo-Shops.)" |
| 4 | `POST /api/chat` „Ich möchte meine Bestellung zurücksenden." | 200 · Intent `return_request` · **kein** Ticket — System fragt nach der Bestellnummer |
| 5 | `POST /api/chat` „Ich möchte die Bestellung #10482 zurücksenden." | 200 · Retourenantrag + **Ticket #2** erstellt · Antwort nennt 30-Tage-Vorprüfung, Rücksendeadresse, „keine echte Retoure autorisiert, keine Rückerstattung" · 9 Timeline-Events inkl. „Retourenrichtlinie geprüft", „Retourenantrag erstellt", „Support-Ticket erstellt" |
| 6 | `POST /api/chat` „My package never arrived, and I want my money back immediately." | 200 · Intent `complaint` → ALWAYS_HUMAN · **Ticket #1** mit hoher Priorität · Antwort ohne Geldversprechen („wir versprechen nichts, was wir nicht geprüft haben") · Events „Support-Ticket erstellt", „An Mitarbeiter eskaliert" |
| 7 | `POST /api/chat` „Wo ist meine Bestellung #99999?" | 200 · `order: null` · „Die Bestellung #99999 wurde nicht gefunden. …" — keine erfundenen Daten |
| 8 | `GET /api/tickets/2` | 200 · Ticket-Detail: `intent: return_request`, `order_ref: 10482`, `status: open`, `priority: normal`, Eskalationsgrund „Freigabe durch Mitarbeiter erforderlich" |
| 9 | `GET /api/dashboard/summary` | 200 · echte Zähler: 6 Unterhaltungen, 12 Nachrichten, 2 offene Tickets, 1 Eskalation, Intent-Verteilung (order_status 2, return_request 2, complaint 1, product_question 1), neueste Workflow-Events |
| 10 | `POST /api/demo/reset` ohne Key | **401** (Admin-Key erforderlich) |

## 3. Abuse-Tests (Phase 7, Suite erneut grün)

Aus `test_phase7_security.py` (19/19) — Erwartung vs. Ergebnis:

- **Order-Enumeration** (20 unbekannte IDs #99000–#99019): alle 200 mit
  ehrlicher „nicht gefunden"-Klärung, `order: null`, keine Detail-Leaks.
- **Oversized** (5000 Zeichen): 400, deutsch
  („Ihre Nachricht ist zu lang (maximal 2000 Zeichen).").
- **Leere Nachricht**: 400, deutsch.
- **Rapid-Fire** (Limit 5/Min. im Test): 5×200, dann 429 mit
  `Retry-After: 60`.
- **Tages-Cap** (auf 3 gesetzt): `[200, 200, 200, 429]`.
- **Lese-Limit** (4/Min.): 4×200, dann 429.
- **Reset ohne/falscher Key**: 401 + `admin_auth_failure` im Audit-Log;
  mit Key: 200, Daten wiederhergestellt, `demo_reset` auditiert.
- **Reset-Rate-Limit** (2/Std.): 429 beim 3. Versuch.
- **KI-Quota** (Stub, Cap 2): 2 echte Calls, 3. Request → Mock-Fallback
  (`provider: "mock"`, `quota_fallback: true`, deutscher Hinweis,
  Event `llm_quota_fallback`).
- **Audit-Nachweis:** Rows für `demo_reset`, `admin_auth_failure`,
  `ticket_created`, `escalated`; IPs nur gehasht; Audit überlebt Resets.

Live gegen `uvicorn` (Ports 8123/8124, frische DBs, Phase 7):
`POST /api/chat` ×8 bei Limit 5/Min. → `200×5, 429×3` mit
`retry-after: 60`; Enumeration → `order: null`; Admin-Key-Datei Modus
0600, einmalige stdout-Ausgabe bei Generierung.

## 4. Bekannte Test-Lücken (nicht verschwiegen)

- Kein automatisierter Browser-E2E-Test des Frontends (nur Build + Lint).
- Kein Lasttest über die Abuse-Szenarien hinaus.
- Echte KI-Provider und echte Shopify-API nie gegen Live-Systeme getestet.
- Multi-Worker-Verhalten des In-Memory-Rate-Limiters nicht getestet.

---

*Methodik: Suite (`pytest -q`) und Live-Curls wurden am 2026-10-09 auf
dieser VM ausgeführt. Frontend-Verifikation: `npm run build`
(Next.js 16.4.0, alle 7 Routen) in Phase 8.*
