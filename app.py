"""
app.py — Clinical Data Standards Pipeline Dashboard (Streamlit)

A multi-section Streamlit application that wraps the SDTM/ADaM pipeline,
providing interactive data exploration, validation reporting, and
demographics visualization for cross-functional teams.

Usage:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
import sys
import io
import time
from datetime import datetime
from typing import Union

# ──────────────────────────────────────────────────────────────────────
# Project Path Setup
# ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from utils.cdash_utils import (
    to_iso8601, derive_age, assign_age_group,
    add_domain_keys, order_sdtm_columns, STUDYID,
    derive_safety_flag, derive_itt_flag, derive_comp_flag,
    compute_duration_days,
)
from scripts.validate_core import CDISCValidator, ValidationResult
from scripts.create_adsl import TRACEABILITY


# ──────────────────────────────────────────────────────────────────────
# Page Config & Custom CSS
# ──────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CDISCPILOT01 — Clinical Data Pipeline",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* ── Global ────────────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

    html, body, [class*="st-"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }
    code, pre, .stCode {
        font-family: 'IBM Plex Mono', monospace !important;
    }

    /* ── Sidebar ───────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0A2647 0%, #0F4C75 60%, #144272 100%);
    }
    section[data-testid="stSidebar"] * {
        color: #E8EDF2 !important;
    }
    section[data-testid="stSidebar"] .stRadio label {
        padding: 8px 12px;
        border-radius: 6px;
        transition: background 0.2s;
    }
    section[data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(255,255,255,0.08);
    }

    /* ── Metric Cards ──────────────────────────────────────────── */
    [data-testid="stMetric"] {
        background: white;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.78rem !important;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #64748B !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        color: #0F4C75 !important;
    }

    /* ── DataFrames ────────────────────────────────────────────── */
    .stDataFrame {
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        overflow: hidden;
    }

    /* ── Status badges ─────────────────────────────────────────── */
    .badge-pass {
        background: #ECFDF5; color: #065F46; padding: 4px 12px;
        border-radius: 20px; font-weight: 600; font-size: 0.82rem;
        border: 1px solid #A7F3D0; display: inline-block;
    }
    .badge-fail {
        background: #FEF2F2; color: #991B1B; padding: 4px 12px;
        border-radius: 20px; font-weight: 600; font-size: 0.82rem;
        border: 1px solid #FECACA; display: inline-block;
    }
    .badge-warn {
        background: #FFFBEB; color: #92400E; padding: 4px 12px;
        border-radius: 20px; font-weight: 600; font-size: 0.82rem;
        border: 1px solid #FDE68A; display: inline-block;
    }

    /* ── Section headers ───────────────────────────────────────── */
    .section-header {
        border-bottom: 2px solid #0F4C75;
        padding-bottom: 8px;
        margin-bottom: 20px;
    }

    /* ── Pipeline step cards ───────────────────────────────────── */
    .step-card {
        background: white;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #0F4C75;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .step-card.active {
        border-left-color: #F59E0B;
        background: #FFFBEB;
    }
    .step-card.done {
        border-left-color: #10B981;
        background: #ECFDF5;
    }

    /* ── Hide streamlit branding ───────────────────────────────── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────
# Sidebar Navigation
# ──────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 20px 0 10px 0;">
        <div style="font-size: 2.2rem;">🧬</div>
        <div style="font-size: 1.15rem; font-weight: 700; letter-spacing: 0.03em; margin-top: 6px;">
            CDISCPILOT01
        </div>
        <div style="font-size: 0.78rem; opacity: 0.7; margin-top: 2px;">
            Clinical Data Standards Pipeline
        </div>
    </div>
    <hr style="border-color: rgba(255,255,255,0.15); margin: 12px 0 20px 0;">
    """, unsafe_allow_html=True)

    page = st.radio(
        "Navigation",
        [
            "🏠  Pipeline Dashboard",
            "📊  Data Explorer",
            "🗺️  SDTM Mapping Spec",
            "✅  Validation Report",
            "👥  Demographics",
            "🔗  Traceability",
            "📤  Upload & Convert",
        ],
        label_visibility="collapsed",
    )

    st.markdown("<hr style='border-color: rgba(255,255,255,0.15); margin: 20px 0;'>", unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size: 0.72rem; opacity: 0.5; text-align: center; padding: 10px;">
        SDTM IG 3.4 · ADaM IG 1.3<br>
        Python Pipeline v1.0
    </div>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────────────────────────────
def data_path(subpath: str) -> str:
    return os.path.join(PROJECT_ROOT, subpath)


def load_if_exists(path: str) -> Union[pd.DataFrame, None]:
    full = data_path(path)
    if os.path.exists(full):
        return pd.read_csv(full)
    return None


@st.cache_data
def load_raw_enrollment():
    return load_if_exists("data/raw/enrollment.csv")

@st.cache_data
def load_raw_disposition():
    return load_if_exists("data/raw/disposition.csv")

@st.cache_data
def load_raw_vitals():
    return load_if_exists("data/raw/vitals.csv")

@st.cache_data
def load_sdtm_dm():
    return load_if_exists("data/sdtm/dm.csv")

@st.cache_data
def load_adam_adsl():
    return load_if_exists("data/adam/adsl.csv")

def load_validation_json(domain: str) -> Union[dict , None]:
    path = data_path(f"output/{domain.lower()}_validation.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def run_pipeline_step(step_name: str, func, *args):
    """Run a pipeline step with status tracking."""
    with st.spinner(f"Running {step_name}..."):
        start = time.time()
        result = func(*args)
        elapsed = time.time() - start
    return result, elapsed


# ──────────────────────────────────────────────────────────────────────
# Color Palettes
# ──────────────────────────────────────────────────────────────────────
TRT_COLORS = {
    "Placebo": "#94A3B8",
    "Xanomeline Low Dose": "#3B82F6",
    "Xanomeline High Dose": "#EF4444",
}
SEX_COLORS = {"F": "#EC4899", "M": "#3B82F6"}


# ======================================================================
# PAGE: Pipeline Dashboard
# ======================================================================
if page == "🏠  Pipeline Dashboard":
    st.markdown("# 🧬 Clinical Data Pipeline Dashboard")
    st.markdown("**Study CDISCPILOT01** — End-to-end SDTM/ADaM conversion with CDISC conformance validation")

    st.markdown("---")

    # Check current state
    has_raw = os.path.exists(data_path("data/raw/enrollment.csv"))
    has_sdtm = os.path.exists(data_path("data/sdtm/dm.csv"))
    has_adam = os.path.exists(data_path("data/adam/adsl.csv"))
    has_val = os.path.exists(data_path("output/dm_validation.json"))
    has_viz = os.path.exists(data_path("output/demographics_summary.png"))

    # Status metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Raw Data", "✓ Ready" if has_raw else "✗ Missing")
    col2.metric("SDTM DM", "✓ Built" if has_sdtm else "— Pending")
    col3.metric("ADaM ADSL", "✓ Built" if has_adam else "— Pending")
    col4.metric("Validation", "✓ Done" if has_val else "— Pending")
    col5.metric("Visuals", "✓ Done" if has_viz else "— Pending")

    st.markdown("---")

    # Pipeline execution
    st.subheader("Run Pipeline")

    col_run, col_info = st.columns([1, 2])

    with col_run:
        run_all = st.button("▶  Run Full Pipeline", type="primary", use_container_width=True)
        st.caption("Executes all 5 steps sequentially")

    with col_info:
        st.markdown("""
        | Step | Description | Output |
        |------|-------------|--------|
        | 1 | Build SDTM mapping spec | `specs/sdtm_spec.xlsx` |
        | 2 | Create SDTM DM domain | `data/sdtm/dm.csv` + `.xpt` |
        | 3 | Derive ADaM ADSL | `data/adam/adsl.csv` + `.xpt` |
        | 4 | CDISC conformance checks | `output/*_validation.json` |
        | 5 | Demographics summary | `output/demographics_summary.png` |
        """)

    if run_all:
        log_area = st.empty()
        progress = st.progress(0, text="Initializing pipeline...")

        captured = io.StringIO()
        old_stdout = sys.stdout

        # Step 1: Spec
        progress.progress(10, text="Step 1/5 — Building SDTM specification...")
        from scripts.build_spec import build_spec
        build_spec()
        st.toast("✓ SDTM spec built", icon="📋")

        # Step 2: DM
        progress.progress(30, text="Step 2/5 — Creating SDTM DM domain...")
        from scripts.create_dm import create_dm, save_dm
        dm = create_dm()
        save_dm(dm)
        st.toast("✓ SDTM DM created", icon="📊")

        # Step 3: ADSL
        progress.progress(50, text="Step 3/5 — Deriving ADaM ADSL...")
        from scripts.create_adsl import create_adsl, save_adsl
        adsl = create_adsl()
        save_adsl(adsl)
        st.toast("✓ ADaM ADSL derived", icon="📈")

        # Step 4: Validate
        progress.progress(70, text="Step 4/5 — Running CDISC validation...")
        from scripts.validate_core import (
            CDISCValidator, print_validation_report, generate_json_report
        )
        os.makedirs(data_path("output"), exist_ok=True)

        dm_csv = pd.read_csv(data_path("data/sdtm/dm.csv"), dtype=str)
        v1 = CDISCValidator()
        dm_findings = v1.validate_dm(dm_csv)
        generate_json_report(dm_findings, "DM", data_path("output/dm_validation.json"))

        adsl_csv = pd.read_csv(data_path("data/adam/adsl.csv"), dtype=str)
        v2 = CDISCValidator()
        adsl_findings = v2.validate_adsl(adsl_csv)
        generate_json_report(adsl_findings, "ADSL", data_path("output/adsl_validation.json"))
        st.toast("✓ Validation complete", icon="✅")

        # Step 5: Visualization
        progress.progress(90, text="Step 5/5 — Generating demographics summary...")
        from scripts.demographics_summary import load_adsl as load_adsl_viz, generate_table_14_1_1, create_demographics_figure
        adsl_v = load_adsl_viz()
        create_demographics_figure(adsl_v, data_path("output/demographics_summary.png"))
        table_txt = generate_table_14_1_1(adsl_v)
        with open(data_path("output/table_14_1_1.txt"), "w") as f:
            f.write(table_txt)
        st.toast("✓ Visualizations generated", icon="👥")

        progress.progress(100, text="Pipeline complete!")
        st.cache_data.clear()

        st.success("Pipeline executed successfully — all 5 steps complete. Navigate using the sidebar to explore results.")

    # File inventory
    if has_sdtm or has_adam:
        st.markdown("---")
        st.subheader("Output Inventory")

        files = []
        for root, dirs, filenames in os.walk(data_path("")):
            for fn in filenames:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, data_path(""))
                if rel.startswith(("data/sdtm", "data/adam", "output", "specs")):
                    size = os.path.getsize(full)
                    files.append({
                        "File": rel,
                        "Size": f"{size/1024:.1f} KB",
                        "Modified": datetime.fromtimestamp(os.path.getmtime(full)).strftime("%Y-%m-%d %H:%M"),
                    })
        if files:
            st.dataframe(pd.DataFrame(files), use_container_width=True, hide_index=True)


# ======================================================================
# PAGE: Data Explorer
# ======================================================================
elif page == "📊  Data Explorer":
    st.markdown("# 📊 Data Explorer")
    st.markdown("Browse and compare datasets at each pipeline stage: **Raw → SDTM → ADaM**")

    tab_raw, tab_sdtm, tab_adam = st.tabs(["📁 Raw EDC Data", "🔄 SDTM DM", "📈 ADaM ADSL"])

    # ── Raw Data ───────────────────────────────────────────────────
    with tab_raw:
        raw_choice = st.selectbox("Select raw dataset:", ["enrollment.csv", "disposition.csv", "vitals.csv"])
        df = load_if_exists(f"data/raw/{raw_choice}")
        if df is not None:
            c1, c2, c3 = st.columns(3)
            c1.metric("Rows", len(df))
            c2.metric("Columns", len(df.columns))
            c3.metric("Subjects", df["SUBJID"].nunique() if "SUBJID" in df.columns else "N/A")

            with st.expander("Column Details", expanded=False):
                col_info = pd.DataFrame({
                    "Column": df.columns,
                    "Non-Null": df.notna().sum().values,
                    "Null": df.isna().sum().values,
                    "Unique": df.nunique().values,
                    "Sample": [str(df[c].dropna().iloc[0]) if df[c].notna().any() else "" for c in df.columns],
                })
                st.dataframe(col_info, use_container_width=True, hide_index=True)

            st.dataframe(df, use_container_width=True, height=400)
        else:
            st.warning("Raw data not found. Run the pipeline first.")

    # ── SDTM DM ───────────────────────────────────────────────────
    with tab_sdtm:
        dm = load_sdtm_dm()
        if dm is not None:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Subjects", dm["USUBJID"].nunique())
            c2.metric("Sites", dm["SITEID"].nunique())
            c3.metric("Variables", len(dm.columns))
            c4.metric("Domain", "DM")

            # Filters
            st.markdown("**Filters**")
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                sel_site = st.multiselect("Site", sorted(dm["SITEID"].unique()), default=sorted(dm["SITEID"].unique()))
            with fc2:
                sel_arm = st.multiselect("Arm", sorted(dm["ARM"].unique()), default=sorted(dm["ARM"].unique()))
            with fc3:
                sel_sex = st.multiselect("Sex", sorted(dm["SEX"].unique()), default=sorted(dm["SEX"].unique()))

            filtered = dm[dm["SITEID"].isin(sel_site) & dm["ARM"].isin(sel_arm) & dm["SEX"].isin(sel_sex)]
            st.markdown(f"*Showing {len(filtered)} of {len(dm)} subjects*")
            st.dataframe(filtered, use_container_width=True, height=400)

            # Download
            csv_buf = filtered.to_csv(index=False)
            st.download_button("⬇ Download filtered DM (CSV)", csv_buf, "dm_filtered.csv", "text/csv")
        else:
            st.info("SDTM DM not yet created. Run the pipeline from the Dashboard.")

    # ── ADaM ADSL ──────────────────────────────────────────────────
    with tab_adam:
        adsl = load_adam_adsl()
        if adsl is not None:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Subjects", adsl["USUBJID"].nunique())
            c2.metric("Safety Pop", (adsl["SAFFL"] == "Y").sum())
            c3.metric("Completers", (adsl["COMPLFL"] == "Y").sum())
            c4.metric("Variables", len(adsl.columns))

            # Population filter
            pop = st.radio("Population:", ["All Subjects", "Safety (SAFFL=Y)", "ITT (ITTFL=Y)", "Completers (COMPLFL=Y)"], horizontal=True)
            filtered = adsl.copy()
            if pop == "Safety (SAFFL=Y)":
                filtered = filtered[filtered["SAFFL"] == "Y"]
            elif pop == "ITT (ITTFL=Y)":
                filtered = filtered[filtered["ITTFL"] == "Y"]
            elif pop == "Completers (COMPLFL=Y)":
                filtered = filtered[filtered["COMPLFL"] == "Y"]

            st.dataframe(filtered, use_container_width=True, height=400)

            csv_buf = filtered.to_csv(index=False)
            st.download_button("⬇ Download ADSL (CSV)", csv_buf, "adsl.csv", "text/csv")
        else:
            st.info("ADaM ADSL not yet derived. Run the pipeline from the Dashboard.")


# ======================================================================
# PAGE: SDTM Mapping Spec
# ======================================================================
elif page == "🗺️  SDTM Mapping Spec":
    st.markdown("# 🗺️ SDTM Mapping Specification")
    st.markdown("Source-to-target mapping for the **DM (Demographics)** domain — SDTM IG 3.4")

    # Inline spec data
    spec_rows = [
        {"SDTM Variable": "STUDYID", "Label": "Study Identifier", "Type": "Char",
         "Source": "Assigned", "Raw Variable": "N/A", "Derivation": "Hardcoded: 'CDISCPILOT01'", "CT": ""},
        {"SDTM Variable": "DOMAIN", "Label": "Domain Abbreviation", "Type": "Char",
         "Source": "Assigned", "Raw Variable": "N/A", "Derivation": "Hardcoded: 'DM'", "CT": ""},
        {"SDTM Variable": "USUBJID", "Label": "Unique Subject Identifier", "Type": "Char",
         "Source": "enrollment.csv", "Raw Variable": "STUDYID + SUBJID",
         "Derivation": "STUDYID || '-' || SUBJID", "CT": ""},
        {"SDTM Variable": "SUBJID", "Label": "Subject Identifier", "Type": "Char",
         "Source": "enrollment.csv", "Raw Variable": "SUBJID", "Derivation": "Direct mapping", "CT": ""},
        {"SDTM Variable": "SITEID", "Label": "Study Site Identifier", "Type": "Char",
         "Source": "enrollment.csv", "Raw Variable": "SITEID", "Derivation": "Direct mapping", "CT": ""},
        {"SDTM Variable": "BRTHDTC", "Label": "Date/Time of Birth", "Type": "Char",
         "Source": "enrollment.csv", "Raw Variable": "BRTHDT",
         "Derivation": "Convert to ISO 8601 (YYYY-MM-DD)", "CT": ""},
        {"SDTM Variable": "AGE", "Label": "Age", "Type": "Num",
         "Source": "Derived", "Raw Variable": "BRTHDTC, RFSTDTC",
         "Derivation": "floor((RFSTDTC − BRTHDTC) / 365.25)", "CT": ""},
        {"SDTM Variable": "AGEU", "Label": "Age Units", "Type": "Char",
         "Source": "Assigned", "Raw Variable": "N/A", "Derivation": "Hardcoded: 'YEARS'", "CT": "AGEU"},
        {"SDTM Variable": "AGEGR1", "Label": "Pooled Age Group 1", "Type": "Char",
         "Source": "Derived", "Raw Variable": "AGE",
         "Derivation": "<65 → '<65'; 65–80 → '65-80'; >80 → '>80'", "CT": ""},
        {"SDTM Variable": "SEX", "Label": "Sex", "Type": "Char",
         "Source": "enrollment.csv", "Raw Variable": "SEX", "Derivation": "Direct mapping", "CT": "SEX"},
        {"SDTM Variable": "RACE", "Label": "Race", "Type": "Char",
         "Source": "enrollment.csv", "Raw Variable": "RACE", "Derivation": "Direct mapping", "CT": "RACE"},
        {"SDTM Variable": "ETHNIC", "Label": "Ethnicity", "Type": "Char",
         "Source": "enrollment.csv", "Raw Variable": "ETHNIC", "Derivation": "Direct mapping", "CT": "ETHNIC"},
        {"SDTM Variable": "COUNTRY", "Label": "Country", "Type": "Char",
         "Source": "enrollment.csv", "Raw Variable": "COUNTRY", "Derivation": "Direct mapping", "CT": "COUNTRY"},
        {"SDTM Variable": "RFSTDTC", "Label": "Reference Start Date/Time", "Type": "Char",
         "Source": "enrollment.csv", "Raw Variable": "RFSTDTC", "Derivation": "Convert to ISO 8601", "CT": ""},
        {"SDTM Variable": "RFENDTC", "Label": "Reference End Date/Time", "Type": "Char",
         "Source": "enrollment.csv", "Raw Variable": "RFENDTC", "Derivation": "Convert to ISO 8601", "CT": ""},
        {"SDTM Variable": "ARMCD", "Label": "Planned Arm Code", "Type": "Char",
         "Source": "enrollment.csv", "Raw Variable": "ARMCD", "Derivation": "Direct mapping", "CT": ""},
        {"SDTM Variable": "ARM", "Label": "Description of Planned Arm", "Type": "Char",
         "Source": "enrollment.csv", "Raw Variable": "ARM", "Derivation": "Direct mapping", "CT": ""},
    ]
    spec_df = pd.DataFrame(spec_rows)

    # Filters
    fc1, fc2 = st.columns(2)
    with fc1:
        type_filter = st.multiselect("Filter by Type:", ["Char", "Num"], default=["Char", "Num"])
    with fc2:
        source_filter = st.multiselect("Filter by Source:", spec_df["Source"].unique().tolist(),
                                        default=spec_df["Source"].unique().tolist())

    filtered = spec_df[spec_df["Type"].isin(type_filter) & spec_df["Source"].isin(source_filter)]

    def highlight_type(row):
        if row["Type"] == "Num":
            return ["color: #2563EB; font-weight: 600"] * len(row)
        return [""] * len(row)

    st.dataframe(
        filtered.style.apply(highlight_type, axis=1),
        use_container_width=True,
        height=500,
        hide_index=True,
    )

    # Mapping flow diagram
    st.markdown("---")
    st.subheader("Mapping Flow: Raw → SDTM DM")
    st.markdown("""
    ```
    enrollment.csv                        SDTM DM Domain
    ┌──────────────────┐                  ┌──────────────────────────────┐
    │ SUBJID           │──── direct ────→ │ SUBJID                       │
    │ SITEID           │──── direct ────→ │ SITEID                       │
    │ BRTHDT           │──── ISO8601 ───→ │ BRTHDTC                      │
    │ RFSTDTC          │──── ISO8601 ───→ │ RFSTDTC                      │
    │ SEX, RACE        │──── direct ────→ │ SEX, RACE (+ CT validation)  │
    │ ARMCD, ARM       │──── direct ────→ │ ARMCD, ARM                   │
    └──────────────────┘                  │                              │
                                          │ STUDYID    ← hardcoded      │
                                          │ DOMAIN     ← 'DM'           │
                                          │ USUBJID    ← STUDYID+SUBJID │
                                          │ AGE, AGEU  ← derived        │
                                          │ AGEGR1     ← derived        │
                                          └──────────────────────────────┘
    ```
    """)

    # Download spec
    spec_path = data_path("specs/sdtm_spec.xlsx")
    if os.path.exists(spec_path):
        with open(spec_path, "rb") as f:
            st.download_button("⬇ Download sdtm_spec.xlsx", f, "sdtm_spec.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ======================================================================
# PAGE: Validation Report
# ======================================================================
elif page == "✅  Validation Report":
    st.markdown("# ✅ CDISC Conformance Validation Report")

    tab_dm, tab_adsl, tab_live = st.tabs(["SDTM DM", "ADaM ADSL", "🔄 Run Live Validation"])

    for tab, domain, domain_label in [(tab_dm, "dm", "SDTM DM"), (tab_adsl, "adsl", "ADaM ADSL")]:
        with tab:
            report = load_validation_json(domain)
            if report is None:
                st.info(f"No validation report found for {domain_label}. Run the pipeline first.")
                continue

            # Summary header
            errors = report["summary"]["errors"]
            warnings = report["summary"]["warnings"]
            passed = report["summary"]["passed"]
            total = errors + warnings + passed

            if errors > 0:
                st.markdown(f'<span class="badge-fail">FAIL — {errors} error(s)</span>', unsafe_allow_html=True)
            elif warnings > 0:
                st.markdown(f'<span class="badge-warn">REVIEW — {warnings} warning(s)</span>', unsafe_allow_html=True)
            else:
                st.markdown(f'<span class="badge-pass">PASS — all {passed} checks passed</span>', unsafe_allow_html=True)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Checks", total)
            c2.metric("Errors", errors)
            c3.metric("Warnings", warnings)
            c4.metric("Passed", passed)

            # Findings gauge
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=passed,
                title={"text": f"{domain_label} — Checks Passed"},
                gauge={
                    "axis": {"range": [0, total]},
                    "bar": {"color": "#10B981"},
                    "steps": [
                        {"range": [0, total * 0.5], "color": "#FEE2E2"},
                        {"range": [total * 0.5, total * 0.8], "color": "#FEF3C7"},
                        {"range": [total * 0.8, total], "color": "#D1FAE5"},
                    ],
                    "threshold": {"line": {"color": "#064E3B", "width": 3}, "value": passed},
                },
            ))
            fig_gauge.update_layout(height=250, margin=dict(t=60, b=20, l=30, r=30))
            st.plotly_chart(fig_gauge, use_container_width=True)

            # Detailed findings
            st.subheader("Detailed Findings")
            findings_df = pd.DataFrame(report["findings"])
            findings_df["icon"] = findings_df["severity"].map({"ERROR": "🔴", "WARNING": "🟡", "NOTE": "🟢"})
            findings_df = findings_df[["icon", "rule_id", "severity", "variable", "message", "affected_records"]]
            findings_df.columns = ["", "Rule ID", "Severity", "Variable", "Message", "Affected"]
            st.dataframe(findings_df, use_container_width=True, hide_index=True, height=400)

    # Live validation tab
    with tab_live:
        st.markdown("Re-run validation on the current datasets with real-time output.")

        run_val = st.button("🔄 Run Validation Now", type="primary")
        if run_val:
            dm = load_sdtm_dm()
            adsl = load_adam_adsl()

            if dm is not None:
                st.markdown("### SDTM DM Validation")
                validator = CDISCValidator()
                findings = validator.validate_dm(dm.astype(str))
                for f in findings:
                    icon = {"ERROR": "🔴", "WARNING": "🟡", "NOTE": "🟢"}[f.severity]
                    st.markdown(f"{icon} **[{f.rule_id}]** {f.message}")
                generate_json_report(findings, "DM", data_path("output/dm_validation.json"))

            if adsl is not None:
                st.markdown("### ADaM ADSL Validation")
                validator2 = CDISCValidator()
                findings2 = validator2.validate_adsl(adsl.astype(str))
                for f in findings2:
                    icon = {"ERROR": "🔴", "WARNING": "🟡", "NOTE": "🟢"}[f.severity]
                    st.markdown(f"{icon} **[{f.rule_id}]** {f.message}")
                generate_json_report(findings2, "ADSL", data_path("output/adsl_validation.json"))

            st.success("Validation reports updated.")


