create index user_sessions_install on public.user_sessions(user_id,install_id);
drop policy attendees_write on public.meeting_attendees;
create policy attendees_insert on public.meeting_attendees for insert to authenticated with check(hub_private.can_edit_meeting(meeting_id));
create policy attendees_update on public.meeting_attendees for update to authenticated using(hub_private.can_edit_meeting(meeting_id)) with check(hub_private.can_edit_meeting(meeting_id));
create policy attendees_delete on public.meeting_attendees for delete to authenticated using(hub_private.can_edit_meeting(meeting_id));
drop policy actions_write on public.meeting_actions;
create policy actions_insert on public.meeting_actions for insert to authenticated with check(hub_private.can_edit_meeting(meeting_id));
create policy actions_update on public.meeting_actions for update to authenticated using(hub_private.can_edit_meeting(meeting_id)) with check(hub_private.can_edit_meeting(meeting_id));
create policy actions_delete on public.meeting_actions for delete to authenticated using(hub_private.can_edit_meeting(meeting_id));
