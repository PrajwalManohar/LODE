import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Database } from "lucide-react";
import { api } from "../lib/api";
import { PageBody, PageHeader } from "../components/PageShell";

export default function Admin() {
  const qc = useQueryClient();
  const { data: rag } = useQuery({ queryKey: ["rag"], queryFn: api.rag });
  const { data: runs = [] } = useQuery({ queryKey: ["runs"], queryFn: api.runs });

  const reindex = useMutation({
    mutationFn: api.reindex,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rag"] });
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });

  return (
    <>
      <PageHeader
        title="Knowledge base"
        actions={
          <button onClick={() => reindex.mutate()} disabled={reindex.isPending} className="btn-primary">
            <RefreshCw className={`w-4 h-4 ${reindex.isPending ? "animate-spin" : ""}`} /> Re-index corpus
          </button>
        }
      />
      <PageBody>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Tile label="Total chunks" value={rag?.total_chunks ?? 0} icon={<Database className="w-4 h-4 text-ink-600" />} />
          <Tile label="Indexed docs" value={rag?.documents?.length ?? 0} />
          <Tile label="Run logs"     value={runs.length} />
          <Tile label="Last update"  value={rag?.last_update ? new Date(rag.last_update).toLocaleDateString() : "—"} />
        </div>

        <section className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-ink-200">
            <h2 className="text-[15px] font-semibold">Historical run logs (searchable via RAG)</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-ink-50 border-b border-ink-200">
              <tr className="text-left text-[11px] tracking-wider font-semibold uppercase text-ink-500">
                <th className="px-5 py-3">Material</th>
                <th className="px-5 py-3">Instrument</th>
                <th className="px-5 py-3">Parameters</th>
                <th className="px-5 py-3">Quality</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-200">
              {runs.slice(0, 20).map((r) => (
                <tr key={String(r.id)} className="hover:bg-ink-50">
                  <td className="px-5 py-3 font-medium text-ink-900">{String(r.material_type)}</td>
                  <td className="px-5 py-3 font-mono text-xs text-ink-600">{String(r.instrument_id)}</td>
                  <td className="px-5 py-3 text-ink-500 max-w-md truncate">{String(r.parameters)}</td>
                  <td className="px-5 py-3">{String(r.quality_rating)}/5</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <div className="card-pad border-l-4 border-l-gold-500">
          <h3 className="font-semibold text-ink-900">RAG feedback loop</h3>
          <p className="text-sm text-ink-600 mt-1">
            Post-run reports (Agent 5) re-index into ChromaDB so the next researcher asking
            “has anyone run chalcopyrite on the XRD?” retrieves this lab’s actual parameters.
          </p>
        </div>
      </PageBody>
    </>
  );
}

function Tile({ label, value, icon }: { label: string; value: number | string; icon?: React.ReactNode }) {
  return (
    <div className="card-pad">
      <div className="flex items-center gap-2">
        {icon}
        <p className="text-sm text-ink-500">{label}</p>
      </div>
      <p className="text-[24px] font-bold text-ink-900 mt-2 leading-none tabular-nums">{value}</p>
    </div>
  );
}
