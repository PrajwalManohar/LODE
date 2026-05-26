-- ===========================================================================
-- 0006 · User-scoped RLS for realtime data flow
--
-- Realtime push respects RLS. The 0003 policies only let admins SELECT from
-- automation_events, so a non-admin user's MyRequests page would never
-- receive HITL state changes via realtime — only via the 15s REST polling
-- fallback. Same story for bookings: the existing policy keys on user_id,
-- but the backend currently inserts bookings with user_id = NULL (we identify
-- the researcher by email coming from the form). This migration:
--
--   1. Adds automation_events_user_own — SELECT by users whose profile email
--      matches payload->>'researcher_email' on HITL rows.
--   2. Adds bookings_owner_by_email — SELECT/UPDATE by users whose profile
--      email matches bookings.researcher_email, in addition to the existing
--      user_id-based policy. Multiple permissive policies are OR'd.
--   3. Backfills bookings.user_id for any existing rows where researcher_email
--      matches a profile (so legacy data flows correctly too).
-- ===========================================================================

-- 1) Users see their own HITL events in automation_events.
drop policy if exists automation_events_user_own on public.automation_events;
create policy automation_events_user_own on public.automation_events
  for select using (
    kind = 'hitl_request'
    and exists (
      select 1 from public.profiles p
      where p.id = auth.uid()
        and p.email is not null
        and p.email = payload->>'researcher_email'
    )
  );

-- 2) Users see + update their own bookings by email (in addition to user_id).
drop policy if exists bookings_owner_by_email_read on public.bookings;
create policy bookings_owner_by_email_read on public.bookings
  for select using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()
        and p.email is not null
        and p.email = bookings.researcher_email
    )
  );

-- 3) Backfill user_id on legacy bookings where the email matches a profile.
update public.bookings b
   set user_id = p.id
  from public.profiles p
 where b.user_id is null
   and b.researcher_email is not null
   and p.email = b.researcher_email;
