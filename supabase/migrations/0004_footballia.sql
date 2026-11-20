-- Footballia listings (stage 1, Task 9): external_refs gains a payload for source metadata,
-- e.g. a footballia listing's first_seen_at (posting-lag measurement), teams and date.
alter table public.external_refs add column payload jsonb;
