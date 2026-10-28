"""
Four ways to guess a country's happiness, side by side:

  photos only     all 18 photo signals, ridge (from model.py)
  people only     faces + people + people together, nothing else
  money only      log GDP per head
  money + people  log GDP per head + the three people signals

Every guess is leave-one-country-out: the country being guessed is never
in the data the guess was made from. Then we score each one against three
reports, and look at which countries the photos pulled closer to the truth
and which ones they pushed away.
"""
import json
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed"

MODELS = {
    "photos_only": "Photos only",
    "people_only": "People only",
    "money_only": "Money only",
    "money_people": "Money + people",
}
REPORTS = {"happiness": "WHR 2012-14", "whr_2024": "WHR 2024", "wvs_happy": "World Values Survey"}
PEOPLE = ["face", "people", "together"]


def loo(X, y):
    return cross_val_predict(make_pipeline(StandardScaler(), LinearRegression()), X, y, cv=LeaveOneOut())


def main():
    compare = pd.read_csv(OUT / "compare_countries.csv", index_col="country")
    preds = pd.read_csv(OUT / "predictions.csv", index_col="country")
    signals = pd.read_csv(OUT / "countries.csv", index_col="country")[PEOPLE]

    df = compare[list(REPORTS)].join(preds[["predicted_all_signals", "predicted", "log_gdp"]]).join(signals)
    df = df.dropna(subset=["log_gdp"])
    df["photos_only"] = df.predicted_all_signals
    df["people_only"] = loo(df[PEOPLE], df.happiness)
    df["money_only"] = compare.gdp_only
    df["money_people"] = df.predicted

    scores = []
    for m, label in MODELS.items():
        row = {"model": label, "key": m}
        for r in REPORTS:
            d = df.dropna(subset=[r])
            row[r] = round(spearmanr(d[m], d[r]).statistic, 3)
        scores.append(row)
    scores = pd.DataFrame(scores)
    print(scores.to_string(index=False))

    # rank 1 = happiest. how far is each guess from the real rank?
    ranks = df[list(MODELS) + ["happiness"]].rank(ascending=False)
    off_money = (ranks.money_only - ranks.happiness).abs()
    off_both = (ranks.money_people - ranks.happiness).abs()
    moves = pd.DataFrame({
        "real": ranks.happiness,
        "money_only": ranks.money_only,
        "money_people": ranks.money_people,
        "closer_by": off_money - off_both,  # positive: the photos helped
    }).sort_values("closer_by", ascending=False)

    helped = moves[moves.closer_by > 0]
    hurt = moves[moves.closer_by < 0]
    print(f"\nphotos moved {len(helped)} countries closer, {len(hurt)} further, {len(moves) - len(helped) - len(hurt)} no change")
    print(moves.head(6).to_string())
    print(moves.tail(6).to_string())

    out = df[list(MODELS)].round(3).join(ranks[list(MODELS)].add_suffix("_rank")).join(moves[["real", "closer_by"]])
    out.to_csv(OUT / "showdown_countries.csv")
    scores.to_csv(OUT / "showdown_scores.csv", index=False)

    as_list = lambda part: [{"country": c, **{k: float(v) for k, v in r.items()}} for c, r in part.iterrows()]
    (OUT / "showdown.json").write_text(json.dumps({
        "scores": scores.to_dict(orient="records"),
        "helped": len(helped),
        "hurt": len(hurt),
        "rescued": as_list(moves.head(6)),
        "misled": as_list(moves.tail(6).iloc[::-1]),
    }, indent=2))


if __name__ == "__main__":
    main()
