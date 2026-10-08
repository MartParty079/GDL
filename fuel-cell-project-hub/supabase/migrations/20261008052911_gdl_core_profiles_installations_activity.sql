
create table if not exists public.profiles (
  id uuid primary key,
  email text not null,
  display_name text,
  role text not null default 'user' check (role in ('admin','user')),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.installations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  install_id uuid not null unique,
  label text,
  platform text,
  app_version text,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);

create table if not exists public.activity_events (
  id bigint generated always as identity primary key,
  user_id uuid not null,
  install_id uuid,
  event_type text not null,
  entity_type text,
  entity_id text,
  entity_name text,
  app_version text,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists activity_events_user_created_idx
  on public.activity_events (user_id, created_at desc);

create index if not exists activity_events_type_created_idx
  on public.activity_events (event_type, created_at desc);

create index if not exists installations_user_idx
  on public.installations (user_id);

alter table public.profiles enable row level security;
alter table public.installations enable row level security;
alter table public.activity_events enable row level security;

drop policy if exists profiles_select_self on public.profiles;
create policy profiles_select_self
on public.profiles
for select
to authenticated
using ((select auth.uid()) = id);

drop policy if exists installations_select_self on public.installations;
create policy installations_select_self
on public.installations
for select
to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists installations_insert_self on public.installations;
create policy installations_insert_self
on public.installations
for insert
to authenticated
with check ((select auth.uid()) = user_id);

drop policy if exists installations_update_self on public.installations;
create policy installations_update_self
on public.installations
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

drop policy if exists activity_select_self on public.activity_events;
create policy activity_select_self
on public.activity_events
for select
to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists activity_insert_self on public.activity_events;
create policy activity_insert_self
on public.activity_events
for insert
to authenticated
with check ((select auth.uid()) = user_id);
