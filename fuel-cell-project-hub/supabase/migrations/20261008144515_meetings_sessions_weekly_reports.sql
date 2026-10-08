-- Additive shared metadata only. Actual research files remain in shared storage.
create or replace function hub_private.is_admin() returns boolean
language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.profiles where id=(select auth.uid()) and active and role='admin');
$$;
revoke all on function hub_private.is_admin() from public,anon;
grant execute on function hub_private.is_admin() to authenticated;

alter table public.activity_events add column client_event_id uuid unique;
drop policy activity_select_self on public.activity_events;
create policy activity_select_self on public.activity_events for select to authenticated
using ((select hub_private.active_account()) and ((select auth.uid())=user_id or (select hub_private.is_admin())));
drop policy activity_insert_self on public.activity_events;
create policy activity_insert_self on public.activity_events for insert to authenticated
with check ((select auth.uid())=user_id and (select hub_private.active_account())
and event_type in ('LOGIN','LOGOUT','APP_STARTED','APP_UPDATED','FILE_OPENED','FILE_LOCATION_OPENED',
'SAMPLE_VIEWED','SAMPLE_CREATED','SAMPLE_UPDATED','EXPERIMENT_VIEWED','EXPERIMENT_CREATED','EXPERIMENT_UPDATED',
'REPORT_OPENED','IMAGE_VIEWED','METADATA_UPDATED','TAG_CHANGED','INDEX_STARTED','INDEX_COMPLETED','INDEX_FAILED',
'LEGACY_FILE_VIEWED','LEGACY_FILE_IMPORTED','SETTINGS_CHANGED','FILE_ADDED','MEETING_CREATED','MEETING_UPDATED',
'MEETING_NOTES_EDITED','TRANSCRIPT_EDITED','ACTION_ITEM_COMPLETED')
and octet_length(details::text)<=2048 and length(coalesce(entity_name,''))<=180);

create table public.user_sessions (
 id uuid primary key, user_id uuid not null references public.profiles(id), install_id uuid not null,
 started_at timestamptz not null, last_active_at timestamptz not null, ended_at timestamptz,
 active_seconds double precision not null default 0, active_intervals jsonb not null default '[]', app_version text not null,
 foreign key(user_id,install_id) references public.installations(user_id,install_id),
 check(last_active_at>=started_at), check(ended_at is null or ended_at>=last_active_at),
 check(active_seconds>=0 and active_seconds<='100000000'::float8),
 check(jsonb_typeof(active_intervals)='array' and jsonb_array_length(active_intervals)<=10000)
);
create index user_sessions_period on public.user_sessions(user_id,started_at,last_active_at);
alter table public.user_sessions enable row level security;
grant select,insert,update on public.user_sessions to authenticated;
revoke all on public.user_sessions from anon;
create policy sessions_read on public.user_sessions for select to authenticated
using ((select hub_private.active_account()) and ((select auth.uid())=user_id or (select hub_private.is_admin())));
create policy sessions_insert on public.user_sessions for insert to authenticated
with check((select hub_private.active_account()) and (select auth.uid())=user_id);
create policy sessions_update on public.user_sessions for update to authenticated
using((select hub_private.active_account()) and (select auth.uid())=user_id)
with check((select hub_private.active_account()) and (select auth.uid())=user_id);
create function hub_private.validate_session() returns trigger
language plpgsql set search_path='' as $$
declare interval jsonb; a timestamptz; b timestamptz; prior timestamptz; seconds double precision:=0;
begin
 if TG_OP='UPDATE' and (new.user_id<>old.user_id or new.install_id<>old.install_id or new.started_at<>old.started_at
    or new.active_seconds<old.active_seconds or (old.ended_at is not null and new is distinct from old)) then
  raise exception 'Session identity and completed measurements are immutable';
 end if;
 if new.last_active_at>now()+interval '5 minutes' then raise exception 'Session clock invalid'; end if;
 for interval in select value from jsonb_array_elements(new.active_intervals) loop
  if jsonb_typeof(interval)<>'array' or jsonb_array_length(interval)<>2 then raise exception 'Invalid interval'; end if;
  a:=(interval->>0)::timestamptz; b:=(interval->>1)::timestamptz;
  if a is null or b is null or a<new.started_at or b<a or b>new.last_active_at or (prior is not null and a<prior)
    then raise exception 'Invalid interval'; end if;
  seconds:=seconds+extract(epoch from b-a); prior:=b;
 end loop;
 if abs(seconds-new.active_seconds)>.1 then raise exception 'Measured duration does not match intervals'; end if;
 return new;
