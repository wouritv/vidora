create extension if not exists pgcrypto;

create table if not exists public.social_accounts (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    user_id uuid not null references auth.users(id) on delete cascade,
    platform text not null,
    access_token_encrypted text not null,
    refresh_token_encrypted text,
    platform_user_id text,
    platform_account_name text,
    scopes text,
    expires_at timestamptz,
    constraint social_accounts_user_platform_key unique (user_id, platform)
);

create table if not exists public.publish_jobs (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    user_id uuid not null references auth.users(id) on delete cascade,
    platform text not null,
    external_id text,
    status text not null default 'queued',
    error_message text,
    completed_at timestamptz,
    scheduled_for timestamptz,
    timezone text,
    payload jsonb not null default '{}'::jsonb
);

create index if not exists idx_social_accounts_user_platform on public.social_accounts(user_id, platform);
create index if not exists idx_publish_jobs_user_created on public.publish_jobs(user_id, created_at desc);
create index if not exists idx_publish_jobs_status on public.publish_jobs(status);
create index if not exists idx_publish_jobs_scheduled on public.publish_jobs(scheduled_for) where scheduled_for is not null;

create or replace function public.set_social_accounts_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_social_accounts_updated_at on public.social_accounts;
create trigger trg_social_accounts_updated_at
before update on public.social_accounts
for each row execute function public.set_social_accounts_updated_at();

alter table public.social_accounts enable row level security;
alter table public.publish_jobs enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'social_accounts' and policyname = 'social_accounts_select_own'
  ) then
    create policy social_accounts_select_own on public.social_accounts
      for select using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'social_accounts' and policyname = 'social_accounts_insert_own'
  ) then
    create policy social_accounts_insert_own on public.social_accounts
      for insert with check (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'social_accounts' and policyname = 'social_accounts_update_own'
  ) then
    create policy social_accounts_update_own on public.social_accounts
      for update using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'social_accounts' and policyname = 'social_accounts_delete_own'
  ) then
    create policy social_accounts_delete_own on public.social_accounts
      for delete using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'publish_jobs' and policyname = 'publish_jobs_select_own'
  ) then
    create policy publish_jobs_select_own on public.publish_jobs
      for select using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'publish_jobs' and policyname = 'publish_jobs_insert_own'
  ) then
    create policy publish_jobs_insert_own on public.publish_jobs
      for insert with check (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'publish_jobs' and policyname = 'publish_jobs_update_own'
  ) then
    create policy publish_jobs_update_own on public.publish_jobs
      for update using (auth.uid() = user_id);
  end if;
end $$;

