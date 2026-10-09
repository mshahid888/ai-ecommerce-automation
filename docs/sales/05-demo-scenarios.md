# Demo-Szenarien — erwartetes Systemverhalten Schritt für Schritt

**Stand:** 2026-10-09 · alle Abläufe gegen die lokale Backend-Instanz
verifiziert · Antworten wortwörtlich aus dem System.

Jede Nachricht durchläuft die Pipeline: Validierung → Intent-
Klassifikation → Entitäten-Extraktion → Geschäftsregeln →
autorisierter Datenzugriff → Antwort → Validierung → Event-Log.

---

## Szenario A — Bestellstatus-Abfrage

**Eingabe:** „Hallo, wo bleibt meine Bestellung #10482?"

| Schritt | Systemverhalten (verifiziert) |
|---|---|
| 1. Validierung | Nachricht ≤ 2000 Zeichen, nicht leer → ok |
| 2. Klassifikation | Intent `order_status`, Konfidenz 0,96 |
| 3. Extraktion | `order_ref = "10482"` (Regex `^\d{3,6}$`) |
| 4. Datenzugriff | Lookup in Demo-Bestellungen → gefunden (versendet, DHL, DEMO-TRK-10482, ETA 14.10.2026, 34,99 €) |
| 5. Regeln | Status-Mapping `shipped → versendet`; nur verifizierte Felder in die Antwort |
| 6. Antwort | „Ihre Bestellung #10482 ist versendet. Versandpartner: DHL. Sendungsnummer: DEMO-TRK-10482 (Demo-Referenz, keine Live-Sendungsverfolgung). Voraussichtliche Zustellung: 14.10.2026. Bestellwert: 34,99 €. Hinweis: Demo-Umgebung — alle Daten sind simuliert." |
| 7. Timeline | Anfrage empfangen → Anliegen erkannt → Bestellnummer extrahiert → Demo-Bestellung geprüft → Geschäftsregeln angewendet → Antwort erstellt → Supportvorgang protokolliert |

**Variante unbekannte Bestellung:** „Wo ist meine Bestellung #99999?"
→ Lookup negativ → „Die Bestellung #99999 wurde nicht gefunden. Bitte
prüfen Sie die Nummer — oder soll sich ein Mitarbeiter bei Ihnen
melden?" — es wird **nichts** erfunden, kein Ticket ohne Grund.

## Szenario B — Produktfrage

**Eingabe:** „Ist diese Trinkflasche spülmaschinengeeignet?"

| Schritt | Systemverhalten (verifiziert) |
|---|---|
| 1.–3. | Intent `product_question`, Konfidenz 0,94 |
| 4. Datenzugriff | Katalogsuche → Treffer „AquaPure 750"; Attribut `spuelmaschinengeeignet: true` aus den hinterlegten Produktdaten |
| 5. Regeln | Nur Katalogdaten verwenden; keine Spezifikation erfinden |
| 6. Antwort | „Ja, AquaPure 750 — spülmaschinengeeignet: ja. (Angaben aus dem Produktkatalog des Demo-Shops.) Hinweis: Demo-Umgebung — alle Daten sind simuliert." |

**Variante fehlende Information:** z. B. Frage nach dem Gewicht →
„… liegen mir im Produktkatalog des Demo-Shops leider keine
Informationen vor — ich erfinde keine Angaben. Soll ich Ihre Frage an
einen Mitarbeiter weitergeben?"

## Szenario C — Retouren-Anfrage

**Eingabe 1:** „Ich möchte meine Bestellung zurücksenden."

| Schritt | Systemverhalten (verifiziert) |
|---|---|
| 1.–3. | Intent `return_request`, Konfidenz 0,95, **keine** Bestellnummer |
| 6. Antwort | „Gerne nehme ich Ihre Retoure auf. Bitte nennen Sie mir Ihre Bestellnummer — zum Beispiel #10482." — **kein** Antrag, **kein** Ticket |

**Eingabe 2:** „Ich möchte die Bestellung #10482 zurücksenden."

| Schritt | Systemverhalten (verifiziert) |
|---|---|
| 4. Datenzugriff | Bestellung #10482 gefunden (Bestelldatum 06.10.2026) |
| 5. Regeln | Deterministische 30-Tage-Frist-Prüfung aus `store_policies` → innerhalb der Frist (vorläufige Eignung) |
| 6. Antrag + Ticket | Retourenantrag angelegt, Support-Ticket erstellt (z. B. Ticket #1 nach frischem Reset), Eskalationsgrund: „Freigabe durch Mitarbeiter erforderlich" |
| 7. Antwort | „Ihr Retourenantrag für Bestellung #10482 wurde als Demo-Vorgang angelegt (Ticket #1) — es wird keine echte Retoure autorisiert und keine Rückerstattung ausgeführt. Vorläufige Prüfung: Die Bestellung liegt innerhalb der 30-tägigen Rückgabefrist. Die endgültige Prüfung übernimmt ein Mitarbeiter. Nächster Schritt: Ein Mitarbeiter prüft den Antrag und sendet Ihnen das Rücksendeetikett. Rücksendeadresse: Muster-Shop GmbH, Retouren, Musterstraße 1, 37073 Göttingen. …" |
| 8. Timeline | … → Bestellnummer extrahiert → Demo-Bestellung geprüft → Retourenrichtlinie geprüft → Retourenantrag erstellt → Support-Ticket erstellt → Antwort erstellt → Supportvorgang protokolliert |

Getrennte Stufen — Sammlung, Vorprüfung, Antrag — sind im Code und in
der Timeline unterscheidbar. Autorisierung und Erstattung existieren
nicht.

## Szenario D — Eskalation (Beschwerde)

**Eingabe:** „My package never arrived, and I want my money back immediately."

| Schritt | Systemverhalten (verifiziert) |
|---|---|
| 1.–3. | Intent `complaint`, Konfidenz 0,90 → ALWAYS_HUMAN-Regel greift |
| 6. Ticket | Support-Ticket mit **hoher Priorität** erstellt (z. B. Ticket #2 nach Szenario C), Eskalationsgrund protokolliert |
| 7. Antwort | „Das tut mir leid zu hören. Ich habe Ihr Anliegen mit hoher Priorität an unser Team weitergegeben (Ticket #2). Ein Mitarbeiter wird sich so bald wie möglich bei Ihnen melden — wir versprechen nichts, was wir nicht geprüft haben. …" — **kein** Erstattungsversprechen |
| 8. Timeline | … → Support-Ticket erstellt → An Mitarbeiter eskaliert → … |

---

**Hinweis zu Ticket-Nummern:** Sie sind fortlaufend pro Datenbank.
Nach einem Demo-Reset beginnt die Zählung wieder bei #1 — in
Präsentationen Nummern daher als beispielhaft kennzeichnen.
