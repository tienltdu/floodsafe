# Dashboard App Architecture Guide

This document explains how the files in this repository work together to produce the Streamlit dashboard, and what a future maintainer should change when building a similar app or extending this one.

## 1. What this app is

This repository is a read-only Streamlit dashboard for reviewing a precomputed reservoir operations scenario.

The app does not run optimization itself. It only:

1. loads exported artifacts from `data/`,
2. merges observed and optimized time series,
3. derives status and summary values for a selected playback window,
4. renders charts, alerts, recommendations, and downloadable outputs in Streamlit.

## 2. File and folder responsibilities

### App entry point

- `app.py`
  - Owns the Streamlit UI.
  - Builds the sidebar controls, KPI cards, alerts, recommendation panel, charts, summary table, and download buttons.
  - Imports all data-loading and business-logic helpers from `lib/dashboard_data.py`.

### Data and business logic

- `lib/dashboard_data.py`
  - Owns path definitions for the data files.
  - Loads JSON, CSV, and XLSX artifacts.
  - Derives calculated fields such as optimized reservoir level and optimized downstream level.
  - Merges observed and optimized time series on timestamp.
  - Computes playback-window summaries, operational status, threshold flags, and recommendation text.
  - Returns a `DashboardBundle` object that `app.py` uses.

### Input and output artifacts

- `data/DD_sub1234_2025_hourlyPS.xlsx`

  - Observed event data used for the baseline time series.
- `data/timeseries_export.csv`

  - Optimized time-series output used by the dashboard.
- `data/reservoir_parameters.csv`

  - Current parameter source for levels, thresholds, and priorities shown in the dashboard.
  - At runtime, these values override the same fields from the summary JSON.
- `data/storage_V.csv`

  - Storage curve used to convert optimized storage volume into optimized reservoir water level.
- `data/notebook_exports/summaries/*.json`

  - Run summary artifacts.
  - The app lists these files in the sidebar and lets the user choose one run.
  - Each JSON provides the time window, references to related outputs, and baseline metadata for the run.
- `data/notebook_exports/summaries/*.xlsx`

  - Downloadable workbook version of the selected run summary.
- `data/notebook_exports/figures/*.png`

  - Downloadable figure image for the selected run.

### Environment and packaging

- `requirements.txt`

  - Python dependencies needed by the app.
- `README.md`

  - Short deployment and run instructions.

## 3. Runtime dependency flow

The main runtime flow is:

1. `streamlit run app.py` starts the app.
2. `app.py` adds `lib/` to `sys.path` so it can import `dashboard_data`.
3. `app.py` calls `list_run_summaries()` to find available run JSON files in `data/notebook_exports/summaries/`.
4. The user selects a run summary and decision horizon in the sidebar.
5. `app.py` calls `load_dashboard_bundle(selected_summary_path)`.
6. `load_dashboard_bundle()` loads and combines the supporting files:
   - summary JSON,
   - reservoir parameters CSV,
   - observed event XLSX,
   - optimized time-series CSV,
   - storage curve CSV.
7. `load_dashboard_bundle()` returns a `DashboardBundle` containing:
   - raw summary metadata,
   - observed data,
   - optimized data,
   - merged time series,
   - merged parameters,
   - artifact-readiness info.
8. `app.py` uses `timestamp_options()` to build the playback slider.
9. `app.py` uses `horizon_slice()` to extract the active playback window.
10. `derive_operational_state()` and `derive_window_summary()` compute the state shown in cards, alerts, and tables.
11. `recommendation_text()` turns the computed state into operator-facing text.
12. `app.py` renders Plotly charts and download buttons using the bundle and computed window data.

## 4. How the two main Python files connect

### `app.py` depends on `lib/dashboard_data.py`

`app.py` imports these helpers:

- `list_run_summaries()`
- `load_dashboard_bundle()`
- `timestamp_options()`
- `horizon_slice()`
- `derive_operational_state()`
- `derive_window_summary()`
- `recommendation_text()`
- `resolve_local_artifact()`

That means `app.py` is intentionally thin. It should mainly handle presentation and user interaction, while `lib/dashboard_data.py` should own data contracts and calculation logic.

### Recommended maintenance boundary

Keep this split when extending the app:

- Put UI layout and Plotly chart code in `app.py`.
- Put file loading, data cleanup, derived metrics, thresholds, and recommendation logic in `lib/dashboard_data.py`.

If a future version grows significantly, the next clean split would be:

- `lib/data_loader.py` for file I/O,
- `lib/domain_logic.py` for status and recommendation rules,
- `lib/charts.py` for Plotly figure creation,
- `app.py` as the Streamlit composition layer only.

## 5. Data model used by the app

### A. Summary JSON drives run selection

Each summary JSON acts as the run descriptor. It tells the app:

- which event window to display,
- where the related PNG and XLSX outputs are,
- what default reservoir metadata came from the export process.

Important fields used by the app include:

- `time_window.start`
- `time_window.stop`
- `raw_event_source`
- `files.figure_png`
- `files.summary_xlsx`
- `reservoir_parameters.values`
- `reservoir_parameters.units`

### B. Reservoir parameters CSV overrides summary JSON values

Inside `load_dashboard_bundle()`, the app reads `data/reservoir_parameters.csv` and merges it into the JSON summary parameters.

Current behavior:

- summary JSON values are loaded first,
- CSV values are applied after that,
- the CSV wins when keys overlap.

This is important for maintenance because changing `data/reservoir_parameters.csv` changes thresholds and labels shown in the dashboard even if the JSON still contains older values.

### C. Observed and optimized series are aligned on time

The merged playback table is built by:

