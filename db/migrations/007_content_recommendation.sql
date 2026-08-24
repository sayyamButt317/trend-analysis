-- Content recommendation agent results
-- Run in Supabase SQL Editor or: psql "$DATABASE_URL" -f db/migrations/007_content_recommendation.sql

create extension if not exists "pgcrypto";

create table if not exists public.content_recommendation (
    id uuid primary key default gen_random_uuid(),
    prompt_id uuid references public.prompts (id) on delete set null,
    company_id text,
    company_name text,
    agent_type text not null default 'content_recommendation',
    status text not null default 'failed',
    success boolean not null default false,
    error text,
    warning text,
    summary text,
    platforms text[] not null default '{}'::text[],
    calendar_days integer,
    idea_count integer,
    ideas_count integer not null default 0,
    calendar_items_count integer not null default 0,
    duration_sec numeric(10, 3),
    request_payload jsonb not null default '{}'::jsonb,
    result jsonb not null default '{}'::jsonb,
    content_calendar jsonb not null default '{}'::jsonb,
    content_ideas jsonb not null default '[]'::jsonb,
    recommendation jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_content_recommendation_prompt_id
    on public.content_recommendation (prompt_id);

create index if not exists idx_content_recommendation_created_at
    on public.content_recommendation (created_at desc);

create index if not exists idx_content_recommendation_status
    on public.content_recommendation (status);

create index if not exists idx_content_recommendation_company_id
    on public.content_recommendation (company_id)
    where company_id is not null;

create index if not exists idx_content_recommendation_agent_type
    on public.content_recommendation (agent_type);

alter table public.content_recommendation enable row level security;

drop policy if exists "content_recommendation_anon_insert" on public.content_recommendation;
drop policy if exists "content_recommendation_anon_select" on public.content_recommendation;
drop policy if exists "content_recommendation_anon_delete" on public.content_recommendation;

create policy "content_recommendation_anon_insert"
    on public.content_recommendation for insert to anon, authenticated
    with check (true);

create policy "content_recommendation_anon_select"
    on public.content_recommendation for select to anon, authenticated
    using (true);

create policy "content_recommendation_anon_delete"
    on public.content_recommendation for delete to anon, authenticated
    using (true);

comment on table public.content_recommendation is
    'Content recommendation agent results (SUPABASE_TABLE_CONTENT_RECOMMENDATION).';

comment on column public.content_recommendation.company_id is
    'External company identifier supplied by the client for content recommendation lookups.';
