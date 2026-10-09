# Video-Skript: KI-gestützte E-Commerce-Automatisierung (60–90 Sekunden)

**Produkt:** AI E-Commerce Automation — Demo-Store „Muster-Shop GmbH"
**Sprache:** Deutsch · **Ziel:** 60–90 Sekunden, ein echter Workflow,
keine Marketing-Abstraktion
**Stand:** 2026-10-09, Backend Phase 0–9 verifiziert (107 Tests grün)
**Status des Videos:** Skript und Produktionsanleitung (nicht gerendert)

---

## Ehrlichkeits-Rahmen (gilt für jede Szene)

1. Jede dargestellte Aktion muss in der Demo **reproduzierbar** sein.
2. Alle Antworten sind **echte Backend-Ausgaben** der angegebenen
   Demo-Nachrichten — kein Text darf nachträglich geschönt werden.
3. Der Disclaimer „Hinweis: Demo-Umgebung — alle Daten sind simuliert"
   gehört in jede Aufnahme sichtbar mit ins Bild (er ist Teil der echten
   Antwort).
4. Fiktive Sendungsreferenzen (`DEMO-TRK-…`) dürfen niemals als echte
   Carrier-Daten präsentiert werden.
5. Die Voiceover-Aussagen müssen dem tatsächlichen Verhalten entsprechen
   (siehe Szenen-Tabelle unten).

---

## Szenen

### Szene 1 — 0:00–0:08 · Das Problem (8 s)

| Aspekt | Vorgabe |
|---|---|
| **Bild** | Textkarte auf hellem Hintergrund: „Jede Woche dieselben Anfragen im Postfach: *Wo bleibt meine Bestellung?*" — darunter ein fiktives, überladenes Support-Postfach (Mock-Screenshot, eindeutig als Illustration gekennzeichnet, z. B. Bildunterschrift „Symbolbild"). |
| **Voiceover** | „Ein Onlineshop, ein Problem: Dieselben Kundenfragen — jeden Tag, jede Woche. Bestellstatus, Retouren, Produktfragen. Die Antworten liegen alle schon im System." |
| **UI-Capture** | Kein Produkt-UI nötig; ein statisches Titelbild reicht. Wichtig: keine erfundenen Markennamen, keine angeblichen Kundendaten. |
| **Dauer** | 8 Sekunden |

### Szene 2 — 0:08–0:20 · Die Kundenfrage (12 s)

