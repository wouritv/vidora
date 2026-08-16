create extension if not exists pgcrypto;

create table if not exists public.jobs (
    id uuid primary key default gen_random_uuid(),
    status text not null default 'created',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    user_id uuid not null references auth.users(id) on delete cascade,
    job_type text not null,
    attempts integer not null default 0,
    max_attempts integer not null default 2,
    progress integer not null default 0,
    current_step text,
    error_code text,
    error_message text,
    queue_name text not null default 'main',
    pipeline_name text,
    reserved_quota numeric(12, 4) not null default 0,
    consumed_quota numeric(12, 4) not null default 0,
    estimated_cost_usd numeric(12, 6) not null default 0,
    actual_cost_usd numeric(12, 6) not null default 0,
    job_data jsonb not null default '{}'::jsonb,
    result_data jsonb not null default '{}'::jsonb
);

create table if not exists public.job_logs (
    id bigserial primary key,
    job_id uuid not null references public.jobs(id) on delete cascade,
    level text not null default 'INFO',
    message text not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_jobs_user_created on public.jobs(user_id, created_at desc);
create index if not exists idx_jobs_status on public.jobs(status);
create index if not exists idx_jobs_queue_status on public.jobs(queue_name, status);
create index if not exists idx_job_logs_job_created on public.job_logs(job_id, created_at asc);

create or replace function public.set_jobs_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_jobs_updated_at on public.jobs;
create trigger trg_jobs_updated_at
before update on public.jobs
for each row execute function public.set_jobs_updated_at();

alter table public.jobs enable row level security;
alter table public.job_logs enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'jobs' and policyname = 'jobs_select_own'
  ) then
    create policy jobs_select_own on public.jobs
      for select using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'jobs' and policyname = 'jobs_insert_own'
  ) then
    create policy jobs_insert_own on public.jobs
      for insert with check (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'jobs' and policyname = 'jobs_update_own'
  ) then
    create policy jobs_update_own on public.jobs
      for update using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'job_logs' and policyname = 'job_logs_select_own'
  ) then
    create policy job_logs_select_own on public.job_logs
      for select using (
        exists (
          select 1
          from public.jobs j
          where j.id = job_logs.job_id and j.user_id = auth.uid()
        )
      );
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'job_logs' and policyname = 'job_logs_insert_own'
  ) then
    create policy job_logs_insert_own on public.job_logs
      for insert with check (
        exists (
          select 1
          from public.jobs j
          where j.id = job_logs.job_id and j.user_id = auth.uid()
        )
      );
  end if;
end $$;

