-- Bowling Bro' photo scoring: one row per photo read, used for the daily limit and cost tracking.
-- Run once in the Supabase SQL editor.
create table if not exists public.bb_photo_reads (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade default auth.uid(),
  read_at timestamptz not null default now(),
  model text,
  input_tokens integer,
  output_tokens integer
);
create index if not exists bb_photo_reads_user_time on public.bb_photo_reads (user_id, read_at);
alter table public.bb_photo_reads enable row level security;
-- bowlers can see and add their own rows, but not change or delete them (so the limit holds)
drop policy if exists "own reads: select" on public.bb_photo_reads;
create policy "own reads: select" on public.bb_photo_reads for select to authenticated using (user_id = auth.uid());
drop policy if exists "own reads: insert" on public.bb_photo_reads;
create policy "own reads: insert" on public.bb_photo_reads for insert to authenticated with check (user_id = auth.uid());
