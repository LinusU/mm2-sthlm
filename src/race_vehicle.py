"""Original compact racer content; simulation stays in the external engine."""

import math
from pathlib import Path
import struct

from PIL import Image
from props import chunk, geometry, lp


def cuboid(lo, hi):
    points = [
        (x, y, z)
        for x in (lo[0], hi[0])
        for y in (lo[1], hi[1])
        for z in (lo[2], hi[2])
    ]
    faces = [
        (0, 1, 3, 2),
        (4, 6, 7, 5),
        (0, 4, 5, 1),
        (2, 3, 7, 6),
        (0, 2, 6, 4),
        (1, 5, 7, 3),
    ]
    return [
        tuple(points[i] for i in tri)
        for a, b, c, d in faces
        for tri in ((a, b, c), (a, c, d))
    ]


def wheel(x, z):
    triangles = []
    for i in range(12):
        a, b = 2 * math.pi * i / 12, 2 * math.pi * (i + 1) / 12
        p = (x - 0.12, -0.35 + 0.32 * math.cos(a), z + 0.32 * math.sin(a))
        q = (x - 0.12, -0.35 + 0.32 * math.cos(b), z + 0.32 * math.sin(b))
        r, s = (x + 0.12, q[1], q[2]), (x + 0.12, p[1], p[2])
        triangles.extend(
            [
                (p, q, r),
                (p, r, s),
                ((x - 0.12, -0.35, z), q, p),
                ((x + 0.12, -0.35, z), s, r),
            ]
        )
    return triangles


def lift(triangles):
    # Native imported vehicles use the tyre contact plane as model origin.
    return [tuple((x, y + 0.67, z) for x, y, z in tri) for tri in triangles]


def bound():
    points = [
        (x, y, z) for x in (-0.83, 0.83) for y in (0.27, 1.52) for z in (-1.9, 1.9)
    ]
    faces = [
        (0, 1, 3, 2),
        (4, 6, 7, 5),
        (0, 4, 5, 1),
        (2, 3, 7, 6),
        (0, 2, 6, 4),
        (1, 5, 7, 3),
    ]
    return (
        "version: 1.01\nverts: 8\nmaterials: 0\nedges: 0\npolys: 6\n\n"
        + "".join(f"v {x} {y} {z}\n" for x, y, z in points)
        + "\n"
        + "".join("quad " + " ".join(map(str, face)) + " 0\n" for face in faces)
    )


def mesh():
    shaders = struct.pack("<2I", 1, 5)
    for name in (
        "sthlm_racer_paint",
        "sthlm_racer_glass",
        "sthlm_racer_rubber",
        "sthlm_racer_lamp",
        "sthlm_racer_tail",
    ):
        shaders += lp(name) + struct.pack(
            "<17f", *([1, 1, 1, 1] * 2 + [0, 0, 0, 0] * 2 + [0])
        )
    result = b"PKG3" + chunk("shaders", shaders)
    body = cuboid((-0.83, -0.4, -1.9), (0.83, 0.18, 1.9))
    body += cuboid((-0.7, 0.18, -0.6), (0.7, 0.85, 0.8))
    result += chunk("BODY_H", geometry(lift(body), 0))
    result += chunk(
        "GLASS_H", geometry(lift(cuboid((-0.705, 0.3, -0.61), (0.705, 0.75, 0.81))), 1)
    )
    for i, (x, z) in enumerate(
        ((-0.83, -1.25), (0.83, -1.25), (-0.83, 1.25), (0.83, 1.25))
    ):
        result += chunk(f"WHL{i}_H", geometry(lift(wheel(x, z)), 2))
    for shader, z in ((3, -1.91), (4, 1.9)):
        lamps = cuboid((-0.75, -0.08, z), (-0.45, 0.08, z + 0.01))
        lamps += cuboid((0.45, -0.08, z), (0.75, 0.08, z + 0.01))
        result += chunk(f"LAMP{shader}_H", geometry(lift(lamps), shader))
    return result


def tuning():
    wheel_fields = """SuspensionExtent 0.2
SuspensionLimit 0.05
SuspensionFactor 1.0
SuspensionDampCoef 0.1
SteeringLimit 0.5
BrakeCoef 0.14
TireDispLimitLong 0.075
TireDampCoefLong 0.75
TireDragCoefLong 0.01
TireDispLimitLat 0.075
TireDampCoefLat 0.75
TireDragCoefLat 0.02
OptimumSlipPercent 0.05
StaticFric 3.0
SlidingFric 2.95"""
    return (
        """type: a
vehCarSim {
Mass 1100
InertiaBox 1.8 1.3 4.0
CenterOfGravity 0 -0.1 0
DrivetrainType 1
Aero {
Drag 0.5
Down 0
}
Engine {
MaxHorsePower 180
IdleRPM 750
OptRPM 5800
MaxRPM 8500
}
Trans {
AutoNumGears 4
Reverse 20
Low 20
High 75
}
"""
        + "".join(
            f"{name} {{\n{wheel_fields if name == 'WheelFront' else wheel_fields.replace('SteeringLimit 0.5', 'SteeringLimit 0')}\n}}\n"
            for name in ("WheelFront", "WheelBack")
        )
        + "}\n"
    )


def write(out):
    out = Path(out)
    for folder in ("geometry", "bound", "tune/vehicle", "texture"):
        (out / folder).mkdir(parents=True, exist_ok=True)
    (out / "geometry/sthlm_racer.pkg").write_bytes(mesh())
    for i, (x, z) in enumerate(
        ((-0.83, -1.25), (0.83, -1.25), (-0.83, 1.25), (0.83, 1.25))
    ):
        transform = [
            x - 0.12,
            0,
            z - 0.32,
            x + 0.12,
            0.64,
            z + 0.32,
            0,
            0,
            0,
            x,
            0.32,
            z,
        ]
        (out / f"geometry/sthlm_racer_whl{i}.mtx").write_bytes(
            struct.pack("<12f", *transform)
        )
    (out / "bound/sthlm_racer_bound.bnd").write_text(bound())
    (out / "tune/vehicle/sthlm_racer.vehcarsim").write_text(tuning())
    (out / "tune/sthlm_racer.info").write_text(
        "Description=Stockholm Compact\nColors=Blue\n"
    )
    colors = {
        "paint": (43, 105, 151),
        "glass": (42, 61, 68),
        "rubber": (30, 31, 33),
        "lamp": (230, 222, 171),
        "tail": (163, 28, 23),
    }
    for name, color in colors.items():
        Image.new("RGB", (32, 32), color).save(out / f"texture/sthlm_racer_{name}.png")