end;
$$;
revoke all on function hub_private.validate_session() from public,anon,authenticated;
create trigger validate_session before insert or update on public.user_sessions for each row execute function hub_private.validate_session();

create table public.meetings (
 id uuid primary key, title text not null check(length(title) between 1 and 180), meeting_date date not null,
 start_time text not null default '', end_time text not null default '', location text not null default '',
 meeting_type text not null, description text not null default '', source_type text not null check(source_type in ('current','legacy')),
 created_by uuid not null references public.profiles(id), updated_by uuid not null references public.profiles(id),
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 content jsonb not null default '{}' check(jsonb_typeof(content)='object' and octet_length(content::text)<=500000),
 revision integer not null default 1, client_mutation_id uuid not null
);
create index meetings_date on public.meetings(meeting_date);
create index meetings_creator on public.meetings(created_by);
create index meetings_editor on public.meetings(updated_by);
create table public.meeting_attendees (
 id uuid primary key default gen_random_uuid(), meeting_id uuid not null references public.meetings(id) on delete cascade,
 person_key text not null, user_id uuid references public.profiles(id), guest_name text not null default '',
 attended boolean not null, attendance_status text not null check(attendance_status in ('Present','Absent','Remote','Excused','Partial')),
 notes text not null default '', unique(meeting_id,person_key),
 check((user_id is not null and person_key=user_id::text) or (user_id is null and length(guest_name)>0)),
 check(attended=(attendance_status in ('Present','Remote','Partial')))
);
create index meeting_attendees_user on public.meeting_attendees(user_id,meeting_id);
create table public.meeting_actions (
 id uuid primary key, meeting_id uuid not null references public.meetings(id) on delete cascade,
 title text not null check(length(title) between 1 and 300), assigned_to uuid references public.profiles(id),
 due_date date, completed boolean not null default false
);
create index meeting_actions_meeting on public.meeting_actions(meeting_id);
create index meeting_actions_assigned on public.meeting_actions(assigned_to);
create function hub_private.can_edit_meeting(identity uuid) returns boolean
language sql stable security definer set search_path='' as $$
 select hub_private.active_account() and exists(select 1 from public.meetings where id=identity
 and (created_by=(select auth.uid()) or hub_private.is_admin()));
$$;
revoke all on function hub_private.can_edit_meeting(uuid) from public,anon;
grant execute on function hub_private.can_edit_meeting(uuid) to authenticated;
alter table public.meetings enable row level security;
alter table public.meeting_attendees enable row level security;
alter table public.meeting_actions enable row level security;
revoke all on public.meetings,public.meeting_attendees,public.meeting_actions from anon;
grant select,insert,update on public.meetings to authenticated;
grant select,insert,update,delete on public.meeting_attendees,public.meeting_actions to authenticated;
create policy meetings_read on public.meetings for select to authenticated using((select hub_private.active_account()));
create policy meetings_insert on public.meetings for insert to authenticated
with check((select hub_private.active_account()) and created_by=(select auth.uid()) and updated_by=(select auth.uid()));
create policy meetings_update on public.meetings for update to authenticated
using(hub_private.can_edit_meeting(id)) with check(hub_private.can_edit_meeting(id) and updated_by=(select auth.uid()));
create policy attendees_read on public.meeting_attendees for select to authenticated using((select hub_private.active_account()));
create policy attendees_write on public.meeting_attendees for all to authenticated
using(hub_private.can_edit_meeting(meeting_id)) with check(hub_private.can_edit_meeting(meeting_id));
create policy actions_read on public.meeting_actions for select to authenticated using((select hub_private.active_account()));
create policy actions_write on public.meeting_actions for all to authenticated
using(hub_private.can_edit_meeting(meeting_id)) with check(hub_private.can_edit_meeting(meeting_id));
create function hub_private.guard_meeting() returns trigger language plpgsql set search_path='' as $$
begin
 if new.created_by<>old.created_by or new.created_at<>old.created_at or new.id<>old.id then
  raise exception 'Meeting creator and identity are immutable';
 end if;
 new.updated_at:=now(); new.revision:=old.revision+1; return new;
end; $$;
revoke all on function hub_private.guard_meeting() from public,anon,authenticated;
create trigger guard_meeting before update on public.meetings for each row execute function hub_private.guard_meeting();

