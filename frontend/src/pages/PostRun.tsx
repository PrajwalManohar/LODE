import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, AlertCircle, Loader2, XCircle } from "lucide-react";
import { api } from "../lib/api";
import { PageBody, PageHeader } from "../components/PageShell";

export default function PostRun() {
  const qc = useQueryClient();
  const { data: bookings = [] } = useQuery({ queryKey: ["bookings"], queryFn: api.bookings });

  const [bookingId, setBookingId] = useState("");
  const [ranAsPlanned, setRanAsPlanned] = useState(true);
  const [params, setParams] = useState("");
  const [anomalies, setAnomalies] = useState("");
  const [quality, setQuality] = useState(4);
  const [researcher, setResearcher] = useState("");
  const [result, setResult] = useState<{ message: string; maintenance_alert: boolean } | null>(null);

  useEffect(() => {
    if (!bookingId && bookings.length > 0) {
      const last = bookings[bookings.length - 1];
      setBookingId(String(last.id));
      if (last.researcher_name) setResearcher(String(last.researcher_name));
    }
  }, [bookings, bookingId]);

  useEffect(() => {
    if (!result) return;
    const t = window.setTimeout(() => setResult(null), 12000);
    return () => window.clearTimeout(t);
  }, [result]);

  const submit = useMutation({
    mutationFn: () =>
      api.postRun({
        booking_id: parseInt(bookingId, 10) || 0,
        ran_as_planned: ranAsPlanned,
        actual_parameters: params,
        anomalies,
        data_quality_rating: quality,
        notes: "",
        researcher_name: researcher,
      }),
    onMutate: () => setResult(null),
    onSuccess: (data) => {
      setResult(data);
      // A post-run can open a work order + re-index the corpus — refresh the
      // surfaces that depend on it so the demo stays consistent.
      qc.invalidateQueries({ queryKey: ["work-orders"] });
      qc.invalidateQueries({ queryKey: ["automations"] });
      qc.invalidateQueries({ queryKey: ["rag"] });
    },
  });

  useEffect(() => {
    if (!submit.isError) return;
    const t = window.setTimeout(() => submit.reset(), 8000);
    return () => window.clearTimeout(t);
  }, [submit]);

  return (
    <>
      <PageHeader
        title="Post-run report"
        subtitle="Log how your session went — Agent 5 records the run, re-indexes the knowledge base, and opens a maintenance work order if anomalies are detected."
      />
      <PageBody className="max-w-3xl">
        <form
          className="card-pad space-y-5"
          onSubmit={(e) => { e.preventDefault(); submit.mutate(); }}
        >
          <Field label="Booking">
            {bookings.length > 0 ? (
              <select className="input" value={bookingId} onChange={(e) => setBookingId(e.target.value)}>
                {bookings.map((b) => (
                  <option key={String(b.id)} value={String(b.id)}>
                    #{String(b.id)} · {String(b.instrument_name ?? b.instrument_id)} ·{" "}
                    {new Date(String(b.start_time)).toLocaleString()}
                  </option>
                ))}
              </select>
            ) : (
              <input className="input" value={bookingId} onChange={(e) => setBookingId(e.target.value)} placeholder="No bookings yet" />
            )}
          </Field>

          <Field label="Researcher name">
            <input className="input" value={researcher} onChange={(e) => setResearcher(e.target.value)} />
          </Field>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={ranAsPlanned}
              onChange={(e) => setRanAsPlanned(e.target.checked)}
              className="rounded border-ink-300"
            />
            <span className="text-sm">Experiment ran as planned</span>
          </label>

          <Field label="Actual parameters used">
            <textarea
              className="input min-h-[100px] resize-y"
              value={params}
              onChange={(e) => setParams(e.target.value)}
              placeholder="e.g. 15 kV, EDS mapping, 2θ 10–80°"
            />
          </Field>

          <Field label="Anomalies (if any)">
            <textarea
              className="input min-h-[80px] resize-y"
              value={anomalies}
              onChange={(e) => setAnomalies(e.target.value)}
              placeholder="Detector saturation, vacuum issues…"
            />
          </Field>

          <Field label={`Data quality rating: ${quality}/5`}>
            <input
              type="range" min={1} max={5} value={quality}
              onChange={(e) => setQuality(parseInt(e.target.value, 10))}
              className="w-full accent-navy-700"
            />
          </Field>

          <button
            type="submit"
            className="btn-primary w-full"
            disabled={submit.isPending || !bookingId}
          >
            {submit.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Processing report…
              </>
            ) : (
              "Submit post-run report"
            )}
          </button>
        </form>

        {submit.isError && (
          <div className="card-pad flex items-start gap-3 border-danger-600/40">
            <XCircle className="w-6 h-6 text-danger-700 shrink-0" />
            <div>
              <p className="font-semibold text-ink-900">Could not submit the report</p>
              <p className="text-sm text-danger-700 mt-1 font-mono break-all">
                {String((submit.error as Error)?.message || submit.error)}
              </p>
              <button
                onClick={() => submit.mutate()}
                className="btn mt-3 text-xs"
                disabled={submit.isPending}
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {result && (
          <div className={`card-pad flex items-start gap-3 ${result.maintenance_alert ? "border-danger-600/40" : "border-ok-600/40"}`}>
            {result.maintenance_alert
              ? <AlertCircle className="w-6 h-6 text-danger-700 shrink-0" />
              : <CheckCircle2 className="w-6 h-6 text-ok-700 shrink-0" />}
            <div>
              <p className="font-semibold text-ink-900">{result.message}</p>
              <p className={`text-sm mt-1 ${result.maintenance_alert ? "text-danger-700" : "text-ok-700"}`}>
                {result.maintenance_alert
                  ? "Critical maintenance alert triggered — a work order was opened and the instrument is booking-blocked. Check Analytics → Maintenance."
                  : "Report logged successfully. No anomalies were flagged."}
              </p>
            </div>
          </div>
        )}
      </PageBody>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-[11px] font-semibold tracking-wide text-ink-500 uppercase mb-1">{label}</span>
      {children}
    </label>
  );
}
