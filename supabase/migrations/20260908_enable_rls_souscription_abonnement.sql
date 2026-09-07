-- Security audit finding H12: `souscription` and `abonnement` pre-date the
-- tracked migration history (created out-of-band), so whether Row Level
-- Security was ever enabled on them could not be confirmed from the repo.
-- This migration makes that protection explicit and self-documenting,
-- independent of how/when the tables were originally created.
--
-- Note: the backend API talks to Supabase using the service_role key, which
-- bypasses RLS entirely -- these policies do not protect against a bug in
-- the backend's own authorization checks. They matter as defense-in-depth
-- for any future code path (e.g. a frontend query using the anon key) that
-- might read these tables directly.

-- ---------------------------------------------------------------------
-- souscription: one row per user subscription/purchase (owner: `userid`)
-- ---------------------------------------------------------------------
alter table if exists public.souscription enable row level security;

drop policy if exists souscription_select_own on public.souscription;
create policy souscription_select_own
on public.souscription
for select
to authenticated
using (userid = auth.uid());

drop policy if exists souscription_insert_own on public.souscription;
create policy souscription_insert_own
on public.souscription
for insert
to authenticated
with check (userid = auth.uid());

drop policy if exists souscription_update_own on public.souscription;
create policy souscription_update_own
on public.souscription
for update
to authenticated
using (userid = auth.uid())
with check (userid = auth.uid());

drop policy if exists souscription_delete_own on public.souscription;
create policy souscription_delete_own
on public.souscription
for delete
to authenticated
using (userid = auth.uid());

-- ---------------------------------------------------------------------
-- abonnement: shared subscription-plan catalog, not user-owned data.
-- Every user needs to be able to read the available plans (e.g. to render
-- a pricing page); nobody should be able to write to it via anon/
-- authenticated roles -- only the backend's service_role key (which
-- bypasses RLS) manages these rows.
-- ---------------------------------------------------------------------
alter table if exists public.abonnement enable row level security;

drop policy if exists abonnement_select_all on public.abonnement;
create policy abonnement_select_all
on public.abonnement
for select
to authenticated, anon
using (true);

-- Deliberately no insert/update/delete policy: with RLS enabled and no
-- matching policy, those operations are denied by default for the anon
-- and authenticated roles.
