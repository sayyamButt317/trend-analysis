-- Trend discovery results
-- Run in Supabase SQL Editor or: psql "$DATABASE_URL" -f db/migrations/003_trends.sql

create table if not exists public.trends (
    id uuid primary key default gen_random_uuid(),
    prompt_id uuid references public.prompts (id) on delete set null,
    agent_type text not null default 'trend',
    status text not null default 'failed',
    success boolean not null default false,
    error text,
    platform text not null default 'instagram',
    country text,
    category text,
    discovery_source text,
    summary text,
    post_count integer not null default 0,
    viral_post_count integer not null default 0,
    duration_sec numeric(10, 3),
    discovered_influencers jsonb not null default '[]'::jsonb,
    hashtags jsonb not null default '[]'::jsonb,
    topics jsonb not null default '[]'::jsonb,
    trend_scores jsonb not null default '[]'::jsonb,
    trend_groups jsonb not null default '[]'::jsonb,
    viral_posts jsonb not null default '[]'::jsonb,
    viral_sounds jsonb not null default '[]'::jsonb,
    viral_categories jsonb not null default '[]'::jsonb,
    audio_summary jsonb not null default '[]'::jsonb,
    result jsonb not null default '{}'::jsonb,
    config jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_trends_created_at on public.trends (created_at desc);
create index if not exists idx_trends_agent_type on public.trends (agent_type);
create index if not exists idx_trends_platform on public.trends (platform);
create index if not exists idx_trends_country on public.trends (country);
create index if not exists idx_trends_category on public.trends (category);
create index if not exists idx_trends_status on public.trends (status);
create index if not exists idx_trends_prompt_id on public.trends (prompt_id);

alter table public.trends enable row level security;

drop policy if exists "trends_anon_insert" on public.trends;
drop policy if exists "trends_anon_select" on public.trends;

create policy "trends_anon_insert"
    on public.trends for insert to anon, authenticated
    with check (true);

create policy "trends_anon_select"
    on public.trends for select to anon, authenticated
    using (true);
