import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { CalendarDays, AlertTriangle, FlaskConical, MapPin, FileDown, CheckCircle2, Loader2 } from "lucide-react";
import clsx from "clsx";
import {
  api,
  BookingOption,
  ChatResponse,
  ExperimentContext,
  InstrumentFit,
} from "../lib/api";
import { PageBody, PageHeader } from "../components/PageShell";
import { Citations } from "../components/Citations";

type Nav = {
  lastResponse: ChatResponse;
  context: ExperimentContext;
  sessionId?: string;
};

export default function FitResults() {
  const { state } = useLocation();
  const navigate = useNavigate();
  const data = state as Nav | null;

  useEffect(() => {
    if (!data) navigate("/intake", { replace: true });
  }, [data, navigate]);
  if (!data) return null;

  const { context: ctx, sessionId } = data;
  const recs = data.lastResponse.recommendations;
  const slots = data.lastResponse.booking_options;
  const safety = data.lastResponse.safety_gate;

  const sortedRecs = useMemo(() => [...recs].sort((a, b) => b.fit_score - a.fit_score), [recs]);

  const [picked, setPicked] = useState<InstrumentFit | null>(sortedRecs[0] ?? null);
  const [confirmed, setConfirmed] = useState<ChatResponse | null>(null);

  const confirm = useMutation({
    mutationFn: (opt: BookingOption) => api.confirm(ctx, opt, picked!, sessionId),
    onSuccess: (resp) => setConfirmed(resp),
  });

  const steps = [
    { label: "Context",   state: "done" } as const,
    { label: "Fit score", state: "done" } as const,
    { label: "Schedule",  state: confirmed ? "done" : "active" } as const,
    { label: "SOP",       state: confirmed ? "done" : "pending" } as const,
  ];

  return (
    <>
      <PageHeader title="Instrument fit results" steps={steps} />

      <PageBody>
        {/* Context summary strip */}
        <div className="card-pad flex flex-wrap items-start gap-x-10 gap-y-3">
          <span className="w-9 h-9 rounded-lg bg-ink-100 flex items-center justify-center">
            <FlaskConical className="w-4 h-4 text-ink-600" />
          </span>
          <SummaryItem label="Material"  value={ctx.material_type || "—"} />
          <SummaryItem label="Goal"      value={ctx.analysis_goal || "—"} />
          <SummaryItem label="Deadline"  value={ctx.deadline || ctx.urgency || "—"} />
          <SummaryItem label="Prep"      value={ctx.coating_status || ctx.surface_condition || "Ready"} />
        </div>

        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-semibold">
            Agent 2 — Instrument fit scores{" "}
            <span className="font-normal text-ink-500">
              ({recs.length} instruments evaluated · {data.lastResponse.citations.length} RAG sources)
            </span>
          </h2>
        </div>

        {safety && !safety.passed && (
          <div className="rounded-xl border border-warn-600/40 bg-warn-50 p-4">
            <p className="text-sm font-semibold text-warn-700 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" /> Safety gate — lab manager review required
            </p>
            <ul className="mt-2 list-disc list-inside text-xs text-ink-700 space-y-1">
              {safety.reasons.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>
        )}

        <div className="space-y-4">
          {sortedRecs.map((r, idx) => (
            <FitCard
              key={r.instrument_id}
              rec={r}
              top={idx === 0}
              isPicked={picked?.instrument_id === r.instrument_id}
              onPick={() => setPicked(r)}
            />
          ))}
        </div>

        {/* Slot picker */}
        {picked && slots.length > 0 && !confirmed && (
          <section className="card-pad">
            <h2 className="text-[15px] font-semibold mb-3">Agent 3 — Proposed slots</h2>
            <div className="grid md:grid-cols-3 gap-3">
              {slots.map((s) => (
                <button
                  key={s.start_time + s.rank}
                  type="button"
                  disabled={confirm.isPending}
                  onClick={() => confirm.mutate(s)}
                  className="text-left rounded-xl border border-ink-200 p-4 hover:border-navy-700 hover:bg-ink-50 transition"
                >
                  <p className="text-sm font-semibold text-ink-900">
                    {new Date(s.start_time).toLocaleString(undefined, {
                      weekday: "short", month: "short", day: "numeric",
                      hour: "numeric", minute: "2-digit",
                    })}
                  </p>
                  <p className="text-xs text-ink-500 mt-1">{s.notes}</p>
                  <p className="text-xs mt-3 text-navy-700 font-mono">
                    score {s.score.toFixed(0)} · rank #{s.rank}
                  </p>
                </button>
              ))}
            </div>
            {confirm.isPending && (
              <p className="text-sm text-ink-500 mt-3 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" /> Generating SOP and firing automations…
              </p>
            )}
          </section>
        )}

        {confirmed && (
          <section className="rounded-xl border border-ok-600/40 bg-ok-50 p-5">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-6 h-6 text-ok-700 shrink-0" />
              <div className="flex-1">
                <p className="text-base font-semibold text-ok-700">Booking confirmed</p>
                <p className="text-sm text-ink-700 mt-1">{confirmed.message}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {confirmed.sop_path && (
                    <a className="btn-primary" href={api.sopUrl(confirmed.sop_path)} download>
                      <FileDown className="w-4 h-4" /> Download custom SOP
                    </a>
                  )}
                  <button className="btn" onClick={() => navigate("/bookings")}>
                    <CalendarDays className="w-4 h-4" /> View schedule
                  </button>
                </div>
                {confirmed.automations && (
                  <div className="mt-4 text-xs text-ink-600 space-y-1">
                    {confirmed.automations.airtable_booking && (
                      <p>
                        ● Airtable booking: <span className="font-mono">{confirmed.automations.airtable_booking.id}</span>
                        {" "}({confirmed.automations.airtable_booking.destination})
                      </p>
                    )}
                    {confirmed.automations.email && (
                      <p>
                        ● Email + SOP attachment via{" "}
                        <span className="font-semibold">{confirmed.automations.email.transport}</span>
                        {" "}→ {confirmed.automations.email.to.join(", ") || "no recipients"}
                      </p>
                    )}
                    {confirmed.automations.work_order ? <p>● Work order opened</p> : null}
                  </div>
                )}
              </div>
            </div>
          </section>
        )}
      </PageBody>
    </>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] font-semibold tracking-wider text-ink-500 uppercase">{label}</p>
      <p className="text-sm text-ink-900 font-medium mt-0.5">{value}</p>
    </div>
  );
}

