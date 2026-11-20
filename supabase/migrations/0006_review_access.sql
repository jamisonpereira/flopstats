-- Review screen access (stage 1, Task 16). Only signed-in users whose email is listed in
-- settings.admin_emails (a JSON array) may read and act on the review tables.

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce(
    (auth.jwt() ->> 'email') in (
      select jsonb_array_elements_text(s.value) from public.settings s where s.key = 'admin_emails'
    ),
    false)
$$;
revoke execute on function public.is_admin() from public, anon;
grant execute on function public.is_admin() to authenticated;

do $$
declare
  t text;
begin
  -- read access for the review screen
  foreach t in array array[
    'review_items', 'incidents', 'incident_players', 'clips', 'reviews', 'match_lineups', 'players',
    'matches', 'teams', 'videos', 'detection_runs', 'match_events', 'external_refs'
  ] loop
    execute format('create policy admin_select on public.%I for select to authenticated using ((select public.is_admin()))', t);
  end loop;
  -- what review decisions change
  foreach t in array array['review_items', 'incidents', 'incident_players', 'videos', 'external_refs', 'match_events'] loop
    execute format('create policy admin_update on public.%I for update to authenticated using ((select public.is_admin())) with check ((select public.is_admin()))', t);
  end loop;
end;
$$;

create policy admin_insert on public.reviews for insert to authenticated with check ((select public.is_admin()));
