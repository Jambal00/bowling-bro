-- Bowling Bro': screen-time logging. One row per visit to a screen (or a tab inside one).
-- The app can only add rows for the signed-in bowler; nobody can read them from the app.
-- Pete reads them through the Supabase connector (service access) for the usage dashboard.

create table if not exists public.bb_screen_views (
  id          bigint generated always as identity primary key,
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  session_id  text not null check (length(session_id) <= 64),
  screen      text not null check (length(screen) <= 40),
  tab         text check (length(tab) <= 60),
  started_at  timestamptz not null,
  seconds     integer not null check (seconds between 1 and 1800),
  app_version text check (length(app_version) <= 32),
  created_at  timestamptz not null default now()
);

create index if not exists bb_screen_views_started_idx on public.bb_screen_views (started_at);
create index if not exists bb_screen_views_user_idx on public.bb_screen_views (user_id, started_at);

alter table public.bb_screen_views enable row level security;

revoke all on public.bb_screen_views from anon, authenticated;
grant insert (session_id, screen, tab, started_at, seconds, app_version) on public.bb_screen_views to authenticated;

drop policy if exists "insert own screen views" on public.bb_screen_views;
create policy "insert own screen views" on public.bb_screen_views
  for insert to authenticated
  with check (user_id = auth.uid() and started_at > now() - interval '14 days' and started_at < now() + interval '5 minutes');
