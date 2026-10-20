"""
Join the geotagged Flickr photos (MediaEval 2016 placing set, part of YFCC100M)
with Open Images, which hosts copies of the same Flickr photos plus labels.

Output: data/interim/matched.csv with one row per photo we can actually
download and place in a country.
"""
import csv
import gzip
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLACES = ROOT / "data/raw/placemeta.sqlite"
OUT = ROOT / "data/interim/matched.csv"

OI_IDS = "https://storage.googleapis.com/openimages/2018_04/image_ids_and_rotation.csv"

# The UK shows up twice (UK + England etc). Keep the country, drop the nation.
UK_NATIONS = {"England", "Scotland", "Wales", "Northern Ireland"}

PHOTO_ID = re.compile(r"/(\d+)_[0-9a-f]+(?:_o)?\.jpg")


def load_countries():
    print("reading places...", file=sys.stderr)
    db = sqlite3.connect(PLACES)
    rows = db.execute("select photoid, placename from place_hierarchy where type = 'Country'")
    country = {}
    for pid, name in rows:
        name = urllib.parse.unquote_plus(name)
        if name in UK_NATIONS:
            country.setdefault(pid, "United Kingdom")
        else:
            country[pid] = name
    print(f"{len(country):,} placed photos", file=sys.stderr)
    return country


def main():
    country = load_countries()
    OUT.parent.mkdir(parents=True, exist_ok=True)

    hits = 0
    with urllib.request.urlopen(OI_IDS) as resp, open(OUT, "w", newline="") as f:
        lines = (line.decode("utf-8", "replace") for line in resp)
        reader = csv.DictReader(lines)
        out = csv.writer(f)
        out.writerow(["image_id", "subset", "photo_id", "country", "author", "title", "thumb"])
        for i, row in enumerate(reader):
            m = PHOTO_ID.search(row["OriginalURL"])
            if not m:
                continue
            pid = int(m.group(1))
            if pid in country:
                hits += 1
                out.writerow([
                    row["ImageID"], row["Subset"], pid, country[pid],
                    row["AuthorProfileURL"].rstrip("/").rsplit("/", 1)[-1],
                    row["Title"], row["Thumbnail300KURL"],
                ])
            if i % 500_000 == 0:
                print(f"{i:,} scanned, {hits:,} matched", file=sys.stderr)

    print(f"done: {hits:,} matched", file=sys.stderr)


if __name__ == "__main__":
    main()
