-- Bring anonymous_stories into the same "project" model already used by
-- reels and captions: one project per operation, listed/opened/deleted the
-- same way across all three modules (see 20260906_create_projects_table.sql
-- and 20260906_add_projects_to_reels_and_captions.sql).

-- Allow 'anonymous_story' as a project_type alongside the existing 'reel'
-- and 'caption'. The original check constraint has no explicit name, so it
-- got Postgres's default naming (<table>_<column>_check).
alter table public.projects
    drop constraint if exists projects_project_type_check;
alter table public.projects
    add constraint projects_project_type_check
    check (project_type in ('reel', 'caption', 'anonymous_story'));

-- Give anonymous_stories.project_id the same FK + cascade-on-delete
-- semantics reels/captions already have, so deleting a project also
-- deletes its story row at the database level (app.py's soft_delete_project
-- also deletes it explicitly first, same as it does for reels/captions --
-- this FK is the safety net, not the primary mechanism).
do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'anonymous_stories_project_id_fkey'
  ) then
    alter table public.anonymous_stories
      add constraint anonymous_stories_project_id_fkey
      foreign key (project_id) references public.projects(id) on delete cascade;
  end if;
end $$;
