-- LODE Phase 4 · Automation audit trail (realtime)
-- Every automation attempt (email send, booking sync, work-order routing) is
-- recorded here so the admin UI shows a live, queryable feed instead of local
-- JSONL files.

create table if not exists public.automation_events (
  id          bigint generated always as identity primary key,
  kind        text not null,             -- email | booking_sync | work_order
  status      text not null,             -- sent | queued | failed | created
  target      text,                      -- recipients / table / instrument
  detail      text,                      -- human-readable summary
  payload     jsonb,
  error       text,
  created_at  timestamptz not null default now()
);
create index if not exists automation_events_kind_idx on public.automation_events(kind);
create index if not exists automation_events_created_idx on public.automation_events(created_at desc);

alter table public.automation_events enable row level security;
drop policy if exists automation_events_admin on public.automation_events;
create policy automation_events_admin on public.automation_events
  for select using (public.is_admin());

-- Realtime
alter table public.automation_events replica identity full;
do $$
begin
  begin alter publication supabase_realtime add table public.automation_events;
  exception when duplicate_object then null; end;
end $$;
