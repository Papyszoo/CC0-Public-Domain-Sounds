#!/usr/bin/env python3
"""Fetch the original author's cover art for sound packs that have one.

An original cover always beats a generated one, so this runs first and
generate_branded_covers.py only fills the gaps it leaves.

Two rules learned the hard way, both of which had silently produced generated
covers for packs that DO have author art:

1. `<meta>` attribute order is not fixed. itch.io emits
   `content="..." property="og:image"`, Kenney emits the reverse. A regex that
   assumes one order finds nothing and the pack quietly falls back to a
   generated cover. Parse the tag, not a byte order.
2. A failed fetch must be loud. This script exits non-zero and prints every
   failure; a silent fallback is what made the covers untrustworthy.

Every result is recorded in covers/covers.json so which packs carry author art
(and where it came from) is auditable instead of guessed.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import urllib.request

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COVERS_DIR = os.path.join(REPO, "covers")
REGISTRY = os.path.join(COVERS_DIR, "covers.json")
os.makedirs(COVERS_DIR, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

# folder -> page carrying the pack's own artwork. Kenney and itch.io both put a
# usable cover in og:image; anything else needs its own extractor here.
OFFICIAL_PAGES = {
    "kenney_casinoaudio": "https://kenney.nl/assets/casino-audio",
    "kenney_digitalaudio": "https://kenney.nl/assets/digital-audio",
    "kenney_impactsounds": "https://kenney.nl/assets/impact-sounds",
    "kenney_interfacesounds": "https://kenney.nl/assets/interface-sounds",
    "kenney_musicjingles": "https://kenney.nl/assets/music-jingles",
    "kenney_rpgaudio": "https://kenney.nl/assets/rpg-audio",
    "kenney_uiaudio": "https://kenney.nl/assets/ui-audio",
    "kenney_voiceoverfighter": "https://kenney.nl/assets/voiceover-pack-fighter",
    "kenney_voiceoverpack": "https://kenney.nl/assets/voiceover-pack",
    "sci-fi-sounds": "https://kenney.nl/assets/sci-fi-sounds",
    "Maximiliano-Stradex-Ambient": "https://stradex.itch.io/haste-cc0-asets",
}

# Packs whose upstream has no usable author artwork, with the reason. Recorded
# so a later run doesn't re-investigate the same dead ends — drop an entry here
# if a source ever publishes real art.
NO_OFFICIAL_ART = {
    "opengameart": (
        "OpenGameArt renders an automatic waveform-on-background image for audio "
        "submissions; there is no author-supplied cover to take."
    ),
    "abstraction": (
        "Abstraction's site has no per-pack page and the current Gumroad catalogue "
        "no longer lists these 2021 monthly/micro packs."
    ),
    "other": "No cover image found on the source page.",
}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def og_image(html: str) -> str | None:
    """The og:image URL, whatever order the meta tag's attributes are in."""
    for tag in re.findall(r"<meta[^>]*>", html, re.I):
        if re.search(r"""(?:property|name)\s*=\s*["']og:image["']""", tag, re.I):
            match = re.search(r"""content\s*=\s*["']([^"']+)["']""", tag, re.I)
            if match:
                return match.group(1)
    return None


def fetch_cover(folder: str, page_url: str) -> tuple[bool, str]:
    try:
        html = fetch(page_url).decode("utf-8", "ignore")
    except Exception as exc:  # noqa: BLE001 - reported, then counted as a failure
        return False, f"page unreachable: {exc}"

    image_url = og_image(html)
    if not image_url:
        return False, "no og:image on the page"

    try:
        data = fetch(image_url)
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:  # noqa: BLE001
        return False, f"image unreadable ({image_url}): {exc}"

    out_path = os.path.join(COVERS_DIR, f"{folder}.png")
    image.convert("RGBA").save(out_path, "PNG")
    print(f"  [OK]   {folder} <- {image_url} ({image.width}x{image.height})")
    return True, image_url


def main() -> int:
    registry: dict[str, dict] = {}
    if os.path.exists(REGISTRY):
        with open(REGISTRY, encoding="utf-8") as handle:
            registry = json.load(handle)

    failures: list[tuple[str, str]] = []
    print(f"Fetching original cover art for {len(OFFICIAL_PAGES)} pack(s)...")
    for folder, page_url in OFFICIAL_PAGES.items():
        ok, detail = fetch_cover(folder, page_url)
        if ok:
            registry[folder] = {
                "origin": "original",
                "page": page_url,
                "image": detail,
            }
        else:
            print(f"  [FAIL] {folder}: {detail}")
            failures.append((folder, detail))

    with open(REGISTRY, "w", encoding="utf-8") as handle:
        json.dump(dict(sorted(registry.items())), handle, indent=2)
        handle.write("\n")

    originals = sum(1 for v in registry.values() if v.get("origin") == "original")
    print(f"\n{originals} original cover(s) on disk; {len(failures)} failed.")
    if failures:
        print("A pack listed in OFFICIAL_PAGES has author art — do not accept a")
        print("generated cover for it. Fix the extractor or remove the entry:")
        for folder, detail in failures:
            print(f"  {folder}: {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
