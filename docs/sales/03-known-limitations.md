# Bekannte Grenzen — ehrlich benannt

**Stand:** 2026-10-09. Dieses Dokument gehört zum Verkaufsgespräch dazu.
Was hier steht, wird nicht verschwiegen und nicht kleingeredet.

---

## 1. Demo-Daten, keine echten Daten
Die gesamte Demo läuft mit fiktiven Daten (Shop „Muster-Shop GmbH",
Bestellungen #10482 u. a., Produkte, Kunden „Max Mustermann /
Erika Musterfrau"). Es gibt **keine** echten Bestellungen, Kunden oder
Zahlungen. Jede Antwort trägt den Demo-Hinweis.

## 2. KI-Provider: Mock als Standard
Standardmäßig antwortet ein **deterministischer Mock** mit deutschen
Keyword-Regeln (offline, kostenlos, reproduzierbar). Die Anbindung echter
Provider (`openai_compatible`, `gemini`) ist implementiert und
umschaltbar, wurde aber **nicht im Dauerbetrieb verifiziert**
(Gemini-Live-Test war durch Modell-Überlastung blockiert). Für einen
Pilotkunden mit echten Kundennachrichten ist ein echter Provider mit
Evaluierung der Antwortqualität erforderlich.

## 3. Öffentlicher Chat ohne Login — Absicht
Der Demo-Chat ist bewusst ohne Konto nutzbar. Schutz: Rate Limiting pro
IP (30/Min., 200/Tag), Input-Caps, Admin-Key für den Reset, Audit-Log.
Details: `docs/SECURITY.md`. Das ist ein **Demo**-Schutzmodell, kein
Enterprise-Sicherheitskonzept.

## 4. Keine echten Aktionen möglich
Das System kann **keine** echten Retouren autorisieren, **keine**
Rückerstattungen ausführen, **keine** Bestellungen stornieren oder ändern
und **keine** Zahlungen verarbeiten. Das ist eine bewusste
Architekturentscheidung (Trennung von KI und Geschäftslogik), kein Bug.

## 5. Einzelne Nachrichten, kein Dialoggedächtnis
Jede Nachricht startet derzeit eine eigene Unterhaltung. Mehrstufige
Dialoge mit Kontext über Nachrichten hinweg sind nicht implementiert —
die Retoure fragt deshalb bei fehlender Bestellnummer explizit nach.

## 6. Deutschsprachige Oberfläche
Die Kundenoberfläche ist derzeit deutsch. Die Geschäftslogik ist
sprachneutral angelegt; weitere Sprachen sind Roadmap, nicht Bestand.

## 7. Shopify: Schnittstelle + Simulation, kein echter Shop
Der `StoreIntegration`-Adapter existiert mit simulierter Shopify-Schicht.
**Kein echter Shopify-Shop ist angebunden.** Eine Dev-Store-Anbindung
ist vorbereitet (Schritte in `docs/SHOPIFY.md`), braucht aber ein
Shopify-Partner-Konto des Kunden bzw. von uns.

## 8. Kein öffentliches Deployment (Stand heute)
Das Deployment ist vorbereitet (Systemd-Unit, Nginx-Beispiel,
Vercel-Konfiguration, `docs/DEPLOYMENT.md`) — es gibt **derzeit keine
öffentliche Demo-URL**. Go-Live wartet auf Zugangsdaten
(GitHub-Push, Vercel, Hetzner-Backend).

## 9. Nicht produktionsreif für echte Kundendaten
Für den Betrieb mit echten Kundendaten fehlen (bewusst noch nicht
gebaut): Benutzer-Authentifizierung, DSGVO-Auftragsverarbeitung
(AV-Vertrag, TOMs — siehe `docs/sales/09-production-integration-checklist.md`),
Backup-/Monitoring-Konzept, WAF/DDoS-Schutz, Secrets-Rotation.
→ Verweis: `docs/SECURITY.md` §1 „Explizit NICHT geschützt" und §4.

## 10. Ein-Worker-nahe Demo-Architektur
SQLite als Datei-DB, In-Memory-Rate-Limiter (Zähler gehen bei Neustart
verloren), unbegrenzt wachsendes Audit-Log. Für die Demo angemessen —
für Produktion zu ersetzen (siehe Produktions-Checkliste).

---

*Diese Grenzen sind der Grund, warum das erste Angebot ein
**4-Wochen-Pilot** ist (`docs/sales/07-pilot-scope.md`) — kein
„Plug-and-play-Produkt".*
