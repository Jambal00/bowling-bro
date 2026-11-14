-- Bowling Bro': team photo. One scoreboard photo saves games for teammates.
-- A row is one game for one bowler, sent by a teammate. Only teams switched on in
-- bb_team_photo_teams can use it, and only within their own team (from the latest league sheet).

create table if not exists public.bb_team_photo_teams (
  league_id text not null,
  team      integer not null,
  primary key (league_id, team)
);
alter table public.bb_team_photo_teams enable row level security;
revoke all on public.bb_team_photo_teams from anon, authenticated;
insert into public.bb_team_photo_teams (league_id, team) values ('tme-2026-27', 7) on conflict do nothing;

-- the bowler ids on the caller's team in the latest sheet, if that team is switched on
create or replace function public.bb_my_team_bowlers(p_league text)
returns setof integer
language sql stable security definer set search_path = public
as $$
  with me as (
    select bowler_id from public.bb_league_members
    where league_id = p_league and email = lower(coalesce((select auth.jwt()) ->> 'email', ''))
  ),
  lw as (select data from public.bb_league_weeks where league_id = p_league order by week desc limit 1),
  bw as (
    select (b ->> 'id')::int as id, coalesce((b ->> 'rosterTeam')::int, (b ->> 'team')::int) as team
    from lw, jsonb_array_elements(lw.data -> 'bowlers') b
  ),
  myteam as (select bw.team from bw join me on me.bowler_id = bw.id)
  select bw.id from bw, myteam
  where bw.team = myteam.team
    and exists (select 1 from public.bb_team_photo_teams t where t.league_id = p_league and t.team = myteam.team)
$$;
revoke execute on function public.bb_my_team_bowlers(text) from public, anon;
grant execute on function public.bb_my_team_bowlers(text) to authenticated;

create table if not exists public.bb_team_games (
  id          bigint generated always as identity primary key,
  league_id   text not null,
  game_date   date not null,
  game_no     integer not null check (game_no between 1 and 10),
  bowler_id   integer not null,
  game        jsonb not null check (pg_column_size(game) < 20000),
  from_user   uuid not null default auth.uid() references auth.users(id) on delete cascade,
  from_name   text check (length(from_name) <= 40),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (league_id, game_date, game_no, bowler_id)
);
create index if not exists bb_team_games_bowler_idx on public.bb_team_games (league_id, bowler_id, updated_at);

alter table public.bb_team_games enable row level security;
revoke all on public.bb_team_games from anon, authenticated;
grant select on public.bb_team_games to authenticated;
grant insert (league_id, game_date, game_no, bowler_id, game, from_name) on public.bb_team_games to authenticated;
grant update (game, from_user, from_name, updated_at) on public.bb_team_games to authenticated;

drop policy if exists "team games: read own team" on public.bb_team_games;
create policy "team games: read own team" on public.bb_team_games for select to authenticated
  using (bowler_id in (select public.bb_my_team_bowlers(league_id)));
drop policy if exists "team games: send to own team" on public.bb_team_games;
create policy "team games: send to own team" on public.bb_team_games for insert to authenticated
  with check (from_user = (select auth.uid()) and bowler_id in (select public.bb_my_team_bowlers(league_id))
              and game_date between current_date - 14 and current_date + 1);
drop policy if exists "team games: resend within own team" on public.bb_team_games;
create policy "team games: resend within own team" on public.bb_team_games for update to authenticated
  using (bowler_id in (select public.bb_my_team_bowlers(league_id)))
  with check (from_user = (select auth.uid()) and bowler_id in (select public.bb_my_team_bowlers(league_id)));

-- an upsert from the app sends every column, so the sender and the key columns need these too
-- (the policies above still pin from_user to the sender and keep rows within the team)
grant insert (from_user, updated_at) on public.bb_team_games to authenticated;
grant update (league_id, game_date, game_no, bowler_id) on public.bb_team_games to authenticated;
