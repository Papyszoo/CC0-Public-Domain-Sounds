#!/usr/bin/env python3
"""Generate the ModelibrStore external-pack manifest from packs/*/pack.json."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote


REPO = Path(__file__).resolve().parent.parent
PACKS_ROOT = REPO / "packs"
OWNER_REPO = "Papyszoo/CC0-Public-Domain-Sounds"
AUDIO_EXTS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aiff"}
SOUND_CATEGORIES = {
    "Ambience",
    "Music",
    "UI",
    "Footsteps",
    "Impacts & Hits",
    "Weapons & Combat",
    "Voice",
    "Creatures & Animals",
    "Machines & Vehicles",
    "Magic",
    "Foley & Objects",
    "Whooshes & Transitions",
}
REQUIRED_METADATA = ("name", "creator", "website", "license", "description")


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPO), *args], text=True
    ).strip()


def pinned_commit() -> str:
    dirty = git("status", "--porcelain", "--", "packs")
    if dirty and not os.environ.get("ALLOW_DIRTY"):
        sys.exit(
            "packs/ has uncommitted changes — commit and push them first, "
            "or set ALLOW_DIRTY=1 for a preview."
        )

    commit = os.environ.get("PINNED_SHA")
    if not commit:
        commit = git("log", "-1", "--format=%H", "--", "packs")
    if not commit:
        if os.environ.get("ALLOW_DIRTY"):
            commit = git("rev-parse", "HEAD")
        else:
            sys.exit("packs/ has no committed content to pin")

    on_remote = git("branch", "-r", "--contains", commit)
    if not on_remote and not os.environ.get("ALLOW_UNPUSHED"):
        sys.exit(
            f"Commit {commit} is not on a remote branch — push it first, "
            "or set ALLOW_UNPUSHED=1 for a preview."
        )
    return commit


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def external_url(commit: str, relative: str) -> str:
    encoded = "/".join(quote(part) for part in relative.split("/"))
    return f"https://raw.githubusercontent.com/{OWNER_REPO}/{commit}/{encoded}"


def humanize(stem: str) -> str:
    value = re.sub(r"[_\-]+", " ", stem).strip()
    value = re.sub(r"\s+", " ", value)
    return " ".join(word if word.isupper() else word.capitalize() for word in value.split())


def category_for(relative: str, options: dict) -> str | None:
    value = "/" + relative.lower()
    for pattern, category in options.get("category_rules", ()):
        if re.search(pattern, value):
            return category
    return options.get("category")


def load_packs() -> list[tuple[str, Path, dict]]:
    if not PACKS_ROOT.is_dir():
        sys.exit("missing packs/ directory")

    packs = []
    for root in sorted(PACKS_ROOT.iterdir(), key=lambda path: path.name.casefold()):
        metadata_path = root / "pack.json"
        if not root.is_dir() or not metadata_path.is_file():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        missing = [key for key in REQUIRED_METADATA if not metadata.get(key)]
        if missing:
            sys.exit(f"{metadata_path.relative_to(REPO)} is missing: {', '.join(missing)}")
        if metadata["license"] != "CC0":
            sys.exit(f"{metadata_path.relative_to(REPO)} must declare license CC0")
        packs.append((root.name, root, metadata))

    if not packs:
        sys.exit("no packs found under packs/")
    return packs


def main() -> None:
    commit = pinned_commit()
    packs_out = []
    total_files = 0
    total_bytes = 0

    for slug, pack_root, metadata in load_packs():
        sounds_root = pack_root / "sounds"
        if not sounds_root.is_dir():
            sys.exit(f"packs/{slug} has no sounds/ directory")

        options = metadata.get("generation", {})
        files_out = []
        items_out = []
        previews_out = []
        seen_names: dict[str, int] = {}

        for path in sorted(sounds_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in AUDIO_EXTS:
                continue

            logical = path.relative_to(sounds_root).as_posix()
            if path.name.startswith("._") or path.name in options.get("skip_names", ()):
                continue
            if any(logical.startswith(prefix) for prefix in options.get("exclude_prefixes", ())):
                continue
            required_segment = options.get("only_dirs_containing")
            if required_segment and required_segment not in "/" + logical:
                continue

            relative = path.relative_to(REPO).as_posix()
            item_name = humanize(path.stem.removeprefix(options.get("strip_prefix", "")))
            if item_name in seen_names:
                parent = path.parent.relative_to(sounds_root).as_posix()
                candidate = f"{item_name} ({humanize(Path(parent).name)})"
                if candidate in seen_names:
                    seen_names[item_name] += 1
                    candidate = f"{item_name} ({seen_names[item_name]})"
                item_name = candidate
            seen_names.setdefault(item_name, 1)

            size = path.stat().st_size
            files_out.append(
                {
                    "fileName": path.name,
                    "path": relative,
                    "externalUrl": external_url(commit, relative),
                    "sha256": sha256(path),
                    "size": size,
                    "role": "Audio",
                }
            )

            category = category_for(logical, options)
            if category is not None and category not in SOUND_CATEGORIES:
                sys.exit(f"unknown category {category!r} for {relative}")
            item = {
                "name": item_name,
                "itemType": "Sound",
                "isPreviewable": True,
                "files": [{"path": relative, "role": "Audio"}],
            }
            if category is not None:
                item["metadataJson"] = json.dumps({"category": category})
            items_out.append(item)

            thumbnail = pack_root / "thumbnails" / Path(logical).with_suffix(".png")
            if thumbnail.is_file():
                thumbnail_relative = thumbnail.relative_to(REPO).as_posix()
                previews_out.append(
                    {
                        "fileName": thumbnail.name,
                        "path": thumbnail_relative,
                        "externalUrl": external_url(commit, thumbnail_relative),
                        "sha256": sha256(thumbnail),
                        "size": thumbnail.stat().st_size,
                        "contentType": "image/png",
                        "type": "Thumbnail",
                        "itemName": item_name,
                    }
                )

        cover = pack_root / "cover.png"
        if cover.is_file():
            cover_relative = cover.relative_to(REPO).as_posix()
            previews_out.insert(
                0,
                {
                    "fileName": cover.name,
                    "path": cover_relative,
                    "externalUrl": external_url(commit, cover_relative),
                    "sha256": sha256(cover),
                    "size": cover.stat().st_size,
                    "contentType": "image/png",
                    "type": "Thumbnail",
                },
            )

        if not files_out:
            sys.exit(f"pack produced no files: {slug}")
        total_files += len(files_out)
        total_bytes += sum(file["size"] for file in files_out)
        packs_out.append(
            {
                "name": metadata["name"],
                "creator": metadata["creator"],
                "website": metadata["website"],
                "description": metadata["description"],
                "license": metadata["license"],
                "folder": f"packs/{slug}",
                "itemCount": len(items_out),
                "items": items_out,
                "files": files_out,
                "previews": previews_out,
            }
        )

    manifest = {
        "source": {
            "repository": f"https://github.com/{OWNER_REPO}",
            "commit": commit,
        },
        "license": "CC0-1.0",
        "packs": packs_out,
    }
    output = Path(os.environ.get("MANIFEST_OUTPUT", REPO / "store-manifest.json"))
    output.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"packs: {len(packs_out)}")
    print(f"files: {total_files} ({total_bytes / 1e6:.1f} MB)")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
