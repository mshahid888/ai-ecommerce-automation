# Pilotumfang — 4-Wochen-Pilot für Shop-Betreiber

**Ziel:** Auf Basis der Kundendaten **eines** Shops nachweisen, dass die
vier Demo-Szenarien (Bestellstatus, Produktfrage, Retoure, Eskalation)
zuverlässig auf echten Shop-Daten laufen — bevor über einen
Produktivbetrieb gesprochen wird.

**Kein Erfolgsversprechen:** Der Pilot misst, was tatsächlich passiert.
Es werden keine Einsparungen, keine Automatisierungsquoten und keine
Umsatzeffekte garantiert.

---

## Woche 1 — Daten & Richtlinien

**Wir liefern:**
- Einrichtung einer separaten Pilot-Instanz (eigene Datenbank, eigene
  Konfiguration — keine Vermischung mit der öffentlichen Demo).
- Import-Skripte für Produktkatalog und Bestelldaten aus den Formaten
  des Kunden (CSV/Excel/API — siehe Onboarding-Checkliste).

**Der Kunde liefert:**
- Produktkatalog-Export (Name, Beschreibung, relevante Attribute,
  Bestand).
- Bestelldaten-Export oder Lesezugriff (mind. Bestellnummer, Status,
  Versandpartner, Sendungsreferenz, Datum, Betrag).
- Retouren-, Versand- und Zahlungsrichtlinie als Text (Vorlage:
  `04-sample-store-policy.md`).
- Eskalationskontakte (wer erhält Tickets welcher Priorität, auf welchem
  Kanal).

**Erfolgskriterium:** Alle Daten sind importiert; die vier Szenarien
laufen auf Kundendaten in einer geschlossenen Testumgebung.

## Woche 2 — Anpassung & Antwortqualität

**Wir liefern:**
- Übernahme der Kundenrichtlinien in die deterministische
  Regel-Engine (Retourenfrist, Versandkosten, Zahlungsarten).
- Anpassung von Tonalität und Antwortvorlagen (Anrede, Markenstimme).
- Feinabstimmung der Intent-Erkennung anhand echter Kundenformulierungen
  des Kunden (Stichprobe, vom Kunden bereitgestellt oder anonymisiert).
- Anbindung eines echten KI-Providers (Kosten trägt das vereinbarte
  KI-Budget; Mock bleibt als Fallback).

**Der Kunde liefert:**
- 20–50 echte, anonymisierte Kundenanfragen als Testkorpus (freiwillig,
  aber stark empfohlen).
- Feedback zu Tonalität und Antwortvorlagen (eine Feedback-Runde).

**Erfolgskriterium:** Alle vier Demo-Szenarien sind auf Kundendaten
reproduzierbar; Fehlklassifikationen der Teststichprobe sind
dokumentiert und eskalieren ehrlich statt zu raten.

## Woche 3 — Eskalation & Dashboard im Team-Test

**Wir liefern:**
- Eskalations-Workflow an das Kunden-Team (Ticket-Benachrichtigung per
  E-Mail oder vorhandenes Ticketsystem, soweit ohne Zusatzkosten
  machbar).
- Team-Zugang zum Operations-Dashboard und zur Ticket-Ansicht.
- Dokumentierte Antwortzeit- und Verfügbarkeitsgrenzen der Pilot-Instanz.

**Der Kunde liefert:**
- 1–2 Teammitglieder, die Eskalations-Tickets sichten und bewerten
  (Aufwand: ca. 2–3 Stunden in dieser Woche).
- Bewertung: War die Eskalation berechtigt? War die Ticket-Qualität
  brauchbar?

**Erfolgskriterium:** Eskalierte Fälle landen vollständig und
nachvollziehbar beim Team; kein kritischer Fall wird stillschweigend
„beantwortet".

## Woche 4 — Auswertung & Entscheidung

**Wir liefern:**
- Auswertungsbericht: Anzahl Vorgänge je Intent, Eskalationsquote,
  dokumentierte Fehlfälle, ehrliche Einschätzung, welche Anliegen sich
  für den Produktivbetrieb eignen.
- Angebot für den Produktivbetrieb **oder** begründete Empfehlung,
  (noch) nicht live zu gehen.
- Übergabe aller Konfigurationen und Dokumentation an den Kunden.

**Der Kunde entscheidet:**
- Go / No-Go für den Produktivbetrieb (Checkliste:
  `09-production-integration-checklist.md`).
- Bei Go: Festlegung von Hosting, KI-Budget und Support-Modell.

**Erfolgskriterium:** Der Kunde kann auf Basis des Berichts eine
fundierte Entscheidung treffen — unabhängig davon, wie sie ausfällt.

---

## Rahmenbedingungen

- **Daten:** Pilot läuft auf einer separaten Instanz; keine echten
  Kundendaten in der öffentlichen Demo. AV-Vertrag vor Import echter
  Kundendaten (siehe Produktions-Checkliste).
- **Kosten:** Hosting und KI-Nutzung des Piloten werden vorab
  transparent aufgeschlüsselt; keine versteckten Abos.
- **Eigentum:** Konfigurationen und Dokumentation gehören dem Kunden;
  die Plattform bleibt beim Anbieter (Lizenz-/Betriebsmodell wird im
  Angebot in Woche 4 festgelegt).
- **Abbruch:** Der Pilot kann beidseitig wöchentlich beendet werden;
  bereits gelieferte Dokumentation bleibt beim Kunden.
