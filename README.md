# AI E-Commerce Automation (working title)

AI-gestützte Support- und Bestellautomatisierung für deutsche Onlineshops —
Phase 2: Demo-Store + deutschsprachiger Kundensupport-Chat, Ende-zu-Ende verdrahtet.

> **Demo-Umgebung – simulierte Daten.** Alles in diesem Projektstand läuft mit
> frei erfundenen Demo-Daten (Shop „Muster-Shop GmbH", fiktive Bestellnummern,
> fiktive Sendungsreferenzen). Keine echten Bestellungen, keine echten
> Kundendaten, keine echten Zahlungen.

## Was funktioniert (Phase 2, verifiziert)

- **Backend** (Python 3.12, FastAPI + Pydantic v2, SQLite, eigener venv):
  - `GET /health` — Status inkl. konfiguriertem LLM-Provider
  - `POST /api/chat` — vollständiger Workflow: validieren → Absicht
    klassifizieren (deutsche Mock-Regeln) → Bestellnummer extrahieren →
    deterministischer Datenzugriff + Geschäftsregeln → deutsche Antwort,
    die **nur** aus verifizierten Demo-Daten erzeugt wird. Antwortet mit
    `{answer, intent, order, ticket, events[]}`; jeder Event-Eintrag entspricht
    einer tatsächlich ausgeführten Operation
  - Szenarien: **Bestellstatus** (#10482 versendet/DHL, #10483 in Bearbeitung,
    #10471 zugestellt, #10479 verzögert), **Produkt fragen** (Katalog mit
    Attributen, z. B. AquaPure 750 spülmaschinengeeignet), **Retouren-Triage**
    (deterministische 30-Tage-Prüfung aus `store_policies`, Retourenantrag +
    Ticket, keine echte Retoure, keine Rückerstattung), **Eskalation**
    (Beschwerde/Mensch → Ticket mit Priorität und Eskalationsgrund)
  - Unbekannte Bestellung/Produkt/Attribut → ehrliche deutsche Klärung oder
    Angebot zur Mitarbeiter-Übergabe — niemals erfundene Daten
  - `GET /api/tickets`, `GET /api/tickets/{id}` — Support-Tickets lesen
  - `GET /api/events` — Workflow-Ereignisse (neueste zuerst)
  - `POST /api/demo/reset` — setzt **nur** die Demo-Daten zurück (Neu-Seed)
  - Provider-Abstraktion: `mock` (Standard, deterministisch, offline) |
    `openai_compatible` | `gemini` (Secure-Vault-Surrogat, nur
    `generativelanguage.googleapis.com`; Schlüssel nie in Code/Env/Dateien)
  - Mehrmandanten-Schema: alle Geschäftstabellen tragen `store_id`; Repository-
    Schicht erzwingt Store-Isolation in jeder Abfrage
  - CORS für die Frontend-Dev-Origin (`CORS_ORIGINS`)
