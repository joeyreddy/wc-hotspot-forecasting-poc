"""Shared settings for the synthetic proof of concept (Western Cape)."""
from pathlib import Path

import os

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
INPUTS = DATA / "inputs"          # committed inputs: cells.parquet, wc_monthly_targets.csv
POC = DATA / "out"                # generated outputs
SITE = ROOT / "site"              # demo page + poc-data.json
POC.mkdir(parents=True, exist_ok=True)
# Only build_grid.py needs the CrimeStats repository (boundaries, sub-places, SAPS monthly data)
CRIMESTATS = Path(os.environ.get("CRIMESTATS_ROOT", ROOT.parent / "crimestats"))

PROVINCE = "Western Cape"
CELL = 500                     # grid cell size in metres
CRS = "EPSG:32734"             # UTM 34S, metres
MIN_DENSITY = 50               # people per km2: sparser land goes to one rural cell per station
TYPES = ["Murder", "Attempted murder", "Robbery with aggravating circumstances",
         "Burglary at residential premises"]
SHORT = {"Murder": "murder", "Attempted murder": "attempted", "Robbery with aggravating circumstances": "robbery",
         "Burglary at residential premises": "burglary"}
PROSPER = ["Nyanga", "Philippi", "Gugulethu", "Kraaifontein", "Harare", "Khayelitsha", "Elsies River",
           "Ravensmead", "Manenberg", "Steenberg", "Muizenberg", "Mitchells Plain", "Mfuleni", "Delft",
           "Bishop Lavis"]
SEED = 20261121
