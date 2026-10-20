"""
Do photos know how happy a country is?

Two steps:
1. one signal at a time: rank correlation with the happiness score,
   with a bootstrap interval over countries
2. all signals together: ridge regression, scored by leave-one-country-out
   cross-validation, then a placebo run where the happiness scores are
   shuffled 1,000 times. if the real score doesn't beat the placebo,
   there's nothing there.
3. the same single-signal check on countries with 200+ photos only.
   this one was decided after seeing step 1, so treat it as a lead,
   not a finding.
4. wealth check: is a signal just a stand-in for GDP? we take out what
   log GDP per head explains (on ranks) and correlate what's left.
5. does a picture add anything to money? compare leave-one-out error of
   "GDP only" against "GDP + the three people signals". placebo: shuffle
   the photo signals between countries 1,000 times and see how often the
   gain is that big by luck.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed"
RNG = np.random.default_rng(7)

SIGNALS = [
    "smile_given_face", "smile", "face", "people", "together", "fun",
    "nature", "sunset", "city", "indoors", "pets", "food", "night",
    "joy_title", "brightness", "saturation", "warmth", "colourfulness",
]


def bootstrap_rho(x, y, n=2000):
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y = x[ok], y[ok]
    rhos = []
    for _ in range(n):
        i = RNG.integers(0, len(x), len(x))
        rhos.append(spearmanr(x[i], y[i]).statistic)
    return np.nanpercentile(rhos, [2.5, 97.5])


def one_by_one(df):
    rows = []
    y = df.happiness.to_numpy()
    for s in SIGNALS:
        x = df[s].to_numpy(dtype=float)
        ok = ~np.isnan(x)
        rho, p = spearmanr(x[ok], y[ok])
        lo, hi = bootstrap_rho(x, y)
        rows.append({"signal": s, "rho": rho, "lo": lo, "hi": hi, "p": p, "n": int(ok.sum())})
    return pd.DataFrame(rows).sort_values("rho", ascending=False)


def partial_rho(df, signal, control="log_gdp"):
    d = df[[signal, "happiness", control]].dropna().rank()
    resid = lambda col: d[col] - np.polyval(np.polyfit(d[control], d[col], 1), d[control])
    rho, p = spearmanr(resid(signal), resid("happiness"))
    return rho, p, len(d)


def wealth_check(df):
    rows = []
    for label, part in [("all", df), ("200plus", df[df.photos >= 200])]:
        for s in SIGNALS:
            rho, p, n = partial_rho(part, s)
            rows.append({
                "countries": label, "signal": s,
                "rho_with_gdp": spearmanr(part[s], part.log_gdp, nan_policy="omit").statistic,
                "partial_rho": rho, "p": p, "n": n,
            })
    return pd.DataFrame(rows)


PEOPLE = ["face", "people", "together"]


def loo_r2(X, y):
    from sklearn.linear_model import LinearRegression
    pred = cross_val_predict(make_pipeline(StandardScaler(), LinearRegression()), X, y, cv=LeaveOneOut())
    return r2(y, pred), pred


def money_plus_photos(df, runs=1000):
    d = df.dropna(subset=["log_gdp"])
    y = d.happiness.to_numpy()
    base, _ = loo_r2(d[["log_gdp"]].to_numpy(), y)
    both, pred = loo_r2(d[["log_gdp"] + PEOPLE].to_numpy(), y)

    gains = []
    photo = d[PEOPLE].to_numpy()
    for _ in range(runs):
        shuffled = photo[RNG.permutation(len(photo))]
        gains.append(loo_r2(np.column_stack([d.log_gdp, shuffled]), y)[0] - base)
    gains = np.array(gains)
    return {
        "n": len(d),
        "r2_gdp_only": round(base, 3),
        "r2_gdp_plus_people": round(both, 3),
        "gain": round(both - base, 3),
        "placebo_gain_95th": round(float(np.percentile(gains, 95)), 3),
        "placebo_p": round(float((gains >= both - base).mean()), 4),
    }, pd.Series(pred, index=d.index)


def model():
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        RidgeCV(alphas=np.logspace(-2, 3, 30)),
    )


def r2(y, pred):
    return 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()


def all_together(df, placebo_runs=1000):
    X, y = df[SIGNALS].to_numpy(dtype=float), df.happiness.to_numpy()
    pred = cross_val_predict(model(), X, y, cv=LeaveOneOut())
    real = r2(y, pred)

    fake = []
    for _ in range(placebo_runs):
        ys = RNG.permutation(y)
        fake.append(r2(ys, cross_val_predict(model(), X, ys, cv=LeaveOneOut())))
    fake = np.array(fake)

    fitted = model().fit(X, y)
    weights = pd.Series(fitted[-1].coef_, index=SIGNALS).sort_values()
    return real, fake, pred, weights


def main():
    df = pd.read_csv(OUT / "countries.csv", index_col="country").dropna(subset=["happiness"])

    single = one_by_one(df)
    single.round(3).to_csv(OUT / "signals.csv", index=False)
    print(single.round(2).to_string(index=False))

    well = one_by_one(df[df.photos >= 200])
    well.round(3).to_csv(OUT / "signals_200plus.csv", index=False)
    print(f"\ncountries with 200+ photos ({(df.photos >= 200).sum()}):")
    print(well.round(2).to_string(index=False))

    gdp = pd.read_csv(ROOT / "data/raw/gdp_2014_owid.csv").set_index("Entity")["GDP per capita"]
    df["log_gdp"] = np.log(df.index.map(gdp).astype(float))
    wealth = wealth_check(df)
    wealth.round(3).to_csv(OUT / "wealth_check.csv", index=False)
    print("\nwealth check:")
    print(wealth[wealth.signal.isin(["together", "people", "face", "nature", "sunset", "food"])].round(2).to_string(index=False))
    print("gdp vs happiness:", round(spearmanr(df.log_gdp, df.happiness, nan_policy="omit").statistic, 2))

    money, money_pred = money_plus_photos(df)
    print("\nmoney + photos:", money)

    real, fake, pred, weights = all_together(df)
    df["predicted_all_signals"] = pred
    df["predicted"] = money_pred
    df[["iso3", "happiness", "predicted", "predicted_all_signals", "log_gdp"]].round(3).to_csv(OUT / "predictions.csv")

    summary = {
        "countries": len(df),
        "photos": int(df.photos.sum()),
        "cv_r2": round(real, 3),
        "cv_rho": round(spearmanr(df.happiness, pred).statistic, 3),
        "placebo_r2_95th": round(float(np.percentile(fake, 95)), 3),
        "placebo_p": round(float((fake >= real).mean()), 4),
        "countries_200plus": int((df.photos >= 200).sum()),
        "money_plus_photos": money,
        "weights": weights.round(3).to_dict(),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
