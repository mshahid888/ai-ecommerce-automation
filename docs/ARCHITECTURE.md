# Architektur — AI E-Commerce Automation (Phasen 1–2)

> **Phase 2 (2026-10-09):** Der Chat-Workflow ist vollständig implementiert
> (deutsche Mock-Klassifikation, Bestell-Lookup, Produktkatalog,
> Retouren-Triage, Eskalation). Die unten stehenden Abschnitte markieren,
> was in Phase 2 real wurde; Stubs sind als solche gekennzeichnet.

## Schichtenübersicht

```
┌─────────────────────────────────────────────────────────────┐
│  frontend/  Next.js 16 (App Router) + TypeScript + Tailwind │
│  / (Chat) · /dashboard · /tickets · lib/api.ts (HTTP-Client)│
│  Keine Secrets. Backend-URL nur via NEXT_PUBLIC_API_URL.    │
└───────────────────────────┬─────────────────────────────────┘
                            │  HTTP / JSON
┌───────────────────────────▼─────────────────────────────────┐
│  backend/  Python 3.12 · FastAPI + Pydantic v2 · uvicorn     │
│                                                             │
│  app/api/        Routen: chat, tickets, events, demo, deps   │
│       │                                                     │
│  app/services/   Pipeline: validate → classify → plan →     │
│       │          respond → log (jeder Schritt = DB-Event)    │
│       │                                                     │
│  app/ai/         Provider-Abstraktion (LLMProvider-Interface)│
│       │          mock · openai_compatible · gemini           │
│       │                                                     │
│  app/rules/      Deterministische Geschäftslogik (KEIN LLM): │
│       │          escalation (echt) · order_rules (echt, P2) ·      │
│       │          return_policy (deterministische Engine, P2) ·    │
│       │          product_rules (Katalogsuche, P2)                 │
│       │                                                     │
│  app/db/         SQLite (stdlib) + Repository-Schicht:       │
│                  database · schema.sql · repositories · seed  │
│                  Alle Geschäftstabellen tragen store_id.     │
│  app/validators.py  Input-Caps (2000 Zeichen / 64 KiB)       │
└─────────────────────────────────────────────────────────────┘
```

## Pipeline (Phase 2 — vollständig, deterministisch)

```
Kundennachricht
  → 1. Input-Validierung            (validators.py — Caps, Typen)
  → 2. Intent-Klassifikation        (ai/providers.py — LLM NUR hier;
                                     Mock: deutsche Keyword-Regeln)
  → 3. Entitäts-Extraktion          (Regex #?\d{4,6} + Normalisierung,
                                     services/pipeline.py)
  → 4. Geschäftsregeln              (rules/ — reines Python, KEIN LLM:
                                     order_rules, product_rules,
                                     return_policy, escalation)
  → 5. Autorisierter Datenzugriff    (repositories — immer mit store_id;
                                     Orders, Produkte, Policies)
  → 6. Aktionsauswahl               (services/pipeline.py — je Intent:
                                     order_status / product_question /
                                     return_request / escalation)
  → 7. Antwort-Generierung          (deutsche Templates, ausschließlich aus
                                     verifizierten Demo-Daten; Unbekanntes →
                                     ehrliche Klärung/Eskalation)
  → 8. Output-Validierung           (keine erfundenen Daten: Antworten werden
                                     nur aus DB-Zeilen gebaut)
  → 9. Event-Logging                (workflow_events — nur echte Schritte)
  → UI-Update (Timeline aus echten Events)
```

**Eiserne Regel:** Das LLM interpretiert Sprache und liefert strukturierte
Klassifikation. Es führt **niemals** Aktionen aus: kein DB-Zugriff, keine
Statuswechsel, keine Retourenfreigabe, keine Eskalationsentscheidung ohne
deterministische Regel. Alle Schreibvorgänge und Policy-Entscheidungen laufen
in `rules/` und `services/` als testbares Python.

Jeder Timeline-Eintrag im Frontend entspricht einer tatsächlich ausgeführten
Backend-Operation (DB-Zeile in `workflow_events`). Schlägt der Provider fehl,
gibt es einen ehrlichen Fehlerzustand — keinen erfundenen Erfolg.

## KI/Business-Logik-Trennung

