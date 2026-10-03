#!/usr/bin/env python3
"""Report source-profile grade, curvature and source-aware cross-section twist."""

import argparse
import json
import math
import sys

import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from elevation import RoadField, bridge_approaches  # noqa: E402
from road_profiles import diagnostics  # noqa: E402
from terrain import TerrainGrid  # noqa: E402


def inventory(city):
    terrain = TerrainGrid.from_project(ROOT, city["origin"])
    bridge_ids = set(city["bridge_ways"])
    ordinary = [r for r in city["roads"] if r["id"] not in bridge_ids]
    elevated = [r for r in city["roads"] if r["id"] in bridge_ids]
    ground, deck, seams, _ = bridge_approaches(ordinary, elevated)
    fields = (
        RoadField(ground, terrain, junctions=seams),
        RoadField(deck, terrain, junctions=seams),
    )
    profiles = diagnostics(city["roads"])
    by_id = {p["source_way"]: p for p in profiles}
    shared = {}
    displacement = []
    hills = {}
    for road in city["roads"]:
        field = fields[road["id"] in bridge_ids]
        if road["id"] not in bridge_ids and not road.get("height_override"):
            for x, n, h in road["elevated_points"]:
                raw = max(0.9, terrain.height(x, n))
                displacement.append(abs(h - raw))
                hills.setdefault(road.get("tags", {}).get("name", ""), []).append(
                    (raw, h)
                )
        crossfalls, distances, warps = [], [], []
        points = road["elevated_points"]
        for a, b in zip(points, points[1:]):
            length = math.dist(a[:2], b[:2])
            if not length:
                continue
            x, n = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            nx, nn = -(b[1] - a[1]) / length, (b[0] - a[0]) / length
            half = road["width"] / 2
            left = field.height_for_road(road, x + nx * half, n + nn * half)
            right = field.height_for_road(road, x - nx * half, n - nn * half)
            crossfalls.append((right - left) / road["width"])
            start = [
                field.height_for_road(
                    road, a[0] + sign * nx * half, a[1] + sign * nn * half
                )
                for sign in (-1, 1)
            ]
            end = [
                field.height_for_road(
                    road, b[0] + sign * nx * half, b[1] + sign * nn * half
                )
                for sign in (-1, 1)
            ]
            warps.append(abs((end[1] - end[0]) - (start[1] - start[0])))
            distances.append(length)
        row = by_id[road["id"]]
        sampled = {
            **road,
            "elevated_points": [
                [p[0], p[1], field.height_for_road(road, p[0], p[1])] for p in points
            ],
        }
        sampled_profile = diagnostics([sampled])[0]
        row["sampled_surface_max_grade"] = sampled_profile["max_grade"]
        row["sampled_surface_max_vertical_curvature_per_m"] = sampled_profile[
            "max_vertical_curvature_per_m"
        ]
        row["max_same_segment_quad_warp_m"] = max(warps, default=0)
        row["max_crossfall"] = max(map(abs, crossfalls), default=0)
        row["max_crossfall_change_per_m"] = max(
            (
                abs(a - b) / ((da + db) / 2)
                for a, b, da, db in zip(
                    crossfalls, crossfalls[1:], distances, distances[1:]
                )
            ),
            default=0,
        )
        source_nodes = {
            tuple(p): node for node, p in zip(road["nodes"], road["points"])
        }
        for p in points:
            node = source_nodes.get(tuple(p[:2]))
            if node is not None:
                shared.setdefault(node, []).append(p[2])
    ordinary_profiles = [p for p in profiles if p["source_way"] not in bridge_ids]
    return {
        "road_count": len(profiles),
        "ordinary_abs_displacement_percentiles_m": dict(
            zip(
                ["p50", "p90", "p95", "p99", "max"],
                map(float, np.percentile(displacement, [50, 90, 95, 99, 100])),
            )
        ),
        "representative_hills": {
            name: {
                "raw_terrain_range_m": [
                    min(p[0] for p in hills[name]),
                    max(p[0] for p in hills[name]),
                ],
                "smoothed_profile_range_m": [
                    min(p[1] for p in hills[name]),
                    max(p[1] for p in hills[name]),
                ],
            }
            for name in [
                "Bastugatan",
                "Brännkyrkagatan",
                "Fleminggatan",
                "Hantverkargatan",
                "Sankt Eriksgatan",
                "Erstagatan",
                "Hornsgatan",
            ]
            if name in hills
        },
        "ordinary_grade_above_16_01_percent": sum(
            p["max_grade"] > 0.1601 for p in ordinary_profiles
        ),
        "ordinary_curvature_above_0_0031_per_m": sum(
            p["max_vertical_curvature_per_m"] > 0.0031 for p in ordinary_profiles
        ),
        "max_shared_source_node_difference_m": max(
            (max(h) - min(h) for h in shared.values()), default=0
        ),
        "worst_grade": sorted(profiles, key=lambda p: p["max_grade"], reverse=True)[
            :20
        ],
        "worst_curvature": sorted(
            profiles, key=lambda p: p["max_vertical_curvature_per_m"], reverse=True
        )[:20],
        "worst_sampled_grade": sorted(
            profiles, key=lambda p: p["sampled_surface_max_grade"], reverse=True
        )[:20],
        "worst_sampled_curvature": sorted(
            profiles,
            key=lambda p: p["sampled_surface_max_vertical_curvature_per_m"],
            reverse=True,
        )[:20],
        "worst_quad_warp": sorted(
            profiles, key=lambda p: p["max_same_segment_quad_warp_m"], reverse=True
        )[:20],
        "worst_twist": sorted(
            profiles, key=lambda p: p["max_crossfall_change_per_m"], reverse=True
        )[:20],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "package", type=Path, nargs="?", default=ROOT / "dist/stockholm"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = (
        json.dumps(
            inventory(json.loads((args.package / "normalized.json").read_text())),
            indent=2,
        )
        + "\n"
    )
    if args.output:
        args.output.write_text(result)
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
