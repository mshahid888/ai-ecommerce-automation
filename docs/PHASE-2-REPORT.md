# Phase 2 — Demo-Store + deutscher Kundensupport-Chat (Ende-zu-Ende)

**Datum:** 2026-10-09
**Status:** Implementiert, getestet, verifiziert. Commit folgt.

Phase 2 verdrahtet den Phase-1-Skelett-Workflow vollständig: deutsche
Absichtserkennung (Mock-Regeln), Bestell-Lookup, Produktkatalog,
Retouren-Triage mit deterministischer Richtlinienprüfung, Eskalation,
echte Event-Timeline und eine vollständig angebundene deutsche Chat-UI.

## Was wurde implementiert

### Backend

- **`app/db/seed.py`** (erweitert): Demo-Shop „Muster-Shop GmbH", 4 Produkte
  (Trinkflasche „AquaPure 750" mit `spuelmaschinengeeignet=true`, Material,
  Volumen; Solarbank; Kaffeemühle; LED-Schreibtischlampe), 2 fiktive Kunden,
  4 Bestellungen (#10482 versendet/DHL/`DEMO-TRK-10482`/ETA 14.10.2026,
  #10483 in Bearbeitung, #10471 zugestellt, #10479 verzögert), 2 Policies
  als explizite Konfigurationszeilen (`returns`: 30-Tage-Frist, Bedingungen,
  Ausnahmen, Rücksendeadresse; `shipping`: Kosten, Lieferzeit). Alle
  Referenzen fiktiv und als Demo gekennzeichnet.
- **`app/ai/providers.py`** (Mock erweitert): deutsche Keyword-Regeln für
  `order_status` („wo bleibt meine bestellung", „bestellstatus",
  „lieferstatus", …), `product_question` („spülmaschinengeeignet",
  „ist diese/das/der/die", …), `return_request` („zurücksenden", „retoure",
  „rückgabe", „widerruf", …), `human_support` („mitarbeiter", „mensch",
  „support"), `complaint` („beschwerde", „nie angekommen", „never arrived",
  …). Bestellnummern-Regex `#?(\d{4,6})`; bloße Nummern (z. B. „#10482")
  fallen auf `order_status` zurück. Beschwerde-Signale werden vor
  Retoure-Signalen geprüft (stärkeres Routing-Signal).
- **`app/rules/order_rules.py`** (real): Normalisierung (`010482`→`10482`),
  store-isolierter Lookup; unbekannt → `None` (kein Raten).
- **`app/rules/product_rules.py`** (neu): deterministische Katalogsuche
  (Token-Overlap über Name/Beschreibung), Attribut-Erkennung aus der
  Nachricht, deutsche Werteformatierung (`true`→„ja", `750`→„750 ml").
  Antworten stammen ausschließlich aus `attributes_json` — Unbekanntes wird
  nie erfunden.
- **`app/rules/return_policy.py`** (real): deterministische Engine gegen die
  `returns`-Policy-Zeile. Liefert nur eine **vorläufige** Prüfung
  (`preliminary_eligible` / `not_shipped` / `window_expired` / `unclear`);
  Freigabe und Rückerstattung bleiben menschlich. Die Demo führt niemals
  eine echte Retoure oder Rückerstattung aus.
- **`app/services/pipeline.py`** (vollständig neu): je Intent ein echter
  Workflow mit echten Events —
  `message_received → intent_classified → [order_ref_extracted] →
  [order_lookup | product_search | policy_check] → [return_request_created] →
  [ticket_created] → [escalated] → [rules_applied] → response_generated →
  interaction_logged`. Jeder Event entspricht einer tatsächlich
  ausgeführten Operation; übersprungene Schritte hinterlassen keine Events.
- **`app/api/chat.py`**: Antwortvertrag `{answer, intent, order, ticket,
  events[], escalated}` (+ `reply_de`/`timeline`/`ticket_id` aus
  Kompatibilitätsgründen).
- **`app/main.py` + `app/config.py`**: CORS für die Frontend-Dev-Origin
  (`CORS_ORIGINS`, Standard `http://localhost:3000,http://127.0.0.1:3000`).

### Frontend (deutsch, mobil responsiv, keine Robot-Grafiken)

- **`app/page.tsx`**: 4 Beispiel-Buttons mit den exakten Demo-Szenarien,
  Ticket-Hinweis-Banner bei erstelltem Ticket, Timeline rendert die echten
  `events[]` jeder Antwort, Ladezustand („Anfrage wird bearbeitet …"),
  Fehlerzustand, Demo-Banner bleibt („Demo-Umgebung – simulierte Daten").
- **`lib/api.ts`**: Typen für den Phase-2-Vertrag (`answer`, `order`,
  `events`, `ticket`, `escalated`).
- **`app/layout.tsx`**: Footer auf Phase 2 aktualisiert.

### Docs

- `docs/ARCHITECTURE.md`: Pipeline-, Rules-, Seed- und API-Abschnitte auf
  Phase 2 aktualisiert. `README.md`: Phase-2-Funktionsliste, 33 Tests,
  `CORS_ORIGINS`-Doku.

## Tests — tatsächliche Ergebnisse

```
33 passed, 3 warnings in 0.33s   (backend/.venv/bin/python -m pytest tests/ -q)
```

- 21 Phase-1-Tests weiterhin grün (Health, Provider-Vertrag, Validatoren,
  Store-Isolation, Demo-Reset — Zähler an neues Seed angepasst: 4 Orders,
  2 Policies, `DEMO-TRK-10482`).
- 12 neue Tests in `tests/test_chat_pipeline.py`, alle grün:
  - Bestellstatus-Happy-Path (#10482 → „versendet", DHL, `DEMO-TRK-10482`,
    34,99 €; exakte Event-Kette mit 7 Events)
  - Bloße Bestellnummer („#10479" → verzögert)
  - Unbekannte Bestellung (#99999 → „nicht gefunden" + Mitarbeiter-Angebot,
    keine erfundenen Daten)
  - Produktfrage mit Katalogdaten (spülmaschinengeeignet → „Ja")
  - Produktfrage mit fehlendem Attribut (Farbe → „keine Informationen" +
    Eskalationsangebot)
  - Unbekanntes Produkt → Nachfrage, welches Produkt gemeint ist
  - Retoure ohne Bestellnummer → Nachfrage (kein Ticket, keine DB-Zeilen)
  - Retoure mit #10482 → Ticket + `return_requests`-Zeile
    (`status='pending_review'`, niemals auto-autorisiert)
  - Return-Policy-Engine als Unit-Test (fristgerecht/abgelaufen/fehlend)
  - Mitarbeiter-Wunsch → Eskalations-Ticket mit Grund + Empfehlung
  - Beschwerde (Szenario D) → Eskalation mit hoher Priorität, keine
    unhaltbaren Versprechen
  - Demo-Reset stellt Seed wieder her (Order gelöscht → Reset → 4 Orders,
    4 Produkte, 2 Policies)

## Curl-Verifikation (uvicorn, frische DB, Mock-Provider)

**Szenario A** — `Hallo, wo bleibt meine Bestellung #10482?`
→ `intent: order_status (0.93)` —
„Ihre Bestellung #10482 ist versendet. Versandpartner: DHL.
Sendungsnummer: DEMO-TRK-10482 (Demo-Referenz, keine
Live-Sendungsverfolgung). Voraussichtliche Zustellung: 14.10.2026.
Bestellwert: 34,99 €. Hinweis: Demo-Umgebung — alle Daten sind simuliert."
Events: `message_received, intent_classified, order_ref_extracted,
order_lookup, rules_applied, response_generated, interaction_logged`

**Szenario B** — `Ist diese Trinkflasche spülmaschinengeeignet?`
→ `intent: product_question (0.85)` —
„Ja, AquaPure 750 — spülmaschinengeeignet: ja. (Angaben aus dem
Produktkatalog des Demo-Shops.) Hinweis: Demo-Umgebung — alle Daten sind
simuliert."

**Szenario C** — `Ich möchte meine Bestellung zurücksenden.`
→ `intent: return_request (0.92)` —
„Gerne nehme ich Ihre Retoure auf. Bitte nennen Sie mir Ihre
Bestellnummer — zum Beispiel #10482."
Mit `#10482` → Ticket #2, `return_request_created`,
„wurde als Demo-Vorgang angelegt … es wird keine echte Retoure
autorisiert und keine Rückerstattung ausgeführt. Vorläufige Prüfung:
Die Bestellung liegt innerhalb der 30-tägigen Rückgabefrist."

**Szenario D** — `My package never arrived, and I want my money back immediately.`
→ `intent: complaint (0.90)`, `escalated: true`, Ticket #1 —
„Das tut mir leid zu hören. Ich habe Ihr Anliegen mit hoher Priorität
an unser Team weitergegeben (Ticket #1). Ein Mitarbeiter wird sich so
bald wie möglich bei Ihnen melden — wir versprechen nichts, was wir
nicht geprüft haben."

Zusätzlich verifiziert: unbekannte Bestellung #99999 → „Die Bestellung
#99999 wurde nicht gefunden. Bitte prüfen Sie die Nummer — oder soll
sich ein Mitarbeiter bei Ihnen melden?"; CORS-Preflight von
`http://localhost:3000` → 200 mit `access-control-allow-origin`.

**Frontend:** `npm run build` grün (Next.js 16, TypeScript, 4 Routen).
Ein Live-Render-Test im Browser steht aus (kein Browser-Zugriff in
dieser Umgebung) — Build + API-Vertrag sind verifiziert.

## Offene Punkte / bekannte Einschränkungen

1. Jede Nachricht startet eine neue Konversation — kein Dialoggedächtnis
   über Nachrichten hinweg (Retoure mit nachgereichter Bestellnummer
   erfordert derzeit, die Nummer in derselben Nachricht zu nennen).
2. Die Mock-Klassifikation ist keyword-basiert; mehrdeutige Formulierungen
   können falsch routen (dann greift die Konfidenz-Schwelle → Mensch).
   Echte Provider (`gemini`/`openai_compatible`) sind anschlussfertig.
3. Produkt-Matching ist Token-Overlap — bei mehreren ähnlichen Produkten
   ggf. ungenau (Demo-Katalog: 4 Produkte, unkritisch).
4. Dashboard (`/dashboard`) zeigt weiterhin Platzhalter-Kennzahlen.
5. Kein Live-Browser-Render-Test durchgeführt.

## Sicherheit (Phase-2-Stand)

Vorhanden: Input-Caps (2000 Zeichen / 64 KiB), generische Fehlermeldungen,
Store-Isolation in jeder Abfrage (per Test verifiziert), Demo-Isolation
(Reset berührt nur `is_demo=1`-Zeilen, per Test verifiziert), keine Secrets
im Frontend, keine echten Zahlungs-/Refund-Pfade (per Design + Test
`status='pending_review'`), CORS auf Dev-Origins begrenzt, Bestell-Lookup
nur bei exakter Referenz (kein Enumerieren fremder Bestellungen möglich —
unbekannte Referenz → Klärung statt Daten).
Offen (Phase 7, Pflicht vor Public Deploy): Rate Limiting, Tages-Quotas,
Admin-API-Keys, Audit-Logging, Aufzählschutz-Härtung.

## Kosten

**0 €** zusätzlich: SQLite, Mock-Provider, lokale Entwicklung. Keine
kostenpflichtigen Dienste eingeführt.

## Deployment-Status

Nicht deployed (Phase 8). Blocker unverändert aus Phase 0: Vercel-OAuth
und Hetzner-Deploy-Key erfordern Shahids Aktionen.

## Nächste Phase (Phase 3)

Deutsche Intent-Klassifikation vertiefen: Konfidenz-Kalibrierung,
Mehrdeutigkeits-Tests, optional Gemini-Provider für die Demo; danach
Phase 4/5 sind durch Phase 2 bereits weitgehend abgedeckt (Lookup und
Retouren-Triage sind real) — der Phasenplan sollte ggf. neu justiert
werden (Dashboard/Timeline in Phase 6 ausbauen).
