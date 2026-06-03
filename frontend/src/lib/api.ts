import { supabase } from "./supabase";

const API = "/api";

export interface Citation {
  source: string;
  section: string;
  page: string;
  excerpt: string;
}

export interface ExperimentContext {
  material_type: string;
  analysis_goal: string;
  sample_dimensions: string;
  surface_condition: string;
  coating_status: string;
  urgency: string;
  deadline?: string;
  researcher_name: string;
  researcher_email: string;
  research_group: string;
  trained_instruments: string[];
  notes: string;
  is_complete: boolean;
  hazardous_materials?: string[];
  hazmat_review_required?: boolean;
}

export interface SafetyGateResult {
  passed: boolean;
  reasons: string[];
  requires_review: boolean;
}

export interface InstrumentFit {
  instrument_id: string;
  instrument_name: string;
  fit_score: number;
  grade: string;
  rationale: string;
  citations: Citation[];
  requires_training: boolean;
  prep_time_minutes: number;
  run_duration_minutes: number;
}

export interface BookingOption {
  instrument_id: string;
  instrument_name: string;
  start_time: string;
  end_time: string;
  prep_start: string;
  rank: number;
  score: number;
  notes: string;
}

export interface ChatResponse {
  message: string;
  context?: ExperimentContext;
  recommendations: InstrumentFit[];
  booking_options: BookingOption[];
  citations: Citation[];
  needs_clarification: boolean;
  escalated: boolean;
  sop_path?: string;
  safety_gate?: SafetyGateResult;
  session_id?: string;
  automations?: {
    airtable_booking?: { id: string; destination: string; table: string };
    email?: { sent: boolean; transport: string; id: string; to: string[] };
    work_order?: Record<string, unknown> | null;
  };
}

export interface AgentDecision {
  id: number;
  session_id: string;
  agent: string;
  input_summary: string;
  output_summary: string;
  reasoning: string;
  confidence: number;
  rag_chunks_json: string;
  citations_json: string;
  outcome: string;
  created_at: string;
}

export interface EquityRow {
  group: string;
  hours: number;
  pct: number;
}

export interface WorkOrderNote {
  author: string;
  text: string;
  at: string;
}

export interface WorkOrder {
  id: number;
  instrument_id: string;
  instrument_name?: string;
  issue: string;
  severity: string;
  usage_hours: number;
  calibration_interval_hours: number;
  recommended_action: string;
  status: string;
  created_at: string;
  source: string;
  assigned_team?: string | null;
  notes?: string; // jsonb array, serialized as a JSON string by the data layer
}

export const WO_TEAMS = ["Lab Tech", "Facilities", "Vendor Service", "EH&S"] as const;

export interface AutomationEvent {
  id: number;
  kind: string; // email | booking_sync | work_order
  status: string; // sent | queued | failed | created
  target: string;
  detail: string;
  payload: string;
  error: string | null;
  created_at: string;
}

