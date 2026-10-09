"use client";

import { useEffect, useState } from "react";
import { getEvents, type WorkflowEvent } from "@/lib/api";

const STAT_CARDS = [
  { label: "Unterhaltungen (Demo)", note: "Platzhalter" },
  { label: "Offene Tickets (Demo)", note: "Platzhalter" },
  { label: "Eskalationen (Demo)", note: "Platzhalter" },
] as const;

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("de-DE");
}

export default function DashboardPage() {
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [backendDown, setBackendDown] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getEvents(20)
      .then((data) => {
        if (!cancelled) setEvents(data);
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

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Dashboard
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Übersicht für den Shop-Betrieb. Live-Daten ab Phase 6.
        </p>
      </div>

      <section aria-label="Kennzahlen (Demo)">
        <div className="grid gap-4 sm:grid-cols-3">
          {STAT_CARDS.map((card) => (
            <div
              key={card.label}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <p className="text-sm font-medium text-slate-600">{card.label}</p>
              <p className="mt-2 text-3xl font-semibold text-slate-400">–</p>
              <span className="mt-3 inline-block rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
                {card.note}
              </span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-slate-500">
          Die Kennzahlen sind Platzhalter und werden erst mit echten
          Betriebsdaten (Phase 6) befüllt.
        </p>
      </section>

      <section aria-label="Letzte Ereignisse">
        <h2 className="mb-3 text-lg font-semibold tracking-tight text-slate-900">
          Letzte Ereignisse
        </h2>

        {loading && (
          <p role="status" className="text-sm text-slate-600">
            Ereignisse werden geladen …
          </p>
        )}

        {!loading && backendDown && (
          <div
            role="alert"
            className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm"
          >
            Das Backend ist nicht erreichbar – Ereignisse können derzeit nicht
            angezeigt werden.
          </div>
        )}

        {!loading && !backendDown && events.length === 0 && (
          <p className="text-sm text-slate-600">
            Noch keine Ereignisse vorhanden.
          </p>
        )}

        {!loading && !backendDown && events.length > 0 && (
          <ul className="divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white shadow-sm">
            {events.map((event) => (
              <li
                key={event.id}
                className="flex flex-wrap items-center justify-between gap-2 px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-slate-900">
                    {event.label_de}
                  </p>
                  <p className="text-xs text-slate-500">
                    {event.event_key}
                    {event.conversation_id != null &&
                      ` · Unterhaltung #${event.conversation_id}`}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-slate-500">
                    {formatDate(event.created_at)}
                  </p>
                  <p className="text-xs text-slate-500">
                    Status: {event.status}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