function FitCard({
  rec,
  top,
  isPicked,
  onPick,
}: {
  rec: InstrumentFit;
  top: boolean;
  isPicked: boolean;
  onPick: () => void;
}) {
  const score = rec.fit_score;
  const grade = rec.grade || gradeFromScore(score);
  const color =
    score >= 80 ? { bar: "bg-ok-600", text: "text-ok-700", badge: "bg-navy-800 text-white" } :
    score >= 50 ? { bar: "bg-warn-600", text: "text-warn-700", badge: "bg-ink-200 text-ink-700" } :
                  { bar: "bg-ink-300", text: "text-ink-500", badge: "bg-ink-100 text-ink-500" };

  const params = paramsFromRationale(rec.rationale);
  const warning = warnFromRec(rec);

  return (
    <article className={clsx("card overflow-hidden", isPicked && "ring-2 ring-navy-700")}>
      <div className="px-5 py-4 flex items-start gap-4">
        <div className={clsx("w-10 h-10 rounded-md flex items-center justify-center font-bold text-sm shrink-0", color.badge)}>
          {grade}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-[15px] font-semibold text-ink-900">{rec.instrument_name}</h3>
            {top && <span className="pill bg-gold-100 text-gold-700">RECOMMENDED</span>}
          </div>
          <p className="text-xs text-ink-500 mt-0.5 flex items-center gap-1">
            <MapPin className="w-3 h-3" /> Coolbaugh Hall
          </p>
          <div className="mt-3 h-1.5 rounded-full bg-ink-100 overflow-hidden">
            <div className={clsx("h-full rounded-full", color.bar)} style={{ width: `${score}%` }} />
          </div>
        </div>
        <div className="text-right shrink-0 w-16">
          <p className={clsx("text-2xl font-bold tabular-nums leading-none", color.text)}>{score}</p>
          <p className="text-xs text-ink-500 mt-1">/100</p>
        </div>
      </div>

      <div className="px-5 pb-4 pl-[76px] -mt-1">
        <p className="text-sm text-ink-700 leading-relaxed">{rec.rationale}</p>

        {(rec.citations?.length ?? 0) > 0 && (
          <div className="mt-3">
            <Citations citations={rec.citations} label="" />
          </div>
        )}

        {params.length > 0 && (
          <div className="mt-3 grid grid-cols-2 md:grid-cols-3 gap-2">
            {params.map((p) => (
              <div key={p.label} className="rounded-lg border border-ink-200 px-3 py-2 bg-ink-50">
                <p className="text-[10px] font-semibold tracking-wider text-ink-500 uppercase">{p.label}</p>
                <p className="text-sm text-ink-900 mt-0.5">{p.value}</p>
              </div>
            ))}
          </div>
        )}

        <div className="mt-4 flex items-center justify-between gap-3 flex-wrap">
          <div className="text-xs">
            {warning ? (
              <span className="flex items-center gap-1.5 text-warn-700">
                <AlertTriangle className="w-3.5 h-3.5" /> {warning}
              </span>
            ) : rec.requires_training ? (
              <span className="flex items-center gap-1.5 text-warn-700">
                <AlertTriangle className="w-3.5 h-3.5" /> Training required — lab manager review
              </span>
            ) : (
              <span className="pill-ok">Ready to schedule</span>
            )}
          </div>
          <button
            type="button"
            onClick={onPick}
            className={isPicked ? "btn-primary" : "btn"}
          >
            <CalendarDays className="w-4 h-4" /> {isPicked ? "Selected" : "Select & schedule"}
          </button>
        </div>
      </div>
    </article>
  );
}

function gradeFromScore(s: number) {
  if (s >= 85) return "A";
  if (s >= 70) return "B";
  if (s >= 50) return "C";
  if (s >= 25) return "D";
  return "N/A";
}
function paramsFromRationale(_r: string): { label: string; value: string }[] {
  // Heuristic param extraction kept small to mirror the mockup look
  return [];
}
function warnFromRec(rec: InstrumentFit) {
  if (rec.prep_time_minutes > 0) {
    return `Carbon coating required (+${rec.prep_time_minutes} min prep)`;
  }
  return "";
}
