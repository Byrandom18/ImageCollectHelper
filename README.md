# Image Collect Helper

Desktop tools for collecting open-licensed photos, converting them to numbered WebP files, and closing gaps in filenames. Built for a Unity jigsaw game that loads images from `StreamingAssets`.

## What it does

**Collector** (`run.bat`)

- Downloads photos from Wikimedia Commons and Openverse (no API key)
- Optional Pexels / Unsplash / Pixabay with your own keys
- Categories: landscapes, cities, animals, food, sea, flowers, sunsets, winter, space, plus a custom query
- Saves as `01.webp`, `02.webp`, … with a configurable start number
- Crops to 16:9, compresses WebP to a size budget (default 220 KB)
- Optional local HTTP/SOCKS proxy (env, Windows system proxy, or a listening port such as `127.0.0.1:10809`)

**Renamer** (`run_rename.bat`)

- Turns `01.webp`, `02.webp`, `04.webp` into `01.webp`, `02.webp`, `03.webp`
- Leaves non-numeric names (and `credits.txt`) alone
- Renames matching Unity `*.meta` files together with the image

## Requirements

- Windows
- Python 3.10+ (`python` or `py -3` on PATH)

## Run

```text
run.bat          → collector
run_rename.bat   → filename renumbering
```

The first launch creates `.venv` and installs dependencies from `requirements.txt`.

CLI example:

```text
python -m collector --cli --count 10 --start 1 --categories landscapes,animals --out path\to\folder
```

## Unity layout

Default destinations:

| Preset | Path |
| --- | --- |
| Campaign | `C:\Unity\JigsawPuzzles\Assets\StreamingAssets\campaign` |
| Dailies | `...\StreamingAssets\dailies` |
| Tab mosaics | `...\StreamingAssets\campaign\tabs` |

Attribution is written to `credits.txt` in the output folder, or to `Assets/Content/image_credits.txt` when saving into `StreamingAssets`.

## API keys

Wikimedia and Openverse work without keys.

For Pexels, Unsplash, or Pixabay, copy `secrets.example.json` to **`secrets.json`** (this file is gitignored) and fill in the keys — or paste them in the collector UI. The app stores tokens only in `secrets.json`, never in git.

| Source | Where to get a key |
| --- | --- |
| Pexels | https://www.pexels.com/api/ |
| Unsplash | https://unsplash.com/developers |
| Pixabay | https://pixabay.com/api/docs/ |

## License of collected images

Files come from third-party catalogs. Keep `credits.txt` and follow each photo’s license (often CC BY / CC BY-SA, Pexels, Unsplash, or Pixabay).
