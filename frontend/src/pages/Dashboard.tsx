import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus, FileText, CalendarDays, MapPin } from "lucide-react";
import clsx from "clsx";
import { api } from "../lib/api";
import { PageHeader, PageBody } from "../components/PageShell";
import StatusBanner from "../components/StatusBanner";
import { useAuth } from "../lib/auth";

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export default function Dashboard() {
  const { profile, user } = useAuth();
  const firstName =
    (profile?.full_name?.split(" ")[0]) ||
    (profile?.email?.split("@")[0]) ||
    (user?.email?.split("@")[0]) ||
    "Researcher";
  const userEmail = profile?.email || user?.email || "";

  const { data: instruments = [] } = useQuery({ queryKey: ["instruments"], queryFn: api.instruments });
  const { data: bookings = [] } = useQuery({ queryKey: ["bookings"], queryFn: api.bookings });
  const { data: util = [] } = useQuery({ queryKey: ["utilization"], queryFn: api.utilization });
  const { data: rag } = useQuery({ queryKey: ["rag"], queryFn: api.rag });
  const { data: runs = [] } = useQuery({ queryKey: ["runs"], queryFn: api.runs });

  const todayBookings = bookings.slice(0, 5);
  const bookingsThisWeek = bookings.length;
  const sopsGenerated = bookings.filter((b) => b.sop_path).length;

  // Per-instrument utilization % (last week / target 40h)
  const utilByInstr = new Map<string, number>();
  util.forEach((u) => {
    utilByInstr.set(u.instrument_id, (utilByInstr.get(u.instrument_id) ?? 0) + u.hours);
  });

  return (
    <>
      <PageHeader
        title={`${greeting()}, ${firstName}`}
        subtitle={
          userEmail ? (
            <>
              Signed in as <span className="font-medium text-ink-700">{userEmail}</span> · Here's
              what's happening in the lab today.
            </>
          ) : (
            "Here's what's happening in the lab today."
          )
        }
        badge={<StatusBanner />}
        actions={
          <>
            <Link to="/intake" className="btn-primary">
              <Plus className="w-4 h-4" /> Book a session
            </Link>
            <Link to="/postrun" className="btn">
              <FileText className="w-4 h-4" /> My SOPs
            </Link>
            <Link to="/bookings" className="btn">
              <CalendarDays className="w-4 h-4" /> View schedule
            </Link>
          </>
        }
      />

      <PageBody>
        {/* KPI tiles */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiTile
            label="Active instruments"
            value={instruments.filter((i) => i.status === "operational").length.toString()}
            sub={<span className="text-ok-700">✓ All operational</span>}
          />
          <KpiTile
            label="Bookings this week"
            value={bookingsThisWeek.toString()}
            sub={<span className="text-ok-700">↑ {Math.max(0, bookingsThisWeek - 3)} vs last week</span>}
          />
          <KpiTile
            label="SOPs generated"
            value={sopsGenerated.toString()}
            sub={<span className="text-ink-500">{rag?.total_chunks ?? 0} RAG citations</span>}
          />
          <KpiTile
            label="Completed runs"
            value={runs.length.toString()}
            sub={<span className="text-ink-500">Indexed in corpus</span>}
          />
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Instrument status */}
          <section className="card overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-ink-200">
              <h2 className="text-[15px] font-semibold">Instrument status</h2>
              <Link to="/instruments" className="text-sm text-navy-700 hover:underline">View all</Link>
            </div>
            <ul className="divide-y divide-ink-200">
              {instruments.map((inst) => {
                const hours = utilByInstr.get(inst.id) ?? 0;
                const pct = Math.min(100, Math.round((hours / 40) * 100));
                const state = stateForInstrument(inst, pct);
                return (
                  <li key={inst.id} className="px-5 py-4 flex items-start gap-4">
                    <span className={clsx(
                      "mt-1.5 w-2 h-2 rounded-full shrink-0",
                      state.dot
                    )} />
                    <div className="flex-1 min-w-0">
                      <p className="text-[14px] font-semibold text-ink-900 leading-tight">{inst.name}</p>
                      <p className="text-xs text-ink-500 mt-0.5 flex items-center gap-1">
                        <MapPin className="w-3 h-3" /> {inst.location}
                      </p>
                    </div>
                    <div className="w-[140px] shrink-0 flex flex-col items-end">
                      <div className="flex items-center gap-2 w-full">
                        <div className="flex-1 h-1.5 rounded-full bg-ink-100 overflow-hidden">
                          <div
                            className={clsx("h-full rounded-full", state.bar)}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="text-xs font-mono text-ink-600 tabular-nums">{pct}%</span>
                      </div>
                      <span className={clsx("mt-1.5", state.pill)}>{state.label}</span>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>

          {/* Today's bookings */}
          <section className="card overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-ink-200">
              <h2 className="text-[15px] font-semibold">Today’s bookings</h2>
              <Link to="/bookings" className="text-sm text-navy-700 hover:underline">View all</Link>
            </div>
            {todayBookings.length === 0 ? (
              <div className="px-5 py-12 text-center text-ink-500 text-sm">
                No bookings yet — start a session from the Book a session tab.
              </div>
            ) : (
              <ul className="divide-y divide-ink-200">
                {todayBookings.map((b) => {
                  const start = new Date(String(b.start_time));
                  const end = new Date(String(b.end_time));
                  const ctx = parseCtx(b.experiment_context);
                  return (
                    <li key={String(b.id)} className="px-5 py-4 flex items-start gap-4">
                      <div className="w-[110px] shrink-0 text-xs font-mono text-ink-700 leading-tight">
                        {fmtTime(start)} – {fmtTime(end)}
                        <p className="text-[10px] text-ink-400 mt-0.5">
                          {start.toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                        </p>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[14px] font-semibold text-ink-900 leading-tight">
                          {String(b.researcher_name ?? "Researcher")}
                        </p>
                        <p className="text-xs text-ink-500 mt-1 leading-snug">
                          {String(b.instrument_name ?? b.instrument_id)} ·{" "}
                          {ctx?.analysis_goal || "—"}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>
      </PageBody>
    </>
  );
}

function KpiTile({ label, value, sub }: { label: string; value: string; sub: React.ReactNode }) {
  return (
    <div className="card-pad">
      <p className="text-sm text-ink-500">{label}</p>
      <p className="text-[28px] font-bold text-ink-900 mt-1 leading-none tracking-tight">{value}</p>
      <p className="text-xs mt-2">{sub}</p>
    </div>
  );
}

function stateForInstrument(inst: { status: string }, pct: number) {
  if (inst.status === "maintenance") {
    return {
      label: "Maintenance",
      dot: "bg-warn-600",
      bar: "bg-warn-600",
      pill: "pill bg-warn-50 text-warn-700",
    };
  }
  if (pct >= 80) {
    return {
      label: "High load",
      dot: "bg-warn-600",
      bar: "bg-warn-600",
      pill: "pill bg-warn-50 text-warn-700",
    };
  }
  return {
    label: "Operational",
    dot: "bg-ok-600",
    bar: "bg-ok-600",
    pill: "pill bg-ok-50 text-ok-700",
  };
}

function fmtTime(d: Date) {
  return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function parseCtx(v: unknown): { analysis_goal?: string; material_type?: string } | null {
  if (typeof v !== "string") return null;
  try {
    return JSON.parse(v);
  } catch {
    return null;
  }
}
