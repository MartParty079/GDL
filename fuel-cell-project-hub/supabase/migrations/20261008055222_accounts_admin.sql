-- Extend the inspected existing tables; preserve all accounts and research data.
create schema if not exists hub_private;
revoke all on schema hub_private from public, anon, authenticated;
grant usage on schema hub_private to authenticated;
alter table public.profiles add column if not exists last_login timestamptz;
alter table public.installations drop constraint installations_install_id_key;
alter table public.installations add constraint installations_user_install_key unique(user_id,install_id);
create index if not exists activity_user_created_idx on public.activity_events(user_id,created_at desc);
create index if not exists activity_created_idx on public.activity_events(created_at desc);
create index if not exists installations_user_idx on public.installations(user_id);

create or replace function hub_private.active_account() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists(select 1 from public.profiles where id=(select auth.uid()) and active);
$$;
revoke all on function hub_private.active_account() from public;
grant execute on function hub_private.active_account() to authenticated;

-- Enforce the invariant even across concurrent admin requests. This trigger
-- runs only on server writes: desktop callers have no profile UPDATE policy.
create or replace function hub_private.keep_admin() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  perform pg_catalog.pg_advisory_xact_lock(710038);
  if old.role='admin' and old.active and (new.role<>'admin' or not new.active) then
    if not exists(select 1 from public.profiles where id<>old.id and role='admin' and active) then
      raise exception 'At least one active administrator must remain';
    end if;
  end if;
  new.updated_at=now();
  return new;
end;
$$;
revoke all on function hub_private.keep_admin() from public,anon,authenticated;
create trigger profiles_keep_admin before update on public.profiles
for each row execute function hub_private.keep_admin();

create or replace function hub_private.login_seen() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.event_type='LOGIN' then
    update public.profiles set last_login=greatest(coalesce(last_login,new.created_at),new.created_at)
    where id=new.user_id;
  end if;
  return new;
end;
$$;
revoke all on function hub_private.login_seen() from public,anon,authenticated;
create trigger activity_login_seen after insert on public.activity_events
for each row execute function hub_private.login_seen();

drop policy installations_update_self on public.installations;
drop policy installations_insert_self on public.installations;
drop policy installations_select_self on public.installations;
create policy installations_select_self on public.installations for select to authenticated
using ((select auth.uid())=user_id and (select hub_private.active_account()));
create policy installations_insert_self on public.installations for insert to authenticated
with check ((select auth.uid())=user_id and (select hub_private.active_account()));
create policy installations_update_self on public.installations for update to authenticated
using ((select auth.uid())=user_id and (select hub_private.active_account()))
with check ((select auth.uid())=user_id and (select hub_private.active_account()));
drop policy activity_insert_self on public.activity_events;
drop policy activity_select_self on public.activity_events;
create policy activity_insert_self on public.activity_events for insert to authenticated
with check ((select auth.uid())=user_id and (select hub_private.active_account())
and event_type in ('LOGIN','LOGOUT','APP_STARTED','APP_UPDATED','FILE_OPENED','FILE_LOCATION_OPENED',
'SAMPLE_VIEWED','SAMPLE_CREATED','SAMPLE_UPDATED','EXPERIMENT_VIEWED','EXPERIMENT_CREATED','EXPERIMENT_UPDATED',
'REPORT_OPENED','IMAGE_VIEWED','METADATA_UPDATED','TAG_CHANGED','INDEX_STARTED','INDEX_COMPLETED','INDEX_FAILED',
'LEGACY_FILE_VIEWED','LEGACY_FILE_IMPORTED','SETTINGS_CHANGED')
and octet_length(details::text)<=2048 and length(entity_name)<=180);
create policy activity_select_self on public.activity_events for select to authenticated
using ((select auth.uid())=user_id and (select hub_private.active_account()));
alter table public.profiles enable row level security;
alter table public.installations enable row level security;
alter table public.activity_events enable row level security;
revoke all on public.profiles,public.installations,public.activity_events from anon;
grant select,insert on public.profiles to authenticated;
revoke update,delete on public.profiles from authenticated;
grant select,insert,update on public.installations to authenticated;
grant select,insert on public.activity_events to authenticated;
grant usage on sequence public.activity_events_id_seq to authenticated;
