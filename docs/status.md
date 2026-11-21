# Status: Western Cape hotspot forecasting PoC

_Last updated: 21 Nov 2026_

## Links
- Live demo (private): https://claude.ai/artifact/DaRyQ949ZNePGVbowqAvuf
- Repo: github.com/joeyreddy/wc-hotspot-forecasting-poc (private) — `src/`, `data/inputs/`, `site/`, `docs/method-and-results.md`, `run.sh`
- Older copy also in crimestats `poc/` (removal offered, not decided)

## Purpose
Prove, on synthetic incident data, what the province could do with incident-level crime data, to support a data-sharing request (SAPS / Dept of Police Oversight and Community Safety). Audience: Minister Anroux Marais (mandate: Western Cape) and officials.

## Current state
- Scope: all 152 WC precincts; 19,848 populated 500 m blocks + 80 rural cells; 7.0 m residents.
- ~300k synthetic incidents (murder, attempted murder, aggravated robbery, residential burglary); station-month totals = real SAPS Apr 2021–Sep 2026; locations/times simulated with persistent risk + near-repeat contagion.
- Five methods over 24 out-of-sample months (Oct 2024–Sep 2026). Murder: last month 38% / PAI 7.5; last 12 months 67% / 13.3; self-exciting 72% / 14.4; Poisson regression 73% / 14.6.
- Also: station 80% interval coverage (Poisson vs negative binomial), Knox near-repeat test, Prosper flagging audit (5% of area, 28% of residents, 50% of murders), feedback-loop simulation, data-request table.

## Open items
1. Draft the data-sharing request (SAPS CAS geocoded incidents, 10111 / City calls, mortuary and trauma data, gang intelligence, City land use).
2. Stakeholder deck built on the demo for the Minister's visit.
3. POPIA impact assessment and ethics sign-off before any real data.
4. Possible additions: risk terrain modelling layer, hierarchical count model, PAI at several area thresholds.

## Decisions
- Synthetic data clearly labelled everywhere; the PoC proves the pipeline, not real-world accuracy.
- Area-level only; police-detected crime kept separate; ranges shown with forecasts; humans decide deployment.
- Separate private repo; no licence.
