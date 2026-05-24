import { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Check, Mail } from "lucide-react";
import clsx from "clsx";
import { useAuth } from "../lib/auth";
import { initials } from "./Layout";

export function PageHeader({
  title,
  badge,
  actions,
  steps,
  subtitle,
}: {
  title: string;
  badge?: ReactNode;
  actions?: ReactNode;
  steps?: { label: string; state: "done" | "active" | "pending" }[];
  subtitle?: ReactNode;
}) {
  return (
    <div className="border-b border-ink-200 bg-white">
      <div className="px-8 pt-6 pb-5 flex items-start justify-between gap-6 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="font-display text-[24px] font-bold text-ink-900 tracking-tight leading-none">
              {title}
            </h1>
            {badge}
          </div>
          {subtitle && (
            <p className="text-sm text-ink-500 mt-1.5 leading-snug">{subtitle}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {actions}
          <UserChip />
        </div>
      </div>
      {steps && (
        <div className="px-8 pb-4 flex items-center gap-6 flex-wrap">
          {steps.map((s, i) => (
            <div key={s.label} className="flex items-center gap-2">
              <StepDot index={i + 1} state={s.state} />
              <span
                className={clsx(
                  "text-sm tracking-tight",
                  s.state === "active" && "text-ink-900 font-semibold",
                  s.state === "done" && "text-ok-700",
                  s.state === "pending" && "text-ink-500"
                )}
              >
                {s.label}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function UserChip() {
  const { profile, user } = useAuth();
  if (!user) return null;
  const name = profile?.full_name || profile?.email || user.email || "Researcher";
  const email = profile?.email || user.email || "";
  return (
    <Link
      to="/profile"
      title="View profile"
      className="flex items-center gap-2.5 px-2 py-1.5 pr-3 rounded-full border border-ink-200 bg-white hover:bg-ink-50 hover:border-ink-300 transition group"
    >
      <span className="w-7 h-7 rounded-full bg-navy-800 text-white text-[11px] font-bold flex items-center justify-center shrink-0">
        {initials(name)}
      </span>
      <span className="text-right leading-tight">
        <span className="block text-xs font-semibold text-ink-900 truncate max-w-[180px] tracking-tight">
          {name}
        </span>
        {email && (
          <span className="block text-[10px] text-ink-500 truncate max-w-[180px] flex items-center justify-end gap-1">
            <Mail className="w-2.5 h-2.5" />
            {email}
          </span>
        )}
      </span>
    </Link>
  );
}

function StepDot({ index, state }: { index: number; state: "done" | "active" | "pending" }) {
  if (state === "done") {
    return (
      <span className="w-5 h-5 rounded-full bg-ok-600 text-white flex items-center justify-center">
        <Check className="w-3 h-3" strokeWidth={3} />
      </span>
    );
  }
  return (
    <span
      className={clsx(
        "w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold",
        state === "active"
          ? "bg-navy-800 text-white"
          : "bg-ink-200 text-ink-500"
      )}
    >
      {index}
    </span>
  );
}

export function PageBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={clsx("p-8 space-y-6", className)}>{children}</div>;
}
