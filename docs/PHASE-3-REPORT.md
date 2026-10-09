# Phase 3 — Klassifikationstiefe, Konfidenz-Kalibrierung, Gemini-Hookup

**Datum:** 2026-10-09
**Status:** Implementiert, getestet (62/62 grün), per curl live verifiziert,
als Phase 3 committet.

Phase 3 vertieft die deutsche Absichtserkennung: 11 Intents mit echten
Workflows und echten Events, ein validiertes Klassifikations-Schema, eine
deterministische Eskalations-Policy mit Konfidenz-Schwelle, Token-/Quota-
Guardrails in der Config und der vollständig implementierte Gemini-Provider.

## Was wurde implementiert

### Backend

- **`app/services/intent.py`** (erweitert): `Intent`-Enum mit 11 Werten
  (`shipping_info`, `payment_question`, `product_availability`,
  `order_cancel`, `greeting` neu), `ALWAYS_HUMAN =
  {complaint, order_cancel, human_support, unknown}` als Policy-Menge,
  `normalize_intent_name()` mit Alias-Normalisierung (z. B.
  `human_request` → `human_support`).
- **`app/services/classification.py`** (neu): strikt validiertes
  `Classification`-Schema (`intent, confidence, order_ref, product_hint,
  return_reason, language, requires_human, reason`) — der
  Validierungs-Ansatz ist aus
  `~/workspace/ai-customer-support-automation/src/classifier.py` portiert:
  Intent muss im Enum sein, Konfidenz 0–1 (kein bool), `order_ref` muss
  `^\d{3,6}$` matchen; **jeder** Fehler → `safe_fallback()` (unknown, 0.0,
  requires_human=True). Niemals Crash, niemals Raten. Alle Downstream-Code
  (Pipeline, Eskalation, API) nutzt nur dieses Schema, nie rohen
  Modell-Text. Plus deterministische `detect_language()`-Heuristik (de/en).
- **`app/rules/escalation.py`** (Phase-3-Policy): `decide_escalation()`
  liefert `(escalate, reason_code)` — Konfidenz < Schwelle (Default 0,6)
  → `"low_confidence"` (vor der Intent-Policy geprüft, weil
  informationsreicher fürs Team), ALWAYS_HUMAN → `"always_human"`,
  Klassifikator-Flag → `"classifier_requires_human"`. `should_escalate()`
  bleibt als boolean-Wrapper.
