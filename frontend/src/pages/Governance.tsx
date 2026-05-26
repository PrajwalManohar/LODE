import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  CheckCircle2,
  ChevronDown,
  Filter,
  Mail,
  MessageSquarePlus,
  Search,
  ShieldAlert,
  Sparkles,
  Users,
  X,
  XCircle,
} from "lucide-react";
import clsx from "clsx";
import { PageBody, PageHeader } from "../components/PageShell";
import { api, AutomationEvent, EquityRow, WorkOrder, WorkOrderNote, WO_TEAMS } from "../lib/api";
import { useAuth } from "../lib/auth";

type Toast = { kind: "ok" | "err"; text: string } | null;

export default function Governance() {
  const qc = useQueryClient();
  const { isAdmin } = useAuth();
  const [params, setParams] = useSearchParams();
  const [toast, setToast] = useState<Toast>(null);

  // ---------------- Data ----------------
  const { data: equity }       = useQuery({ queryKey: ["equity"], queryFn: () => api.equity(8) });
  const { data: workOrders = [] } = useQuery({ queryKey: ["work-orders"], queryFn: api.workOrders });
  const { data: bookings = [] }   = useQuery({ queryKey: ["bookings"], queryFn: api.bookings });
  const { data: instruments = [] }= useQuery({ queryKey: ["instruments"], queryFn: api.instruments });
  const { data: util = [] }       = useQuery({ queryKey: ["utilization"], queryFn: api.utilization });
  const { data: rag }             = useQuery({ queryKey: ["rag"], queryFn: api.rag });
  const { data: automations = [] } = useQuery({ queryKey: ["automations"], queryFn: () => api.automations() });
  const { data: hitlReqs = [] }   = useQuery({ queryKey: ["hitl"], queryFn: () => api.hitlList() });
  const { data: audit = [] }      = useQuery({ queryKey: ["audit"], queryFn: () => api.audit(40) });

  // ---------------- Mutations ----------------
  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => api.setWorkOrderStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["work-orders"] }),
  });
  const assignMutation = useMutation({
    mutationFn: ({ id, team }: { id: number; team: string }) => api.assignWorkOrder(id, team),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["work-orders"] });
      qc.invalidateQueries({ queryKey: ["automations"] });
      setToast({ kind: "ok", text: "Work order assigned." });
    },
    onError: (e: Error) => setToast({ kind: "err", text: e.message || "Assign failed." }),
  });
  const noteMutation = useMutation({
    mutationFn: ({ id, text }: { id: number; text: string }) => api.addWorkOrderNote(id, text),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["work-orders"] }),
    onError: (e: Error) => setToast({ kind: "err", text: e.message || "Could not add note." }),
  });

  const approveMutation = useMutation({
    mutationFn: (id: number) => api.hitlApprove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hitl"] });
      qc.invalidateQueries({ queryKey: ["automations"] });
      setToast({ kind: "ok", text: "HITL request approved." });
    },
    onError: (e: Error) => setToast({ kind: "err", text: e.message || "Approve failed." }),
  });
  const denyMutation = useMutation({
    mutationFn: (id: number) => api.hitlDeny(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hitl"] });
      qc.invalidateQueries({ queryKey: ["automations"] });
      setToast({ kind: "ok", text: "HITL request denied." });
    },
    onError: (e: Error) => setToast({ kind: "err", text: e.message || "Deny failed." }),
  });
  const monthlyMutation = useMutation({
    mutationFn: () => api.sendMonthlyReport(),
    onSuccess: (r) =>
      setToast({
        kind: "ok",
        text: `Monthly report sent for ${r.period} (transport: ${r.result.transport}).`,
      }),
    onError: (e: Error) => setToast({ kind: "err", text: e.message || "Monthly send failed." }),
  });

  // ---------------- URL-driven HITL action (from the email button) ----------------
  useEffect(() => {
    const eid = params.get("hitl");
    const action = params.get("action");
    if (!eid || !action) return;
    const id = Number(eid);
    if (Number.isNaN(id)) return;
    if (action === "approve") approveMutation.mutate(id);
    else if (action === "deny") denyMutation.mutate(id);
    // Strip the params so reloading doesn't re-fire.
    const next = new URLSearchParams(params);
    next.delete("hitl");
    next.delete("action");
    setParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-dismiss toast after 4s.
  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(id);
  }, [toast]);

  // ---------------- KPIs ----------------
  const totalBookings = bookings.length;
  const sopsGenerated = bookings.filter((b) => b.sop_path).length;
  const pendingHitl = hitlReqs.filter((h) => h.status === "pending");
  const emails = automations.filter((a) => a.kind === "email");
  const emailSuccess =
    emails.length === 0 ? 100 : Math.round((emails.filter((e) => e.status === "sent").length / emails.length) * 100);
  const avgFit = avgFitScore(audit);
  const escalations = audit.filter((d) => d.outcome === "escalate").length;

  const perInstrument = instruments.map((inst) => {
    const hrs = util.filter((u) => u.instrument_id === inst.id).reduce((s, u) => s + u.hours, 0);
    return { id: inst.id, name: shortName(inst.name), hours: hrs, pct: Math.min(100, Math.round((hrs / 160) * 100)) };
  });

  return (
    <>
      <PageHeader
        title="Analytics & governance"
        subtitle="Live operational telemetry — bookings, automations, equity, and the HITL queue."
        actions={
          <>
            <button
              onClick={() => monthlyMutation.mutate()}
              disabled={monthlyMutation.isPending}
              className="btn"
              title="Send the green monthly-utilization email now"
            >
              <Mail className="w-4 h-4" /> Send monthly report
            </button>
          </>
        }
      />

      <PageBody>
        {toast && (
          <div
            className={clsx(
              "rounded-lg border px-4 py-2.5 text-sm font-medium flex items-center gap-2",
              toast.kind === "ok"
                ? "bg-ok-50 border-ok-200 text-ok-700"
                : "bg-danger-50 border-danger-200 text-danger-700"
            )}
          >
            {toast.kind === "ok" ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
            {toast.text}
            <button onClick={() => setToast(null)} className="ml-auto text-current/60 hover:text-current">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* KPI row — 5-up */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <KpiTile label="Total bookings" value={totalBookings} sub="all-time" />
          <KpiTile label="Avg fit score"  value={avgFit} suffix="/100" sub="agent confidence" />
          <KpiTile label="SOPs generated" value={sopsGenerated} sub="with citations" />
          <KpiTile
            label="HITL pending"
            value={pendingHitl.length}
            sub={`${escalations} total escalations`}
            tone={pendingHitl.length > 0 ? "warn" : "ok"}
          />
          <KpiTile
            label="Email delivery"
            value={`${emailSuccess}%`}
            sub={`${emails.length} dispatches`}
            tone={emailSuccess >= 95 ? "ok" : emailSuccess >= 80 ? "warn" : "danger"}
          />
        </div>

        {/* HITL — top-priority operator surface */}
        <HitlSection
          requests={hitlReqs}
          onApprove={(id) => approveMutation.mutate(id)}
          onDeny={(id) => denyMutation.mutate(id)}
          pending={approveMutation.isPending || denyMutation.isPending}
        />

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Instrument utilization */}
          <section className="card overflow-hidden">
            <div className="card-header">
              <h2 className="font-display text-[15px] font-semibold">Instrument utilization</h2>
              <span className="text-xs text-ink-500">Hours used / 160 hr target</span>
            </div>
            <ul className="divide-y divide-ink-200">
              {perInstrument.map((p) => (
                <li key={p.id} className="px-5 py-3 flex items-center gap-4">
                  <p className="flex-1 text-sm text-ink-900 truncate">{p.name}</p>
                  <p className="text-xs text-ink-500 w-12 text-right font-mono tabular-nums">{p.hours.toFixed(0)}h</p>
                  <div className="w-40 h-1.5 rounded-full bg-ink-100 overflow-hidden">
                    <div
                      className={clsx(
                        "h-full rounded-full",
                        p.pct >= 80 ? "bg-warn-600" : p.pct >= 50 ? "bg-navy-700" : "bg-ok-600"
                      )}
                      style={{ width: `${p.pct}%` }}
                    />
                  </div>
                  <p className="text-sm font-semibold w-12 text-right tabular-nums">{p.pct}%</p>
                </li>
              ))}
            </ul>
          </section>

          {/* Booking equity */}
          <section className="card overflow-hidden">
            <div className="card-header">
              <h2 className="font-display text-[15px] font-semibold">Booking equity by group</h2>
              {equity?.flagged?.length ? (
                <span className="pill-warn">{equity.flagged.length} flagged</span>
              ) : (
                <span className="pill-ok">balanced</span>
              )}
            </div>
            <div className="px-5 py-4 space-y-3">
              {(equity?.groups ?? []).map((g) => (
                <EquityBar key={g.group} g={g} />
              ))}
              {(equity?.groups?.length ?? 0) === 0 && (
                <p className="text-sm text-ink-500">No booking activity in the 8-week window.</p>
              )}
            </div>
          </section>
        </div>

        {/* Maintenance — full-width with filters & rich details */}
        <MaintenanceSection
          workOrders={workOrders}
          instruments={instruments}
          isAdmin={isAdmin}
          pending={statusMutation.isPending}
          assigning={assignMutation.isPending}
          noting={noteMutation.isPending}
          onStatus={(id, status) => statusMutation.mutate({ id, status })}
          onAssign={(id, team) => assignMutation.mutate({ id, team })}
          onNote={(id, text) => noteMutation.mutate({ id, text })}
        />

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Automation activity */}
          <section className="card overflow-hidden lg:col-span-2">
            <div className="card-header">
              <h2 className="font-display text-[15px] font-semibold">Automation activity</h2>
              <span className="pill-ok">Realtime</span>
            </div>
            <ul className="divide-y divide-ink-200 max-h-[420px] overflow-y-auto">
              {automations.slice(0, 30).map((a) => (
                <AutomationRow key={a.id} a={a} />
              ))}
              {automations.length === 0 && (
                <li className="px-5 py-12 text-center text-sm text-ink-500">
                  No automations yet — confirm a booking to fire the email + ticket sync.
                </li>
              )}
            </ul>
          </section>

          {/* RAG + agent stats */}
          <section className="card overflow-hidden">
            <div className="card-header">
              <h2 className="font-display text-[15px] font-semibold">Knowledge base</h2>
              <span className="pill-ok">Indexed</span>
            </div>
            <div className="grid grid-cols-2 gap-3 px-5 py-5">
              <Stat label="Total chunks" value={rag?.total_chunks ?? 0} />
              <Stat label="Indexed docs" value={rag?.documents?.length ?? 0} />
              <Stat label="Avg retrieval" value="38 ms" />
              <Stat label="Escalations" value={escalations} tone={escalations > 0 ? "warn" : "ok"} />
            </div>
            <div className="px-5 py-3 border-t border-ink-100">
              <p className="text-[11px] tracking-wider text-ink-500 uppercase font-semibold mb-2">
                Email transport mix
              </p>
              <TransportBar emails={emails} />
            </div>
          </section>
        </div>
      </PageBody>
    </>
  );
}

