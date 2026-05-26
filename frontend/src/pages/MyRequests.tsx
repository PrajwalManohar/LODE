import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  Clock,
  ClipboardList,
  Loader2,
  Mail,
  ShieldAlert,
  Sparkles,
  Wrench,
  X,
} from "lucide-react";
import clsx from "clsx";
import { PageBody, PageHeader } from "../components/PageShell";
import { api, AutomationEvent, BookingOption, WorkOrder } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useRealtime } from "../lib/useRealtime";

type Toast = { kind: "ok" | "err"; text: string } | null;

/**
 * "My Requests" — the user-facing request tracker. Shows live status for:
 *   • HITL booking requests (pending / approved / denied / completed)
 *   • Maintenance work orders for instruments the user has upcoming bookings on
 *
 * Real-time updates come from the existing useRealtime() hook subscribed to
 * automation_events + work_orders, so changes from a supervisor or facilities
 * appear here without a refresh.
 */
type PendingFlash = {
  kind: "pending";
  instrument: string;
  reasons: string[];
  sessionId?: string;
};

export default function MyRequests() {
  const { profile, user } = useAuth();
  const email = (profile?.email || user?.email || "").trim();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const [toast, setToast] = useState<Toast>(null);
  const [flash, setFlash] = useState<PendingFlash | null>(
    (location.state as { flash?: PendingFlash } | null)?.flash ?? null,
  );
  // useRealtime returns true when the supabase channel is SUBSCRIBED.
  // It's already mounted in Layout, calling it here just reads the same
  // status — the subscription is shared.
  const live = useRealtime();

  // Clear the flash from history.state so a refresh won't redisplay it.
  useEffect(() => {
    if (flash) navigate(location.pathname, { replace: true, state: {} });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { data, isLoading } = useQuery({
    queryKey: ["my-requests", email],
    queryFn: () => api.myRequests(email),
    enabled: !!email,
    refetchInterval: 15000,           // belt-and-braces in case realtime is off
    refetchOnWindowFocus: true,       // catch admin actions taken in other tabs
    staleTime: 0,
  });

  // The shared useRealtime() hook (mounted in Layout) now invalidates
  // ["my-requests"] when automation_events, work_orders, or bookings change
  // server-side, so this page refreshes the moment Supabase pushes a row.

  const complete = useMutation({
    mutationFn: ({ eventId, option }: { eventId: number; option?: BookingOption }) =>
      api.completeHitl(eventId, option),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["my-requests", email] });
      qc.invalidateQueries({ queryKey: ["bookings"] });
      setToast(
        r.ok
          ? { kind: "ok", text: `Booking confirmed (#${r.booking_id ?? "?"}). SOP generated and emailed.` }
          : { kind: "err", text: r.message || "Confirmation failed" }
      );
    },
    onError: (e: Error) => setToast({ kind: "err", text: e.message || "Confirmation failed" }),
  });

  // Dismissed request IDs — persisted server-side via the audit log so the
  // "cleared" state follows the user across devices.
  const { data: dismissedRes } = useQuery({
    queryKey: ["dismissed-requests", email],
    queryFn: () => api.dismissedIds(email),
    enabled: !!email,
  });
  const dismissedIds = useMemo(
    () => new Set(dismissedRes?.event_ids ?? []),
    [dismissedRes],
  );

  const dismiss = useMutation({
    mutationFn: (eventId: number) => api.dismissRequest(eventId, email),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dismissed-requests", email] });
      setToast({ kind: "ok", text: "Request cleared from your list." });
    },
    onError: (e: Error) => setToast({ kind: "err", text: e.message || "Could not clear request" }),
  });

  const { data: dismissedWoRes } = useQuery({
    queryKey: ["dismissed-work-orders", email],
    queryFn: () => api.dismissedWorkOrderIds(email),
    enabled: !!email,
  });
  const dismissedWoIds = useMemo(
    () => new Set(dismissedWoRes?.work_order_ids ?? []),
    [dismissedWoRes],
  );
  const dismissWo = useMutation({
    mutationFn: (id: number) => api.dismissWorkOrder(id, email),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dismissed-work-orders", email] });
      setToast({ kind: "ok", text: "Work order cleared from your list." });
    },
    onError: (e: Error) => setToast({ kind: "err", text: e.message || "Could not clear work order" }),
  });

  // Auto-complete from email link: /requests?complete=<event_id>
  useEffect(() => {
    const eid = params.get("complete");
    if (!eid) return;
    const id = Number(eid);
    if (!Number.isNaN(id)) complete.mutate({ eventId: id });
    const next = new URLSearchParams(params);
    next.delete("complete");
    setParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 6000);
    return () => window.clearTimeout(t);
  }, [toast]);

  const hitl = (data?.hitl ?? []).filter((h) => !dismissedIds.has(h.id));
  const maintenance = (data?.maintenance ?? []).filter((w) => !dismissedWoIds.has(w.id));

  const counts = useMemo(() => ({
    pending: hitl.filter((h) => h.status === "pending").length,
    approved: hitl.filter((h) => h.status === "approved").length,
    denied: hitl.filter((h) => h.status === "denied").length,
    completed: hitl.filter((h) => h.status === "completed").length,
    openMaint: maintenance.filter((w) => w.status !== "closed").length,
  }), [hitl, maintenance]);

  if (!email) {
    return (
      <>
        <PageHeader title="My Requests" />
        <PageBody>
          <div className="card-pad text-sm text-ink-600">
            Sign in to see your requests.
          </div>
        </PageBody>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="My Requests"
        subtitle="Your booking approvals and any maintenance affecting your sessions — live."
        badge={
          <span className="flex items-center gap-2">
            <span
              className={clsx(
                "chip inline-flex items-center gap-1.5",
                live ? "bg-ok-50 text-ok-700" : "bg-ink-100 text-ink-500",
              )}
              title={live ? "Supabase realtime connected" : "Realtime offline — using 15s polling"}
            >
              <span className={clsx("w-1.5 h-1.5 rounded-full", live ? "bg-ok-600 animate-pulse" : "bg-ink-400")} />
              {live ? "Live" : "Polling"}
            </span>
            <span className="chip bg-ink-100 text-ink-700 font-mono text-xs">{email}</span>
          </span>
        }
      />

      <PageBody>
        {flash && flash.kind === "pending" && (
          <div className="rounded-xl border border-warn-600/40 bg-warn-50 p-5">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-warn-100 flex items-center justify-center shrink-0">
                <Mail className="w-5 h-5 text-warn-700" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-base font-semibold text-warn-700">
                  Your booking was received and is awaiting admin approval.
                </p>
                <p className="text-sm text-ink-700 mt-1">
                  We have emailed every admin to review your request for{" "}
                  <span className="font-semibold">{flash.instrument}</span>. You will also receive
                  an email when a decision is made. Track the status here in real time — the row
                  below will update automatically.
                </p>
                {flash.reasons.length > 0 && (
                  <details className="mt-3 text-xs">
                    <summary className="cursor-pointer text-ink-600 font-medium">
                      Why approval is required ({flash.reasons.length})
                    </summary>
                    <ul className="mt-2 ml-2 space-y-1">
                      {flash.reasons.map((r, i) => (
                        <li key={i} className="text-ink-600 flex items-start gap-1.5">
                          <span className="text-warn-700 mt-0.5">•</span>
                          <span>{r}</span>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
              <button
                onClick={() => setFlash(null)}
                className="text-warn-700/60 hover:text-warn-700 shrink-0"
                title="Dismiss"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {toast && (
          <div
            className={clsx(
              "rounded-lg border px-4 py-2.5 text-sm font-medium flex items-center gap-2",
              toast.kind === "ok"
                ? "bg-ok-50 border-ok-200 text-ok-700"
                : "bg-danger-50 border-danger-200 text-danger-700"
            )}
          >
            {toast.kind === "ok" ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
            {toast.text}
            <button onClick={() => setToast(null)} className="ml-auto text-current/60 hover:text-current">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Quick counters */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Stat label="Pending"  value={counts.pending}   tone={counts.pending > 0 ? "warn" : "neutral"} icon={<Clock className="w-4 h-4" />} />
          <Stat label="Approved" value={counts.approved}  tone={counts.approved > 0 ? "ok" : "neutral"} icon={<CheckCircle2 className="w-4 h-4" />} />
          <Stat label="Denied"   value={counts.denied}    tone={counts.denied > 0 ? "danger" : "neutral"} icon={<X className="w-4 h-4" />} />
          <Stat label="Completed" value={counts.completed} tone="neutral" icon={<ClipboardList className="w-4 h-4" />} />
          <Stat label="Affecting me" value={counts.openMaint} tone={counts.openMaint > 0 ? "warn" : "neutral"} icon={<Wrench className="w-4 h-4" />} />
        </div>

        {/* HITL section */}
        <section className="card overflow-hidden">
          <header className="card-header">
            <h2 className="font-display text-[15px] font-semibold flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-warn-700" /> Booking approval requests
            </h2>
            {isLoading && <Loader2 className="w-4 h-4 animate-spin text-ink-400" />}
          </header>
          {hitl.length === 0 ? (
            <Empty
              icon={<ShieldAlert className="w-10 h-10 text-ink-300 mx-auto" />}
              text={
                <>
                  You have no approval requests yet. When a booking requires admin sign-off — for
                  example, missing training certification, calibration overdue, hazardous
                  materials, or a fit score below 80 — it will appear here in real time with the
                  current status (pending → approved/denied → completed).
                </>
              }
              action={<Link className="btn-primary mt-4" to="/intake"><Sparkles className="w-4 h-4" /> Start a booking</Link>}
            />
          ) : (
            <ul className="divide-y divide-ink-200">
              {hitl.map((h) => (
                <HitlRow
                  key={h.id}
                  h={h}
                  onComplete={(option) => complete.mutate({ eventId: h.id, option })}
                  onDismiss={() => dismiss.mutate(h.id)}
                  pending={complete.isPending}
                  dismissing={dismiss.isPending}
                />
              ))}
            </ul>
          )}
        </section>

        {/* Maintenance section */}
        <section className="card overflow-hidden">
          <header className="card-header">
            <h2 className="font-display text-[15px] font-semibold flex items-center gap-2">
              <Wrench className="w-4 h-4 text-purple-700" /> Maintenance affecting my bookings
            </h2>
          </header>
          {maintenance.length === 0 ? (
            <Empty
              icon={<Wrench className="w-10 h-10 text-ink-300 mx-auto" />}
              text="No active maintenance on any instrument you have an upcoming booking on."
            />
          ) : (
            <ul className="divide-y divide-ink-200">
              {maintenance.map((w) => (
                <MaintenanceRow
                  key={w.id}
                  w={w}
                  onDismiss={() => dismissWo.mutate(w.id)}
                  dismissing={dismissWo.isPending}
                />
              ))}
            </ul>
          )}
        </section>
      </PageBody>
    </>
  );
}

// ============================================================================
// Rows
// ============================================================================
function HitlRow({
  h, onComplete, onDismiss, pending, dismissing,
}: {
  h: AutomationEvent;
  onComplete: (option?: BookingOption) => void;
  onDismiss: () => void;
  pending: boolean;
  dismissing: boolean;
}) {
  const p = parsePayload(h.payload);
  const status = h.status;
  const reasons: string[] = Array.isArray(p.reasons) ? (p.reasons as string[]) : [];
  const [picking, setPicking] = useState(false);
  const [slots, setSlots] = useState<BookingOption[] | null>(null);
  const [loadingSlots, setLoadingSlots] = useState(false);

  const loadSlots = async () => {
    setPicking(true);
    if (slots) return;
    setLoadingSlots(true);
    try {
      const r = await api.requestSlots(h.id);
      setSlots(r.options);
    } catch {
      setSlots([]);
    } finally {
      setLoadingSlots(false);
    }
  };

  const statusBlock = (() => {
    if (status === "pending") return { pill: "pill-warn", label: "Awaiting supervisor review", icon: <Clock className="w-4 h-4" /> };
    if (status === "approved") return { pill: "pill-ok", label: "Approved — ready to confirm", icon: <CheckCircle2 className="w-4 h-4" /> };
    if (status === "denied") return { pill: "pill-danger", label: "Denied", icon: <X className="w-4 h-4" /> };
    if (status === "completed") return { pill: "pill-muted", label: "Booking confirmed", icon: <CheckCircle2 className="w-4 h-4" /> };
    return { pill: "pill-muted", label: status, icon: null };
  })();

  return (
    <li className="px-5 py-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-semibold text-ink-900 tracking-tight">
              {str(p, "booking_code", `HITL-${h.id}`)}
            </p>
            <span className={statusBlock.pill}>{statusBlock.label}</span>
            {p.alert_title ? <span className="pill-muted">{String(p.alert_title)}</span> : null}
          </div>
          <p className="text-xs text-ink-500 mt-1 leading-snug">
            <span className="text-ink-700">{str(p, "instrument_name")}</span>
            {" · "}
            <span className="text-ink-700">{str(p, "when", "Not scheduled")}</span>
          </p>
          <p className="text-xs text-ink-500 mt-0.5">
            Experiment: <span className="text-ink-700">{str(p, "experiment")}</span>
          </p>
          {reasons.length > 0 && (
            <ul className="mt-2 ml-1 space-y-0.5">
              {reasons.map((r, i) => (
                <li key={i} className="text-xs text-ink-600 flex items-start gap-1.5">
                  <span className="text-warn-700 mt-0.5">•</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="text-[11px] text-ink-400 mt-2">
            Submitted {new Date(h.created_at).toLocaleString()}
          </p>
        </div>
        {/* Clear button — only on terminal-state rows (approved / denied / completed).
            Pending requests cannot be cleared. */}
        {(status === "approved" || status === "denied" || status === "completed") && (
          <button
            onClick={onDismiss}
            disabled={dismissing}
            className="btn shrink-0 text-xs"
            title="Remove this request from your list (audit trail is retained)"
          >
            {dismissing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <X className="w-3.5 h-3.5" />}
            Clear
          </button>
        )}
        {status === "approved" && !picking && (
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              onClick={() => onComplete()}
              disabled={pending}
              className="btn-primary"
              title="Confirm the booking at the slot your supervisor approved"
            >
              {pending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CalendarDays className="w-4 h-4" />}
              Confirm this slot
            </button>
            <button
              onClick={loadSlots}
              disabled={pending}
              className="btn"
              title="Choose a different time before confirming"
            >
              <Clock className="w-4 h-4" /> Pick a different time
            </button>
          </div>
        )}
        {status === "denied" && (
          <Link to="/intake" className="btn shrink-0">
            <Sparkles className="w-4 h-4" /> Start a new booking
          </Link>
        )}
      </div>

      {/* Reschedule picker (item 5) */}
      {status === "approved" && picking && (
        <div className="mt-3 ml-1 rounded-xl border border-ink-200 bg-ink-50 p-4">
          <div className="flex items-center justify-between gap-2 mb-2">
            <p className="text-xs font-semibold text-ink-700 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" /> Choose a new time for {str(p, "instrument_name")}
            </p>
            <button onClick={() => setPicking(false)} className="text-ink-400 hover:text-ink-700" title="Back">
              <X className="w-4 h-4" />
            </button>
          </div>
          {loadingSlots ? (
            <p className="text-xs text-ink-500 flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" /> Finding open slots…
            </p>
          ) : slots && slots.length > 0 ? (
            <div className="grid sm:grid-cols-3 gap-2">
              {slots.map((o, i) => (
                <button
                  key={i}
                  onClick={() => onComplete(o)}
                  disabled={pending}
                  className="text-left rounded-lg border border-ink-200 bg-white px-3 py-2 hover:border-navy-500 hover:ring-2 hover:ring-navy-500/20 transition disabled:opacity-50"
                >
                  <p className="text-xs font-semibold text-ink-900">
                    {new Date(o.start_time).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}
                  </p>
                  <p className="text-[11px] text-ink-600">
                    {new Date(o.start_time).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}
                    {" – "}
                    {new Date(o.end_time).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}
                  </p>
                </button>
              ))}
            </div>
          ) : (
            <p className="text-xs text-ink-500">No open slots found — confirm the original slot instead.</p>
          )}
          <p className="text-[11px] text-ink-400 mt-2">
            Selecting a slot confirms the booking and generates the SOP for that time.
          </p>
        </div>
      )}
    </li>
  );
}

function MaintenanceRow({
  w, onDismiss, dismissing,
}: {
  w: WorkOrder;
  onDismiss: () => void;
  dismissing: boolean;
}) {
  const usagePct =
    w.calibration_interval_hours > 0
      ? Math.round((w.usage_hours / w.calibration_interval_hours) * 100)
      : 0;
  const statusPill =
    w.status === "closed" ? "pill-ok" : w.status === "in_progress" ? "pill-info" : "pill-warn";
  const isClosed = w.status === "closed";
  return (
    <li className={clsx("px-5 py-4", isClosed && "opacity-70")}>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-semibold text-ink-900 tracking-tight">
              WO-{String(w.id).padStart(3, "0")} · {w.instrument_name ?? w.instrument_id}
            </p>
            <span className={statusPill}>{w.status.replace("_", " ")}</span>
            <SeverityPill severity={w.severity} />
          </div>
          <p className="text-sm text-ink-700 mt-1.5 leading-snug">{w.issue}</p>
          {w.recommended_action && (
            <p className="text-xs text-ink-500 mt-1.5 leading-snug">
              <span className="font-semibold text-ink-600 uppercase tracking-wider text-[10px]">
                Recommendation:
              </span>{" "}
              {w.recommended_action}
            </p>
          )}
          <div className="flex items-center gap-3 mt-2 flex-wrap">
            <span className="text-[11px] font-mono text-ink-500 tabular-nums">
              {w.usage_hours.toFixed(0)}h / {w.calibration_interval_hours}h cal
            </span>
            <div className="w-32 h-1 rounded-full bg-ink-100 overflow-hidden">
              <div
                className={clsx(
                  "h-full rounded-full",
                  usagePct >= 100 ? "bg-danger-600" : usagePct >= 75 ? "bg-warn-600" : "bg-navy-700"
                )}
                style={{ width: `${Math.min(100, usagePct)}%` }}
              />
            </div>
            <span className="text-[11px] text-ink-400">
              Opened {new Date(w.created_at).toLocaleString()}
            </span>
          </div>
        </div>
        {isClosed && (
          <button
            onClick={onDismiss}
            disabled={dismissing}
            className="btn shrink-0 text-xs"
            title="Remove this closed work order from your list"
          >
            {dismissing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <X className="w-3.5 h-3.5" />}
            Clear
          </button>
        )}
      </div>
    </li>
  );
}

// ============================================================================
// Bits
// ============================================================================
function Stat({
  label, value, tone, icon,
}: {
  label: string;
  value: number;
  tone: "ok" | "warn" | "danger" | "neutral";
  icon: React.ReactNode;
}) {
  const accent =
    tone === "danger" ? "text-danger-700" :
    tone === "warn" ? "text-warn-700" :
    tone === "ok" ? "text-ok-700" : "text-ink-900";
  return (
    <div className="card-pad">
      <p className="text-xs text-ink-500 font-medium flex items-center gap-1.5">
        {icon} {label}
      </p>
      <p className={clsx("text-[24px] font-bold mt-1 leading-none tabular-nums", accent)}>{value}</p>
    </div>
  );
}

function Empty({
  icon, text, action,
}: {
  icon: React.ReactNode;
  text: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="px-5 py-12 text-center max-w-xl mx-auto">
      {icon}
      <p className="text-ink-500 mt-3 text-sm leading-relaxed">{text}</p>
      {action}
    </div>
  );
}

function SeverityPill({ severity }: { severity: string }) {
  const s = severity.toLowerCase();
  if (s === "critical") return <span className="pill-danger">Critical</span>;
  if (s === "warning") return <span className="pill-warn">Warning</span>;
  return <span className="pill-muted">{severity}</span>;
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

function str(p: Record<string, unknown>, key: string, fallback = "—"): string {
  const v = p[key];
  return typeof v === "string" && v ? v : fallback;
}
