#!/usr/bin/env python3
"""Generate store-manifest.json for the CC0-Public-Domain-Sounds fork.

Shape follows base-meshes/store-manifest.json (files/items with externalUrl
pinned to a commit SHA), extended to multiple packs, each carrying
name/creator/website/description/license as requested.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from urllib.parse import quote

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_BASE = "https://raw.githubusercontent.com/Papyszoo/CC0-Public-Domain-Sounds"

AUDIO_EXTS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aiff"}

# Store taxonomy v1 (ModelibrStore docs/taxonomy.json, PackItemType.Sound).
# Submission validation is strict — only these names are accepted.
SOUND_CATEGORIES = {
    "Ambience", "Music", "UI", "Footsteps", "Impacts & Hits",
    "Weapons & Combat", "Voice", "Creatures & Animals",
    "Machines & Vehicles", "Magic", "Foley & Objects",
    "Whooshes & Transitions",
}


def categorize(relpath: str, opts: dict) -> str | None:
    """First matching keyword rule wins, else the pack default (may be None)."""
    low = relpath.lower()
    for pattern, cat in opts.get("category_rules", ()):
        if re.search(pattern, low):
            return cat
    return opts.get("category")

OGA = "https://opengameart.org/content/"
ABSTRACTION = "https://abstractionmusic.com"
KENNEY = "https://kenney.nl"
UPSTREAM = "https://github.com/lavenderdotpet/CC0-Public-Domain-Sounds"

BB_NOTE = (
    "Public-domain (CC0) sample pack by Benjamin Burnes of Abstraction "
    "(abstractionmusic.com); license stated in the pack's readme."
)

# folder -> (pack name, creator, website, description, extra options)
PACKS = {
    "100-CC0-SFX": (
        "100 CC0 SFX",
        "rubberduck",
        OGA + "100-cc0-sfx",
        "100 household and foley sound effects — bells, dishes, doors, glass, "
        "metal, springs, slams, tools and more. CC0, by rubberduck (OpenGameArt).",
        {"category": "Foley & Objects", "category_rules": [(r"shot", "Weapons & Combat"), (r"machine", "Machines & Vehicles")]},
    ),
    "100-CC0-wood-metal-SFX": (
        "100 CC0 Metal and Wood SFX",
        "rubberduck",
        OGA + "100-cc0-metal-and-wood-sfx",
        "100 metal and wood sounds: doors, hammers, keys, locks, hits, falling, "
        "breaking, cracking and squeaking. CC0, by rubberduck (OpenGameArt).",
        {"category": "Foley & Objects", "category_rules": [(r"hit|slam|fall|break", "Impacts & Hits")]},
    ),
    "100-cc0-sfx-2": (
        "100 CC0 SFX #2",
        "rubberduck",
        OGA + "100-cc0-sfx-2",
        "Second pack of 100 CC0 sound effects: air, doors, footsteps, glass, hits, "
        "items, ambient/machine/water loops, metal, stones, switches, thunder and "
        "wood. By rubberduck (OpenGameArt).",
        {"strip_prefix": "sfx100v2_", "category": "Foley & Objects", "category_rules": [(r"footstep", "Footsteps"), (r"loop_|thunder", "Ambience"), (r"hit", "Impacts & Hits"), (r"_air", "Whooshes & Transitions")]},
    ),
    "25-CC0-bang-sfx": (
        "25 CC0 Bang / Firework SFX",
        "rubberduck",
        OGA + "25-cc0-bang-firework-sfx",
        "25 bang, firework, cannon and explosion sounds recorded from real "
        "fireworks, incl. sci-fi variations. CC0, by rubberduck (OpenGameArt).",
        {"category": "Impacts & Hits"},
    ),
    "25-CC0-mud-sfx": (
        "25 CC0 Mud SFX",
        "rubberduck",
        OGA + "25-cc0-mud-sfx",
        "25 wet, squishy mud/slime sound effects recorded in real mud. CC0, by "
        "rubberduck (OpenGameArt).",
        {"category": "Foley & Objects"},
    ),
    "30-cc0-sfx-loops": (
        "30 CC0 SFX Loops",
        "rubberduck",
        OGA + "30-cc0-sfx-loops",
        "30 loopable effects: machines, alarms, ambient, noise, rain and water. "
        "CC0, by rubberduck (OpenGameArt).",
        {"category": "Ambience", "category_rules": [(r"machine|pump|saw|boil", "Machines & Vehicles"), (r"alarm", "UI")]},
    ),
    "30-cc0-weird-sfx": (
        "30 Weird CC0 SFX",
        "rubberduck",
        OGA + "30-weird-cc0-sfx",
        "30 weird sound effects — part recorded and filtered, part synthesized. "
        "CC0, by rubberduck (OpenGameArt).",
        {"category": "Foley & Objects"},
    ),
    "40-cc0-water-splash-slime-sfx": (
        "40 CC0 Water / Splash / Slime SFX",
        "rubberduck",
        OGA + "40-cc0-water-splash-slime-sfx",
        "40 water, splash and slime sounds incl. bubble and rain loops, partly "
        "recorded from real slime. CC0, by rubberduck (OpenGameArt).",
        {"category": "Foley & Objects", "category_rules": [(r"loop", "Ambience")]},
    ),
    "50-CC0-retro-synth-SFX": (
        "50 CC0 Retro / Synth SFX",
        "rubberduck",
        OGA + "50-cc0-retro-synth-sfx",
        "50 retro/synth effects made in LMMS with ZynAddSubFX: power-ups, coins, "
        "explosions, shots, beeps and lasers. CC0, by rubberduck (OpenGameArt).",
        {"category": "UI", "category_rules": [(r"laser|shoot|shot|explos", "Weapons & Combat")]},
    ),
    "50-cc0-sci-fi-sfx": (
        "50 CC0 Sci-Fi SFX",
        "rubberduck",
        OGA + "50-cc0-sci-fi-sfx",
        "50 sci-fi effects: beeps, explosions, loops, lasers, rockets, shooting, "
        "teleport and terminal sounds. CC0, by rubberduck (OpenGameArt).",
        {"category": "UI", "category_rules": [(r"laser|shoot|explos|rocket", "Weapons & Combat"), (r"loop|ambient", "Ambience"), (r"teleport", "Magic")]},
    ),
    "60-sci-fi-sfx": (
        "60 CC0 Sci-Fi SFX",
        "rubberduck",
        OGA + "60-cc0-sci-fi-sfx",
        "60 sci-fi sounds (22 effects with 2–3 variations each): lasers, phasers, "
        "beeps, terminals, ambient space and warp. CC0, by rubberduck (OpenGameArt).",
        {},
    ),
    "75-cc0-breaking-falling-hit-sfx": (
        "75 CC0 Breaking / Falling / Hit SFX",
        "rubberduck",
        OGA + "75-cc0-breaking-falling-hit-sfx",
        "75 breaking, falling and impact sounds across wood, metal, glass, rock "
        "and stone. CC0, by rubberduck (OpenGameArt).",
        {"category": "Impacts & Hits"},
    ),
    "80-CC0-RPG-SFX": (
        "80 CC0 RPG SFX",
        "rubberduck",
        OGA + "80-cc0-rpg-sfx",
        "80 fantasy/RPG effects: blades, pages, chains, creatures, coins, gems, "
        "locks, metal and spells. CC0, by rubberduck (OpenGameArt).",
        {"category": "Foley & Objects", "category_rules": [(r"blade", "Weapons & Combat"), (r"spell", "Magic"), (r"creature", "Creatures & Animals")]},
    ),
    "80-CC0-creature-SFX": (
        "80 CC0 Creature SFX",
        "rubberduck",
        OGA + "80-cc0-creature-sfx",
        "80 creature sounds — aliens, barks, breaths, bugs, grunts, roars, screams "
        "and more, mostly voice-acted and filtered. CC0, by rubberduck (OpenGameArt).",
        {"category": "Creatures & Animals"},
    ),
    "80-CC0-creature-sfx-2": (
        "80 CC0 Creature SFX #2",
        "rubberduck",
        OGA + "80-cc0-creture-sfx-2",
        "80 more creature sounds continuing the numbering of the first pack: "
        "aliens, attacks, bugs, monsters, slimes and roars. CC0, by rubberduck "
        "(OpenGameArt).",
        {"category": "Creatures & Animals"},
    ),
    "BB_2HTC Samples Vol 4": (
        "2HTC Samples Vol. 4",
        "Benjamin Burnes (Abstraction) & Mark Powers",
        ABSTRACTION,
        "Percussion sample pack — drums, loops, pads, solos and weird hits — "
        "recorded with percussionist Mark Powers. " + BB_NOTE,
        # mp3 duplicate of the same wav recording
        {"skip_names": {"2021-12-30 Moist Alleyway - Dampstep.mp3"}, "category": "Music"},
    ),
    "BB_2HTC Samples Vol 4 Addendum": (
        "2HTC Samples Vol. 4 Addendum",
        "Benjamin Burnes (Abstraction) & Mark Powers",
        ABSTRACTION,
        "Addendum to 2HTC Samples Vol. 4 with additional drums, loops, pads and "
        "solos. " + BB_NOTE,
        {"category": "Music"},
    ),
    "BB_Retail Therapy Sample Pack": (
        "Retail Therapy Sample Pack",
        "Benjamin Burnes (Abstraction)",
        ABSTRACTION,
        "Large foley sample pack recorded in retail environments — carts, "
        "registers, packaging and shop ambience. " + BB_NOTE,
        {"category": "Foley & Objects", "category_rules": [(r"chittering", "Creatures & Animals"), (r"laughter", "Voice")]},
    ),
    # "LQ_interface" intentionally omitted: likely LibreQuake material, and
    # LibreQuake assets are BSD — provenance too murky for a CC0 store.
    "MMRetroArcadeSoundsPack1_0_5": (
        "Free Retro Arcade Sounds Pack",
        "The Motion Monkey",
        "http://www.themotionmonkey.co.uk/free-resources/retro-arcade-sounds/",
        "Original retro arcade sounds — explosions, guns, impacts, vehicles, "
        "speech and vocal effects (v1.0.5, WAV). CC0 as stated in the pack readme.",
        # ogg/wav/m4a triplicate trees: keep lossless wav only.
        {
            "only_dirs_containing": "/wav/",
            "category_rules": [
                (r"/explosions/|/guns/", "Weapons & Combat"),
                (r"/impact/", "Impacts & Hits"),
                (r"/speech/|/vocal/", "Voice"),
                (r"/vehicles/", "Machines & Vehicles"),
                (r"/misc/", "UI"),
            ],
        },
    ),
    "Maximiliano-Stradex-Ambient": (
        "H.A.S.T.E. Ambient Tracks",
        "Maximiliano Ruben Viamonte (Stradex)",
        "https://stradex.itch.io/haste-cc0-asets",
        "Two ambient tracks and a theme from the discontinued game H.A.S.T.E., "
        "released CC0 by its author.",
        {"category": "Music"},
    ),
    "MissLavs Sounds": (
        "MissLav's Sounds",
        "MissLav (lavender.pet)",
        UPSTREAM,
        "Household recordings (angry dog, chair wheel, pots and pans) by the "
        "curator of the upstream CC0-Public-Domain-Sounds collection, CC0.",
        {"category": "Foley & Objects", "category_rules": [(r"angerdog", "Creatures & Animals")]},
    ),
    "beast_or_animal": (
        "Animal or Beast Sounds",
        "pauliuw",
        OGA + "animal-or-beast-sounds",
        "7 strange animal/beast growls and voices for RPG and fantasy games. "
        "CC0, by pauliuw (OpenGameArt).",
        {"category": "Creatures & Animals"},
    ),
    "kenney_casinoaudio": (
        "Casino Audio",
        "Kenney",
        KENNEY,
        "Casino sounds by Kenney (kenney.nl): cards, chips and dice. CC0 per the "
        "included license.",
        {"skip_names": {"Preview.ogg"}, "category": "Foley & Objects"},
    ),
    "kenney_digitalaudio": (
        "Digital Audio",
        "Kenney",
        KENNEY,
        "Digital/chiptune-style effects by Kenney (kenney.nl): beeps, zaps, "
        "power-ups and glitches. CC0 per the included license.",
        {"skip_names": {"Preview.ogg"}, "category": "UI"},
    ),
    "kenney_impactsounds": (
        "Impact Sounds",
        "Kenney",
        KENNEY,
        "Impact sounds by Kenney (kenney.nl): bells, punches, mining and "
        "footsteps on various materials. CC0 per the included license.",
        {"skip_names": {"Preview.ogg"}, "category": "Impacts & Hits", "category_rules": [(r"footstep", "Footsteps")]},
    ),
    "kenney_interfacesounds": (
        "Interface Sounds",
        "Kenney",
        KENNEY,
        "UI interface sounds by Kenney (kenney.nl): clicks, confirmations, "
        "drops, glass and pluck tones. CC0 per the included license.",
        {"skip_names": {"Preview.ogg"}, "category": "UI"},
    ),
    "kenney_musicjingles": (
        "Music Jingles",
        "Kenney",
        KENNEY,
        "Short musical jingles by Kenney (kenney.nl) for wins, losses and "
        "level-ups. CC0 per the included license.",
        {"skip_names": {"Preview.ogg"}, "category": "Music"},
    ),
    "kenney_rpgaudio": (
        "RPG Audio",
        "Kenney",
        KENNEY,
        "RPG interface and foley sounds by Kenney (kenney.nl): doors, footsteps, "
        "handles, cloth and metal. CC0 per the included license.",
        {"skip_names": {"Preview.ogg"}, "category": "Foley & Objects", "category_rules": [(r"footstep", "Footsteps")]},
    ),
    "kenney_uiaudio": (
        "UI Audio",
        "Kenney",
        KENNEY,
        "Classic UI sound set by Kenney (kenney.nl): clicks, rollovers and "
        "switches. CC0 per the included license.",
        {"skip_names": {"Preview.ogg"}, "category": "UI"},
    ),
    "kenney_voiceoverfighter": (
        "Voiceover Pack: Fighter",
        "Kenney",
        KENNEY,
        "Fighting-game announcer voice lines by Kenney (kenney.nl) — 'Fight', "
        "'K.O.', countdowns and more. CC0 per the included license.",
        {"skip_names": {"Preview.ogg"}, "category": "Voice"},
    ),
    "kenney_voiceoverpack": (
        "Voiceover Pack",
        "Kenney",
        KENNEY,
        "Male and female voice lines by Kenney (kenney.nl) — menu words, "
        "numbers, letters and phrases. CC0 per the included license.",
        {"skip_names": {"Preview.ogg"}, "category": "Voice"},
    ),
    "metal_interactions": (
        "Metal Interactions",
        "qubodup",
        OGA + "metal-interactions",
        "Heavy metal interaction sounds — swings, button presses and clanks. "
        "CC0, by qubodup (OpenGameArt).",
        {"category": "Impacts & Hits"},
    ),
    "sci-fi-sounds": (
        "Sci-Fi Sounds",
        "Kenney",
        KENNEY,
        "Sci-fi sounds by Kenney (kenney.nl): engines, lasers, doors and "
        "computer ambience. CC0 per the included license.",
        {"skip_names": {"Preview.ogg"}, "category": "Foley & Objects", "category_rules": [(r"engine|thruster", "Machines & Vehicles"), (r"laser|explosion", "Weapons & Combat"), (r"computer", "UI"), (r"forcefield", "Magic"), (r"impact", "Impacts & Hits")]},
    ),
    "warfork-cc0": (
        "Warfork CC0 Sounds & Music",
        "Team Forbidden LLC",
        "https://www.warfork.com",
        "The CC0-dedicated sound and music set from the arena FPS Warfork: "
        "announcer lines, weapons, items, movement, menu sounds and music "
        "tracks. CC0 per the included dedication by Team Forbidden.",
        # sounds/music/ is a byte-identical duplicate of music/;
        # trailer cc0-source.mp3 duplicates cc0-source.wav.
        {
            "exclude_prefixes": ("warfork-cc0/sounds/music/",),
            "skip_names": {"cc0-source.mp3"},
            "category": "Foley & Objects",
            "category_rules": [
                (r"footstep", "Footsteps"),
                (r"/music/|/trailer/", "Music"),
                (r"/announcer/|/ctftactics/|/vsay/|/players/", "Voice"),
                (r"/weapons/|/bomb/", "Weapons & Combat"),
                (r"/items/|/menu/", "UI"),
                (r"/movers/", "Machines & Vehicles"),
                (r"/ambient/|/world/", "Ambience"),
            ],
        },
    ),
    # "angerdog" intentionally omitted: exact duplicate subset of "MissLavs Sounds".
}

# bb monthly packs + micro packs share boilerplate; generate their entries.
BB_MONTHLY = {
    "bb - Books, Paper, Writing (Jan 2021)": "Books, paper and writing foley",
    "bb - Bottle Plops (Apr 2021)": "Bottle plop and cork pop foley",
    "bb - Fans and Drones (Jul 2021)": "Fan hum and drone ambience",
    "bb - Japanese Pull Saw (Oct 2021)": "Japanese pull-saw cutting foley",
    "bb - Keyboard Sounds (Mar 2021)": "Keyboard typing and key-press foley",
    "bb - Novice Cello (Nov 2021)": "Novice cello notes, bows and scrapes",
    "bb - Pill Bottles (Jun 2021)": "Pill-bottle rattle and cap foley",
    "bb - Rubik's Cube (Feb 2021)": "Rubik's Cube turning and clacking foley",
    "bb - Slide Whistle (Aug 2021)": "Slide whistle rises, falls and warbles",
    "bb - Smol Mechanisms (May 2021)": "Small mechanism clicks, winds and gears",
    "bb - Toolbox Rummaging (Sept 2021)": "Toolbox rummaging and tool clatter",
}
BB_MONTHLY_CATS = {
    "bb - Fans and Drones (Jul 2021)": "Ambience",
    "bb - Novice Cello (Nov 2021)": "Music",
    "bb - Slide Whistle (Aug 2021)": "Music",
}
for folder, desc in BB_MONTHLY.items():
    title = re.sub(r"^bb - ", "", folder)
    PACKS[folder] = (
        title,
        "Benjamin Burnes (Abstraction)",
        ABSTRACTION,
        desc + ", from Abstraction's monthly sample-pack series. " + BB_NOTE,
        {"category": BB_MONTHLY_CATS.get(folder, "Foley & Objects")},
    )

MICRO = {
    "Micro Pack - CaptSubtle - Melon": "Melon knocks, cuts and squishes",
    "Micro Pack - Cat Meows": "Cat meow recordings",
    "Micro Pack - Chairmat": "Chair-mat crunches and flexes",
    "Micro Pack - Kitchen Knives": "Kitchen knife shings, chops and sharpening",
    "Micro Pack - MadameBerry - Stream Noises": "Stream and flowing-water ambience",
    "Micro Pack - NazdyNate - Electromagnetic Sounds": "Electromagnetic hums and buzzes",
    "Micro Pack - Organic Wooshes": "Organic whoosh and swipe sounds",
    "Micro Pack - Paper Cutter": "Paper-cutter slices and chops",
    "Micro Pack - Record Fuzzies": "Vinyl record fuzz, crackle and noise",
    "Micro Pack - Small Can": "Small tin-can hits, rolls and rattles",
}
MICRO_CATS = {
    "Micro Pack - Cat Meows": "Creatures & Animals",
    "Micro Pack - MadameBerry - Stream Noises": "Ambience",
    "Micro Pack - NazdyNate - Electromagnetic Sounds": "Ambience",
    "Micro Pack - Organic Wooshes": "Whooshes & Transitions",
}
for folder, desc in MICRO.items():
    title = re.sub(r"^Micro Pack - ", "", folder)
    PACKS[folder] = (
        "Micro Pack: " + title,
        "Benjamin Burnes (Abstraction)",
        ABSTRACTION,
        desc + ", from Abstraction's Micro Pack series. " + BB_NOTE,
        {"category": MICRO_CATS.get(folder, "Foley & Objects")},
    )


def humanize(stem: str) -> str:
    s = re.sub(r"[_\-]+", " ", stem).strip()
    s = re.sub(r"\s+", " ", s)
    return " ".join(w if w.isupper() else w.capitalize() for w in s.split(" "))


def main() -> None:
    commit = subprocess.check_output(
        ["git", "-C", REPO, "rev-parse", "HEAD"], text=True
    ).strip()

    # The manifest pins every URL to this commit and states each file's SHA-256.
    # Generating from a dirty tree describes bytes that were never committed,
    # and generating from an unpushed commit produces URLs the store cannot
    # fetch — both surface as a mass validation failure minutes into a
    # submission, long after the store has started downloading.
    dirty = subprocess.check_output(
        ["git", "-C", REPO, "status", "--porcelain"], text=True
    ).strip()
    if dirty and not os.environ.get("ALLOW_DIRTY"):
        sys.exit(
            "Working tree has uncommitted changes — commit and push them first, "
            "or set ALLOW_DIRTY=1 to generate a preview."
        )

    on_remote = subprocess.check_output(
        ["git", "-C", REPO, "branch", "-r", "--contains", commit], text=True
    ).strip()
    if not on_remote and not os.environ.get("ALLOW_UNPUSHED"):
        sys.exit(
            f"Commit {commit} is not on any remote branch — push it before "
            "generating, or set ALLOW_UNPUSHED=1 for a preview."
        )

    packs_out = []
    total_files = 0
    total_bytes = 0

    for folder in sorted(PACKS, key=str.lower):
        name, creator, website, description, opts = PACKS[folder]
        root = os.path.join(REPO, folder)
        if not os.path.isdir(root):
            sys.exit(f"missing folder: {folder}")

        files_out = []
        items_out = []
        previews_out = []
        seen_names: dict[str, int] = {}

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d != "__MACOSX")
            for fn in sorted(filenames):
                ext = os.path.splitext(fn)[1].lower()
                if ext not in AUDIO_EXTS:
                    continue
                if fn.startswith("._") or fn in opts.get("skip_names", set()):
                    continue
                abspath = os.path.join(dirpath, fn)
                relpath = os.path.relpath(abspath, REPO)
                if any(
                    relpath.replace(os.sep, "/").startswith(pfx)
                    for pfx in opts.get("exclude_prefixes", ())
                ):
                    continue
                if "only_dirs_containing" in opts and opts[
                    "only_dirs_containing"
                ] not in relpath.replace(os.sep, "/"):
                    continue

                with open(abspath, "rb") as fh:
                    data = fh.read()
                sha = hashlib.sha256(data).hexdigest()
                size = len(data)

                stem = os.path.splitext(fn)[0]
                if prefix := opts.get("strip_prefix"):
                    stem = stem.removeprefix(prefix)
                item_name = humanize(stem)
                # Disambiguate name collisions (same stem in sibling dirs)
                # with the parent directory, then a counter.
                if item_name in seen_names:
                    parent = os.path.basename(dirpath)
                    candidate = (
                        f"{item_name} ({humanize(parent)})"
                        if parent != folder
                        else item_name
                    )
                    if candidate in seen_names:
                        seen_names[item_name] += 1
                        candidate = f"{item_name} ({seen_names[item_name]})"
                    item_name = candidate
                seen_names.setdefault(item_name, 1)

                files_out.append(
                    {
                        "fileName": fn,
                        "path": relpath.replace(os.sep, "/"),
                        "externalUrl": f"{RAW_BASE}/{commit}/"
                        + "/".join(quote(p) for p in relpath.split(os.sep)),
                        "sha256": sha,
                        "size": size,
                        "role": "Audio",
                    }
                )
                category = categorize(relpath.replace(os.sep, "/"), opts)
                if category is not None and category not in SOUND_CATEGORIES:
                    sys.exit(f"unknown category {category!r} for {relpath}")
                item = {
                    "name": item_name,
                    "itemType": "Sound",
                    "isPreviewable": True,
                    "files": [
                        {"path": relpath.replace(os.sep, "/"), "role": "Audio"}
                    ],
                }
                if category is not None:
                    item["metadataJson"] = json.dumps({"category": category})
                items_out.append(item)

                wf_rel = "waveforms/" + os.path.splitext(
                    relpath.replace(os.sep, "/")
                )[0] + ".png"
                wf_abs = os.path.join(REPO, wf_rel)
                if os.path.isfile(wf_abs):
                    with open(wf_abs, "rb") as fh:
                        wf_data = fh.read()
                    previews_out.append(
                        {
                            "fileName": os.path.basename(wf_rel),
                            "path": wf_rel,
                            "externalUrl": f"{RAW_BASE}/{commit}/"
                            + "/".join(quote(p) for p in wf_rel.split("/")),
                            "sha256": hashlib.sha256(wf_data).hexdigest(),
                            "size": len(wf_data),
                            "contentType": "image/png",
                            "type": "Thumbnail",
                            "itemName": item_name,
                        }
                    )

        # Pack main cover thumbnail preview (inserted first so it wins primary thumbnail selection)
        cover_rel = f"covers/{folder}.png"
        cover_abs = os.path.join(REPO, cover_rel)
        if os.path.isfile(cover_abs):
            with open(cover_abs, "rb") as fh:
                cover_data = fh.read()
            previews_out.insert(
                0,
                {
                    "fileName": os.path.basename(cover_rel),
                    "path": cover_rel,
                    "externalUrl": f"{RAW_BASE}/{commit}/"
                    + "/".join(quote(p) for p in cover_rel.split("/")),
                    "sha256": hashlib.sha256(cover_data).hexdigest(),
                    "size": len(cover_data),
                    "contentType": "image/png",
                    "type": "Thumbnail",
                },
            )

        if not files_out:
            sys.exit(f"pack produced no files: {folder}")
        total_files += len(files_out)
        total_bytes += sum(f["size"] for f in files_out)

        packs_out.append(
            {
                "name": name,
                "creator": creator,
                "website": website,
                "description": description,
                "license": "CC0",
                "folder": folder,
                "itemCount": len(items_out),
                "items": items_out,
                "files": files_out,
                "previews": previews_out,
            }
        )

    manifest = {
        "source": {
            "repository": "https://github.com/Papyszoo/CC0-Public-Domain-Sounds",
            "commit": commit,
        },
        "license": "CC0-1.0",
        "packs": packs_out,
    }

    out_path = os.path.join(REPO, "store-manifest.json")
    with open(out_path, "w") as fh:
        json.dump(manifest, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    print(f"packs: {len(packs_out)}")
    print(f"files: {total_files}  ({total_bytes / 1e6:.1f} MB)")
    for p in packs_out:
        print(f"  {p['itemCount']:4d}  {p['name']}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
