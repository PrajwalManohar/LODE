-- 0007 · Work-order actions: team assignment + review comments
-- Additive, non-destructive. Safe to re-run.
alter table public.work_orders add column if not exists assigned_team text;
alter table public.work_orders add column if not exists notes jsonb default '[]'::jsonb;
