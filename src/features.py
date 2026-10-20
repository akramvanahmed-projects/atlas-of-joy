"""
Turn photos into country-level signals.

Per photo we know (where available):
- Open Images labels: machine guesses, corrected by human checks
- colour measures from the pixels
- the title the photographer wrote

Per country we report shares and averages. Output:
data/processed/photos.csv     one row per photo
data/processed/countries.csv  one row per country, plus the happiness score
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data/interim"
OUT = ROOT / "data/processed"

MACHINE_MIN = 0.5  # a machine label counts if the classifier is at least this sure

# Open Images class ids, grouped into the signals we care about
GROUPS = {
    "smile": ["/m/019nj4", "/m/01j3sz", "/m/016pp7"],  # smile, laugh, happy
    "face": ["/m/0dzct", "/m/01k74n"],  # human face, facial expression
    "people": ["/m/01g317", "/m/03bt1vf", "/m/04yx4", "/m/05r655", "/m/01bl7v", "/m/0ytgt", "/m/0jnvp", "/m/01bgsw"],
    "together": ["/m/019_nn", "/m/09dhj", "/m/03qtwd", "/m/011l78", "/m/05_4_", "/m/081hv", "/m/0hr5k", "/m/081pkj"],
    "fun": ["/m/0ds99lh", "/m/04g3r", "/m/06bm2", "/m/02jwqh"],  # fun, leisure, recreation, vacation
    "nature": ["/m/05h0n", "/m/07j7r", "/m/09d_r", "/m/0838f", "/m/06npx", "/m/0b3yr", "/m/08t9c_", "/m/0c9ph5", "/m/05s2s"],
    "sunset": ["/m/01b2w5"],
    "city": ["/m/0cgh4", "/m/01n32", "/m/01c8br", "/m/06gfj", "/m/0k4j"],
    "indoors": ["/m/06ht1", "/m/02rfdq"],
    "pets": ["/m/0bt9lr", "/m/01yrx"],
    "food": ["/m/02wbm"],
    "night": ["/m/01d74z"],
}

# Words in titles that point at a good time. A few languages, not exhaustive.
JOY_WORDS = {
    "party", "wedding", "birthday", "holiday", "holidays", "vacation", "beach", "friends",
    "fun", "smile", "smiles", "happy", "love", "festival", "celebration", "christmas",
    "picnic", "summer", "family", "kids", "baby", "dance", "dancing", "concert",
    "fiesta", "boda", "cumpleaños", "vacaciones", "playa", "amigos", "familia",
    "fête", "mariage", "anniversaire", "vacances", "plage", "amis",
    "hochzeit", "geburtstag", "urlaub", "strand", "freunde", "familie", "feier",
    "festa", "matrimonio", "compleanno", "vacanze", "spiaggia", "amici",
    "casamento", "aniversário", "férias", "praia",
}
WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def label_table(photo_ids):
    machine = pd.read_csv(INTERIM / "labels_machine.csv")
    human = pd.read_csv(INTERIM / "labels_human.csv")

    present = machine[machine.confidence >= MACHINE_MIN][["image_id", "label"]].assign(on=1)
    checked = human[["image_id", "label", "confidence"]].rename(columns={"confidence": "on"})

    # a human yes or no beats the machine
    both = pd.concat([present, checked]).drop_duplicates(["image_id", "label"], keep="last")
    both = both[both.on == 1]

    table = pd.DataFrame(index=pd.Index(photo_ids, name="image_id"))
    for name, ids in GROUPS.items():
        hit = both[both.label.isin(ids)].image_id.unique()
        table[name] = table.index.isin(hit).astype(int)
    return table


def joy_in_title(title):
    if not isinstance(title, str):
        return 0
    return int(any(w in JOY_WORDS for w in WORD.findall(title.lower())))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sample = pd.read_csv(INTERIM / "sample.csv")
    colour = pd.read_csv(INTERIM / "colour.csv")

    photos = sample[["image_id", "country", "author", "title"]].set_index("image_id")
    photos = photos.join(label_table(photos.index))
    photos["joy_title"] = photos.title.map(joy_in_title)
    photos = photos.join(colour.set_index("image_id"))
    photos.to_csv(OUT / "photos.csv")

    g = photos.groupby("country")
    countries = pd.DataFrame({
        "photos": g.size(),
        "users": g.author.nunique(),
        "with_pixels": g.brightness.count(),
    })
    for name in list(GROUPS) + ["joy_title"]:
        countries[name] = g[name].mean()

    # smiling among photos that show a face at all, so it isn't just "more portraits"
    faces = photos[photos.face == 1]
    countries["smile_given_face"] = faces.groupby("country").smile.mean()

    for col in ["brightness", "saturation", "warmth", "colourfulness"]:
        countries[col] = g[col].mean()
    # colour from fewer than 20 photos is too noisy to trust
    countries.loc[countries.with_pixels < 20, ["brightness", "saturation", "warmth", "colourfulness"]] = np.nan

    whr = pd.read_csv(ROOT / "data/raw/whr_2014_owid.csv")
    whr = whr.rename(columns={"Entity": "country", "Code": "iso3", "Self-reported life satisfaction": "happiness"})
    countries = countries.join(whr.set_index("country")[["iso3", "happiness"]])

    countries.round(4).to_csv(OUT / "countries.csv")
    print(f"{len(photos):,} photos, {len(countries)} countries")


if __name__ == "__main__":
    main()
