import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, BookOpen, FileText, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { PageBody, PageHeader } from "../components/PageShell";

/**
 * RAG chunk browser. Reached from email/SOP citation deep-links like
 *   /knowledge?source=Bruker%20D8%20Advance%20Manual&section=5.1&page=89
 * Shows the matching chunks plus the rest of the chunks from the same source
 * so the reader gets context, not just the cited fragment.
 */
export default function Knowledge() {
  const [params] = useSearchParams();
  const source = params.get("source") || "";
  const section = params.get("section") || "";
  const page = params.get("page") || "";
  const instrument = params.get("instrument_id") || "";

  // 1) Exact-match query (what was cited)
  const exact = useQuery({
    queryKey: ["rag-chunks-exact", source, section, page, instrument],
    queryFn: () => api.ragChunks({ source, section, page, instrument_id: instrument }),
    enabled: !!source,
  });

  // 2) All chunks from the same source for context
  const sameSource = useQuery({
    queryKey: ["rag-chunks-source", source, instrument],
    queryFn: () => api.ragChunks({ source, instrument_id: instrument }),
    enabled: !!source,
  });

  const exactIds = useMemo(
    () => new Set((exact.data ?? []).map((c) => c.id)),
    [exact.data],
  );
  const others = (sameSource.data ?? []).filter((c) => !exactIds.has(c.id));

  if (!source) {
    return (
      <>
        <PageHeader title="Knowledge base" />
        <PageBody>
          <div className="card-pad text-sm text-ink-600">
            No source specified. Open a citation link from an SOP or an email to land on a
            specific section.
          </div>
        </PageBody>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={source}
        subtitle={
          section || page
            ? `Cited section: ${section}${page ? ` · p.${page}` : ""}`
            : "All chunks from this RAG source"
        }
        badge={
          <Link to=".." className="chip bg-ink-100 text-ink-700 inline-flex items-center gap-1.5">
            <ArrowLeft className="w-3.5 h-3.5" /> Back
          </Link>
        }
      />
      <PageBody>
        {(exact.isLoading || sameSource.isLoading) && (
          <div className="card-pad flex items-center gap-2 text-sm text-ink-500">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading RAG chunks…
          </div>
        )}

        {!exact.isLoading && (exact.data ?? []).length === 0 && (
          <div className="card-pad text-sm text-ink-600">
            <p className="font-semibold text-ink-900">No exact match for that section.</p>
            <p className="mt-1">
              The corpus may have been re-indexed since the SOP was generated, or the citation
              points to a section that doesn't exist in our knowledge base. Other chunks from the
              same source are shown below.
            </p>
          </div>
        )}

        {(exact.data ?? []).length > 0 && (
          <section className="card overflow-hidden">
            <header className="card-header">
              <BookOpen className="w-4 h-4 text-navy-700" />
              <h2 className="font-display text-[15px] font-semibold">
                Cited chunk{(exact.data ?? []).length > 1 ? "s" : ""}{" "}
                <span className="font-normal text-ink-500">
                  ({(exact.data ?? []).length})
                </span>
              </h2>
            </header>
            <ul className="divide-y divide-ink-200">
              {(exact.data ?? []).map((c) => (
                <ChunkRow key={c.id} c={c} highlighted />
              ))}
            </ul>
          </section>
        )}

        {others.length > 0 && (
          <section className="card overflow-hidden">
            <header className="card-header">
              <FileText className="w-4 h-4 text-ink-600" />
              <h2 className="font-display text-[15px] font-semibold">
                Other chunks from this source{" "}
                <span className="font-normal text-ink-500">({others.length})</span>
              </h2>
            </header>
            <ul className="divide-y divide-ink-200">
              {others.map((c) => (
                <ChunkRow key={c.id} c={c} />
              ))}
            </ul>
          </section>
        )}
      </PageBody>
    </>
  );
}

function ChunkRow({
  c, highlighted = false,
}: {
  c: { id: string; content: string; source: string; section: string; page: string; corpus_type: string; instrument_id: string };
  highlighted?: boolean;
}) {
  return (
    <li
      className={`px-5 py-4 ${highlighted ? "bg-gold-50/40" : ""}`}
    >
      <div className="flex items-center gap-2 flex-wrap text-xs text-ink-500 mb-2">
        {c.section && <span className="pill-muted">{c.section}</span>}
        {c.page && <span className="pill-muted">p.{c.page}</span>}
        {c.corpus_type && <span className="pill-muted">{c.corpus_type}</span>}
        {c.instrument_id && <span className="pill-muted">{c.instrument_id}</span>}
        <span className="font-mono text-ink-400 text-[10px]">{c.id}</span>
      </div>
      <p className="text-sm text-ink-800 leading-relaxed whitespace-pre-wrap">{c.content}</p>
    </li>
  );
}
