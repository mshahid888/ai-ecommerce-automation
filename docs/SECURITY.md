# SECURITY.md — AI E-Commerce Automation (Demo)

**Stand:** Phase 7, 2026-10-09. Dies ist die Sicherheitsdokumentation der
öffentlichen Demo, kein Audit-Zertifikat.

## 1. Threat Model

**Was die Demo ist:** eine öffentlich erreichbare Demo-Website. Jeder
Besucher kann ohne Konto chatten. Angreifer-Modell: neugierige Besucher,
automatisierte Scanner, Skript-Kiddies — keine gezielten APTs.

**Was es zu schützen gilt:**

| Asset | Schutz |
|---|---|
| Demo-Datenbank (SQLite) | Keine echten Kundendaten enthalten; Store-Isolation per `store_id` (Phase 6, getestet) |
| KI-Budget | Tages-Kontingent `LLM_DAILY_REQUEST_CAP` (Standard 500); nur echte Provider zählen |
| Server-Verfügbarkeit | Rate Limiting pro IP; Input-Caps; Timeouts beim LLM-Provider |
| Admin-Funktionen (Demo-Reset) | Serverseitiger Admin-Key (`X-Admin-Key`, Constant-Time-Vergleich) |
| Audit-Protokoll | Append-only Tabelle `audit_log`; überlebt Demo-Resets |

**Explizit NICHT geschützt / nicht vorhanden (by design):**

- Kein Login/Auth am öffentlichen Chat — der Chat ist absichtlich offen.
- SQLite als Single-File-DB — kein Hochverfügbarkeits- oder
  Backup-Konzept über Datei-Kopien hinaus.
- Keine PII-Verarbeitung — es gibt keine echten Kundendaten; Demo-Namen
  sind fiktiv.
- Keine DSGVO-Auftragsverarbeitung — für den Produktivbetrieb mit echten
  Kundendaten wären AV-Verträge, TOMs und ein DPA-Review nötig.

## 2. Was Phase 7 implementiert

### Rate Limiting (`app/security/rate_limit.py`, `middleware.py`)
In-Memory Sliding-Window pro Client-IP (kein Redis nötig):
- `POST /api/chat`: 30/Min. UND 200/Tag (`RL_CHAT_PER_MINUTE`, `RL_CHAT_PER_DAY`)
- `POST /api/demo/reset`: 5/Std. (`RL_RESET_PER_HOUR`)
- `GET /api/*`: 60/Min. (`RL_READ_PER_MINUTE`)
- Master-Schalter: `RATE_LIMIT_ENABLED` (Standard: an)

Ablehnung → **429** mit deutschem Text und `Retry-After`-Header.
Ein Stichproben-Anteil der Ablehnungen landet im Audit-Log
(`AUDIT_SAMPLE_RATE`, Standard 5 %).

### Admin-Key (`app/security/admin.py`)
- Quelle: `ADMIN_API_KEY` (Umgebung) oder einmalig generiert
  (`secrets.token_urlsafe(32)`, Datei `backend/data/.admin_key`, Modus 0600,
  `.admin_key` ist git-ignoriert).
- Bei Generierung **einmalig** auf stdout ausgegeben, danach nie geloggt.
- Prüfung mit `hmac.compare_digest` (Constant-Time) gegen Header `X-Admin-Key`.
- Fehlversuche → 401 + Audit-Log (`admin_auth_failure`).
- Erforderlich für `POST /api/demo/reset` und künftige Admin-Endpunkte.

### KI-Tageskontingent (`app/ai/quota.py`)
- Zähler in SQLite-Tabelle `ai_usage` (pro UTC-Tag, pro Provider) — überlebt
  Neustarts.
- Nur echte Provider zählen; Mock-Aufrufe zählen nie.
- Bei Überschreitung: Antwort kommt vom deterministischen Mock —
  `quota_fallback: true` + ehrlicher deutscher Hinweis + echter
  Workflow-Event `llm_quota_fallback`. Der Chat schlägt nie fehl.

### Audit-Logging (`app/security/audit.py`, Tabelle `audit_log`)
Append-only: `created_at`, `actor_ip_hash` (SHA-256, gekürzt — keine Roh-IPs),
`action`, `details_json`, `store_id`. Protokolliert:
- `demo_reset` — jeder Demo-Reset (mit Store-ID)
- `admin_auth_failure` — jeder fehlgeschlagene Admin-Versuch
- `rate_limit_hit` — stichprobenartig (s. o.)
- `ticket_created` — jede Ticket-Erstellung (aus der Pipeline)
- `escalated` — jede Eskalation an Mitarbeiter

Der Demo-Reset fasst `audit_log` **nicht** an — Missbrauchsspuren überleben.

