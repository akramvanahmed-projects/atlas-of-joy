"""
Pick the photos we'll actually analyse.

Rules:
- locals only: a user's home country is where at least 60% of their placed
  photos were taken (and they need 5+ placed photos for that to mean anything)
- at most 30 photos per user per country, so one keen photographer
  can't define a whole country
- at most 300 photos per country
- keep a country only if it has 50+ photos from 5+ different locals
- when there's a choice, prefer photos we can actually download, since
  only part of Open Images is mirrored as image files
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEED = 7

PER_USER = 30
PER_COUNTRY = 300
MIN_PHOTOS = 50
MIN_USERS = 5

# Flickr place names that differ from the happiness data
RENAME = {
    "Czech Republic": "Czechia",
    "Macedonia": "North Macedonia",
}


def downloadable(df):
    # validation and test images are all mirrored, train only the "boxable" part
    boxable = set((ROOT / "data/raw/boxable_train_ids.txt").read_text().split())
    return (df.subset != "train") | df.image_id.isin(boxable)


def home_countries(df):
    counts = df.groupby(["author", "country"]).size().rename("n").reset_index()
    counts["total"] = counts.groupby("author").n.transform("sum")
    counts["share"] = counts.n / counts.total
    top = counts.sort_values("n").groupby("author").tail(1)
    top = top[(top.share >= 0.6) & (top.total >= 5)]
    return top.set_index("author").country.rename("home")


def main():
    df = pd.read_csv(ROOT / "data/interim/matched.csv")
    df["country"] = df.country.replace(RENAME)

    df = df.join(home_countries(df), on="author")
    locals_ = df[df.country == df.home].drop(columns="home")

    locals_ = locals_.assign(downloadable=downloadable(locals_))
    locals_ = (
        locals_.sample(frac=1, random_state=SEED)
        .sort_values("downloadable", ascending=False, kind="stable")
        .groupby(["country", "author"]).head(PER_USER)
        .groupby("country").head(PER_COUNTRY)
    )

    stats = locals_.groupby("country").agg(photos=("image_id", "size"), users=("author", "nunique"))
    keep = stats[(stats.photos >= MIN_PHOTOS) & (stats.users >= MIN_USERS)].index
    sample = locals_[locals_.country.isin(keep)].sort_values(["country", "image_id"])

    sample.to_csv(ROOT / "data/interim/sample.csv", index=False)
    stats.loc[keep].sort_values("photos", ascending=False).to_csv(ROOT / "data/interim/sample_stats.csv")
    print(f"{len(sample):,} photos, {len(keep)} countries, {sample.author.nunique():,} users")


if __name__ == "__main__":
    main()
