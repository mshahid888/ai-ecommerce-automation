# Phase 7 — Testing, Security & Abuse Protection (Public-Demo-Readiness)

**Datum:** 2026-10-09
**Status:** Implementiert, getestet (**86/86 grün**: 67 Bestand + 19 neu),
per curl gegen `uvicorn` live-verifiziert, als Phase 7 committet.

Phase 7 härtet die öffentliche Demo: Rate Limiting, Admin-Key,
KI-Tageskontingent, Audit-Logging, Input-Härtung, Lifespan-Migration.
Ausführliche Sicherheitsdokumentation: `docs/SECURITY.md`.

## Was wurde implementiert

### Backend

- **`app/security/` (neu):**
  - `rate_limit.py` — `SlidingWindowLimiter`: In-Memory Sliding-Window pro
    Client-IP (`time.monotonic`, thread-safe, kein Redis).
  - `middleware.py` — `RateLimitMiddleware` (reines ASGI):
    `POST /api/chat` → 30/Min. + 200/Tag pro IP; `POST /api/demo/reset` →
    5/Std.; `GET /api/*` → 60/Min. Alle Limits via Env konfigurierbar
    (`RL_CHAT_PER_MINUTE`, `RL_CHAT_PER_DAY`, `RL_READ_PER_MINUTE`,
    `RL_RESET_PER_HOUR`, `RATE_LIMIT_ENABLED`). Ablehnung → **429** mit
    deutschem Text + `Retry-After`-Header; Stichproben (`AUDIT_SAMPLE_RATE`)
    der Ablehnungen landen im Audit-Log.
  - `admin.py` — `ensure_admin_key()` (Env `ADMIN_API_KEY` oder einmalig
    generiert + persistiert in `data/.admin_key`, Modus 0600, **einmalig**
    auf stdout, danach nie geloggt) und `require_admin()`-Dependency
    (`X-Admin-Key`, `hmac.compare_digest`, 401 + Audit bei Fehlversuch).
  - `audit.py` — `log_audit()` / `hash_ip()` (SHA-256 gekürzt, keine Roh-IPs).
- **`app/ai/quota.py` (neu):** `check_and_consume_quota()` zählt echte
  Provider-Calls pro UTC-Tag in Tabelle `ai_usage` (überlebt Neustarts);
  `QuotaGuardedProvider` + `QuotaExhausted`; `is_real_provider()` (Mock
  zählt nie). Bei Cap-Überschreitung antwortet der Mock — ehrlich
  gekennzeichnet (`quota_fallback: true`, deutscher Hinweis, echter
  Workflow-Event `llm_quota_fallback`).
- **`app/db/schema.sql`:** Tabellen `audit_log` (append-only) und
  `ai_usage` — `CREATE TABLE IF NOT EXISTS`, bestehende DBs migrieren
  automatisch via `init_db`.
- **`app/config.py`:** neue Settings (Admin-Key, Rate-Limit-Schalter +
  Limits, Audit-Sampling); `rate_limit_placeholder` entfernt.
- **`app/main.py`:** `@app.on_event("startup")` → `lifespan`-Handler
  (Deprecation-Warning behoben); `RateLimitMiddleware` registriert;
  CORS erlaubt zusätzlich Header `X-Admin-Key`.
- **`app/api/chat.py`:** Validierungsfehler → **400** mit deutschem Text
  (statt 422/englisch); Quota-Verbrauch *vor* Pipeline-Start (keine
  halb geschriebenen Conversations); `actor_ip` an Pipeline;
  `result.provider = "mock"` bei Fallback.
- **`app/api/demo.py`:** `POST /api/demo/reset` erfordert `require_admin`
  (401 ohne/falscher Key); jeder Reset wird audit-geloggt; Audit-Tabelle
  wird vom Reset nicht angefasst.
- **`app/services/pipeline.py`:** optionaler `actor_ip`-Parameter;
  `ticket_created`- und `escalated`-Events werden audit-geloggt;
  `quota_fallback`-Event im Pipeline-Verlauf (ehrlich, da wirklich
  ausgeführt).
- **`app/validators.py`:** Fehlermeldungen auf Deutsch (kundenorientiert),
  weiterhin generisch (keine Internals).
- **`.gitignore`:** `.admin_key` aufgenommen.

### Frontend

- **`lib/api.ts`:** `resetDemo(adminKey?)` sendet `X-Admin-Key`;
  Fehlermeldungen bevorzugen das deutsche `message`-Feld;
  `ChatResponse` kennt `quota_fallback`/`quota_note`. Kein
  `dangerouslySetInnerHTML` (verifiziert: keine Vorkommen);
  Fehler-States rendern nur kontrollierte Backend-Texte.
- **`app/page.tsx`:** Passwort-Feld für den Admin-Schlüssel (nur im
  Memory, nie persistiert) neben „Demo zurücksetzen"; 401 zeigt den
  deutschen Backend-Text; Quota-Fallback-Hinweis als Banner.
- **`app/dashboard/page.tsx`:** neuer Abschnitt „Sicherheit &
  Datenschutz (Demo)": simulierte Daten, keine echten Retouren/
  Zahlungen, Nutzungsbegrenzung, KI-Kontingent, Admin-Schutz.
- `npm run build` grün (Next.js 16.4.0, TypeScript ok, 7 Routen).

