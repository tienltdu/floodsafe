from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
LIB_DIR = PROJECT_ROOT / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from dashboard_data import (  # noqa: E402
    load_dashboard_bundle,
    list_run_summaries,
    recommendation_text,
    resolve_local_artifact,
    horizon_slice,
    timestamp_options,
)


st.set_page_config(
    page_title="Dakdrinh Flood Operations Demo",
    page_icon="🌊",
    layout="wide",
)


def format_status(status: str) -> str:
    mapping = {
        "normal": "Normal",
        "watch": "Watch",
        "critical": "Critical",
    }
    return mapping.get(status, status.title())


def status_color(status: str) -> str:
    colors = {
        "normal": "#1b7f3b",
        "watch": "#c47a00",
        "critical": "#b42318",
    }
    return colors.get(status, "#344054")


def make_level_chart(df, params, current_time):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Datetime"], y=df["WLDD"], name="Observed WL", line=dict(color="black", width=2)))
    fig.add_trace(
        go.Scatter(
            x=df["Datetime"],
            y=df["reservoir_level_optimized"],
            name="Optimized WL",
            line=dict(color="#d92d20", width=2.5, dash="dash"),
        )
    )
    band_lines = [
        ("Dead WL", params["dead_water_level"], "#6941c6"),
        ("Pre-Flood", params["pre_flood_target_level"], "#16a34a"),
        ("Normal WL", params["normal_water_level"], "#2563eb"),
        ("Max Allowable", params["maximum_allowable_reservoir_level"], "#b42318"),
    ]
    for name, value, color in band_lines:
        fig.add_hline(y=value, line_color=color, line_dash="dot", annotation_text=name, annotation_position="top left")

    fig.add_vline(x=current_time, line_color="#98a2b3", line_dash="dash")
    fig.update_layout(
        title="Reservoir Water Level",
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(orientation="h", y=1.08),
        xaxis_title="Time",
        yaxis_title="Water Level (m)",
        height=360,
    )
    return fig


def make_release_chart(df, current_time):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Datetime"], y=df["QinDD"], name="Observed Inflow", line=dict(color="#2f9e44", width=2)))
    fig.add_trace(go.Scatter(x=df["Datetime"], y=df["QoutDD"], name="Observed Outflow", line=dict(color="black", width=2, dash="dash")))
    fig.add_trace(
        go.Scatter(
            x=df["Datetime"],
            y=df["Qoutput_Reservoir1"],
            name="Optimized Outflow",
            line=dict(color="#d92d20", width=2.5),
        )
    )
    fig.add_vline(x=current_time, line_color="#98a2b3", line_dash="dash")
    fig.update_layout(
        title="Reservoir Inflow / Outflow Hydrograph",
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(orientation="h", y=1.08),
        xaxis_title="Time",
        yaxis_title="Flow (m3/s)",
        height=360,
    )
    return fig


def make_downstream_chart(df, threshold, current_time):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Datetime"], y=df["QinSG"], name="Observed Downstream Flow", line=dict(color="black", width=2)))
    fig.add_trace(
        go.Scatter(
            x=df["Datetime"],
            y=df["Q_controlpoint"],
            name="Optimized Downstream Flow",
            line=dict(color="#7a5af8", width=2.5),
        )
    )
    if threshold is not None:
        fig.add_hline(
            y=threshold,
            line_color="#b42318",
            line_dash="dot",
            annotation_text="Downstream Threshold",
            annotation_position="top left",
        )
    fig.add_vline(x=current_time, line_color="#98a2b3", line_dash="dash")
    fig.update_layout(
        title="Downstream Control Point Hydrograph",
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(orientation="h", y=1.08),
        xaxis_title="Time",
        yaxis_title="Flow (m3/s)",
        height=360,
    )
    return fig


def render_readiness(readiness: dict[str, tuple[bool, str]]):
    st.sidebar.subheader("Artifact Readiness")
    for label, (ok, path_text) in readiness.items():
        icon = "OK" if ok else "Missing"
        st.sidebar.caption(f"{icon} {label}")
        st.sidebar.code(path_text, language=None)


def render_alerts(flags: dict[str, bool]):
    label_map = {
        "reservoir_above_pre_flood_target": "Reservoir above pre-flood target",
        "reservoir_above_normal_level": "Reservoir above normal level",
        "reservoir_above_maximum_allowable": "Reservoir above maximum allowable level",
        "downstream_above_threshold_optimized": "Optimized downstream flow above threshold",
        "downstream_above_threshold_observed": "Observed downstream flow above threshold",
    }
    active = [label_map[key] for key, value in flags.items() if value]
    if not active:
        st.success("No active threshold alerts in the selected optimized run.")
    else:
        for item in active:
            st.warning(item)


