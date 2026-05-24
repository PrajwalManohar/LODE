-- LODE Phase 1 · Core schema (mirrors vein/db/database.py) + profiles/roles
-- Run order: 0001 → 0002 → 0003 → 0004

-- ---------------------------------------------------------------------------
-- profiles: one row per auth.users, carries role + lab metadata
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

-- Auto-create a profile when a user signs up. First user becomes admin.
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

-- ---------------------------------------------------------------------------
-- Domain tables
-- ---------------------------------------------------------------------------
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
