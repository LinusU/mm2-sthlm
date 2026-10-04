"""Decode the two reported basins' native floors and make a bounded drive guide."""

import json
from pathlib import Path
import sys

from shapely.geometry import Point, Polygon, shape

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests"))
from test_vertex_pools import read_native  # noqa: E402

package = Path(sys.argv[1])
out = Path(__file__).parent
city = json.loads((package / "normalized.json").read_text())
ids = {"way/338452356", "way/697302459"}
basins = [p for p in city["shallow_water"] if p["id"] in ids]
writer = read_native(package / "city/stockholm.parts/part_0_1.psdl")
triangles = []
counts = {10: 1, 2: 4, 5: 3, 6: 3, 11: 6, 7: 4}
for rid, (_, attrs, _) in enumerate(writer.rooms, 1):
    cursor, material = 0, ""
    while cursor < len(attrs):
        code = attrs[cursor]
        kind = (code >> 3) & 15
        words = attrs[cursor + 1 : cursor + 1 + counts[kind]]
        if kind == 10:
            material = writer.textures[((code & 7) * 256 + words[0]) - 1]
        if kind in (5, 6):
            points = [writer.vertices[v] for v in words]
            poly = Polygon([(x, -z) for x, y, z in points])
            if poly.area > 1e-8 and poly.intersects(
                Polygon([(490, 1059), (525, 1059), (525, 1141), (490, 1141)])
            ):
                triangles.append((poly, points, material, rid))
        cursor += counts[kind] + 1


def probe(x, n):
    result = []
    for poly, v, material, room in triangles:
        if not poly.buffer(1e-5).covers(Point(x, n)):
            continue
        a, b, c = v
        ux, un = b[0] - a[0], -b[2] + a[2]
        vx, vn = c[0] - a[0], -c[2] + a[2]
        dx, dn = x - a[0], n + a[2]
        determinant = ux * vn - un * vx
        u = (dx * vn - dn * vx) / determinant
        t = (ux * dn - un * dx) / determinant
        y = a[1] + u * (b[1] - a[1]) + t * (c[1] - a[1])
        result.append(
            {
                "y_m": y,
                "material": material,
                "room": room,
                "deadly": room in writer.water_rooms,
            }
        )
    return result


samples = []
for n in range(1081, 1141, 2):
    floors = probe(510, n)
    assert floors, (510, n)
    floor = max(floors, key=lambda p: p["y_m"])
    samples.append({"x": 510, "north": n, **floor})
centres = []
for basin in basins:
    pt = shape(basin["geometry"]).representative_point()
    floors = probe(pt.x, pt.y)
    assert any(f["material"] == "sthlm_pond_floor" and not f["deadly"] for f in floors)
    centres.append(
        {
            "id": basin["id"],
            "position": [pt.x, pt.y],
            "water_level_m": basin["water_level_m"],
            "floor_level_m": basin["floor_level_m"],
            "native_floors": floors,
        }
    )
(out / "native-floor-query.json").write_text(
    json.dumps({"basins": centres, "route_samples": samples}, indent=2) + "\n"
)
with (out / "source-guide.opp").open("w") as f:
    f.write(
        "x,y,z,brake,forward offset,side offset,target speed,speed start,side start\n"
    )
    for p in samples:
        f.write(f"{p['x']},{p['y_m']:.5f},{-p['north']},0,0,0,5,0,0\n")
print(f"510,{samples[0]['y_m'] + 0.35:.5f},-1081,0")
