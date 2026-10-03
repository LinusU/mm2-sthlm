"""Original north-up map art exported through native MM2 HUD-map resources.

City geometry uses east/north metres. The PKG plane uses east/south, while
its authored V coordinates follow MM2's bottom-up texture convention.
"""

import json
import math
import struct

from PIL import Image, ImageDraw
from shapely.geometry import LineString, Polygon, shape
from shapely.ops import unary_union

from props import chunk, lp

PALETTE = {
    "water": (12, 171, 213),
    "land": (227, 219, 198),
    "park": (166, 213, 139),
    "road": (255, 255, 237),
}
TEXTURE_SIZE = 2048
SUPERSAMPLE = 2
GREEN_LEISURE = {"park", "garden", "nature_reserve", "recreation_ground"}
GREEN_LANDUSE = {"forest", "grass", "meadow", "recreation_ground", "village_green"}
GREEN_NATURAL = {"wood", "grassland", "scrub", "heath"}


def green(tags):
    return (
        tags.get("leisure") in GREEN_LEISURE
        or tags.get("landuse") in GREEN_LANDUSE
        or tags.get("natural") in GREEN_NATURAL
    )


def polygons(geometry):
    if geometry.is_empty:
        return
    if geometry.geom_type == "Polygon":
        yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from polygons(part)


def park_geometry(city, source, land):
    """Retain complete OSM polygons; record incomplete source features explicitly."""
    if source is None:
        return Polygon(), {"polygons": 0, "omitted_incomplete": []}
    # Imported lazily: the main generator imports this module at export time.
    from sthlm import assemble_relation, project

    elements = source["elements"]
    nodes = {e["id"]: e for e in elements if e["type"] == "node"}
    ways = {e["id"]: e for e in elements if e["type"] == "way"}
    out, omitted = [], []
    for item in elements:
        if not green(item.get("tags", {})):
            continue
        if item["type"] not in {"way", "relation"}:
            continue
        try:
            if item["type"] == "way":
                ids = item["nodes"]
                if len(ids) < 4 or ids[0] != ids[-1]:
                    continue  # A tagged open line is not an area.
                poly = Polygon(
                    [
                        project(nodes[n]["lon"], nodes[n]["lat"], city["origin"])
                        for n in ids
                    ]
                )
            else:
                poly = assemble_relation(item, ways, nodes, city["origin"], land)
            if not poly.is_valid:
                omitted.append(f"{item['type']}/{item['id']}: invalid polygon")
                continue
            poly = poly.intersection(land)
            if not poly.is_empty:
                out.append(poly)
        except (KeyError, ValueError):
            omitted.append(f"{item['type']}/{item['id']}: incomplete polygon")
    return unary_union(out), {"polygons": len(out), "omitted_incomplete": omitted}


def square_bounds(land, roads, margin=180):
    minx, minn, maxx, maxn = land.bounds
    for road in roads:
        for x, n in road["points"]:
            minx, minn = min(minx, x), min(minn, n)
            maxx, maxn = max(maxx, x), max(maxn, n)
    # Integer-metre boundaries and identical scale on both axes.
    cx, cn = (minx + maxx) / 2, (minn + maxn) / 2
    half = math.ceil(max(maxx - minx, maxn - minn) / 2 + margin)
    return [
        math.floor(cx - half),
        math.floor(cn - half),
        math.floor(cx - half) + 2 * half,
        math.floor(cn - half) + 2 * half,
    ]


def to_pixel(x, north, bounds, size=TEXTURE_SIZE):
    """Continuous north-up pixel coordinates; inverse of the plane's UV mapping."""
    west, south, east, north_edge = bounds
    return (
        (x - west) / (east - west) * size,
        (north_edge - north) / (north_edge - south) * size,
    )


def area_mask(geometry, bounds, size):
    mask = Image.new("L", (size, size))
    draw = ImageDraw.Draw(mask)
    for poly in polygons(geometry):
        draw.polygon(
            [to_pixel(x, n, bounds, size) for x, n in poly.exterior.coords], fill=255
        )
        for hole in poly.interiors:
            draw.polygon([to_pixel(x, n, bounds, size) for x, n in hole.coords], fill=0)
    return mask