- reading observed rows from the XLSX file,
- reading optimized rows from `timeseries_export.csv`,
- filtering both datasets to the selected summary JSON `time_window`,
- inner-joining on `observed.Datetime == optimized.time`.

Only timestamps present in both datasets appear in the dashboard slider and charts.

## 6. Derived fields and calculations

The dashboard does more than display raw file contents. It computes several values at load time and playback time.

### Load-time derived fields in `lib/dashboard_data.py`

- `reservoir_level_optimized`

  - Derived from `V_Reservoir1` using `data/storage_V.csv`.
- `downstream_level_optimized`

  - Derived from `Q_controlpoint` using the rating-curve constants:
    - `DOWNSTREAM_STAGE_K`
    - `DOWNSTREAM_STAGE_P`
    - `DOWNSTREAM_STAGE_WREF`
- threshold columns in `merged`

  - Copied from summary parameters into the merged DataFrame so downstream logic can reference them consistently.

### Playback-window derived fields

For the currently selected timestamp and horizon, the app computes:

- release peak observed vs optimized,
- downstream peak observed vs optimized,
- end-of-window observed and optimized water level,
- percent change against observed values,
- threshold flags,
- overall status: `normal`, `watch`, or `critical`,
- recommendation text and tradeoff text.

## 7. How the UI is assembled

Inside `main()` in `app.py`, the dashboard is built in this order:

1. Page title and caption.
2. Sidebar controls:
   - decision horizon radio,
   - run-summary select box,
   - playback-time slider,
   - artifact readiness panel.
3. Status banner.
4. Top KPI metrics.
5. Alerts and recommendation panel.
6. Four Plotly charts:
   - reservoir water level,
   - reservoir inflow/outflow,
   - downstream flow,
   - downstream water level.
7. Run-summary metrics and table for the active playback window.
8. Download buttons for JSON, XLSX, and PNG outputs.

Chart helpers in `app.py` are:

- `make_level_chart()`
- `make_release_chart()`
- `make_downstream_flow_chart()`
- `make_downstream_level_chart()`

These functions expect the merged playback window DataFrame and threshold/parameter values already prepared by `lib/dashboard_data.py`.

## 8. What to change for common maintenance tasks

### Change thresholds or operating targets

Update:

- `data/reservoir_parameters.csv`

Why:

- this file overrides matching parameter values from the summary JSON at runtime.

### Add a new scenario/run to the dashboard

Add or replace:

- a new summary JSON in `data/notebook_exports/summaries/`,
- its matching summary XLSX,
- its matching PNG,
- updated `data/timeseries_export.csv` and observed event XLSX if the new run depends on different underlying time-series data.

Check:

- the JSON `time_window` matches the timestamps in both observed and optimized data,
- the JSON `files` paths resolve correctly.

### Change recommendation wording or status rules

Update:

- `derive_operational_state()` in `lib/dashboard_data.py`
- `recommendation_text()` in `lib/dashboard_data.py`

### Add a new chart or KPI

Usually update both:

- `lib/dashboard_data.py` if the new value needs transformation or derived metrics,
- `app.py` if the new value is only a presentation change.

Rule of thumb:

- if it touches raw files, parsing, or business rules, put it in `lib/dashboard_data.py`;
- if it only changes layout or figure rendering, put it in `app.py`.

### Swap in a different project or reservoir

You will likely need to update:

- file paths in `lib/dashboard_data.py`,
- expected column names in the observed XLSX and optimized CSV loaders,
- storage-curve mapping in `load_storage_curve()` / `load_optimized_timeseries()`,
- downstream stage constants,
- threshold and parameter names,
- text labels in `app.py`.

This app is not fully schema-driven yet, so changing domains usually requires code updates, not just data replacement.

## 9. Assumptions and coupling to be aware of

The app currently assumes:

- observed data contains a `Datetime` column and fields such as `WLDD`, `QinDD`, `QoutDD`, `QinSG`, and optionally `WLSG`;
- optimized data contains `time`, `Qoutput_Reservoir1`, `Q_controlpoint`, and `V_Reservoir1`;
- summary JSON has a valid `time_window`;
- files referenced by the JSON are either correct as written or recoverable through `resolve_local_artifact()`;
- one `timeseries_export.csv` is compatible with the selected summary JSON.

The last point is the biggest architectural coupling: the selected run summary can vary per file, but the optimized CSV path is currently global, not per run.

If future runs need separate optimized time-series files, the clean improvement is to store a per-run CSV path in the summary JSON and make `load_optimized_timeseries()` accept that path.

## 10. Suggested path for a similar future app

If someone wants to build a similar dashboard for another case, reuse this sequence:

1. Define the artifact contract first:
   - summary JSON,
   - observed time-series file,
   - optimized time-series file,
   - parameter file,
   - optional downloadable outputs.
2. Implement loaders and validation in a library module.
3. Merge datasets into one playback-ready DataFrame.
4. Compute status logic and recommendation text in pure Python helpers.
5. Keep Streamlit focused on controls, layout, and charts.
6. Make each run self-describing by storing all required artifact paths in the run summary.

That keeps the UI simple and makes maintenance easier when data sources evolve.

## 11. Quick reference

### Startup

- command: `streamlit run app.py`

### Core code path

- `app.py` -> `list_run_summaries()` -> `load_dashboard_bundle()` -> `horizon_slice()` -> `derive_operational_state()` / `derive_window_summary()` -> `recommendation_text()` -> Streamlit render

### Most important files

- `app.py`
- `lib/dashboard_data.py`
- `data/reservoir_parameters.csv`
- `data/timeseries_export.csv`
- `data/DD_sub1234_2025_hourlyPS.xlsx`
- `data/notebook_exports/summaries/*.json`
