#!/usr/bin/env python3
"""Generate NEMO neural-network icon as base64 ICO, printed to stdout."""
import struct, zlib, base64, math

W = H = 64

def dist(ax, ay, bx, by):
    return math.sqrt((bx - ax) ** 2 + (by - ay) ** 2)

def line_alpha(px, py, x1, y1, x2, y2, radius=2.4):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        d = dist(px, py, x1, y1)
    else:
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        d = dist(px, py, x1 + t * dx, y1 + t * dy)
    return max(0.0, (radius - d) / radius) if d < radius else 0.0

# Neural net layout  (input | hidden | output)
NODES = [(12, 20), (12, 32), (12, 44),   # Input
         (32, 16), (32, 32), (32, 48),   # Hidden
         (52, 32)]                         # Output
EDGES = [(0,3),(0,4),(0,5),
         (1,3),(1,4),(1,5),
         (2,3),(2,4),(2,5),
         (3,6),(4,6),(5,6)]

BG     = (7,  9,  15)
LINE   = (30, 80,  200)
NODE   = (59, 126, 255)
NODE_C = (150, 190, 255)

pixels = []
for y in range(H):
    row = []
    for x in range(W):
        r, g, b, a = BG[0], BG[1], BG[2], 255

        # Draw edges
        best_e = 0.0
        for e1, e2 in EDGES:
            al = line_alpha(x, y, *NODES[e1], *NODES[e2])
            if al > best_e:
                best_e = al
        if best_e > 0.0:
            r = int(r * (1 - best_e) + LINE[0] * best_e)
            g = int(g * (1 - best_e) + LINE[1] * best_e)
            b = int(b * (1 - best_e) + LINE[2] * best_e)

        # Draw nodes
        for nx, ny in NODES:
            d = dist(x, y, nx, ny)
            R = 5.5
            if d < R:
                if d < 2.5:
                    al = 1.0
                    nr, ng, nb = NODE_C
                else:
                    al = (R - d) / (R - 2.5)
                    nr, ng, nb = NODE
                r = int(r * (1 - al) + nr * al)
                g = int(g * (1 - al) + ng * al)
                b = int(b * (1 - al) + nb * al)

        row.append((r, g, b, a))
    pixels.append(row)


def make_png(px_data, w, h):
    def chunk(name, data):
        c = name + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    raw = b""
    for row in px_data:
        raw += b"\x00"
        for r2, g2, b2, a2 in row:
            raw += bytes([r2, g2, b2, a2])
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def make_ico(png_data, w, h):
    offset = 6 + 16
    return (
        struct.pack("<HHH", 0, 1, 1)
        + struct.pack(
            "<BBBBHHII",
            w if w < 256 else 0,
            h if h < 256 else 0,
            0, 0, 1, 32, len(png_data), offset,
        )
        + png_data
    )


png = make_png(pixels, W, H)
ico = make_ico(png, W, H)
print(base64.b64encode(ico).decode())
