"""Hotspot forecasting models and their evaluation on the synthetic incidents.

Task: at the end of each month, rank the 500 m cells for the NEXT month; police can cover the
top 5% of the populated area (about 990 cells, 250 km2). Rural pseudo-cells are never flagged
but their crimes count in the denominators.

Models (each uses only data available at the forecast date)
  naive        last month's counts
  persistent   last 12 months' counts (long-run hotspots)
  kde          last 3 months, spatially smoothed (kernel density style)
  self_exciting long-run background + exponentially decaying recent crimes nearby
                (a discrete version of the self-exciting point process used in real systems);
                decay and weight fitted on training months
  glm          Poisson regression on lagged own and neighbour counts, recent 14 days, population

Metrics (standard in crime forecasting)
  hit rate  share of next month's crimes inside the flagged cells
  PAI       Prediction Accuracy Index = hit rate / share of area flagged (higher = better; 1 = random)
  PEI       Predictive Efficiency Index = crimes captured / most crimes ANY choice of that many
            cells could have captured (0-1)
Also: station-level 80% interval coverage, and a Knox near-repeat test.

Output: data/out/eval.json (+ per-month predictions for the demo page)
"""
import json

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.spatial import cKDTree
from sklearn.linear_model import PoissonRegressor

from common import INPUTS, POC, SHORT, TYPES
from generate import neighbours

TOP = 0.05
TEST_N = 24


def month_matrix(inc, cells, months, typ):
    d = inc[inc.type == typ]
    mi = {m: i for i, m in enumerate(months)}
    r = d.month.map(mi).values
    M = sparse.coo_matrix((np.ones(len(d)), (r, d.cell.values)), shape=(len(months), len(cells))).toarray()
    return M


def recent_weighted(inc_t, cells_n, end, tau, days=60):
    d = inc_t[(inc_t.datetime < end) & (inc_t.datetime >= end - pd.Timedelta(days=days))]
    w = np.exp(-(end - d.datetime).dt.total_seconds().values / 86400 / tau)
    return np.bincount(d.cell.values, weights=w, minlength=cells_n)


def metrics(score, actual, grid_mask):
    n_flag = int(round(TOP * grid_mask.sum()))
    s = np.where(grid_mask, score + 1e-9 * np.random.default_rng(0).random(len(score)), -np.inf)
    flag = np.argpartition(-s, n_flag)[:n_flag]
    N = actual.sum()
    if N == 0:
        return None, flag
    hits = actual[flag].sum()
    best = np.sort(actual[grid_mask])[::-1][:n_flag].sum()
    hr = hits / N
    return {"hit": hr, "pai": hr / (n_flag / grid_mask.sum()), "pei": hits / best if best else 0}, flag


