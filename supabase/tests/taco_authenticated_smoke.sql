create temporary table taco_test_user on commit drop as
select id
from auth.users
where lower(coalesce(raw_app_meta_data ->> 'must_change_password', 'false')) <> 'true'
  and case
    when coalesce(raw_app_meta_data, '{}'::jsonb) ? 'must_change_password'
      then lower(coalesce(raw_app_meta_data ->> 'must_change_password', 'false')) <> 'true'
    else lower(coalesce(raw_user_meta_data ->> 'must_change_password', 'false')) <> 'true'
  end
limit 1;

grant select on taco_test_user to authenticated;
set role authenticated;
do $set_test_claims$
declare
  test_user_id uuid;
begin
  select id into test_user_id from taco_test_user;
  perform set_config('request.jwt.claims', json_build_object('sub', test_user_id)::text, false);
end;
$set_test_claims$;

select food.name, food.match_kind
from public.search_taco_foods('arroz integral cozido', null, 1, 0) as food;
