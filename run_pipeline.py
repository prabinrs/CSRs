#!/usr/bin/env python3
"""
run_pipeline.py — End-to-end SDTM/ADaM pipeline execution.

Usage:
    python run_pipeline.py

Pipeline Steps:
  1. Build SDTM mapping specification (sdtm_spec.xlsx)
  2. Create SDTM DM domain from raw EDC data
  3. Derive ADaM ADSL from SDTM DM + disposition
  4. Run CDISC conformance validation on both datasets
  5. Generate demographics summary (Table 14.1.1 + figure)
"""

import os
import sys
import time

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

def banner(text: str):
    width = 70
    print(f"\n{'━' * width}")
    print(f"  {text}")
    print(f"{'━' * width}")

def main():
    start = time.time()

    banner("SDTM/ADaM PIPELINE — CDISCPILOT01")
    print(f"  Project Root: {PROJECT_ROOT}")
    print(f"  Python: {sys.version.split()[0]}")

    # ── Step 1: Build SDTM Spec ────────────────────────────────────
    banner("STEP 1 — Building SDTM Mapping Specification")
    from scripts.build_spec import build_spec
    build_spec()

    # ── Step 2: Create SDTM DM ────────────────────────────────────
    banner("STEP 2 — Creating SDTM DM Domain")
    from scripts.create_dm import create_dm, save_dm
    dm = create_dm()
    save_dm(dm)

    # ── Step 3: Derive ADaM ADSL ──────────────────────────────────
    banner("STEP 3 — Deriving ADaM ADSL")
    from scripts.create_adsl import create_adsl, save_adsl, print_traceability
    print_traceability()
    adsl = create_adsl()
    save_adsl(adsl)

    # ── Step 4: Validation ─────────────────────────────────────────
    banner("STEP 4 — CDISC Conformance Validation")
    from scripts.validate_core import (
        CDISCValidator, print_validation_report, generate_json_report
    )
    import pandas as pd

    os.makedirs(os.path.join(PROJECT_ROOT, "output"), exist_ok=True)

    dm_csv = pd.read_csv(
        os.path.join(PROJECT_ROOT, "data", "sdtm", "dm.csv"), dtype=str
    )
    validator = CDISCValidator()
    dm_findings = validator.validate_dm(dm_csv)
    dm_status = print_validation_report(dm_findings, "SDTM DM")
    generate_json_report(
        dm_findings, "DM",
        os.path.join(PROJECT_ROOT, "output", "dm_validation.json")
    )

    adsl_csv = pd.read_csv(
        os.path.join(PROJECT_ROOT, "data", "adam", "adsl.csv"), dtype=str
    )
    validator2 = CDISCValidator()
    adsl_findings = validator2.validate_adsl(adsl_csv)
    adsl_status = print_validation_report(adsl_findings, "ADaM ADSL")
    generate_json_report(
        adsl_findings, "ADSL",
        os.path.join(PROJECT_ROOT, "output", "adsl_validation.json")
    )

    # ── Step 5: Demographics Summary ──────────────────────────────
    banner("STEP 5 — Demographics Summary & Visualization")
    from scripts.demographics_summary import (
        load_adsl, generate_table_14_1_1, create_demographics_figure
    )
    adsl_viz = load_adsl()
    table = generate_table_14_1_1(adsl_viz)
    print(table)

    fig_path = os.path.join(PROJECT_ROOT, "output", "demographics_summary.png")
    create_demographics_figure(adsl_viz, fig_path)

    tbl_path = os.path.join(PROJECT_ROOT, "output", "table_14_1_1.txt")
    with open(tbl_path, "w") as f:
        f.write(table)
    print(f"[VIZ] Table 14.1.1 → {tbl_path}")

    # ── Final Summary ─────────────────────────────────────────────
    elapsed = time.time() - start
    banner("PIPELINE COMPLETE")
    print(f"""
  Outputs Generated:
    specs/sdtm_spec.xlsx           — SDTM mapping specification
    data/sdtm/dm.csv               — SDTM DM domain (CSV)
    data/sdtm/dm.xpt               — SDTM DM domain (SAS XPT v5)
    data/adam/adsl.csv              — ADaM ADSL dataset (CSV)
    data/adam/adsl.xpt              — ADaM ADSL dataset (SAS XPT v5)
    output/dm_validation.json      — DM conformance report
    output/adsl_validation.json    — ADSL conformance report
    output/demographics_summary.png — Demographics figure
    output/table_14_1_1.txt        — Table 14.1.1 text

  Validation: DM={dm_status} | ADSL={adsl_status}
  Total time: {elapsed:.1f}s
""")


if __name__ == "__main__":
    main()
