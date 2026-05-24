import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { LogIn, UserPlus, Loader2, ShieldCheck, FlaskConical, Sparkles } from "lucide-react";
import { useAuth } from "../lib/auth";

type LocState = { from?: { pathname?: string } };

export default function Login() {
  const { session, loading, signIn, signUp, configured } = useAuth();
  const nav = useNavigate();
  const location = useLocation();
  const fromPath = (location.state as LocState | null)?.from?.pathname || "/";

  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [group, setGroup] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // KEY FIX — wait for the session to *actually* appear before navigating.
  // Previously we called nav("/") synchronously after signIn(), but Supabase's
  // onAuthStateChange updates `session` async, so RequireAuth would see a
  // stale null and bounce back to /login (the "page not found" flash).
  useEffect(() => {
    if (!loading && session) {
      nav(fromPath, { replace: true });
    }
  }, [session, loading, nav, fromPath]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      if (mode === "signin") {
        const { error } = await signIn(email, password);
        if (error) setError(error);
        // Navigation handled by the useEffect above once session is set.
      } else {
        const { error } = await signUp(email, password, {
          full_name: fullName,
          research_group: group,
        });
        if (error) setError(error);
        else setNotice("Account created. Check your inbox to confirm, then sign in.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.05fr_1fr] bg-navy-900">
      {/* Left — brand panel */}
      <div className="relative hidden lg:flex flex-col justify-between p-12 overflow-hidden bg-gradient-to-br from-navy-900 via-navy-800 to-navy-700">
        <div
          className="absolute inset-0 opacity-[0.06]"
          style={{
            backgroundImage:
              "radial-gradient(circle at 1px 1px, #c89e54 1px, transparent 0)",
            backgroundSize: "28px 28px",
          }}
        />
        <div className="absolute -top-32 -right-24 w-[420px] h-[420px] rounded-full bg-gold-500/15 blur-3xl" />
        <div className="absolute -bottom-40 -left-24 w-[420px] h-[420px] rounded-full bg-navy-500/30 blur-3xl" />

        <div className="relative">
          <h1 className="font-display text-5xl font-extrabold tracking-tight text-gold-500 leading-none">
            LODE
          </h1>
          <p className="text-sm text-navy-300 mt-3 font-medium tracking-wide">
            Lab Operations &amp; Data Engine
          </p>
          <p className="text-xs text-navy-300/70 mt-1 tracking-wide uppercase">
            Colorado School of Mines · Shared Instrumentation Facility
          </p>
        </div>

        <div className="relative space-y-5">
          <Feature
            icon={<FlaskConical className="w-5 h-5 text-gold-400" />}
            title="Five-agent booking pipeline"
            text="Conversational intake, fit scoring, scheduling, SOP generation, and post-run analysis — every decision RAG-grounded with manual citations."
          />
          <Feature
            icon={<ShieldCheck className="w-5 h-5 text-gold-400" />}
            title="Safety gate, by design"
            text="Training, hazmat, calibration, and confidence rules enforced architecturally — no UI bypass."
          />
          <Feature
            icon={<Sparkles className="w-5 h-5 text-gold-400" />}
            title="Governance you can audit"
            text="Every agent decision is logged with its reasoning chain, confidence score, and source citations."
          />
        </div>

        <p className="relative text-xs text-navy-300/60">
          © {new Date().getFullYear()} Colorado School of Mines · LODE platform
        </p>
      </div>

      {/* Right — form panel */}
      <div className="flex items-center justify-center p-6 sm:p-12 bg-ink-50">
        <div className="w-full max-w-md">
          <div className="lg:hidden text-center mb-8">
            <h1 className="font-display text-4xl font-extrabold tracking-tight text-navy-800">
              LODE
            </h1>
            <p className="text-sm text-ink-500 mt-1">Lab Operations &amp; Data Engine</p>
          </div>

          <div className="bg-white rounded-2xl shadow-pop border border-ink-200 p-8">
            <div className="mb-6">
              <h2 className="font-display text-2xl font-bold text-ink-900 tracking-tight">
                {mode === "signin" ? "Welcome back" : "Create your account"}
              </h2>
              <p className="text-sm text-ink-500 mt-1.5">
                {mode === "signin"
                  ? "Sign in to access the lab intelligence platform."
                  : "Register a researcher account to book instruments and generate SOPs."}
              </p>
            </div>

            {!configured && (
              <div className="mb-5 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-xs text-amber-800 leading-relaxed">
                <p className="font-semibold mb-0.5">Supabase not configured</p>
                Set <code className="font-mono">VITE_SUPABASE_URL</code> and{" "}
                <code className="font-mono">VITE_SUPABASE_ANON_KEY</code> in{" "}
                <code className="font-mono">frontend/.env</code>, then restart Vite.
              </div>
            )}

            <form onSubmit={submit} className="space-y-4">
              {mode === "signup" && (
                <>
                  <Field
                    label="Full name"
                    value={fullName}
                    onChange={setFullName}
                    placeholder="Dr. Sarah Chen"
                    autoComplete="name"
                  />
                  <Field
                    label="Research group"
                    value={group}
                    onChange={setGroup}
                    placeholder="MetEng-Lab"
                    autoComplete="organization"
                  />
                </>
              )}
              <Field
                label="Email"
                type="email"
                value={email}
                onChange={setEmail}
                placeholder="you@mines.edu"
                autoComplete="email"
                required
              />
              <Field
                label="Password"
                type="password"
                value={password}
                onChange={setPassword}
                placeholder="••••••••"
                autoComplete={mode === "signin" ? "current-password" : "new-password"}
                required
              />

              {error && (
                <div className="rounded-lg bg-danger-50 border border-danger-200 px-3 py-2 text-sm text-danger-700">
                  {error}
                </div>
              )}
              {notice && (
                <div className="rounded-lg bg-ok-50 border border-ok-200 px-3 py-2 text-sm text-ok-700">
                  {notice}
                </div>
              )}

              <button
                type="submit"
                disabled={busy || !configured}
                className="w-full inline-flex items-center justify-center gap-2 bg-navy-800 hover:bg-navy-700 text-white rounded-lg py-3 font-semibold text-sm transition disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
              >
                {busy ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Please wait…
                  </>
                ) : mode === "signin" ? (
                  <>
                    <LogIn className="w-4 h-4" />
                    Sign in
                  </>
                ) : (
                  <>
                    <UserPlus className="w-4 h-4" />
                    Create account
                  </>
                )}
              </button>
            </form>

            <div className="mt-6 pt-5 border-t border-ink-200 text-center">
              <button
                onClick={() => {
                  setMode(mode === "signin" ? "signup" : "signin");
                  setError(null);
                  setNotice(null);
                }}
                className="text-sm text-navy-700 hover:text-navy-900 font-medium transition"
              >
                {mode === "signin"
                  ? "Need an account? Sign up →"
                  : "← Have an account? Sign in"}
              </button>
            </div>
          </div>

          <p className="text-center text-xs text-ink-400 mt-6">
            Protected by Supabase Auth · Colorado School of Mines
          </p>
        </div>
      </div>
    </div>
  );
}

function Feature({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return (
    <div className="flex items-start gap-3.5">
      <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center shrink-0">
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-white tracking-tight">{title}</p>
        <p className="text-xs text-navy-300 leading-relaxed mt-0.5">{text}</p>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  required,
  autoComplete,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
  required?: boolean;
  autoComplete?: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-ink-700 tracking-wide">{label}</span>
      <input
        type={type}
        value={value}
        required={required}
        placeholder={placeholder}
        autoComplete={autoComplete}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1.5 w-full rounded-lg border border-ink-200 bg-white px-3.5 py-2.5 text-sm text-ink-900 placeholder:text-ink-400 focus:border-navy-500 focus:ring-2 focus:ring-navy-500/20 outline-none transition"
      />
    </label>
  );
}
