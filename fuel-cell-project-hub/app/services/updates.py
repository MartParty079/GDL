"""Read-only release notification. Installation is deliberately a later milestone."""
import json
import re
from urllib.request import Request, urlopen


def latest_release(repository):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Release repository must be owner/repository, for example team/fuel-cell-hub.")
    request = Request(f"https://api.github.com/repos/{repository}/releases/latest",
                      headers={"Accept": "application/vnd.github+json", "User-Agent": "FuelCellProjectHub"})
    with urlopen(request, timeout=8) as response:
        release = json.load(response)
    return {"tag": release["tag_name"], "url": release["html_url"], "name": release.get("name") or release["tag_name"]}
