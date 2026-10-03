import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import props


class PropPathsetTests(unittest.TestCase):
    def test_mixed_assets_keep_directed_pairs_separate_from_point_stamps(self):
        instances = [
            {"asset": "sthlm_tree", "position": [1, 2, 3]},
            {"asset": "gate", "position": [4, 5, 6], "direction": [7, 5, 9]},
            {"asset": "sthlm_tree", "position": [10, 11, 12]},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            props.write(out, instances)
            data = (out / "city/stockholm/props.pathset").read_bytes()
        self.assertEqual(data[:4], b"PTH1")
        self.assertEqual(struct.unpack_from("<II", data, 4), (2, 0))
        offset = 12
        parsed = []
        for _ in range(2):
            name = data[offset : offset + 32].rstrip(b"\0").decode()
            count, _ = struct.unpack_from("<II", data, offset + 32)
            offset += 40
            points = []
            for _ in range(count):
                flags, *point = struct.unpack_from("<I3f", data, offset)
                self.assertEqual(flags, 0)
                points.append(point)
                offset += 16
            kind = data[offset]
            offset += 4
            parsed.append((name, kind, points))
        self.assertEqual(offset, len(data))
        self.assertEqual(parsed[0], ("sthlm_tree", 0, [[1, 2, 3], [10, 11, 12]]))
        self.assertEqual(parsed[1], ("gate", 1, [[4, 5, 6], [7, 5, 9]]))
