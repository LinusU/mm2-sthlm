"""Explicit Stockholm PBF acquisition/clipping; offline builds need no osmium."""

import argparse
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import urllib.request
import osmium

ROOT = Path(__file__).resolve().parents[1]
BOUNDS = [17.970, 59.286, 18.174, 59.373]
URL = "https://data.bbbike.org/osm/bbbike/Stockholm/Stockholm.osm.pbf"


class Extract(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.ways, self.nodes, self.relations = {}, {}, []

    def node(self, n):
        if (
            n.tags.get("natural") == "tree"
            and BOUNDS[0] <= n.location.lon <= BOUNDS[2]
            and BOUNDS[1] <= n.location.lat <= BOUNDS[3]
        ):
            self.nodes[n.id] = {
                "type": "node",
                "id": n.id,
                "lon": n.location.lon,
                "lat": n.location.lat,
                "tags": dict(n.tags),
            }

    def way(self, w):
        pts = [(n.ref, n.lon, n.lat) for n in w.nodes if n.location.valid()]
        if len(pts) != len(w.nodes):
            return
        if (
            not pts
            or max(p[1] for p in pts) < BOUNDS[0]
            or min(p[1] for p in pts) > BOUNDS[2]
            or max(p[2] for p in pts) < BOUNDS[1]
            or min(p[2] for p in pts) > BOUNDS[3]
        ):
            return
        # Include untagged member ways so local building/island relations keep holes.
        self.ways[w.id] = {
            "type": "way",
            "id": w.id,
            "nodes": [p[0] for p in pts],
            "tags": dict(w.tags),
        }
        for nid, lon, lat in pts:
            if nid not in self.nodes:
                self.nodes[nid] = {"type": "node", "id": nid, "lon": lon, "lat": lat}

    def relation(self, r):
        tags = dict(r.tags)
        if not (
            tags.get("building")
            or tags.get("natural") == "water"
            or tags.get("place") == "island"
        ):
            return
        members = [
            {
                "type": {"w": "way", "n": "node", "r": "relation"}[m.type],
                "ref": m.ref,
                "role": m.role,
            }
            for m in r.members
        ]
        if any(m["type"] == "way" and m["ref"] in self.ways for m in members):
            self.relations.append(
                {"type": "relation", "id": r.id, "members": members, "tags": tags}
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pbf", type=Path, default=ROOT / ".cache/Stockholm.osm.pbf")
    args = parser.parse_args()
    pbf = args.pbf
    if not pbf.exists():
        pbf.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(URL, timeout=180) as r:
            pbf.write_bytes(r.read())
    expected = ROOT / ".cache/Stockholm.CHECKSUM.txt"
    md5 = hashlib.md5(pbf.read_bytes(), usedforsecurity=False).hexdigest()
    if expected.exists():
        entry = next(
            (
                line.split()[0]
                for line in expected.read_text().splitlines()
                if "Stockholm.osm.pbf" in line
            ),
            None,
        )
        if entry is not None and entry != md5:
            raise ValueError("downloaded PBF does not match provider checksum")
    extract = Extract()
    extract.apply_file(str(pbf), locations=True, idx="flex_mem")
    with gzip.open(ROOT / "sources/osm.json.gz", "rt") as f:
        base = json.load(f)
    # Keep complete lake membership from the original source; only retain base
    # water relations, their member ways and nodes, not obsolete building/roads.
    relations = [
        e
        for e in base["elements"]
        if e["type"] == "relation" and e.get("tags", {}).get("natural") == "water"
    ]
    wayids = {m["ref"] for r in relations for m in r["members"] if m["type"] == "way"}
    ways = {
        e["id"]: e for e in base["elements"] if e["type"] == "way" and e["id"] in wayids
    }
    nodeids = {n for w in ways.values() for n in w["nodes"]}
    nodes = {
        e["id"]: e
        for e in base["elements"]
        if e["type"] == "node" and e["id"] in nodeids
    }
    # Base lake geometry stays internally consistent; new roads/buildings share
    # current nodes unless these belong to the retained complete lake ring.
    nodes.update(extract.nodes)
    ways.update(extract.ways)
    allrels = {r["id"]: r for r in relations}
    omitted = []
    for r in extract.relations:
        missing = [
            m["ref"]
            for m in r["members"]
            if m["type"] == "way" and m["ref"] not in ways
        ]
        if missing:
            omitted.append(
                {
                    "id": r["id"],
                    "tags": r["tags"],
                    "reason": "regional extract has incomplete relation",
                    "missing_members": missing,
                }
            )
        else:
            allrels[r["id"]] = r
    elements = [*nodes.values(), *ways.values(), *allrels.values()]
    elements.sort(key=lambda e: (e["type"], e["id"]))
    combined = {
        "version": 0.6,
        "generator": "mm2-sthlm bounded BBBike PBF fixture with retained complete lake relations",
        "elements": elements,
    }
    out = ROOT / "sources/expanded"
    out.mkdir(exist_ok=True)
    data = json.dumps(combined, ensure_ascii=False, separators=(",", ":")).encode()
    target = out / "osm.json.gz"
    target.write_bytes(gzip.compress(data, mtime=0))
    with osmium.io.Reader(str(pbf)) as reader:
        timestamp = reader.header().get("osmosis_replication_timestamp")
    if expected.exists():
        (out / "provider-checksum.txt").write_bytes(expected.read_bytes())
    manifest = {
        "url": URL,
        "retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_timestamp": timestamp
        or "not in PBF header; download index reports 2026-09-26T19:27:50Z",
        "pbf_sha256": hashlib.sha256(pbf.read_bytes()).hexdigest(),
        "pbf_md5": hashlib.md5(pbf.read_bytes(), usedforsecurity=False).hexdigest(),
        "provider_checksum_sha256": hashlib.sha256(expected.read_bytes()).hexdigest()
        if expected.exists()
        else None,
        "provider_md5_verified": bool(
            expected.exists()
            and any(
                line.split()[0] == md5 and line.split()[-1] == "Stockholm.osm.pbf"
                for line in expected.read_text().splitlines()
                if line.split()
            )
        ),
        "snapshot_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "license": "ODbL-1.0",
        "attribution": "© OpenStreetMap contributors; regional extract provided by BBBike.org",
        "bounds_buffer": BOUNDS,
        "elements": len(elements),
        "base_water_source": json.loads((ROOT / "sources/manifest.json").read_text()),
        "omitted_source_relations": omitted,
        "acquisition_history": [
            "whole-envelope Overpass returned HTTP 504",
            "bounded overpass-api.de request returned HTTP 406",
            "bounded kumi request timed out",
            "ready-made Stockholm regional PBF downloaded; only buffered geometry retained",
        ],
        "privacy": "No contributor/user/changeset metadata retained",
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )
    print(
        f"Saved {len(elements)} genuine elements ({len(ways)} ways, {len(allrels)} relations); gzip {target.stat().st_size} bytes; omitted {len(omitted)} source relations",
        flush=True,
    )


if __name__ == "__main__":
    main()