// ============================================================================
// HITL section
// ============================================================================
function HitlSection({
  requests,
  onApprove,
  onDeny,
  pending,
}: {
  requests: AutomationEvent[];
  onApprove: (id: number) => void;
  onDeny: (id: number) => void;
  pending: boolean;
}) {
  const [status, setStatus] = useState<"pending" | "approved" | "denied" | "all">("pending");
  const filtered = useMemo(
    () => (status === "all" ? requests : requests.filter((r) => r.status === status)),
    [requests, status]
  );
  const counts = useMemo(() => {
    return {
      pending: requests.filter((r) => r.status === "pending").length,
      approved: requests.filter((r) => r.status === "approved").length,
      denied: requests.filter((r) => r.status === "denied").length,
    };
  }, [requests]);

  return (
    <section className="card overflow-hidden">
      <div className="card-header">
        <div className="flex items-center gap-2.5">
          <ShieldAlert className="w-4 h-4 text-warn-700" />
          <h2 className="font-display text-[15px] font-semibold">Human-in-the-loop queue</h2>
          {counts.pending > 0 && <span className="pill-warn">{counts.pending} awaiting review</span>}
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          {(["pending", "approved", "denied", "all"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={clsx(
                "px-2.5 py-1 rounded-full border transition capitalize",
                status === s
                  ? "bg-navy-800 text-white border-navy-800"
                  : "bg-white text-ink-600 border-ink-200 hover:border-ink-300"
              )}
            >
              {s} {s !== "all" && `(${counts[s]})`}
            </button>
          ))}
        </div>
      </div>
      {filtered.length === 0 ? (
        <div className="px-5 py-12 text-center text-sm text-ink-500">
          {status === "pending"
            ? "No pending requests — all bookings auto-approved."
            : `No ${status} requests.`}
        </div>
      ) : (
        <ul className="divide-y divide-ink-200">
          {filtered.map((r) => (
            <HitlRow
              key={r.id}
              r={r}
              onApprove={() => onApprove(r.id)}
              onDeny={() => onDeny(r.id)}
              pending={pending}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function HitlRow({
  r,
  onApprove,
  onDeny,
  pending,
}: {
  r: AutomationEvent;
  onApprove: () => void;
  onDeny: () => void;
  pending: boolean;
}) {
  const [open, setOpen] = useState(false);
  const payload = parsePayload(r.payload);
  const reasons: string[] = Array.isArray(payload.reasons)
    ? (payload.reasons as string[]).filter((x) => typeof x === "string")
    : [];
  const isPending = r.status === "pending";
  const statusPill =
    r.status === "approved"
      ? "pill-ok"
      : r.status === "denied"
      ? "pill-danger"
      : "pill-warn";
  const s = (k: string, fallback = "—"): string => {
    const v = payload[k];
    return typeof v === "string" && v ? v : fallback;
  };
  const n = (k: string): string => {
    const v = payload[k];
    return typeof v === "number" ? String(v) : typeof v === "string" && v ? v : "—";
  };
  const ctx = (payload.context && typeof payload.context === "object"
    ? payload.context : {}) as Record<string, unknown>;
  const cs = (k: string): string => {
    const v = ctx[k];
    return typeof v === "string" && v ? v : "—";
  };
  return (
    <li className="px-5 py-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="min-w-0 flex-1 text-left flex items-start gap-2"
        >
          <ChevronDown
            className={clsx("w-4 h-4 text-ink-400 mt-0.5 shrink-0 transition-transform", open && "rotate-180")}
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="text-sm font-semibold text-ink-900 tracking-tight">
                {s("booking_code", `HITL-${r.id}`)}
              </p>
              <span className={statusPill}>{r.status}</span>
              <span className="pill-muted">{s("alert_title", r.detail || "—")}</span>
            </div>
            <p className="text-xs text-ink-500 mt-1 leading-snug">
              <span className="text-ink-700 font-medium">{s("researcher_name")}</span>{" "}
              ({s("researcher_email")}) ·{" "}
              <span className="text-ink-700">{s("instrument_name")}</span> · {s("when", "Not scheduled")}
            </p>
            <p className="text-xs text-ink-500 mt-0.5">
              Experiment: <span className="text-ink-700">{s("experiment")}</span>
            </p>
            {reasons.length > 0 && (
              <ul className="mt-2 ml-1 space-y-0.5">
                {reasons.map((reason: string, i: number) => (
                  <li key={i} className="text-xs text-ink-600 flex items-start gap-1.5">
                    <span className="text-warn-700 mt-0.5">•</span>
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </button>
        {isPending && (
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              onClick={onApprove}
              disabled={pending}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold bg-ok-600 text-white hover:bg-ok-700 disabled:opacity-50 transition"
            >
              <Check className="w-3.5 h-3.5" /> Approve
            </button>
            <button
              onClick={onDeny}
              disabled={pending}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold bg-danger-600 text-white hover:bg-danger-700 disabled:opacity-50 transition"
            >
              <X className="w-3.5 h-3.5" /> Deny
            </button>
          </div>
        )}
      </div>

      {/* Drill-down: the full request the operator is signing off on */}
      {open && (
        <div className="mt-3 ml-6 grid sm:grid-cols-3 gap-3">
          <Detail label="Fit score" value={`${n("fit_score")} / 100`} />
          <Detail label="Grade" value={s("grade")} />
          <Detail label="Confidence" value={`${n("confidence")}%`} />
          <Detail label="Research group" value={s("research_group")} />
          <Detail label="Training status" value={s("training_status")} />
          <Detail label="Session" value={s("session_id", r.target || "—")} />
          <Detail label="Material" value={cs("material_type")} />
          <Detail label="Analysis goal" value={cs("analysis_goal")} />
          <Detail label="Deadline" value={cs("deadline")} />
        </div>
      )}
    </li>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-ink-200 bg-white px-3 py-2">
      <p className="text-[10px] font-semibold tracking-wider text-ink-500 uppercase">{label}</p>
      <p className="text-xs text-ink-900 mt-0.5 break-words">{value}</p>
    </div>
  );
}

// ============================================================================
// Maintenance section — full filters
// ============================================================================
function MaintenanceSection({
  workOrders,
  instruments,
  isAdmin,
  pending,
  assigning,
  noting,
  onStatus,
  onAssign,
  onNote,
}: {
  workOrders: WorkOrder[];
  instruments: { id: string; name: string }[];
  isAdmin: boolean;
  pending: boolean;
  assigning: boolean;
  noting: boolean;
  onStatus: (id: number, status: string) => void;
  onAssign: (id: number, team: string) => void;
  onNote: (id: number, text: string) => void;
}) {
  const [severity, setSeverity] = useState<"all" | "critical" | "warning">("all");
  const [status, setStatus]     = useState<"all" | "open" | "in_progress" | "closed">("open");
  const [instrument, setInstrument] = useState<string>("all");
  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    return workOrders.filter((w) => {
      if (severity !== "all" && w.severity !== severity) return false;
      if (status !== "all" && w.status !== status) return false;
      if (instrument !== "all" && w.instrument_id !== instrument) return false;
      if (q && !`${w.issue} ${w.instrument_name ?? ""} ${w.source}`.toLowerCase().includes(q.toLowerCase()))
        return false;
      return true;
    });
  }, [workOrders, severity, status, instrument, q]);

  const counts = useMemo(() => {
    const all = workOrders.length;
    return {
      all,
      open: workOrders.filter((w) => w.status === "open").length,
      critical: workOrders.filter((w) => w.severity === "critical" && w.status !== "closed").length,
    };
  }, [workOrders]);

  return (
    <section className="card overflow-hidden">
      <div className="card-header">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2.5">
            <h2 className="font-display text-[15px] font-semibold">Maintenance work orders</h2>
            <span className="pill-warn">{counts.open} open</span>
            {counts.critical > 0 && <span className="pill-danger">{counts.critical} critical</span>}
            <span className="pill-muted">{counts.all} total</span>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2.5">
          <FilterSelect
            icon={<Filter className="w-3.5 h-3.5" />}
            label="Severity"
            value={severity}
            onChange={(v) => setSeverity(v as typeof severity)}
            options={[
              ["all", "All severities"],
              ["critical", "Critical"],
              ["warning", "Warning"],
            ]}
          />
          <FilterSelect
            icon={<Filter className="w-3.5 h-3.5" />}
            label="Status"
            value={status}
            onChange={(v) => setStatus(v as typeof status)}
            options={[
              ["all", "All statuses"],
              ["open", "Open"],
              ["in_progress", "In progress"],
              ["closed", "Closed"],
            ]}
          />
          <FilterSelect
            icon={<Filter className="w-3.5 h-3.5" />}
            label="Instrument"
            value={instrument}
            onChange={(v) => setInstrument(v)}
            options={[
              ["all", "All instruments"] as [string, string],
              ...instruments.map((i) => [i.id, shortName(i.name)] as [string, string]),
            ]}
          />
          <label className="block">
            <span className="block text-[10px] font-bold tracking-wider text-ink-500 uppercase mb-1">
              Search
            </span>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-ink-400" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="issue, source…"
                className="w-full bg-white border border-ink-200 rounded-md pl-7 pr-3 py-1.5 text-xs focus:outline-none focus:border-navy-500 focus:ring-2 focus:ring-navy-500/20 transition"
              />
            </div>
          </label>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="px-5 py-12 text-center text-sm text-ink-500">
          No work orders match these filters.
        </div>
      ) : (
        <ul className="divide-y divide-ink-200">
          {filtered.map((w) => (
            <WorkOrderRow
              key={w.id}
              w={w}
              isAdmin={isAdmin}
              pending={pending}
              assigning={assigning}
              noting={noting}
              onStatus={(s) => onStatus(w.id, s)}
              onAssign={(team) => onAssign(w.id, team)}
              onNote={(text) => onNote(w.id, text)}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function FilterSelect({
  icon,
  label,
  value,
  onChange,
  options,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <label className="block">
      <span className="block text-[10px] font-bold tracking-wider text-ink-500 uppercase mb-1">
        {label}
      </span>
      <div className="relative">
        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-400">{icon}</span>
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full appearance-none bg-white border border-ink-200 rounded-md pl-7 pr-7 py-1.5 text-xs text-ink-900 focus:outline-none focus:border-navy-500 focus:ring-2 focus:ring-navy-500/20 transition"
        >
          {options.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </div>
    </label>
  );
}

function parseNotes(raw?: string): WorkOrderNote[] {
  if (!raw) return [];
  try {
    const arr = typeof raw === "string" ? JSON.parse(raw) : raw;
    return Array.isArray(arr) ? (arr as WorkOrderNote[]) : [];
  } catch {
    return [];
  }
}

function WorkOrderRow({
  w,
  isAdmin,
  pending,
  assigning,
  noting,
  onStatus,
  onAssign,
  onNote,
}: {
  w: WorkOrder;
  isAdmin: boolean;
  pending: boolean;
  assigning: boolean;
  noting: boolean;
  onStatus: (status: string) => void;
  onAssign: (team: string) => void;
  onNote: (text: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [noteText, setNoteText] = useState("");
  const usagePct =
    w.calibration_interval_hours > 0
      ? Math.round((w.usage_hours / w.calibration_interval_hours) * 100)
      : 0;
  const notes = parseNotes(w.notes);

  return (
    <li className={clsx(w.status === "closed" && "opacity-60")}>
      {/* Clickable summary row — toggles the drill-down */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full text-left px-5 py-4 hover:bg-ink-50/60 transition flex items-start gap-3"
      >
        <ChevronDown
          className={clsx("w-4 h-4 text-ink-400 mt-0.5 shrink-0 transition-transform", open && "rotate-180")}
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-semibold text-ink-900 tracking-tight">
              WO-{String(w.id).padStart(3, "0")}
            </p>
            <span className="text-ink-400">·</span>
            <p className="text-sm text-ink-900 truncate">{w.instrument_name ?? w.instrument_id}</p>
            <SeverityPill severity={w.severity} />
            <StatusPill status={w.status} />
            {w.assigned_team ? (
              <span className="pill-info inline-flex items-center gap-1">
                <Users className="w-3 h-3" /> {w.assigned_team}
              </span>
            ) : (
              <span className="pill-muted text-[10px]">unassigned</span>
            )}
            {notes.length > 0 && (
              <span className="pill-muted text-[10px] inline-flex items-center gap-1">
                <MessageSquarePlus className="w-3 h-3" /> {notes.length}
              </span>
            )}
          </div>
          <p className="text-sm text-ink-700 mt-1.5 leading-snug line-clamp-1">{w.issue}</p>
        </div>
        <span className="text-[11px] text-ink-400 shrink-0 mt-0.5 hidden sm:block">
          {new Date(w.created_at).toLocaleDateString()}
        </span>
      </button>

      {/* Drill-down panel */}
      {open && (
        <div className="px-5 pb-5 pl-12 space-y-4">
          {w.recommended_action && (
            <p className="text-xs text-ink-600 leading-snug">
              <span className="font-semibold text-ink-600 uppercase tracking-wider text-[10px]">
                Recommendation:
              </span>{" "}
              {w.recommended_action}
            </p>
          )}
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-[11px] font-mono text-ink-500 tabular-nums">
              {w.usage_hours.toFixed(0)}h / {w.calibration_interval_hours}h cal · {usagePct}%
            </span>
            <div className="w-40 h-1.5 rounded-full bg-ink-100 overflow-hidden">
              <div
                className={clsx(
                  "h-full rounded-full",
                  usagePct >= 100 ? "bg-danger-600" : usagePct >= 75 ? "bg-warn-600" : "bg-navy-700"
                )}
                style={{ width: `${Math.min(100, usagePct)}%` }}
              />
            </div>
            <span className="pill-muted text-[10px]">source: {w.source}</span>
            <span className="text-[11px] text-ink-400">{new Date(w.created_at).toLocaleString()}</span>
          </div>

          {isAdmin && (
            <>
              {/* Actions: assign + status */}
              <div className="flex items-end gap-3 flex-wrap">
                <label className="block">
                  <span className="block text-[10px] font-bold tracking-wider text-ink-500 uppercase mb-1">
                    Assign to team
                  </span>
                  <select
                    value={w.assigned_team ?? ""}
                    onChange={(e) => e.target.value && onAssign(e.target.value)}
                    disabled={assigning || w.status === "closed"}
                    className="appearance-none bg-white border border-ink-200 rounded-md px-3 py-1.5 text-xs text-ink-900 focus:outline-none focus:border-navy-500 focus:ring-2 focus:ring-navy-500/20 transition disabled:opacity-50"
                  >
                    <option value="">— select team —</option>
                    {WO_TEAMS.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </label>
                {w.status !== "closed" && (
                  <div className="flex items-center gap-1.5">
                    {w.status === "open" && (
                      <button
                        onClick={() => onStatus("in_progress")}
                        disabled={pending}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-semibold bg-info-50 text-info-700 border border-info-200 hover:bg-info-100 transition disabled:opacity-50"
                      >
                        <Sparkles className="w-3 h-3" /> Start
                      </button>
                    )}
                    <button
                      onClick={() => onStatus("closed")}
                      disabled={pending}
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-semibold bg-ok-50 text-ok-700 border border-ok-200 hover:bg-ok-100 transition disabled:opacity-50"
                    >
                      <Check className="w-3 h-3" /> Resolve & close
                    </button>
                  </div>
                )}
              </div>

              {/* Review comments */}
              <div>
                <p className="text-[10px] font-bold tracking-wider text-ink-500 uppercase mb-2">
                  Review comments
                </p>
                {notes.length > 0 ? (
                  <ul className="space-y-2 mb-2">
                    {notes.map((n, i) => (
                      <li key={i} className="rounded-lg border border-ink-200 bg-ink-50 px-3 py-2">
                        <p className="text-xs text-ink-800 leading-snug">{n.text}</p>
                        <p className="text-[10px] text-ink-400 mt-1">
                          {n.author} · {n.at ? new Date(n.at).toLocaleString() : ""}
                        </p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-ink-400 mb-2">No comments yet.</p>
                )}
                <div className="flex items-center gap-2">
                  <input
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && noteText.trim()) {
                        onNote(noteText.trim());
                        setNoteText("");
                      }
                    }}
                    placeholder="Add a review comment…"
                    className="flex-1 bg-white border border-ink-200 rounded-md px-3 py-1.5 text-xs focus:outline-none focus:border-navy-500 focus:ring-2 focus:ring-navy-500/20 transition"
                  />
                  <button
                    onClick={() => {
                      if (noteText.trim()) {
                        onNote(noteText.trim());
                        setNoteText("");
                      }
                    }}
                    disabled={noting || !noteText.trim()}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-semibold bg-navy-800 text-white hover:bg-navy-900 transition disabled:opacity-50"
                  >
                    <MessageSquarePlus className="w-3 h-3" /> Add
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </li>
  );
}

// ============================================================================
// Bits
// ============================================================================
function KpiTile({
  label,
  value,
  suffix,
  sub,
  tone,
}: {
  label: string;
  value: number | string;
  suffix?: string;
  sub: React.ReactNode;
  tone?: "ok" | "warn" | "danger";
}) {
  const accent =
    tone === "danger" ? "text-danger-700" : tone === "warn" ? "text-warn-700" : tone === "ok" ? "text-ok-700" : "text-ink-900";
  return (
    <div className="card-pad">
      <p className="text-sm text-ink-500 font-medium">{label}</p>
      <p className={clsx("text-[28px] font-bold mt-1 leading-none tabular-nums tracking-tight", accent)}>
        {value}
        {suffix ? <span className="text-base font-medium text-ink-400">{suffix}</span> : null}
      </p>
      <p className="text-xs mt-2 text-ink-500">{sub}</p>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number | string; tone?: "ok" | "warn" }) {
  const accent = tone === "warn" ? "text-warn-700" : tone === "ok" ? "text-ok-700" : "text-ink-900";
  return (
    <div className="rounded-lg border border-ink-200 p-3 bg-ink-50">
      <p className="text-[11px] tracking-wider text-ink-500 uppercase font-semibold">{label}</p>
      <p className={clsx("text-xl font-bold mt-1 tabular-nums", accent)}>{value}</p>
    </div>
  );
}

function EquityBar({ g }: { g: EquityRow }) {
  const flagged = g.pct > 40;
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-ink-900 font-medium">{g.group}</span>
        <span className={clsx("tabular-nums font-mono text-xs", flagged ? "text-warn-700 font-semibold" : "text-ink-500")}>
          {g.pct}% · {g.hours.toFixed(1)}h
        </span>
      </div>
      <div className="mt-1 h-1.5 rounded-full bg-ink-100 overflow-hidden">
        <div
          className={clsx("h-full rounded-full", flagged ? "bg-warn-600" : "bg-navy-700")}
          style={{ width: `${Math.min(100, g.pct)}%` }}
        />
      </div>
    </div>
  );
}

function TransportBar({ emails }: { emails: AutomationEvent[] }) {
  const byTransport = useMemo(() => {
    const map = new Map<string, number>();
    for (const e of emails) {
      const raw = e.payload ? parsePayload(e.payload).transport : undefined;
      const t = typeof raw === "string" && raw ? raw : "unknown";
      map.set(t, (map.get(t) ?? 0) + 1);
    }
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [emails]);
  const total = emails.length;
  if (total === 0) return <p className="text-xs text-ink-500">No email dispatches yet.</p>;
  return (
    <div className="space-y-1.5">
      {byTransport.map(([t, n]) => {
        const pct = Math.round((n / total) * 100);
        return (
          <div key={t}>
            <div className="flex justify-between text-xs">
              <span className="text-ink-700">{t}</span>
              <span className="text-ink-500 tabular-nums">
                {n} · {pct}%
              </span>
            </div>
            <div className="h-1 rounded-full bg-ink-100 overflow-hidden mt-0.5">
              <div className="h-full bg-navy-700 rounded-full" style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

const automationKindLabel: Record<string, string> = {
  email: "Email",
  booking_sync: "Booking",
  work_order: "Work order",
  hitl_request: "HITL",
};

function AutomationRow({ a }: { a: AutomationEvent }) {
  const cls =
    a.status === "sent" || a.status === "approved"
      ? "pill-ok"
      : a.status === "failed" || a.status === "denied"
      ? "pill-danger"
      : "pill-info";
  return (
    <li className="px-5 py-3 flex items-center gap-4">
      <span className="pill-muted shrink-0">{automationKindLabel[a.kind] ?? a.kind}</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-ink-900 truncate">{a.detail || a.target}</p>
        <p className="text-[11px] text-ink-500 mt-0.5 font-mono truncate">
          {a.target || "—"} · {new Date(a.created_at).toLocaleString()}
        </p>
      </div>
      <span className={clsx(cls, "shrink-0")}>{a.status}</span>
    </li>
  );
}

function SeverityPill({ severity }: { severity: string }) {
  const s = severity.toLowerCase();
  if (s === "critical") return <span className="pill-danger">Critical</span>;
  if (s === "warning") return <span className="pill-warn">Warning</span>;
  return <span className="pill-muted">{severity}</span>;
}

function StatusPill({ status }: { status: string }) {
  const cls =
    status === "closed" ? "pill-ok" : status === "in_progress" ? "pill-info" : "pill-warn";
  return <span className={cls}>{status.replace("_", " ")}</span>;
}

function parsePayload(p: unknown): Record<string, unknown> {
  if (typeof p === "string") {
    try {
      return JSON.parse(p);
    } catch {
      return {};
    }
  }
  if (p && typeof p === "object") return p as Record<string, unknown>;
  return {};
}

function shortName(name: string) {
  return name.replace(/Bruker /, "Bruker ").replace(/JEOL /, "JEOL ");
}

function avgFitScore(decisions: { agent: string; confidence: number }[]) {
  const xs = decisions.filter((d) => d.agent === "agent2_fit").map((d) => d.confidence).filter(Boolean);
  if (xs.length === 0) return "—";
  return Math.round(xs.reduce((s, x) => s + x, 0) / xs.length);
}
