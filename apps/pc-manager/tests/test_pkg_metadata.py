import io
import struct
import unittest
from odium_pc.pkg_metadata import read_package_hints

CID = b"UP0000-CUSA12345_00-TESTGAME00000000"


def make_pkg(*, with_sfo=False, corrupt_table=False):
    header = bytearray(0x1000)
    header[:4] = b"\x7fCNT"
    header[0x40:0x64] = CID
    if not with_sfo:
        return bytes(header)
    kv = [("TITLE", "Independent Test Game"), ("TITLE_ID", "CUSA12345"),
          ("APP_VER", "01.40"), ("CONTENT_ID", CID.decode())]
    key_table = b""
    data_table = b""
    entries = []
    for key, val in kv:
        koff = len(key_table)
        key_table += key.encode() + b"\x00"
        voff = len(data_table)
        encoded = val.encode() + b"\x00"
        data_table += encoded
        entries.append(struct.pack("<HHIII", koff, 0x0204, len(encoded), len(encoded), voff))
    key_offset = 20 + 16 * len(kv)
    data_offset = key_offset + len(key_table)
    sfo = struct.pack("<4sIIII", b"\x00PSF", 0x101, key_offset, data_offset,
                      len(kv)) + b"".join(entries) + key_table + data_table
    struct.pack_into(">I", header, 0x10, 999999 if corrupt_table else 1)
    struct.pack_into(">I", header, 0x18, 0x100)
    entry = struct.pack(">IIIIIIQ", 0x1000, 0, 0, 0, 0x1000, len(sfo), 0)
    header[0x100:0x120] = entry
    return bytes(header) + sfo


class MetadataTests(unittest.TestCase):
    def test_header_only(self):
        h = read_package_hints(io.BytesIO(make_pkg()))
        self.assertEqual(h.title_id, "CUSA12345")
        self.assertEqual(h.content_id, CID.decode())
        self.assertIsNone(h.title)

    def test_sfo_read(self):
        h = read_package_hints(io.BytesIO(make_pkg(with_sfo=True)))
        self.assertEqual(h.title, "Independent Test Game")
        self.assertEqual(h.app_version, "01.40")
        self.assertEqual(h.title_id, "CUSA12345")

    def test_bad_table_is_bounded(self):
        h = read_package_hints(io.BytesIO(make_pkg(with_sfo=True, corrupt_table=True)))
        self.assertIsNone(h.title)
        self.assertEqual(h.title_id, "CUSA12345")

    def test_reject_other_format(self):
        with self.assertRaises(ValueError):
            read_package_hints(io.BytesIO(b"\x7fPKG" + b"\x00" * 400))

    def test_zero_and_truncated(self):
        h = read_package_hints(io.BytesIO(b"\x7fCNT"))
        self.assertIsNone(h.title_id)
        self.assertIn("Truncated", h.note)


if __name__ == "__main__":
    unittest.main()
