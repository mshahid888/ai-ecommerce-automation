# Feature-Liste — AI E-Commerce Automation

**Stand:** 2026-10-09 · Phasen 0–9 abgeschlossen · **107 automatisierte Tests, alle grün**
**Demo-Umgebung:** alle Daten simuliert (Shop „Muster-Shop GmbH")

Diese Liste beschreibt ausschließlich, was die Software **tatsächlich**
kann. Sie ist in drei Zonen geteilt — nichts aus „Simuliert" oder
„Später" darf als heute verfügbare Funktion verkauft werden.

---

## ✅ Verfügbar (implementiert und getestet)

### KI-Kundensupport (deutsch)
- Chat-Antworten auf Deutsch für die 11 erkannten Anliegen:
  Bestellstatus, Produktfrage, Retourenanfrage, Beschwerde, Menschlicher
  Support, Versandinfo, Zahlungsfrage, Produktverfügbarkeit,
  Bestellstornierung, Begrüßung, Unbekannt.
- Deutsche Mock-Klassifikation (deterministisch, offline) als Standard;
  umschaltbar auf echte Provider (`openai_compatible`, `gemini`) per
  Umgebungsvariable.
- Konfidenz < 0,6 → automatische Eskalation an einen Mitarbeiter mit
  ehrlicher Erklärung. `complaint`, `order_cancel`, `human_support`,
  `unknown` → **immer** Mensch (ALWAYS_HUMAN-Regel).
- Das LLM interpretiert nur Sprache und extrahiert strukturierte Daten.
  **Alle** Aktionen (Lookup, Policy-Prüfung, Ticket-Erstellung, Eskalation)
  laufen in deterministischem Python-Code — validiert vor jeder Verwendung.

### Bestellstatus-Abfrage
- Bestellnummer-Extraktion aus Freitext („Hallo, wo bleibt meine
  Bestellung #10482?").
- Prüfung in den Shop-Daten; Antwort nur aus verifizierten Feldern
  (Status, Versandpartner, Sendungsreferenz, voraussichtliche Zustellung,
  Bestellwert).
- Unbekannte Bestellung → ehrliche Klärung + Angebot zur
  Mitarbeiter-Übergabe, niemals erfundene Daten.

### Produktfragen aus dem Katalog
- Antworten ausschließlich aus dem hinterlegten Produktkatalog
  (Beschreibung + Attribute), z. B. „AquaPure 750 — spülmaschinengeeignet: ja".
- Unbekannte Produkte oder Attribute → ehrliches „keine Information"
  + Eskalationsangebot.
- Verfügbarkeitsabfrage mit echtem Lagerbestand („nicht auf Lager" bei 0).

### Retouren-Triage (deterministisch)
- Sammeln der Bestellnummer → Lookup → **deterministische**
  30-Tage-Rückgabefrist-Prüfung aus der konfigurierten Shop-Richtlinie
  (kein LLM-Urteil, keine Rechtsauslegung).
- Klare Trennung: Informationssammlung → vorläufige
  Eignungsprüfung → Antragstellung. **Keine Autorisierung, keine
  Rückerstattung** — der Code kann das nicht ausführen.
- Jede Retoure erzeugt einen Retourenantrag + Support-Ticket mit
  Eskalationsgrund („Freigabe durch Mitarbeiter erforderlich").

### Tickets, Eskalation, Timeline
- Support-Tickets mit ID, Anliegen, Bestellung, Status, Priorität,
  Eskalationsgrund, Zusammenfassung, Ereignisverlauf; Detailseite im
  Frontend.
- Echte Aktivitäts-Timeline: jeder Eintrag („Anfrage empfangen",
  „Anliegen erkannt", „Bestellnummer extrahiert", „Demo-Bestellung
  geprüft", „Geschäftsregeln angewendet", „Antwort erstellt",
  „Supportvorgang protokolliert" …) entspricht einer **tatsächlich
  ausgeführten** Backend-Operation.
- Operations-Dashboard mit **echten DB-Zählern**: Unterhaltungen,
  Nachrichten, offene Tickets, Eskalationen, Anliegen-Verteilung,
  neueste Workflow-Events.

### Sicherheit & Missbrauchsschutz (Demo)
- Rate Limiting pro IP: Chat 30/Min. + 200/Tag, Lesezugriffe 60/Min.,
  Demo-Reset 5/Std. (konfigurierbar, 429 mit deutschem Text).
- KI-Tageskontingent für echte Provider (Standard 500 Calls/Tag);
  bei Überschreitung ehrlicher Mock-Fallback statt Ausfall.
- Admin-Key für den Demo-Reset (Constant-Time-Vergleich, 401 ohne Key).
- Input-Caps (2000 Zeichen/Nachricht, 64 KiB Body), deutsche 400er,
  keine Stack-Trace-Leaks, kein `dangerouslySetInnerHTML`.
- Audit-Log (append-only, IPs gehasht, überlebt Demo-Resets).
- Demo-Reset stellt **nur** Demo-Daten wieder her.

### Multi-Store-Architektur
- Jede Geschäftstabelle trägt `store_id`; die Repository-Schicht erzwingt
  Store-Isolation in jeder Abfrage (getestet).
- Shop-Richtlinien (Retoure, Versand, Zahlung) sind explizite
  Konfigurationsdaten — nicht im Prompt hartcodiert.

### Shopify-Schnittstelle
- Einheitliches `StoreIntegration`-Interface (Demo ↔ Shopify).
- `SimulatedShopifyAdapter`: gleiche Demo-Daten in Shopify-förmigen
  Antworten (`gid://shopify/Order/…`, `simulated: True`) — umschaltbar per
  `STORE_BACKEND`.
- Webhook-Endpunkt mit HMAC-Prüfung, Dedupe und ehrlichem 503 ohne
  konfiguriertes Secret.

---

## ⚠️ Simuliert (in der Demo bewusst unecht)

- **Alle Daten:** Shop, Bestellungen (#10482 u. a.), Produkte, Kunden
  („Max Mustermann"), Sendungsreferenzen (`DEMO-TRK-…`), Lieferdaten —
  alles fiktiv, alles als Demo gekennzeichnet.
- **KI-Provider:** Standard ist der deterministische Mock (deutsche
  Keyword-Regeln). Die Gemini-/OpenAI-Anbindung existiert, wurde aber
  nicht im Dauerbetrieb verifiziert.
- **Shopify:** nur simulierte Integration; **kein echter Shop
  angebunden**, kein Dev-Store, keine Credentials.
- **Retouren:** Antragstellung und Vorprüfung sind echt implementiert —
  Autorisierung und Rückerstattung sind absichtlich nicht möglich.
- **Versandinfos:** Versandkosten/-zeiten stammen aus der konfigurierten
  Richtlinie, nicht aus einer Live-Carrier-API.

## 🔜 Später (Roadmap, nicht implementiert)

- Abandoned-Cart-Recovery, Inventar-Alerts, Bestellverarbeitungs-Workflows
  (Phase 11)
- WooCommerce-Adapter, Multi-Store-Administration
- Mehrsprachigkeit (UI derzeit deutsch)
- Echte Shopify-Dev-Store-Anbindung (Schritte dokumentiert in
  `docs/SHOPIFY.md`, braucht Shahids Partner-Konto)
- Öffentliches Demo-Deployment (vorbereitet, Go-Live wartet auf
  Zugangsdaten — siehe `docs/DEPLOYMENT.md`)

---

*Detailnachweise: `docs/SECURITY.md` (Tests + Abuse-Verifikation),
`docs/SHOPIFY.md` (Integrationsstand), `docs/sales/10-test-report.md`
(Testbericht), `docs/sales/03-known-limitations.md` (Grenzen).*
