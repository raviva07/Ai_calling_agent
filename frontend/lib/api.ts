export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
export const WS_BASE = API_BASE.replace(/^http/, "ws");

export type Customer = {
  id: string;
  name: string;
  phone_number: string;
  company_name?: string | null;
  purpose?: string | null;
  product?: string | null;
  created_at: string;
};

export type Turn = { id: string; speaker: string; message: string; created_at: string };

export type CallRecord = {
  id: string;
  customer_id: string;
  customer_name: string;
  phone_number: string;
  status: string;
  outcome?: string | null;
  lead_status?: string | null;
  follow_up_required: boolean;
  direction: string;
  started_at?: string | null;
  ended_at?: string | null;
  duration_seconds: number;
  provider_call_id?: string | null;
  agent_state: Record<string, unknown>;
  structured_summary?: Record<string, unknown> | null;
  summary_text?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  created_at: string;
  turns: Turn[];
};

export type TelephonyConfig = {
  browser_demo_ready: boolean;
  real_call_provider: string;
  real_call_ready: boolean;
  reasons: string[];
  public_backend_url: string;
  twilio_from_number_configured: boolean;
  twilio_voice_mode?: string;
  twilio_account_tier?: string;
  twilio_signature_validation?: boolean;
};

export type DashboardStats = {
  total_calls: number;
  active_calls: number;
  completed_calls: number;
  failed_calls: number;
  interested_leads: number;
  follow_ups_required: number;
  average_call_duration_seconds: number;
};

export const LIVE_CALL_STATUSES = new Set(["created", "queued", "initiated", "ringing", "in_progress"]);
export const TERMINAL_CALL_STATUSES = new Set(["completed", "failed", "no_answer", "no_response", "disconnected", "canceled", "busy"]);

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed (${response.status})`);
  }
  return response.json();
}

export const api = {
  customers: () => request<Customer[]>("/api/customers"),
  createCustomer: (payload: Omit<Customer, "id" | "created_at">) => request<Customer>("/api/customers", { method: "POST", body: JSON.stringify(payload) }),
  startCall: (customerId: string, mode: "browser" | "twilio" = "browser") => request<CallRecord>("/api/calls/start", { method: "POST", body: JSON.stringify({ customer_id: customerId, mode }) }),
  telephonyConfig: () => request<TelephonyConfig>("/api/telephony/config"),
  calls: (query = "") => request<CallRecord[]>(`/api/calls${query ? `?${query}` : ""}`),
  call: (id: string) => request<CallRecord>(`/api/calls/${id}`),
  endCall: (id: string, reason = "completed") => request<CallRecord>(`/api/calls/${id}/end`, { method: "POST", body: JSON.stringify({ reason }) }),
  stats: () => request<DashboardStats>("/api/dashboard"),
  event: (id: string, event_type: string, details: Record<string, unknown> = {}) => request(`/api/calls/${id}/events`, { method: "POST", body: JSON.stringify({ event_type, details }) }),
};

export function humanizeStatus(value: string | null | undefined) {
  if (!value) return "Unknown";
  return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function isCallLive(call: Pick<CallRecord, "status" | "ended_at">) {
  return !call.ended_at && LIVE_CALL_STATUSES.has(call.status);
}

export function callLifecycleLabel(call: Pick<CallRecord, "status" | "ended_at">) {
  if (call.ended_at || TERMINAL_CALL_STATUSES.has(call.status)) {
    return `Ended · ${humanizeStatus(call.status)}`;
  }
  return humanizeStatus(call.status);
}

export function statusTone(status: string | null | undefined) {
  const value = (status || "").toLowerCase();
  if (["failed", "no_answer", "no_response", "disconnected", "canceled", "busy"].includes(value)) return "red";
  if (value === "completed") return "green";
  if (LIVE_CALL_STATUSES.has(value)) return "blue";
  return "amber";
}

export function formatDuration(seconds: number) {
  const safe = Math.max(0, Number(seconds) || 0);
  const m = Math.floor(safe / 60).toString().padStart(2, "0");
  const s = Math.floor(safe % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}
