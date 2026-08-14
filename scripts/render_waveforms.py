#!/usr/bin/env python3
"""Render a waveform PNG for every audio file in store-manifest.json.

Output: packs/<pack>/thumbnails/<audio-relative-path>.png.
Two-pass: peak-detect (volumedetect), then showwavespic with makeup gain so
quiet recordings don't render as flat lines. Gain capped at +20 dB.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZE = "800x160"
COLOR = "#64748b"
MAX_GAIN_DB = 20.0

def render(path: str) -> tuple[str, str | None]:
    src = os.path.join(REPO, path)
    parts = path.replace(os.sep, "/").split("/")
    if len(parts) < 4 or parts[0] != "packs" or parts[2] != "sounds":
        return path, "unexpected manifest audio path"
    out = os.path.join(
        REPO,
        "packs",
        parts[1],
        "thumbnails",
        os.path.splitext("/".join(parts[3:]))[0] + ".png",
    )
    if os.path.isfile(out):
        return path, None
    os.makedirs(os.path.dirname(out), exist_ok=True)

    try:
        probe = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", src, "-af", "volumedetect",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=120,
        )
        m = re.search(r"max_volume: (-?[\d.]+) dB", probe.stderr)
        gain = min(max(-float(m.group(1)), 0.0), MAX_GAIN_DB) if m else 0.0

        filt = (
            f"aformat=channel_layouts=mono,volume={gain:.1f}dB,"
            f"showwavespic=s={SIZE}:colors={COLOR}:filter=peak"
        )
        res = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", src,
             "-filter_complex", filt, "-frames:v", "1", "-y", out],
            capture_output=True, text=True, timeout=120,
        )
        if res.returncode != 0 or not os.path.isfile(out):
            return path, (res.stderr.strip() or "no output")[:300]
        return path, None
    except Exception as e:  # timeout, decode crash — report, don't abort run
        return path, repr(e)[:300]

def main() -> None:
    with open(os.path.join(REPO, "store-manifest.json")) as fh:
        manifest = json.load(fh)
    paths = [f["path"] for p in manifest["packs"] for f in p["files"]]
    print(f"rendering {len(paths)} waveforms...")

    failures = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for i, (path, err) in enumerate(pool.map(render, paths), 1):
            if err:
                failures.append((path, err))
            if i % 250 == 0:
                print(f"  {i}/{len(paths)} ({len(failures)} failed)")

    print(f"done: {len(paths) - len(failures)} ok, {len(failures)} failed")
    for path, err in failures:
        print(f"FAILED {path}: {err}")
    sys.exit(1 if failures else 0)

if __name__ == "__main__":
    main()
