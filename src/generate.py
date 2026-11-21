"""Generate SYNTHETIC incident-level crime data for the Western Cape.

What is real and what is invented
---------------------------------
REAL   : the number of crimes per police station per month and crime type
         (SAPS monthly figures Apr 2021-Mar 2026; Apr-Sep 2026 from the quarterly releases,
         split into months using each station's 2025 monthly pattern); population per cell.
INVENTED: where inside the precinct and when (day, hour) each crime happened.

How locations and times are invented
------------------------------------
* Background risk per 500 m cell = population^0.8 x a smooth random "hotspot" surface, so some
  neighbourhoods are persistently riskier (as in real data). Violent types share part of the
  surface (gang territory); burglary has its own.
* Near-repeat contagion: each crime raises risk in the same and adjacent cells for the following
  days (decay ~7 days for violence, ~10 days for burglary; murders also raise attempted-murder
  risk and vice versa, mimicking retaliation). This is what real self-exciting models exploit.
* Each station-month's REAL total is spread over days (weekends heavier for violence) and then
  over the precinct's cells in proportion to background + contagion. Hours follow type profiles.

Because the contagion is built in, the PoC proves that the PIPELINE detects and exploits such
patterns; it does not prove that Western Cape crime has them. Real incident data is needed for that.

Inputs: data/inputs/cells.parquet, data/inputs/wc_monthly_targets.csv
Output: data/out/incidents_synthetic.parquet
"""
import json
import re

import numpy as np
import pandas as pd
from scipy import sparse

from common import CELL, CRIMESTATS, INPUTS, POC, PROVINCE, SEED, TYPES

DATA = CRIMESTATS / "data"

rng = np.random.default_rng(SEED)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def monthly_targets(stations):
    f = INPUTS / "wc_monthly_targets.csv"
    if f.exists():                        # committed copy: real SAPS station x type x month counts
        t = pd.read_csv(f, index_col=[0, 1])
        return t.astype(int)
    return monthly_targets_from_sources(stations)


def monthly_targets_from_sources(stations):
    m = pd.read_csv(DATA / "interim" / "saps_monthly.csv")
    m = m[(m.province == PROVINCE) & m.category.isin(TYPES)]
    key = {norm(s): s for s in stations}
    m["station"] = m.station.map(lambda s: key.get(norm(s)))
    m = m[m.station.notna()]
    t = m.pivot_table(index=["station", "category"], columns="month", values="count", aggfunc="sum").fillna(0)
    # Apr-Sep 2026 from the dashboard's quarterly figures (period 12 = Q1, 16 = Q2 of 2026/27)
    S = json.loads((DATA / "interim" / "stations.json").read_text())
    cats = S["cats"]
    q = {}
    for r in S["rows"]:
        if r[0] in key.values():
            for c in TYPES:
                a = r[5][cats.index(c)]
                q[(r[0], c)] = (a[12] or 0, a[16] or 0)
    new_months = ["2026-04-01", "2026-05-01", "2026-06-01", "2026-07-01", "2026-08-01", "2026-09-01"]
    prev = ["2025-04-01", "2025-05-01", "2025-06-01", "2025-07-01", "2025-08-01", "2025-09-01"]
    for nm in new_months:
        t[nm] = 0.0
    for (s, c), (q1, q2) in q.items():
        if (s, c) not in t.index:
            continue
        for qi, tot in ((0, q1), (1, q2)):
            pm = t.loc[(s, c), prev[qi * 3:(qi + 1) * 3]].values + 0.5
            alloc = rng.multinomial(int(round(tot)), pm / pm.sum())
            for k in range(3):
                t.loc[(s, c), new_months[qi * 3 + k]] = alloc[k]
    return t.astype(int)


def smooth_field(cells, n_bumps, scale_m, sd):
    """Sum of random Gaussian bumps -> log-risk surface."""
    xy = cells[["x", "y"]].values
    lo, hi = xy.min(0), xy.max(0)
    # place bumps where people are
    p = cells["pop"].values / cells["pop"].sum()
    centres = xy[rng.choice(len(xy), n_bumps, p=p)]
    amp = rng.normal(0, sd, n_bumps)
    z = np.zeros(len(xy))
    for c, a in zip(centres, amp):
        d2 = ((xy - c) ** 2).sum(1)
        z += a * np.exp(-d2 / (2 * scale_m ** 2))
    return z


def neighbours(cells):
    idx = {(a, b): i for i, (a, b) in enumerate(zip(cells.ix, cells.iy)) if a >= 0}
    r, c, v = [], [], []
    for (a, b), i in idx.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                j = idx.get((a + dx, b + dy))
                if j is not None:
                    r.append(i); c.append(j); v.append(1.0 if dx == dy == 0 else 0.35)
    n = len(cells)
    for i in np.where(cells.ix.values < 0)[0]:
        r.append(i); c.append(i); v.append(1.0)
    return sparse.csr_matrix((v, (r, c)), shape=(n, n))


