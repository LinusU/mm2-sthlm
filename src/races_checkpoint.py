"""Authored Stockholm any-order Checkpoint catalog, independent of the engine.

Shared routing/export belongs to races.py. Coordinates in the configuration
are documentation only: resolve node_id on way_id in the retained road graph.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARAMETERS = (
    "CarType",
    "TimeofDay",
    "Weather",
    "Opponents",
    "Cops",
    "Ambient",
    "Peds",
    "NumLaps",
    "TimeLimit",
    "Difficulty",
)


def anchors(event):
    """Native CSV row roles: start, unordered gates, separately armed finish."""
    return [event["start"], *event["checkpoints"], event["finish"]]


def itinerary(event):
    """A suggested opponent route; never an ordering constraint on the player."""
    return [
        event["start"],
        *(event["checkpoints"][i] for i in event["suggested_order"]),
        event["finish"],
    ]


def validate_catalog(catalog, roads=None):
    """Reject inconsistent authoring or source ownership before native export.

    Optional roads are the current normalized retained roads. The shared
    router must additionally reject disconnected legs and boundary escapes.
    """
    if (
        catalog.get("schema") != 1
        or catalog.get("family") != "race"
        or catalog.get("native_rule") != "AnyOrder"
    ):
        raise ValueError("Checkpoint requires schema 1, race family, AnyOrder")
    events = catalog["events"]
    if len(events) != 10:
        raise ValueError("Stockholm requires ten Checkpoint events")
    owned = {r["id"]: r for r in roads} if roads is not None else None
    previous_length = 0
    for index, event in enumerate(events):
        if (
            event["index"] != index
            or event["difficulty_rank"] != index + 1
            or event["id"] != f"checkpoint-{index + 1:02}"
        ):
            raise ValueError("Checkpoint identity or catalog progression drift")
        gates = event["checkpoints"]
        if len(gates) < 2 or sorted(event["suggested_order"]) != list(
            range(len(gates))
        ):
            raise ValueError("Each itinerary must visit every gate exactly once")
        for order in event.get("opponent_orders", [event["suggested_order"]]):
            if sorted(order) != list(range(len(gates))):
                raise ValueError(
                    "Each opponent plan must visit every gate exactly once"
                )
        nodes = [a["node_id"] for a in anchors(event)]
        if len(set(nodes)) != len(nodes):
            raise ValueError("Start, gates and finish must be distinct")
        length = event["suggested_route_length_m"]
        if length <= previous_length:
            raise ValueError("Checkpoint catalog lengths must increase")
        previous_length = length
        for anchor in anchors(event):
            if not isinstance(anchor["node_id"], int) or not isinstance(
                anchor["way_id"], int
            ):
                raise ValueError("Anchors require exact source node and way IDs")
            if owned is not None:
                road = owned.get(anchor["way_id"])
                if road is None or anchor["node_id"] not in road["nodes"]:
                    raise ValueError(
                        f"Missing retained anchor ownership: {anchor['label']}"
                    )
                if road["width"] < 5:
                    raise ValueError("Checkpoint anchor is on an unsafe narrow road")
        for rank in ("amateur", "professional"):
            params = event[rank]
            if set(params) != set(PARAMETERS):
                raise ValueError("Native Checkpoint parameters are incomplete")
            if not 4 <= params["Opponents"] <= 7:
                raise ValueError("Checkpoint opponents must follow original 4–7 range")
            if not all(0 <= params[p] <= 1 for p in ("Ambient", "Peds")):
                raise ValueError("Native densities must lie between zero and one")
        if event["professional"]["Ambient"] < event["amateur"]["Ambient"]:
            raise ValueError("Professional traffic must be at least Amateur traffic")
    return events


def load(path=None, roads=None):
    catalog = json.loads(
        Path(path or ROOT / "config/races/checkpoint.json").read_text()
    )
    validate_catalog(catalog, roads)
    return catalog
