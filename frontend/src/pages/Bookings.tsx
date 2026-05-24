import { useQuery } from "@tanstack/react-query";
import { CalendarDays, FileDown } from "lucide-react";
import { api } from "../lib/api";
import { PageBody, PageHeader } from "../components/PageShell";

export default function Bookings() {
  const { data: bookings = [], isLoading } = useQuery({ queryKey: ["bookings"], queryFn: api.bookings });

  return (
    <>
      <PageHeader title="Schedule" />
      <PageBody>
        {isLoading ? (
          <p className="text-sm text-ink-500">Loading…</p>
        ) : bookings.length === 0 ? (
          <div className="card-pad text-center py-16">
            <CalendarDays className="w-10 h-10 text-ink-300 mx-auto" />
            <p className="text-ink-500 mt-3 text-sm">
              No bookings yet — complete an experiment intake to schedule.
            </p>
          </div>
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-ink-50 border-b border-ink-200">
                <tr className="text-left text-[11px] tracking-wider font-semibold uppercase text-ink-500">
                  <th className="px-5 py-3">Instrument</th>
                  <th className="px-5 py-3">Researcher</th>
                  <th className="px-5 py-3">Start</th>
                  <th className="px-5 py-3">End</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3 text-right">SOP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-200">
                {bookings.map((b) => (
                  <tr key={String(b.id)} className="hover:bg-ink-50">
                    <td className="px-5 py-3 font-medium text-ink-900">{String(b.instrument_name ?? b.instrument_id)}</td>
                    <td className="px-5 py-3 text-ink-700">{String(b.researcher_name ?? "—")}</td>
                    <td className="px-5 py-3 text-ink-700">{new Date(String(b.start_time)).toLocaleString()}</td>
                    <td className="px-5 py-3 text-ink-700">{new Date(String(b.end_time)).toLocaleString()}</td>
                    <td className="px-5 py-3"><span className="pill-ok">{String(b.status)}</span></td>
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </PageBody>
    </>
  );
}
