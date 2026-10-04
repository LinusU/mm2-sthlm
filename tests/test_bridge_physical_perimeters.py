"""Railings follow shared physical deck exteriors, never an interior lane edge."""

import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import bridges  # noqa: E402
from elevation import RoadField  # noqa: E402


def native_rails(out, asset):
    data = (out / "geometry" / (asset["asset"] + ".pkg")).read_bytes()
    assert data[:4] == b"PKG3"
    offset, polygons = 4, []
    while offset < len(data):
        assert data[offset : offset + 4] == b"FILE"
        length = data[offset + 4]
        name = data[offset + 5 : offset + 4 + length].decode()
        start = offset + 5 + length
        size = struct.unpack_from("<I", data, start)[0]
        payload = data[start + 4 : start + 4 + size]
        offset = start + 4 + size
        if not name.startswith("PART0_"):
            continue
        count = struct.unpack_from("<I", payload, 4)[0]
        vertices = [
            tuple(
                value + asset["position"][axis]
                for axis, value in enumerate(
                    struct.unpack_from("<3f", payload, 36 + i * 20)
                )
            )
            for i in range(count)
        ]
        polygons.extend(
            Polygon([(x, -z) for x, y, z in vertices[i : i + 3]])
            for i in range(0, count, 3)
        )
    return unary_union(polygons)


def road(index, nodes, points, height=10, layer=1):
    return {
        "id": index,
        "nodes": nodes,
        "points": points,
        "elevated_points": [[x, n, height] for x, n in points],
        "width": 9.0,
        "tags": {"bridge": "yes", "name": "Shared name", "layer": str(layer)},
    }


class BridgePhysicalPerimeterTests(unittest.TestCase):
    def test_actual_parallel_and_segmented_decks_have_native_lane_clearance(self):
        fixtures = json.loads(
            (
                Path(__file__).parent / "fixtures/bridge-physical-perimeters.json"
            ).read_text()
        )
        for name, fixture in fixtures.items():
            with self.subTest(bridge=name):
                all_roads = fixture["roads"]
                roads = [r for r in all_roads if r["tags"].get("bridge") == "yes"]
                before = copy.deepcopy(roads)
                grouped = bridges.physical_bridge_groups(roads)
                self.assertEqual(len(grouped), 1)
                self.assertEqual(roads, before)
                field = RoadField(roads, None, bridge=True)
                with tempfile.TemporaryDirectory() as temp:
                    out = Path(temp)
                    (out / "geometry").mkdir()
                    groups = bridges.corridor_mesh(
                        grouped[0][1],
                        {"roads": all_roads},
                        bridges.source_height(roads, field),
                        {"style": "girder"},
                    )
                    asset = bridges.write_asset(out, "fixture", groups, name)
                    rails = native_rails(out, asset)
                owner = 680061607 if name == "stadshus" else 1338916517
                line = LineString(next(r["points"] for r in roads if r["id"] == owner))
                point = (
                    Point(627.402353, 14.174616)
                    if name == "stadshus"
                    else Point(-1297.9158, 153.26717)
                )
                station = line.project(point)
                for offset in range(-10, 11):
                    along = max(0, min(line.length, station + offset))
                    self.assertGreater(line.interpolate(along).distance(rails), 3.5)
                # Source-connected approach openings still remove real endcaps.
                endpoint = Point(roads[0]["points"][0])
                self.assertGreater(endpoint.distance(rails), 10.8)

    def test_true_stacked_and_distant_equal_names_keep_independent_perimeters(self):
        for kind in ("layer", "height", "distant", "crossing"):
            roads = [
                road(1, [1, 2], [[0, 0], [100, 0]]),
                road(2, [3, 4], [[100, 5], [0, 5]]),
            ]
            if kind == "layer":
                roads[1]["tags"]["layer"] = "2"
            elif kind == "height":
                roads[1]["elevated_points"] = [
                    [x, n, 20] for x, n in roads[1]["points"]
                ]
            elif kind == "distant":
                roads[1] = road(2, [3, 4], [[100, 40], [0, 40]])
            else:
                roads[1] = road(2, [3, 4], [[50, -50], [50, 50]])
            with self.subTest(kind=kind):
                self.assertEqual(len(bridges.physical_bridge_groups(roads)), 2)


if __name__ == "__main__":
    unittest.main()