def render(city, source=None, size=TEXTURE_SIZE):
    land = shape(city.get("land", city["bounds"]))
    if "land" not in city:
        land = land.difference(shape(city["water"]))
    if land.is_empty:
        raise ValueError("minimap needs nonempty land")
    # Source ways retain full nodes for provenance; collision/export clips
    # them at the playable mask. Match it so cut streets do not extend at sea.
    roads = []
    boundary = shape(city["bounds"])
    for road in city["roads"]:
        clipped = LineString(road["points"]).intersection(boundary)
        segments = (
            [clipped]
            if clipped.geom_type == "LineString"
            else getattr(clipped, "geoms", [])
        )
        roads.extend(
            {**road, "points": list(segment.coords)}
            for segment in segments
            if segment.geom_type == "LineString" and not segment.is_empty
        )
    bounds = square_bounds(land, roads)
    parks, stats = park_geometry(city, source, land)
    large = size * SUPERSAMPLE
    image = Image.new("RGB", (large, large), PALETTE["water"])
    image.paste(PALETTE["land"], (0, 0, large, large), area_mask(land, bounds, large))
    image.paste(PALETTE["park"], (0, 0, large, large), area_mask(parks, bounds, large))
    draw = ImageDraw.Draw(image)
    pixels_per_metre = large / (bounds[2] - bounds[0])
    for road in roads:
        points = [to_pixel(x, n, bounds, large) for x, n in road["points"]]
        # Restrained hierarchy; ~one pixel minor streets at full-city scale.
        width_m = min(13, max(6, road.get("width", 8) * 0.75))
        width = max(SUPERSAMPLE, round(width_m * pixels_per_metre))
        draw.line(points, fill=PALETTE["road"], width=width, joint="curve")
    return image.resize((size, size), Image.Resampling.LANCZOS), bounds, stats


def geometry(vertices, indices, textured):
    data = struct.pack(
        "<5I", 1, len(vertices), len(indices), 0, 0x102 if textured else 0x002
    )
    data += struct.pack("<HHi", 1, 0, 0) + struct.pack("<iI", 3, len(vertices))
    for vertex in vertices:
        data += struct.pack("<" + "f" * len(vertex), *vertex)
    return (
        data
        + struct.pack("<I", len(indices))
        + struct.pack("<" + "H" * len(indices), *indices)
    )


def package(vertices, indices, paints, texture=""):
    shaders = struct.pack("<2I", len(paints), 1)
    for color in paints:
        shaders += lp(texture) + struct.pack(
            "<17f", *color, *([1, 1, 1, 1] + [0, 0, 0, 1] * 2 + [0])
        )
    return (
        b"PKG3"
        + chunk("H", geometry(vertices, indices, bool(texture)))
        + chunk("shaders", shaders)
    )


TRI_PAINTS = [
    (0.05, 0.08, 0.18, 1),
    (0.2, 0.5, 1, 1),
    (0.2, 0.85, 0.35, 1),
    (0.8, 0.2, 0.8, 1),
    (1, 0.2, 0.15, 1),
    (1, 0.9, 0.05, 1),
    (1, 0.6, 0.15, 1),
    (0.1, 0.9, 0.9, 1),
    (1, 1, 1, 1),
    (0.55, 0.3, 0.95, 1),
]
DOT_PAINTS = [
    (1, 0.2, 0.15, 1),
    (0.2, 0.5, 1, 1),
    (0.2, 0.85, 0.35, 1),
    (0.4, 0.4, 0.4, 1),
    (1, 0.9, 0.05, 1),
    (1, 1, 1, 1),
    (1, 0.7, 0.1, 1),
    (0.1, 0.9, 0.9, 1),
    (0.8, 0.2, 0.8, 1),
]


def write(out, city, source=None):
    image, bounds, stats = render(city, source)
    for directory in ["geometry", "texture", "tune"]:
        (out / directory).mkdir(parents=True, exist_ok=True)
    image.save(out / "texture/hudmap_stockholm.png")
    west, south, east, north = bounds
    # Native authored V is bottom-up; the engine complements it for PNG.
    vertices = [
        (west, 0, -north, 0, 1),
        (east, 0, -north, 1, 1),
        (east, 0, -south, 1, 0),
        (west, 0, -south, 0, 0),
    ]
    (out / "geometry/hudmap_stockholm.pkg").write_bytes(
        package(vertices, [0, 1, 2, 0, 2, 3], [(1, 1, 1, 1)], "hudmap_stockholm")
    )
    (out / "geometry/hudmap_tri.pkg").write_bytes(
        package([(-8, 0, 14), (8, 0, 14), (0, 0, -14)], [0, 1, 2], TRI_PAINTS)
    )
    # Original twelve-sided dot, stored under the native square-marker path.
    dot = [(0, 0, 0)] + [
        (7 * math.cos(i * math.tau / 12), 0, 7 * math.sin(i * math.tau / 12))
        for i in range(12)
    ]
    indices = [v for i in range(12) for v in (0, i + 1, (i + 1) % 12 + 1)]
    (out / "geometry/hudmap_square.pkg").write_bytes(package(dot, indices, DOT_PAINTS))
    ocean = " ".join(f"{c / 255:.6f}" for c in PALETTE["water"])
    (out / "tune/stockholm.mmhudmap").write_text(f"""type: a
mmHudMap {{
Size 0.21 0.25
Pos 0.78 0.75
ZoomIn 0
Approach Rate 1.2
ZoomInDist 600
ZoomOutDist 1200
IconScaleMin 30
IconScaleMax 55
ZoomInDistFS 2600
ZoomOutDistFS 6000
IconScaleMinFS 35
IconScaleMaxFS 65
Ocean Color {ocean}
}}
""")
    return {
        "schema": 1,
        "style": "original MM2-inspired cyan water, beige land, green parks, ivory streets",
        "palette_rgb": {k: list(v) for k, v in PALETTE.items()},
        "texture": "texture/hudmap_stockholm.png",
        "texture_size": list(image.size),
        "bounds_east_north_m": bounds,
        "bounds_world_xz_m": [west, -north, east, -south],
        "orientation": "north-up; world +X east, -Z north; authored V=1 north",
        "metres_per_pixel": (east - west) / TEXTURE_SIZE,
        "roads": len(city["roads"]),
        "parks": stats,
        "resources": [
            "tune/stockholm.mmhudmap",
            "geometry/hudmap_stockholm.pkg",
            "geometry/hudmap_tri.pkg",
            "geometry/hudmap_square.pkg",
            "texture/hudmap_stockholm.png",
        ],
    }


