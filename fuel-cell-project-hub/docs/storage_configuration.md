# Editable native storage

Configure research in Settings > Storage > Project: edit the active name/root,
add/remove legacy roots one per line, or add current/reference/archive sources.
The previous-project selector restores the preserved project identity. Legacy
roots stay read-only and Old Test Data; importing a reference is an explicit copy.

Storage holds the database, generated output, cache/logs and backup locations.
Use dedicated application-owned folders outside the research roots. Type paths
(including environment variables), Browse, Open, Validate and Save locations.
Moving the catalog uses SQLite backup, preserves its original and refuses an
existing destination catalog. Reset fields restores defaults without applying
changes until Save. There is no cloud mode or account configuration.

Indexing controls bounded resident extraction, watching, periodic reconciliation
and the five index operations. Advanced provides Backup Index, Restore Index,
Index Run History, Edit Classification Rules, and portable project folder
mappings. Rules map keywords to research categories; rebuild content to apply
changed rules to existing unchanged documents. Manual edits always win.

Folder mappings are relative paths for Procedures, Samples, Experiments, Raw
Data, Processed Data, Analysis, Reports, Reference, Exports and Archive. Saving
changes application metadata; it does not create folders or move datasets. GDL
input/output/reports defaults use these mappings unless Analysis Tools supplies
an explicit override.

Advanced shared setup retains the explicitly initialized shared-library wizard.
It requires confirmation before creating its project marker and refuses configured
research sources. It is optional and separate from native indexing.

Personal settings, old snapshots, backups and databases remain outside Git.
See [native indexing](native_indexing.md) for architecture and operational limits.