| Aspekt | Vorgabe |
|---|---|
| **Bild** | Produkt-UI, Seite `/` (Support-Chat), Desktop oder Mobil. Der Demo-Banner („Demo-Umgebung — simulierte Daten") muss sichtbar sein. |
| **Aktion** | Klick auf die Beispiel-Frage **„Hallo, wo bleibt meine Bestellung #10482?"** → Senden. Ladezustand „Anfrage wird bearbeitet …" kurz zeigen. |
| **Voiceover** | „Eine Kundin fragt: *Wo bleibt meine Bestellung Nummer 10482?* Kein Konto, keine Anmeldung — die Demo ist für jeden Besucher offen." |
| **UI-Capture** | Frontend-Dev-Server `http://localhost:3000` (oder die Deploy-URL, sobald verifiziert). Beispiel-Fragen-Klicks filmen; danach 2 Sekunden den Ladezustand halten. |
| **Dauer** | 12 Sekunden |

### Szene 3 — 0:20–0:35 · Erkennen, extrahieren, prüfen (15 s)

| Aspekt | Vorgabe |
|---|---|
| **Bild** | Gleiche Chat-Ansicht, Fokus auf das **Aktivitätsfeld** (Timeline) neben/unter dem Chat. |
| **Aktion** | Die Timeline-Ereignisse erscheinen nacheinander, jedes nach der **echten** Backend-Operation: „Anfrage empfangen" → „Anliegen erkannt" → „Bestellnummer extrahiert" → „Demo-Bestellung geprüft" → „Geschäftsregeln angewendet" → „Antwort erstellt" → „Supportvorgang protokolliert". |
| **Voiceover** | „Das System erkennt das Anliegen — eine Bestellstatus-Anfrage —, liest die Bestellnummer aus, prüft sie in den Shop-Daten und wendet die Geschäftsregeln an. Jeder Schritt in der Zeitleiste entspricht einer Operation, die gerade wirklich ausgeführt wurde." |
| **UI-Capture** | Beim selben Request wie Szene 2 filmen; ggf. leicht verlangsamt abspielen, damit die Ereignisse lesbar sind. **Nichts** einblenden, was nicht im echten Event-Log steht. |
| **Dauer** | 15 Sekunden |

### Szene 4 — 0:35–0:48 · Die geprüfte deutsche Antwort (13 s)

| Aspekt | Vorgabe |
|---|---|
| **Bild** | Chat-Ansicht, die Antwort-Bubble ist vollständig lesbar (ggf. leicht einzoomen). |
| **Aktion** | Die echte Backend-Antwort liegt vor — wortwörtlich gefilmt, nicht umgeschrieben: |
| **Echte Demo-Antwort (Stand 2026-10-09, verifiziert)** | „Ihre Bestellung #10482 ist versendet. Versandpartner: DHL. Sendungsnummer: DEMO-TRK-10482 (Demo-Referenz, keine Live-Sendungsverfolgung). Voraussichtliche Zustellung: 14.10.2026. Bestellwert: 34,99 €. Hinweis: Demo-Umgebung — alle Daten sind simuliert." |
| **Voiceover** | „Die Antwort kommt ausschließlich aus geprüften Shop-Daten: versendet, mit DHL, voraussichtliche Zustellung am 14. Oktober. Die Sendungsnummer ist als Demo-Referenz gekennzeichnet — nichts wird erfunden, nichts versprochen." |
| **UI-Capture** | Antwort-Bubble ca. 6–8 Sekunden stehen lassen; danach ggf. scrollen, damit der Demo-Hinweis am Ende der Nachricht sichtbar bleibt. |
| **Dauer** | 13 Sekunden |

### Szene 5 — 0:48–1:03 · Retouren-Anfrage (15 s)

| Aspekt | Vorgabe |
|---|---|
| **Bild** | Chat-Ansicht. |
| **Aktion (zweistufig, beide Schritte echt)** | 1. Klick auf die Beispiel-Frage **„Ich möchte meine Bestellung zurücksenden."** → System fragt ehrlich nach der Bestellnummer: *„Gerne nehme ich Ihre Retoure auf. Bitte nennen Sie mir Ihre Bestellnummer — zum Beispiel #10482."*<br>2. In das Eingabefeld tippen und senden: **„Ich möchte die Bestellung #10482 zurücksenden."** |
| **Echte Demo-Antwort (Stand 2026-10-09, verifiziert)** | „Ihr Retourenantrag für Bestellung #10482 wurde als Demo-Vorgang angelegt (Ticket #1) — es wird keine echte Retoure autorisiert und keine Rückerstattung ausgeführt. Vorläufige Prüfung: Die Bestellung liegt innerhalb der 30-tägigen Rückgabefrist. Die endgültige Prüfung übernimmt ein Mitarbeiter. Nächster Schritt: Ein Mitarbeiter prüft den Antrag und sendet Ihnen das Rücksendeetikett. Rücksendeadresse: Muster-Shop GmbH, Retouren, Musterstraße 1, 37073 Göttingen. Hinweis: Demo-Umgebung — alle Daten sind simuliert." |
| **Voiceover** | „Eine Retoure: Das System fragt die fehlende Bestellnummer nach, prüft dann die 30-tägige Rückgabefrist aus der hinterlegten Shop-Richtlinie — und legt einen Retourenantrag an. Wichtig: Es wird nichts autorisiert, nichts erstattet. Die endgültige Prüfung übernimmt ein Mensch." |
| **UI-Capture** | Beide Nachrichten hintereinander filmen; die zweite Antwort ca. 5 Sekunden stehen lassen. Timeline zeigt zusätzlich: „Retourenrichtlinie geprüft" → „Retourenantrag erstellt" → „Support-Ticket erstellt". |
| **Dauer** | 15 Sekunden |

### Szene 6 — 1:03–1:15 · Ticket, Timeline, Eskalation (12 s)

| Aspekt | Vorgabe |
|---|---|
| **Bild** | 1. Seite `/tickets`: Tabelle mit dem Retouren-Ticket. 2. Klick → Ticket-Detail: ID, Anliegen „Retourenanfrage", Bestellung #10482, Status offen, Eskalationsgrund, empfohlene Aktion, Ereignisverlauf. 3. Optional: Zurück im Chat die vierte Beispiel-Frage **„My package never arrived, and I want my money back immediately."** senden → Antwort: *„Das tut mir leid zu hören. Ich habe Ihr Anliegen mit hoher Priorität an unser Team weitergegeben (Ticket #…)."*, Timeline: „Support-Ticket erstellt" → „An Mitarbeiter eskaliert". |
| **Voiceover** | „Jeder Vorgang wird zum nachvollziehbaren Ticket: Anliegen, Bestellung, Status, Grund. Bei Beschwerden eskaliert das System sofort an einen Mitarbeiter — mit Priorität und Eskalationsgrund, ohne leere Versprechen." |
| **UI-Capture** | Ticket-Detail-Seite ca. 5 Sekunden, Eskalations-Ticket (falls gefilmt) ca. 4 Sekunden. Ticket-Nummern im Video sind beispielhaft — nach einem Demo-Reset beginnen sie wieder bei #1. |
| **Dauer** | 12 Sekunden |

### Szene 7 — 1:15–1:30 · Dashboard und CTA (15 s)

| Aspekt | Vorgabe |
|---|---|
| **Bild** | Seite `/dashboard`: echte Kennzahlen aus der Datenbank (Unterhaltungen, Nachrichten, offene Tickets, Eskalationen), Anliegen-Verteilung als Balkenliste, Aktivitätenliste aus den echten Workflow-Events. Alles als Demo-Daten gekennzeichnet. |
| **Aktion** | Kurz über das Dashboard fahren/schwenken, dann ausblenden auf den Schluss-Text. |
| **Voiceover** | „Und das Team behält den Überblick: alle Unterhaltungen, Tickets und Eskalationen — gezählt aus echten Vorgängen, nichts geschönt." |
| **UI-Capture** | **Vor** der Aufnahme: Demo zurücksetzen, dann die Szenen 2–6 einmal durchspielen, damit das Dashboard die echten, gerade erzeugten Zahlen zeigt. Keine Archiv-Screenshots mit alten Daten. |
| **Schluss-Text (exakt)** | „KI-gestützte E-Commerce-Automatisierung"<br>„Von der Kundenanfrage bis zum strukturierten Supportprozess."<br>„Shahid Nawaz | AI Automation Specialist" |
| **Dauer** | 15 Sekunden |

**Gesamt:** ca. 90 Sekunden (Zielkorridor 60–90 s; beim Schnitt eher straffen als strecken).

---

## Produktionsanleitung

### Werkzeuge (kostenlos, keine neuen Abos nötig)

- **Bildschirmaufnahme:** OBS Studio (kostenlos). Browserfenster als Quelle, 30 fps.
- **Schnitt:** DaVinci Resolve (kostenlos) oder CapCut Desktop.
- **Voiceover:** eigene deutsche Aufnahme (ruhig, sachlich) oder deutsche TTS-Stimme (z. B. ElevenLabs, deutsch, neutral). Text aus dem Skript **wortwörtlich** übernehmen.
- **Untertitel:** deutsche Untertitel einbrennen (Zugänglichkeit, Mobile ohne Ton).

### 16:9 (horizontal, YouTube/Website)

- Aufnahmeauflösung **1920×1080**, Browser auf ~1600 px Breite (Chat + Timeline nebeneinander lesbar).
- System-Skalierung so wählen, dass die Antwort-Bubble ohne Scrollen lesbar ist.
- Export: H.264, 1080p, ~8 Mbit/s.

### 9:16 (vertikal, Reels/Shorts/Status)

- Browserfenster auf **Mobile-Breite (~430 px)** stellen und das Chat-Frontend responsive aufnehmen — **nicht** das 16:9-Video seitlich beschneiden (Text wäre unlesbar).
- Alternativ: zweite Aufnahme-Session mit schmalem Viewport, gleiches Skript, gekürzte Voiceover-Pausen.
- Export: 1080×1920, H.264.

### Aufnahme-Checkliste (vor „Record")

1. Backend läuft, `DEMO_MODE=true`, Demo-Daten frisch zurückgesetzt (`POST /api/demo/reset` mit Admin-Key).
2. Szenen 2–6 in genau dieser Reihenfolge durchspielen; **keine** Extra-Nachrichten zwischendurch (sonst stimmen Dashboard-Zahlen und Ticket-Nummern nicht mit dem Skript überein).
3. Demo-Banner und Demo-Disclaimer in jeder Szene sichtbar.
4. Keine echten Kundendaten, keine echten Bestellungen, keine echten Zahlungen — alles bleibt Demo.
5. Voiceover erst nach dem Schnitt aufnehmen (Timing an die echten UI-Ereignisse anpassen).

---

## Honesty-Rulebox: Welche Demo-Nachricht erzeugt welche Szene

| Szene | Exakte Demo-Nachricht (Beispiel-Button oder Eingabe) | Echte Systemreaktion |
|---|---|---|
| 2–4 | „Hallo, wo bleibt meine Bestellung #10482?" | Intent `order_status`, Konfidenz ~0,96; Antwort mit geprüften Daten: versendet, DHL, DEMO-TRK-10482, ETA 14.10.2026, 34,99 € |
| 2–4 (Variante) | „Wo ist meine Bestellung #99999?" | „Die Bestellung #99999 wurde nicht gefunden. Bitte prüfen Sie die Nummer — oder soll sich ein Mitarbeiter bei Ihnen melden?" |
| 5 (Schritt 1) | „Ich möchte meine Bestellung zurücksenden." | Frage nach der Bestellnummer — kein Antrag, kein Ticket |
| 5 (Schritt 2) | „Ich möchte die Bestellung #10482 zurücksenden." | Retourenantrag + Ticket, 30-Tage-Vorprüfung, **keine** Autorisierung/Erstattung |
| 6 | „My package never arrived, and I want my money back immediately." | Beschwerde → Ticket mit hoher Priorität, Eskalation an Mitarbeiter, kein Geldversprechen |
| Zusatz (nicht im Video, aber filmbar) | „Ist diese Trinkflasche spülmaschinengeeignet?" | Produktfrage → „Ja, AquaPure 750 — spülmaschinengeeignet: ja." (nur Katalogdaten) |

> **Nicht behauptet:** Das Video ist nicht gerendert. Es existiert kein
> öffentliches Demo-URL (Stand Phase 8: Deploy vorbereitet, Go-Live wartet
> auf Shahids Zugangsdaten). Alle obigen Nachrichten wurden am 2026-10-09
> gegen die lokale Backend-Instanz verifiziert (Antworten wortwörtlich oben).
