-- Bowling Bro' league sheets: a league's weekly results, visible only to bowlers on its roster.
-- Run once in the Supabase SQL editor. Safe to run again.
-- The roster and the weekly data are added separately (they hold league members' names and scores,
-- so they are not kept in this public repo).

create table if not exists public.bb_league_members (
  league_id text not null,
  email text not null,                 -- lower case; the email the bowler signs in with
  bowler_id integer not null,          -- the bowler's ID on the league sheet
  name text,
  admin boolean not null default false,
  primary key (league_id, email)
);
create table if not exists public.bb_league_weeks (
  league_id text not null,
  week integer not null,
  data jsonb not null,                 -- that week's sheet: bowlers, results, standings, schedule
  published_at timestamptz not null default now(),
  primary key (league_id, week)
);
alter table public.bb_league_members enable row level security;
alter table public.bb_league_weeks enable row level security;

-- the leagues the signed-in bowler is on (and runs), looked up by their sign-in email
create or replace function public.bb_my_leagues() returns setof text
language sql stable security definer set search_path = public as $$
  select league_id from public.bb_league_members where email = lower(coalesce(auth.jwt() ->> 'email', ''))
$$;
create or replace function public.bb_my_admin_leagues() returns setof text
language sql stable security definer set search_path = public as $$
  select league_id from public.bb_league_members where email = lower(coalesce(auth.jwt() ->> 'email', '')) and admin
$$;
revoke all on function public.bb_my_leagues() from public;
revoke all on function public.bb_my_admin_leagues() from public;
grant execute on function public.bb_my_leagues() to authenticated;
grant execute on function public.bb_my_admin_leagues() to authenticated;

-- read only from the app: a bowler sees their own roster row (the admin sees the whole roster),
-- and the weeks of their own league. Nobody else gets anything. Changes are made here in SQL.
drop policy if exists "roster: own row or admin" on public.bb_league_members;
create policy "roster: own row or admin" on public.bb_league_members for select to authenticated
  using (email = lower(coalesce(auth.jwt() ->> 'email', '')) or league_id in (select public.bb_my_admin_leagues()));
drop policy if exists "weeks: own league" on public.bb_league_weeks;
create policy "weeks: own league" on public.bb_league_weeks for select to authenticated
  using (league_id in (select public.bb_my_leagues()));