def main():
    st.title("Dakdrinh Flood Operations Demo")
    st.caption("2025 flood event playback and recommendation screen based on notebook-generated optimization outputs.")

    summary_paths = list_run_summaries()
    if not summary_paths:
        st.error("No run summary JSON found in output/notebook_exports/summaries. Run the notebook first.")
        st.stop()

    summary_options = {path.name: path for path in summary_paths}
    selected_summary_name = st.sidebar.selectbox("Run Summary", list(summary_options.keys()))
    try:
        bundle = load_dashboard_bundle(summary_options[selected_summary_name])
    except Exception as exc:
        st.error(f"Failed to load dashboard data: {exc}")
        st.info("Make sure the notebook artifacts are current and the environment includes openpyxl.")
        st.stop()

    render_readiness(bundle.readiness)

    horizons = bundle.summary.get("dashboard_defaults", {}).get("horizons_hours", [24, 48, 72])
    default_horizon = bundle.summary.get("dashboard_defaults", {}).get("default_horizon_hours", 48)
    selected_horizon = st.sidebar.radio("Decision Horizon", horizons, index=horizons.index(default_horizon) if default_horizon in horizons else 0)

    timestamps = timestamp_options(bundle.merged)
    if not timestamps:
        st.error("No aligned observed/optimized timestamps were found for the selected run.")
        st.stop()

    default_time = timestamps[0]
    current_time = st.sidebar.select_slider("Playback Time", options=timestamps, value=default_time)

    window_df = horizon_slice(bundle.merged, current_time, selected_horizon)
    if window_df.empty:
        st.error("Selected time window has no data.")
        st.stop()
    current_row = window_df.iloc[0]

    status = bundle.summary.get("status", "watch")
    st.markdown(
        f"""
        <div style="padding:0.8rem 1rem;border-radius:12px;background:{status_color(status)};color:white;font-weight:600;display:inline-block;">
            Status: {format_status(status)}
        </div>
        """,
        unsafe_allow_html=True,
    )

    top1, top2, top3, top4, top5 = st.columns(5)
    top1.metric("Playback Time", current_time.strftime("%Y-%m-%d %H:%M"))
    top2.metric("Reservoir Level", f"{current_row['WLDD']:.2f} m")
    top3.metric("Optimized Release", f"{current_row['Qoutput_Reservoir1']:.2f} m3/s")
    top4.metric("Optimized Downstream", f"{current_row['Q_controlpoint']:.2f} m3/s")
    top5.metric("End WL (Optimized)", f"{bundle.summary['reservoir']['water_level_optimized_end_m']:.2f} m")

    left, right = st.columns([1.1, 0.9])
    with left:
        st.subheader("Alerts")
        render_alerts(bundle.summary.get("threshold_flags", {}))
    with right:
        st.subheader("Recommendation")
        action, reason, tradeoff = recommendation_text(bundle.summary, current_row)
        st.info(action)
        st.write(reason)
        st.caption(tradeoff)

    chart1, chart2 = st.columns(2)
    params = bundle.parameters["values"]
    with chart1:
        st.plotly_chart(make_level_chart(window_df, params, current_time), use_container_width=True)
    with chart2:
        st.plotly_chart(make_release_chart(window_df, current_time), use_container_width=True)

    st.plotly_chart(
        make_downstream_chart(window_df, params.get("downstream_flow_threshold"), current_time),
        use_container_width=True,
    )

    st.subheader("Run Summary")
    sum1, sum2, sum3, sum4 = st.columns(4)
    sum1.metric("Observed Peak Release", f"{bundle.summary['reservoir']['release_peak_observed']['value']:.1f} m3/s")
    sum2.metric("Optimized Peak Release", f"{bundle.summary['reservoir']['release_peak_optimized']['value']:.1f} m3/s")
    sum3.metric("Observed Peak Downstream", f"{bundle.summary['control_point']['flow_peak_observed']['value']:.1f} m3/s")
    sum4.metric("Optimized Peak Downstream", f"{bundle.summary['control_point']['flow_peak_optimized']['value']:.1f} m3/s")

    st.dataframe(
        {
            "Metric": [
                "Event label",
                "Run generated at",
                "Observed end WL",
                "Optimized end WL",
                "Release peak reduction",
                "Downstream peak reduction",
            ],
            "Value": [
                bundle.summary["event_label"],
                bundle.summary.get("run_generated_at", "n/a"),
                f"{bundle.summary['reservoir']['water_level_observed_end_m']:.2f} m",
                f"{bundle.summary['reservoir']['water_level_optimized_end_m']:.2f} m",
                f"{bundle.summary['reservoir']['release_peak_reduction_percent']:.1f} %",
                f"{bundle.summary['control_point']['flow_peak_reduction_percent']:.1f} %",
            ],
        },
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Report Outputs")
    files = bundle.summary.get("files", {})
    col_a, col_b, col_c = st.columns(3)
    json_bytes = bundle.summary_path.read_bytes()
    xlsx_path = resolve_local_artifact(files.get("summary_xlsx"), bundle.summary_path, "summary_xlsx")
    png_path = resolve_local_artifact(files.get("figure_png"), bundle.summary_path, "figure_png")
    with col_a:
        st.download_button("Download Summary JSON", data=json_bytes, file_name=bundle.summary_path.name, mime="application/json")
        st.code(str(bundle.summary_path), language=None)
    with col_b:
        if xlsx_path and xlsx_path.exists():
            st.download_button("Download Summary XLSX", data=xlsx_path.read_bytes(), file_name=xlsx_path.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            st.code(str(xlsx_path), language=None)
        else:
            st.error("Summary XLSX not found.")
    with col_c:
        if png_path and png_path.exists():
            st.download_button("Download Figure PNG", data=png_path.read_bytes(), file_name=png_path.name, mime="image/png")
            st.code(str(png_path), language=None)
        else:
            st.error("Figure PNG not found.")


if __name__ == "__main__":
    main()
