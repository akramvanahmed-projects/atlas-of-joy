"""
Colour signals for every photo in the sample.

We download each image from the public Open Images bucket, shrink it,
measure a few things and keep a 64px thumbnail for the map. The full
image is never written to disk.

Measures (all 0..1 unless noted):
- brightness     mean HSV value
- saturation     mean HSV saturation
- warmth         mean (R - B), from -1 (blue) to 1 (orange)
- colourfulness  Hasler & Suesstrunk (2003), scaled down by 100
"""
import csv
import io
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BUCKET = "https://open-images-dataset.s3.amazonaws.com"
THUMBS = ROOT / "data/thumbs"


def measure(img):
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32) / 255
    hsv = np.asarray(img.convert("HSV"), dtype=np.float32) / 255
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]

    rg = r - g
    yb = 0.5 * (r + g) - b
    colourfulness = np.hypot(rg.std(), yb.std()) + 0.3 * np.hypot(rg.mean(), yb.mean())

    return {
        "brightness": hsv[..., 2].mean(),
        "saturation": hsv[..., 1].mean(),
        "warmth": (r - b).mean(),
        "colourfulness": colourfulness,
    }


def process(row):
    url = f"{BUCKET}/{row['subset']}/{row['image_id']}.jpg"
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            img = Image.open(io.BytesIO(resp.read()))
            img.draft("RGB", (512, 512))  # let the jpeg decoder do the downscaling
            img = img.convert("RGB")
    except Exception as e:  # dead link, truncated file, whatever. skip it.
        print(f"skip {row['image_id']}: {e}", file=sys.stderr)
        return None

    img.thumbnail((256, 256))
    out = {"image_id": row["image_id"], **{k: round(float(v), 4) for k, v in measure(img).items()}}

    thumb = img.copy()
    thumb.thumbnail((64, 64))
    thumb.save(THUMBS / f"{row['image_id']}.jpg", quality=80)
    return out


def main():
    THUMBS.mkdir(parents=True, exist_ok=True)
    with open(ROOT / "data/interim/sample.csv") as f:
        rows = [r for r in csv.DictReader(f) if r["downloadable"] == "True"]

    out_path = ROOT / "data/interim/colour.csv"
    fields = ["image_id", "brightness", "saturation", "warmth", "colourfulness"]
    with open(out_path, "w", newline="") as f, ThreadPoolExecutor(32) as pool:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        for i, res in enumerate(pool.map(process, rows), 1):
            if res:
                w.writerow(res)
            if i % 1000 == 0:
                print(f"{i:,}/{len(rows):,}", file=sys.stderr)


if __name__ == "__main__":
    main()