HOURS = {  # relative frequency by hour of day
    "violent": np.array([6, 5, 4, 3, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 5, 6, 8, 9, 10, 10, 9, 8], float),
    "burglary": np.array([4, 4, 4, 4, 3, 3, 3, 4, 6, 7, 7, 6, 5, 5, 5, 5, 4, 4, 4, 4, 4, 4, 4, 4], float),
}


def main():
    cells = pd.read_parquet(INPUTS / "cells.parquet")
    stations = sorted(cells.station.unique())
    T = monthly_targets(stations)
    A = neighbours(cells)
    pop = cells["pop"].values
    gang = smooth_field(cells, 400, 1200, 0.7)
    base = {
        "Murder": np.log(pop + 1) * 0.6 + gang + smooth_field(cells, 300, 800, 0.5),
        "Attempted murder": np.log(pop + 1) * 0.6 + gang + smooth_field(cells, 300, 800, 0.5),
        "Robbery with aggravating circumstances": np.log(pop + 1) * 0.6 + 0.4 * gang + smooth_field(cells, 500, 900, 0.8),
        "Burglary at residential premises": np.log(pop + 1) * 0.6 + smooth_field(cells, 500, 1000, 0.9),
    }
    mu = {k: np.exp(v - v.max()) for k, v in base.items()}
    for k in mu:
        mu[k][cells.rural.values] *= 0.6          # sparse rural land: lower risk per person
    st_cells = {s: np.where(cells.station.values == s)[0] for s in stations}
    decay = {"Murder": np.exp(-1 / 7), "Attempted murder": np.exp(-1 / 7),
             "Robbery with aggravating circumstances": np.exp(-1 / 7), "Burglary at residential premises": np.exp(-1 / 10)}
    alpha = {"Murder": 0.9, "Attempted murder": 0.9, "Robbery with aggravating circumstances": 0.6,
             "Burglary at residential premises": 0.7}
    E = {k: np.zeros(len(cells)) for k in TYPES}
    months = sorted(T.columns)
    out = []
    for mth in months:
        start = pd.Timestamp(mth)
        days = pd.date_range(start, start + pd.offsets.MonthEnd(0))
        wd = np.array([1.25 if d.weekday() >= 4 else 0.9 for d in days])
        daily = {}
        for (s, c), n in T[mth].items():
            if n <= 0 or s not in st_cells:
                continue
            w = wd if c != "Burglary at residential premises" else np.ones(len(days))
            daily[(s, c)] = rng.multinomial(n, w / w.sum())
        for di, day in enumerate(days):
            today = {k: np.zeros(len(cells)) for k in TYPES}
            for c in TYPES:
                exc = A @ (E[c] + (0.5 * E["Attempted murder" if c == "Murder" else "Murder"] if c in ("Murder", "Attempted murder") else 0))
                lam = mu[c] * (1 + alpha[c] * exc)      # each recent nearby crime raises risk
                for s in stations:
                    d = daily.get((s, c))
                    if d is None or d[di] == 0:
                        continue
                    ids = st_cells[s]
                    p = lam[ids]
                    p = p / p.sum()
                    hits = rng.choice(ids, size=d[di], p=p)
                    np.add.at(today[c], hits, 1)
                    prof = HOURS["burglary" if c.startswith("Burglary") else "violent"]
                    hrs = rng.choice(24, size=d[di], p=prof / prof.sum())
                    for h, cid in zip(hrs, hits):
                        out.append((c, day + pd.Timedelta(hours=int(h), minutes=int(rng.integers(60))), int(cid), s))
            for c in TYPES:
                E[c] = E[c] * decay[c] + today[c]
        print(mth, len(out))
    df = pd.DataFrame(out, columns=["type", "datetime", "cell", "station"])
    # jitter location inside the cell
    xy = cells.set_index("cell").loc[df.cell, ["x", "y"]].values
    df["x"] = xy[:, 0] + rng.uniform(-CELL / 2, CELL / 2, len(df)) * (~cells.rural.values[df.cell])
    df["y"] = xy[:, 1] + rng.uniform(-CELL / 2, CELL / 2, len(df)) * (~cells.rural.values[df.cell])
    df["synthetic"] = True
    df.to_parquet(POC / "incidents_synthetic.parquet")
    # check: totals per station-month equal SAPS
    chk = df.assign(month=df.datetime.dt.strftime("%Y-%m-01")).groupby(["station", "type", "month"]).size()
    tgt = T.stack()
    tgt = tgt[tgt > 0]
    tgt.index.names = ["station", "type", "month"]
    ok = (chk.reindex(tgt.index).fillna(0).astype(int) == tgt).mean()
    print(f"{len(df):,} synthetic incidents; station-month totals equal SAPS for {ok:.1%} of cases")


if __name__ == "__main__":
    main()