- **`app/ai/providers.py`** (Mock erweitert): deutsche Keyword-Regeln für
  die 5 neuen Intents (Reihenfolge so gewählt, dass spezifische Intents
  vor generischen gewinnen — „Versand meiner Bestellung" → shipping_info
  trotz „Bestellung"); `greeting` wird bewusst ZULETZT geprüft, damit
  „Hallo, wo bleibt meine Bestellung #10482?" → order_status bleibt.
  Konfidenz-Kalibrierung dokumentiert: Basis pro Regel + 0,03 je
  zusätzlichem Keyword-Treffer, Cap 0,98. Ausgabe enthält zusätzlich
  `product_hint`, `return_reason`, `language`. `widerrufen` wandert von
  `return_request` nach `order_cancel`. System-Prompt auf 11 Intents +
  neue Felder aktualisiert; `max_tokens` kommt aus der Config.
- **`app/services/pipeline.py`**: ersetzt das alte `_parse_classification`
  durch strikte Validierung; neue Handler `handle_greeting`,
  `handle_shipping_info` (aus `shipping`-Policy), `handle_payment_question`
  (aus `payments`-Policy), `handle_product_availability` (Demo-Bestand,
  ehrlich „nicht auf Lager"); `handle_escalation` nimmt das validierte
  Schema + Reason-Code (`low_confidence` → eigene ehrliche deutsche
  Erklärung), `order_cancel` mit Bestellkontext im Ticket. Neues Event
  `store_info` („Shop-Informationen abgerufen"). `return_request` läuft
  weiterhin durch die Triage (deren Ticket IST der Human-Handoff) — das
  `requires_human`-Flag des Klassifikators divertiert sie nicht mehr in
  den generischen Eskalationspfad (nur echte Unsicherheit < 0,6 tut das).
- **`app/db/seed.py`**: neue `payments`-Policy (PayPal, Kreditkarte, Kauf
  auf Rechnung, Vorkasse — Demo-Hinweis: keine echten Zahlungen), jedes
  Produkt hat `bestand_stueck` (AquaPure 42, Solarbank 15, Kaffeemühle 0,
  LED-Lampe 28). `app/rules/product_rules.py`: `stock_level()`-Helper,
  Label „Verfügbarkeit", Formatierung „42 Stück auf Lager".
- **`app/config.py`**: `CONFIDENCE_THRESHOLD` (0,6),
  `LLM_MAX_TOKENS_PER_REQUEST` (300),
  `LLM_DAILY_REQUEST_CAP` (500 — Durchsetzung erst Phase 7, Config jetzt).
- **Gemini-Provider**: vollständig implementiert, folgt dem Skill-Pattern
  exakt (`dynamic_credentials.add_surrogate_to_request` +
  `read_json_response`, nur `generativelanguage.googleapis.com`, kein Key
  in Code/Env/Chat). Default bleibt `mock`.

### Docs

- `docs/ARCHITECTURE.md`: Pipeline-Diagramm (Phase 3), Eskalations-Zeile,
  Provider-Sektion (Mock-Vertrag 8 Felder, Gemini-Status), Seed-Beschreibung
  (3 Policies, Bestand).
- `README.md`: Phase-3-Sektion, Testzähler 62, neue Env-Variablen.

## Tests — tatsächliche Ergebnisse

```
62 passed, 3 warnings in 0.70s   (backend/.venv/bin/python -m pytest tests/ -q)
```

- 33 Phase-1/2-Tests weiterhin grün (Policy-Zähler 2→3 angepasst).
- 29 neue Tests in `tests/test_phase3_classification.py`, alle grün:
  - 6 neue Intents geroutet (greeting ohne Ticket; shipping_info mit
    4,99 €/50,00 €/2–4 Werktage/DHL aus der Policy; payment_question mit
    PayPal/Rechnung; Verfügbarkeit 42 Stück vs. „nicht auf Lager";
    order_cancel → Ticket, high priority, Bestellkontext)
  - greeting schattet order_status nicht („Hallo, wo bleibt meine
    Bestellung #10482?" → order_status)
  - Konfidenz-Kalibrierung: mehr Keyword-Treffer → höhere Konfidenz
  - Schwelle: 0,55 → Ticket mit `escalation_reason="low_confidence"` +
    deutsche Erklärung; 0,61 → normale Antwort
  - ALWAYS_HUMAN bei 0,99 ignoriert (complaint, order_cancel,
    human_support, unknown) + Alias `human_request` → `human_support`
  - Stubbed-Failing-Provider: ungültiges JSON / falscher Intent /
    falsche Konfidenz (1,5, −0,2, „high", true) / kaputte Bestellnummer →
    safe_fallback + Ticket, kein Crash
  - Provider-Ausfall (LLMError) → 502 `ai_provider_unavailable` mit
    ehrlicher deutscher Antwort
  - Edge Cases: „Wo bleibt meine Bestellung?" ohne Nummer → Nachfrage
    (kein Ticket); gemischtsprachige Beschwerde → Eskalation, keine
    erfundenen Versprechen

## Curl-Verifikation (uvicorn, frische DB, Mock-Provider)

- `Guten Morgen` → `greeting (0.90)`, Events
  `message_received, intent_classified, response_generated,
  interaction_logged`, kein Ticket — „Hallo und herzlich willkommen beim
  Demo-Shop „Muster-Shop GmbH“! Wie kann ich Ihnen helfen? …"
- `Wie lange dauert der Versand?` → `shipping_info (0.91)`, Events inkl.
  `store_info, rules_applied` — „Versandkosten: 4,99 €. versandkostenfrei
  ab 50,00 €. Lieferzeit: 2-4 Werktage. Versandpartner: DHL, Hermes. …"
- `Ist die Kaffeemühle manuell noch lieferbar?` →
  `product_availability (0.87)` — „… ist derzeit leider nicht auf Lager.
  Soll ich Ihre Anfrage an einen Mitarbeiter weitergeben …?"
- `Ich möchte meine Bestellung stornieren` → `order_cancel (0.95)`,
  Ticket #1 (high, reason `always_human`), Eskalations-Events
- `blarg wibble zzz` → `unknown (0.35)`, Ticket #4 mit
  `escalation_reason="low_confidence"`, ehrliche deutsche Erklärung

## Gemini — ehrlicher Verifikationsstand

- Provider-Code vollständig implementiert, Credential-Helper lädt,
  Surrogat wird an `generativelanguage.googleapis.com` angehängt.
- Der Modellname `gemini-3.8-flash` wurde von der Google-API bestätigt
  (`gemini-2.5-flash` antwortet 404 mit dem Hinweis, 3.8-flash zu nutzen).
- **Keine erfolgreiche Live-Klassifikation in dieser Umgebung:**
  anhaltende HTTP-503-Antworten („This model is currently experiencing
  high demand … try again later") — kein Auth-Problem (kein 401/403),
  sondern Modell-Kapazität. Nicht weiter gehämmert (Rate-Limit-Risiko).
- `LLM_PROVIDER=gemini` bleibt anschlussfertig; Default bleibt `mock`.
  Erneuter Live-Test nach Kapazitätsfreigabe.

## Offene Punkte / bekannte Einschränkungen

1. Kein Dialoggedächtnis über Nachrichten hinweg (aus Phase 2 übernommen).
2. Die Mock-Konfidenz ist eine Keyword-Heuristik, kein kalibriertes
   Modell-Score — für die Demo/deterministische Tests ausreichend,
   dokumentiert in `providers.py`.
3. `LLM_DAILY_REQUEST_CAP` ist konfiguriert, aber erst in Phase 7
   durchgesetzt.
4. Frontend unverändert (API-Vertrag stabil) — kein `npm run build` nötig.

## Sicherheit (Phase-3-Stand)

Unverändert aus Phase 2 plus: strikte Validierung eliminiert eine ganze
Klasse von Fehlern (Modell-Output kann keine ungültigen Intents,
Konfidenzen oder Bestellnummern mehr in die Pipeline schmuggeln);
`order_cancel` kann nie automatisch stornieren (ALWAYS_HUMAN);
Low-Confidence-Nachrichten erhalten immer ein Ticket statt einer
geratenen Antwort. Offen (Phase 7, Pflicht vor Public Deploy): Rate
Limiting, Tages-Quotas, Admin-API-Keys, Audit-Logging.

## Kosten

**0 €** zusätzlich: SQLite, Mock-Provider (Default), lokale Entwicklung.
Gemini-Nutzung (nach Kapazitätsfreigabe) vernachlässigbar bei
Temperatur 0,0 und ~300-Token-Ceiling.

## Deployment-Status

Nicht deployed (Phase 8). Blocker unverändert: Vercel-OAuth und
Hetzner-Deploy-Key erfordern Shahids Aktionen.

## Nächste Phase

Phase 4/5 (Bestell-Lookup, Produkt-Q&A, Retouren-Triage) sind durch
Phase 2+3 bereits weitgehend abgedeckt. Sinnvoller nächster Schritt:
**Phase 6** — Operations-Dashboard + echte Event-Timeline ausbauen
(`store_info`-Events u. a. einbeziehen), oder **Phase 7** — Rate Limiting,
Quotas (dann `LLM_DAILY_REQUEST_CAP` durchsetzen), Abuse-Härtung vor dem
Public Deploy.
