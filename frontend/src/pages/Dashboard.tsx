import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Plus, FileText, CalendarDays, MapPin, Megaphone, ExternalLink,
  Lightbulb, Sparkles, FlaskConical, Users, Bell, ShieldCheck,
  ChevronDown, FileDown, GraduationCap, Activity, ListChecks,
} from "lucide-react";
import clsx from "clsx";
import { api } from "../lib/api";
import { PageHeader, PageBody } from "../components/PageShell";
import StatusBanner from "../components/StatusBanner";
import { useAuth } from "../lib/auth";

type TileKey = "instruments" | "bookings" | "sops" | "trainings";

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

type Booking = Record<string, unknown>;

export default function Dashboard() {
  const { profile, user, isAdmin } = useAuth();
  const firstName =
    (profile?.full_name?.split(" ")[0]) ||
    (profile?.email?.split("@")[0]) ||
    (user?.email?.split("@")[0]) ||
    "Researcher";
  const userEmail = profile?.email || user?.email || "";

  const { data: instruments = [] } = useQuery({ queryKey: ["instruments"], queryFn: api.instruments });
  const { data: rag } = useQuery({ queryKey: ["rag"], queryFn: api.rag });
  const { data: feed } = useQuery({ queryKey: ["notifications"], queryFn: api.notifications });

  // Admins see the whole facility; everyone else only ever sees their own data.
  const { data: allBookings = [] } = useQuery({
    queryKey: ["bookings"], queryFn: api.bookings, enabled: isAdmin,
  });
  const { data: myBookings = [] } = useQuery({
    queryKey: ["my-bookings", userEmail], queryFn: () => api.myBookings(userEmail),
    enabled: !isAdmin && !!userEmail,
  });
  const { data: labDay = [] } = useQuery({
    queryKey: ["lab-day", userEmail], queryFn: () => api.labDay(userEmail),
    enabled: !isAdmin && !!userEmail,
  });
  const { data: util = [] } = useQuery({ queryKey: ["utilization"], queryFn: api.utilization, enabled: isAdmin });
  const { data: runs = [] } = useQuery({ queryKey: ["runs"], queryFn: api.runs, enabled: isAdmin });

  const myList = (isAdmin ? allBookings : myBookings) as Booking[];
  const sopsGenerated = myList.filter((b) => b.sop_path).length;
  const myUpcoming = myList.filter((b) => isFuture(b.start_time)).length;

  const utilByInstr = new Map<string, number>();
  util.forEach((u) => utilByInstr.set(u.instrument_id, (utilByInstr.get(u.instrument_id) ?? 0) + u.hours));

  const [activeTile, setActiveTile] = useState<TileKey | null>(null);
  const toggleTile = (k: TileKey) => setActiveTile((cur) => (cur === k ? null : k));

  return (
    <>
      <PageHeader
        title={`${greeting()}, ${firstName}`}
        subtitle={
          userEmail ? (
            <>
              Signed in as <span className="font-medium text-ink-700">{userEmail}</span>
              {isAdmin && <span className="ml-2 pill-info">Admin</span>}
            </>
          ) : ("Here's what's happening in the lab today.")
        }
        badge={<StatusBanner />}
        actions={
          <>
            <Link to="/intake" className="btn-primary"><Plus className="w-4 h-4" /> Book a session</Link>
            <Link to="/postrun" className="btn"><FileText className="w-4 h-4" /> Post-run report</Link>
            <Link to="/requests" className="btn"><CalendarDays className="w-4 h-4" /> My Requests</Link>
          </>
        }
      />

      <PageBody>
        {/* KPI tiles — role-scoped, click to expand a per-tile breakdown */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiTile tileKey="instruments" active={activeTile === "instruments"} onClick={toggleTile}
            label="Active instruments"
            value={instruments.filter((i) => i.status === "operational").length.toString()}
            sub={<span className="text-ink-500">{instruments.length} in the facility</span>} />
          <KpiTile tileKey="bookings" active={activeTile === "bookings"} onClick={toggleTile}
            label={isAdmin ? "Total bookings" : "My bookings"} value={myList.length.toString()}
            sub={<span className="text-ok-700">{myUpcoming} upcoming</span>} />
          <KpiTile tileKey="sops" active={activeTile === "sops"} onClick={toggleTile}
            label={isAdmin ? "SOPs generated" : "My SOPs"} value={sopsGenerated.toString()}
            sub={<span className="text-ink-500">{rag?.total_chunks ?? 0} RAG citations</span>} />
          <KpiTile tileKey="trainings" active={activeTile === "trainings"} onClick={toggleTile}
            label={isAdmin ? "Completed runs" : "My trainings"}
            value={(isAdmin ? runs.length : (profile?.trained_instruments?.length ?? 0)).toString()}
            sub={<span className="text-ink-500">{isAdmin ? "Indexed in corpus" : "Certifications on file"}</span>} />
        </div>

        {/* Breakdown panel — appears below the active tile */}
        {activeTile === "instruments" && (
          <InstrumentsBreakdown instruments={instruments} utilByInstr={utilByInstr} onClose={() => setActiveTile(null)} />
        )}
        {activeTile === "bookings" && (
          <BookingsBreakdown bookings={myList} isAdmin={isAdmin} onClose={() => setActiveTile(null)} />
        )}
        {activeTile === "sops" && (
          <SopsBreakdown bookings={myList} onClose={() => setActiveTile(null)} />
        )}
        {activeTile === "trainings" && (
          <TrainingsBreakdown isAdmin={isAdmin}
            trained={profile?.trained_instruments ?? []}
            runs={runs as Record<string, unknown>[]}
            onClose={() => setActiveTile(null)} />
        )}

        {/* Instrument status + bookings — primary working surface, kept near the top */}
        <div className="grid lg:grid-cols-2 gap-6">
          {/* Instrument status — public */}
          <section className="card overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-ink-200">
              <h2 className="text-[15px] font-semibold">Instrument status</h2>
              <Link to="/instruments" className="text-sm text-navy-700 hover:underline">View all</Link>
            </div>
            <ul className="divide-y divide-ink-200 max-h-[420px] overflow-y-auto">
              {instruments.map((inst) => {
                const hours = utilByInstr.get(inst.id) ?? 0;
                const pct = Math.min(100, Math.round((hours / 40) * 100));
                const state = stateForInstrument(inst, pct);
                return (
                  <li key={inst.id} className="px-5 py-3.5 flex items-start gap-4">
                    <span className={clsx("mt-1.5 w-2 h-2 rounded-full shrink-0", state.dot)} />
                    <div className="flex-1 min-w-0">
                      <p className="text-[14px] font-semibold text-ink-900 leading-tight truncate">{inst.name}</p>
                      <p className="text-xs text-ink-500 mt-0.5 flex items-center gap-1">
                        <MapPin className="w-3 h-3" /> {inst.location}
                      </p>
                    </div>
                    <span className={clsx("mt-0.5 shrink-0", state.pill)}>{state.label}</span>
                  </li>
                );
              })}
            </ul>
          </section>

          {/* Bookings — role-scoped */}
          {isAdmin ? (
            <BookingCard title="Today's bookings (facility-wide)" to="/bookings"
              bookings={(allBookings as Booking[]).filter((b) => isToday(b.start_time))}
              emptyText="No bookings scheduled for today." showResearcher />
          ) : (
            <div className="space-y-6">
              <BookingCard title="My bookings" to="/requests"
                bookings={(myBookings as Booking[])}
                emptyText="You have no bookings yet — start one from Book a session." />
              <section className="card overflow-hidden">
                <div className="flex items-center justify-between px-5 py-4 border-b border-ink-200">
                  <h2 className="text-[15px] font-semibold flex items-center gap-2">
                    <Users className="w-4 h-4 text-navy-600" /> Today in your lab
                  </h2>
                </div>
                {(labDay as Booking[]).length === 0 ? (
                  <div className="px-5 py-8 text-center text-ink-500 text-sm">
                    No other sessions today at the labs where you have a booking.
                  </div>
                ) : (
                  <ul className="divide-y divide-ink-200">
                    {(labDay as Booking[]).map((b) => (
                      <BookingRow key={String(b.id)} b={b} showResearcher showLocation />
                    ))}
                  </ul>
                )}
              </section>
            </div>
          )}
        </div>

        {/* Campus & Facility — engaging, AI-digested, all users (moved below the working surface) */}
        {feed && (
          <section className="card overflow-hidden">
            <div className="px-5 py-4 border-b border-ink-200 flex items-center justify-between gap-2">
              <h2 className="font-display text-[15px] font-semibold flex items-center gap-2">
                <Megaphone className="w-4 h-4 text-gold-600" /> Campus &amp; facility
              </h2>
              <span className="pill-info inline-flex items-center gap-1">
                <Sparkles className="w-3 h-3" /> AI daily digest
              </span>
            </div>

            {/* AI digest banner */}
            <div className="px-5 py-4 bg-gradient-to-r from-navy-50 to-gold-50/40 border-b border-ink-100">
              <p className="text-sm text-ink-800 leading-relaxed">{feed.digest}</p>
            </div>

            <div className="grid lg:grid-cols-3 gap-0 divide-y lg:divide-y-0 lg:divide-x divide-ink-200">
              {/* Announcements / news */}
              <div className="p-5 lg:col-span-2">
                <p className="text-[10px] font-bold tracking-[0.16em] text-ink-500 uppercase mb-3 flex items-center gap-1.5">
                  <Bell className="w-3.5 h-3.5" /> Announcements &amp; news
                </p>
                <ul className="space-y-3">
                  {feed.announcements.map((a, i) => (
                    <li key={i} className="group">
                      <a href={a.url} target="_blank" rel="noreferrer"
                         className="block rounded-lg border border-ink-200 px-3 py-2.5 hover:border-navy-400 hover:bg-ink-50/60 transition">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="pill-muted text-[10px]">{a.tag}</span>
                          {a.date && <span className="text-[10px] text-ink-400">{a.date}</span>}
                          <ExternalLink className="w-3 h-3 text-ink-300 ml-auto group-hover:text-navy-600" />
                        </div>
                        <p className="text-sm font-semibold text-ink-900 mt-1 leading-snug">{a.title}</p>
                        <p className="text-xs text-ink-600 mt-0.5 leading-snug">{a.body}</p>
                      </a>
                    </li>
                  ))}
                </ul>
                <p className="text-[10px] text-ink-400 mt-3">Source: {feed.source}</p>
              </div>

              {/* Circulars + facts + research */}
              <div className="p-5 space-y-5">
                <div>
                  <p className="text-[10px] font-bold tracking-[0.16em] text-ink-500 uppercase mb-2 flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5" /> Facility circulars
                  </p>
                  <ul className="space-y-2">
                    {feed.circulars.map((c, i) => (
                      <li key={i} className="text-xs">
                        <a href={c.url} target="_blank" rel="noreferrer" className="font-semibold text-ink-800 hover:text-navy-700 hover:underline">
                          {c.title}
                        </a>
                        <p className="text-ink-500 leading-snug">{c.body}</p>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-[10px] font-bold tracking-[0.16em] text-ink-500 uppercase mb-2 flex items-center gap-1.5">
                    <Lightbulb className="w-3.5 h-3.5" /> Did you know?
                  </p>
                  <ul className="space-y-1.5">
                    {feed.facts.slice(0, 3).map((f, i) => (
                      <li key={i} className="text-xs text-ink-600 flex items-start gap-1.5">
                        <span className="text-gold-600 mt-0.5">◆</span><span>{f}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-[10px] font-bold tracking-[0.16em] text-ink-500 uppercase mb-2 flex items-center gap-1.5">
                    <FlaskConical className="w-3.5 h-3.5" /> Research themes
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {feed.research_themes.map((r, i) => (
                      <span key={i} className="pill-muted text-[11px]" title={r.detail}>{r.theme}</span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}
      </PageBody>
    </>
  );
}

function BookingCard({
  title, to, bookings, emptyText, showResearcher,
}: {
  title: string; to: string; bookings: Booking[]; emptyText: string; showResearcher?: boolean;
}) {
  return (
    <section className="card overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-ink-200">
        <h2 className="text-[15px] font-semibold">{title}</h2>
        <Link to={to} className="text-sm text-navy-700 hover:underline">View all</Link>
      </div>
      {bookings.length === 0 ? (
        <div className="px-5 py-12 text-center text-ink-500 text-sm">{emptyText}</div>
      ) : (
        <ul className="divide-y divide-ink-200 max-h-[420px] overflow-y-auto">
          {bookings.slice(0, 6).map((b) => (
            <BookingRow key={String(b.id)} b={b} showResearcher={showResearcher} />
          ))}
        </ul>
      )}
    </section>
  );
}

function BookingRow({ b, showResearcher, showLocation }: { b: Booking; showResearcher?: boolean; showLocation?: boolean }) {
  const start = new Date(String(b.start_time));
  const end = new Date(String(b.end_time));
  const ctx = parseCtx(b.experiment_context);
  return (
    <li className="px-5 py-3.5 flex items-start gap-4">
      <div className="w-[110px] shrink-0 text-xs font-mono text-ink-700 leading-tight">
        {fmtTime(start)} – {fmtTime(end)}
        <p className="text-[10px] text-ink-400 mt-0.5">
          {start.toLocaleDateString(undefined, { month: "short", day: "numeric" })}
        </p>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[14px] font-semibold text-ink-900 leading-tight truncate">
          {showResearcher ? String(b.researcher_name ?? "Researcher") : String(b.instrument_name ?? b.instrument_id)}
        </p>
        <p className="text-xs text-ink-500 mt-1 leading-snug truncate">
          {String(b.instrument_name ?? b.instrument_id)}
          {showLocation && b.instrument_location ? ` · ${String(b.instrument_location)}` : ""}
          {ctx?.analysis_goal ? ` · ${ctx.analysis_goal}` : ""}
        </p>
      </div>
    </li>
  );
}

function KpiTile({
  tileKey, label, value, sub, active, onClick,
}: {
  tileKey: TileKey;
  label: string;
  value: string;
  sub: React.ReactNode;
  active: boolean;
  onClick: (k: TileKey) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onClick(tileKey)}
      aria-expanded={active}
      aria-controls={`kpi-breakdown-${tileKey}`}
      className={clsx(
        "card-pad text-left transition relative w-full",
        "hover:border-navy-400 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-navy-500/40",
        active && "ring-2 ring-navy-700 border-navy-500",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm text-ink-500">{label}</p>
        <ChevronDown
          className={clsx(
            "w-4 h-4 text-ink-400 shrink-0 transition-transform",
            active && "rotate-180 text-navy-700",
          )}
        />
      </div>
      <p className="text-[28px] font-bold text-ink-900 mt-1 leading-none tracking-tight">{value}</p>
      <p className="text-xs mt-2">{sub}</p>
      <p className="text-[10px] text-ink-400 mt-1.5 tracking-wide uppercase">
        {active ? "Hide details" : "Click for breakdown"}
      </p>
    </button>
  );
}

// ============================================================================
// Tile breakdown panels
// ============================================================================
function BreakdownShell({
  id, title, icon, onClose, children,
}: {
  id: string;
  title: string;
  icon: React.ReactNode;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="card overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-ink-200 bg-ink-50/60">
        <h3 className="text-[14px] font-semibold flex items-center gap-2 text-ink-800">
          {icon} {title}
        </h3>
        <button
          type="button"
          onClick={onClose}
          className="text-xs text-ink-500 hover:text-ink-800"
        >
          Hide
        </button>
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function InstrumentsBreakdown({
  instruments, utilByInstr, onClose,
}: {
  instruments: Array<{ id: string; name: string; location: string; status: string }>;
  utilByInstr: Map<string, number>;
  onClose: () => void;
}) {
  const groups = { operational: [] as typeof instruments, highLoad: [] as typeof instruments, maintenance: [] as typeof instruments };
  instruments.forEach((inst) => {
    const hours = utilByInstr.get(inst.id) ?? 0;
    const pct = Math.min(100, Math.round((hours / 40) * 100));
    if (inst.status === "maintenance") groups.maintenance.push(inst);
    else if (pct >= 80) groups.highLoad.push(inst);
    else groups.operational.push(inst);
  });

  return (
    <BreakdownShell id="kpi-breakdown-instruments" title="Instrument status breakdown" icon={<Activity className="w-4 h-4 text-navy-700" />} onClose={onClose}>
      <div className="grid sm:grid-cols-3 gap-4">
        <BreakdownGroup label="Operational" tone="ok" count={groups.operational.length} items={groups.operational} />
        <BreakdownGroup label="High load" tone="warn" count={groups.highLoad.length} items={groups.highLoad} />
        <BreakdownGroup label="Maintenance" tone="danger" count={groups.maintenance.length} items={groups.maintenance} />
      </div>
      <Link to="/instruments" className="text-sm text-navy-700 hover:underline mt-4 inline-block">
        Open instruments page →
      </Link>
    </BreakdownShell>
  );
}

function BreakdownGroup({
  label, tone, count, items,
}: {
  label: string;
  tone: "ok" | "warn" | "danger";
  count: number;
  items: Array<{ id: string; name: string; location: string }>;
}) {
  const toneClass =
    tone === "ok" ? "text-ok-700 bg-ok-50 border-ok-200" :
    tone === "warn" ? "text-warn-700 bg-warn-50 border-warn-200" :
    "text-danger-700 bg-danger-50 border-danger-200";
  return (
    <div className="rounded-lg border border-ink-200">
      <div className={clsx("px-3 py-2 border-b border-ink-200 flex items-center justify-between", toneClass)}>
        <span className="text-xs font-semibold">{label}</span>
        <span className="text-xs font-mono tabular-nums">{count}</span>
      </div>
      {items.length === 0 ? (
        <p className="px-3 py-2 text-xs text-ink-400">None</p>
      ) : (
        <ul className="divide-y divide-ink-100">
          {items.map((it) => (
            <li key={it.id} className="px-3 py-2 text-xs">
              <p className="font-medium text-ink-900 truncate">{it.name}</p>
              <p className="text-ink-500 mt-0.5 flex items-center gap-1"><MapPin className="w-3 h-3" /> {it.location}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function BookingsBreakdown({
  bookings, isAdmin, onClose,
}: {
  bookings: Booking[];
  isAdmin: boolean;
  onClose: () => void;
}) {
  const upcoming = bookings.filter((b) => isFuture(b.start_time))
    .sort((a, b) => new Date(String(a.start_time)).getTime() - new Date(String(b.start_time)).getTime());
  const past = bookings.length - upcoming.length;
  const today = bookings.filter((b) => isToday(b.start_time)).length;
  const withSop = bookings.filter((b) => b.sop_path).length;

  return (
    <BreakdownShell id="kpi-breakdown-bookings" title={isAdmin ? "Facility booking breakdown" : "My booking breakdown"} icon={<CalendarDays className="w-4 h-4 text-navy-700" />} onClose={onClose}>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <MiniStat label="Upcoming" value={upcoming.length} tone="ok" />
        <MiniStat label="Today" value={today} tone="info" />
        <MiniStat label="Past" value={past} tone="neutral" />
        <MiniStat label="With SOP" value={withSop} tone="neutral" />
      </div>
      <p className="text-[11px] font-semibold tracking-wider text-ink-500 uppercase mb-2">Next {Math.min(5, upcoming.length)} upcoming</p>
      {upcoming.length === 0 ? (
        <p className="text-sm text-ink-500">No upcoming bookings.</p>
      ) : (
        <ul className="divide-y divide-ink-200 rounded-lg border border-ink-200">
          {upcoming.slice(0, 5).map((b) => (
            <BookingRow key={String(b.id)} b={b} showResearcher={isAdmin} />
          ))}
        </ul>
      )}
      <Link to={isAdmin ? "/bookings" : "/requests"} className="text-sm text-navy-700 hover:underline mt-4 inline-block">
        {isAdmin ? "Open bookings page" : "Open my requests"} →
      </Link>
    </BreakdownShell>
  );
}

function SopsBreakdown({
  bookings, onClose,
}: {
  bookings: Booking[];
  onClose: () => void;
}) {
  const withSop = bookings.filter((b) => b.sop_path)
    .sort((a, b) => new Date(String(b.start_time)).getTime() - new Date(String(a.start_time)).getTime());
  return (
    <BreakdownShell id="kpi-breakdown-sops" title="SOP documents" icon={<FileText className="w-4 h-4 text-navy-700" />} onClose={onClose}>
      {withSop.length === 0 ? (
        <p className="text-sm text-ink-500">No SOPs generated yet — book a session and they'll be created automatically.</p>
      ) : (
        <ul className="divide-y divide-ink-200 rounded-lg border border-ink-200">
          {withSop.slice(0, 8).map((b) => {
            const start = new Date(String(b.start_time));
            return (
              <li key={String(b.id)} className="px-4 py-3 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink-900 truncate">
                    {String(b.instrument_name ?? b.instrument_id)}
                  </p>
                  <p className="text-xs text-ink-500 mt-0.5">
                    {start.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}
                    {b.researcher_name ? ` · ${String(b.researcher_name)}` : ""}
                  </p>
                </div>
                <a
                  href={api.sopUrl(String(b.sop_path))}
                  download
                  className="btn shrink-0 text-xs"
                  title="Download generated SOP"
                >
                  <FileDown className="w-3.5 h-3.5" /> SOP
                </a>
              </li>
            );
          })}
        </ul>
      )}
    </BreakdownShell>
  );
}

function TrainingsBreakdown({
  isAdmin, trained, runs, onClose,
}: {
  isAdmin: boolean;
  trained: string[];
  runs: Record<string, unknown>[];
  onClose: () => void;
}) {
  if (isAdmin) {
    const recent = [...runs]
      .sort((a, b) => new Date(String(b.completed_at ?? b.created_at ?? 0)).getTime() - new Date(String(a.completed_at ?? a.created_at ?? 0)).getTime())
      .slice(0, 8);
    return (
      <BreakdownShell id="kpi-breakdown-trainings" title="Completed runs" icon={<ListChecks className="w-4 h-4 text-navy-700" />} onClose={onClose}>
        {runs.length === 0 ? (
          <p className="text-sm text-ink-500">No runs recorded yet.</p>
        ) : (
          <ul className="divide-y divide-ink-200 rounded-lg border border-ink-200">
            {recent.map((r, i) => (
              <li key={i} className="px-4 py-2.5 text-sm flex items-center justify-between gap-3">
                <span className="font-medium text-ink-900 truncate">
                  {String(r.instrument_name ?? r.instrument_id ?? "Run")}
                </span>
                <span className="text-xs text-ink-500 font-mono shrink-0">
                  {r.completed_at ? new Date(String(r.completed_at)).toLocaleDateString() : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </BreakdownShell>
    );
  }
  return (
    <BreakdownShell id="kpi-breakdown-trainings" title="My trainings" icon={<GraduationCap className="w-4 h-4 text-navy-700" />} onClose={onClose}>
      {trained.length === 0 ? (
        <p className="text-sm text-ink-500">No instrument trainings on file yet. Contact the facility manager to record certifications.</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {trained.map((t, i) => (
            <span key={i} className="pill bg-navy-50 text-navy-700 border border-navy-200">{t}</span>
          ))}
        </div>
      )}
    </BreakdownShell>
  );
}

function MiniStat({ label, value, tone }: { label: string; value: number; tone: "ok" | "warn" | "danger" | "info" | "neutral" }) {
  const cls =
    tone === "ok" ? "text-ok-700" :
    tone === "warn" ? "text-warn-700" :
    tone === "danger" ? "text-danger-700" :
    tone === "info" ? "text-info-700" : "text-ink-800";
  return (
    <div className="rounded-lg border border-ink-200 px-3 py-2.5">
      <p className="text-[10px] font-semibold tracking-wider text-ink-500 uppercase">{label}</p>
      <p className={clsx("text-lg font-bold tabular-nums leading-none mt-1", cls)}>{value}</p>
    </div>
  );
}

function stateForInstrument(inst: { status: string }, pct: number) {
  if (inst.status === "maintenance")
    return { label: "Maintenance", dot: "bg-warn-600", pill: "pill bg-warn-50 text-warn-700" };
  if (pct >= 80)
    return { label: "High load", dot: "bg-warn-600", pill: "pill bg-warn-50 text-warn-700" };
  return { label: "Operational", dot: "bg-ok-600", pill: "pill bg-ok-50 text-ok-700" };
}

function fmtTime(d: Date) {
  return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function isToday(v: unknown): boolean {
  try { return new Date(String(v)).toDateString() === new Date().toDateString(); }
  catch { return false; }
}

function isFuture(v: unknown): boolean {
  try { return new Date(String(v)).getTime() >= Date.now(); }
  catch { return false; }
}

function parseCtx(v: unknown): { analysis_goal?: string; material_type?: string } | null {
  if (typeof v !== "string") return (v && typeof v === "object" ? (v as { analysis_goal?: string }) : null);
  try { return JSON.parse(v); } catch { return null; }
}