## Tests — tatsächliche Ergebnisse

```
86 passed in 1.24s   (backend/.venv/bin/python -m pytest tests/ -q)
```

- 67 Phase-1–6-Tests weiterhin grün (3 mussten an Phase-7-Verhalten
  angepasst werden: Admin-Key beim Reset, deutsche Validierungstexte).
- 19 neue Tests in `tests/test_phase7_security.py`, alle grün:
  Sliding-Window-Unit (2), Quota-Unit (3: Zählung, Guard-Enforcement,
  Tageswechsel), Admin-Key-Generierung (einmalig/persistiert/0600),
  IP-Hash, Order-Enumeration (20 IDs, kein Leak), Rapid-Fire
  (5×200→429→Erholung), Tages-Cap, Lese-Limit, Oversized→400,
  Empty→400, Body→413, Reset-Auth (401/401/200 + Audit),
  Reset-Rate-Limit, KI-Quota-Fallback (Stub, Cap 2 → Mock mit ehrlichem
  Event), Audit für Tickets/Eskalationen, Audit überlebt Reset.

## Live-Verifikation (uvicorn, frische DBs — echte Auszüge)

```
# Rate Limit (5/Min.): 8× POST /api/chat
req 1 -> 200 | req 2 -> 200 | req 3 -> 200 | req 4 -> 200 | req 5 -> 200
req 6 -> 429 | req 7 -> 429 | req 8 -> 429
HTTP/1.1 429 Too Many Requests
retry-after: 60
{"error":"rate_limit_exceeded","message":"Zu viele Anfragen. Bitte warten Sie
einen Moment und versuchen Sie es erneut."}

# Admin-Auth
POST /api/demo/reset (ohne Key)      -> 401 {"detail":"Admin-Schlüssel fehlt oder ist ungültig."}
POST /api/demo/reset (falscher Key)  -> 401 (identisch)
POST /api/demo/reset (korrekter Key) -> 200 {"status":"reset","demo_store":"demo-muster-shop"}

# Input-Härtung
5000 Zeichen  -> 400 {"detail":"Ihre Nachricht ist zu lang (maximal 2000 Zeichen)."}
Leere Nachricht -> 400 {"detail":"Bitte geben Sie eine Nachricht ein — leere Nachrichten
können nicht verarbeitet werden."}

# Enumeration
#99001 -> order: null | "Die Bestellung #99001 wurde nicht gefunden. …"
#99002 -> order: null | "Die Bestellung #99002 wurde nicht gefunden. …"
#99003 -> order: null | "Die Bestellung #99003 wurde nicht gefunden. …"

# Admin-Key-Generierung (ohne ADMIN_API_KEY)
stdout (einmalig): "ADMIN_API_KEY generated and saved to …/data/.admin_key
(mode 0600). … Key: <32-Byte-Key>"
Datei: -rw------- ; zweiter Start: keine erneute Ausgabe.

# Audit-Log (live DB)
admin_auth_failure | ip_hash: 12ca17b49af22894 | store: None   (2×)
demo_reset         | ip_hash: 12ca17b49af22894 | store: demo-muster-shop
```

## Was ist / ist nicht produktionsreif

**Bereit für die öffentliche Demo (Phase 8):** Abuse-Schutz steht —
Rate Limiting, Admin-Key, KI-Kostenbremse, Audit-Log, ehrliche Fehler.
**Explizit NICHT produktionsreif für echte Kundendaten:** kein
Auth-Konzept am Chat (by design offen), SQLite Single-File, In-Memory
Limiter (Zähler bei Neustart weg), Admin-Key als Datei statt Secret-Store,
kein DSGVO-/PII-Konzept — siehe `docs/SECURITY.md` §1/§6.

## Verbleibende Punkte / bekannte Einschränkungen

1. In-Memory-Limiter verliert Zähler bei Neustart; bei mehreren
   Backend-Instanzen wäre ein geteilter Speicher nötig (derzeit 1 Instanz).
2. `audit_log` wächst unbegrenzt — für die Demo ok, Retention erst bei
   Pilotkunden definieren.
3. `backend/data/.admin_key` wurde bei der Live-Verifikation generiert
   (git-ignoriert, Modus 0600) — auf Hetzner gehört `ADMIN_API_KEY` als
   echte Env-Variable gesetzt (Phase-8-Checkliste in SECURITY.md).
4. Frontend-Reset: Admin-Key muss der Operator manuell eintippen (Memory
   only) — bewusst so, kein Key im Browser-Speicher.

## Sicherheit

Siehe `docs/SECURITY.md`: Threat Model, Schutzmaßnahmen, Abuse-Test-
Tabelle, Pre-Launch-Checkliste, Env-Referenz. Secret-Scan des Diffs:
sauber (einziger Treffer: `type="password"` im Frontend-Formular).

## Kosten

**0 €** zusätzlich: stdlib + SQLite, keine neuen Dienste.

## Deployment-Status

Nicht deployed (Phase 8). Blocker unverändert: Vercel-OAuth und
Hetzner-Deploy-Key erfordern Shahids Aktionen. Neu in Phase 8:
`ADMIN_API_KEY` als Env auf dem Backend setzen, `CORS_ORIGINS` auf die
Vercel-Domain einengen.

## Nächste Phase

**Phase 8** — Public Demo Deploy (Vercel + Hetzner), URL live verifizieren.
