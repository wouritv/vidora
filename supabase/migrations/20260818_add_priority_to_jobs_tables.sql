alter table if exists public.jobs
    add column if not exists priority integer not null default 1;

alter table if exists public.jobs
    drop constraint if exists jobs_priority_check;

alter table if exists public.jobs
    add constraint jobs_priority_check check (priority between 1 and 3);

create index if not exists idx_jobs_queue_priority_created
    on public.jobs(queue_name, priority desc, created_at asc);

alter table if exists public.publish_jobs
    add column if not exists priority integer not null default 1;

alter table if exists public.publish_jobs
    drop constraint if exists publish_jobs_priority_check;

alter table if exists public.publish_jobs
    add constraint publish_jobs_priority_check check (priority between 1 and 3);

create index if not exists idx_publish_jobs_user_priority_created
    on public.publish_jobs(user_id, priority desc, created_at desc);

