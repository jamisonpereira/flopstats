-- The AI's own verdict, kept when Jamison's review changes incidents.status (precision needs it).
alter table public.incidents add column ai_status text
  check (ai_status in ('confirmed', 'review', 'rejected', 'ai_judged'));
update public.incidents set ai_status = status where ai_status is null;
