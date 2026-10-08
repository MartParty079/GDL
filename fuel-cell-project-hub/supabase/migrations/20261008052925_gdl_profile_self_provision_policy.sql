
drop policy if exists profiles_insert_self_user on public.profiles;
create policy profiles_insert_self_user
on public.profiles
for insert
to authenticated
with check (
  (select auth.uid()) = id
  and role = 'user'
  and active = true
  and email = (select auth.jwt() ->> 'email')
);
