-- ClaimRadar BG persistent database schema
-- Apply this in Supabase SQL Editor or through the Supabase MCP apply_migration tool.

create extension if not exists pgcrypto;

create table if not exists public.claimradar_checks (
  id text primary key,
  title text,
  mode text,
  visibility text not null default 'public' check (visibility in ('public', 'private')),
  text_preview text,
  html text,
  copy_text text,
  content jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_claimradar_checks_created_at on public.claimradar_checks(created_at desc);
create index if not exists idx_claimradar_checks_visibility on public.claimradar_checks(visibility);
create index if not exists idx_claimradar_checks_mode on public.claimradar_checks(mode);

create table if not exists public.claimradar_feedback (
  id text primary key default encode(gen_random_bytes(6), 'hex'),
  kind text,
  name text,
  email text,
  comment text,
  content jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_claimradar_feedback_created_at on public.claimradar_feedback(created_at desc);
create index if not exists idx_claimradar_feedback_kind on public.claimradar_feedback(kind);

create table if not exists public.claimradar_abuse_reports (
  id text primary key default encode(gen_random_bytes(6), 'hex'),
  check_id text,
  reason text,
  details text,
  page text,
  content jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_claimradar_abuse_created_at on public.claimradar_abuse_reports(created_at desc);
create index if not exists idx_claimradar_abuse_check_id on public.claimradar_abuse_reports(check_id);

create table if not exists public.claimradar_visibility_events (
  event_id uuid primary key default gen_random_uuid(),
  id text not null,
  visibility text not null check (visibility in ('public', 'private')),
  content jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create index if not exists idx_claimradar_visibility_id_time on public.claimradar_visibility_events(id, updated_at desc);

create table if not exists public.claimradar_jobs (
  id text primary key,
  type text,
  status text,
  progress integer not null default 0,
  payload_preview jsonb not null default '{}'::jsonb,
  result jsonb,
  error text,
  content jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_claimradar_jobs_updated_at on public.claimradar_jobs(updated_at desc);
create index if not exists idx_claimradar_jobs_status on public.claimradar_jobs(status);
create index if not exists idx_claimradar_jobs_type on public.claimradar_jobs(type);

-- RLS is enabled for safety. The server app should connect with DATABASE_URL.
-- Do not expose the database password in frontend code.
alter table public.claimradar_checks enable row level security;
alter table public.claimradar_feedback enable row level security;
alter table public.claimradar_abuse_reports enable row level security;
alter table public.claimradar_visibility_events enable row level security;
alter table public.claimradar_jobs enable row level security;

-- Public read policy for public result pages can be enabled later if using Supabase REST directly.
-- The current FastAPI app reads through server-side DATABASE_URL, so public RLS policies are not required.
