# CC0 Public Domain Sounds

CC0 sound packs prepared for [ModelibrStore](https://store.modelibr.com). Each
pack keeps its audio, waveform thumbnails, Store metadata, original licensing
notes, and any verified author cover together.

## Layout

```text
packs/
  <stable-pack-name>/
    pack.json        Store metadata, taxonomy rules, and cover provenance
    cover.png        optional verified original-author artwork
    sounds/          audio plus original license/readme/credit files
    thumbnails/      generated waveform PNGs mirroring sounds/ paths
scripts/
store-manifest.json  generated Store import manifest; do not hand-edit
LICENSE              repository-wide CC0 dedication
```

The folder and published pack name are stable identifiers. Do not rename them
after publication. Non-audio source documents are retained when they establish
licensing or provenance; archives, duplicate encodings, operating-system files,
and files excluded from Store publication are not retained.

## Adding or updating a pack

1. Verify an explicit CC0/public-domain statement from the authoritative source.
2. Add `packs/<name>/pack.json` and put distributable audio under `sounds/`.
   Preserve the source's license, readme, and credit files with the sounds.
3. Commit and push content changes. Manifest URLs are pinned to the latest
   commit affecting `packs/`, so unpublished content cannot be imported.
4. Run `python3 scripts/gen_store_manifest.py` and inspect the manifest diff.
5. Optionally run `python3 scripts/render_waveforms.py` to create missing
   waveform thumbnails. Refresh verified author artwork only with
   `python3 scripts/fetch_official_covers.py`.

For a local structural check before committing, write a disposable preview:

```sh
ALLOW_DIRTY=1 ALLOW_UNPUSHED=1 MANIFEST_OUTPUT=/tmp/sounds-manifest.json \
  python3 scripts/gen_store_manifest.py
```

Never publish a preview manifest: its pinned URLs may not exist on GitHub yet.
