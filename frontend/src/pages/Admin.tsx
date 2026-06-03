import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Database, Search, Sparkles, FileText, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { PageBody, PageHeader } from "../components/PageShell";

export default function Admin() {
  const qc = useQueryClient();
  const { data: rag } = useQuery({ queryKey: ["rag"], queryFn: api.rag });
  const { data: runs = [] } = useQuery({ queryKey: ["runs"], queryFn: api.runs });
  const { data: inv } = useQuery({ queryKey: ["rag-inventory"], queryFn: api.ragInventory });

  const reindex = useMutation({
    mutationFn: api.reindex,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rag"] });
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: ["rag-inventory"] });
    },
  });

  return (
    <>
      <PageHeader
        title="Knowledge base"
        subtitle="What the RAG retriever is indexed on, and a live semantic-search demo."
        actions={
          <button onClick={() => reindex.mutate()} disabled={reindex.isPending} className="btn-primary">
            <RefreshCw className={`w-4 h-4 ${reindex.isPending ? "animate-spin" : ""}`} /> Re-index corpus
          </button>
        }
      />
      <PageBody>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Tile label="Total chunks" value={inv?.total_chunks ?? rag?.total_chunks ?? 0} icon={<Database className="w-4 h-4 text-ink-600" />} />
          <Tile label="Embedding model" value={inv?.embedding_model ?? "all-MiniLM-L6-v2"} />
          <Tile label="Vector dims" value={inv?.vector_dims ?? 384} />
          <Tile label="Run logs" value={runs.length} />
        </div>

        {/* Live semantic search — the demoable RAG path */}
        <RagSearchPanel />

        {/* Corpus inventory — what it is "trained" (retrieved) against */}
        {inv && (
          <section className="card overflow-hidden">
            <div className="card-header">
              <h2 className="text-[15px] font-semibold flex items-center gap-2">
                <FileText className="w-4 h-4 text-navy-700" /> Corpus inventory — source documents
              </h2>
              <div className="flex flex-wrap gap-1.5">
                {inv.by_type.map((t) => (
                  <span key={t.corpus_type} className="pill-muted text-[11px]">
                    {t.corpus_type} · {t.chunks}
                  </span>
                ))}
              </div>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-ink-50 border-b border-ink-200">
                <tr className="text-left text-[11px] tracking-wider font-semibold uppercase text-ink-500">
                  <th className="px-5 py-3">Source document</th>
                  <th className="px-5 py-3">Type</th>
                  <th className="px-5 py-3">Instrument</th>
                  <th className="px-5 py-3 text-right">Chunks</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-200">
                {inv.by_source.map((s, i) => (
                  <tr key={i} className="hover:bg-ink-50">
                    <td className="px-5 py-2.5 font-medium text-ink-900">{s.source}</td>
                    <td className="px-5 py-2.5"><span className="pill-muted text-[11px]">{s.corpus_type}</span></td>
                    <td className="px-5 py-2.5 font-mono text-xs text-ink-500">{s.instrument_id || "—"}</td>
                    <td className="px-5 py-2.5 text-right tabular-nums text-ink-700">{s.chunks}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        <section className="card overflow-hidden">
          <div className="card-header">
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

const SAMPLE_QUERIES = [
  "how do I image a fracture surface on uncoated steel?",
  "trace metals in mine drainage water",
  "phase identification of chalcopyrite",
  "what PPE is required for X-ray instruments?",
  "carbon coating procedure before SEM",
];

function RagSearchPanel() {
  const [q, setQ] = useState(SAMPLE_QUERIES[0]);
  const search = useMutation({
    mutationFn: (query: string) => api.ragSearch(query, { k: 5 }),
  });

  return (
    <section className="card overflow-hidden">
      <div className="card-header">
        <h2 className="text-[15px] font-semibold flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-gold-600" /> Live semantic search (RAG retrieval)
        </h2>
        <span className="pill-info text-[11px]">pgvector · cosine similarity</span>
      </div>
      <div className="px-5 py-4 space-y-3">
        <p className="text-xs text-ink-500">
          Embeds your text with <span className="font-mono">all-MiniLM-L6-v2</span> (384-dim) and runs the
          <span className="font-mono"> match_documents()</span> cosine search — the exact chunks the agents receive.
        </p>
        <div className="flex flex-wrap gap-1.5">
          {SAMPLE_QUERIES.map((s) => (
            <button key={s} onClick={() => setQ(s)}
              className="text-[11px] px-2.5 py-1 rounded-full bg-ink-100 hover:bg-ink-200 text-ink-700 font-medium">
              {s.length > 38 ? s.slice(0, 38) + "…" : s}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && q.trim()) search.mutate(q); }}
            placeholder="Ask the knowledge base anything…"
            className="input flex-1"
          />
          <button onClick={() => q.trim() && search.mutate(q)} disabled={search.isPending}
            className="btn-primary shrink-0">
            {search.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            Search
          </button>
        </div>

        {search.data && (
          <ul className="space-y-2 pt-1">
            {search.data.results.map((r, i) => (
              <li key={i} className="rounded-lg border border-ink-200 p-3">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-xs font-mono font-semibold text-navy-700 w-14 shrink-0">
                    {(r.similarity * 100).toFixed(1)}%
                  </span>
                  <div className="h-2 flex-1 rounded-full bg-ink-100 overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-navy-500 to-gold-500"
                      style={{ width: `${Math.max(3, Math.min(100, r.similarity * 100))}%` }} />
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-wrap text-[11px] text-ink-500 mb-1">
                  <span className="font-semibold text-ink-800">{r.source}</span>
                  {r.section && <span className="pill-muted">{r.section}</span>}
                  <span className="pill-muted">{r.corpus_type}</span>
                  {r.instrument_id && <span className="pill-muted">{r.instrument_id}</span>}
                </div>
                <p className="text-xs text-ink-700 leading-relaxed">{r.text}</p>
              </li>
            ))}
            {search.data.results.length === 0 && (
              <li className="text-sm text-ink-500">No chunks matched.</li>
            )}
          </ul>
        )}
        {search.isError && (
          <p className="text-xs text-danger-700">Search failed: {(search.error as Error).message}</p>
        )}
      </div>
    </section>
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
