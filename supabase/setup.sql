-- ===========================================================================
-- LODE · Supabase one-shot setup
-- Paste this whole file into Supabase → SQL Editor → Run.
-- It is the concatenation of migrations 0001→0004, idempotent and re-runnable.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 0001 · Core schema + profiles/roles
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
  id                  uuid primary key references auth.users(id) on delete cascade,
  email               text,
  full_name           text,
  research_group      text,
  role                text not null default 'user' check (role in ('user','admin')),
  trained_instruments text[] default '{}',
  created_at          timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
declare
  is_first boolean;
begin
  select count(*) = 0 into is_first from public.profiles;
  insert into public.profiles (id, email, full_name, research_group, role)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', ''),
    coalesce(new.raw_user_meta_data->>'research_group', ''),
    case when is_first then 'admin' else 'user' end
  );
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

create table if not exists public.instruments (
  id                          text primary key,
  name                        text not null,
  type                        text not null,
  manufacturer                text,
  model                       text,
  location                    text,
  warmup_minutes              integer default 30,
  cooldown_minutes            integer default 15,
  status                      text default 'operational',
  required_training           text,
  calibration_interval_hours  integer default 500,
  last_calibrated_at          timestamptz
);

create table if not exists public.bookings (
  id                  bigint generated always as identity primary key,
  instrument_id       text not null references public.instruments(id),
  user_id             uuid references public.profiles(id),
  researcher_name     text,
  researcher_email    text,
  start_time          timestamptz not null,
  end_time            timestamptz not null,
  status              text default 'confirmed',
  experiment_context  jsonb,
  sop_path            text,
  created_at          timestamptz not null default now()
);
create index if not exists bookings_instrument_idx on public.bookings(instrument_id);
create index if not exists bookings_user_idx on public.bookings(user_id);

create table if not exists public.run_logs (
  id              bigint generated always as identity primary key,
  instrument_id   text not null,
  researcher_name text,
  material_type   text,
  parameters      text,
  outcome         text,
  quality_rating  integer,
  run_date        timestamptz default now(),
  booking_id      bigint
);

create table if not exists public.maintenance_logs (
  id            bigint generated always as identity primary key,
  instrument_id text not null,
  error_code    text,
  description   text,
  action_taken  text,
  severity      text,
  logged_at     timestamptz default now()
);

create table if not exists public.rag_metadata (
  id            bigint generated always as identity primary key,
  corpus_type   text,
  document_name text,
  chunk_count   integer,
  indexed_at    timestamptz default now()
);

create table if not exists public.agent_decisions (
  id             bigint generated always as identity primary key,
  session_id     text,
  agent          text not null,
  input_summary  text,
  output_summary text,
  reasoning      text,
  confidence     integer,
  rag_chunks     jsonb,
  citations      jsonb,
  outcome        text,
  created_at     timestamptz default now()
);
create index if not exists agent_decisions_session_idx on public.agent_decisions(session_id);

create table if not exists public.work_orders (
  id                          bigint generated always as identity primary key,
  instrument_id               text not null,
  issue                       text,
  severity                    text,
  usage_hours                 real,
  calibration_interval_hours  real,
  recommended_action          text,
  status                      text default 'open',
  created_at                  timestamptz default now(),
  source                      text
);

-- ---------------------------------------------------------------------------
-- 0002 · RAG vector store (pgvector)
-- ---------------------------------------------------------------------------
create extension if not exists vector;

create table if not exists public.documents (
  id            text primary key,
  content       text not null,
  embedding     vector(384),
  source        text,
  section       text,
  page          text,
  corpus_type   text,
  instrument_id text,
  created_at    timestamptz not null default now()
);

-- NOTE: at demo corpus scale (tens–hundreds of chunks) we use EXACT cosine
-- search — an ivfflat index with lists=100 returns too few/zero rows on a tiny
-- corpus. Re-enable an ivfflat/hnsw index (tuned lists + ivfflat.probes) only
-- once the corpus grows into the thousands. See migration 0008.
-- create index if not exists documents_embedding_idx
--   on public.documents using ivfflat (embedding vector_cosine_ops) with (lists = 100);
create index if not exists documents_instrument_idx on public.documents(instrument_id);
create index if not exists documents_corpus_type_idx on public.documents(corpus_type);

create or replace function public.match_documents(
  query_embedding   vector(384),
  match_count       int default 5,
  filter_instrument text default null,
  filter_corpus     text default null
)
returns table (
  id text, content text, source text, section text, page text,
  corpus_type text, instrument_id text, similarity float
)
language sql stable
as $$
  select
    d.id, d.content, d.source, d.section, d.page, d.corpus_type, d.instrument_id,
    1 - (d.embedding <=> query_embedding) as similarity
  from public.documents d
  where (filter_instrument is null or d.instrument_id = filter_instrument)
    and (filter_corpus is null or d.corpus_type = filter_corpus)
  order by d.embedding <=> query_embedding
  limit match_count;
$$;

