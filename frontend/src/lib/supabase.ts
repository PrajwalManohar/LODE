import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

/** True when both env vars are present — gates the auth UI vs a config notice. */
export const supabaseConfigured = Boolean(url && anonKey);

/**
 * Single shared browser client. When env is missing we still construct a
 * placeholder so imports don't throw; calls will simply fail until configured.
 */
export const supabase: SupabaseClient = createClient(
  url ?? "http://localhost",
  anonKey ?? "public-anon-key",
  {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
    },
  }
);

export type Role = "user" | "admin";

export interface Profile {
  id: string;
  email: string | null;
  full_name: string | null;
  research_group: string | null;
  role: Role;
  trained_instruments: string[] | null;
}
