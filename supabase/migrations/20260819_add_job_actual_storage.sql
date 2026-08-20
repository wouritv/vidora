-- Track actual reel/caption storage consumption directly on jobs.

alter table if exists public.jobs
    add column if not exists actual_storage_gb numeric(14, 6) not null default 0;

