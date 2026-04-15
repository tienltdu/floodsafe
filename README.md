# Streamlit Operator Demo Package

This folder is the deployment-ready package for the Dakdrinh flood-operations demo app.

## Contents

- `app.py`
- `requirements.txt`
- `lib/dashboard_data.py`
- `data/reservoir_parameters.csv`
- `data/DD_sub1234_2025_hourlyPS.xlsx`
- `data/storage_V.csv`
- `data/timeseries_export.csv`
- `data/notebook_exports/figures/*.png`
- `data/notebook_exports/summaries/*.json`
- `data/notebook_exports/summaries/*.xlsx`

## Purpose

This package is intended for hosted deployment as a read-only website.

It does **not** run optimization on the server.
It only reads precomputed dashboard artifacts generated from the notebook workflow.

## Local Run

Create a Python environment and install:

```powershell
pip install -r requirements.txt
```

Then launch:

```powershell
streamlit run app.py
```

## Deploy

This folder can be pushed as the app root for:

- Streamlit Community Cloud
- Render
- other simple Python app hosting services

Use:

- main file: `app.py`
- dependencies: `requirements.txt`

## Refreshing Data

When you want newer dashboard content:

1. Run the main notebook in the root project:
   - `src/Optimazation_Ruby.ipynb`
2. Copy the refreshed artifacts into this package:
   - `src/reservoir_parameters.csv`
   - `src/DD_sub1234_2025_hourlyPS.xlsx`
   - `src/storage_V.csv`
   - `output/timeseries_export.csv`
   - latest `output/notebook_exports/figures/*`
   - latest `output/notebook_exports/summaries/*`

## Notes

- Keep this package small and stable.
- Do not place notebooks, model files, or RTC-Tools runtime code here unless the hosted app actually needs them.
