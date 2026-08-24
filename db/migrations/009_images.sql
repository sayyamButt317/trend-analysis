-- Image generation agent results
-- Run in Supabase SQL Editor or: psql "$DATABASE_URL" -f db/migrations/009_images.sql

create extension if not exists "pgcrypto";

create table if not exists public.images (
    id uuid primary key default gen_random_uuid(),
    prompt_id uuid references public.prompts (id) on delete set null,
    company_id text,
    agent_type text not null default 'image_generation',
    status text not null default 'failed',
    success boolean not null default false,
    error text,
    summary text,
    platform text,
    purpose text,
    aspect_ratio text,
    style text,
    images_count integer not null default 0,
    jobs_count integer not null default 0,
    duration_sec numeric(10, 3),
    request_payload jsonb not null default '{}'::jsonb,
    result jsonb not null default '{}'::jsonb,
    project jsonb not null default '{}'::jsonb,
    script jsonb not null default '{}'::jsonb,
    image_jobs jsonb not null default '[]'::jsonb,
    generated_images jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_images_prompt_id
    on public.images (prompt_id);

create index if not exists idx_images_created_at
    on public.images (created_at desc);

create index if not exists idx_images_status
    on public.images (status);

create index if not exists idx_images_company_id
    on public.images (company_id)
    where company_id is not null;

create index if not exists idx_images_agent_type
    on public.images (agent_type);

create index if not exists idx_images_platform
    on public.images (platform);

create index if not exists idx_images_purpose
    on public.images (purpose);

alter table public.images enable row level security;

drop policy if exists "images_anon_insert" on public.images;
drop policy if exists "images_anon_select" on public.images;
drop policy if exists "images_anon_delete" on public.images;

create policy "images_anon_insert"
    on public.images for insert to anon, authenticated
    with check (true);

create policy "images_anon_select"
    on public.images for select to anon, authenticated
    using (true);

create policy "images_anon_delete"
    on public.images for delete to anon, authenticated
    using (true);

comment on table public.images is
    'Image generation agent results (SUPABASE_TABLE_IMAGES).';

comment on column public.images.company_id is
    'External company identifier supplied by the client for image generation lookups.';

comment on column public.images.generated_images is
    'Array of generated still metadata (url, s3_url, s3_key, scene_number, etc.).';
