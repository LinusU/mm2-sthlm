import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import race_vehicle


class RaceVehicleTests(unittest.TestCase):
    def test_native_model_clearance_keeps_tyres_below_body(self):
        data = race_vehicle.mesh()
        self.assertEqual(data[:4], b"PKG3")
        offset, parts = 4, {}
        while offset < len(data):
            self.assertEqual(data[offset : offset + 4], b"FILE")
            size = data[offset + 4]
            name = data[offset + 5 : offset + 4 + size].decode()
            length = struct.unpack_from("<I", data, offset + 5 + size)[0]
            begin = offset + 9 + size
            if name != "shaders":
                count = struct.unpack_from("<I", data, begin + 4)[0]
                parts[name] = [
                    struct.unpack_from("<3f", data, begin + 36 + i * 20)
                    for i in range(count)
                ]
            offset = begin + length
        self.assertEqual(offset, len(data))
        self.assertGreater(min(p[1] for p in parts["BODY_H"]), 0.2)
        centres = []
        for i in range(4):
            vertices = parts[f"WHL{i}_H"]
            self.assertAlmostEqual(min(p[1] for p in vertices), 0, places=5)
            self.assertAlmostEqual(max(p[1] for p in vertices), 0.64, places=5)
            centres.append(
                tuple(
                    (min(p[k] for p in vertices) + max(p[k] for p in vertices)) / 2
                    for k in (0, 2)
                )
            )
        self.assertEqual(len(set(centres)), 4)
        bound_y = [
            float(line.split()[2])
            for line in race_vehicle.bound().splitlines()
            if line.startswith("v ")
        ]
        self.assertGreater(min(bound_y), 0.2)
        self.assertLessEqual(max(bound_y), max(p[1] for p in parts["BODY_H"]) + 1e-5)

    def test_compact_has_front_steering_with_fixed_rear_axle(self):
        text = race_vehicle.tuning()
        front, back = text.split("WheelBack", 1)
        self.assertIn("SteeringLimit 0.5", front)
        self.assertIn("SteeringLimit 0\n", back)
        self.assertNotIn("SteeringLimit 0.5", back)
