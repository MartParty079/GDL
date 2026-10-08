-- The provider can only provision an app account after a server-side invite.
-- Public signup cannot create an active research-team profile.
create or replace function hub_private.invited_account() returns boolean
language sql stable security definer set search_path = '' as $$
  select (select auth.uid()) is not null and exists(
    select 1 from auth.users where id=(select auth.uid()) and invited_at is not null
  );
$$;
revoke all on function hub_private.invited_account() from public,anon;
grant execute on function hub_private.invited_account() to authenticated;
drop policy profiles_insert_self_user on public.profiles;
create policy profiles_insert_self_user on public.profiles for insert to authenticated
with check ((select auth.uid())=id and role='user' and active=true
and email=(select auth.jwt()->>'email') and (select hub_private.invited_account()));
