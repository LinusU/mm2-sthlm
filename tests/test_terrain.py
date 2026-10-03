import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.terrain import TerrainGrid


class TerrainGridTests(unittest.TestCase):
    def make_grid(
        self,
        values,
        *,
        nodata=-9999.0,
        origin=(18.045, 59.328),
        advertised_width=None,
        advertised_digest=None,
    ):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        directory = Path(temp.name)
        values = np.asarray(values, dtype=np.float32)
        rows, cols = values.shape
        np.savez(directory / "grid.npz", height=values)
        metadata = {
            "origin_wgs84": list(origin),
            "local_transform": [0.0, 10.0, 0.0, 40.0, 0.0, -10.0],
            "width": cols if advertised_width is None else advertised_width,
            "height": rows,
            "nodata": nodata,
        }
        if advertised_digest is not None:
            metadata["fixture_sha256"] = advertised_digest
        (directory / "metadata.json").write_text(json.dumps(metadata))
        return TerrainGrid(directory / "grid.npz", directory / "metadata.json", origin)

    def test_bilinear_interpolation_uses_east_and_north_axes(self):
        # Values at cell centers (x=5,15; n=35,25): z = 100 + 2*x + 3*n.
        grid = self.make_grid([[215.0, 235.0], [185.0, 205.0]])
        self.assertEqual(grid.height(10.0, 30.0), 210.0)
        self.assertEqual(grid.height(7.5, 32.5), 212.5)

    def test_nodata_in_any_interpolation_cell_raises(self):
        grid = self.make_grid([[1.0, -9999.0], [3.0, 4.0]])
        with self.assertRaisesRegex(ValueError, "nodata"):
            grid.height(10.0, 30.0)

    def test_out_of_coverage_and_nonfinite_coordinates_raise(self):
        grid = self.make_grid(np.ones((3, 3)))
        with self.assertRaisesRegex(ValueError, "outside"):
            grid.height(-1.0, 30.0)
        with self.assertRaisesRegex(ValueError, "finite"):
            grid.height(float("nan"), 30.0)

    def test_fixture_shape_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "malformed terrain grid"):
            self.make_grid(np.ones((2, 2)), advertised_width=3)

    def test_advertised_fixture_checksum_is_enforced(self):
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.make_grid(np.ones((2, 2)), advertised_digest="0" * 64)

    def test_real_project_fixture_covers_target_with_finite_heights(self):
        root = Path(__file__).resolve().parents[1]
        grid = TerrainGrid.from_project(root, (18.045, 59.328))
        self.assertEqual(grid.metadata["coverage_nodata_cells"], 0)
        self.assertEqual(
            grid.metadata["coverage_valid_cells"], grid.metadata["coverage_total_cells"]
        )
        for x, n in ((0.0, 0.0), (-4270.0, -4690.0), (7340.0, 5020.0)):
            self.assertTrue(np.isfinite(grid.height(x, n)))
        with self.assertRaisesRegex(ValueError, "different local origin"):
            TerrainGrid.from_project(root, (18.0, 59.0))


if __name__ == "__main__":
    unittest.main()
