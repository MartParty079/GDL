-- Run through an administrator SQL connection. All fixture rows roll back.
-- This verifies database authorization with JWT claims, not a browser login.
begin;
insert into public.profiles(id,email,display_name,role,active) values
 ('11111111-1111-4111-8111-111111111111','fixture-a@example.invalid','Fixture A','user',true),
 ('22222222-2222-4222-8222-222222222222','fixture-b@example.invalid','Fixture B','user',true),
 ('33333333-3333-4333-8333-333333333333','fixture-disabled@example.invalid','Fixture Disabled','user',false),
 ('44444444-4444-4444-8444-444444444444','fixture-admin@example.invalid','Fixture Admin','admin',true);
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"11111111-1111-4111-8111-111111111111","role":"authenticated"}',true);
insert into public.installations(user_id,install_id) values('11111111-1111-4111-8111-111111111111','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
insert into public.user_sessions(id,user_id,install_id,started_at,last_active_at,ended_at,active_seconds,active_intervals,app_version)
 values('aaaaaaaa-1111-4111-8111-111111111111','11111111-1111-4111-8111-111111111111','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',now()-interval '1 hour',now(),now(),3600,
 jsonb_build_array(jsonb_build_array(now()-interval '1 hour',now())),'0.3.3');
insert into public.activity_events(user_id,install_id,event_type,entity_name,client_event_id)
 values('11111111-1111-4111-8111-111111111111','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','LOGIN','Fixture','aaaaaaaa-2222-4222-8222-222222222222');
insert into public.activity_events(user_id,event_type,entity_name,client_event_id)
 values('11111111-1111-4111-8111-111111111111','LOGIN','Fixture','aaaaaaaa-2222-4222-8222-222222222222') on conflict(client_event_id) do nothing;
select public.hub_save_meeting('{
 "id":"bbbbbbbb-1111-4111-8111-111111111111","title":"Fixture review","meeting_date":"2026-10-08","meeting_type":"Team Meeting","source_type":"current",
 "client_mutation_id":"bbbbbbbb-2222-4222-8222-222222222222","content":{"notes":"Saved fixture notes","transcript":"Fixture transcript","related":[{"id":"S-fixture","kind":"sample","name":"Fixture sample","origin":"current"}]},
 "attendees":[{"person_key":"11111111-1111-4111-8111-111111111111","user_id":"11111111-1111-4111-8111-111111111111","attended":true,"attendance_status":"Present"},
 {"person_key":"22222222-2222-4222-8222-222222222222","user_id":"22222222-2222-4222-8222-222222222222","attended":false,"attendance_status":"Absent"}],
 "actions":[{"id":"cccccccc-1111-4111-8111-111111111111","title":"Verify fixture","assigned_to":"11111111-1111-4111-8111-111111111111","due_date":"2026-10-16","completed":false}]
}'::jsonb,0);
do $$ declare result jsonb; count integer;
begin
 select count(*) into count from public.activity_events where client_event_id='aaaaaaaa-2222-4222-8222-222222222222';
 if count<>1 then raise exception 'Event retry duplicated'; end if;
 if not exists(select 1 from public.meeting_attendees where user_id=auth.uid() and attended) then raise exception 'Attendance not saved'; end if;
 if not exists(select 1 from public.meeting_actions where title='Verify fixture') then raise exception 'Action missing'; end if;
 result:=public.hub_save_meeting(jsonb_build_object('id','bbbbbbbb-1111-4111-8111-111111111111','client_mutation_id','dddddddd-1111-4111-8111-111111111111'),0);
 if result->>'conflict'<>'true' then raise exception 'Stale edit accepted'; end if;
 result:=public.hub_save_meeting(jsonb_build_object('id','bbbbbbbb-1111-4111-8111-111111111111','client_mutation_id','bbbbbbbb-2222-4222-8222-222222222222'),0);
 if (result->>'revision')::integer<>1 then raise exception 'Retry changed meeting revision'; end if;
 begin
  update public.user_sessions set active_seconds=9999 where user_id=auth.uid();
  raise exception 'Completed session was altered';
 exception when check_violation or raise_exception then
  if SQLERRM='Completed session was altered' then raise; end if;
 end;
end; $$;
select set_config('request.jwt.claims','{"sub":"22222222-2222-4222-8222-222222222222","role":"authenticated"}',true);
do $$ declare count integer;
begin
 if exists(select 1 from public.user_sessions where user_id='11111111-1111-4111-8111-111111111111') then raise exception 'Foreign sessions exposed'; end if;
 if exists(select 1 from public.activity_events where user_id='11111111-1111-4111-8111-111111111111') then raise exception 'Foreign activity exposed'; end if;
 if not exists(select 1 from public.meetings where id='bbbbbbbb-1111-4111-8111-111111111111') then raise exception 'Shared meeting unreadable'; end if;
 update public.meetings set title='Unauthorized' where id='bbbbbbbb-1111-4111-8111-111111111111';
 get diagnostics count=row_count;
 if count<>0 then raise exception 'Foreign meeting editable'; end if;
 update public.meeting_attendees set attended=true,attendance_status='Present' where meeting_id='bbbbbbbb-1111-4111-8111-111111111111';
 get diagnostics count=row_count;
 if count<>0 then raise exception 'Foreign attendance editable'; end if;
 begin
  insert into public.activity_events(user_id,event_type,entity_name) values('11111111-1111-4111-8111-111111111111','LOGIN','Spoof');
  raise exception 'Foreign activity inserted';
 exception when insufficient_privilege then null;
 end;
end; $$;
select set_config('request.jwt.claims','{"sub":"33333333-3333-4333-8333-333333333333","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from public.meetings) then raise exception 'Disabled user read meetings'; end if;
 if exists(select 1 from public.hub_team_roster()) then raise exception 'Disabled user read roster'; end if;
end; $$;
reset role;
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"44444444-4444-4444-8444-444444444444","role":"authenticated"}',true);
do $$ begin
 if not exists(select 1 from public.user_sessions where user_id='11111111-1111-4111-8111-111111111111') then raise exception 'Admin cannot report sessions'; end if;
 if not exists(select 1 from public.activity_events where user_id='11111111-1111-4111-8111-111111111111') then raise exception 'Admin cannot report activity'; end if;
 update public.meetings set title='Admin edited fixture',updated_by=auth.uid() where id='bbbbbbbb-1111-4111-8111-111111111111';
 if not found then raise exception 'Admin cannot edit meeting'; end if;
end; $$;
reset role;
do $$ begin
 if has_table_privilege('anon','public.user_sessions','SELECT') or has_table_privilege('anon','public.meetings','SELECT')
 or has_function_privilege('anon','public.hub_save_meeting(jsonb,integer)','EXECUTE') then raise exception 'Anonymous access enabled'; end if;
end; $$;
rollback;
