"""
Pull the Open Images labels for our sample.

Open Images ships two kinds of image-level labels:
- machine: a Google classifier's guesses with a confidence score
- human: people confirmed (1) or rejected (0) some of those guesses

The files are big (gigabytes), so we stream them and keep only our rows.
"""
import csv
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://storage.googleapis.com/openimages/"

FILES = {
    "machine": [
        "v5/train-annotations-machine-imagelabels.csv",
        "v5/validation-annotations-machine-imagelabels.csv",
        "v5/test-annotations-machine-imagelabels.csv",
    ],
    "human": [
        "v6/oidv6-train-annotations-human-imagelabels.csv",
        "v5/validation-annotations-human-imagelabels.csv",
        "v5/test-annotations-human-imagelabels.csv",
    ],
}


def main(kind):
    with open(ROOT / "data/interim/sample.csv") as f:
        wanted = {row["image_id"] for row in csv.DictReader(f)}

    out_path = ROOT / f"data/interim/labels_{kind}.csv"
    kept = 0
    with open(out_path, "w", newline="") as out:
        w = csv.writer(out)
        w.writerow(["image_id", "label", "confidence"])
        for name in FILES[kind]:
            with urllib.request.urlopen(BASE + name) as resp:
                lines = (line.decode() for line in resp)
                for row in csv.DictReader(lines):
                    if row["ImageID"] in wanted:
                        w.writerow([row["ImageID"], row["LabelName"], row["Confidence"]])
                        kept += 1
            print(f"{name}: {kept:,} rows so far", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