export interface Instrument {
  id: string;
  name: string;
  type: string;
  manufacturer: string;
  model: string;
  location: string;
  warmup_minutes: number;
  status: string;
  required_training: string;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  // Attach the Supabase JWT to every API call so the backend can authorize
  // /api/me/* (and admin endpoints in production). The data layer expects
  // a Bearer token via Authorization header — see backend/auth.py.
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const authHeaders: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {};
  const res = await fetch(`${API}${url}`, {
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...init?.headers,
    },
    ...init,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface CampusFeed {
  digest: string;
  announcements: { title: string; body: string; tag: string; date?: string; url: string }[];
  circulars: { title: string; body: string; tag: string; url: string }[];
  facts: string[];
  research_themes: { theme: string; detail: string }[];
  source: string;
}

export interface PlatformStatus {
  version: string;
  demo_mode: boolean;
  llm_configured: boolean;
  instruments_count: number;
  rag_chunks: number;
  rag_last_update: string | null;
  fit_threshold: number;
}

export const api = {
  health: () => fetchJson<{ status: string }>("/health"),
  status: () => fetchJson<PlatformStatus>("/status"),
  notifications: () => fetchJson<CampusFeed>("/notifications"),
  intake: (
    message: string,
    history: { role: string; content: string }[],
    context?: ExperimentContext,
    session_id?: string
  ) =>
    fetchJson<ChatResponse>("/chat/intake", {
      method: "POST",
      body: JSON.stringify({ message, history, context, session_id }),
    }),
  intakeForm: (context: ExperimentContext, session_id?: string) =>
    fetchJson<ChatResponse>("/chat/intake/form", {
      method: "POST",
      body: JSON.stringify({ context, session_id }),
    }),
  confirm: (
    context: ExperimentContext,
    option: BookingOption,
    recommendation: InstrumentFit,
    session_id?: string
  ) =>
    fetchJson<ChatResponse>("/chat/confirm", {
      method: "POST",
      body: JSON.stringify({ context, option, recommendation, session_id }),
    }),
  instruments: () => fetchJson<Instrument[]>("/instruments"),
  bookings: () => fetchJson<Record<string, unknown>[]>("/bookings"),
  // Only the signed-in researcher's own bookings (privacy-scoped for non-admins).
  myBookings: (email: string) =>
    fetchJson<Record<string, unknown>[]>(`/bookings?email=${encodeURIComponent(email)}`),
  // Today's bookings at the labs where this user has a booking (lab-mate awareness).
  labDay: (email: string) =>
    fetchJson<Record<string, unknown>[]>(`/bookings/lab-day?email=${encodeURIComponent(email)}`),
  utilization: () =>
    fetchJson<{ instrument: string; week: string; hours: number; instrument_id: string }[]>(
      "/bookings/utilization"
    ),
  rag: () =>
    fetchJson<{
      documents: { corpus_type: string; document_name: string; chunk_count: number; indexed_at: string }[];
      total_chunks: number;
      last_update: string | null;
    }>("/admin/rag"),
  reindex: () => fetchJson<{ indexed: number; total: number }>("/admin/rag/reindex", { method: "POST" }),
  ragInventory: () =>
    fetchJson<{
      total_chunks: number;
      embedding_model: string;
      vector_dims: number | null;
      by_type: { corpus_type: string; chunks: number }[];
      by_source: { source: string; corpus_type: string; instrument_id: string | null; chunks: number }[];
    }>("/admin/rag/inventory"),
  ragSearch: (q: string, opts?: { k?: number; instrument?: string; corpus?: string }) => {
    const p = new URLSearchParams({ q });
    if (opts?.k) p.set("k", String(opts.k));
    if (opts?.instrument) p.set("instrument", opts.instrument);
    if (opts?.corpus) p.set("corpus", opts.corpus);
    return fetchJson<{
      query: string;
      results: {
        similarity: number; source: string; section: string; page: string;
        corpus_type: string; instrument_id: string; text: string;
      }[];
    }>(`/admin/rag/search?${p.toString()}`);
  },
  runs: () => fetchJson<Record<string, unknown>[]>("/admin/runs"),
  audit: (limit = 50) => fetchJson<AgentDecision[]>(`/admin/audit?limit=${limit}`),
  equity: (weeks = 4) =>
    fetchJson<{ window_weeks: number; groups: EquityRow[]; flagged: EquityRow[] }>(
      `/admin/equity?weeks=${weeks}`
    ),
  workOrders: () => fetchJson<WorkOrder[]>("/admin/work-orders"),
  setWorkOrderStatus: (id: number, status: string) =>
    fetchJson<WorkOrder>(`/admin/work-orders/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),
  assignWorkOrder: (id: number, team: string) =>
    fetchJson<WorkOrder>(`/admin/work-orders/${id}/assign`, {
      method: "POST",
      body: JSON.stringify({ team }),
    }),
  addWorkOrderNote: (id: number, text: string, author?: string) =>
    fetchJson<WorkOrder>(`/admin/work-orders/${id}/note`, {
      method: "POST",
      body: JSON.stringify({ text, author }),
    }),
  automations: (kind?: string) =>
    fetchJson<AutomationEvent[]>(`/admin/automations${kind ? `?kind=${kind}` : ""}`),
  hitlList: (status?: string) =>
    fetchJson<AutomationEvent[]>(`/admin/hitl${status ? `?status=${status}` : ""}`),
  hitlApprove: (eventId: number, note?: string) =>
    fetchJson<{ ok: boolean; event: AutomationEvent }>(`/admin/hitl/${eventId}/approve`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  hitlDeny: (eventId: number, note?: string) =>
    fetchJson<{ ok: boolean; event: AutomationEvent }>(`/admin/hitl/${eventId}/deny`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  sendMonthlyReport: (to?: string) =>
    fetchJson<{ ok: boolean; period: string; result: { sent: boolean; transport: string } }>(
      `/admin/reports/monthly/send${to ? `?to=${encodeURIComponent(to)}` : ""}`,
      { method: "POST" },
    ),
  airtableQueue: (table = "LODE_Bookings") =>
    fetchJson<{ id: string; table: string; fields: Record<string, unknown>; created_at: string }[]>(
      `/admin/automations/airtable?table=${encodeURIComponent(table)}`
    ),
  emailOutbox: () =>
    fetchJson<{ id: string; to: string[]; subject: string; transport: string; delivered: boolean; created_at: string; attachment: string }[]>(
      "/admin/automations/email"
    ),
  postRun: (report: Record<string, unknown>) =>
    fetchJson<{ message: string; maintenance_alert: boolean }>("/postrun", {
      method: "POST",
      body: JSON.stringify(report),
    }),
  sopUrl: (path: string) => {
    const name = path.split(/[/\\]/).pop();
    return `${API}/files/sops/${name}`;
  },
  ragChunks: (q: { source?: string; section?: string; page?: string; instrument_id?: string }) => {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(q)) if (v) params.set(k, v);
    return fetchJson<{ id: string; content: string; source: string; section: string; page: string; corpus_type: string; instrument_id: string }[]>(
      `/admin/rag/chunks?${params.toString()}`,
    );
  },
  myRequests: (email: string) =>
    fetchJson<{ hitl: AutomationEvent[]; maintenance: WorkOrder[] }>(
      `/me/requests?email=${encodeURIComponent(email)}`,
    ),
  requestSlots: (eventId: number) =>
    fetchJson<{ options: BookingOption[] }>(`/me/requests/${eventId}/slots`),
  completeHitl: (eventId: number, option?: BookingOption) =>
    fetchJson<{ ok: boolean; booking_id?: number; sop_path?: string; message: string; event_id: number }>(
      `/me/requests/${eventId}/complete`,
      { method: "POST", body: JSON.stringify(option ? { option } : {}) },
    ),
  dismissRequest: (eventId: number, email: string) =>
    fetchJson<{ ok: boolean; event_id: number; status: string; message: string }>(
      `/me/requests/${eventId}/dismiss?email=${encodeURIComponent(email)}`,
      { method: "POST" },
    ),
  dismissedIds: (email: string) =>
    fetchJson<{ event_ids: number[] }>(
      `/me/requests/dismissed?email=${encodeURIComponent(email)}`,
    ),
  dismissWorkOrder: (id: number, email: string) =>
    fetchJson<{ ok: boolean; work_order_id: number; message: string }>(
      `/me/work-orders/${id}/dismiss?email=${encodeURIComponent(email)}`,
      { method: "POST" },
    ),
  dismissedWorkOrderIds: (email: string) =>
    fetchJson<{ work_order_ids: number[] }>(
      `/me/work-orders/dismissed?email=${encodeURIComponent(email)}`,
    ),
  requestBookingEdit: (bookingId: number, email: string, newStart: string, reason?: string) =>
    fetchJson<{ ok: boolean; event_id: number; message: string }>(
      `/me/bookings/${bookingId}/request-edit?email=${encodeURIComponent(email)}`,
      {
        method: "POST",
        body: JSON.stringify({ new_start_time: newStart, reason }),
      },
    ),
  requestBookingCancel: (bookingId: number, email: string, reason?: string) =>
    fetchJson<{ ok: boolean; event_id: number; message: string }>(
      `/me/bookings/${bookingId}/request-cancel?email=${encodeURIComponent(email)}`,
      {
        method: "POST",
        body: JSON.stringify({ reason }),
      },
    ),

  // ---- Privacy & Compliance (GDPR Art. 15 / 17 / 20, FERPA §99.10) ----
  exportMyData: (email: string) =>
    fetchJson<MeExport>(`/me/export?email=${encodeURIComponent(email)}`),
  deleteMyAccount: (email: string) =>
    fetchJson<{ ok: boolean; deleted_profile: boolean; deleted_bookings: number; deleted_auth_user: boolean; message: string }>(
      `/me/delete?email=${encodeURIComponent(email)}`,
      { method: "POST" },
    ),
  myAuditTrail: (email: string, limit = 50) =>
    fetchJson<{ rows: AuditRow[] }>(
      `/me/audit?email=${encodeURIComponent(email)}&limit=${limit}`,
    ),
  safetyPreview: (text: string, context?: Record<string, unknown>) =>
    fetchJson<SafetyPreview>("/me/safety-preview", {
      method: "POST",
      body: JSON.stringify({ text, context }),
    }),
};

export interface AuditRow {
  ts: string;
  event: string;
  actor: string | null;
  subject: string | null;
  detail: Record<string, unknown>;
}

export interface MeExport {
  exported_at: string;
  profile: Record<string, unknown>;
  bookings: Record<string, unknown>[];
  hitl_requests: AutomationEvent[];
  notice: string;
}

export interface SafetyPreview {
  input_chars: number;
  max_chars: number;
  guardrail_allowed: boolean;
  guardrail_reasons: string[];
  pii_redacted_preview: string;
  hazardous_keywords_detected: string[];
  safety_gate_would_escalate: boolean;
  confidence_floor_pct: number;
  controls: Record<string, unknown>;
  context_before?: Record<string, unknown> | null;
  context_after_redaction?: Record<string, unknown> | null;
  context_field_diff: { field: string; original: string; redacted: string; masked: boolean }[];
  llm_prompt_preview: string;
}
