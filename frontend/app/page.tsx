"use client";

import { useEffect, useRef, useState } from "react";
import Timeline from "@/components/Timeline";
import {
  ApiError,
  apiBaseUrl,
  postChat,
  resetDemo,
  type TimelineStep,
} from "@/lib/api";

interface Message {
  id: number;
  role: "user" | "assistant";
  text: string;
  /** True when the text is the backend's honest error reply (not a normal answer). */
  isErrorReply?: boolean;
}

const EXAMPLE_QUESTIONS = [
  "Wo bleibt meine Bestellung #10482?",
  "Ist die Trinkflasche spülmaschinengeeignet?",
  "Ich möchte eine Bestellung zurücksenden.",
] as const;

let nextId = 1;
function makeId(): number {
  nextId += 1;
  return nextId;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      role: "assistant",
      text: "Wie kann ich Ihnen helfen?",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [backendDown, setBackendDown] = useState(false);
  const [timeline, setTimeline] = useState<TimelineStep[]>([]);
  const [resetNotice, setResetNotice] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const scrollAnchorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage(raw: string) {
    const text = raw.trim();
    if (!text || loading) return;

    setBackendDown(false);
    setMessages((prev) => [...prev, { id: makeId(), role: "user", text }]);
    setInput("");
    setLoading(true);

    try {
      const result = await postChat(text);
      setTimeline(result.timeline ?? []);
      setMessages((prev) => [
        ...prev,
        {
          id: makeId(),
          role: "assistant",
          text: result.reply_de || "(Keine Antwort vom Backend erhalten.)",
        },
      ]);
    } catch (error) {
      if (error instanceof ApiError && error.replyDe) {
        // The backend answered with an error but provided its honest
        // German fallback reply — render that instead of inventing one.
        setMessages((prev) => [
          ...prev,
          {
            id: makeId(),
            role: "assistant",
            text: error.replyDe as string,
            isErrorReply: true,
          },
        ]);
      } else {
        // The backend could not be reached (or returned no usable reply):
        // never fake a reply — show the honest error state.
        setBackendDown(true);
      }
    } finally {
      setLoading(false);
    }
  }

  function handleExampleClick(question: string) {
    setInput(question);
    void sendMessage(question);
  }

  async function handleResetDemo() {
    if (resetting) return;
    setResetting(true);
    setResetNotice(null);
    try {
      const result = await resetDemo();
      setTimeline([]);
      setBackendDown(false);
      setMessages([
        {
          id: makeId(),
          role: "assistant",
          text: "Wie kann ich Ihnen helfen?",
        },
      ]);
      setResetNotice(`Demo wurde zurückgesetzt (${result.demo_store}).`);
    } catch (error) {
      if (error instanceof ApiError) {
        setResetNotice(`Zurücksetzen fehlgeschlagen: ${error.message}.`);
      } else {
        setResetNotice(`Backend nicht erreichbar (${apiBaseUrl()}).`);
      }
    } finally {
      setResetting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Kunden-Chat
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Stellen Sie eine Frage zu Ihrer Bestellung, einem Produkt oder
            einer Retoure. Das Backend antwortet mit einer Demo-Antwort
            (Phase 1 – Stub).
          </p>
        </div>
        <button
          type="button"
          onClick={handleResetDemo}
          disabled={resetting}
          className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {resetting ? "Wird zurückgesetzt …" : "Demo zurücksetzen"}
        </button>
      </div>

      {resetNotice && (
        <p role="status" className="text-sm text-slate-600">
          {resetNotice}
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Chat panel */}
        <section
          aria-label="Support-Chat"
          className="flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm lg:col-span-2"
        >
          <div
            className="max-h-[480px] min-h-[320px] flex-1 space-y-4 overflow-y-auto p-4 sm:p-6"
            aria-live="polite"
          >
            {messages.map((message) =>
              message.role === "user" ? (
                <div key={message.id} className="flex justify-end">
                  <div className="max-w-[80%] rounded-2xl rounded-br-md bg-slate-900 px-4 py-2.5 text-sm text-white">
                    {message.text}
                  </div>
                </div>
              ) : (
                <div key={message.id} className="flex justify-start">
                  <div
                    className={`max-w-[85%] rounded-2xl rounded-bl-md border px-4 py-2.5 text-sm ${
                      message.isErrorReply
                        ? "border-amber-300 bg-amber-50 text-amber-900"
                        : "border-slate-200 bg-slate-50 text-slate-900"
                    }`}
                  >
                    {message.isErrorReply && (
                      <p className="mb-1 text-xs font-semibold">
                        Hinweis des Backends
                      </p>
                    )}
                    {message.text}
                  </div>
                </div>
              ),
            )}

            {loading && (
              <div className="flex justify-start">
                <div
                  role="status"
                  className="rounded-2xl rounded-bl-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-600"
                >
                  Anfrage wird bearbeitet …
                </div>
              </div>
            )}

            {backendDown && (
              <div
                role="alert"
                className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800"
              >
                <p className="font-semibold">Backend nicht erreichbar.</p>
                <p className="mt-1">
                  Das Backend antwortet nicht unter{" "}
                  <span className="font-mono">{apiBaseUrl()}</span>. Bitte
                  stellen Sie sicher, dass das Backend läuft, und versuchen Sie
                  es erneut.
                </p>
              </div>
            )}
            <div ref={scrollAnchorRef} />
          </div>

          <div className="border-t border-slate-200 bg-slate-50 p-4 sm:p-6">
            <div className="mb-4">
              <p
                id="example-questions-label"
                className="mb-2 text-xs font-semibold text-slate-600"
              >
                Beispielfragen
              </p>
              <div
                aria-labelledby="example-questions-label"
                className="flex flex-wrap gap-2"
              >
                {EXAMPLE_QUESTIONS.map((question) => (
                  <button
                    key={question}
                    type="button"
                    onClick={() => handleExampleClick(question)}
                    disabled={loading}
                    className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 transition-colors hover:border-slate-400 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>

            <form
              onSubmit={(event) => {
                event.preventDefault();
                void sendMessage(input);
              }}
              className="flex gap-2"
            >
              <div className="flex-1">
                <label htmlFor="chat-input" className="sr-only">
                  Ihre Nachricht
                </label>
                <input
                  id="chat-input"
                  type="text"
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="Ihre Nachricht …"
                  disabled={loading}
                  autoComplete="off"
                  className="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200 disabled:opacity-60"
                />
              </div>
              <button
                type="submit"
                disabled={loading || input.trim().length === 0}
                className="shrink-0 rounded-md bg-slate-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Senden
              </button>
            </form>
          </div>
        </section>

        {/* Timeline panel */}
        <aside
          aria-label="Aktivitätsverlauf"
          className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6"
        >
          <h2 className="mb-1 text-lg font-semibold tracking-tight text-slate-900">
            Aktivitätsverlauf
          </h2>
          <p className="mb-4 text-sm text-slate-600">
            Die einzelnen Schritte der letzten Anfrage, wie sie das Backend
            meldet.
          </p>
          <Timeline steps={timeline} />
        </aside>
      </div>
    </div>
  );
}