def main():
    cells = pd.read_parquet(INPUTS / "cells.parquet")
    inc = pd.read_parquet(POC / "incidents_synthetic.parquet")
    inc["month"] = inc.datetime.dt.strftime("%Y-%m-01")
    months = sorted(inc.month.unique())
    n = len(cells)
    grid = ~cells.rural.values
    A = neighbours(cells)
    A2 = A @ A
    logpop = np.log1p(cells["pop"].values)
    test = months[-TEST_N:]
    res = {"months": test, "types": {}, "models": ["naive", "persistent", "kde", "self_exciting", "glm"]}
    preds = {}
    for typ in TYPES:
        M = month_matrix(inc, cells, months, typ)
        it = inc[inc.type == typ]
        mi = {m: i for i, m in enumerate(months)}

        # fit self-exciting weights on training months (before the test period)
        train = months[13:-TEST_N]
        best = None
        for tau in (3, 7, 14, 30):
            for beta in (0.5, 2, 5, 10, 20):
                pais = []
                for m in train[::3]:
                    i = mi[m]
                    end = pd.Timestamp(m)
                    bg = A @ M[i - 12:i].sum(0) / 12
                    rc = A @ recent_weighted(it, n, end, tau)
                    r, _ = metrics(bg + beta * rc, M[i], grid)
                    if r:
                        pais.append(r["pai"])
                score = np.mean(pais)
                if best is None or score > best[0]:
                    best = (score, tau, beta)
        _, tau, beta = best

        # GLM training rows: all months from 13 to the first test month
        def feats(i, end):
            return np.column_stack([
                np.log1p(M[i - 1]), np.log1p(M[i - 3:i].sum(0)), np.log1p(M[i - 12:i].sum(0)),
                np.log1p(A @ M[i - 3:i].sum(0)), np.log1p(A @ M[i - 12:i].sum(0)),
                np.log1p(recent_weighted(it, n, end, 7, 14)), logpop])
        glm = None
        out = {k: [] for k in res["models"]}
        cover = []
        for k_m, m in enumerate(test):
            i = mi[m]
            end = pd.Timestamp(m)
            if glm is None or k_m % 6 == 0:
                Xs, ys = [], []
                for j in range(12, i, 2):
                    Xs.append(feats(j, pd.Timestamp(months[j]))[grid])
                    ys.append(M[j][grid])
                glm = PoissonRegressor(alpha=1e-4, max_iter=300).fit(np.vstack(Xs), np.concatenate(ys))
            F = feats(i, end)
            scores = {
                "naive": M[i - 1].astype(float),
                "persistent": M[i - 12:i].sum(0).astype(float),
                "kde": A2 @ M[i - 3:i].sum(0),
                "self_exciting": A @ M[i - 12:i].sum(0) / 12 + beta * (A @ recent_weighted(it, n, end, tau)),
                "glm": glm.predict(F),
            }
            for k, sc in scores.items():
                r, flag = metrics(sc, M[i], grid)
                out[k].append(r)
                preds.setdefault(SHORT[typ], {}).setdefault(k, []).append(sorted(int(x) for x in flag))
            # station-level coverage of 80% intervals from the GLM (Poisson and negative binomial)
            mu_st = pd.Series(glm.predict(F)).groupby(cells.station.values).sum()
            act_st = pd.Series(M[i]).groupby(cells.station.values).sum()
            cover.append((mu_st, act_st))
        # dispersion from the first half of the test months, coverage on the second half
        half = len(cover) // 2
        mu_a = np.concatenate([c[0].values for c in cover[:half]])
        y_a = np.concatenate([c[1].values for c in cover[:half]])
        phi = max(1e-6, (((y_a - mu_a) ** 2 - mu_a) / np.maximum(mu_a, 1e-6) ** 2).mean())
        from scipy import stats
        cp, cn = [], []
        for mu_s, y_s in cover[half:]:
            mu_v, y_v = mu_s.values, y_s.values
            lo, hi = stats.poisson.ppf(0.1, mu_v), stats.poisson.ppf(0.9, mu_v)
            cp.append(((y_v >= lo) & (y_v <= hi)).mean())
            r_ = 1 / phi
            p_ = r_ / (r_ + mu_v)
            lo, hi = stats.nbinom.ppf(0.1, r_, p_), stats.nbinom.ppf(0.9, r_, p_)
            cn.append(((y_v >= lo) & (y_v <= hi)).mean())
        res["types"][SHORT[typ]] = {
            "label": typ, "self_exciting_params": {"decay_days": tau, "weight": beta},
            "monthly": {k: [None if r is None else {kk: round(vv, 3) for kk, vv in r.items()} for r in v] for k, v in out.items()},
            "mean": {k: {kk: round(float(np.mean([r[kk] for r in v if r])), 3) for kk in ("hit", "pai", "pei")} for k, v in out.items()},
            "station_interval_coverage": {"poisson": round(float(np.mean(cp)), 3), "neg_binomial": round(float(np.mean(cn)), 3)},
            "actual": [[int(c) for c in np.nonzero(M[mi[m]])[0]] for m in test],
            "actual_n": [[int(M[mi[m]][c]) for c in np.nonzero(M[mi[m]])[0]] for m in test],
        }
        print(typ, json.dumps(res["types"][SHORT[typ]]["mean"]), res["types"][SHORT[typ]]["station_interval_coverage"])

    # Knox near-repeat test on violent crime (murder + attempted murder), last 12 months
    v = inc[inc.type.isin(TYPES[:2]) & (inc.month >= months[-12]) & ~cells.rural.values[inc.cell]]
    xy = v[["x", "y"]].values
    t = (v.datetime - v.datetime.min()).dt.total_seconds().values / 86400
    pairs = np.array(list(cKDTree(xy).query_pairs(2000)))
    dists = np.linalg.norm(xy[pairs[:, 0]] - xy[pairs[:, 1]], axis=1)
    dbands = [0, 250, 500, 1000, 2000]
    tbands = [0, 7, 14, 30, 60]

    def table(tt):
        dt = np.abs(tt[pairs[:, 0]] - tt[pairs[:, 1]])
        H, _, _ = np.histogram2d(dists, dt, bins=[dbands, tbands])
        return H
    obs = table(t)
    rng = np.random.default_rng(1)
    perm = np.mean([table(rng.permutation(t)) for _ in range(30)], axis=0)
    res["knox"] = {"distance_bands_m": dbands, "time_bands_days": tbands,
                   "ratio": np.round(obs / np.maximum(perm, 1e-9), 2).tolist(), "events": int(len(v))}
    print("knox", res["knox"]["ratio"])
    (POC / "eval.json").write_text(json.dumps({k: v for k, v in res.items()}, separators=(",", ":")))
    (POC / "preds.json").write_text(json.dumps(preds, separators=(",", ":")))


if __name__ == "__main__":
    main()
