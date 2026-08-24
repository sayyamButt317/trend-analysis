-- Script generation agent results
-- Run in Supabase SQL Editor or: psql "$DATABASE_URL" -f db/migrations/008_script.sql

create extension if not exists "pgcrypto";

create table if not exists public.script (
    id uuid primary key default gen_random_uuid(),
    prompt_id uuid references public.prompts (id) on delete set null,
    company_id text,
    agent_type text not null default 'script_generation',
    status text not null default 'failed',
    success boolean not null default false,
    error text,
    summary text,
    content_type text not null default 'video',
    aspect_ratio text,
    style text,
    duration_seconds integer,
    platform text,
    scenes_count integer not null default 0,
    characters_count integer not null default 0,
    duration_sec numeric(10, 3),
    request_payload jsonb not null default '{}'::jsonb,
    result jsonb not null default '{}'::jsonb,
    project jsonb not null default '{}'::jsonb,
    script jsonb not null default '{}'::jsonb,
    characters jsonb not null default '[]'::jsonb,
    scenes jsonb not null default '[]'::jsonb,
    content_suggestion jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_script_prompt_id
    on public.script (prompt_id);

create index if not exists idx_script_created_at
    on public.script (created_at desc);

create index if not exists idx_script_status
    on public.script (status);

create index if not exists idx_script_company_id
    on public.script (company_id)
    where company_id is not null;

create index if not exists idx_script_agent_type
    on public.script (agent_type);

create index if not exists idx_script_content_type
    on public.script (content_type);

alter table public.script enable row level security;

drop policy if exists "script_anon_insert" on public.script;
drop policy if exists "script_anon_select" on public.script;
drop policy if exists "script_anon_delete" on public.script;

create policy "script_anon_insert"
    on public.script for insert to anon, authenticated
    with check (true);

create policy "script_anon_select"
    on public.script for select to anon, authenticated
    using (true);

create policy "script_anon_delete"
    on public.script for delete to anon, authenticated
    using (true);

comment on table public.script is
    'Script generation agent results (SUPABASE_TABLE_SCRIPT).';

comment on column public.script.company_id is
    'External company identifier supplied by the client for script lookups.';
