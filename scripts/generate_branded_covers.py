#!/usr/bin/env python3
"""Generate stylish 800x800 pack cover PNGs for sound packs with no author art.

Run fetch_official_covers.py FIRST: an original cover always beats a generated
one, and this script refuses to overwrite any cover that covers/covers.json
records as original.
"""

from __future__ import annotations

import json
import os
import sys
import math
from PIL import Image, ImageDraw, ImageFont

# Import PACKS metadata from gen_store_manifest.py
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from gen_store_manifest import PACKS, categorize

COVERS_DIR = os.path.join(REPO, "covers")
os.makedirs(COVERS_DIR, exist_ok=True)

REGISTRY_PATH = os.path.join(COVERS_DIR, "covers.json")
REGISTRY: dict[str, dict] = {}
if os.path.exists(REGISTRY_PATH):
    with open(REGISTRY_PATH, encoding="utf-8") as _handle:
        REGISTRY = json.load(_handle)

WIDTH = 800
HEIGHT = 800

# Color schemes by category: (BG_START, BG_END, ACCENT, CARD_BORDER)
THEMES = {
    "Foley & Objects": ((15, 23, 42), (30, 41, 59), (245, 158, 11), (51, 65, 85)),
    "Weapons & Combat": ((69, 10, 10), (136, 19, 55), (239, 68, 68), (153, 27, 27)),
    "Creatures & Animals": ((6, 78, 59), (4, 120, 87), (16, 185, 129), (6, 95, 70)),
    "Impacts & Hits": ((67, 20, 7), (124, 45, 18), (249, 115, 22), (154, 52, 18)),
    "Ambience": ((8, 51, 68), (14, 116, 144), (6, 182, 212), (21, 94, 117)),
    "UI": ((59, 7, 100), (107, 33, 168), (168, 85, 247), (126, 34, 206)),
    "Music": ((76, 5, 25), (131, 24, 67), (236, 72, 153), (157, 23, 77)),
    "Voice": ((15, 23, 42), (30, 58, 138), (56, 189, 248), (30, 64, 175)),
    "Whooshes & Transitions": ((19, 42, 31), (22, 101, 52), (34, 197, 94), (21, 128, 61)),
}
DEFAULT_THEME = ((15, 23, 42), (30, 41, 59), (99, 102, 241), (51, 65, 85))


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                index = 1 if (bold and p.endswith(".ttc")) else 0
                return ImageFont.truetype(p, size, index=index)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_gradient(img: Image.Image, color1: tuple, color2: tuple):
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        ratio = y / float(HEIGHT)
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b, 255))


def draw_waveform(draw: ImageDraw.Draw, y_center: int, width: int, height: int, accent: tuple, folder: str):
    num_bars = 48
    bar_width = 8
    gap = (width - (num_bars * bar_width)) // (num_bars - 1)
    start_x = (WIDTH - width) // 2

    # Deterministic wave envelope based on folder string
    seed = sum(ord(c) for c in folder)
    for i in range(num_bars):
        h_ratio = (math.sin(i * 0.35 + seed) * 0.4 + math.cos(i * 0.15 + seed * 2) * 0.4 + 0.5)
        # Fade edges
        edge_factor = math.sin((i / (num_bars - 1)) * math.pi)
        bar_h = max(8, int(h_ratio * height * edge_factor))
        x = start_x + i * (bar_width + gap)
        y0 = y_center - bar_h // 2
        y1 = y_center + bar_h // 2
        # Glow / bar
        draw.rectangle([x, y0, x + bar_width, y1], fill=accent + (230,), outline=None)


