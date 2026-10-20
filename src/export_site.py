"""
Write docs/data.json and copy the thumbnails the site needs.
"""
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pycountry

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed"
SITE = ROOT / "docs"
THUMBS_PER_COUNTRY = 24
SEED = 7

FIELDS = [
    "photos", "users", "happiness", "predicted", "gdp", "beyond_wealth", "smile_given_face", "smile", "face",
    "people", "together", "fun", "nature", "sunset", "city", "indoors", "pets", "food",
    "night", "joy_title", "brightness", "saturation", "warmth", "colourfulness",
]


def iso_num(iso3):
    if iso3 == "OWID_KOS":
        return None
    c = pycountry.countries.get(alpha_3=iso3)
    return c.numeric if c else None


def main():
    countries = pd.read_csv(DATA / "countries.csv", index_col="country")
    preds = pd.read_csv(DATA / "predictions.csv", index_col="country")
    countries["predicted"] = preds.predicted
    countries["gdp"] = np.exp(preds.log_gdp)

    # how much happier (or less happy) a country is than its GDP alone predicts
    ok = preds.log_gdp.notna()
    fit = np.polyfit(preds.log_gdp[ok], preds.happiness[ok], 1)
    countries["beyond_wealth"] = preds.happiness - np.polyval(fit, preds.log_gdp)
    photos = pd.read_csv(DATA / "photos.csv")
    sample = pd.read_csv(ROOT / "data/interim/sample.csv", usecols=["image_id", "photo_id"])
    photos = photos.merge(sample, on="image_id")

    have_thumb = {p.stem for p in (ROOT / "data/thumbs").glob("*.jpg")}
    photos = photos[photos.image_id.isin(have_thumb)]

    out_thumbs = SITE / "thumbs"
    shutil.rmtree(out_thumbs, ignore_errors=True)
    out_thumbs.mkdir()

    rows = []
    for name, c in countries.iterrows():
        picks = photos[photos.country == name]
        picks = picks.sample(min(THUMBS_PER_COUNTRY, len(picks)), random_state=SEED)
        thumbs = []
        for p in picks.itertuples():
            shutil.copy(ROOT / f"data/thumbs/{p.image_id}.jpg", out_thumbs)
            thumbs.append({
                "id": p.image_id,
                "author": p.author,
                "title": p.title if isinstance(p.title, str) else "",
                "page": f"https://www.flickr.com/photos/{p.author}/{p.photo_id}",
            })
        row = {"name": name, "iso3": c.iso3, "iso_num": iso_num(c.iso3)}
        for f in FIELDS:
            v = c.get(f)
            row[f] = None if pd.isna(v) else round(float(v), 4)
        row["thumbs"] = thumbs
        rows.append(row)

    summary = json.loads((DATA / "summary.json").read_text())
    signals = pd.read_csv(DATA / "signals.csv")
    wealth = pd.read_csv(DATA / "wealth_check.csv").query("countries == 'all'")
    signals = signals.merge(wealth[["signal", "partial_rho", "p"]].rename(columns={"p": "partial_p"}), on="signal")
    signals = signals.sort_values("partial_rho", ascending=False).round(3).to_dict(orient="records")
    data = {"summary": summary, "signals": signals, "countries": rows}
    (SITE / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    print(f"{len(rows)} countries, {sum(len(r['thumbs']) for r in rows)} thumbnails")


if __name__ == "__main__":
    main()
