# Muster-Shop-Richtlinie (Vorlage für Kunden)

**Zweck:** Diese Datei zeigt, wie die Shop-Richtlinien des Demo-Shops
hinterlegt sind — als **explizite Konfigurationsdaten**, die die
deterministische Geschäftslogik liest (nicht als Prompt-Text).
Ein Kunde erhält dieselbe Struktur mit **seinen** Werten befüllt.

Quelle im Code: `backend/app/db/seed.py` (`_POLICIES`), Tabellen
`store_policies`. Stand: 2026-10-09.

---

## Retourenrichtlinie (`returns`)

| Feld | Demo-Wert |
|---|---|
| Rückgabefrist | 30 Tage |
| Widerrufsfrist | 14 Tage |
| Bedingungen | Ware unbenutzt und in Originalverpackung; Bestellnummer angeben |
| Ausnahmen | versiegelte Hygieneartikel nach Öffnung |
| Rücksendeadresse | Muster-Shop GmbH, Retouren, Musterstraße 1, 37073 Göttingen |
| Hinweis | „Dies ist eine Demo-Richtlinie. Im Demo-Modus werden keine echten Retouren autorisiert und keine Rückerstattungen ausgeführt." |

**Wie sie verwendet wird:** Die Retouren-Triage prüft deterministisch,
ob das Bestelldatum innerhalb der 30-tägigen Frist liegt. Ergebnis ist
eine **vorläufige** Eignungsprüfung; die endgültige Freigabe übernimmt
immer ein Mitarbeiter. Es findet keine Rechtsauslegung durch das
Sprachmodell statt.

## Versandrichtlinie (`shipping`)

| Feld | Demo-Wert |
|---|---|
| Versandkosten | 4,99 € |
| Versandkostenfrei ab | 50,00 € |
| Lieferzeit | 2–4 Werktage |
| Versandpartner | DHL, Hermes |
| Tracking-Hinweis | „Demo-Umgebung: Sendungsnummern sind fiktiv, keine Live-Sendungsverfolgung." |

**Wie sie verwendet wird:** Intent `shipping_info` beantwortet
Versandkosten- und Lieferzeitfragen ausschließlich aus diesen Werten.

## Zahlungsrichtlinie (`payments`)

| Feld | Demo-Wert |
|---|---|
| Zahlungsarten | PayPal, Kreditkarte (Visa/Mastercard), Kauf auf Rechnung, Vorkasse per Überweisung |
| Hinweis | „Zahlungsabwicklung erfolgt über den Zahlungsanbieter des Shops; im Demo-Modus werden keine echten Zahlungen ausgeführt." |

**Wie sie verwendet wird:** Intent `payment_question` listet die
konfigurierten Zahlungsarten auf. Zahlungsabwicklung selbst ist
außerhalb des Systemumfangs.

---

## Was ein Kunde anpassen muss (Onboarding)

1. **Retoure:** Frist in Tagen, Bedingungen, Ausnahmen,
   Rücksendeadresse, Eskalationskontakt für Freigaben.
2. **Versand:** Kosten, Freigrenze, Lieferzeiten, Carrier, Umgang mit
   Sendungsverfolgung (echte Tracking-Links erst mit Shop-Anbindung).
3. **Zahlung:** angebotene Zahlungsarten, Ansprechpartner bei
   Zahlungsproblemen.
4. **Eskalationsregeln:** welche Anliegen immer zum Menschen
   (Standard: Beschwerde, Stornierung, unbekannte Anliegen,
   Konfidenz < 0,6), Erreichbarkeit und Reaktionszeit-Zusagen.
5. **Tonalität:** Anrede (Du/Sie), Markenstimme für Antwortvorlagen.

Siehe `docs/sales/08-client-onboarding-checklist.md`.
