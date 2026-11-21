# Western Cape hotspot forecasting: proof of concept

> **Synthetic data.** Every incident location and time in this repository is invented.
> The number of crimes per police station per month is real (SAPS, April 2021 to September 2026).

This proof of concept shows what the Western Cape could do with **incident-level** crime data:
forecast next month's crime hotspots on a 500 m grid across the province, and test those
forecasts the way crime analysts do. It exists to support a data-sharing request. With access to
geocoded SAPS case records (and the other sources listed below), the same pipeline runs on real
data.

It is part of the CrimeStats work (private repository `joeyreddy/crimestats`).

## What it does

1. **Grid**: 19,848 populated 500 m blocks (4,962 km²) and 80 rural cells across 152 Western Cape
   police precincts, with population from Stats SA 2022 / Census 2011 sub-places.
2. **Synthetic incidents** (`src/generate.py`): about 300,000 murders, attempted murders,
   aggravated robberies and residential burglaries. Each station-month's real SAPS total is spread
   over days, hours and blocks according to population, persistent neighbourhood risk and
   near-repeat contagion. Station-month totals match SAPS exactly.
3. **Forecasting** (`src/evaluate.py`): five methods, refitted before each of 24 unseen test months
   (October 2024 to September 2026): last month, last 12 months, smoothed last 3 months,
   self-exciting (long-run hotspots plus recent nearby crime) and Poisson regression.
4. **Evaluation**: hit rate, Prediction Accuracy Index (PAI) and Predictive Efficiency Index (PEI)
   at 5% of area; 80% interval coverage per station (Poisson against negative binomial); Knox
   near-repeat test.
5. **Safeguards** (`src/build_site.py`): who gets flagged (Operation Prosper precincts against
   their share of crime), and a simulation of the patrol-detection feedback loop.
6. **Demo page** (`site/`): interactive map and results.

## Headline results (synthetic, murder)

| Method | Hit rate in top 5% of blocks | PAI |
|---|---|---|
| Last month | 38% | 7.5 |
| Last 12 months | 67% | 13.3 |
| Self-exciting | 72% | 14.4 |
| Poisson regression | 73% | 14.6 |

These figures show the pipeline works and can tell methods apart. They do **not** show the
accuracy real data would give: locations, timing and contagion are simulated. Full write-up:
[docs/method-and-results.md](docs/method-and-results.md).

## Run it

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
./run.sh                       # generate -> evaluate -> build site data (about 30 seconds)
cd site && python3 -m http.server 8080   # open http://localhost:8080
```

Inputs are committed in `data/inputs/`: `cells.parquet` (the grid) and
`wc_monthly_targets.csv` (real SAPS station × crime type × month counts). `src/build_grid.py`
rebuilds the grid and needs the CrimeStats repository next to this one (or set `CRIMESTATS_ROOT`).

## Data needed to make it real

| Ingredient | In this demo | Real source |
|---|---|---|
| Crimes per station per month | Real | SAPS quarterly releases |
| Location and time of each crime | Simulated | SAPS Crime Administration System (CAS), geocoded, via data-sharing agreement |
| Calls for help | Simulated | SAPS 10111 and City of Cape Town emergency call logs |
| Independent check on violence | Simulated | Forensic Pathology mortuary records; trauma unit admissions |
| Gang territories and conflicts | Simulated | SAPS Crime Intelligence, gang task teams, GI-TOC researchers |
| Population per block | Real | Stats SA 2022 ward estimates, Census 2011 sub-places |
| Places that attract crime | Not used | City of Cape Town land use, liquor licences, transport hubs |

## Principles

Area-level only, no personal data. Police-detected crime (drugs, firearms) is kept separate from
crime the public reports. Every forecast carries a range. People, not the model, decide on
deployment. Any real incident data needs a POPIA impact assessment before use.

Private repository; all rights reserved.
