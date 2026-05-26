import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import {
  ArrowRight,
  Loader2,
  Lock,
  MessageSquare,
  ShieldAlert,
  AlertTriangle,
  Sparkles,
} from "lucide-react";
import clsx from "clsx";
import { api, ExperimentContext } from "../lib/api";
import { PageHeader, PageBody } from "../components/PageShell";
import { useAuth } from "../lib/auth";

/**
 * Default "Book a session" path — a structured form. Submits to
 * /chat/intake/form which runs the SAME fit + schedule + safety pipeline as
 * the chat does. The chat path remains available at /intake/chat for users
 * who want to interact conversationally.
 */
export default function IntakeForm() {
  const navigate = useNavigate();
  const { profile, user } = useAuth();

  const authName = profile?.full_name || user?.user_metadata?.full_name || "";
  const authEmail = profile?.email || user?.email || "";
  const authGroup = profile?.research_group || user?.user_metadata?.research_group || "";
  const authTrainedCsv = (profile?.trained_instruments ?? []).join(", ");

  const [researcherName, setResearcherName] = useState(authName);
  const [researcherEmail, setResearcherEmail] = useState(authEmail);
  const [researchGroup, setResearchGroup] = useState(authGroup);
  const [trainedCsv, setTrainedCsv] = useState(authTrainedCsv);

  const [materialType, setMaterialType] = useState("");
  const [analysisGoal, setAnalysisGoal] = useState("");
  const [sampleDims, setSampleDims] = useState("");
  const [surfaceCondition, setSurfaceCondition] = useState("");
  const [coatingStatus, setCoatingStatus] = useState("");
  const [urgency, setUrgency] = useState<"low" | "medium" | "high" | "critical">("medium");
  const [deadline, setDeadline] = useState("");
  const [notes, setNotes] = useState("");
  const [hazardCsv, setHazardCsv] = useState("");

  // Backfill from auth after the profile loads.
  useEffect(() => {
    if (authName && !researcherName) setResearcherName(authName);
    if (authEmail && !researcherEmail) setResearcherEmail(authEmail);
    if (authGroup && !researchGroup) setResearchGroup(authGroup);
    if (authTrainedCsv && !trainedCsv) setTrainedCsv(authTrainedCsv);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authName, authEmail, authGroup, authTrainedCsv]);

  // Auto-dismiss the error banner so the user doesn't have to clear it manually.
  // submit.reset() clears isError/error from react-query's mutation state.

  const buildCtx = (): ExperimentContext => ({
    material_type: materialType.trim(),
    analysis_goal: analysisGoal.trim(),
    sample_dimensions: sampleDims.trim(),
    surface_condition: surfaceCondition.trim(),
    coating_status: coatingStatus.trim(),
    urgency,
    deadline: deadline.trim() || undefined,
    // Identity is always the signed-in user — never editable, so a researcher
    // can only ever raise a request for themselves.
    researcher_name: (authName || researcherName).trim(),
    researcher_email: (authEmail || researcherEmail).trim(),
    research_group: researchGroup.trim(),
    trained_instruments: trainedCsv
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
    notes: notes.trim(),
    is_complete: true,
    hazardous_materials: hazardCsv
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  });

  const submit = useMutation({
    mutationFn: () => api.intakeForm(buildCtx()),
    onSuccess: (data) => {
      // If the safety gate refused, we have no usable slot picker — send the
      // user to My Requests with a banner explaining what happened.
      if (data.escalated) {
        const reasons = data.safety_gate?.reasons || [];
        navigate("/requests", {
          state: {
            flash: {
              kind: "pending",
              instrument: data.recommendations?.[0]?.instrument_name || "the recommended instrument",
              reasons,
              sessionId: data.session_id,
            },
          },
        });
        return;
      }
      navigate("/fit", {
        state: { lastResponse: data, context: data.context ?? buildCtx(), sessionId: data.session_id },
      });
    },
  });

  useEffect(() => {
    if (!submit.isError) return;
    const t = window.setTimeout(() => submit.reset(), 8000);
    return () => window.clearTimeout(t);
  }, [submit]);

  const requiredOk = materialType.trim() && analysisGoal.trim() && researcherName.trim() && researcherEmail.trim();

  const steps = [
    { label: "Context",   state: "active"  } as const,
    { label: "Fit score", state: "pending" } as const,
    { label: "Schedule",  state: "pending" } as const,
    { label: "SOP",       state: "pending" } as const,
  ];

  return (
    <>
      <PageHeader
        title="Book a session"
        badge={
          <Link
            to="/intake/chat"
            className="chip bg-ink-100 text-ink-700 hover:bg-ink-200 inline-flex items-center gap-1"
            title="Switch to the conversational chat"
          >
            <MessageSquare className="w-3.5 h-3.5" />
            Try chat instead
          </Link>
        }
        steps={steps}
      />

      <PageBody>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!requiredOk || submit.isPending) return;
            submit.mutate();
          }}
          className="space-y-6"
        >
          {/* Researcher panel */}
          <section className="card-pad">
            <h2 className="text-[13px] font-bold tracking-[0.16em] text-ink-500 uppercase mb-3">
              Researcher
            </h2>
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-3">
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
                <input
                  className="input"
                  value={researchGroup}
                  onChange={(e) => setResearchGroup(e.target.value)}
                />
              </Field>
              <Field label="Training (comma-separated instrument IDs)">
                <input
                  className="input"
                  value={trainedCsv}
                  onChange={(e) => setTrainedCsv(e.target.value)}
                  placeholder="sem-jeol, xrd-d8"
                />
              </Field>
            </div>
          </section>

          {/* Experiment panel */}
          <section className="card-pad">
            <h2 className="text-[13px] font-bold tracking-[0.16em] text-ink-500 uppercase mb-3">
              Experiment
            </h2>
            <div className="grid md:grid-cols-2 gap-3">
              <Field label="Material *">
                <input
                  className="input"
                  value={materialType}
                  onChange={(e) => setMaterialType(e.target.value)}
                  placeholder="e.g. chalcopyrite ore powder, martensitic steel"
                  required
                />
              </Field>
              <Field label="Analysis goal *">
                <input
                  className="input"
                  value={analysisGoal}
                  onChange={(e) => setAnalysisGoal(e.target.value)}
                  placeholder="e.g. phase identification, fracture surface morphology"
                  required
                />
              </Field>
              <Field label="Sample form / dimensions">
                <input
                  className="input"
                  value={sampleDims}
                  onChange={(e) => setSampleDims(e.target.value)}
                  placeholder="e.g. 5mm × 5mm coupon, 5 g powder"
                />
              </Field>
              <Field label="Surface condition">
                <input
                  className="input"
                  value={surfaceCondition}
                  onChange={(e) => setSurfaceCondition(e.target.value)}
                  placeholder="e.g. uncoated fracture surface, polished"
                />
              </Field>
              <Field label="Coating status">
                <select
                  className="input"
                  value={coatingStatus}
                  onChange={(e) => setCoatingStatus(e.target.value)}
                >
                  <option value="">— select —</option>
                  <option value="not required">Not required</option>
                  <option value="uncoated">Uncoated — needs prep</option>
                  <option value="coating scheduled">Coating already scheduled</option>
                  <option value="coated">Already coated</option>
                </select>
              </Field>
              <Field label="Hazardous materials (if any, comma-separated)">
                <input
                  className="input"
                  value={hazardCsv}
                  onChange={(e) => setHazardCsv(e.target.value)}
                  placeholder="e.g. HF, perchloric"
                />
              </Field>
            </div>
          </section>

          {/* Timing */}
          <section className="card-pad">
            <h2 className="text-[13px] font-bold tracking-[0.16em] text-ink-500 uppercase mb-3">
              Timing
            </h2>
            <div className="grid md:grid-cols-3 gap-3">
              <Field label="Urgency">
                <select
                  className="input"
                  value={urgency}
                  onChange={(e) => setUrgency(e.target.value as typeof urgency)}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </Field>
              <Field label="Deadline (optional)">
                <input
                  className="input"
                  value={deadline}
                  onChange={(e) => setDeadline(e.target.value)}
                  placeholder="e.g. Thursday, 2026-06-04"
                />
              </Field>
              <Field label="Notes for the lab manager">
                <input
                  className="input"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Anything else worth knowing"
                />
              </Field>
            </div>
          </section>

          {/* Submit */}
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="text-xs text-ink-500 flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-gold-500" />
              Submitting runs the same fit / safety / SOP pipeline as the chat — automations fire when you confirm a slot.
            </div>
            <button
              type="submit"
              className="btn-primary"
              disabled={!requiredOk || submit.isPending}
            >
              {submit.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Scoring instruments…
                </>
              ) : (
                <>
                  Find instrument & propose slots <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>

          {submit.isError && (
            <div className="rounded-xl border border-danger-600/40 bg-danger-50 p-4">
              <p className="flex items-center gap-2 text-sm font-semibold text-danger-700">
                <AlertTriangle className="w-4 h-4" /> Could not run intake
              </p>
              <p className="text-xs text-ink-700 mt-1 font-mono break-all">
                {String((submit.error as Error)?.message || submit.error)}
              </p>
            </div>
          )}

          {!requiredOk && (
            <p className="text-xs text-ink-500 flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5" />
              Required: name, email, material, analysis goal.
            </p>
          )}
        </form>
      </PageBody>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className={clsx("block")}>
      <span className="block text-[11px] font-semibold tracking-wide text-ink-500 uppercase mb-1">
        {label}
      </span>
      {children}
    </label>
  );
}
