-- Table grants for Supabase's API roles, stated outright instead of relying on the project's
-- default privileges (the hosted project gives new tables none, so the review screen read nothing).
-- RLS is on for every public table; the policies in 0006/0008 still limit `authenticated` to admins.
-- `anon` gets nothing until the public site adds its own read policies.

revoke all on all tables in schema public from anon;
revoke all on all sequences in schema public from anon;

grant usage on schema public to authenticated, service_role;
grant select, insert, update on all tables in schema public to authenticated;
grant select, insert, update, delete on all tables in schema public to service_role;
grant usage, select on all sequences in schema public to authenticated, service_role;

alter default privileges in schema public revoke all on tables from anon;
alter default privileges in schema public revoke all on sequences from anon;
alter default privileges in schema public grant select, insert, update on tables to authenticated;
alter default privileges in schema public grant select, insert, update, delete on tables to service_role;
alter default privileges in schema public grant usage, select on sequences to authenticated, service_role;
