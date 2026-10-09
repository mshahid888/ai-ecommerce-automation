# Demo-Anleitung für Interessenten

**Zielgruppe:** Shop-Betreiber, die die Demo selbst ausprobieren
**Dauer:** ca. 10 Minuten · **Voraussetzungen:** nur ein Browser, kein Konto

> Diese Demo läuft mit **simulierten Daten** (Shop „Muster-Shop GmbH",
> fiktive Bestellungen und Produkte). Sie dient der Veranschaulichung der
> Workflows — nicht der Verarbeitung echter Kundendaten.

---

## 1. Demo öffnen

1. Öffnen Sie die Demo-URL im Browser (Desktop oder Smartphone).
2. Sie landen direkt im **Support-Chat** — keine Anmeldung nötig.
3. Beachten Sie den Demo-Banner: alles, was Sie sehen, sind Demo-Daten.

## 2. Die vier Szenarien ausprobieren

Klicken Sie nacheinander auf die vier **Beispiel-Fragen** (oder tippen
Sie die Nachrichten selbst ein). Beobachten Sie jeweils zwei Dinge:
die **Antwort** und die **Aktivitäts-Zeitleiste** daneben/darunter.

### Szenario A — Bestellstatus
**Nachricht:** „Hallo, wo bleibt meine Bestellung #10482?"
**Beobachten:**
- Die Zeitleiste: *Anfrage empfangen → Anliegen erkannt →
  Bestellnummer extrahiert → Demo-Bestellung geprüft →
  Geschäftsregeln angewendet → Antwort erstellt → Supportvorgang
  protokolliert.*
- Die Antwort nennt den echten Demo-Status: **versendet, DHL,
  DEMO-TRK-10482, voraussichtlich 14.10.2026, 34,99 €** —
  plus Demo-Hinweis.
**Gegenprobe (wichtig):** Tippen Sie „Wo ist meine Bestellung #99999?"
→ Das System antwortet ehrlich *„nicht gefunden"* und bietet einen
Mitarbeiter an — es erfindet keine Bestellung.

### Szenario B — Produktfrage
**Nachricht:** „Ist diese Trinkflasche spülmaschinengeeignet?"
**Beobachten:**
- Antwort: *„Ja, AquaPure 750 — spülmaschinengeeignet: ja.
  (Angaben aus dem Produktkatalog des Demo-Shops.)"*
- Die Antwort stammt ausschließlich aus dem hinterlegten Katalog.
**Gegenprobe:** Fragen Sie nach einer Eigenschaft, die nicht im Katalog
steht (z. B. „Wie schwer ist die Trinkflasche?") → ehrliches
„keine Information" + Angebot zur Mitarbeiter-Übergabe.

### Szenario C — Retoure
**Nachricht 1:** „Ich möchte meine Bestellung zurücksenden."
**Beobachten:** Das System fragt nach der Bestellnummer — es erstellt
noch **keinen** Antrag und kein Ticket.
**Nachricht 2:** „Ich möchte die Bestellung #10482 zurücksenden."
**Beobachten:**
- Zeitleiste: *… → Retourenrichtlinie geprüft → Retourenantrag
  erstellt → Support-Ticket erstellt …*
- Antwort: Antrag angelegt (Ticket-Nummer wird genannt), vorläufige
  Prüfung „innerhalb der 30-tägigen Rückgabefrist", Rücksendeadresse —
  und der klare Satz: **keine echte Retoure autorisiert, keine
  Rückerstattung ausgeführt**. Die endgültige Prüfung übernimmt ein
  Mitarbeiter.

### Szenario D — Eskalation
**Nachricht:** „My package never arrived, and I want my money back immediately."
**Beobachten:**
- Das System erkennt die Beschwerde, erstellt **sofort** ein Ticket mit
  **hoher Priorität** und eskaliert an einen Mitarbeiter.
- Antwort enthält **kein** Geldversprechen: *„… wir versprechen nichts,
  was wir nicht geprüft haben."*

## 3. Dashboard und Tickets ansehen

1. Öffnen Sie **Dashboard** in der Navigation: echte Kennzahlen aus den
   soeben erzeugten Vorgängen (Unterhaltungen, Nachrichten, offene
   Tickets, Eskalationen), Anliegen-Verteilung, Aktivitätenliste.
2. Öffnen Sie **Tickets**: Tabelle aller erzeugten Tickets — Klick auf
   eine Zeile zeigt die Detailseite (Zusammenfassung, Eskalationsgrund,
   empfohlene Aktion, verknüpfte Unterhaltung, Ereignisverlauf).

## 4. Demo zurücksetzen

- Auf der Chat-Seite: Button **„Demo zurücksetzen"**.
- Stellt die Ausgangsdaten wieder her (Bestellungen, Produkte,
  Richtlinien). Betrifft **nur** Demo-Daten.
- Das Audit-Protokoll bleibt aus Sicherheitsgründen erhalten.

---

## Was die Demo Ihnen zeigt — und was nicht

| Sie sehen | Sie sehen nicht |
|---|---|
| Echte Workflow-Logik (Klassifikation, Regeln, Tickets) | Echte Kundendaten (gibt es hier keine) |
| Ehrliche Antworten aus geprüften Daten | Echte KI-Antworten eines großen Modells (Standard: deterministischer Mock) |
| Deterministische Retouren-Vorprüfung | Echte Retouren-Autorisierung oder Erstattungen (absichtlich unmöglich) |
| Shopify-Adapter als Schnittstelle + Simulation | Einen angebundenen echten Shopify-Shop |

**Nächster Schritt:** Pilotumfang und Onboarding —
`docs/sales/07-pilot-scope.md`, `docs/sales/08-client-onboarding-checklist.md`.