def read_chunks(data):
    """Strictly inspect the small PKG3 resources emitted by this module."""
    if data[:4] != b"PKG3":
        raise ValueError("minimap resource is not PKG3")
    chunks, pos = {}, 4
    try:
        while pos < len(data):
            if data[pos : pos + 4] != b"FILE":
                raise ValueError("invalid minimap PKG chunk")
            length = data[pos + 4]
            if not length or data[pos + 4 + length] != 0:
                raise ValueError("invalid minimap PKG name")
            name = data[pos + 5 : pos + 4 + length].decode()
            start = pos + 5 + length
            size = struct.unpack_from("<I", data, start)[0]
            end = start + 4 + size
            if end > len(data) or name in chunks:
                raise ValueError("invalid minimap PKG payload")
            chunks[name] = data[start + 4 : end]
            pos = end
    except (IndexError, struct.error, UnicodeDecodeError) as exc:
        raise ValueError("truncated minimap PKG") from exc
    return chunks


def validate(out):
    metadata = json.loads((out / "minimap.json").read_text())
    bounds = metadata["bounds_east_north_m"]
    if len(bounds) != 4 or not all(math.isfinite(v) for v in bounds):
        raise ValueError("invalid minimap bounds")
    west, south, east, north = bounds
    if east <= west or north <= south or east - west != north - south:
        raise ValueError("minimap must use equal metre scales")
    if metadata["bounds_world_xz_m"] != [west, -north, east, -south]:
        raise ValueError("minimap world bounds mismatch")
    for path in metadata["resources"]:
        if not (out / path).is_file():
            raise ValueError(f"missing minimap resource {path}")
    with Image.open(out / metadata["texture"]) as image:
        if image.size != tuple(metadata["texture_size"]) or image.mode != "RGB":
            raise ValueError("invalid minimap image")
        image.verify()
    expected_vertices = [
        (west, 0, -north, 0, 1),
        (east, 0, -north, 1, 1),
        (east, 0, -south, 1, 0),
        (west, 0, -south, 0, 0),
    ]
    for name, paints in [("stockholm", 1), ("tri", 10), ("square", 9)]:
        chunks = read_chunks((out / f"geometry/hudmap_{name}.pkg").read_bytes())
        shader = chunks["shaders"]
        if struct.unpack_from("<2I", shader) != (paints, 1):
            raise ValueError("invalid minimap paint palette")
        pos = 8
        for _ in range(paints):
            length = shader[pos]
            texture = shader[pos + 1 : pos + length].decode()
            pos += 1 + length
            values = struct.unpack_from("<17f", shader, pos)
            pos += 68
            if not all(math.isfinite(v) for v in values) or values[3] != 1:
                raise ValueError("invalid minimap shader")
            if texture and not (out / f"texture/{texture}.png").is_file():
                raise ValueError("missing minimap shader texture")
        if pos != len(shader):
            raise ValueError("invalid minimap shader length")
        if name == "stockholm":
            geometry = chunks["H"]
            if struct.unpack_from("<5I", geometry) != (1, 4, 6, 0, 0x102):
                raise ValueError("invalid minimap tile geometry")
            vertices = [
                struct.unpack_from("<5f", geometry, 36 + i * 20) for i in range(4)
            ]
            if any(
                tuple(actual) != tuple(expected)
                for actual, expected in zip(vertices, expected_vertices)
            ):
                raise ValueError("minimap tile bounds/UV mismatch")
    return {
        "tiles": 1,
        "marker_paints": {"tri": 10, "square": 9},
        "texture_size": metadata["texture_size"],
    }
