import copy
from pathlib import Path
import sys
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from expanded import ChunkedWriter  # noqa: E402
from sthlm import PsdlWriter  # noqa: E402


def fixture():
    writer = PsdlWriter()
    writer.textures = ["road", "facade"]
    writer.heights = [0.0, 12.5]
    for room in range(3):
        refs = [writer.vertex((room * 20 + i, i % 2, i // 2)) for i in range(4)]
        attrs = [
            0x50,
            1,
            0x92,
            *refs,
            0xA9,
            *refs[:3],
            0xB1,
            *refs[1:],
            0x5E,
            0,
            1,
            24,
            8,
            refs[0],
            refs[1],
            0x3C,
            0,
            1,
            refs[2],
            refs[3],
        ]
        writer.rooms.append((refs, attrs, 4 if room != 1 else 0))
    writer.water_rooms = [1, 3]
    return writer


def geometry(writer):
    result = []
    counts = {10: 1, 2: 4, 5: 3, 6: 3, 11: 6, 7: 4}
    vertex_slots = {
        10: (),
        2: (0, 1, 2, 3),
        5: (0, 1, 2),
        6: (0, 1, 2),
        11: (4, 5),
        7: (2, 3),
    }
    for index, (perimeter, attrs, flags) in enumerate(writer.rooms, 1):
        decoded = []
        cursor = 0
        while cursor < len(attrs):
            code = attrs[cursor]
            kind = (code >> 3) & 15
            words = list(attrs[cursor + 1 : cursor + 1 + counts[kind]])
            for slot in vertex_slots[kind]:
                words[slot] = writer.vertices[words[slot]]
            decoded.append((code, tuple(words)))
            cursor += counts[kind] + 1
        result.append(
            (
                tuple(writer.vertices[v] for v in perimeter),
                decoded,
                flags,
                index in writer.water_rooms,
            )
        )
    return result


def read_native(path):
    data = path.read_bytes()
    offset = 4

    def read(fmt):
        nonlocal offset
        values = struct.unpack_from("<" + fmt, data, offset)
        offset += struct.calcsize("<" + fmt)
        return values

    writer = PsdlWriter()
    version, count = read("II")
    assert data[:4] == b"PSD0" and version == 2 and count <= 65535
    writer.vertices = [read("3f") for _ in range(count)]
    writer.heights = [read("f")[0] for _ in range(read("I")[0])]
    for _ in range(read("I")[0] - 1):
        size = read("B")[0]
        writer.textures.append(data[offset : offset + size - 1].decode())
        offset += size
    count, _ = read("II")
    assert count <= 65535
    for _ in range(count - 1):
        perimeter, words = read("II")
        refs = [read("HH")[0] for _ in range(perimeter)]
        writer.rooms.append((refs, list(read("H" * words)), 0))
    flags = read("B" * count)
    writer.rooms = [(p, a, flags[i]) for i, (p, a, _) in enumerate(writer.rooms, 1)]
    writer.water_rooms = [
        int(line) for line in path.with_suffix(".water").read_text().splitlines()[1:]
    ]
    return writer


class VertexPoolTests(unittest.TestCase):
    def test_complete_room_geometry_tables_flags_water_preserved(self):
        original = fixture()
        snapshot = copy.deepcopy(original.__dict__)
        pools = original.vertex_pools(6)
        self.assertEqual(len(pools), 3)
        self.assertEqual(
            [room for pool in pools for room in geometry(pool)], geometry(original)
        )
        self.assertEqual([p.water_rooms for p in pools], [[1], [], [1]])
        for pool in pools:
            self.assertLessEqual(len(pool.vertices), 6)
            self.assertEqual(pool.heights, original.heights)
            self.assertEqual(pool.textures, original.textures)
        self.assertEqual(original.__dict__, snapshot)
        self.assertEqual(
            [p.__dict__ for p in pools], [p.__dict__ for p in original.vertex_pools(6)]
        )
        self.assertIs(original.vertex_pools()[0], original)

    def test_rejects_single_room_overflow_unsupported_truncated_invalid(self):
        for change, error in [
            (lambda w: None, "Single room"),
            (lambda w: w.rooms[0][1].__setitem__(0, 0), "Unsupported"),
            (lambda w: w.rooms[0][1].append(0xB1), "Truncated"),
            (lambda w: w.rooms[0][0].append(999), "Invalid source"),
        ]:
            writer = fixture()
            change(writer)
            with self.assertRaisesRegex(ValueError, error):
                writer.vertex_pools(3 if error == "Single room" else 6)

    def test_unlimited_source_indices_remap_to_native_u16(self):
        writer = fixture()
        offset = 65536
        writer.vertices = [(0, 0, 0)] * offset + writer.vertices
        for perimeter, attrs, _ in writer.rooms:
            perimeter[:] = [v + offset for v in perimeter]
            for slot in (3, 4, 5, 6, 8, 9, 10, 12, 13, 14, 20, 21, 25, 26):
                attrs[slot] += offset
        pools = writer.vertex_pools()
        self.assertEqual(len(pools), 1)
        self.assertEqual(len(pools[0].vertices), 12)
        self.assertEqual(geometry(pools[0]), geometry(writer))

    def test_native_room_count_limit(self):
        writer = fixture()
        writer.rooms = [writer.rooms[0]] * 65535
        writer.water_rooms = [65535]
        pools = writer.vertex_pools()
        self.assertEqual([len(p.rooms) for p in pools], [65534, 1])
        self.assertEqual(pools[1].water_rooms, [1])

    def test_chunk_spills_are_deterministic_with_local_primary_water(self):
        with tempfile.TemporaryDirectory() as folder:
            chunks = ChunkedWriter((0, 0, 0))
            original = fixture()
            chunks.parts[(0, 0)] = original
            path = Path(folder) / "city" / "stockholm.psdl"
            chunks.write(path, (0, 0, 0), pool_limit=6)
            self.assertEqual(chunks.water_rooms, [1])
            self.assertEqual(list(chunks.parts), [(0, 0), (0, 0, 1), (0, 0, 2)])
            names = path.with_suffix(".chunks").read_text().splitlines()[1:]
            self.assertEqual(
                names,
                [
                    "city/stockholm.parts/part_0_0_spill_1.psdl",
                    "city/stockholm.parts/part_0_0_spill_2.psdl",
                ],
            )
            self.assertEqual(
                [room for p in chunks.parts.values() for room in geometry(p)],
                geometry(original),
            )
            emitted = [
                read_native(p) for p in [path, *(Path(folder) / n for n in names)]
            ]
            self.assertEqual(
                [room for pool in emitted for room in geometry(pool)],
                geometry(original),
            )
            for pool in emitted:
                self.assertLessEqual(len(pool.vertices), 6)
            for name in names:
                self.assertTrue((Path(folder) / name).is_file())
            self.assertEqual(
                (Path(folder) / names[1]).with_suffix(".water").read_text(), "0.2\n1\n"
            )

    def test_part_cap_preflight_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            chunks = ChunkedWriter((0, 0, 0))
            chunks.parts = {(i, 0): fixture() for i in range(130)}
            path = Path(folder) / "city" / "stockholm.psdl"
            with self.assertRaisesRegex(ValueError, "129"):
                chunks.write(path, (0, 0, 0))
            self.assertFalse(path.exists())

    def test_rewriting_shards_preserves_manifest_order_and_native_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            chunks = ChunkedWriter((0, 0, 0))
            chunks.parts = {(0, 0): fixture(), (-1, 0): fixture()}
            path = root / "city/stockholm.psdl"
            chunks.write(path, (0, 0, 0), pool_limit=6)
            before = {
                p.relative_to(root): p.read_bytes()
                for p in root.rglob("*")
                if p.is_file()
            }
            chunks.write(path, (0, 0, 0), pool_limit=6)
            after = {
                p.relative_to(root): p.read_bytes()
                for p in root.rglob("*")
                if p.is_file()
            }
            self.assertEqual(before, after)