-- Guarded private lookup returns only the team roster, never private auth/session data.
create function hub_private.team_roster() returns table(id uuid,display_name text,active boolean)
language sql stable security definer set search_path='' as $$
 select p.id,coalesce(nullif(p.display_name,''),split_part(p.email,'@',1)),p.active
 from public.profiles p where p.active and hub_private.active_account() order by p.display_name,p.id;
$$;
revoke all on function hub_private.team_roster() from public,anon;
grant execute on function hub_private.team_roster() to authenticated;
create function public.hub_team_roster() returns table(id uuid,display_name text,active boolean)
language sql stable security invoker set search_path='' as $$select * from hub_private.team_roster();$$;
revoke all on function public.hub_team_roster() from public,anon;
grant execute on function public.hub_team_roster() to authenticated;

create function public.hub_meeting_record(identity uuid) returns jsonb
language sql stable security invoker set search_path='' as $$
 select to_jsonb(m)||jsonb_build_object('attendees',coalesce((select jsonb_agg(to_jsonb(a)) from public.meeting_attendees a where a.meeting_id=m.id),'[]'::jsonb),
 'actions',coalesce((select jsonb_agg(to_jsonb(a)) from public.meeting_actions a where a.meeting_id=m.id),'[]'::jsonb))
 from public.meetings m where m.id=identity;
$$;
revoke all on function public.hub_meeting_record(uuid) from public,anon;
grant execute on function public.hub_meeting_record(uuid) to authenticated;
create function public.hub_save_meeting(record jsonb, expected_revision integer) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare identity uuid:=(record->>'id')::uuid; existing public.meetings; item jsonb;
begin
 -- Serializes initial inserts as well as updates; expected revision prevents lost edits.
 perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(identity::text,8173));
 select * into existing from public.meetings where id=identity for update;
 if found then
  if not hub_private.can_edit_meeting(identity) then raise exception 'Meeting access unavailable'; end if;
  if existing.client_mutation_id=(record->>'client_mutation_id')::uuid then return public.hub_meeting_record(identity); end if;
  if existing.revision<>expected_revision then return jsonb_build_object('conflict',true); end if;
  update public.meetings set title=record->>'title',meeting_date=(record->>'meeting_date')::date,
   start_time=coalesce(record->>'start_time',''),end_time=coalesce(record->>'end_time',''),location=coalesce(record->>'location',''),
   meeting_type=record->>'meeting_type',description=coalesce(record->>'description',''),source_type=record->>'source_type',
   content=record->'content',updated_by=auth.uid(),client_mutation_id=(record->>'client_mutation_id')::uuid where id=identity;
 else
  if expected_revision<>0 then return jsonb_build_object('conflict',true); end if;
  insert into public.meetings(id,title,meeting_date,start_time,end_time,location,meeting_type,description,source_type,created_by,updated_by,content,client_mutation_id)
   values(identity,record->>'title',(record->>'meeting_date')::date,coalesce(record->>'start_time',''),coalesce(record->>'end_time',''),
   coalesce(record->>'location',''),record->>'meeting_type',coalesce(record->>'description',''),record->>'source_type',auth.uid(),auth.uid(),record->'content',(record->>'client_mutation_id')::uuid);
 end if;
 delete from public.meeting_attendees where meeting_id=identity;
 for item in select value from jsonb_array_elements(coalesce(record->'attendees','[]'::jsonb)) loop
  insert into public.meeting_attendees(meeting_id,person_key,user_id,guest_name,attended,attendance_status,notes)
   values(identity,item->>'person_key',nullif(item->>'user_id','')::uuid,coalesce(item->>'guest_name',''),(item->>'attended')::boolean,item->>'attendance_status',coalesce(item->>'notes',''));
 end loop;
 delete from public.meeting_actions where meeting_id=identity;
 for item in select value from jsonb_array_elements(coalesce(record->'actions','[]'::jsonb)) loop
  insert into public.meeting_actions(id,meeting_id,title,assigned_to,due_date,completed)
   values((item->>'id')::uuid,identity,item->>'title',nullif(item->>'assigned_to','')::uuid,nullif(item->>'due_date','')::date,coalesce((item->>'completed')::boolean,false));
 end loop;
 return public.hub_meeting_record(identity);
end;
$$;
revoke all on function public.hub_save_meeting(jsonb,integer) from public,anon;
grant execute on function public.hub_save_meeting(jsonb,integer) to authenticated;
