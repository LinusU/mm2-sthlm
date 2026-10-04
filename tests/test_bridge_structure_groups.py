"""Source topology governs bridge railing continuity and landmark export."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

from shapely.geometry import LineString, Point, Polygon, box, mapping
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import bridges  # noqa: E402
from elevation import RoadField  # noqa: E402


class Terrain:
    def height(self, x, north):
        return 0.0


def road(index, nodes, points, name, layer=1, height=20):
    return {
        "id": index,
        "nodes": nodes,
        "points": points,
        "elevated_points": [[x, n, height] for x, n in points],
        "width": 9.0,
        "tags": {
            "highway": "secondary",
            "bridge": "yes",
            "name": name,
            "layer": str(layer),
        },
    }


def rail_distance(groups, centre):
    return min(
        Point(x, -z).distance(centre)
        for triangle in groups[0][1]
        for x, y, z in triangle
    )


class BridgeStructureGroupTests(unittest.TestCase):
    def test_source_connected_layer_change_keeps_rails_at_internal_join(self):
        fixture = json.loads(
            (Path(__file__).parent / "fixtures/bridge-layer-join.json").read_text()
        )
        roads = fixture["roads"]
        grouped = bridges.source_bridge_groups(roads)
        self.assertEqual(len(grouped), 1)
        self.assertEqual({r["id"] for r in grouped[0][1]}, set(fixture["bridge_ways"]))
        centre = Point(79.22865604826349, 752.4307021696313)
        field = RoadField(roads, Terrain(), bridge=True)
        groups = bridges.corridor_mesh(
            grouped[0][1],
            {"roads": roads},
            bridges.source_height(roads, field),
            {"style": "girder"},
        )
        # Grouping by local layer previously treated this degree-two node as
        # two road ends and removed railings eleven metres on both sides.
        rail = unary_union(
            [Polygon([(x, -z) for x, y, z in triangle]) for triangle in groups[0][1]]
        )
        for member in roads:
            line = LineString(member["points"])
            station = line.project(centre)
            for offset in range(-10, 11):
                along = station + offset
                if 0 <= along <= line.length:
                    point = line.interpolate(along)
                    if point.distance(centre) <= 10:
                        clearance = point.distance(rail)
                        self.assertGreater(clearance, 4.0)
                        self.assertLess(clearance, 5.0)
        # A real external source-connected road still needs its approach portal.
        approach = road(
            99, [11872638940, 999], [[centre.x, centre.y], [120, 752]], "Side street"
        )
        opened = bridges.corridor_mesh(
            grouped[0][1],
            {"roads": [*roads, approach]},
            bridges.source_height(roads, field),
            {"style": "girder"},
        )
        self.assertGreater(rail_distance(opened, centre), 10.8)

    def test_equal_named_unconnected_stacked_spans_keep_separate_portals(self):
        roads = [
            road(1, [1, 2], [[0, 0], [100, 0]], "Same bridge", 1, 10),
            road(2, [3, 4], [[0, 0], [100, 0]], "Same bridge", 2, 30),
        ]
        grouped = bridges.source_bridge_groups(roads)
        self.assertEqual([[r["id"] for r in rs] for name, rs in grouped], [[1], [2]])
        for name, members in grouped:
            groups = bridges.corridor_mesh(
                members, {"roads": roads}, lambda x, n: 10, {"style": "girder"}
            )
            self.assertGreater(rail_distance(groups, Point(0, 0)), 10.8)
            self.assertGreater(rail_distance(groups, Point(100, 0)), 10.8)

    def test_named_arch_landmark_is_actually_written_for_each_source_component(self):
        roads = [
            road(1, [1, 2], [[0, 0], [120, 0]], "Västerbron"),
            road(2, [3, 4], [[0, 25], [120, 25]], "Västerbron"),
        ]
        city = {
            "roads": roads,
            "bridge_ways": [1, 2],
            "bridge_road_surface": mapping(box(-5, -5, 125, 30)),
            "spawn": [0, 0],
        }
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            instances = bridges.write(out, city, lambda x, n: 20, road_triangles=[])
            assets = {item["asset"] for item in instances}
            self.assertEqual(assets, {"sthlm_vasterbron", "sthlm_vasterbron_1"})
            for asset in assets:
                self.assertEqual(
                    (out / f"geometry/{asset}.pkg").read_bytes()[:4], b"PKG3"
                )
            self.assertTrue(all(item["triangle_count"] > 100 for item in instances))


if __name__ == "__main__":
    unittest.main()