# ======================================================================
# PAGE: Demographics
# ======================================================================
elif page == "👥  Demographics":
    st.markdown("# 👥 Demographics Summary")

    adsl = load_adam_adsl()
    if adsl is None:
        st.info("ADaM ADSL not yet available. Run the pipeline from the Dashboard.")
    else:
        adsl["AGE"] = pd.to_numeric(adsl["AGE"], errors="coerce")
        adsl["TRTDURD"] = pd.to_numeric(adsl["TRTDURD"], errors="coerce")

        # Population selector
        pop = st.radio("Population:", ["Safety (SAFFL=Y)", "ITT (ITTFL=Y)", "All Subjects"], horizontal=True)
        if pop == "Safety (SAFFL=Y)":
            df = adsl[adsl["SAFFL"] == "Y"].copy()
        elif pop == "ITT (ITTFL=Y)":
            df = adsl[adsl["ITTFL"] == "Y"].copy()
        else:
            df = adsl.copy()

        st.markdown(f"*{len(df)} subjects in selected population*")
        st.markdown("---")

        # ── Interactive Charts ─────────────────────────────────────
        col1, col2 = st.columns(2)

        with col1:
            # Age distribution
            fig_age = px.box(
                df, x="TRT01A", y="AGE", color="TRT01A",
                color_discrete_map=TRT_COLORS,
                title="Age Distribution by Treatment Arm",
                labels={"TRT01A": "Treatment", "AGE": "Age (years)"},
                points="all",
            )
            fig_age.update_layout(showlegend=False, height=400)
            st.plotly_chart(fig_age, use_container_width=True)

        with col2:
            # Sex distribution
            sex_ct = df.groupby(["TRT01A", "SEX"]).size().reset_index(name="count")
            fig_sex = px.bar(
                sex_ct, x="TRT01A", y="count", color="SEX",
                color_discrete_map=SEX_COLORS,
                barmode="group",
                title="Sex Distribution by Treatment Arm",
                labels={"TRT01A": "Treatment", "count": "Subjects", "SEX": "Sex"},
            )
            fig_sex.update_layout(height=400)
            st.plotly_chart(fig_sex, use_container_width=True)

        col3, col4 = st.columns(2)

        with col3:
            # Race sunburst
            race_ct = df.groupby(["TRT01A", "RACE"]).size().reset_index(name="count")
            fig_race = px.sunburst(
                race_ct, path=["TRT01A", "RACE"], values="count",
                title="Race Distribution (Sunburst)",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig_race.update_layout(height=450)
            st.plotly_chart(fig_race, use_container_width=True)

        with col4:
            # Treatment duration
            fig_dur = px.violin(
                df, x="TRT01A", y="TRTDURD", color="TRT01A",
                color_discrete_map=TRT_COLORS, box=True, points="all",
                title="Treatment Duration by Arm",
                labels={"TRT01A": "Treatment", "TRTDURD": "Duration (days)"},
            )
            fig_dur.update_layout(showlegend=False, height=450)
            st.plotly_chart(fig_dur, use_container_width=True)

        # ── Completion status ──────────────────────────────────────
        st.markdown("---")
        st.subheader("Study Completion")
        comp_ct = df.groupby(["TRT01A", "COMPLFL"]).size().reset_index(name="count")
        comp_ct["Status"] = comp_ct["COMPLFL"].map({"Y": "Completed", "N": "Discontinued"})
        fig_comp = px.bar(
            comp_ct, x="TRT01A", y="count", color="Status",
            color_discrete_map={"Completed": "#10B981", "Discontinued": "#EF4444"},
            barmode="stack",
            labels={"TRT01A": "Treatment", "count": "Subjects"},
        )
        fig_comp.update_layout(height=350)
        st.plotly_chart(fig_comp, use_container_width=True)

        # ── Discontinuation reasons ────────────────────────────────
        disc = df[df["COMPLFL"] == "N"]
        if len(disc) > 0:
            st.subheader("Discontinuation Reasons")
            disc_ct = disc.groupby(["TRT01A", "DCDECOD"]).size().reset_index(name="count")
            fig_disc = px.bar(
                disc_ct, x="count", y="DCDECOD", color="TRT01A",
                color_discrete_map=TRT_COLORS,
                orientation="h",
                labels={"DCDECOD": "Reason", "count": "Subjects", "TRT01A": "Treatment"},
            )
            fig_disc.update_layout(height=300)
            st.plotly_chart(fig_disc, use_container_width=True)

        # ── Table 14.1.1 ──────────────────────────────────────────
        st.markdown("---")
        st.subheader("Table 14.1.1 — Demographics Summary (Text)")
        tbl_path = data_path("output/table_14_1_1.txt")
        if os.path.exists(tbl_path):
            with open(tbl_path) as f:
                st.code(f.read(), language=None)
        else:
            st.info("Run the pipeline to generate the formatted table.")


# ======================================================================
# PAGE: Traceability
# ======================================================================
elif page == "🔗  Traceability":
    st.markdown("# 🔗 Variable Traceability")
    st.markdown("Trace every ADaM ADSL variable back to its SDTM source — a core requirement for regulatory review.")

    # Traceability table
    trace_df = pd.DataFrame([
        {"ADaM Variable": var, "SDTM Source": info["source"], "Derivation": info["derivation"]}
        for var, info in TRACEABILITY.items()
    ])

    # Search / filter
    search = st.text_input("🔍 Search variables:", placeholder="e.g., AGE, SAFFL, TRT01P...")
    if search:
        mask = trace_df.apply(lambda r: search.upper() in r.str.upper().str.cat(sep=" "), axis=1)
        trace_df = trace_df[mask]

    st.dataframe(trace_df, use_container_width=True, hide_index=True, height=500)

    # Interactive single-variable trace
    st.markdown("---")
    st.subheader("Deep Trace — Single Variable")

    sel_var = st.selectbox("Select ADaM variable:", list(TRACEABILITY.keys()))

    if sel_var:
        info = TRACEABILITY[sel_var]
        st.markdown(f"""
        <div style="background: white; border: 1px solid #E2E8F0; border-radius: 10px; padding: 24px; margin: 16px 0;">
            <div style="font-size: 1.4rem; font-weight: 700; color: #0F4C75;">{sel_var}</div>
            <div style="margin-top: 16px;">
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                    <span style="background: #EEF2FF; color: #3730A3; padding: 4px 10px; border-radius: 6px; font-size: 0.8rem; font-weight: 600;">SOURCE</span>
                    <span style="font-weight: 500;">{info['source']}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="background: #FEF3C7; color: #92400E; padding: 4px 10px; border-radius: 6px; font-size: 0.8rem; font-weight: 600;">DERIVATION</span>
                    <span style="font-weight: 500;">{info['derivation']}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Show actual data flow
        dm = load_sdtm_dm()
        adsl = load_adam_adsl()
        if dm is not None and adsl is not None and sel_var in adsl.columns:
            st.markdown("**Sample data flow** (first 5 subjects):")
            sample = adsl[["USUBJID", sel_var]].head(5)

            # Find the SDTM source column
            source_col = info["source"].replace("DM.", "").replace("DS.", "").split(",")[0].strip()
            if source_col in dm.columns:
                dm_sample = dm[["USUBJID", source_col]].head(5)
                merged = dm_sample.merge(sample, on="USUBJID", suffixes=("_SDTM", "_ADaM"))
                st.dataframe(merged, use_container_width=True, hide_index=True)


# ======================================================================
# PAGE: Upload & Convert
# ======================================================================
elif page == "📤  Upload & Convert":
    st.markdown("# 📤 Upload & Convert Your Data")
    st.markdown("Upload your own raw EDC data and run the SDTM/ADaM conversion pipeline.")

    st.warning("⚠️ **This feature processes data locally.** No data is sent to external servers.")

    st.markdown("---")

    st.subheader("Required File Format")
    st.markdown("""
    Upload a **CSV** file with the following columns (matching the enrollment schema):

    `SUBJID, SITEID, ENRDT, BRTHDT, SEX, RACE, ETHNIC, COUNTRY, ARMCD, ARM, RFSTDTC, RFENDTC`
    """)

    with st.expander("View sample data format"):
        sample = load_raw_enrollment()
        if sample is not None:
            st.dataframe(sample.head(3), use_container_width=True, hide_index=True)

    st.markdown("---")

    uploaded = st.file_uploader("Upload enrollment CSV", type=["csv"], accept_multiple_files=False)

    if uploaded is not None:
        try:
            user_df = pd.read_csv(uploaded, dtype=str)
            st.success(f"Loaded {len(user_df)} rows × {len(user_df.columns)} columns")
            st.dataframe(user_df.head(10), use_container_width=True, height=300)

            # Validate required columns
            required = {"SUBJID", "SITEID", "BRTHDT", "SEX", "RACE", "ARMCD", "ARM", "RFSTDTC", "RFENDTC"}
            missing = required - set(user_df.columns)
            if missing:
                st.error(f"Missing required columns: {missing}")
            else:
                st.markdown("✓ All required columns present")

                if st.button("🚀 Run SDTM DM Conversion", type="primary"):
                    with st.spinner("Converting to SDTM DM..."):
                        # Save temp
                        temp_path = data_path("data/raw/_user_upload.csv")
                        user_df.to_csv(temp_path, index=False)

                        from scripts.create_dm import create_dm
                        dm_result = create_dm(raw_path=temp_path)

                        st.success(f"SDTM DM created — {len(dm_result)} subjects")
                        st.dataframe(dm_result, use_container_width=True, height=400)

                        # Run validation
                        validator = CDISCValidator()
                        findings = validator.validate_dm(dm_result.astype(str))
                        errors = [f for f in findings if f.severity == "ERROR"]
                        if errors:
                            st.error(f"{len(errors)} validation error(s) found:")
                            for f in errors:
                                st.markdown(f"🔴 **[{f.rule_id}]** {f.message}")
                        else:
                            st.success("All CDISC validation checks passed ✓")

                        # Download
                        csv_buf = dm_result.to_csv(index=False)
                        st.download_button("⬇ Download SDTM DM (CSV)", csv_buf, "dm_user.csv", "text/csv")

                        os.remove(temp_path)

        except Exception as e:
            st.error(f"Error reading file: {e}")

    st.markdown("---")
    st.markdown("""
    <div style="background: #F0F9FF; border: 1px solid #BAE6FD; border-radius: 8px; padding: 16px; font-size: 0.88rem;">
        <strong>💡 Extending to other domains:</strong> This pipeline currently handles DM (Demographics) and ADSL (Subject-Level).
        The same pattern applies to AE, VS, LB, and other SDTM/ADaM domains — create a mapping spec,
        write the transformation script, and add validation rules.
    </div>
    """, unsafe_allow_html=True)
