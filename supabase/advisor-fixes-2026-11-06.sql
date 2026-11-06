-- Supabase advisor clean-up, run 2026-11-06.
-- 1. The league helper functions are for signed-in bowlers only (every league policy is "to authenticated").
revoke execute on function public.bb_my_leagues() from public, anon;
revoke execute on function public.bb_my_admin_leagues() from public, anon;
grant execute on function public.bb_my_leagues() to authenticated;
grant execute on function public.bb_my_admin_leagues() to authenticated;

-- 2. Check the signed-in user once per query, not once per row.
alter policy "own reads: insert" on public.bb_photo_reads with check (user_id = (select auth.uid()));
alter policy "own reads: select" on public.bb_photo_reads using (user_id = (select auth.uid()));
alter policy "roster: own row or admin" on public.bb_league_members
  using (email = lower(coalesce((select auth.jwt()) ->> 'email', '')) or league_id in (select public.bb_my_admin_leagues()));
alter policy "insert own screen views" on public.bb_screen_views
  with check (user_id = (select auth.uid()) and started_at > now() - interval '14 days' and started_at < now() + interval '5 minutes');
