import struct, sys

path = "/tmp/pw-test.png"
with open(path, "rb") as f:
    d = f.read(32)
assert d[:8] == b"\x89PNG\r\n\x1a\n", "bad PNG signature"
w, h = struct.unpack(">II", d[16:24])
import os
print("valid PNG %dx%d, %d bytes" % (w, h, os.path.getsize(path)))