### Input-Härtung
- Nachricht: max. 2000 Zeichen (`MAX_MESSAGE_LENGTH`), Body max. 64 KiB.
- Leere/Whitespace-Nachrichten → **400** mit deutschem Text
  („Bitte geben Sie eine Nachricht ein …").
- Zu lange Nachrichten → **400** mit deutschem Text.
- Keine Stack-Traces an Clients: Fehlerantworten sind kontrollierte,
  generische deutsche Texte; FastAPI läuft ohne Debug-Modus.
- Frontend: kein `dangerouslySetInnerHTML`; Fehler-States rendern nur die
  kontrollierten Backend-Texte, nie Roh-Tracebacks.

### Lifespan statt `on_event`
`@app.on_event("startup")` (deprecated) wurde durch einen
`lifespan`-Handler ersetzt — keine Deprecation-Warnings mehr.

## 3. Abuse-Test-Ergebnisse (Phase 7)

Alle Tests in `backend/tests/test_phase7_security.py`, **19/19 grün**;
Gesamt-Suite: **86/86 grün**.

| Angriff | Erwartung | Ergebnis |
|---|---|---|
| Order-Enumeration (20 unbekannte IDs `#99000`–`#99019`) | „nicht gefunden", `order: null`, keine Daten | ✅ alle 200 mit ehrlicher Klärung; keine `orders`-Rows, keine Detail-Leaks in Assistant-Nachrichten |
| Oversized (5000 Zeichen) | 400, deutsch | ✅ `{"detail": "Ihre Nachricht ist zu lang (maximal 2000 Zeichen)."}` |
| Leere Nachricht | 400, deutsch | ✅ `{"detail": "Bitte geben Sie eine Nachricht ein …"}` |
| Rapid-Fire (8 Chats, Limit 5/Min.) | 429 nach Schwelle + `Retry-After` | ✅ 5×200, dann 429 mit `Retry-After: 60`; nach Reset wieder 200 |
| Tages-Cap (200/Tag, auf 3 gesetzt) | 429 beim 4. Request | ✅ `[200, 200, 200, 429]` |
| Leserequests (Limit 4/Min.) | 429 | ✅ 4×200, 2×429 |
| Reset ohne Key / falscher Key | 401 | ✅ 401 + `admin_auth_failure` im Audit-Log |
| Reset mit Key | 200 + Daten wiederhergestellt | ✅ `{"status":"reset"}`; 4 Demo-Bestellungen; `demo_reset` auditiert |
| Reset-Rate-Limit (2/Std.) | 429 beim 3. | ✅ |
| KI-Quota (Stub, Cap 2) | 2× echt, dann Mock-Fallback | ✅ 3. Request: `provider: "mock"`, `quota_fallback: true`, deutscher Hinweis, Event `llm_quota_fallback`, nur 2 Provider-Calls gezählt |
| Audit-Nachweis | Rows für Reset + Ticket + Eskalation | ✅ `demo_reset`, `admin_auth_failure` (2×), `ticket_created`, `escalated`; IPs nur gehasht |
| Audit überlebt Reset | Rows bleiben | ✅ |

Live-Verifikation gegen `uvicorn` (127.0.0.1:8123/8124, frische DBs):
- `POST /api/chat` ×8 bei Limit 5/Min. → `200,200,200,200,200,429,429,429`;
  429-Body `{"error":"rate_limit_exceeded","message":"Zu viele Anfragen. …"}`,
  Header `retry-after: 60`.
- Reset: ohne Key → 401, falscher Key → 401, korrekter Key → 200.
- Oversized/Empty → 400 mit deutschem Text (auf Instanz mit hohem Limit).
- Enumeration `#99001`–`#99003` → `order: null`, „nicht gefunden".
- Admin-Key-Generierung: einmalige stdout-Ausgabe, Datei mit Modus 0600,
  zweiter Start liest Datei ohne erneute Ausgabe.

## 4. Pre-Launch-Checkliste (Stand Phase 7)

- [x] Rate Limiting aktiv (konfigurierbar via Env)
- [x] Admin-Key für Demo-Reset (generiert/persistiert, 401 ohne Key)
- [x] KI-Tageskontingent mit ehrlichem Fallback
- [x] Audit-Log (append-only, IP-gehasht)
- [x] Input-Caps + deutsche 400er
- [x] Keine Traceback-Leaks; kein `dangerouslySetInnerHTML`
- [x] `on_event`-Deprecation behoben
- [x] Frontend-Sicherheitshinweis („Sicherheit & Datenschutz (Demo)")
- [x] Abuse-Tests grün (19 neu + 67 Bestand)
- [ ] **Offen (Phase 8):** `ADMIN_API_KEY` als echte Env-Variable auf dem
      Hetzner-Backend setzen (statt generierter Datei); CORS-Origin auf die
      Vercel-Domain einengen (`CORS_ORIGINS`); Security-Header (HSTS etc.)
      je nach Deployment prüfen.
- [ ] **Nicht Demo-Scope:** WAF, DDoS-Schutz, Secrets-Rotation, PII-/DSGVO-
      Konzept für echte Kundendaten (erst bei Pilotkunden relevant).

## 5. Konfigurationsreferenz (Env)

| Variable | Standard | Zweck |
|---|---|---|
| `ADMIN_API_KEY` | (generiert) | Admin-Key für Mutations-Endpunkte |
| `RATE_LIMIT_ENABLED` | `true` | Rate Limiting an/aus |
| `RL_CHAT_PER_MINUTE` | `30` | Chat-Limit pro IP/Minute |
| `RL_CHAT_PER_DAY` | `200` | Chat-Limit pro IP/Tag |
| `RL_READ_PER_MINUTE` | `60` | Lese-Limit pro IP/Minute |
| `RL_RESET_PER_HOUR` | `5` | Reset-Limit pro IP/Stunde |
| `LLM_DAILY_REQUEST_CAP` | `500` | Echte KI-Calls pro Tag |
| `AUDIT_SAMPLE_RATE` | `0.05` | Anteil auditierter Rate-Limit-Hits |

## 6. Bekannte Einschränkungen

- In-Memory Rate Limiter: Zähler gehen bei Neustart verloren; bei mehreren
  Backend-Instanzen (derzeit nicht der Fall) müsste ein geteilter Speicher
  her.
- Der Admin-Key in `data/.admin_key` ist eine Datei — für den Produktiv-
  betrieb gehört er in einen Secret-Store (Hetzner: Env-Variable).
- Das Audit-Log wächst unbegrenzt — für die Demo ok; im Produktivbetrieb
  Rotation/Retention definieren.
