import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { supabase, supabaseConfigured } from "./supabase";

/**
 * Tables we watch and the TanStack Query keys to invalidate when they change.
 * The backend writes to Postgres via psycopg, which fires these realtime
 * events through the supabase_realtime publication. RLS still applies, so a
 * user only receives events for rows they're allowed to see.
 */
const SUBSCRIPTIONS: { table: string; keys: string[] }[] = [
  // "my-requests" is invalidated on any of these — it's the user-scoped
  // tracker page, scoped by email at the backend, so we just nudge it
  // whenever any HITL/work-order/booking row changes.
  { table: "bookings",          keys: ["bookings", "utilization", "equity", "status", "my-requests"] },
  { table: "work_orders",       keys: ["work-orders", "my-requests"] },
  { table: "agent_decisions",   keys: ["audit"] },
  { table: "instruments",       keys: ["instruments", "status"] },
  { table: "automation_events", keys: ["automations", "hitl", "my-requests"] },
];

/**
 * Subscribes to Postgres changes and invalidates the affected queries so the
 * UI refreshes the instant data changes — no polling delay. Returns whether
 * the realtime channel is currently connected (for a live indicator).
 */
export function useRealtime(): boolean {
  const qc = useQueryClient();
  const [live, setLive] = useState(false);
  // Each hook instance needs its OWN channel — supabase.channel(name) is
  // memoized by name, so reusing one across multiple components causes
  // "cannot add postgres_changes callbacks after subscribe()" the second
  // time it mounts (which crashed MyRequests when Layout was also calling it).
  const channelNameRef = useRef<string>(
    `lode-db-${Math.random().toString(36).slice(2, 10)}`,
  );

  useEffect(() => {
    if (!supabaseConfigured) return;

    const channel = supabase.channel(channelNameRef.current);
    for (const sub of SUBSCRIPTIONS) {
      channel.on(
        "postgres_changes",
        { event: "*", schema: "public", table: sub.table },
        () => {
          for (const key of sub.keys) {
            qc.invalidateQueries({ queryKey: [key] });
          }
        }
      );
    }
    channel.subscribe((status) => setLive(status === "SUBSCRIBED"));

    return () => {
      supabase.removeChannel(channel);
    };
  }, [qc]);

  return live;
}
