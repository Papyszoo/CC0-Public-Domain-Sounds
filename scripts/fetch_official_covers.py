#!/usr/bin/env python3
"""Fetch the original author's cover art for sound packs that have one.

A pack either ships the author's own cover or it ships none: the store renders
its title as text instead. Nothing here invents artwork — a generated cover is
a picture the author never made, and once published it is indistinguishable
from the real thing.

Two rules learned the hard way, both of which had silently hidden author art
behind a generated cover back when this repo still generated them:

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

# Why a pack has no author artwork, keyed by the source host. Recorded per pack
# so a later run — or a later agent — doesn't re-investigate the same dead ends.
# Drop an entry into OFFICIAL_PAGES if a source ever publishes real art.
NO_OFFICIAL_ART = {
    "opengameart.org": (
        "OpenGameArt renders an automatic waveform-on-background image for audio "
        "submissions; there is no author-supplied cover to take."
    ),
    "abstractionmusic.com": (
        "No per-pack page on the author's site, and the current Gumroad catalogue "
        "no longer lists these 2021 monthly/micro packs."
    ),
    "www.warfork.com": (
        "The only art available is the game's Steam capsule, which is not part of "
        "the CC0 sound release."
    ),
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
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from gen_store_manifest import PACKS

    registry: dict[str, dict] = {}
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

    # Every other pack is recorded as having no cover at all — the store shows
    # its title as text. A stale generated PNG left on disk would quietly become
    # a cover again, so those are removed here too.
    for folder, data in PACKS.items():
        if folder in registry:
            continue
        website = data[2] or ""
        host = website.split("/")[2] if "://" in website else ""
        registry[folder] = {
            "origin": "none",
            "reason": NO_OFFICIAL_ART.get(host, "No cover image found on the source page."),
        }
        stale = os.path.join(COVERS_DIR, f"{folder}.png")
        if os.path.exists(stale):
            os.remove(stale)
            print(f"  [RM]   {folder}: removed a cover with no author source")

    with open(REGISTRY, "w", encoding="utf-8") as handle:
        json.dump(dict(sorted(registry.items())), handle, indent=2)
        handle.write("\n")

    originals = sum(1 for v in registry.values() if v.get("origin") == "original")
    none = sum(1 for v in registry.values() if v.get("origin") == "none")
    print(f"\n{originals} pack(s) with author art; {none} show their title as text.")
    if failures:
        print("A pack listed in OFFICIAL_PAGES has author art — do not accept a")
        print("generated cover for it. Fix the extractor or remove the entry:")
        for folder, detail in failures:
            print(f"  {folder}: {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
