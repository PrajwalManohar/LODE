-- LODE Phase 1 · Realtime
-- Add tables to the supabase_realtime publication so the frontend gets live
-- INSERT/UPDATE/DELETE events (req #1 + #5). REPLICA IDENTITY FULL ensures
-- UPDATE/DELETE payloads include the old row for client-side reconciliation.

alter table public.bookings        replica identity full;
alter table public.work_orders     replica identity full;
alter table public.agent_decisions replica identity full;
alter table public.instruments     replica identity full;

do $$
begin
  -- create the publication if the project doesn't already have it
  if not exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    create publication supabase_realtime;
  end if;
end $$;

alter publication supabase_realtime add table public.bookings;
alter publication supabase_realtime add table public.work_orders;
alter publication supabase_realtime add table public.agent_decisions;
alter publication supabase_realtime add table public.instruments;
