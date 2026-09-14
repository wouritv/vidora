-- The story-generation prompt (anonymous_stories.STORY_SYSTEM_PROMPT) now
-- takes PAGE_NAME (the community the story is written for) and
-- TARGET_LANGUAGE (the language to write it in) as user-supplied context
-- from the create-story form. Persist both on the story row so a later
-- regenerate reuses the same context instead of losing it.
alter table public.anonymous_stories
    add column if not exists page_name text,
    add column if not exists target_language text;
