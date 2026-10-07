"""Register the supplied ZIP locally, without changing existing overrides."""
import hashlib
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.storage import Store
from app.services.gdl_analysis import GDLAnalysisService
from app.services.gdl_package import zip_version, archive_digest


def register(archive):
    archive = Path(archive).resolve()
    service = GDLAnalysisService(Store())
    registry = service.registry
    if registry.config_error:
        raise ValueError("Existing GDL settings are unreadable; they were preserved.")
    if registry.config.get("package_source"):
        print("Existing GDL package source retained.")
        return
    if zip_version(archive) != int(registry.manifest()["version"]):
        raise ValueError("The source ZIP version does not match the bundled engine.")
    registry.config.update(package_source=str(archive), source_sha256=archive_digest(archive))
    registry.save_config()
    print("GDL update source registered locally. No engine or applications were launched.")


if __name__ == "__main__":
    register(sys.argv[1])
