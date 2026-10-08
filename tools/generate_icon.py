"""Render a simple native tray mark as an opaque App Store icon, no dependencies."""
import json
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]


def segment_distance(x, y, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    t = max(0, min(1, ((x-x1)*dx + (y-y1)*dy)/(dx*dx + dy*dy)))
    return ((x-x1-t*dx)**2 + (y-y1-t*dy)**2)**0.5


def main():
    size = 1024
    strokes = [(235, 480, 315, 350), (315, 350, 709, 350), (709, 350, 789, 480),
               (235, 480, 235, 700), (235, 700, 789, 700), (789, 700, 789, 480),
               (235, 480, 400, 480), (400, 480, 440, 560), (440, 560, 584, 560),
               (584, 560, 624, 480), (624, 480, 789, 480)]
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            light = 1 - y / size
            color = [int(5 + 6*light), int(109 + 28*light), int(124 + 24*light)]
            if 200 < x < 824 and 315 < y < 734:
                distance = min(segment_distance(x, y, *stroke) for stroke in strokes)
                alpha = max(0, min(1, 24-distance))
                color = [int(channel*(1-alpha) + 255*alpha) for channel in color]
            rows.extend(color)
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind+data) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b"")
    catalog = ROOT / "AtodeYaruBox/Resources/Assets.xcassets"
    icon = catalog / "AppIcon.appiconset"; icon.mkdir(parents=True, exist_ok=True)
    (icon / "AppIcon.png").write_bytes(png)
    (catalog / "Contents.json").write_text(json.dumps({"info": {"author": "xcode", "version": 1}}, indent=2) + "\n")
    (icon / "Contents.json").write_text(json.dumps({"images": [{"filename": "AppIcon.png", "idiom": "universal", "platform": "ios", "size": "1024x1024"}], "info": {"author": "xcode", "version": 1}}, indent=2) + "\n")
    colors = ROOT / "Shared/Resources/Colors.xcassets"
    colors.mkdir(parents=True, exist_ok=True)
    (colors/"Contents.json").write_text(json.dumps({"info": {"author": "xcode", "version": 1}}))
    palettes = {"BoxAccent": ["006A70", "64DAD4", "004A4D", "B4FFFA"], "BoxButton": ["006A70", "006A70", "004A4D", "004A4D"]}
    for name, palette in palettes.items():
        entries = []
        for index, color in enumerate(palette):
            entry = {"idiom": "universal", "color": {"color-space": "srgb", "components": {"red": "0x"+color[:2], "green": "0x"+color[2:4], "blue": "0x"+color[4:], "alpha": "1.000"}}}
            if index == 1: entry["appearances"] = [{"appearance": "luminosity", "value": "dark"}]
            elif index == 2: entry["appearances"] = [{"appearance": "contrast", "value": "high"}]
            elif index == 3: entry["appearances"] = [{"appearance": "luminosity", "value": "dark"}, {"appearance": "contrast", "value": "high"}]
            entries.append(entry)
        folder = colors/(name+".colorset"); folder.mkdir(exist_ok=True)
        (folder/"Contents.json").write_text(json.dumps({"colors": entries, "info": {"author": "xcode", "version": 1}}, indent=2)+"\n")
    print("Generated opaque 1024x1024 AppIcon")


if __name__ == "__main__": main()