def generate_cover(folder: str, name: str, creator: str, desc: str, opts: dict):
    out_path = os.path.join(COVERS_DIR, f"{folder}.png")

    # An original cover always wins. Protection comes from covers/covers.json,
    # never from a name prefix: the old `folder.startswith("kenney_")` test
    # overwrote the author artwork of any pack whose folder was named otherwise,
    # which is how three packs with real covers ended up showing generated ones.
    if REGISTRY.get(folder, {}).get("origin") == "original":
        if os.path.exists(out_path):
            print(f"Keeping original cover for {folder}")
            return
        print(
            f"WARNING: {folder} is registered as having original art but "
            f"covers/{folder}.png is missing — run fetch_official_covers.py."
        )
        return

    category = opts.get("category", "Foley & Objects")
    theme = THEMES.get(category, DEFAULT_THEME)
    bg_start, bg_end, accent, border = theme

    img = Image.new("RGBA", (WIDTH, HEIGHT))
    draw_gradient(img, bg_start, bg_end)
    draw = ImageDraw.Draw(img)

    # Draw dark inner glass card
    card_margin = 40
    card_rect = [card_margin, card_margin, WIDTH - card_margin, HEIGHT - card_margin]
    draw.rectangle(card_rect, fill=(15, 23, 42, 180), outline=border + (255,), width=2)

    # Top Pill Badge
    font_badge = get_font(18, bold=True)
    badge_text = f"CC0 SOUND PACK • {category.upper()}"
    badge_bbox = font_badge.getbbox(badge_text)
    badge_w = badge_bbox[2] - badge_bbox[0] + 32
    badge_h = 36
    badge_x = (WIDTH - badge_w) // 2
    badge_y = 70

    draw.rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], fill=accent + (40,), outline=accent + (200,), width=1)
    draw.text((badge_x + 16, badge_y + 7), badge_text, fill=accent + (255,), font=font_badge)

    # Title
    font_title = get_font(44, bold=True)
    # Wrap title if long
    words = name.split()
    lines = []
    curr = ""
    for w in words:
        test = (curr + " " + w).strip()
        if font_title.getbbox(test)[2] > (WIDTH - 120):
            lines.append(curr)
            curr = w
        else:
            curr = test
    if curr:
        lines.append(curr)

    title_y = 150
    for line in lines:
        w = font_title.getbbox(line)[2]
        draw.text(((WIDTH - w) // 2, title_y), line, fill=(255, 255, 255, 255), font=font_title)
        title_y += 52

    # Draw stylized waveform center graphic
    wave_y = max(380, title_y + 50)
    draw_waveform(draw, wave_y, width=640, height=140, accent=accent, folder=folder)

    # Creator Credit & License footer
    font_sub = get_font(22, bold=True)
    font_mini = get_font(18, bold=False)

    creator_text = f"Created by {creator}"
    w_cr = font_sub.getbbox(creator_text)[2]
    draw.text(((WIDTH - w_cr) // 2, HEIGHT - 130), creator_text, fill=(226, 232, 240, 255), font=font_sub)

    license_text = "100% PUBLIC DOMAIN • FREE COMMERCIAL USE"
    w_lic = font_mini.getbbox(license_text)[2]
    draw.text(((WIDTH - w_lic) // 2, HEIGHT - 90), license_text, fill=(148, 163, 184, 255), font=font_mini)

    img.save(out_path, "PNG")
    print(f"Generated cover for {folder} ({category}) -> {os.path.basename(out_path)}")


# Why a pack has no author art, by source. Recorded per pack so the next run
# (or the next agent) doesn't re-investigate a known dead end.
NO_ART_REASONS = {
    "opengameart.org": (
        "OpenGameArt auto-generates a waveform image for audio submissions; "
        "there is no author-supplied cover to take."
    ),
    "abstractionmusic.com": (
        "No per-pack page on the author's site, and the current Gumroad "
        "catalogue no longer lists these 2021 monthly/micro packs."
    ),
}


def main():
    print(f"Generating covers for {len(PACKS)} packs...")
    for folder, data in PACKS.items():
        name, creator, website, desc, opts = data
        generate_cover(folder, name, creator, desc, opts)

    # Record provenance for every pack, so which covers are the author's own
    # and which this script invented is auditable rather than assumed.
    registry = dict(REGISTRY)
    for folder, data in PACKS.items():
        if registry.get(folder, {}).get("origin") == "original":
            continue
        website = data[2] or ""
        host = website.split("/")[2] if "://" in website else ""
        registry[folder] = {
            "origin": "generated",
            "reason": NO_ART_REASONS.get(host, "No cover image found on the source page."),
        }
    with open(REGISTRY_PATH, "w", encoding="utf-8") as handle:
        json.dump(dict(sorted(registry.items())), handle, indent=2)
        handle.write("\n")

    originals = sum(1 for v in registry.values() if v.get("origin") == "original")
    print(
        f"All cover images ready: {originals} original, "
        f"{len(registry) - originals} generated (see covers/covers.json)."
    )


if __name__ == "__main__":
    main()
