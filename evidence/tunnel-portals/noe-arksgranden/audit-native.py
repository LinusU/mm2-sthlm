"""Inspect facade collision bottoms in the exported native passage footprint."""

import json
from pathlib import Path
import sys
from shapely.geometry import Point, shape

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests"))
from test_vertex_pools import read_native  # noqa: E402

package = Path(sys.argv[1])
building = json.loads(
    (ROOT / "tests/fixtures/noe-arksgranden-portal.json").read_text()
)["building"]
footprint = shape(building["geometry"]).buffer(0.02)
rows = []
counts = {10: 1, 2: 4, 5: 3, 6: 3, 11: 6, 7: 4}
for path in sorted((package / "city/stockholm.parts").glob("part_*_-2*.psdl")):
    writer = read_native(path)
    for room, (_, attrs, _) in enumerate(writer.rooms, 1):
        cursor = 0
        while cursor < len(attrs):
            code = attrs[cursor]
            kind = (code >> 3) & 15
            words = attrs[cursor + 1 : cursor + 1 + counts[kind]]
            if kind == 7:
                a, b = [writer.vertices[v] for v in words[2:4]]
                if footprint.covers(Point(a[0], -a[2])) and footprint.covers(
                    Point(b[0], -b[2])
                ):
                    rows.append(
                        {
                            "file": path.name,
                            "room": room,
                            "left": a,
                            "right": b,
                            "top_y_m": writer.heights[words[1]],
                        }
                    )
            cursor += counts[kind] + 1
print(json.dumps({"package": str(package), "facade_colliders": rows}, indent=2))
