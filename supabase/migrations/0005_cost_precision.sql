-- A 20 s wide-net window costs about $0.000165; numeric(10,4) rounded each charge to $0.0002.
alter table public.cost_ledger alter column usd type numeric(14, 8);
alter table public.verifications alter column usd type numeric(14, 8);
