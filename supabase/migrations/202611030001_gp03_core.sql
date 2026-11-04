-- GP-03. Apply to a fresh Supabase project with Supabase CLI migration up.
-- Auth owns auth.users. All application data lives in public.
create extension if not exists pgcrypto;

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  name text not null default '',
  timezone text not null default 'America/Sao_Paulo' check (length(timezone) between 1 and 100),
  whatsapp_number text unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (whatsapp_number is null or whatsapp_number ~ '^\+[1-9][0-9]{7,14}$')
);

create table public.notification_preferences (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  morning_time time not null default time '07:00',
  evening_time time not null default time '23:00',
  quiet_start time not null default time '00:00',
  quiet_end time not null default time '07:00',
  reminder_offsets_minutes integer[] not null default array[60],
  enabled boolean not null default true,
  check (array_position(reminder_offsets_minutes, null) is null),
  check (0 < all(reminder_offsets_minutes))
);

create table public.integrations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  provider text not null check (provider in ('google_calendar', 'whatsapp')),
  status text not null default 'disconnected' check (status in ('disconnected', 'pending', 'connected', 'failed')),
  external_account_id text,
  -- Opaque reference to server-side secret storage; no OAuth token in this table.
  credential_ref text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, user_id), unique (user_id, provider)
);

create table public.appointments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  title text not null check (length(btrim(title)) between 1 and 500),
  description text, location text,
  starts_at timestamptz not null,
  ends_at timestamptz,
  status text not null default 'scheduled' check (status in ('scheduled', 'cancelled', 'completed')),
  google_event_id text, google_calendar_id text,
  sync_status text not null default 'pending' check (sync_status in ('not_applicable', 'pending', 'synced', 'failed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, user_id),
  unique (user_id, google_calendar_id, google_event_id),
  check (ends_at is null or ends_at > starts_at)
);

create table public.tasks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  title text not null check (length(btrim(title)) between 1 and 500),
  description text,
  due_at timestamptz,
  priority text check (priority in ('low', 'medium', 'high')),
  category text,
  status text not null default 'pending' check (status in ('pending', 'completed', 'cancelled')),
  completed_at timestamptz,
  sync_to_calendar boolean not null default false,
  google_event_id text,
  sync_status text not null default 'not_applicable' check (sync_status in ('not_applicable', 'pending', 'synced', 'failed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, user_id),
  check ((status = 'completed') = (completed_at is not null)),
  check (sync_to_calendar or (google_event_id is null and sync_status = 'not_applicable'))
);

create table public.routines (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  title text not null check (length(btrim(title)) between 1 and 500),
  recurrence_rule jsonb not null check (jsonb_typeof(recurrence_rule) = 'object' and recurrence_rule <> '{}'::jsonb),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, user_id)
);

create table public.routine_occurrences (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  routine_id uuid not null,
  scheduled_for date not null,
  status text not null default 'pending' check (status in ('pending', 'completed', 'skipped')),
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (id, user_id),
  unique (routine_id, scheduled_for),
  foreign key (routine_id, user_id) references public.routines(id, user_id) on delete cascade,
  check ((status = 'completed') = (completed_at is not null))
);

create table public.reminders (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  appointment_id uuid, task_id uuid, routine_occurrence_id uuid,
  scheduled_at timestamptz not null,
  status text not null default 'pending' check (status in ('pending', 'claimed', 'sent', 'failed', 'cancelled')),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  sent_at timestamptz,
  idempotency_key text not null check (length(idempotency_key) between 1 and 128),
  created_at timestamptz not null default now(),
  unique (user_id, idempotency_key),
  foreign key (appointment_id, user_id) references public.appointments(id, user_id) on delete cascade,
  foreign key (task_id, user_id) references public.tasks(id, user_id) on delete cascade,
  foreign key (routine_occurrence_id, user_id) references public.routine_occurrences(id, user_id) on delete cascade,
  unique (id, user_id),
  check (num_nonnulls(appointment_id, task_id, routine_occurrence_id) = 1)
);

create table public.message_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  provider text not null,
  provider_message_id text not null check (length(provider_message_id) between 1 and 500),
  direction text not null check (direction in ('inbound', 'outbound')),
  status text not null default 'received' check (status in ('received', 'processed', 'failed', 'sent')),
  processed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (provider, provider_message_id, direction),
  unique (id, user_id)
);

create table public.activity_log (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  entity_type text not null, entity_id uuid not null,
  action text not null,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table public.idempotency_keys (
  user_id uuid not null references public.profiles(id) on delete cascade,
  key text not null check (length(key) between 1 and 128),
  request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
  status text not null default 'processing' check (status in ('processing', 'completed')),
  response_status integer check (response_status between 200 and 299),
  response_body jsonb,
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  primary key (user_id, key),
  check ((status = 'completed') = (completed_at is not null)),
  check (status <> 'completed' or response_status is not null)
);

create or replace function public.create_profile_for_auth_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles(id, name) values (new.id, coalesce(new.raw_user_meta_data ->> 'name', ''));
  insert into public.notification_preferences(user_id) values (new.id);
  return new;
end $$;
revoke all on function public.create_profile_for_auth_user() from public, anon, authenticated;
create trigger on_auth_user_created after insert on auth.users
for each row execute function public.create_profile_for_auth_user();
-- Supports projects that already have Auth users when this migration is applied.
insert into public.profiles(id, name)
select id, coalesce(raw_user_meta_data ->> 'name', '') from auth.users
on conflict (id) do nothing;
insert into public.notification_preferences(user_id)
select id from public.profiles on conflict (user_id) do nothing;

create index appointments_user_starts_idx on public.appointments(user_id, starts_at);
create index tasks_user_status_due_idx on public.tasks(user_id, status, due_at);
create index routines_user_active_idx on public.routines(user_id, active);
create index occurrences_user_date_idx on public.routine_occurrences(user_id, scheduled_for);
create index reminders_due_idx on public.reminders(scheduled_at) where status in ('pending', 'failed');
create index reminders_user_status_idx on public.reminders(user_id, status);
create index messages_user_created_idx on public.message_events(user_id, created_at desc);
create index activity_user_created_idx on public.activity_log(user_id, created_at desc);

-- The API uses an isolated NOLOGIN role plus request.jwt.claim.sub in each transaction.
-- Clients authenticated through the Supabase Data API have no direct table grants.
-- FORCE protects against accidental owner connections; service_role/BYPASSRLS still bypasses.
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'app_backend') then
    create role app_backend nologin noinherit nobypassrls;
  end if;
end $$;
grant app_backend to postgres;
grant usage on schema public, auth to app_backend;
do $$
declare t text;
begin
  foreach t in array array['profiles','notification_preferences','integrations','appointments','tasks','routines','routine_occurrences','reminders','message_events','activity_log','idempotency_keys'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force row level security', t);
    execute format('revoke all on public.%I from anon, authenticated', t);
    execute format('grant select, insert, update, delete on public.%I to app_backend', t);
    if t <> 'profiles' then
      execute format('create policy owner_only on public.%I for all to app_backend using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()))', t);
    end if;
  end loop;
end $$;
create policy owner_only on public.profiles for all to app_backend
  using (id = (select auth.uid())) with check (id = (select auth.uid()));
-- auth.users trigger executes as migration owner; FORCE RLS still permits bootstrap.
create policy profile_bootstrap on public.profiles for insert to postgres with check (true);
create policy preferences_bootstrap on public.notification_preferences for insert to postgres
  with check (true);
-- Backend must SET LOCAL ROLE app_backend before reading private data.
