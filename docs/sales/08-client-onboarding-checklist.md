# Client-Onboarding-Checkliste

**Zweck:** Alles, was wir vom Shop-Betreiber brauchen, um den
4-Wochen-Piloten zu starten. Je vollständiger die Antworten, desto
schneller die Woche 1.

---

## A. Daten

- [ ] **Produktkatalog-Export** — Format: CSV, Excel oder API-Zugang.
      Benötigte Felder: Artikelnummer/SKU, Name, Beschreibung,
      kundenrelevante Attribute (z. B. Material, Maße, Pflegehinweise),
      aktueller Bestand.
- [ ] **Bestelldaten** — Export oder Lesezugriff (Shopify, WooCommerce,
      JTL, …). Benötigte Felder: Bestellnummer, Status, Kundenzuordnung
      (pseudonymisiert genügt), Versandpartner, Sendungsreferenz,
      Bestelldatum, Betrag, Währung.
- [ ] **Testkorpus (empfohlen):** 20–50 echte, anonymisierte
      Kundenanfragen aus E-Mail/Chat der letzten Monate — zur
      Abstimmung der Intent-Erkennung.
- [ ] **Datenformat-Abstimmung:** Zeichensatz (UTF-8), Trennzeichen,
      Update-Rhythmus (einmalig vs. täglich).

## B. Richtlinien & Entscheidungen

- [ ] **Retourenrichtlinie** als Text: Frist in Tagen, Bedingungen,
      Ausnahmen, Rücksendeadresse (Vorlage:
      `04-sample-store-policy.md`).
- [ ] **Versandrichtlinie:** Kosten, Freigrenze, Lieferzeiten, Carrier.
- [ ] **Zahlungsarten:** Liste der angebotenen Zahlungsmethoden.
- [ ] **Eskalationsregeln:** Welche Anliegen immer zum Menschen?
      (Standard: Beschwerde, Stornierung, unbekannte Anliegen,
      Konfidenz < 0,6.) Wer erhält Tickets welcher Priorität, auf
      welchem Kanal (E-Mail, Ticketsystem, Messenger)?
- [ ] **Markenstimme:** Anrede (Du/Sie), Ton (sachlich/freundlich),
      No-Go-Formulierungen, Impressums-/Kontaktangaben für Antworten.
- [ ] **Sprache:** Deutsch als Startsprache bestätigt; weitere Sprachen
      als Wunsch vermerken (Roadmap).

## C. Technisch

- [ ] **Shop-System:** Shopify / WooCommerce / JTL / Shopware / sonstiges
      + Version.
- [ ] **API-Zugang (lesend):** API-Credentials mit minimalen Scopes
      (nur lesen: Bestellungen, Produkte) — Token werden serverseitig
      in der `.env` (Modus 0600) abgelegt, nie committet, nie im
      Frontend.
- [ ] **Webhook-Wunsch:** Soll der Shop Ereignisse senden (z. B.
      Bestellstatus-Änderungen)? Falls ja: HTTPS-Endpunkt und Secret
      abstimmen.
- [ ] **Domain/Subdomain** für die Kunden-Demo (z. B.
      `support.meinshop.de`) — falls gewünscht.
- [ ] **Ansprechpartner Technik:** Name, E-Mail, Erreichbarkeit für
      Rückfragen in Woche 1–2.

## D. Organisatorisch

- [ ] **Pilot-Ansprechpartner** auf Kundenseite (fachlich) benannt.
- [ ] **1–2 Teammitglieder** für den Eskalations-Test in Woche 3
      reserviert (ca. 2–3 Stunden).
- [ ] **AV-Vertrag** vor Import echter Kundendaten abgeschlossen
      (Entwurf stellen wir; Details in
      `09-production-integration-checklist.md`).
- [ ] **KI-Budget** für Woche 2–4 vereinbart (echter Provider;
      Kostenrahmen vorab transparent).

---

*Nach Eingang von A–C startet Woche 1 des Piloten
(`07-pilot-scope.md`). Unvollständige Punkte werden als offene
Risiken im Wochenbericht geführt — nicht stillschweigend angenommen.*
