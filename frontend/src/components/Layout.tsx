import { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutGrid,
  MessageSquare,
  CalendarDays,
  FlaskConical,
  FileText,
  BookOpen,
  BarChart3,
  Settings,
} from "lucide-react";
import clsx from "clsx";
import { useAuth } from "../lib/auth";
import { useRealtime } from "../lib/useRealtime";

type NavItem = { to: string; label: string; icon: typeof LayoutGrid };
type Section = { title: string; items: NavItem[]; adminOnly?: boolean };

const sections: Section[] = [
  {
    title: "Main",
    items: [
      { to: "/",         label: "Dashboard",     icon: LayoutGrid },
      { to: "/intake",   label: "Book a session", icon: MessageSquare },
      { to: "/bookings", label: "Schedule",      icon: CalendarDays },
    ],
  },
  {
    title: "Research",
    items: [
      { to: "/instruments", label: "Instruments",    icon: FlaskConical },
      { to: "/postrun",     label: "My SOPs",        icon: FileText },
    ],
  },
  {
    title: "Admin",
    adminOnly: true,
    items: [
      { to: "/admin",      label: "Knowledge base", icon: BookOpen },
      { to: "/governance", label: "Analytics",      icon: BarChart3 },
      { to: "/settings",   label: "Settings",       icon: Settings },
    ],
  },
];

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return (parts[0][0] + (parts[1]?.[0] ?? "")).toUpperCase();
}

export default function Layout({ children }: { children: ReactNode }) {
  const { isAdmin } = useAuth();
  const live = useRealtime();
  const visibleSections = sections.filter((s) => !s.adminOnly || isAdmin);

  return (
    <div className="flex min-h-screen bg-ink-50">
      <aside className="w-[244px] shrink-0 bg-navy-800 text-white flex flex-col">
        {/* Wordmark */}
        <div className="px-6 pt-6 pb-5 border-b border-white/5">
          <h1 className="font-display text-2xl font-extrabold tracking-tight text-gold-500 leading-none">
            LODE
          </h1>
          <div className="flex items-center justify-between mt-1.5">
            <p className="text-[11px] text-navy-300 tracking-wide">Lab Operations &amp; Data Engine</p>
            <span
              title={live ? "Realtime connected" : "Realtime offline"}
              className="flex items-center gap-1 text-[10px] font-semibold text-navy-300"
            >
              <span
                className={clsx(
                  "w-1.5 h-1.5 rounded-full",
                  live ? "bg-green-400 animate-pulse" : "bg-navy-500"
                )}
              />
              {live ? "Live" : "Off"}
            </span>
          </div>
        </div>

        <nav className="flex-1 px-3 py-5 space-y-6 overflow-y-auto">
          {visibleSections.map((sec) => (
            <div key={sec.title}>
              <p className="px-3 text-[10px] font-bold tracking-[0.18em] text-navy-300 uppercase">
                {sec.title}
              </p>
              <ul className="mt-2 space-y-0.5">
                {sec.items.map(({ to, label, icon: Icon }) => (
                  <li key={to}>
                    <NavLink
                      to={to}
                      end={to === "/"}
                      className={({ isActive }) =>
                        clsx(
                          "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition relative tracking-tight",
                          isActive
                            ? "bg-gold-500/10 text-gold-400"
                            : "text-navy-300 hover:text-white hover:bg-white/5"
                        )
                      }
                    >
                      {({ isActive }) => (
                        <>
                          {isActive && (
                            <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r bg-gold-500" />
                          )}
                          <Icon className="w-[18px] h-[18px] shrink-0" />
                          <span>{label}</span>
                        </>
                      )}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        {/* Sidebar footer — quiet tagline only; profile + sign-out live in the top-right chip */}
        <div className="px-6 py-4 border-t border-white/5 text-[10px] text-navy-300/70 tracking-wide">
          Colorado School of Mines
          <br />
          Shared Instrumentation Facility
        </div>
      </aside>

      <main className="flex-1 min-w-0 overflow-auto">{children}</main>
    </div>
  );
}
