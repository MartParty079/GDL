-- Activity names are optional in the pre-existing schema. LOGIN and other
-- account events must be accepted without an entity name.
drop policy activity_insert_self on public.activity_events;
create policy activity_insert_self on public.activity_events for insert to authenticated
with check ((select auth.uid())=user_id and (select hub_private.active_account())
and event_type in ('LOGIN','LOGOUT','APP_STARTED','APP_UPDATED','FILE_OPENED','FILE_LOCATION_OPENED',
'SAMPLE_VIEWED','SAMPLE_CREATED','SAMPLE_UPDATED','EXPERIMENT_VIEWED','EXPERIMENT_CREATED','EXPERIMENT_UPDATED',
'REPORT_OPENED','IMAGE_VIEWED','METADATA_UPDATED','TAG_CHANGED','INDEX_STARTED','INDEX_COMPLETED','INDEX_FAILED',
'LEGACY_FILE_VIEWED','LEGACY_FILE_IMPORTED','SETTINGS_CHANGED')
and octet_length(details::text)<=2048 and coalesce(length(entity_name),0)<=180);
