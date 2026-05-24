import { useNavigate } from "react-router-dom";
import {
  Mail,
  User as UserIcon,
  Building2,
  ShieldCheck,
  GraduationCap,
  Calendar,
  LogOut,
  Copy,
  Check,
} from "lucide-react";
import { useState } from "react";
import { PageHeader, PageBody } from "../components/PageShell";
import { useAuth } from "../lib/auth";
import { initials } from "../components/Layout";

export default function Profile() {
  const { user, profile, role, isAdmin, signOut } = useAuth();
  const nav = useNavigate();
  const [copied, setCopied] = useState<string | null>(null);

  const displayName = profile?.full_name || profile?.email || user?.email || "Researcher";
  const displayEmail = profile?.email || user?.email || "—";
  const researchGroup = profile?.research_group || "—";
  const roleLabel = role ? role[0].toUpperCase() + role.slice(1) : "User";
  const trained = profile?.trained_instruments ?? [];
  const memberSince = user?.created_at
    ? new Date(user.created_at).toLocaleDateString(undefined, {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "—";
  const lastSignIn = user?.last_sign_in_at
    ? new Date(user.last_sign_in_at).toLocaleString()
    : "—";

  async function copy(text: string, key: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      /* ignore */
    }
  }

  async function handleSignOut() {
    await signOut();
    nav("/login", { replace: true });
  }

  return (
    <>
      <PageHeader
        title="Profile"
        actions={
          <button
            onClick={handleSignOut}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-danger-50 text-danger-700 border border-danger-200 hover:bg-danger-100 transition"
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </button>
        }
      />

      <PageBody>
        {/* Identity card */}
        <section className="card overflow-hidden">
          <div className="relative bg-gradient-to-br from-navy-800 via-navy-700 to-navy-600 px-8 py-10">
            <div
              className="absolute inset-0 opacity-[0.08]"
              style={{
                backgroundImage:
                  "radial-gradient(circle at 1px 1px, #c89e54 1px, transparent 0)",
                backgroundSize: "24px 24px",
              }}
            />
            <div className="relative flex items-center gap-6">
              <div className="w-20 h-20 rounded-2xl bg-gold-500 flex items-center justify-center text-navy-900 font-display font-extrabold text-2xl shadow-lg shrink-0">
                {initials(displayName)}
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="font-display text-2xl font-bold text-white tracking-tight truncate">
                  {displayName}
                </h2>
                <p className="text-sm text-navy-300 mt-1 flex items-center gap-1.5 truncate">
                  <Mail className="w-3.5 h-3.5" />
                  {displayEmail}
                </p>
                <div className="flex items-center gap-2 mt-3 flex-wrap">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider bg-gold-500/15 text-gold-400 border border-gold-500/30">
                    <ShieldCheck className="w-3 h-3" />
                    {roleLabel}
                  </span>
                  {researchGroup !== "—" && (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-white/10 text-white border border-white/15">
                      <Building2 className="w-3 h-3" />
                      {researchGroup}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Details grid */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Account info */}
          <section className="card overflow-hidden lg:col-span-2">
            <div className="px-6 py-4 border-b border-ink-200">
              <h3 className="font-display text-[15px] font-semibold text-ink-900 tracking-tight">
                Account information
              </h3>
              <p className="text-xs text-ink-500 mt-0.5">
                Identity and access details synced from Supabase Auth.
              </p>
            </div>
            <dl className="divide-y divide-ink-100">
              <Row
                icon={<UserIcon className="w-4 h-4" />}
                label="Full name"
                value={profile?.full_name || "—"}
              />
              <Row
                icon={<Mail className="w-4 h-4" />}
                label="Email address"
                value={displayEmail}
                onCopy={
                  displayEmail !== "—"
                    ? () => copy(displayEmail, "email")
                    : undefined
                }
                copied={copied === "email"}
              />
              <Row
                icon={<Building2 className="w-4 h-4" />}
                label="Research group"
                value={researchGroup}
              />
              <Row
                icon={<ShieldCheck className="w-4 h-4" />}
                label="Role"
                value={
                  <span
                    className={
                      isAdmin
                        ? "pill bg-cite-50 text-cite-700"
                        : "pill bg-ink-100 text-ink-600"
                    }
                  >
                    {roleLabel}
                  </span>
                }
              />
              <Row
                icon={<Calendar className="w-4 h-4" />}
                label="Member since"
                value={memberSince}
              />
              <Row
                icon={<Calendar className="w-4 h-4" />}
                label="Last sign-in"
                value={lastSignIn}
              />
              {user?.id && (
                <Row
                  icon={<UserIcon className="w-4 h-4" />}
                  label="User ID"
                  value={
                    <span className="font-mono text-xs text-ink-600">
                      {user.id}
                    </span>
                  }
                  onCopy={() => copy(user.id, "uid")}
                  copied={copied === "uid"}
                />
              )}
            </dl>
          </section>

          {/* Training certifications */}
          <section className="card overflow-hidden">
            <div className="px-6 py-4 border-b border-ink-200 flex items-center justify-between">
              <div>
                <h3 className="font-display text-[15px] font-semibold text-ink-900 tracking-tight">
                  Training
                </h3>
                <p className="text-xs text-ink-500 mt-0.5">
                  Instruments you're certified to operate.
                </p>
              </div>
              <span className="pill bg-navy-50 text-navy-700 border border-navy-200">
                {trained.length}
              </span>
            </div>
            <div className="px-6 py-5">
              {trained.length === 0 ? (
                <div className="text-center py-6">
                  <GraduationCap className="w-8 h-8 text-ink-300 mx-auto mb-2" />
                  <p className="text-sm text-ink-500">No certifications on file</p>
                  <p className="text-xs text-ink-400 mt-1">
                    Contact the lab manager to add training records.
                  </p>
                </div>
              ) : (
                <ul className="space-y-2">
                  {trained.map((t) => (
                    <li
                      key={t}
                      className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-ok-50 border border-ok-200"
                    >
                      <GraduationCap className="w-4 h-4 text-ok-700 shrink-0" />
                      <span className="text-sm font-medium text-ok-700 truncate">
                        {t}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </div>

        {/* Session card */}
        <section className="card-pad">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <h3 className="font-display text-[15px] font-semibold text-ink-900 tracking-tight">
                Session
              </h3>
              <p className="text-sm text-ink-500 mt-1 max-w-lg">
                Signing out will end your current session on this device and
                return you to the login screen.
              </p>
            </div>
            <button
              onClick={handleSignOut}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold bg-navy-800 text-white hover:bg-navy-700 transition shadow-sm"
            >
              <LogOut className="w-4 h-4" />
              Sign out of LODE
            </button>
          </div>
        </section>
      </PageBody>
    </>
  );
}

function Row({
  icon,
  label,
  value,
  onCopy,
  copied,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  onCopy?: () => void;
  copied?: boolean;
}) {
  return (
    <div className="px-6 py-3.5 flex items-center gap-4">
      <div className="w-7 h-7 rounded-md bg-ink-100 text-ink-500 flex items-center justify-center shrink-0">
        {icon}
      </div>
      <div className="text-xs font-medium text-ink-500 tracking-wide w-36 shrink-0">
        {label}
      </div>
      <div className="text-sm text-ink-900 flex-1 min-w-0 truncate">{value}</div>
      {onCopy && (
        <button
          onClick={onCopy}
          className="text-ink-400 hover:text-navy-700 transition shrink-0"
          title="Copy"
        >
          {copied ? (
            <Check className="w-4 h-4 text-ok-600" />
          ) : (
            <Copy className="w-4 h-4" />
          )}
        </button>
      )}
    </div>
  );
}
