# AI E-Commerce Automation (working title)

AI-gestützte Support- und Bestellautomatisierung für deutsche Onlineshops —
Phase 1: funktionales Produkt-Skelett.

> **Demo-Umgebung – simulierte Daten.** Alles in diesem Projektstand läuft mit
> frei erfundenen Demo-Daten (Shop „Muster-Shop GmbH", fiktive Bestellnummern,
> fiktive Sendungsreferenzen). Keine echten Bestellungen, keine echten
> Kundendaten, keine echten Zahlungen.

## Was funktioniert (Phase 1, verifiziert)

- **Backend** (Python 3.12, FastAPI + Pydantic v2, SQLite, eigener venv):
  - `GET /health` — Status inkl. konfiguriertem LLM-Provider
  - `POST /api/chat` — nimmt eine Kundennachricht entgegen, validiert sie,
    klassifiziert die Absicht (Mock-Provider), erzeugt eine als Demo
    gekennzeichnete Antwort und protokolliert echte Workflow-Ereignisse
    (`message_received → intent_classified → action_planned → response_generated`)
  - `GET /api/tickets`, `GET /api/tickets/{id}` — Support-Tickets lesen
  - `GET /api/events` — Workflow-Ereignisse (neueste zuerst)
  - `POST /api/demo/reset` — setzt **nur** die Demo-Daten zurück (Neu-Seed)
  - Provider-Abstraktion: `mock` (Standard, deterministisch, offline) |
    `openai_compatible` | `gemini` (Secure-Vault-Surrogat, nur
    `generativelanguage.googleapis.com`; Schlüssel nie in Code/Env/Dateien)
  - Mehrmandanten-Schema: alle Geschäftstabellen tragen `store_id`; Repository-
    Schicht erzwingt Store-Isolation in jeder Abfrage
- **Frontend** (Next.js 16 App Router, TypeScript, Tailwind CSS v4, deutsche UI):
  - `/` — Kundensupport-Chat: Eingabe, Beispiel-Fragen, Senden, Lade-/Fehler-
    zustände, Aktivitätsverlauf (echte Backend-Events), Demo-Banner,
    „Demo zurücksetzen"
  - `/dashboard` — Platzhalter-Operations-Dashboard (Demo-Kennzahlen, echte
    Ereignisliste ab Backend)
  - `/tickets` — Ticket-Liste aus dem Backend (mit Empty State)
- **Tests:** 21 pytest-Tests, alle grün (Health, Provider-Vertrag, Validatoren,
  Store-Isolation, Demo-Reset).

## Was noch Stub ist (ehrlich)

- Die Chat-Antwort ist eine **gekennzeichnete Stub-Antwort** — der echte
  Antwort-Workflow (Bestell-Lookup, Produktkatalog, Retourenprüfung) kommt in
  Phase 3–5.
- `services/intent.py`, `rules/order_rules.py`, `rules/return_policy.py` sind
  dokumentierte Stubs mit Phasen-Verweis.
- Escalation-Regel (`confidence < 0.6` oder Beschwerde/Mensch gewünscht) ist
  dagegen **echte, getestete Logik**.
- Rate Limiting, Quotas, Admin-API-Keys kommen in Phase 7 (Pflicht vor
  öffentlichem Demo-Deploy in Phase 8).

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
cd backend && .venv/bin/python -m pytest -q     # 21 Tests
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
