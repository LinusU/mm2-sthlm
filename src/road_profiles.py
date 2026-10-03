"""Source-connected road fairing; the untouched terrain remains a separate asset."""

import math

import numpy as np

SPACING = 5.0
MAX_GRADE = 0.16
MAX_CURVATURE = 0.003


def smooth(roads, terrain, anchors):
    """Fair a connected street graph without joining geometric crossings.

    OSM node identity connects roads. Bridge connection heights are fixed;
    other samples can move to remove terrain artefacts. Diffusion has a roughly
    25 m footprint, leaving the broad Stockholm hills intact. Projection then
    limits grade and vertical acceleration, including across source way cuts.
    """
    keys, xy, initial, chains, edges = {}, [], [], [], []
    for road in roads:
        chain = []
        for j, (a, b) in enumerate(zip(road["points"], road["points"][1:])):
            length = math.dist(a, b)
            count = max(1, math.ceil(length / SPACING))
            for k in range(count):
                t = k / count
                p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                key = ("node", road["nodes"][j]) if k == 0 else (road["id"], j, k)
                if key not in keys:
                    keys[key] = len(xy)
                    xy.append(p)
                    # Median rejects isolated returns without adding lateral
                    # samples from a nearby upper/lower carriageway.
                    tangent = (
                        (b[0] - a[0]) / max(length, 1e-6),
                        (b[1] - a[1]) / max(length, 1e-6),
                    )
                    initial.append(
                        max(
                            0.9,
                            float(
                                np.median(
                                    [
                                        terrain.height(
                                            p[0] + tangent[0] * d, p[1] + tangent[1] * d
                                        )
                                        for d in (-10, -5, 0, 5, 10)
                                    ]
                                )
                            ),
                        )
                    )
                chain.append(keys[key])
        key = ("node", road["nodes"][-1])
        if key not in keys:
            keys[key] = len(xy)
            xy.append(tuple(road["points"][-1]))
            initial.append(max(0.9, terrain.height(*xy[-1])))
        chain.append(keys[key])
        chains.append(chain)
        edges.extend(
            (a, b, math.dist(xy[a], xy[b]))
            for a, b in zip(chain, chain[1:])
            if math.dist(xy[a], xy[b]) > 1e-6
        )
    edges = list(
        {tuple(sorted((a, b))): (a, b, length) for a, b, length in edges}.values()
    )
    if not edges:
        return []
    # Preserve the already corrected bridge bank approach samples.
    for road, chain in zip(roads, chains):
        old = road.get("elevated_points", [])
        if not old:
            continue
        for reverse, node in ((False, road["nodes"][0]), (True, road["nodes"][-1])):
            if node not in anchors:
                continue
            ordered = list(reversed(chain)) if reverse else chain
            distance = 0.0
            for j, i in enumerate(ordered):
                if j:
                    distance += math.dist(xy[i], xy[ordered[j - 1]])
                if distance > 30:
                    break
                initial[i] = (
                    float(np.interp(distance, [0, 30], [anchors[node], anchors[node]]))
                    if all(abs(v[2] - anchors[node]) < 1e-8 for v in old)
                    else initial[i]
                )
    heights = np.array(initial, dtype=float)
    left, right, lengths = (np.array(v) for v in zip(*edges))
    left, right = left.astype(int), right.astype(int)
    degree = np.bincount(np.r_[left, right], minlength=len(xy))
    fixed = {
        keys[("node", node)]: value
        for node, value in anchors.items()
        if ("node", node) in keys
    }
    terminal = np.flatnonzero(degree == 1)
    for _ in range(80):
        total = np.bincount(
            np.r_[left, right],
            weights=np.r_[heights[right], heights[left]],
            minlength=len(xy),
        )
        heights += 0.4 * (total / np.maximum(degree, 1) - heights)
        heights[terminal] = np.array(initial)[terminal]
        for i, value in fixed.items():
            heights[i] = value
    # Curvature triples continue through degree-two source nodes, avoiding
    # abrupt crests at arbitrary OSM way splits.
    neighbours = [[] for _ in xy]
    for a, b, length in edges:
        neighbours[a].append((b, length))
        neighbours[b].append((a, length))
    groups = np.arange(len(xy))
    triples = []
    for chain in chains:
        for a, i, b in zip(chain, chain[1:], chain[2:]):
            da, db = math.dist(xy[a], xy[i]), math.dist(xy[b], xy[i])
            if da > 1e-6 and db > 1e-6:
                triples.append((a, i, b, da, db))
    for i, ns in enumerate(neighbours):
        for k, (a, da) in enumerate(ns):
            for b, db in ns[k + 1 :]:
                va = ((xy[a][0] - xy[i][0]) / da, (xy[a][1] - xy[i][1]) / da)
                vb = ((xy[b][0] - xy[i][0]) / db, (xy[b][1] - xy[i][1]) / db)
                if va[0] * vb[0] + va[1] * vb[1] < -0.85:
                    triples.append((a, i, b, da, db))
    triples = list(dict.fromkeys(triples))
    if triples:
        ta, ti, tb, da, db = (np.array(v) for v in zip(*triples))
        ta, ti, tb = ta.astype(int), ti.astype(int), tb.astype(int)
        ca, ci, cb = 1 / da, -1 / da - 1 / db, 1 / db
        ta, ti, tb = groups[ta], groups[ti], groups[tb]
        norm = (
            ca * ca
            + ci * ci
            + cb * cb
            + 2 * ca * ci * (ta == ti)
            + 2 * ca * cb * (ta == tb)
            + 2 * ci * cb * (ti == tb)
        )
        norm = np.maximum(norm, 1e-12)
        triple_degree = np.maximum(np.bincount(np.r_[ta, ti, tb], minlength=len(xy)), 1)
        limit = MAX_CURVATURE * (da + db) / 2
    left, right = groups[left], groups[right]
    degree = np.maximum(np.bincount(np.r_[left, right], minlength=len(xy)), 1)
    # A junction has one local tangent plane. Project the first connected
    # samples onto the common plane rather than letting independent street
    # slopes produce a crease at the shared node.
    junction_rows = []
    for i, ns in enumerate(neighbours):
        if len(ns) < 3:
            continue
        matrix = np.array([[xy[a][0] - xy[i][0], xy[a][1] - xy[i][1]] for a, _ in ns])
        u, singular, _ = np.linalg.svd(matrix, full_matrices=True)
        rank = int(np.sum(singular > max(singular[0], 1) * 1e-8))
        for vector in u[:, rank:].T:
            coeff = np.r_[-sum(vector), vector]
            junction_rows.append(([i] + [a for a, _ in ns], coeff))
    if junction_rows:
        width = max(len(indices) for indices, _ in junction_rows)
        ji = np.zeros((len(junction_rows), width), dtype=int)
        jc = np.zeros_like(ji, dtype=float)
        for k, (indices, coeff) in enumerate(junction_rows):
            ji[k, : len(indices)] = indices
            jc[k, : len(indices)] = coeff
        jnorm = np.sum(jc * jc, axis=1)
        jdegree = np.maximum(np.bincount(ji[jc != 0], minlength=len(xy)), 1)
    # Alternating convex projections do not flatten a real constant grade.
    for _ in range(12000):
        delta = heights[right] - heights[left]
        excess = delta - np.clip(delta, -MAX_GRADE * lengths, MAX_GRADE * lengths)
        adjustment = np.zeros(len(xy))
        np.add.at(adjustment, left, excess / 2)
        np.add.at(adjustment, right, -excess / 2)
        heights += adjustment / np.maximum(degree, 1)
        if triples:
            bend = ca * heights[ta] + ci * heights[ti] + cb * heights[tb]
            excess = (bend - np.clip(bend, -limit, limit)) / norm
            adjustment.fill(0)
            np.add.at(adjustment, ta, -excess * ca)
            np.add.at(adjustment, ti, -excess * ci)
            np.add.at(adjustment, tb, -excess * cb)
            heights += adjustment / triple_degree

        if junction_rows:
            residual = np.sum(jc * heights[ji], axis=1) / jnorm
            adjustment.fill(0)
            np.add.at(adjustment, ji.ravel(), (-residual[:, None] * jc).ravel())
            heights += adjustment / jdegree
        heights = np.maximum(heights, 0.9)
        for i, value in fixed.items():
            heights[i] = value
    for road, chain in zip(roads, chains):
        road["elevated_points"] = [[*xy[i], float(heights[groups[i]])] for i in chain]
    return diagnostics(roads)


def diagnostics(roads):
    """Reproducible per-source inventory of centreline grade and curvature."""
    results = []
    for road in roads:
        points = road["elevated_points"]
        lengths = [math.dist(a[:2], b[:2]) for a, b in zip(points, points[1:])]
        grades = [
            (b[2] - a[2]) / d if d else 0
            for a, b, d in zip(points, points[1:], lengths)
        ]
        curvatures = [
            abs(b - a) / ((da + db) / 2)
            for a, b, da, db in zip(grades, grades[1:], lengths, lengths[1:])
            if da + db > 0
        ]
        results.append(
            {
                "source_way": road["id"],
                "name": road.get("tags", {}).get("name", ""),
                "max_grade": max(map(abs, grades), default=0),
                "max_vertical_curvature_per_m": max(curvatures, default=0),
                "height_range_m": [
                    min(p[2] for p in points),
                    max(p[2] for p in points),
                ],
            }
        )
    return sorted(results, key=lambda r: r["max_grade"], reverse=True)
