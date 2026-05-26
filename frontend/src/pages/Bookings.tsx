import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays, FileDown, ShieldCheck, Pencil, Trash2, X, Loader2, CheckCircle2, AlertTriangle,
} from "lucide-react";
import clsx from "clsx";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { PageBody, PageHeader } from "../components/PageShell";

type Toast = { kind: "ok" | "err"; text: string } | null;
type Booking = Record<string, unknown>;

export default function Bookings() {
  const qc = useQueryClient();
  const { profile, user, isAdmin } = useAuth();
  const userEmail = (profile?.email || user?.email || "").trim();

  // Privacy scoping — non-admin researchers only ever see their own schedule;
  // admins see the full facility view.
  const { data: bookings = [], isLoading } = useQuery({
    queryKey: isAdmin ? ["bookings"] : ["my-bookings", userEmail],
    queryFn: isAdmin ? api.bookings : () => api.myBookings(userEmail),
    enabled: isAdmin || !!userEmail,
  });

  const [toast, setToast] = useState<Toast>(null);
  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 6000);
    return () => window.clearTimeout(t);
  }, [toast]);

  const editM = useMutation({
    mutationFn: ({ id, newStart, reason }: { id: number; newStart: string; reason?: string }) =>
      api.requestBookingEdit(id, userEmail, newStart, reason),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["my-requests", userEmail] });
      setToast({ kind: "ok", text: r.message });
    },
    onError: (e: Error) => setToast({ kind: "err", text: e.message || "Could not submit reschedule" }),
  });
  const cancelM = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason?: string }) =>
      api.requestBookingCancel(id, userEmail, reason),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["my-requests", userEmail] });
      setToast({ kind: "ok", text: r.message });
    },
    onError: (e: Error) => setToast({ kind: "err", text: e.message || "Could not submit cancellation" }),
  });

  return (
    <>
      <PageHeader
        title={isAdmin ? "Schedule — facility-wide" : "My schedule"}
        subtitle={isAdmin
          ? "All bookings across the facility. Filter by instrument from the table."
          : "Your booked sessions. Edits and cancellations go through admin approval."}
        badge={
          <span className="chip bg-ink-100 text-ink-700 inline-flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5" />
            {isAdmin ? "Admin view" : "Personal view"}
          </span>
        }
      />
      <PageBody>
        {toast && (
          <div className={clsx(
            "rounded-lg border px-4 py-2.5 text-sm font-medium flex items-center gap-2",
            toast.kind === "ok" ? "bg-ok-50 border-ok-200 text-ok-700" : "bg-danger-50 border-danger-200 text-danger-700",
          )}>
            {toast.kind === "ok" ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
            {toast.text}
            <button onClick={() => setToast(null)} className="ml-auto text-current/60 hover:text-current">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {isLoading ? (
          <p className="text-sm text-ink-500">Loading…</p>
        ) : bookings.length === 0 ? (
          <div className="card-pad text-center py-16">
            <CalendarDays className="w-10 h-10 text-ink-300 mx-auto" />
            <p className="text-ink-500 mt-3 text-sm">
              {isAdmin
                ? "No bookings yet — once a researcher confirms an intake, the booking will appear here."
                : "You don't have any bookings yet — start one from Book a session."}
            </p>
          </div>
        ) : (
          <div className="card overflow-hidden">
            <div className="card-header">
              <h2 className="card-title">{isAdmin ? "All bookings" : "Your bookings"}</h2>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-ink-50 border-b border-ink-200">
                <tr className="text-left text-[11px] tracking-wider font-semibold uppercase text-ink-500">
                  <th className="px-5 py-3">Instrument</th>
                  {isAdmin && <th className="px-5 py-3">Researcher</th>}
                  <th className="px-5 py-3">Start</th>
                  <th className="px-5 py-3">End</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3 text-right">SOP</th>
                  {!isAdmin && <th className="px-5 py-3 text-right">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-200">
                {bookings.map((b) => (
                  <BookingRow
                    key={String(b.id)}
                    b={b}
                    isAdmin={isAdmin}
                    onEdit={(id, newStart, reason) => editM.mutate({ id, newStart, reason })}
                    onCancel={(id, reason) => cancelM.mutate({ id, reason })}
                    pending={editM.isPending || cancelM.isPending}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </PageBody>
    </>
  );
}

function BookingRow({
  b, isAdmin, onEdit, onCancel, pending,
}: {
  b: Booking;
  isAdmin: boolean;
  onEdit: (id: number, newStart: string, reason?: string) => void;
  onCancel: (id: number, reason?: string) => void;
  pending: boolean;
}) {
  const id = Number(b.id);
  const startISO = String(b.start_time);
  const status = String(b.status ?? "");
  const isFuture = new Date(startISO).getTime() > Date.now();
  const isCancelled = status === "cancelled";
  const canModify = !isAdmin && isFuture && !isCancelled;

  const [mode, setMode] = useState<"none" | "edit" | "cancel">("none");
  // datetime-local needs YYYY-MM-DDTHH:MM (no seconds, local tz)
  const [newStart, setNewStart] = useState<string>(() => isoToLocalInput(startISO));
  const [reason, setReason] = useState<string>("");

  function submit() {
    if (mode === "edit") onEdit(id, new Date(newStart).toISOString(), reason || undefined);
    else if (mode === "cancel") onCancel(id, reason || undefined);
    setMode("none");
    setReason("");
  }

  return (
    <>
      <tr className="hover:bg-ink-50">
        <td className="px-5 py-3 font-medium text-ink-900">{String(b.instrument_name ?? b.instrument_id)}</td>
        {isAdmin && <td className="px-5 py-3 text-ink-700">{String(b.researcher_name ?? "—")}</td>}
        <td className="px-5 py-3 text-ink-700">{new Date(startISO).toLocaleString()}</td>
        <td className="px-5 py-3 text-ink-700">{new Date(String(b.end_time)).toLocaleString()}</td>
        <td className="px-5 py-3">
          <span className={clsx(isCancelled ? "pill-muted" : "pill-ok")}>{status || "confirmed"}</span>
        </td>
        <td className="px-5 py-3 text-right">
          {b.sop_path ? (
            <a
              href={api.sopUrl(String(b.sop_path))}
              className="text-navy-700 hover:underline inline-flex items-center gap-1 text-sm"
              download
            >
              <FileDown className="w-4 h-4" /> Download
            </a>
          ) : (
            <span className="text-ink-400">—</span>
          )}
        </td>
        {!isAdmin && (
          <td className="px-5 py-3 text-right">
            {canModify ? (
              <div className="inline-flex items-center gap-1.5">
                <button
                  onClick={() => setMode(mode === "edit" ? "none" : "edit")}
                  className="btn text-xs"
                  title="Request a reschedule (admin approval required)"
                  disabled={pending}
                >
                  <Pencil className="w-3.5 h-3.5" /> Edit
                </button>
                <button
                  onClick={() => setMode(mode === "cancel" ? "none" : "cancel")}
                  className="btn text-xs"
                  title="Request cancellation (admin approval required)"
                  disabled={pending}
                >
                  <Trash2 className="w-3.5 h-3.5" /> Cancel
                </button>
              </div>
            ) : (
              <span className="text-ink-400 text-xs italic">
                {isCancelled ? "cancelled" : !isFuture ? "past" : ""}
              </span>
            )}
          </td>
        )}
      </tr>
      {mode !== "none" && (
        <tr className="bg-ink-50/60">
          <td colSpan={isAdmin ? 7 : 7} className="px-5 py-4">
            <div className="flex items-end gap-3 flex-wrap">
              {mode === "edit" && (
                <label className="block">
                  <span className="block text-[11px] font-semibold tracking-wide text-ink-500 uppercase mb-1">
                    New start time
                  </span>
                  <input
                    type="datetime-local"
                    className="input"
                    value={newStart}
                    onChange={(e) => setNewStart(e.target.value)}
                  />
                </label>
              )}
              <label className="block flex-1 min-w-[220px]">
                <span className="block text-[11px] font-semibold tracking-wide text-ink-500 uppercase mb-1">
                  Reason (optional)
                </span>
                <input
                  type="text"
                  className="input"
                  placeholder={mode === "edit" ? "e.g. sample delayed" : "e.g. project pivot"}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </label>
              <div className="flex items-center gap-2">
                <button onClick={submit} disabled={pending} className="btn-primary text-xs">
                  {pending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                  Submit {mode === "edit" ? "reschedule" : "cancellation"} for approval
                </button>
                <button onClick={() => { setMode("none"); setReason(""); }} className="btn text-xs">
                  Discard
                </button>
              </div>
            </div>
            <p className="text-[11px] text-ink-500 mt-2">
              An admin will review your request. You'll get an email and an entry in <span className="font-mono">My Requests</span> once they decide.
            </p>
          </td>
        </tr>
      )}
    </>
  );
}

function isoToLocalInput(iso: string): string {
  try {
    const d = new Date(iso);
    const tzOffsetMin = d.getTimezoneOffset();
    const local = new Date(d.getTime() - tzOffsetMin * 60_000);
    return local.toISOString().slice(0, 16);
  } catch {
    return "";
  }
}