-- ---------------------------------------------------------------------------
-- 0003 · Row Level Security
-- ---------------------------------------------------------------------------
create or replace function public.is_admin()
returns boolean
language sql stable security definer set search_path = public
as $$
  select exists (select 1 from public.profiles where id = auth.uid() and role = 'admin');
$$;

alter table public.profiles         enable row level security;
alter table public.instruments      enable row level security;
alter table public.bookings         enable row level security;
alter table public.run_logs         enable row level security;
alter table public.maintenance_logs enable row level security;
alter table public.rag_metadata     enable row level security;
alter table public.agent_decisions  enable row level security;
alter table public.work_orders      enable row level security;
alter table public.documents        enable row level security;

drop policy if exists profiles_self_read   on public.profiles;
drop policy if exists profiles_self_update on public.profiles;
drop policy if exists profiles_admin_all   on public.profiles;
create policy profiles_self_read   on public.profiles for select using (id = auth.uid() or public.is_admin());
create policy profiles_self_update on public.profiles for update using (id = auth.uid());
create policy profiles_admin_all   on public.profiles for all    using (public.is_admin()) with check (public.is_admin());

drop policy if exists instruments_read  on public.instruments;
drop policy if exists instruments_admin on public.instruments;
create policy instruments_read  on public.instruments for select using (auth.role() = 'authenticated');
create policy instruments_admin on public.instruments for all    using (public.is_admin()) with check (public.is_admin());

drop policy if exists bookings_owner_read   on public.bookings;
drop policy if exists bookings_owner_insert on public.bookings;
drop policy if exists bookings_owner_update on public.bookings;
drop policy if exists bookings_admin_delete on public.bookings;
create policy bookings_owner_read   on public.bookings for select using (user_id = auth.uid() or public.is_admin());
create policy bookings_owner_insert on public.bookings for insert with check (user_id = auth.uid() or public.is_admin());
create policy bookings_owner_update on public.bookings for update using (user_id = auth.uid() or public.is_admin());
create policy bookings_admin_delete on public.bookings for delete using (public.is_admin());

drop policy if exists run_logs_read  on public.run_logs;
drop policy if exists run_logs_admin on public.run_logs;
create policy run_logs_read  on public.run_logs for select using (auth.role() = 'authenticated');
create policy run_logs_admin on public.run_logs for all    using (public.is_admin()) with check (public.is_admin());

drop policy if exists maint_read  on public.maintenance_logs;
drop policy if exists maint_admin on public.maintenance_logs;
create policy maint_read  on public.maintenance_logs for select using (auth.role() = 'authenticated');
create policy maint_admin on public.maintenance_logs for all    using (public.is_admin()) with check (public.is_admin());

drop policy if exists rag_meta_read  on public.rag_metadata;
drop policy if exists rag_meta_admin on public.rag_metadata;
create policy rag_meta_read  on public.rag_metadata for select using (auth.role() = 'authenticated');
create policy rag_meta_admin on public.rag_metadata for all    using (public.is_admin()) with check (public.is_admin());

drop policy if exists decisions_admin on public.agent_decisions;
create policy decisions_admin on public.agent_decisions for select using (public.is_admin());

drop policy if exists work_orders_read  on public.work_orders;
drop policy if exists work_orders_admin on public.work_orders;
create policy work_orders_read  on public.work_orders for select using (auth.role() = 'authenticated');
create policy work_orders_admin on public.work_orders for all    using (public.is_admin()) with check (public.is_admin());

drop policy if exists documents_read on public.documents;
create policy documents_read on public.documents for select using (auth.role() = 'authenticated');

-- ---------------------------------------------------------------------------
-- 0004 · Realtime
-- ---------------------------------------------------------------------------
alter table public.bookings        replica identity full;
alter table public.work_orders     replica identity full;
alter table public.agent_decisions replica identity full;
alter table public.instruments     replica identity full;

do $$
begin
  if not exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    create publication supabase_realtime;
  end if;
end $$;

-- add tables (ignore "already member" errors on re-run)
do $$
begin
  begin alter publication supabase_realtime add table public.bookings;        exception when duplicate_object then null; end;
  begin alter publication supabase_realtime add table public.work_orders;     exception when duplicate_object then null; end;
  begin alter publication supabase_realtime add table public.agent_decisions; exception when duplicate_object then null; end;
  begin alter publication supabase_realtime add table public.instruments;     exception when duplicate_object then null; end;
end $$;

-- ---------------------------------------------------------------------------
-- 0005 · Automation audit trail (realtime)
-- ---------------------------------------------------------------------------
create table if not exists public.automation_events (
  id          bigint generated always as identity primary key,
  kind        text not null,             -- email | booking_sync | work_order
  status      text not null,             -- sent | queued | failed | created
  target      text,
  detail      text,
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

alter table public.automation_events replica identity full;
do $$
begin
  begin alter publication supabase_realtime add table public.automation_events;
  exception when duplicate_object then null; end;
end $$;
