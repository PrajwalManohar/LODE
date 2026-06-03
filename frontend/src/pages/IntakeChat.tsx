import { useEffect, useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import {
  ArrowUp,
  Loader2,
  Lock,
  ShieldAlert,
  AlertTriangle,
  ArrowRight,
  ClipboardList,
  Shield,
} from "lucide-react";
import clsx from "clsx";
import { api, ChatResponse, ExperimentContext, Citation } from "../lib/api";
import { PageHeader, PageBody } from "../components/PageShell";
import { Citations } from "../components/Citations";
import { useAuth } from "../lib/auth";

type Msg = { role: "user" | "assistant"; content: string };

const SESSION_BADGE = "#A9F2";

export default function IntakeChat() {
  const navigate = useNavigate();
  const { profile, user } = useAuth();

  // Derive defaults from the signed-in user so the email / Airtable / SOP
  // all carry the real researcher identity instead of placeholder data.
  const authName = profile?.full_name || user?.user_metadata?.full_name || "";
  const authEmail = profile?.email || user?.email || "";
  const authGroup = profile?.research_group || user?.user_metadata?.research_group || "";
  const authTrainedCsv = (profile?.trained_instruments ?? []).join(", ");
  const firstName = authName.split(" ")[0] || authEmail.split("@")[0] || "there";

  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "assistant",
      content: `Hello, ${firstName}. Describe your experiment and I'll find the right instrument, check availability, and generate a customized SOP for your session.`,
    },
  ]);
  const [input, setInput] = useState("");
  const [context, setContext] = useState<ExperimentContext | undefined>();
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);
  const [sessionId, setSessionId] = useState<string | undefined>();

  const [researcherName, setResearcherName] = useState(authName);
  const [researcherEmail, setResearcherEmail] = useState(authEmail);
  const [researchGroup, setResearchGroup] = useState(authGroup);
  const [trainedCsv, setTrainedCsv] = useState(authTrainedCsv);

  // If the auth profile loads after the component mounted (race), backfill
  // any fields the user hasn't edited yet.
  useEffect(() => {
    if (authName && !researcherName) setResearcherName(authName);
    if (authEmail && !researcherEmail) setResearcherEmail(authEmail);
    if (authGroup && !researchGroup) setResearchGroup(authGroup);
    if (authTrainedCsv && !trainedCsv) setTrainedCsv(authTrainedCsv);
    if (authName) {
      setMessages((prev) =>
        prev.length === 1 && prev[0].role === "assistant" && prev[0].content.startsWith("Hello, ")
          ? [
              {
                role: "assistant",
                content: `Hello, ${firstName}. Describe your experiment and I'll find the right instrument, check availability, and generate a customized SOP for your session.`,
              },
            ]
          : prev
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authName, authEmail, authGroup, authTrainedCsv]);

  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), [messages, lastResponse]);

  const buildCtx = (base?: ExperimentContext): ExperimentContext => {
    const trained = trainedCsv.split(",").map((s) => s.trim()).filter(Boolean);
    return {
      material_type: "", analysis_goal: "", sample_dimensions: "", surface_condition: "",
      coating_status: "", urgency: "medium",
      ...(base ?? {}),
      // Identity is always the signed-in user (locked).
      researcher_name: authName || researcherName,
      researcher_email: authEmail || researcherEmail,
      research_group: researchGroup,
      trained_instruments: trained.length ? trained : base?.trained_instruments ?? [],
      notes: base?.notes ?? "",
      is_complete: base?.is_complete ?? false,
    };
  };

  const intake = useMutation({
    mutationFn: () =>
      api.intake(
        input,
        messages.map((m) => ({ role: m.role, content: m.content })),
        buildCtx(context),
        sessionId,
      ),
    onSuccess: (data) => {
      setMessages((m) => [...m, { role: "user", content: input }, { role: "assistant", content: data.message }]);
      setInput("");
      if (data.context) setContext(data.context);
      if (data.session_id) setSessionId(data.session_id);
      setLastResponse(data);
    },
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || intake.isPending) return;
    intake.mutate();
  };

  // Step indicator state
  const ctxReady = !!(context?.material_type && context?.analysis_goal && !lastResponse?.needs_clarification);
  const hasRecs = !!lastResponse?.recommendations?.length;
  const steps = [
    { label: "Context", state: ctxReady ? "done" : "active" } as const,
    { label: "Fit score", state: hasRecs ? "done" : ctxReady ? "active" : "pending" } as const,
    { label: "Schedule", state: "pending" } as const,
    { label: "SOP", state: "pending" } as const,
  ];

  return (
    <>
      <PageHeader
        title="Book a session — chat"
        badge={
          <span className="flex items-center gap-2">
            <Link
              to="/intake"
              className="chip bg-ink-100 text-ink-700 hover:bg-ink-200 inline-flex items-center gap-1"
              title="Switch to the structured form"
            >
              <ClipboardList className="w-3.5 h-3.5" />
              Use form instead
            </Link>
            <span className="chip bg-ink-100 text-ink-700">
              <span className="text-ink-400 mr-1">Session</span>
              {sessionId ? sessionId.replace("sess_", "").slice(0, 4).toUpperCase() : SESSION_BADGE}
            </span>
          </span>
        }
        steps={steps}
      />

      <PageBody>
        <div className="rounded-xl border border-info-600/30 bg-info-50/60 px-4 py-3 flex items-start gap-3 text-xs text-ink-700">
          <Shield className="w-4 h-4 text-info-700 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold text-ink-900 mb-0.5">
              Purpose of processing — what happens with this conversation
            </p>
            <p>
              Your messages are sent to Google Gemini for instrument fit scoring and
              SOP drafting. Name, email, and group are <em>redacted</em> before
              transit; the transcript is not retained outside the resulting booking
              record. Manage or delete your data from{" "}
              <Link to="/profile" className="font-semibold underline text-info-700 hover:text-navy-700">
                Profile → Privacy &amp; Compliance
              </Link>{" "}
              (GDPR Art. 15 / 17 / 20 · FERPA §99.10).
            </p>
          </div>
        </div>

        {/* Researcher chips */}
        <div className="card-pad grid md:grid-cols-2 lg:grid-cols-4 gap-3">
          <Field label="Your name (from your account)">
            <div className="input bg-ink-50 text-ink-700 flex items-center gap-2 cursor-not-allowed">
              <Lock className="w-3.5 h-3.5 text-ink-400 shrink-0" />
              <span className="truncate">{authName || "—"}</span>
            </div>
          </Field>
          <Field label="Email (from your account)">
            <div className="input bg-ink-50 text-ink-700 flex items-center gap-2 cursor-not-allowed">
              <Lock className="w-3.5 h-3.5 text-ink-400 shrink-0" />
              <span className="truncate">{authEmail || "—"}</span>
            </div>
          </Field>
          <Field label="Research group">
            <input className="input" value={researchGroup} onChange={(e) => setResearchGroup(e.target.value)} />
          </Field>
          <Field label="Training (comma-separated)">
            <input className="input" value={trainedCsv} onChange={(e) => setTrainedCsv(e.target.value)} />
          </Field>
        </div>

        {/* Chat panel */}
        <div className="card overflow-hidden">
          <div className="px-6 py-6 space-y-5 max-h-[560px] overflow-y-auto">
            {messages.map((m, i) => (
              <ChatBubble key={i} role={m.role} content={m.content} userName={researcherName} />
            ))}

            {context && ctxReady && <AgentContextCard ctx={context} citations={lastResponse?.citations ?? []} />}

            {lastResponse?.safety_gate && !lastResponse.safety_gate.passed && (
              <div className="rounded-xl border border-warn-600/40 bg-warn-50 p-4">
                <p className="flex items-center gap-2 text-sm font-semibold text-warn-700">
                  <ShieldAlert className="w-4 h-4" /> Safety gate — human review required
                </p>
                <ul className="mt-2 list-disc list-inside text-xs text-ink-700 space-y-1">
                  {lastResponse.safety_gate.reasons.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </div>
            )}

            {context?.hazmat_review_required && (
              <div className="rounded-xl border border-danger-600/40 bg-danger-50 p-4">
                <p className="flex items-center gap-2 text-sm font-semibold text-danger-700">
                  <AlertTriangle className="w-4 h-4" /> Hazardous materials detected
                </p>
                <p className="text-xs text-ink-700 mt-1">
                  {context.hazardous_materials?.join(", ") || "flagged"} — EH&S review required before booking.
                </p>
              </div>
            )}

            {hasRecs && (
              <div className="flex items-center justify-between rounded-xl border border-ink-200 bg-ink-50 px-4 py-3">
                <p className="text-sm text-ink-700">
                  Scoring all {lastResponse?.recommendations.length} instruments now…
                </p>
                <button
                  type="button"
                  onClick={() => navigate("/fit", { state: { lastResponse, context, sessionId } })}
                  className="text-sm font-semibold text-navy-700 inline-flex items-center gap-1 hover:underline"
                >
                  see fit results <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            )}

            {intake.isPending && (
              <div className="flex items-center gap-2 text-ink-500 text-sm">
                <Loader2 className="w-4 h-4 animate-spin" /> Analyzing with RAG corpus…
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <form onSubmit={submit} className="border-t border-ink-200 p-3 flex items-end gap-2">
            <textarea
              className="input min-h-[44px] max-h-[160px] resize-none"
              rows={1}
              placeholder="Add more detail or ask a question…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit(e);
                }
              }}
            />
            <button type="submit" className="btn-primary !px-4 !py-2.5" disabled={intake.isPending}>
              <ArrowUp className="w-4 h-4" /> Send
            </button>
          </form>
        </div>
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

function ChatBubble({ role, content, userName }: { role: "user" | "assistant"; content: string; userName?: string }) {
  const isUser = role === "user";
  const userInitials = (() => {
    const parts = (userName ?? "").trim().split(/\s+/).filter(Boolean);
    if (parts.length === 0) return "U";
    return (parts[0][0] + (parts[1]?.[0] ?? "")).toUpperCase();
  })();
  return (
    <div className={clsx("flex items-start gap-3", isUser ? "flex-row-reverse" : "")}>
      <div
        className={clsx(
          "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0",
          isUser ? "bg-gold-500 text-navy-900" : "bg-ink-200 text-ink-700"
        )}
      >
        {isUser ? userInitials : "L"}
      </div>
      <div
        className={clsx(
          "max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "bg-navy-800 text-white"
            : "bg-ink-100 text-ink-900"
        )}
      >
        {content.split("\n").map((line, j) => (
          <p key={j} className={j > 0 ? "mt-2" : ""}>
            {line.replace(/\*\*(.*?)\*\*/g, "$1")}
          </p>
        ))}
      </div>
    </div>
  );
}

function AgentContextCard({
  ctx,
  citations,
}: {
  ctx: ExperimentContext;
  citations: Citation[];
}) {
  const fields = [
    { k: "MATERIAL", v: ctx.material_type || "—" },
    { k: "ANALYSIS GOAL", v: ctx.analysis_goal || "—" },
    { k: "SAMPLE FORM", v: ctx.sample_dimensions || ctx.surface_condition || "—" },
    { k: "URGENCY", v: (ctx.urgency || "medium") + (ctx.deadline ? ` · ${ctx.deadline}` : "") },
    { k: "PREP STATUS", v: ctx.coating_status || "Ready" },
    { k: "EXPERIENCE", v: ctx.trained_instruments?.length ? "Experienced" : "First-time" },
  ];
  return (
    <div className="ml-11 rounded-xl border border-info-600/30 bg-white">
      <div className="px-4 py-2 border-b border-info-600/20 flex items-center gap-2">
        <span className="text-info-700">●</span>
        <span className="text-[11px] font-bold tracking-[0.16em] text-info-700 uppercase">
          Agent 1 — Experiment context parsed
        </span>
      </div>
      <div className="p-4 grid grid-cols-2 gap-3">
        {fields.map((f) => (
          <div key={f.k} className="rounded-lg border border-ink-200 px-3 py-2.5 bg-white">
            <p className="text-[10px] font-semibold tracking-wider text-ink-500 uppercase">{f.k}</p>
            <p className="text-sm text-ink-900 mt-0.5">{f.v}</p>
          </div>
        ))}
      </div>
      {citations.length > 0 && (
        <div className="px-4 pb-4">
          <Citations citations={citations} />
        </div>
      )}
    </div>
  );
}
