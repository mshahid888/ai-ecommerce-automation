"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { getTickets, type Ticket } from "@/lib/api";

function statusBadgeClass(status: string): string {
  if (status === "open") return "bg-amber-100 text-amber-800";
  if (status === "closed") return "bg-emerald-100 text-emerald-800";
  return "bg-slate-100 text-slate-700";
}

function statusLabel(status: string): string {
  if (status === "open") return "Offen";
  if (status === "closed") return "Geschlossen";
  return status;
}

function priorityLabel(priority: string | null): string {
  if (priority === "high") return "Hoch";
  if (priority === "normal") return "Normal";
  if (priority === "low") return "Niedrig";
  return priority ?? "–";
}

function priorityBadgeClass(priority: string | null): string {
  if (priority === "high") return "bg-red-100 text-red-800";
  if (priority === "low") return "bg-slate-100 text-slate-600";
  return "bg-blue-100 text-blue-800";
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("de-DE");
}

export default function TicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [backendDown, setBackendDown] = useState(false);
  const [onlyOpen, setOnlyOpen] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    let cancelled = false;
    getTickets(50, onlyOpen ? "open" : undefined)
      .then((data) => {
        if (!cancelled) {
          setTickets(data);
          setBackendDown(false);
        }
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
  }, [onlyOpen]);

  useEffect(load, [load]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Tickets
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Eskalierte Anfragen aus dem Chat –{" "}
            <span className="font-medium">Demo-Daten</span>.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setOnlyOpen((v) => !v)}
          aria-pressed={onlyOpen}
          className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
            onlyOpen
              ? "bg-slate-700 text-white"
              : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
          }`}
        >
          {onlyOpen ? "Alle anzeigen" : "Nur offene anzeigen"}
        </button>
      </div>

      {loading && (
        <p role="status" className="text-sm text-slate-600">
          Tickets werden geladen …
        </p>
      )}

      {!loading && backendDown && (
        <div
          role="alert"
          className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm"
        >
          Das Backend ist nicht erreichbar – Tickets können derzeit nicht
          angezeigt werden.
        </div>
      )}

      {!loading && !backendDown && tickets.length === 0 && (
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-8 text-center shadow-sm">
          <p className="text-sm text-slate-600">
            {onlyOpen
              ? "Keine offenen Tickets vorhanden."
              : "Noch keine Tickets vorhanden. Starten Sie eine Unterhaltung auf der Chat-Seite – Eskalationen und Retouren erzeugen automatisch ein Ticket."}
          </p>
        </div>
      )}

      {!loading && !backendDown && tickets.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full min-w-[720px] text-left text-sm">
            <caption className="sr-only">
              Liste der Support-Tickets – Zeile anklicken für Details
            </caption>
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr>
                <th scope="col" className="px-4 py-3 font-semibold text-slate-700">
                  Ticket-ID
                </th>
                <th scope="col" className="px-4 py-3 font-semibold text-slate-700">
                  Anliegen
                </th>
                <th scope="col" className="px-4 py-3 font-semibold text-slate-700">
                  Status
                </th>
                <th scope="col" className="px-4 py-3 font-semibold text-slate-700">
                  Priorität
                </th>
                <th scope="col" className="px-4 py-3 font-semibold text-slate-700">
                  Bestellung
                </th>
                <th scope="col" className="px-4 py-3 font-semibold text-slate-700">
                  Erstellt
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {tickets.map((ticket) => (
                <tr key={ticket.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link
                      href={`/tickets/${ticket.id}`}
                      className="font-mono font-medium text-slate-900 underline underline-offset-2"
                    >
                      #{ticket.id}
                    </Link>
                  </td>
                  <td className="max-w-[280px] truncate px-4 py-3 text-slate-700">
                    <Link
                      href={`/tickets/${ticket.id}`}
                      className="hover:underline"
                      title={ticket.summary ?? ticket.intent ?? ""}
                    >
                      {ticket.intent_label_de ?? ticket.intent ?? "–"}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusBadgeClass(ticket.status)}`}
                    >
                      {statusLabel(ticket.status)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${priorityBadgeClass(ticket.priority)}`}
                    >
                      {priorityLabel(ticket.priority)}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-slate-700">
                    {ticket.order_ref ? `#${ticket.order_ref}` : "–"}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 tabular-nums text-slate-600">
                    {formatDate(ticket.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
