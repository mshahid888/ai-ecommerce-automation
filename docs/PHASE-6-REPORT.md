# Phase 6 — Operations-Dashboard, Ticket-Detail, Event-Timeline

**Datum:** 2026-10-09
**Status:** Implementiert, getestet (67/67 grün), per curl + `npm run build` verifiziert,
als Phase 6 committet.

Phase 6 schließt die Ops-Sicht: Das Dashboard zeigt echte Datenbank-Kennzahlen
(keine Platzhalter mehr), Tickets sind klickbar mit Detailseite (Zusammenfassung,
Eskalationsgrund, empfohlene Aktion, verknüpfte Unterhaltung, Ereignisverlauf),
und neue Ops-Endpunkte liefern Unterhaltungen mit Nachrichten + Timeline.

## Was wurde implementiert

### Backend

- **`app/services/intent.py`**: `INTENT_LABELS_DE` — deterministische
  Intent→Deutsch-Tabelle + `intent_label_de()`-Helper. Kein LLM, keine
  erfundenen Labels.
- **`app/db/repositories.py`**:
  - `TicketRepository.list()` akzeptiert optional `status` (Filter
    `?status=open`).
  - Neu: `ConversationRepository` — `list()` (id, started_at, message_count,
    last_intent aus dem `intent_classified`-Event-Payload), `get()`,
    `messages()`, `events()` — alle store-isoliert; fremde Konversation
    → behandelt als nicht existent (→ 404).
- **`app/services/dashboard.py`** (neu): `build_summary()` — ausschließlich
  echte DB-Zähler: Unterhaltungen, Nachrichten (Join über conversations),
  offene/gesamte Tickets, Eskalationen (echte `escalated`-Events),
  `intents_breakdown` aus `intent_classified`-Events mit `status='done'`
  (fehlgeschlagene Klassifikationen tragen keinen Intent und werden
  ausgeschlossen, nicht geraten), `recent_events` (neueste 15 mit
  deutschem Label + Timestamp), `demo_data: true`.
- **`app/api/ops.py`** (neu, ersetzt `app/api/tickets.py`):
  - `GET /api/dashboard/summary`
  - `GET /api/tickets[?status=open][&limit]` (+ `intent_label_de`)
  - `GET /api/tickets/{id}` → Ticket + verknüpfte Nachrichten + Event-Verlauf
    (404 bei fremdem/fehlendem Ticket)
  - `GET /api/conversations` (+ `last_intent_label_de`)
  - `GET /api/conversations/{id}` → Nachrichten + echte Workflow-Timeline
    (404 bei fremder/fehlender Konversation)
  - Alle Endpunkte read-only, store-scoped per Query-Param `store_id`.
- **`app/main.py`**: `ops`-Router registriert; altes `tickets.py`-Modul entfernt
  (war funktional vom neuen Router abgedeckt und hätte Routen geshadowed).

### Frontend (deutsch, mobil responsiv, Demo-Banner global in `layout.tsx`)

- **`lib/api.ts`**: neue Typen (`DashboardSummary`, `IntentBreakdown`,
  `Conversation`, `ConversationDetail`, `TicketDetail` …) und Client-Funktionen
  (`getDashboardSummary`, `getConversations`, `getConversation`, `getTicket`,
  `getTickets(limit, status?)`).
