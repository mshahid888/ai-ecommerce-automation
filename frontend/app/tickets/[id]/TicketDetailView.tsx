"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ApiError,
  getTicket,
  type TicketDetail,
} from "@/lib/api";

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("de-DE");
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

function InfoRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1 py-3 sm:flex-row sm:gap-6">
      <dt className="w-44 shrink-0 text-sm font-medium text-slate-600">
        {label}
      </dt>
      <dd className="text-sm text-slate-900">{children}</dd>
    </div>
  );
}

export default function TicketDetailView({ id }: { id: string }) {
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [backendDown, setBackendDown] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const numericId = Number(id);
    if (!Number.isInteger(numericId) || numericId <= 0) {
      setNotFound(true);
      setLoading(false);
      return;
    }
    getTicket(numericId)
      .then((data) => {
        if (!cancelled) setTicket(data);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) setNotFound(true);
        else setBackendDown(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/tickets"
          className="text-sm font-medium text-slate-600 underline underline-offset-2"
        >
          ← Zurück zu den Tickets
        </Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
          Ticket #{id}
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Supportvorgang mit verknüpfter Unterhaltung und Verlauf –{" "}
          <span className="font-medium">Demo-Daten</span>.
        </p>
      </div>

      {loading && (
        <p role="status" className="text-sm text-slate-600">
          Ticket wird geladen …
        </p>
      )}

      {!loading && notFound && (
        <div
          role="alert"
          className="rounded-xl border border-slate-200 bg-white px-4 py-8 text-center shadow-sm"
        >
          <p className="text-sm text-slate-600">
            Das Ticket #{id} wurde nicht gefunden.
          </p>
        </div>
      )}

      {!loading && backendDown && (
        <div
          role="alert"
          className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm"
        >
          Das Backend ist nicht erreichbar – das Ticket kann derzeit nicht
          angezeigt werden.
        </div>
      )}

      {!loading && !notFound && !backendDown && ticket && (
        <>
          <section
            aria-label="Ticket-Zusammenfassung"
            className="rounded-xl border border-slate-200 bg-white shadow-sm"
          >
            <div className="divide-y divide-slate-200 px-5">
              <InfoRow label="Anliegen">
                {ticket.intent_label_de}
                {ticket.intent && (
                  <span className="ml-2 font-mono text-xs text-slate-500">
                    ({ticket.intent})
                  </span>
                )}
              </InfoRow>
              <InfoRow label="Zusammenfassung">
                {ticket.summary ?? "–"}
              </InfoRow>
              <InfoRow label="Status">
                <span
                  className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                    ticket.status === "open"
                      ? "bg-amber-100 text-amber-800"
                      : "bg-emerald-100 text-emerald-800"
                  }`}
                >
                  {statusLabel(ticket.status)}
                </span>
              </InfoRow>
              <InfoRow label="Priorität">
                {priorityLabel(ticket.priority)}
              </InfoRow>
              <InfoRow label="Bestellung">
                <span className="font-mono">
                  {ticket.order_ref ? `#${ticket.order_ref}` : "–"}
                </span>
              </InfoRow>
              <InfoRow label="Eskalationsgrund">
                {ticket.escalation_reason ?? "–"}
              </InfoRow>
              <InfoRow label="Empfohlene nächste Aktion">
                {ticket.recommended_action ?? "–"}
              </InfoRow>
              <InfoRow label="Erstellt">
                <span className="tabular-nums">
                  {formatDate(ticket.created_at)}
                </span>
              </InfoRow>
            </div>
          </section>

          <section aria-label="Verknüpfte Unterhaltung">
            <h2 className="text-lg font-semibold text-slate-900">
              Verknüpfte Unterhaltung
            </h2>
            {ticket.messages.length === 0 ? (
              <p className="mt-2 text-sm text-slate-600">
                Keine Nachrichten vorhanden.
              </p>
            ) : (
              <ol className="mt-3 space-y-3">
                {ticket.messages.map((message) => (
                  <li
                    key={message.id}
                    className={`max-w-2xl rounded-xl border px-4 py-3 shadow-sm ${
                      message.role === "user"
                        ? "border-slate-200 bg-white"
                        : "border-slate-300 bg-slate-50"
                    }`}
                  >
                    <p className="text-xs font-semibold text-slate-500">
                      {message.role === "user" ? "Kunde" : "Assistent"}
                    </p>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-slate-800">
                      {message.content}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <section aria-label="Verlauf">
            <h2 className="text-lg font-semibold text-slate-900">
              Ereignisverlauf
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Alle tatsächlich ausgeführten Workflow-Schritte dieser
              Unterhaltung.
            </p>
            {ticket.events.length === 0 ? (
              <p className="mt-2 text-sm text-slate-600">
                Keine Ereignisse vorhanden.
              </p>
            ) : (
              <ol className="mt-3 space-y-0">
                {ticket.events.map((event, index) => (
                  <li key={event.id} className="relative flex gap-4 pb-6">
                    <div className="flex flex-col items-center">
                      <span
                        aria-hidden="true"
                        className={`mt-1 h-3 w-3 rounded-full ${
                          event.status === "failed"
                            ? "bg-red-500"
                            : "bg-slate-700"
                        }`}
                      />
                      {index < ticket.events.length - 1 && (
                        <span
                          aria-hidden="true"
                          className="mt-1 w-px flex-1 bg-slate-200"
                        />
                      )}
                    </div>
                    <div className="pb-1">
                      <p className="text-sm font-medium text-slate-800">
                        {event.label_de}
                        {event.status === "failed" && (
                          <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800">
                            Fehlgeschlagen
                          </span>
                        )}
                      </p>
                      <p className="text-xs tabular-nums text-slate-500">
                        {formatDate(event.created_at)}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </>
      )}
    </div>
  );
}
