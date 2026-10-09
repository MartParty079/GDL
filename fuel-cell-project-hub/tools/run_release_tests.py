"""Run release regressions with isolated Beta metadata and no external login."""

import sys
import os
os.environ.setdefault("GDL_HUB_CHANNEL", "beta")
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def release_tests(suite):
    selected = unittest.TestSuite()
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            selected.addTests(release_tests(test))
        elif test.__class__.__name__ != "ProductionIdentityTests":
            selected.addTest(test)
    return selected


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    print("External identity login is retired; no Microsoft identity flow or Fiji is launched.", flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(release_tests(suite))
    sys.exit(0 if result.wasSuccessful() else 1)
