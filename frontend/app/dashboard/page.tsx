"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  getDashboardSummary,
  type DashboardSummary,
} from "@/lib/api";

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("de-DE");
}

const CARD_DEFS = [
  {
    key: "conversations_count" as const,
    label: "Unterhaltungen",
    description: "Chat-Unterhaltungen in der Demo-Datenbank",
  },
  {
    key: "messages_count" as const,
    label: "Nachrichten",
    description: "Kunden- und Assistentennachrichten",
  },
  {
    key: "tickets_open" as const,
    label: "Offene Tickets",
    description: "Supportfälle mit Mitarbeiterbedarf",
  },
  {
    key: "escalations_count" as const,
    label: "Eskalationen",
    description: "Explizite Übergaben an Mitarbeiter",
  },
] as const;

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [backendDown, setBackendDown] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getDashboardSummary()
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch(() => {
        if (!cancelled) setBackendDown(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const maxIntentCount = Math.max(
    0,
    ...(summary?.intents_breakdown.map((b) => b.count) ?? []),
  );

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Dashboard
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Betriebsübersicht für den Demo-Shop – alle Zahlen stammen aus der
          Datenbank und sind als{" "}
          <span className="font-medium">Demo-Daten</span> gekennzeichnet.
        </p>
      </div>

      {loading && (
        <p role="status" className="text-sm text-slate-600">
          Dashboard wird geladen …
        </p>
      )}

      {!loading && backendDown && (
        <div
          role="alert"
          className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm"
        >
          Das Backend ist nicht erreichbar – Kennzahlen können derzeit nicht
          angezeigt werden.
        </div>
      )}

      {!loading && !backendDown && summary && (
        <>
          <section aria-label="Kennzahlen">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {CARD_DEFS.map((card) => (
                <div
                  key={card.key}
                  className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
                >
                  <p className="text-sm font-medium text-slate-600">
                    {card.label}
                  </p>
                  <p className="mt-2 text-3xl font-semibold tabular-nums text-slate-900">
                    {summary[card.key]}
                  </p>
                  <span className="mt-3 inline-block rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
                    Demo-Daten
                  </span>
                  <p className="mt-2 text-xs text-slate-500">
                    {card.description}
                  </p>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Tickets gesamt:{" "}
              <span className="font-medium tabular-nums text-slate-700">
                {summary.tickets_total}
              </span>{" "}
              (Demo-Daten) ·{" "}
              <Link
                href="/tickets"
                className="font-medium text-slate-700 underline underline-offset-2"
              >
                Alle Tickets ansehen
              </Link>
            </p>
          </section>

          <section aria-label="Anliegen-Verteilung">
            <h2 className="text-lg font-semibold text-slate-900">
              Anliegen-Verteilung
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Erkannte Absichten aus echten Chat-Unterhaltungen.{" "}
              <span className="font-medium">Demo-Daten</span> – keine
              Geschäftsauswertung.
            </p>
            {summary.intents_breakdown.length === 0 ? (
              <div className="mt-4 rounded-xl border border-slate-200 bg-white px-4 py-8 text-center shadow-sm">
                <p className="text-sm text-slate-600">
                  Noch keine Unterhaltungen vorhanden. Starten Sie eine
                  Unterhaltung auf der{" "}
                  <Link href="/" className="font-medium underline">
                    Chat-Seite
                  </Link>
                  , um die Verteilung zu sehen.
                </p>
              </div>
            ) : (
              <div className="mt-4 space-y-3">
                {summary.intents_breakdown.map((row) => (
                  <div key={row.intent}>
                    <div className="flex items-baseline justify-between text-sm">
                      <span className="font-medium text-slate-800">
                        {row.label_de}
                      </span>
                      <span className="tabular-nums text-slate-600">
                        {row.count}
                      </span>
                    </div>
                    <div
                      role="img"
                      aria-label={`${row.label_de}: ${row.count}`}
                      className="mt-1 h-2.5 overflow-hidden rounded-full bg-slate-100"
                    >
                      <div
                        className="h-full rounded-full bg-slate-700"
                        style={{
                          width: `${
                            maxIntentCount > 0
                              ? Math.max(
                                  4,
                                  Math.round(
                                    (row.count / maxIntentCount) * 100,
                                  ),
                                )
                              : 0
                          }%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section aria-label="Letzte Aktivitäten">
            <h2 className="text-lg font-semibold text-slate-900">
              Letzte Aktivitäten
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Tatsächlich ausgeführte Workflow-Schritte – jeder Eintrag
              entspricht einer Operation im Backend.
            </p>
            {summary.recent_events.length === 0 ? (
              <div className="mt-4 rounded-xl border border-slate-200 bg-white px-4 py-8 text-center shadow-sm">
                <p className="text-sm text-slate-600">
                  Noch keine Aktivitäten protokolliert.
                </p>
              </div>
            ) : (
              <ol className="mt-4 space-y-2">
                {summary.recent_events.map((event) => (
                  <li
                    key={event.id}
                    className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm"
                  >
                    <span className="font-medium text-slate-800">
                      {event.label_de}
                      {event.status === "failed" && (
                        <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800">
                          Fehlgeschlagen
                        </span>
                      )}
                    </span>
                    <span className="text-xs tabular-nums text-slate-500">
                      {formatDate(event.created_at)}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </section>
          <section aria-label="Sicherheit und Datenschutz (Demo)">
            <h2 className="text-lg font-semibold text-slate-900">
              Sicherheit &amp; Datenschutz (Demo)
            </h2>
            <div className="mt-3 rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-700 shadow-sm">
              <ul className="list-disc space-y-2 pl-5">
                <li>
                  <span className="font-medium">Simulierte Daten:</span>{" "}
                  Alle Bestellungen, Produkte und Kunden in dieser Demo sind
                  frei erfunden. Es werden keine echten Bestellungen
                  verarbeitet und keine echten Retouren oder
                  Rückerstattungen ausgeführt.
                </li>
                <li>
                  <span className="font-medium">Keine echten Zahlungen:</span>{" "}
                  Die Demo fragt keine Zahlungsdaten ab und speichert keine
                  personenbezogenen Daten echter Kunden.
                </li>
                <li>
                  <span className="font-medium">Nutzungsbegrenzung:</span>{" "}
                  Anfragen sind pro Besucher begrenzt (Chat, Leserequests und
                  Demo-Zurücksetzung). Bei Überschreitung antwortet das
                  Backend mit HTTP&nbsp;429 und einer Wartezeit.
                </li>
                <li>
                  <span className="font-medium">KI-Kontingent:</span> Die
                  Anzahl echter KI-Anfragen pro Tag ist gedeckelt. Ist das
                  Kontingent aufgebraucht, antwortet das Demo-Regelwerk —
                  das wird in der Unterhaltung ehrlich gekennzeichnet.
                </li>
                <li>
                  <span className="font-medium">Admin-Schutz:</span> Das
                  Zurücksetzen der Demo erfordert einen serverseitigen
                  Admin-Schlüssel. Sicherheitsrelevante Ereignisse
                  (z.&nbsp;B. fehlgeschlagene Admin-Versuche) werden in einem
                  unveränderlichen Audit-Protokoll festgehalten.
                </li>
              </ul>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
