-- Structured injury fields for AI actions and clinical condition cards.

alter table public.patient_health_conditions
  add column if not exists injury_local text,
  add column if not exists started_at date,
  add column if not exists notes text,
  add column if not exists origin text,
  add column if not exists recommendations text;

create index if not exists patient_health_conditions_injury_local_idx
  on public.patient_health_conditions (patient_id, injury_local)
  where condition_type = 'injury';
