-- A "who is this?" flop whose team was unknown has no flopper row yet; naming the player
-- in review creates it.
create policy admin_insert on public.incident_players for insert to authenticated with check ((select public.is_admin()));
