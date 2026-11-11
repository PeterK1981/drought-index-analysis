"""Jahresraster direkt vom DWD; keine Zugangsdaten erforderlich."""

from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from .analysis import read_grid

BASE = "https://opendata.dwd.de/climate_environment/CDC/grids_germany/annual"


def download(root, start, end):
    if start > end:
        raise ValueError("Startjahr muss vor oder gleich Endjahr liegen.")
    records = []
    root = Path(root)
    for year in range(start, end + 1):
        for folder, product, stem in [
            ("Precipitation", "precipitation", "precipitation"),
            ("Temperature", "air_temperature_mean", "air_temp_mean"),
        ]:
            filename = f"grids_germany_annual_{stem}_{year}17.asc"
            url = f"{BASE}/{product}/{filename}.gz"
            path = root / folder / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            downloaded = False
            if not path.exists():
                request = Request(url, headers={"User-Agent": "drought-germany/0.1"})
                with urlopen(request, timeout=90) as response:
                    payload = gzip.decompress(response.read())
                temporary = path.with_suffix(".asc.part")
                try:
                    temporary.write_bytes(payload)
                    read_grid(temporary)
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
                downloaded = True
            else:
                read_grid(path)
            records.append({"file": path.relative_to(root).as_posix(), "url": url,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "downloaded_this_run": downloaded})
            print(f"Bereit: {folder}/{filename}", flush=True)
    manifest = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "files": records}
    (root / "download_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
