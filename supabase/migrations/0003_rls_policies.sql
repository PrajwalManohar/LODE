-- LODE Phase 1 · Row Level Security
-- Model: authenticated users read shared lab data; a user sees only their own
-- bookings; admins see/manage everything. The FastAPI backend uses the
-- service_role key, which bypasses RLS for trusted server writes.

-- Helper: is the current JWT an admin?
create or replace function public.is_admin()
returns boolean
language sql stable security definer set search_path = public
as $$
  select exists (
    select 1 from public.profiles
    where id = auth.uid() and role = 'admin'
  );
$$;

alter table public.profiles        enable row level security;
alter table public.instruments     enable row level security;
alter table public.bookings        enable row level security;
alter table public.run_logs        enable row level security;
alter table public.maintenance_logs enable row level security;
alter table public.rag_metadata    enable row level security;
alter table public.agent_decisions enable row level security;
alter table public.work_orders     enable row level security;
alter table public.documents       enable row level security;

-- profiles: see/update own row; admins see all
create policy profiles_self_read   on public.profiles for select using (id = auth.uid() or public.is_admin());
create policy profiles_self_update on public.profiles for update using (id = auth.uid());
create policy profiles_admin_all   on public.profiles for all    using (public.is_admin()) with check (public.is_admin());

-- instruments: any authenticated user reads; admins write
create policy instruments_read  on public.instruments for select using (auth.role() = 'authenticated');
create policy instruments_admin on public.instruments for all    using (public.is_admin()) with check (public.is_admin());

-- bookings: a user reads/creates their own; admins read/manage all
create policy bookings_owner_read   on public.bookings for select using (user_id = auth.uid() or public.is_admin());
create policy bookings_owner_insert on public.bookings for insert with check (user_id = auth.uid() or public.is_admin());
create policy bookings_owner_update on public.bookings for update using (user_id = auth.uid() or public.is_admin());
create policy bookings_admin_delete on public.bookings for delete using (public.is_admin());

-- Shared read-only-for-users, admin-write tables
create policy run_logs_read        on public.run_logs        for select using (auth.role() = 'authenticated');
create policy run_logs_admin       on public.run_logs        for all    using (public.is_admin()) with check (public.is_admin());

create policy maint_read           on public.maintenance_logs for select using (auth.role() = 'authenticated');
create policy maint_admin          on public.maintenance_logs for all    using (public.is_admin()) with check (public.is_admin());

create policy rag_meta_read        on public.rag_metadata    for select using (auth.role() = 'authenticated');
create policy rag_meta_admin       on public.rag_metadata    for all    using (public.is_admin()) with check (public.is_admin());

-- Governance artifacts: admins only (sensitive audit + maintenance)
create policy decisions_admin      on public.agent_decisions for select using (public.is_admin());
create policy work_orders_read     on public.work_orders     for select using (auth.role() = 'authenticated');
create policy work_orders_admin    on public.work_orders     for all    using (public.is_admin()) with check (public.is_admin());

-- documents: authenticated read (RAG passages); writes via service role only
create policy documents_read       on public.documents       for select using (auth.role() = 'authenticated');