| Aufgabe | Wo | LLM beteiligt? |
|---|---|---|
| Nachricht validieren | `validators.py` | nein |
| Absicht erkennen | `ai/providers.py` | **ja** (einzige Stelle) |
| Bestellung nachschlagen | `db/repositories.py` | nein |
| Eskalieren? | `rules/escalation.py` | nein (Regel: Konfidenz < 0.6 o. Beschwerde/Mensch) |
| Retourenberechtigung | `rules/return_policy.py` | nein (deterministische Engine gegen `store_policies`, vorläufige Prüfung; Freigabe = Mensch) |
| Produkt suchen / Attribut beantworten | `rules/product_rules.py` | nein (Token-Match über Katalog, Attribute nur aus `attributes_json`) |
| Antworttext formulieren | `services/pipeline.py` (deutsche Templates aus DB-Daten) | nein (Mock: nur Klassifikation) |
| Antworttext formulieren | `services/pipeline.py` (Phase 3+: Provider) | ja, aber validiert |
| Events/Tickets schreiben | `db/repositories.py` | nein |

## Provider-Abstraktion

```python
class LLMProvider(ABC):
    def classify(self, message: str) -> str: ...   # roher JSON-String

get_provider(config)  # via LLM_PROVIDER: mock | openai_compatible | gemini
```

- **mock** (Standard): deterministische, regelbasierte Demo-Klassifikation.
  Kein Netzwerk, keine Kosten. Vertrag: JSON mit
  `intent, confidence, order_id/order_ref, requires_human, reason`
  (5 Felder — exakt der Vertrag des Vorgängerprojekts
  `ai-customer-support-automation`).
- **openai_compatible**: OpenAI-Style `/chat/completions` via stdlib-urllib,
  `temperature=0.0`, `max_tokens=300`. Key nur aus `LLM_API_KEY`.
- **gemini**: nutzt das verbundene `custom.google-gemini`-Credential über den
  `dynamic_credentials`-Helper (`add_surrogate_to_request` +
  `read_json_response`), strikt begrenzt auf `generativelanguage.googleapis.com`.
  Der Schlüssel steht **nie** in Chat, Env, Dateien oder Code — er wird zur
  Laufzeit als kurzlebiges Surrogat angehängt. Der Import ist abgesichert, damit
  das Backend ohne den Helper lauffähig bleibt (Fehler nur bei tatsächlicher
  Verwendung → ehrlicher 502-JSON-Pfad in `/api/chat`).

## Datenmodell (SQLite, Mehrmandanten-fähig)

Alle Geschäftstabellen tragen `store_id TEXT NOT NULL REFERENCES stores(id)`:

`stores · products · orders · customers · conversations · messages · tickets ·
return_requests · workflow_events · integration_credentials · store_policies`

- Indizes auf allen `store_id`-Spalten.
- Die Repository-Schicht nimmt `store_id` als Pflichtparameter; jede Abfrage
  filtert danach → **kein Cross-Store-Zugriff möglich** (per Test verifiziert).
- Demo-Seed (`db/seed.py`): Shop `demo-muster-shop` („Muster-Shop GmbH",
  `is_demo=1`), 4 Produkte (Trinkflasche „AquaPure 750" mit
  `spuelmaschinengeeignet=true` u.a. Attributen), 2 fiktive Kunden,
  Bestellungen #10482 (versendet, DHL, fiktive Referenz `DEMO-TRK-10482`),
  #10483 (in Bearbeitung), #10471 (zugestellt), #10479 (verzögert),
  2 Policies (`returns`: 30-Tage-Frist, Bedingungen, Ausnahmen,
  Rücksendeadresse; `shipping`: Kosten, Lieferzeit). Policies sind explizite
  Konfigurationszeilen — niemals in Prompts hardcodiert.
  `POST /api/demo/reset` löscht und seedet **nur** Demo-Zeilen (`is_demo=1`).

## API-Verträge (Phase 1)

- `GET /health` → `{status, service, llm_provider, demo_mode}`
- `POST /api/chat` `{message, customer_id?, store_id?}` →
  `{conversation_id, intent, confidence, order_ref, answer, order,
   events[], ticket, provider, escalated}` (+ `reply_de`/`timeline`/
  `ticket_id` aus Kompatibilitätsgründen) · 422 bei ungültigem Payload ·
  413 bei >64 KiB · ehrliches Fehler-JSON bei Provider-Ausfall
- `GET /api/tickets[?store_id]` · `GET /api/tickets/{id}` → 404 wenn fremd/fehlend
- `GET /api/events[?store_id][&limit]` → neueste zuerst
- `POST /api/demo/reset` → nur mit `DEMO_MODE=true`, sonst 403

## Sicherheitsstand Phase 1 (vollständig erst Phase 7)

Vorhanden: Input-Caps, generische Fehlermeldungen (keine Stacktraces),
Demo-Isolation, keine Secrets im Frontend, keine echten Zahlungs-/Refund-Pfade.
Offen (Phase 7, Pflicht vor Public Deploy): Rate Limiting, Tages-Quotas,
Admin-API-Keys, Audit-Logging in DB, Aufzählschutz für Bestellungen.
