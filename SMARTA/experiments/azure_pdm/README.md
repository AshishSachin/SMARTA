# Isolated Azure PdM experiment

This package runs an offline research experiment on the five supplied Microsoft Azure Predictive Maintenance benchmark CSVs. It does not import SMARTA's production inference module, modify AI4I artifacts, add an API route, or change Flutter.

The archive remains at its supplied location and is read directly without extraction. The archive's provenance is consistent with Microsoft's public sample, which Microsoft describes as synthesized from multiple real-world problems. The supplied ZIP has no license manifest, so redistribution and deployment rights are unverified.

## Run

From `SMARTA/`:

```bash
../.venv/bin/python -m experiments.azure_pdm.train
../.venv/bin/python -m unittest discover -s experiments/azure_pdm/tests -v
```

Override the dataset location with:

```bash
../.venv/bin/python -m experiments.azure_pdm.train --dataset-zip /path/to/archive.zip
```

Each run receives a unique directory under `artifacts/`, `metrics/`, and `reports/`; previous experiment outputs are not overwritten. `config.json` holds the seed, splits, model settings, and unset operational alert criteria.

## Interpretation

Targets mean a component failure event is logged in `(t, t + H]`, not that a physical failure onset is known at that exact time. Features use prior hourly observations/events only. Raw classifier scores are not calibrated probabilities. The locked-test results are benchmark evidence only and must not be connected to production inference.
