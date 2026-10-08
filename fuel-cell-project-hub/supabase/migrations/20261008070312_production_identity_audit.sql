-- Preserve existing users; latest activity is maintained without N+1 queries.
alter table public.profiles add column if not exists last_activity timestamptz;
update public.profiles p set last_activity=e.last_seen
from (select user_id,max(created_at) last_seen from public.activity_events group by user_id) e
where p.id=e.user_id;

create or replace function hub_private.login_seen() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  update public.profiles set
    last_activity=greatest(coalesce(last_activity,new.created_at),new.created_at),
    last_login=case when new.event_type='LOGIN' then greatest(coalesce(last_login,new.created_at),new.created_at) else last_login end
  where id=new.user_id;
  return new;
end;
$$;
revoke all on function hub_private.login_seen() from public,anon,authenticated;

create or replace function hub_private.keep_admin() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  perform pg_catalog.pg_advisory_xact_lock(710038);
  if old.role='admin' and old.active and (TG_OP='DELETE' or new.role<>'admin' or not new.active) then
    if not exists(select 1 from public.profiles where id<>old.id and role='admin' and active) then
      raise exception 'At least one active administrator must remain';
    end if;
  end if;
  if TG_OP='DELETE' then return old; end if;
  new.updated_at=now();
  return new;
end;
$$;
revoke all on function hub_private.keep_admin() from public,anon,authenticated;
create trigger profiles_keep_admin_delete before delete on public.profiles
for each row execute function hub_private.keep_admin();
