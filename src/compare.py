"""
How does the photo model's happiness compare with other surveys?

The model was fitted on the World Happiness Report from 2012-2014, the same
years as the photos. Here we line its predictions up against:

- WHR 2024: same question (rate your life 0 to 10), ten years later
- World Values Survey: "taking all things together, would you say you are
  happy?", share answering very or rather happy, mostly the 2017-2022 wave

For a fair baseline we also predict from GDP alone. If the photos help,
GDP + people photos should line up with the other surveys better than GDP
does on its own.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import LeaveOneOut, cross_val_predict

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed"

# the two countries the write-up looks at closely
FOCUS = ["Norway", "Mexico"]


def load(name, col):
    df = pd.read_csv(ROOT / f"data/raw/{name}.csv")
    return df.set_index("Entity")[col]


def main():
    df = pd.read_csv(OUT / "predictions.csv", index_col="country").dropna(subset=["log_gdp"])
    df["gdp_only"] = cross_val_predict(LinearRegression(), df[["log_gdp"]], df.happiness, cv=LeaveOneOut())
    df["whr_2024"] = load("whr_2024_owid", "Self-reported life satisfaction")
    df["wvs_happy"] = load("wvs_happy_owid", "Happiness: Happy")

    reports = {"happiness": "WHR 2012-14", "whr_2024": "WHR 2024", "wvs_happy": "World Values Survey"}
    rows = []
    for col, label in reports.items():
        d = df.dropna(subset=[col])
        rows.append({
            "report": label,
            "countries": len(d),
            "photos_model": spearmanr(d.predicted, d[col]).statistic,
            "gdp_only": spearmanr(d.gdp_only, d[col]).statistic,
        })
    table = pd.DataFrame(rows)
    table["gain"] = table.photos_model - table.gdp_only
    table.round(3).to_csv(OUT / "compare_reports.csv", index=False)
    print(table.round(3).to_string(index=False))

    # ranks make different scales comparable: 1 = happiest of our countries
    ranks = pd.DataFrame({
        "predicted": df.predicted.rank(ascending=False),
        "gdp_only": df.gdp_only.rank(ascending=False),
        **{col: df[col].rank(ascending=False) for col in reports},
    })
    out = df[["predicted", "gdp_only", *reports]].round(3).join(ranks.add_suffix("_rank"))
    out.to_csv(OUT / "compare_countries.csv")
    print(out.loc[FOCUS].T.to_string())

    (OUT / "compare.json").write_text(json.dumps({
        "reports": table.round(3).to_dict(orient="records"),
        "focus": {c: out.loc[c].to_dict() for c in FOCUS},
        "n": len(df),
    }, indent=2))


if __name__ == "__main__":
    main()
