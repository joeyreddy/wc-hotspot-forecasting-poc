#!/usr/bin/env bash
# Rebuild the proof of concept: synthetic incidents -> models and evaluation -> demo data.
set -euo pipefail
cd "$(dirname "$0")/src"
python3 generate.py
python3 evaluate.py
python3 build_site.py
echo "Open site/index.html through a web server, e.g.: cd site && python3 -m http.server 8080"
