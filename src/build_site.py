"""Bundle the PoC results for the demo page, and run the feedback-loop simulation.

Output: site/poc-data.json
"""
import json

import numpy as np
import pandas as pd

from common import INPUTS, POC, PROSPER, SITE, SHORT, TYPES

rng = np.random.default_rng(7)


def feedback_sim(n=300, months=24, top=0.1):
    """Toy model of the patrol -> detection feedback loop for police-detected crime (e.g. drugs).
    True activity is fixed. Detections = activity x (base + patrol effect). Policy A sends patrols
    to where detections were highest last month; policy B sends them by public-reported violence,
    which does not depend on patrols. Measures how concentrated patrols become versus the truth."""
    true = rng.lognormal(0, 0.8, n)
    violence = true * rng.lognormal(0, 0.5, n)          # reported crime correlated with activity
    k = int(top * n)
    true_top = set(np.argsort(-true)[:k])
    out = {}
    for policy in ("detections", "reported"):
        patrol = np.zeros(n)
        patrol[rng.choice(n, k, replace=False)] = 1       # month 0: patrols spread at random
        share_true, conc = [], []
        for _ in range(months):
            det = rng.poisson(true * (0.05 + 2.0 * patrol))
            score = det if policy == "detections" else violence + rng.normal(0, 0.1, n)
            chosen = np.argsort(-score)[:k]
            patrol = np.zeros(n)
            patrol[chosen] = 1
            share_true.append(round(len(true_top & set(chosen)) / k, 3))
            conc.append(round(det[chosen].sum() / det.sum(), 3))
        out[policy] = {"patrols_in_truly_highest_areas": share_true, "detections_share_in_patrolled": conc}
    out["true_share_of_activity_in_top"] = round(float(np.sort(true)[::-1][:k].sum() / true.sum()), 3)
    return out


def delta(ids):
    out, prev = [], 0
    for i in ids:
        out.append(i - prev)
        prev = i
    return out


def main():
    cells = pd.read_parquet(INPUTS / "cells.parquet")
    ev = json.loads((POC / "eval.json").read_text())
    preds = json.loads((POC / "preds.json").read_text())
    stations = sorted(cells.station.unique())
    sidx = {s: i for i, s in enumerate(stations)}
    prosper_cells = cells.station.isin(PROSPER).values
    grid = ~cells.rural.values
    pop = cells["pop"].values
    bias = {}
    for t, models in preds.items():
        bias[t] = {}
        for m, flags in models.items():
            sh = np.mean([prosper_cells[np.array(f)].mean() for f in flags])
            bias[t][m] = round(float(sh), 3)
    crime_share = {}
    for t, v in ev["types"].items():
        tot = pros = 0
        for ids, ns in zip(v["actual"], v["actual_n"]):
            ids = np.array(ids, int); ns = np.array(ns)
            tot += ns.sum(); pros += ns[prosper_cells[ids]].sum() if len(ids) else 0
        crime_share[t] = round(float(pros / tot), 3)
    data = {
        "note": "SYNTHETIC incident locations and times. Monthly station totals are real SAPS figures.",
        "cells": {"lon": cells.lon.round(4).tolist(), "lat": cells.lat.round(4).tolist(),
                  "st": [sidx[s] for s in cells.station], "pop": cells["pop"].round().astype(int).tolist(),
                  "rural": cells.rural.astype(int).tolist()},
        "stations": stations, "prosper": PROSPER,
        "prosper_share": {"area": round(float(prosper_cells[grid].mean()), 3),
                          "population": round(float(pop[prosper_cells].sum() / pop.sum()), 3)},
        "months": ev["months"], "models": ev["models"], "knox": ev["knox"],
        "places": json.loads((INPUTS / "places.json").read_text()) if (INPUTS / "places.json").exists() else {},
        "types": {}, "bias_prosper_share_of_flagged": bias, "prosper_share_of_crime": crime_share, "feedback": feedback_sim(),
    }
    for t, v in ev["types"].items():
        data["types"][t] = {k: v[k] for k in ("label", "mean", "monthly", "station_interval_coverage", "self_exciting_params")}
        data["types"][t]["actual"] = [delta(a) for a in v["actual"]]
        data["types"][t]["actual_n"] = v["actual_n"]
        data["types"][t]["flags"] = {m: [delta(f) for f in fl] for m, fl in preds[t].items()}
    site = SITE
    site.mkdir(exist_ok=True)
    (site / "poc-data.json").write_text(json.dumps(data, separators=(",", ":")))
    print("poc-data.json", round((site / "poc-data.json").stat().st_size / 1e6, 2), "MB")
    print(json.dumps(data["feedback"])[:300])
    print(data["prosper_share"], json.dumps(bias["murder"]))


if __name__ == "__main__":
    main()
