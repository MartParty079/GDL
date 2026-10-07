# GDL integration inventory and baseline

Inventory recorded before behavior changes, October 6, 2026. Original ZIP contains 84 entries and 1,830,127 uncompressed bytes. `analysis/gdl/baseline_inventory.json` records source hashes, including historical runtime artifacts. `analysis/gdl/baseline/` preserves source, five Quick Runs, Swift table, resources and historical documentation unchanged; historical watchdog logs/status are excluded from distributed code. `gdl-path-inventory.txt` contains the source path/configuration search inventory.

## Boundaries found

- BAT invokes the versioned CPython watchdog. Watchdog executes defaults, reads startup_paths.ini, locates Fiji, force-closes Fiji/ImageJ, launches RUN IN FIJI.py and restarts crashes. Its status IDs change per restart. Logs/status normally live beside defaults.
- RUN IN FIJI.py executes defaults and eleven modules in a shared Jython namespace. It handles startup paths, environment overrides, module validation and STARTING/RUNNING/COMPLETED/CANCELED/FAILED status. SystemExit runs the existing emergency report finalizer.
- Defaults contain named-user Fiji roots and report paths, a fixed JMP default, eleven module names, and processing/UI/BEAST/report defaults.
- Core helpers locate Quick Runs beside the runner, migrate old root-level slots, load/save complete JSON settings, select a named-user work zone for choosers and perform bounded JMP discovery.
- UI/settings modules read Swift tables beside images, up to twelve parents, then the bundled table. Profile parsing/scaling and Quick Run processing values must remain intact.
- Workbook helpers choose report destinations, score Fiji roots with named-user bonuses, inspect active Fiji and bounded roots and launch BEAST workers. Worker files/configs reside in output/runtime folders. Java subprocesses inherit the engine environment.
- Main engine chooses batch/single-image inputs and output parent with Fiji choosers, then creates timestamped GDL run folders. Recovery/capture flows have separate choosers. Algorithms, report generation, JSL generation, worker scheduling and emergency finalization are excluded from broad refactoring.
- Configuration transport includes startup_paths.ini, executed defaults, ImageJ preferences, Quick Run JSON, BEAST worker config and environment variables (GDL_V193_*, GDL_EXTRA_USER_ROOTS, GDL_FIJI_LAUNCHER_OVERRIDE, GDL_JMP_EXE_OVERRIDE, FIJI_HOME/IMAGEJ_HOME/IJ_HOME and Java properties).

## Baseline limit

The user explicitly requested building/testing without launching Fiji. No live Quick Run, Fiji/JMP launch, generated report or scientific-output baseline is claimed. Static hashes, legacy pure-function checks, original Quick Run/table preservation and mocked watchdog/adapter checks establish a structural baseline. At the time of the original integration there was no Git repository. The later source-control migration preserves that original baseline locally, excludes it from publication, and tracks the portable managed engine and hash ledger. The original package remains available for later live comparison.

Managed packages retain original filenames/layout. Compatibility patches are limited to configuration/path/transport/watchdog boundaries. ZIP import stages and validates a package before activation; incompatible layouts fail without replacing the active engine. Live scientific acceptance remains a separate test with a known image fixture.

The worker path inventory exposed an additional integration boundary: BEAST prefers nearby saved scripts before the active runner. Hub sessions now explicitly select the session's managed runner, and generated worker bootstraps load the small Hub runtime bridge after defaults. Their existing worker config, scheduling, processing and report logic remain in the engine. Tests compile the generated wrapper, verify canonical runner selection and confirm workers do not emit the parent watchdog's completion status.

The original baseline is local-only because it contains personal path defaults. Git and packaged builds publish the portable managed engine. Baseline comparison tests explicitly skip when the private original is absent; normal package tests use the sanitized legacy source fixture in fresh checkouts.
