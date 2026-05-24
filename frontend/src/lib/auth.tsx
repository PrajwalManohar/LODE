import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { Session, User } from "@supabase/supabase-js";
import { supabase, supabaseConfigured, type Profile, type Role } from "./supabase";

interface AuthState {
  loading: boolean;
  session: Session | null;
  user: User | null;
  profile: Profile | null;
  role: Role | null;
  isAdmin: boolean;
  configured: boolean;
  signIn: (email: string, password: string) => Promise<{ error: string | null }>;
  signUp: (
    email: string,
    password: string,
    meta: { full_name: string; research_group: string }
  ) => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

async function loadProfile(userId: string): Promise<Profile | null> {
  try {
    const { data, error } = await supabase
      .from("profiles")
      .select("id, email, full_name, research_group, role, trained_instruments")
      .eq("id", userId)
      .maybeSingle();
    if (error) {
      console.warn("[auth] profile load error:", error.message);
      return null;
    }
    return (data as Profile) ?? null;
  } catch (err) {
    console.warn("[auth] profile load threw:", err);
    return null;
  }
}

/** Build a minimal Profile from auth user metadata when no DB row exists. */
function profileFromUser(user: User): Profile {
  const meta = (user.user_metadata ?? {}) as {
    full_name?: string;
    research_group?: string;
  };
  return {
    id: user.id,
    email: user.email ?? null,
    full_name: meta.full_name ?? null,
    research_group: meta.research_group ?? null,
    role: "user",
    trained_instruments: [],
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);

  useEffect(() => {
    if (!supabaseConfigured) {
      setLoading(false);
      return;
    }

    // Safety net: never let the splash hang for more than 4s — if Supabase is
    // unreachable, the user still gets to the login page where they can react.
    const hardTimeout = window.setTimeout(() => setLoading(false), 4000);

    supabase.auth
      .getSession()
      .then(({ data }) => {
        setSession(data.session);
        setLoading(false); // KEY: flip immediately. Don't wait for profile.
        window.clearTimeout(hardTimeout);

        // Profile is best-effort and loads in the background. If the DB query
        // fails or the row doesn't exist, fall back to auth metadata so the
        // UI never shows an empty user pill.
        if (data.session?.user) {
          const u = data.session.user;
          loadProfile(u.id).then((p) => setProfile(p ?? profileFromUser(u)));
        }
      })
      .catch((err) => {
        console.warn("[auth] getSession failed:", err);
        setLoading(false);
        window.clearTimeout(hardTimeout);
      });

    const { data: sub } = supabase.auth.onAuthStateChange((event, sess) => {
      console.debug("[auth] event:", event, "session:", !!sess);
      setSession(sess);
      if (sess?.user) {
        const u = sess.user;
        loadProfile(u.id).then((p) => setProfile(p ?? profileFromUser(u)));
      } else {
        setProfile(null);
      }
    });

    return () => {
      window.clearTimeout(hardTimeout);
      sub.subscription.unsubscribe();
    };
  }, []);

  const value: AuthState = {
    loading,
    session,
    user: session?.user ?? null,
    profile,
    role: profile?.role ?? null,
    isAdmin: profile?.role === "admin",
    configured: supabaseConfigured,
    signIn: async (email, password) => {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      return { error: error?.message ?? null };
    },
    signUp: async (email, password, meta) => {
      const { error } = await supabase.auth.signUp({
        email,
        password,
        options: { data: meta },
      });
      return { error: error?.message ?? null };
    },
    signOut: async () => {
      await supabase.auth.signOut();
      setSession(null);
      setProfile(null);
    },
    refreshProfile: async () => {
      if (session?.user) {
        const p = await loadProfile(session.user.id);
        setProfile(p ?? profileFromUser(session.user));
      }
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
