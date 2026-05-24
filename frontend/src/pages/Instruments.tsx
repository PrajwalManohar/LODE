import { useQuery } from "@tanstack/react-query";
import { MapPin, Clock, Shield, FlaskConical } from "lucide-react";
import { api } from "../lib/api";
import { PageBody, PageHeader } from "../components/PageShell";

export default function Instruments() {
  const { data: instruments = [], isLoading } = useQuery({ queryKey: ["instruments"], queryFn: api.instruments });
  return (
    <>
      <PageHeader title="Instruments" />
      <PageBody>
        {isLoading ? (
          <p className="text-sm text-ink-500">Loading…</p>
        ) : (
          <div className="grid md:grid-cols-2 gap-5">
            {instruments.map((inst) => (
              <article key={inst.id} className="card-pad">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-md bg-ink-100 flex items-center justify-center">
                      <FlaskConical className="w-4 h-4 text-ink-600" />
                    </div>
                    <div>
                      <span className="pill-muted">{inst.type}</span>
                      <h3 className="text-[15px] font-semibold mt-1 leading-tight">{inst.name}</h3>
                      <p className="text-xs text-ink-500">{inst.manufacturer} {inst.model}</p>
                    </div>
                  </div>
                  <span className={inst.status === "operational" ? "pill-ok" : "pill-warn"}>{inst.status}</span>
                </div>
                <ul className="mt-4 grid grid-cols-1 gap-2 text-sm text-ink-700">
                  <li className="flex items-center gap-2"><MapPin className="w-3.5 h-3.5 text-ink-400" /> {inst.location}</li>
                  <li className="flex items-center gap-2"><Clock className="w-3.5 h-3.5 text-ink-400" /> Warm-up {inst.warmup_minutes} min</li>
                  <li className="flex items-center gap-2"><Shield className="w-3.5 h-3.5 text-ink-400" /> {inst.required_training}</li>
                </ul>
              </article>
            ))}
          </div>
        )}
      </PageBody>
    </>
  );
}
