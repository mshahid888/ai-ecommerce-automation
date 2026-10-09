# Produktions-Integrations-Checkliste — vom Demo zum Echtbetrieb

**Grundsatz:** Die Demo beweist die Workflows. Der Produktivbetrieb mit
echten Kundendaten ist ein separates Projekt mit eigenen Anforderungen.
Diese Checkliste führt vollständig dorthin — Punkt für Punkt abhaken,
nichts überspringen.

---

## 1. Echter KI-Provider

- [ ] Provider gewählt (`openai_compatible` oder `gemini`;
      Auswahlkriterien: deutsche Antwortqualität, Preis, Latenz).
- [ ] API-Key als Secret hinterlegt (Secret-Store bzw. Server-`.env`,
      Modus 0600) — **nie** im Repo, **nie** im Frontend.
- [ ] Token-/Kosten-Limits gesetzt (`LLM_MAX_TOKENS_PER_REQUEST`,
      `LLM_DAILY_REQUEST_CAP`) und mit dem Kundenbudget abgeglichen.
- [ ] Antwortqualität auf dem Kunden-Testkorpus evaluiert:
      Klassifikationsgenauigkeit je Intent dokumentiert;
      Fehlklassifikationen → ehrliche Eskalation (getestet).
- [ ] Mock bleibt als Fallback bei Provider-Ausfall/Quota-Überschreitung
      konfiguriert (bereits implementiert: `quota_fallback`).
- [ ] Prompt-Injection-Tests mit echten Kundenformulierungen
      wiederholt (der Kunde darf keine Geschäftsregeln umgehen und keine
      fremden Bestellungen einsehen können).

## 2. Authentifizierung & Zugriff

- [ ] Team-Login für Dashboard/Tickets (derzeit: kein Auth — für
      Produktion **Pflicht**).
- [ ] Admin-Funktionen (Demo-Reset entfällt; Config-Änderungen)
      hinter Rollenkonzept.
- [ ] `ADMIN_API_KEY` als echte Umgebungsvariable gesetzt (keine
      generierte Datei mehr).
- [ ] Session-Handling, Passwortregeln, ggf. 2FA für Team-Zugänge.

## 3. Datenschutz / DSGVO — offene Fragen, keine Behauptungen

> Wir behaupten **nicht**, „vollständig DSGVO-konform" zu sein.
> Folgende Punkte sind vor dem Go-Live mit dem Kunden (und ggf. dessen
> Datenschutzbeauftragten) zu klären:

- [ ] **AV-Vertrag** mit dem Kunden als Auftragsverarbeiter
      abgeschlossen (vor jedem Import echter Kundendaten).
- [ ] **TOMs** dokumentiert: Verschlüsselung (TLS, at rest),
      Zugriffskonzepte, Logging-Policy.
- [ ] **Datenminimierung:** Nur Felder importieren, die die vier
      Szenarien brauchen (kein Voll-Dump der Kundendatenbank).
- [ ] **Speicherdauer & Löschung:** Retention für Unterhaltungen,
      Tickets, Audit-Log definiert (Demo: Audit-Log wächst unbegrenzt).
- [ ] **Betroffenenrechte:** Auskunft/Löschung — Verfahren definiert,
      wer führt es aus?
- [ ] **Drittlandtransfer:** Falls der KI-Provider außerhalb der EU
      verarbeitet — Rechtsgrundlage und Kundenfreigabe dokumentiert.
- [ ] **EU AI Act:** Einordnung des Systems (Hochrisiko? Nein —
      Entscheidungsunterstützung mit Mensch im Loop; dennoch
      Transparenzpflichten gegenüber Endkunden prüfen: Hinweis, dass
      eine KI antwortet).
- [ ] **Cookie-/Tracking-Hinweis** der Kunden-Demo an dessen
      Datenschutzerklärung angebunden.

## 4. Shop-Anbindung (echt)

- [ ] Adapter auf echte Shop-API umgestellt (`STORE_BACKEND=shopify`
      bzw. WooCommerce-Adapter — letzterer ist Roadmap).
- [ ] Minimale API-Scopes vergeben (nur lesen), Token serverseitig.
- [ ] Dev-/Staging-Shop zuerst; **kein** Schreibzugriff ohne
      schriftliches Go des Kunden.
- [ ] Webhook-Signaturprüfung mit echtem Secret; Dedupe und
      Retry-Verhalten gegen die echte API getestet.
- [ ] Fehlverhalten dokumentiert: 403 (fehlende Scopes), 429
      (Rate-Limit), Timeouts → ehrliche Kunden-Antworten
      („Shop-Anbindung gestört"), keine erfundenen Daten.
- [ ] Sendungsverfolgung: echte Tracking-Links nur, wenn der Shop sie
      liefert — sonst ehrlicher Hinweis wie in der Demo.

## 5. Hosting, Backup, Monitoring

- [ ] Backend auf eigenem Server (Hetzner o. ä.): Systemd-Unit,
      Reverse-Proxy mit TLS, Security-Header (Vorlagen in
      `backend/deploy/` vorhanden).
- [ ] SQLite → verwaltete Datenbank migrieren (Repository-Schicht
      macht den Wechsel möglich, ohne Geschäftslogik zu ändern).
- [ ] Backup-Konzept: DB-Snapshots, Aufbewahrung, Restore-Test.
- [ ] Monitoring: Health-Checks, Fehlerraten-Alarm, KI-Kosten-Dashboard.
- [ ] Rate-Limiter auf geteilten Speicher umstellen (derzeit In-Memory,
      pro Worker).
- [ ] Log-Rotation für Audit-Log und App-Logs.

## 6. Multi-Store-Betrieb

- [ ] Store-Isolation erneut gegen die Produktions-DB verifiziert
      (Tests existieren für SQLite; nach Migration wiederholen).
- [ ] Pro Store: eigene Richtlinien, eigene Eskalationskontakte,
      eigene KI-Budgets.
- [ ] Onboarding-Prozess pro neuem Store dokumentiert (Checkliste 08
      als Vorlage).

## 7. Abnahme

- [ ] Alle vier Szenarien auf **echten** Kundendaten des Kunden
      reproduzierbar (Pilot-Woche-2-Kriterium wiederholt).
- [ ] Abuse-Tests gegen die Produktions-Instanz wiederholt
      (Enumeration, Oversized-Input, Rate-Limits — siehe
      `docs/SECURITY.md` §3 als Vorlage).
- [ ] Bekannte Grenzen (`03-known-limitations.md`) mit dem Kunden
      durchgegangen und schriftlich akzeptiert.
- [ ] Support-Modell vereinbart: Wer betreut die Instanz, Reaktionszeiten,
      Eskalationsweg bei Systemstörungen.

---

*Erst wenn alle Punkte abgehakt sind, ist der Schritt vom
Pilot- zum Produktivbetrieb vertretbar. Vorher gilt: Demo bleibt Demo.*
