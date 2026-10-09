"use client";

import { useEffect, useState } from "react";
import { getTickets, type Ticket } from "@/lib/api";

function statusBadgeClass(status: string): string {
  if (status === "open") return "bg-amber-100 text-amber-800";
  if (status === "closed") return "bg-emerald-100 text-emerald-800";
  return "bg-slate-100 text-slate-700";
}

export default function TicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [backendDown, setBackendDown] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getTickets(50)
      .then((data) => {
        if (!cancelled) setTickets(data);
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
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Tickets
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Eskalierte Anfragen aus dem Chat (Phase 1 – lesend).
        </p>
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
            Noch keine Tickets vorhanden.
          </p>
        </div>
      )}

      {!loading && !backendDown && tickets.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full min-w-[560px] text-left text-sm">
            <caption className="sr-only">
              Liste der Support-Tickets
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
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {tickets.map((ticket) => (
                <tr key={ticket.id}>
                  <td className="px-4 py-3 font-mono text-slate-900">
                    #{ticket.id}
                  </td>
                  <td className="px-4 py-3 text-slate-700">
                    {ticket.summary ?? ticket.intent ?? "–"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusBadgeClass(ticket.status)}`}
                    >
                      {ticket.status}
                    </span>
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
