# Old Test Data

1. Sign in under **Settings → Microsoft Account**.
2. Open **Settings → Storage → Cloud & Old Test Data**.
3. Choose **Add previous project**. Browse My OneDrive or search a university SharePoint site by name, choose its document library, then double-click folders. **Use this folder** selects the folder currently displayed, including a library root.
4. Enter a historical project name and reference note; confirm **Old Test Data**.
5. Select the saved project and choose **Refresh selected legacy index**. Cancel refresh preserves the previous snapshot. Current cloud refresh and historical refresh are separate actions.
6. Choose **Browse files**, or use **Files & Data → Old Test Data**. Filter by previous project, type, experiment, sample, modified date or archive state. Search includes project names, notes, subcategories and relationship IDs. The default view shows only current work.

Each source has a permanent `LEG-` identifier, stable Graph site/drive/root IDs, import date/user, editable note and `read_only_reference: true`. Every historical file receives the legacy origin and project ID from the saved source definition even when cache contents contain a conflicting origin. Duplicate root imports and reusing the exact current root as historical are rejected. Overlapping subfolders are not automatically deduplicated across distinct source definitions.

Graph scans GET metadata only: filenames, relative paths, stable item IDs, sizes, timestamps, folder/file type and web links. It does not download, parse, hash, rename, move or delete datasets. Indexes commit atomically. Inaccessible child folders retain their last cached descendants with warnings; missing/inaccessible roots and cancellation preserve the entire last snapshot. A future delta-link field is reserved but incremental delta scanning is not implemented.

Classification uses manual overrides, explicit metadata, folder context, filename clues, extensions, then Other. Common folders distinguish Procedures, Reports and Reference; raw CSV data becomes Sensor Data while raw images remain Image. Subcategories distinguish pre/post imaging and pressure/flow/temperature. Ordinary historical names never become fabricated current experiment/sample IDs. **Edit classification** saves portable metadata overrides without changing origin or touching the source file.

**Edit note** changes the project reference note. **Open online** opens its source folder. Files open through their cached web link. Offline caches stay searchable; opening an online resource still requires browser/network access. Corrupt caches are preserved, and do not prevent local browsing or startup.

The local legacy cache defaults to `%LOCALAPPDATA%\FuelCellProjectHub\legacy`. Its editable location is on the same settings page. **Use new cache location** retains old files and searches prior cache locations until a new refresh commits. It never silently moves caches. Project definitions and file overrides are shared through normal project settings; absolute cache paths and authentication tokens remain local.
