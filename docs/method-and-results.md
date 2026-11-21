# Proof of concept: hotspot forecasting on synthetic incident data (Western Cape)

**Purpose**: show decision-makers what CrimeStats can do once incident-level data is shared,
without waiting for data-sharing agreements.

## What is real and what is simulated

| Ingredient | Status |
|---|---|
| Crimes per police station per month (murder, attempted murder, robbery with aggravating circumstances, residential burglary), 152 WC precincts, Apr 2021–Sep 2026 | **Real** (SAPS) |
| Population per 500 m block | **Real** (Stats SA 2022 / Census 2011 sub-places) |
| Location and time of each crime inside its precinct | **Simulated** |

Simulation (`src/generate.py`): each station-month's real total is spread over days (weekends
heavier for violence), hours (type profiles) and 500 m blocks in proportion to population ×
persistent neighbourhood risk × near-repeat contagion (recent nearby crimes raise risk; murders
and attempted murders excite each other). 299,737 incidents; station-month totals match SAPS exactly.

## Pipeline (`src/`)

1. `build_grid.py`: 19,848 populated 500 m blocks (4,962 km²) plus 80 rural cells, 152 precincts, 7.0 m residents.
2. `generate.py`: synthetic incidents.
3. `evaluate.py`: five methods (last month, last 12 months, smoothed last 3 months, self-exciting,
   Poisson regression), refitted before each of 24 test months (Oct 2024–Sep 2026). Metrics:
   hit rate, PAI, PEI at 5% of area; station-level 80% interval coverage (Poisson vs negative binomial);
   Knox near-repeat test.
4. `build_site.py`: bundles results; Prosper-precinct flagging audit; feedback-loop simulation.
5. Demo page: `site/index.html` + `site/poc-data.json`.

## Results (synthetic)

| Murder | Hit rate | PAI |
|---|---|---|
| Last month | 38% | 7.5 |
| Last 12 months | 67% | 13.3 |
| Self-exciting | 72% | 14.4 |
| Poisson regression | 73% | 14.6 |

High PAI partly reflects the real concentration of Western Cape murders in a few precincts
(Prosper precincts: 5% of populated area, 28% of residents, 50% of murders). Station-level interval coverage:
Poisson under-covers for burglary (70%); negative binomial is closer to 80%.

## What it proves and what it does not

- Proves the end-to-end pipeline and evaluation work at provincial scale and can rank methods.
- Does **not** prove real-world accuracy: locations, timing and contagion are simulated (the Knox
  test finds clustering because it was built in). Real CAS incident data is needed.

## Data request (to replace the simulated parts)

SAPS CAS geocoded incidents; 10111 / City emergency calls; Forensic Pathology mortuary and trauma
admissions; gang-territory intelligence; City land-use and liquor licences. See the demo page table.