- **`app/dashboard/page.tsx`**: neu aufgebaut mit echten Daten — 4 KPI-Karten
  (Unterhaltungen, Nachrichten, Offene Tickets, Eskalationen, jeweils mit
  „Demo-Daten"-Tag), Anliegen-Verteilung als ehrliche Balkenliste mit echten
  Zählern (beschriftet „Demo-Daten – keine Geschäftsauswertung"), echte
  Aktivitätenliste, Link zu den Tickets. Lade-, Fehler-, Empty-States.
- **`app/tickets/page.tsx`**: vollständige Tabelle (Ticket-ID, Anliegen,
  Status, Priorität, Bestellung, Erstellt), Zeilen klickbar →
  `/tickets/[id]`; „Nur offene anzeigen"-Umschalter nutzt `?status=open`.
- **`app/tickets/[id]/page.tsx`** (neu, Server-Komponente) +
  **`TicketDetailView.tsx`** (Client-Komponente): Zusammenfassung,
  Eskalationsgrund, empfohlene nächste Aktion (deterministisch gespeicherter
  Wert aus der Pipeline), verknüpfte Unterhaltung (Kunde/Assistent-Bubbles),
  Ereignisverlauf als Timeline. 404-State bei unbekannter ID.
- **Chat-Seite (`app/page.tsx`)**: unverändert, funktioniert weiter.
- **Footer**: Phase-2-Text → Phase 6.

Next.js-16-Notiz: `/tickets/[id]` nutzt `export const instant = false` (Route
rendert on-demand zur Anfragezeit), weil `usePathname()` im Layout während
des Prerenders einer dynamischen Route sonst fehlschlägt. Kein Einfluss auf
die Funktion.

## Tests — tatsächliche Ergebnisse

```
67 passed, 3 warnings in 0.91s   (backend/.venv/bin/python -m pytest tests/ -q)
```

- 62 Phase-1/2/3-Tests weiterhin grün.
- 5 neue Tests in `tests/test_phase6_ops.py`, alle grün:
  - Dashboard-Summary: nach 3 Chats (order_status, greeting, complaint→Ticket)
    `conversations_count=3, messages_count=6, tickets_open/total=1,
    escalations_count=1`; Breakdown enthält genau die 3 Intents je 1× mit
    deutschen Labels („Beschwerde", „Bestellstatus", „Begrüßung");
    `recent_events` ≤ 15, alle mit `label_de` + `created_at`
  - Ticket-Liste + `?status=open`-Filter; `?status=closed` → `[]`
  - Ticket-Detail: verknüpfte Nachrichten (2, Kunde+Assistent), Events
    (`ticket_created`, `escalated`, …), empfohlene Aktion; unbekannte ID → 404
  - Unterhaltungs-Liste (message_count, last_intent+Label) und -Detail
    (order_status-Unterhaltung enthält KEIN `ticket_created`)
  - Store-Isolation: zweiter Store mit eigenem Ticket ist auf allen neuen
    Endpunkten unsichtbar (Liste, Detail, Summary, Conversations); fremde
    IDs → 404, kein Leak; Summary des zweiten Stores zeigt 0/0/leere Listen.

## Curl-Verifikation (uvicorn :8001, frische DB, Mock-Provider)

- 3 Demo-Chats: `order_status (0.96)` ohne Ticket, `greeting (0.90)` ohne
  Ticket, `complaint (0.90)` → Ticket #1, escalated
- `GET /api/dashboard/summary` → 3 Unterhaltungen, 6 Nachrichten, 1 offenes
  Ticket, 1 Eskalation, Breakdown `{complaint:1, greeting:1, order_status:1}`
  mit deutschen Labels, 15 echte Events („Anfrage empfangen", „Anliegen
  erkannt", „Demo-Bestellung geprüft", „Support-Ticket erstellt",
  „An Mitarbeiter eskaliert", …)
- `GET /api/tickets?status=open` → 1 Treffer (high, `always_human`)
- `GET /api/tickets/1` → Detail mit 2 Nachrichten + 6 Events; `/tickets/999999` → 404
- `GET /api/conversations` → 3 Einträge mit last_intent-Labels
- Frontend: `npm run build` grün (Next.js 16, 7 Routen); `next start`
  serviert `/dashboard`, `/tickets`, `/tickets/1` (Shells + Ladezustände
  rendern; Daten kommen clientseitig aus der verifizierten API —
  API-Basis-URL korrekt in den Build eingebettet). Live-Browser-Render-Test
  steht aus (kein Browser-Zugriff in dieser Umgebung).

## Offene Punkte / bekannte Einschränkungen

1. Detailseiten laden Daten clientseitig (useEffect) — kein Server-SEO,
   für die Demo ok.
2. `intents_breakdown` zählt Klassifikationen pro Nachricht (jede Nachricht
   startet derzeit eine neue Konversation — kein Dialoggedächtnis, aus
   Phase 2 übernommen).
3. `escalations_count` zählt explizite `escalated`-Events; Retouren-Tickets
   (Review-Handoff ohne Eskalations-Event) zählen als Tickets, nicht als
   Eskalationen — im Report/Doc so definiert.
4. Ticket-Status ist immer `open` (kein Schließen-Workflow — Phase 7+/11).

## Sicherheit (Phase-6-Stand)

Read-only Ops-Endpunkte, keine Mutationen; strikte Store-Isolation per Test
verifiziert (fremde Store-IDs → 404, kein Daten-Leak); keine Secrets im
Frontend; Demo-Reset weiterhin nur Demo-Zeilen. Offen (Phase 7, Pflicht vor
Public Deploy): Rate Limiting, Tages-Quotas, Admin-API-Keys, Audit-Logging.

## Kosten

**0 €** zusätzlich: SQLite, Mock-Provider, lokale Entwicklung.

## Deployment-Status

Nicht deployed (Phase 8). Blocker unverändert: Vercel-OAuth und
Hetzner-Deploy-Key erfordern Shahids Aktionen.

## Nächste Phase

**Phase 7** — Rate Limiting, Tages-Quotas (`LLM_DAILY_REQUEST_CAP`
durchsetzen), Admin-API-Keys für Ops/Demo-Reset, Audit-Logging,
Abuse-Härtung vor dem Public Deploy.
