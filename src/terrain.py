"""Offline terrain heights sampled from the checked-in Lantmäteriet fixture."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np


class TerrainGrid:
    """Bilinear ground-height sampler in the project's local east/north frame.

    Grid values are absolute RH2000 heights in metres. The local coordinates
    use the same WGS84 equirectangular projection as ``sthlm.project``.
    """

    def __init__(
        self, data_path: Path, metadata_path: Path, origin: tuple[float, float]
    ):
        self._metadata = json.loads(metadata_path.read_text())
        self._origin = tuple(float(value) for value in origin)
        expected_origin = tuple(self._metadata["origin_wgs84"])
        if len(self._origin) != 2 or not all(math.isfinite(v) for v in self._origin):
            raise ValueError("origin must contain finite WGS84 longitude and latitude")
        if any(abs(a - b) > 1e-9 for a, b in zip(self._origin, expected_origin)):
            raise ValueError("terrain fixture was built for a different local origin")
        digest = self._metadata.get("fixture_sha256")
        if digest and hashlib.sha256(data_path.read_bytes()).hexdigest() != digest:
            raise ValueError("terrain fixture checksum mismatch")
        self._height = np.load(data_path, allow_pickle=False)["height"]
        self._left, self._res_x, _, self._top, _, self._res_y = self._metadata[
            "local_transform"
        ]
        self._width = int(self._metadata["width"])
        self._rows = int(self._metadata["height"])
        self._nodata = float(self._metadata["nodata"])
        if (
            self._height.shape != (self._rows, self._width)
            or not np.issubdtype(self._height.dtype, np.floating)
            or self._res_x <= 0
            or self._res_y >= 0
        ):
            raise ValueError("malformed terrain grid dimensions or transform")
        if not np.isfinite(self._height).all():
            raise ValueError("terrain grid contains non-finite samples")
        self.metadata = self._metadata

    @classmethod
    def from_project(cls, root: Path, origin: tuple[float, float]) -> TerrainGrid:
        """Load the checked-in terrain fixture and its provenance metadata."""
        terrain_dir = Path(root) / "sources" / "terrain"
        return cls(
            terrain_dir / "stockholm_10m.npz",
            terrain_dir / "metadata.json",
            origin,
        )

    def height(self, x: float, n: float) -> float:
        """Return bilinearly interpolated absolute ground height in RH2000 m.

        Raises ``ValueError`` for non-finite coordinates, outside coverage, or
        nodata among the four required interpolation samples.
        """
        if not (math.isfinite(x) and math.isfinite(n)):
            raise ValueError("terrain coordinates must be finite")
        col = (x - self._left) / self._res_x - 0.5
        row = (self._top - n) / -self._res_y - 0.5
        c0, r0 = math.floor(col), math.floor(row)
        if c0 < 0 or r0 < 0 or c0 + 1 >= self._width or r0 + 1 >= self._rows:
            raise ValueError(f"terrain coordinate outside fixture coverage: {(x, n)}")
        fx, fy = col - c0, row - r0
        samples = self._height[r0 : r0 + 2, c0 : c0 + 2]
        if np.any(samples == self._nodata):
            raise ValueError(f"terrain nodata at or around coordinate: {(x, n)}")
        north = (1.0 - fx) * float(samples[0, 0]) + fx * float(samples[0, 1])
        south = (1.0 - fx) * float(samples[1, 0]) + fx * float(samples[1, 1])
        result = (1.0 - fy) * north + fy * south
        if not math.isfinite(result):
            raise ValueError(f"non-finite terrain interpolation at {(x, n)}")
        return float(result)
