#!/usr/bin/env python3
"""Fetch official cover images for sound packs from Kenney.nl, itch.io, etc."""

import os
import re
import urllib.request
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COVERS_DIR = os.path.join(REPO, "covers")
os.makedirs(COVERS_DIR, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

KENNEY_PACKS = {
    "kenney_casinoaudio": "casino-audio",
    "kenney_digitalaudio": "digital-audio",
    "kenney_impactsounds": "impact-sounds",
    "kenney_interfacesounds": "interface-sounds",
    "kenney_musicjingles": "music-jingles",
    "kenney_rpgaudio": "rpg-audio",
    "kenney_uiaudio": "ui-audio",
    "kenney_voiceoverfighter": "voiceover-pack-fighter",
    "kenney_voiceoverpack": "voiceover-pack",
    "sci-fi-sounds": "sci-fi-sounds",
}

OTHER_OFFICIAL_URLS = {
    "Maximiliano-Stradex-Ambient": "https://stradex.itch.io/haste-cc0-asets",
    "MMRetroArcadeSoundsPack1_0_5": "http://www.themotionmonkey.co.uk/free-resources/retro-arcade-sounds/",
}

def download_image(url: str, out_path: str) -> bool:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        tmp_path = out_path + ".tmp"
        with open(tmp_path, "wb") as fh:
            fh.write(data)
        # Convert / normalize to PNG
        with Image.open(tmp_path) as img:
            img = img.convert("RGBA")
            img.save(out_path, "PNG")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        print(f"  [OK] Saved {os.path.basename(out_path)} ({len(data)} bytes)")
        return True
    except Exception as e:
        print(f"  [FAIL] {url}: {e}")
        return False

def fetch_kenney_cover(folder: str, slug: str) -> bool:
    out_path = os.path.join(COVERS_DIR, f"{folder}.png")
    page_url = f"https://kenney.nl/assets/{slug}"
    try:
        req = urllib.request.Request(page_url, headers=HEADERS)
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
        m = re.search(r"property=['\"]og:image['\"]\s+content=['\"]([^'\"]+)['\"]", html)
        if not m:
            m = re.search(r"class=['\"]screenshot[^'\"]*['\"]\s+href=['\"]([^'\"]+)['\"]", html)
        if m:
            img_url = m.group(1)
            print(f"Fetching Kenney cover for {folder} from {img_url}...")
            return download_image(img_url, out_path)
    except Exception as e:
        print(f"Error scraping {page_url}: {e}")
    return False

def fetch_itch_cover(folder: str, page_url: str) -> bool:
    out_path = os.path.join(COVERS_DIR, f"{folder}.png")
    try:
        req = urllib.request.Request(page_url, headers=HEADERS)
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
        m = re.search(r"class=['\"]header_image['\"][^>]*src=['\"]([^'\"]+)['\"]", html) or \
            re.search(r"property=['\"]og:image['\"]\s+content=['\"]([^'\"]+)['\"]", html)
        if m:
            img_url = m.group(1)
            print(f"Fetching itch cover for {folder} from {img_url}...")
            return download_image(img_url, out_path)
    except Exception as e:
        print(f"Error scraping {page_url}: {e}")
    return False

def main():
    print("Fetching official covers...")
    success_count = 0
    for folder, slug in KENNEY_PACKS.items():
        if fetch_kenney_cover(folder, slug):
            success_count += 1

    for folder, url in OTHER_OFFICIAL_URLS.items():
        if fetch_itch_cover(folder, url):
            success_count += 1

    print(f"Downloaded {success_count} official cover images.")

if __name__ == "__main__":
    main()
