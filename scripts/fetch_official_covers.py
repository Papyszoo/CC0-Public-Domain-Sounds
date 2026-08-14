#!/usr/bin/env python3
"""Refresh verified original-author covers declared by pack.json files."""

from __future__ import annotations

import io
import json
import re
import sys
import urllib.request
from pathlib import Path

from PIL import Image


REPO = Path(__file__).resolve().parent.parent
PACKS_ROOT = REPO / "packs"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def og_image(html: str) -> str | None:
    for tag in re.findall(r"<meta[^>]*>", html, re.I):
        if re.search(r"""(?:property|name)\s*=\s*["']og:image["']""", tag, re.I):
            match = re.search(r"""content\s*=\s*["']([^"']+)["']""", tag, re.I)
            if match:
                return match.group(1)
    return None


def fetch_cover(page_url: str, output: Path) -> tuple[bool, str]:
    try:
        html = fetch(page_url).decode("utf-8", "ignore")
        image_url = og_image(html)
        if not image_url:
            return False, "no og:image on the page"
        data = fetch(image_url)
        image = Image.open(io.BytesIO(data))
        image.load()
        image.convert("RGBA").save(output, "PNG")
        return True, image_url
    except Exception as exc:  # noqa: BLE001 - report all source failures
        return False, str(exc)


def main() -> int:
    failures = []
    originals = 0
    for metadata_path in sorted(PACKS_ROOT.glob("*/pack.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        cover = metadata.get("cover", {})
        output = metadata_path.parent / "cover.png"

        if cover.get("origin") != "original":
            if output.exists():
                output.unlink()
                print(f"[RM] {metadata_path.parent.name}: no verified author cover")
            continue

        page_url = cover.get("page")
        if not page_url:
            failures.append((metadata_path.parent.name, "missing cover.page"))
            continue
        ok, detail = fetch_cover(page_url, output)
        if not ok:
            failures.append((metadata_path.parent.name, detail))
            print(f"[FAIL] {metadata_path.parent.name}: {detail}")
            continue

        cover["image"] = detail
        metadata_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        originals += 1
        print(f"[OK] {metadata_path.parent.name} <- {detail}")

    print(f"{originals} verified original cover(s) refreshed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
