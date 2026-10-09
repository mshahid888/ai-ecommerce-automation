/**
 * Typed client for the AI E-Commerce Automation backend (Phase 1).
 *
 * Base URL comes from NEXT_PUBLIC_API_URL (default: http://127.0.0.1:8000).
 * No secrets are used here — this is the public demo frontend.
 */

const API_URL: string =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export function apiBaseUrl(): string {
  return API_URL;
}

/** One step of the workflow timeline returned by POST /api/chat. */
export interface TimelineStep {
  key: string;
  label_de: string;
  status: string;
}

/** Successful POST /api/chat response (Phase 1). */
export interface ChatResponse {
  conversation_id: number;
  intent: string;
  confidence: number;
  order_ref: string | null;
  reply_de: string;
  timeline: TimelineStep[];
  ticket_id: number | string | null;
  provider: string;
}

/** A ticket row from GET /api/tickets. */
export interface Ticket {
  id: number;
  conversation_id: number | null;
  intent: string | null;
  order_ref: string | null;
  summary: string | null;
  status: string;
  priority: string | null;
  escalation_reason: string | null;
  recommended_action: string | null;
  created_at: string;
}

/** A workflow event row from GET /api/events. */
export interface WorkflowEvent {
  id: number;
  store_id: string;
  conversation_id: number | null;
  event_key: string;
  label_de: string;
  status: string;
  created_at: string;
}

/** Thrown when the backend answers with a non-2xx status.
 *  Carries the backend's honest German reply (reply_de) when present. */
export class ApiError extends Error {
  status: number;
  replyDe?: string;

  constructor(status: number, message: string, replyDe?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.replyDe = replyDe;
  }
}

interface ErrorPayload {
  error?: string;
  detail?: string;
  reply_de?: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, init);

  if (!res.ok) {
    let payload: ErrorPayload | null = null;
    try {
      payload = (await res.json()) as ErrorPayload;
    } catch {
      // Response has no JSON body — keep the generic message.
    }
    const message =
      payload?.error ?? payload?.detail ?? `Backend antwortet mit HTTP ${res.status}`;
    throw new ApiError(res.status, message, payload?.reply_de);
  }

  return (await res.json()) as T;
}

export function postChat(message: string): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
}

export function getTickets(limit = 50): Promise<Ticket[]> {
  return request<Ticket[]>(`/api/tickets?limit=${limit}`);
}

export function getEvents(limit = 20): Promise<WorkflowEvent[]> {
  return request<WorkflowEvent[]>(`/api/events?limit=${limit}`);
}

export function getHealth(): Promise<{ status?: string }> {
  return request<{ status?: string }>("/health");
}

export function resetDemo(): Promise<{ status: string; demo_store: string }> {
  return request<{ status: string; demo_store: string }>("/api/demo/reset", {
    method: "POST",
  });
}
