"""Rebuild the checked-in local terrain grid from ignored source tiles.

Requires rasterio 1.5.2, pyproj 3.8.0, and NumPy 2.5.3. This acquisition-time
script is not imported by normal map builds.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / ".cache" / "terrain" / "lantmateriet"
OUTPUT_DIR = ROOT / "sources" / "terrain"
ORIGIN = (18.045, 59.328)
BOUNDS = (17.970, 59.286, 18.174, 59.373)
RESOLUTION = 10.0
BUFFER = 20.0
NODATA = -9999.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def deterministic_npz(path: Path, height: np.ndarray) -> None:
    """Write the same compressed NPZ bytes regardless of wall-clock time."""
    array_buffer = io.BytesIO()
    np.lib.format.write_array(
        array_buffer, np.ascontiguousarray(height), allow_pickle=False
    )
    info = zipfile.ZipInfo("height.npy", date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o600 << 16
    with zipfile.ZipFile(
        path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        archive.writestr(
            info,
            array_buffer.getvalue(),
            compress_type=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata_path = OUTPUT_DIR / "metadata.json"
    old_metadata = json.loads(metadata_path.read_text())
    source_paths = sorted(SOURCE_DIR.glob("m*.tif"))
    if {p.name for p in source_paths} != set(old_metadata["source_tiles"]):
        raise SystemExit(
            "source tile list does not match the checked-in provenance manifest"
        )
    source_hashes = {p.name: sha256(p) for p in source_paths}
    if source_hashes != old_metadata["source_tiles"]:
        raise SystemExit(
            "source tile checksum mismatch; refusing to rebuild from changed input"
        )

    radius = 6378137.0
    projected = [
        (
            radius * math.radians(lon - ORIGIN[0]) * math.cos(math.radians(ORIGIN[1])),
            radius * math.radians(lat - ORIGIN[1]),
        )
        for lon in BOUNDS[::2]
        for lat in BOUNDS[1::2]
    ]
    xs, ns = zip(*projected)
    left = math.floor(min(xs) / RESOLUTION) * RESOLUTION - BUFFER
    top = math.ceil(max(ns) / RESOLUTION) * RESOLUTION + BUFFER
    right = math.ceil(max(xs) / RESOLUTION) * RESOLUTION + BUFFER
    bottom = math.floor(min(ns) / RESOLUTION) * RESOLUTION - BUFFER
    width = round((right - left) / RESOLUTION)
    height = round((top - bottom) / RESOLUTION)
    destination = np.full((height, width), NODATA, dtype=np.float32)
    local_crs = CRS.from_proj4(
        f"+proj=eqc +lat_ts={ORIGIN[1]} +lat_0={ORIGIN[1]} "
        f"+lon_0={ORIGIN[0]} +datum=WGS84 +units=m +no_defs"
    )
    transform = from_origin(left, top, RESOLUTION, RESOLUTION)

    for source_path in source_paths:
        with rasterio.open(source_path) as source:
            if source.crs.to_epsg() != 5845 or source.dtypes != ("float32",):
                raise SystemExit(f"unexpected source CRS or dtype: {source_path.name}")
            reproject(
                source=rasterio.band(source, 1),
                destination=destination,
                src_transform=source.transform,
                src_crs=CRS.from_epsg(3006),
                src_nodata=source.nodata,
                dst_transform=transform,
                dst_crs=local_crs,
                dst_nodata=NODATA,
                resampling=Resampling.bilinear,
                init_dest_nodata=False,
            )

    valid = destination != NODATA
    if not valid.all():
        raise SystemExit(
            f"fixture has {destination.size - int(valid.sum())} uncovered cells"
        )
    fixture_path = OUTPUT_DIR / "stockholm_10m.npz"
    deterministic_npz(fixture_path, destination)
    metadata = dict(old_metadata)
    metadata.update(
        {
            "local_transform": [left, RESOLUTION, 0, top, 0, -RESOLUTION],
            "width": width,
            "height": height,
            "fixture_sha256": sha256(fixture_path),
            "coverage_valid_cells": int(valid.sum()),
            "coverage_total_cells": int(destination.size),
            "coverage_nodata_cells": int(destination.size - valid.sum()),
            "builder_versions": {
                "rasterio": rasterio.__version__,
                "pyproj": __import__("pyproj").__version__,
                "numpy": np.__version__,
            },
        }
    )
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(f"wrote {fixture_path.relative_to(ROOT)} sha256={metadata['fixture_sha256']}")
    print(
        f"coverage={int(valid.sum())}/{destination.size}; resolution={RESOLUTION:g} m"
    )


if __name__ == "__main__":
    main()
