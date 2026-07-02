#!/usr/bin/env python3
"""Generate Chrome/Edge store screenshot and promo PNG placeholders.

No external dependencies are required. The output images match Chrome Web Store
recommended screenshot and promo dimensions and are intended as editable store
asset drafts.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "extension" / "store_assets" / "generated"

CYAN = (34, 211, 238, 255)
PURPLE = (168, 85, 247, 255)
BLUE = (15, 23, 42, 255)
DARK = (2, 6, 23, 255)
PANEL = (15, 23, 42, 238)
WHITE = (248, 250, 252, 255)
MUTED = (148, 163, 184, 255)
GREEN = (52, 211, 153, 255)
RED = (248, 113, 113, 255)

ASSETS = [
    ("chrome_screenshot_1_popup_640x400.png", 640, 400, "popup"),
    ("chrome_screenshot_2_youtube_overlay_640x400.png", 640, 400, "youtube"),
    ("chrome_screenshot_3_claim_cards_640x400.png", 640, 400, "cards"),
    ("chrome_screenshot_4_audio_mode_640x400.png", 640, 400, "audio"),
    ("chrome_screenshot_5_product_page_640x400.png", 640, 400, "product"),
    ("chrome_small_promo_440x280.png", 440, 280, "promo"),
    ("chrome_marquee_promo_1400x560.png", 1400, 560, "marquee"),
]

FONT = {
    " ": ["000", "000", "000", "000", "000", "000", "000"],
    "0": ["111", "101", "101", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "010", "010", "111"],
    "2": ["111", "001", "001", "111", "100", "100", "111"],
    "3": ["111", "001", "001", "111", "001", "001", "111"],
    "4": ["101", "101", "101", "111", "001", "001", "001"],
    "5": ["111", "100", "100", "111", "001", "001", "111"],
    "6": ["111", "100", "100", "111", "101", "101", "111"],
    "7": ["111", "001", "001", "010", "010", "010", "010"],
    "8": ["111", "101", "101", "111", "101", "101", "111"],
    "9": ["111", "101", "101", "111", "001", "001", "111"],
    "A": ["010", "101", "101", "111", "101", "101", "101"],
    "B": ["110", "101", "101", "110", "101", "101", "110"],
    "C": ["111", "100", "100", "100", "100", "100", "111"],
    "D": ["110", "101", "101", "101", "101", "101", "110"],
    "E": ["111", "100", "100", "110", "100", "100", "111"],
    "F": ["111", "100", "100", "110", "100", "100", "100"],
    "G": ["111", "100", "100", "101", "101", "101", "111"],
    "H": ["101", "101", "101", "111", "101", "101", "101"],
    "I": ["111", "010", "010", "010", "010", "010", "111"],
    "J": ["001", "001", "001", "001", "101", "101", "111"],
    "K": ["101", "101", "110", "100", "110", "101", "101"],
    "L": ["100", "100", "100", "100", "100", "100", "111"],
    "M": ["101", "111", "111", "101", "101", "101", "101"],
    "N": ["101", "111", "111", "111", "101", "101", "101"],
    "O": ["111", "101", "101", "101", "101", "101", "111"],
    "P": ["111", "101", "101", "111", "100", "100", "100"],
    "Q": ["111", "101", "101", "101", "111", "001", "001"],
    "R": ["110", "101", "101", "110", "110", "101", "101"],
    "S": ["111", "100", "100", "111", "001", "001", "111"],
    "T": ["111", "010", "010", "010", "010", "010", "010"],
    "U": ["101", "101", "101", "101", "101", "101", "111"],
    "V": ["101", "101", "101", "101", "101", "101", "010"],
    "W": ["101", "101", "101", "101", "111", "111", "101"],
    "X": ["101", "101", "101", "010", "101", "101", "101"],
    "Y": ["101", "101", "101", "010", "010", "010", "010"],
    "Z": ["111", "001", "001", "010", "100", "100", "111"],
    "-": ["000", "000", "000", "111", "000", "000", "000"],
    "/": ["001", "001", "010", "010", "100", "100", "100"],
    ".": ["000", "000", "000", "000", "000", "110", "110"],
}


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


class Canvas:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.pixels = [[DARK for _ in range(width)] for _ in range(height)]

    def set(self, x: int, y: int, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y][x] = color

    def rect(self, x: int, y: int, w: int, h: int, color):
        for yy in range(max(0, y), min(self.height, y + h)):
            for xx in range(max(0, x), min(self.width, x + w)):
                self.pixels[yy][xx] = color

    def outline(self, x: int, y: int, w: int, h: int, color, thickness: int = 2):
        self.rect(x, y, w, thickness, color)
        self.rect(x, y + h - thickness, w, thickness, color)
        self.rect(x, y, thickness, h, color)
        self.rect(x + w - thickness, y, thickness, h, color)

    def circle(self, cx: int, cy: int, radius: int, color, thickness: int = 2):
        r2 = radius * radius
        inner = max(0, radius - thickness) ** 2
        for y in range(cy - radius - 1, cy + radius + 2):
            for x in range(cx - radius - 1, cx + radius + 2):
                d = (x - cx) * (x - cx) + (y - cy) * (y - cy)
                if inner <= d <= r2:
                    self.set(x, y, color)

    def text(self, x: int, y: int, text: str, color=WHITE, scale: int = 3):
        cursor = x
        for ch in text.upper():
            glyph = FONT.get(ch, FONT[" "])
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    if bit == "1":
                        self.rect(cursor + gx * scale, y + gy * scale, scale, scale, color)
            cursor += 4 * scale

    def gradient(self):
        for y in range(self.height):
            for x in range(self.width):
                glow = int(34 * (x / max(1, self.width)) + 26 * (1 - y / max(1, self.height)))
                self.pixels[y][x] = (2 + glow // 5, 6 + glow // 3, 23 + glow, 255)

    def save(self, path: Path):
        rows = []
        for row in self.pixels:
            data = bytearray([0])
            for px in row:
                data.extend(px)
            rows.append(bytes(data))
        raw = b"".join(rows)
        png = b"\x89PNG\r\n\x1a\n"
        png += chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 6, 0, 0, 0))
        png += chunk(b"IDAT", zlib.compress(raw, 9))
        png += chunk(b"IEND", b"")
        path.write_bytes(png)


def draw_common(c: Canvas, title: str, subtitle: str):
    c.gradient()
    c.circle(72, 70, 42, CYAN, 4)
    c.circle(72, 70, 22, PURPLE, 5)
    c.rect(130, 40, c.width - 170, 6, CYAN)
    c.text(130, 58, title, WHITE, 4)
    c.text(130, 94, subtitle, MUTED, 2)


def draw_asset(width: int, height: int, kind: str) -> Canvas:
    c = Canvas(width, height)
    draw_common(c, "CLAIMRADAR BG", kind.replace("_", " "))
    if kind == "popup":
        c.rect(70, 135, 230, 215, PANEL)
        c.outline(70, 135, 230, 215, CYAN, 2)
        c.text(92, 160, "POPUP", WHITE, 3)
        c.text(92, 198, "ACTIVE TAB", CYAN, 2)
        c.text(92, 226, "STORAGE", CYAN, 2)
        c.text(92, 254, "USER START", GREEN, 2)
        c.rect(340, 150, 230, 170, PANEL)
        c.outline(340, 150, 230, 170, PURPLE, 2)
        c.text(365, 180, "LOCAL HISTORY", WHITE, 2)
        c.text(365, 215, "NO DATA SALE", GREEN, 2)
    elif kind == "youtube":
        c.rect(45, 140, 330, 190, (17, 24, 39, 255))
        c.outline(45, 140, 330, 190, RED, 4)
        c.rect(410, 125, 190, 225, PANEL)
        c.outline(410, 125, 190, 225, CYAN, 2)
        c.text(430, 158, "YOUTUBE", WHITE, 3)
        c.text(430, 200, "CAPTIONS", CYAN, 2)
        c.text(430, 230, "CLAIMS", GREEN, 2)
    elif kind == "cards":
        for i, color in enumerate([CYAN, PURPLE, GREEN]):
            y = 135 + i * 72
            c.rect(70, y, 500, 54, PANEL)
            c.outline(70, y, 500, 54, color, 2)
            c.text(94, y + 15, f"CLAIM {i+1}", WHITE, 2)
            c.rect(240, y + 18, 260, 10, color)
    elif kind == "audio":
        c.rect(80, 145, 480, 160, PANEL)
        c.outline(80, 145, 480, 160, CYAN, 3)
        for i in range(24):
            h = 18 + (i % 7) * 11
            c.rect(115 + i * 16, 250 - h, 8, h, CYAN if i % 2 else PURPLE)
        c.text(130, 165, "TAB AUDIO", WHITE, 4)
        c.text(130, 210, "USER STARTED", GREEN, 2)
    elif kind == "product":
        c.rect(52, 135, 536, 188, PANEL)
        c.outline(52, 135, 536, 188, PURPLE, 3)
        c.text(92, 170, "PRODUCT PAGE", WHITE, 3)
        c.text(92, 215, "PRIVACY", CYAN, 2)
        c.text(92, 245, "METHODOLOGY", CYAN, 2)
        c.text(92, 275, "SOURCES", GREEN, 2)
    else:
        c.rect(width // 10, height // 3, width * 8 // 10, height // 3, PANEL)
        c.outline(width // 10, height // 3, width * 8 // 10, height // 3, CYAN, max(2, width // 220))
        c.text(width // 8, height // 2 - 28, "CLAIMRADAR BG", WHITE, max(3, width // 220))
        c.text(width // 8, height // 2 + 20, "BULGARIAN CLAIM DETECTION", CYAN, max(2, width // 360))
    return c


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, width, height, kind in ASSETS:
        canvas = draw_asset(width, height, kind)
        canvas.save(OUT / name)
        print(f"Generated {OUT / name}")


if __name__ == "__main__":
    main()
