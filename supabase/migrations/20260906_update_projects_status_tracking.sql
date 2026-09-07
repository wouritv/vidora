-- Update projects table to ensure all status tracking columns are present
-- This migration verifies completed_at timestamp for tracking when projects finish

-- Verify projects table has all required columns
-- (The base table was created in 20260906_create_projects_table.sql)

-- Ensure completed_at column exists and is properly indexed
alter table public.projects
add column if not exists completed_at timestamptz;

-- Create index for completed projects queries
create index if not exists idx_projects_completed_at on public.projects (completed_at desc)
where status in ('completed', 'failed', 'cancelled');

-- Create composite index for user + status + date queries (useful for filtering projects by user and status)
create index if not exists idx_projects_user_status_date on public.projects (user_id, status, created_at desc);

-- Add comment to explain the status field
comment on column public.projects.status is
'Project processing status: processing (active), completed (done), failed (error), or cancelled (user stopped)';

comment on column public.projects.completed_at is
'Timestamp when project transitioned to terminal state (completed, failed, or cancelled)';

