import { useState } from "react";
import clsx from "clsx";
import type { Citation } from "../lib/api";

function shortSource(s: string): string {
  if (!s) return "source";
  return s.length > 32 ? s.slice(0, 30) + "…" : s;
}

function firstToken(section: string): string {
  return section.split(/\s+/)[0];
}

/**
 * Renders RAG citations as clickable chips. Clicking a chip reveals the full
 * reference (source · section · page) and the exact retrieved passage, so the
 * researcher can see where a recommendation came from — not just a label.
 */
export function Citations({
  citations,
  label = "RAG sources retrieved:",
}: {
  citations: Citation[];
  label?: string;
}) {
  const [open, setOpen] = useState<number | null>(null);
  if (!citations?.length) return null;
  const active = open !== null ? citations[open] : null;

  return (
    <div>
      {label && <p className="text-[11px] font-semibold text-ink-500 mb-2">{label}</p>}
      <div className="flex flex-wrap gap-1.5">
        {citations.map((c, i) => (
          <button
            key={i}
            type="button"
            onClick={() => setOpen(open === i ? null : i)}
            title="View source passage"
            className={clsx(
              "pill-cite cursor-pointer transition hover:brightness-95",
              open === i && "ring-1 ring-info-500"
            )}
          >
            📄 {shortSource(c.source)}
            {c.section ? ` §${firstToken(c.section)}` : ""}
            {c.page ? `, p.${c.page}` : ""}
          </button>
        ))}
      </div>

      {active && (
        <div className="mt-2 rounded-lg border border-info-600/30 bg-info-50/50 px-3 py-2.5">
          <p className="text-[11px] font-semibold text-info-700">
            {active.source}
            {active.section ? ` · ${active.section}` : ""}
            {active.page ? ` · p.${active.page}` : ""}
          </p>
          {active.excerpt ? (
            <p className="text-xs text-ink-700 mt-1.5 leading-relaxed border-l-2 border-info-400 pl-2 italic">
              “{active.excerpt}”
            </p>
          ) : (
            <p className="text-xs text-ink-400 mt-1.5 italic">No excerpt available.</p>
          )}
        </div>
      )}
    </div>
  );
}