- **Frontend** (Next.js 16 App Router, TypeScript, Tailwind CSS v4, deutsche UI):
  - `/` — Kundensupport-Chat: Eingabe, Senden, 4 Beispiel-Fragen (die exakten
    Demo-Szenarien), Ladezustand („Anfrage wird bearbeitet …"), Fehlerzustand,
    Antwort-Bubbles, Ticket-Hinweis bei erstelltem Ticket, Aktivitätsverlauf
    aus den **echten** Backend-Events, Demo-Banner, „Demo zurücksetzen"
    (mobil responsiv, keine Robot-Grafiken)
  - `/dashboard` — Operations-Dashboard mit **echten DB-Kennzahlen**
    (Unterhaltungen, Nachrichten, Offene Tickets, Eskalationen),
    Anliegen-Verteilung als ehrliche Balkenliste mit echten Zählern,
    Aktivitätenliste aus den tatsächlichen Workflow-Events (alle als
    Demo-Daten gekennzeichnet)
  - `/tickets` — Ticket-Tabelle (ID, Anliegen, Status, Priorität,
    Bestellung, Erstellt), klickbar → Ticket-Detailseite mit
    Zusammenfassung, Eskalationsgrund, empfohlener Aktion, verknüpfter
    Unterhaltung und Ereignisverlauf
- **Tests:** 67 pytest-Tests, alle grün (Health, Provider-Vertrag, Validatoren,
  Store-Isolation, Demo-Reset, Chat-Pipeline: alle 4 Szenarien + Reset,
  Phase 3: 11 Intents, Konfidenz-Kalibrierung, Eskalations-Policy,
  strikte Klassifikations-Validierung inkl. Stub-Provider-Fallbacks,
  deutsche Edge Cases, Phase 6: Dashboard-Summary, Ticket-Detail,
  Unterhaltungen, Store-Isolation der Ops-Endpunkte).

## Phase 6 (verifiziert) — Ops-Dashboard + Ticket-Detail + Event-Timeline

- `GET /api/dashboard/summary` → echte DB-Zähler: Unterhaltungen,
  Nachrichten, offene/gesamte Tickets, Eskalationen, Anliegen-Verteilung
  (aus `intent_classified`-Events), neueste 15 Workflow-Events — alles als
  Demo-Daten gekennzeichnet
- `GET /api/tickets[?status=open]` + `GET /api/tickets/{id}` →
  Ticket-Detail mit verknüpften Nachrichten und Ereignisverlauf
- `GET /api/conversations` + `GET /api/conversations/{id}` →
  Unterhaltungsliste mit `last_intent` und Nachrichten+Timeline im Detail
- Frontend: `/dashboard` mit echten Kennzahlen, ehrlicher Anliegen-Verteilung
  und Aktivitätenliste; `/tickets` mit klickbarer Tabelle und Detailseite
  (Eskalationsgrund, empfohlene Aktion, Unterhaltung, Timeline);
  Chat-Seite unverändert
- Alle Ops-Endpunkte read-only und strikt store-isoliert (per Test verifiziert)

## Phase 3 (verifiziert) — Klassifikationstiefe + Eskalations-Policy

- 11 Intents: `order_status, product_question, return_request, complaint,
  human_support, shipping_info, payment_question, product_availability,
  order_cancel, greeting, unknown` (Mock: deutsche Keyword-Regeln)
- `shipping_info`: Versandkosten/-zeit aus der `shipping`-Policy
  (4,99 €, frei ab 50 €, 2–4 Werktage, DHL/Hermes)
- `payment_question`: Zahlungsarten aus der `payments`-Policy
  (PayPal, Kreditkarte, Kauf auf Rechnung, Vorkasse)
- `product_availability`: Demo-Bestand pro Produkt (`bestand_stueck`),
  ehrlich „nicht auf Lager" bei 0
- `order_cancel` → ALWAYS_HUMAN: Ticket + Bestellkontext, keine automatische
  Stornierung
- `greeting`: freundliche Begrüßung, kein Ticket, keine Eskalation
- Strikte Validierung (`services/classification.py`, Ansatz aus dem
  Vorgängerprojekt): Intent im Enum, Konfidenz 0–1, Bestellnummer-Regex —
  **jeder** Fehler → `safe_fallback()` → Mensch. Niemals Crash, niemals Raten.
- Eskalations-Policy: `ALWAYS_HUMAN = {complaint, order_cancel,
  human_support, unknown}`, Konfidenz < 0,6 → Ticket mit Grund
  `"low_confidence"` + ehrliche deutsche Erklärung
- Validiertes Schema (intent, confidence, order_ref, product_hint,
  return_reason, language) — Downstream nutzt nur dieses, nie rohen
  Modell-Text
- Gemini-Provider implementiert (Skill-Credential-Pattern); Live-Test in
  dieser Umgebung durch Modell-Überlastung (HTTP 503) blockiert — Mock
  bleibt Default

## Was noch fehlt (ehrlich)

- `services/intent.py::classify()` bleibt ein dokumentierter Stub (die Pipeline
  nutzt den konfigurierten Provider).
- Mehrstufige Dialoge (Kontext über Nachrichten hinweg) sind noch nicht
  implementiert — jede Nachricht startet eine eigene Konversation.
- Phase 7 (verifiziert) — Rate Limiting, KI-Tageskontingent, Admin-Key,
  Audit-Log, Input-Härtung: siehe `docs/PHASE-7-REPORT.md` und
  `docs/SECURITY.md`. Vor Phase 8 (Public Deploy): `ADMIN_API_KEY` als
  echte Env-Variable auf dem Backend setzen, `CORS_ORIGINS` einengen.

## Projekt starten

### Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # optional; Standardwerte laufen ohne .env
.venv/bin/python -m uvicorn app.main:app --port 8000
# -> http://127.0.0.1:8000/health
```

Die Demo-Daten (Shop „Muster-Shop GmbH", Bestellung #10482 u.a.) werden beim
Start automatisch angelegt (`backend/data/demo.db`, wird nicht committet).

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # optional
npm run dev                  # -> http://localhost:3000
```

`NEXT_PUBLIC_API_URL` zeigt auf das Backend (Standard `http://127.0.0.1:8000`).
**Keine Secrets im Frontend-Code.**

### Tests

```bash
cd backend && .venv/bin/python -m pytest -q     # 33 Tests
cd ../frontend && npm run build && npm run lint
```

## Umgebungsvariablen (Backend)

| Variable | Standard | Bedeutung |
|---|---|---|
| `LLM_PROVIDER` | `mock` | `mock` \| `openai_compatible` \| `gemini` |
| `LLM_MODEL` | `gemini-3.8-flash` | Modellname für echte Provider |
| `LLM_API_KEY` | – | nur für `openai_compatible`; nie committen |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | nur für `openai_compatible` |
| `DATABASE_URL` | `sqlite:///./data/demo.db` | SQLite-Pfad |
| `DEMO_MODE` | `true` | `POST /api/demo/reset` nur wenn `true` |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Komma-getrennte Origins für das Frontend |
| `CONFIDENCE_THRESHOLD` | `0.6` | Konfidenzschwelle für Eskalation |
| `LLM_MAX_TOKENS_PER_REQUEST` | `300` | Token-Ceiling pro echtem Provider-Aufruf |
| `LLM_DAILY_REQUEST_CAP` | `500` | Tages-Quota echter KI-Calls (Phase 7: durchgesetzt, Mock-Fallback bei Überschreitung) |
| `ADMIN_API_KEY` | (generiert) | Admin-Key für `POST /api/demo/reset` (`X-Admin-Key`-Header); nie committen |
| `RATE_LIMIT_ENABLED` | `true` | Rate Limiting an/aus |
| `RL_CHAT_PER_MINUTE` | `30` | Chat-Limit pro IP/Minute |
| `RL_CHAT_PER_DAY` | `200` | Chat-Limit pro IP/Tag |
| `RL_READ_PER_MINUTE` | `60` | Lese-Limit pro IP/Minute |
| `RL_RESET_PER_HOUR` | `5` | Reset-Limit pro IP/Stunde |

## Struktur

```
backend/    FastAPI: app/{api,services,ai,rules,db}  (Schichten s. docs/ARCHITECTURE.md)
frontend/   Next.js: app/{page (Chat),dashboard,tickets}, components/, lib/api.ts
docs/       PHASE-0-REPORT.md  ARCHITECTURE.md  GITHUB-SETUP.md
```

## Roadmap

Phasen 2–11 laut `docs/PHASE-0-REPORT.md` §12: Demo-Store-Seed + Chat-UI (2),
deutsche Intent-Klassifikation (3), Bestell-/Produkt-Lookup (4), Retouren-Triage
(5), Dashboard + Timeline (6), Security/Hardening (7), öffentliches Demo-Deploy
(8), Shopify-Adapter (9), Video + Sales-Docs (10), Roadmap WooCommerce u.a. (11).

## Kosten

**0 €** laufend: SQLite, Mock-Provider, lokale Entwicklung. Keine kostenpflichtigen
Dienste eingeführt.
