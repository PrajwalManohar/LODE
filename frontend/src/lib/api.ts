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
}

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
  const res = await fetch(`${API}${url}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
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
};
