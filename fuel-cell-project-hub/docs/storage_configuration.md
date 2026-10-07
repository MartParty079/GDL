# Editable storage

**Settings → Storage** has an editable local synced folder field and visible **Browse**, **Change folder**, **Validate**, **Open folder**, **Reset local mapping** actions. The former field was read-only and its locate action hidden under Advanced.

Browse or type a path, validate it, then choose Change folder. Review and confirm the target. Unmarked folders require confirmation to initialize a project marker. Protected/system/home roots, filesystem redirects and folders marked for a different project are rejected. The mapping changes locally; indexing refreshes against that root. Existing files remain in place. Same-project cloud connections, historical definitions and metadata survive reconnects and local reset. An unavailable mapped root must be reconnected before shared settings can be edited.

Reset clears only the local mapping. It preserves shared files and a local project-settings snapshot for offline access. A snapshot restores previously loaded project definitions after restart; shared project markers remain authoritative when connected.

**Project folders** controls the relative Procedures, Samples, Experiments, Raw Data, Processed Data, Analysis, Reports, Reference, Exports and Archive paths. Each has Browse/Reset/Open. Browsed folders must stay inside the project root. Save validates portable, distinct paths and writes a normal settings revision. Folder mappings do not create, move or reorganize datasets. GDL defaults for input, output and reports resolve from these mappings unless an explicit GDL override exists under **Analysis Tools**.

**Cloud & Old Test Data** controls storage mode on this computer:

- **LocalOnly:** current files come from the local index; cached historical references remain searchable.
- **CloudOnly:** current files come from the selected Graph index.
- **Hybrid:** local current paths take precedence; remaining cloud paths use online links. An explicit file open prefers an existing local file.

**Connect / change current cloud folder** browses Microsoft sources by name and validates the selected root before saving stable IDs. **Disconnect current cloud** removes only that definition. Cached cloud metadata remains on disk. Current and historical refresh actions are independent; cancellation preserves the last snapshot.

Graph is isolated in `microsoft_graph.py` and `microsoft_graph_provider.py`. The provider filename avoids colliding with the existing `storage.py` module. Pagination validates the Microsoft Graph host before sending a token, blocks download endpoints and redirects, and bounds retries for 429/503 responses. No Graph write methods exist.

Shared settings hold relative folder mappings, rules, cloud IDs, legacy definitions and file overrides. Per-user state holds absolute paths, selected mode and caches. Tokens use a separate encrypted Windows store. Current local index rebuild retains its existing change-history semantics. Cloud refresh performs a complete metadata traversal; delta scanning is reserved for later.
