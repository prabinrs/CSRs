"""
create_ds.py — Generate SDTM DS (Disposition) domain from raw EDC data.

Reads: data/raw/disposition.csv
Output: data/sdtm/ds.csv, data/sdtm/ds.xpt
"""

import sys
import os
import pandas as pd
import pyreadstat

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.cdash_utils import (
    to_iso8601, add_domain_keys, order_sdtm_columns, validate_iso_dates
)

DOMAIN_DS = "DS"

def create_ds(raw_path: str = None) -> pd.DataFrame:
    """
    Transform raw disposition data into SDTM DS domain.
    """
    if raw_path is None:
        raw_path = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "disposition.csv")

    print(f"[DS] Reading raw disposition data: {raw_path}")
    raw = pd.read_csv(raw_path, dtype=str)
    print(f"[DS] Loaded {len(raw)} records from raw data")

    # ── Step 1: Add domain identifiers ─────────────────────────────
    ds = add_domain_keys(raw, domain=DOMAIN_DS)

    # ── Step 2: Convert dates to ISO 8601 ──────────────────────────
    if "DSSTDTC" in ds.columns:
        ds["DSSTDTC"] = ds["DSSTDTC"].apply(to_iso8601)

    # ── Step 3: Derive sequence number ─────────────────────────────
    # Assuming chronological order, cumcount provides 1-based index (with +1)
    ds["DSSEQ"] = ds.groupby("USUBJID").cumcount() + 1

    # ── Step 4: Map standard variables ─────────────────────────────
    # (DSTERM, DSDECOD, DSCAT are assumed to be present in raw disposition.csv)
    
    # ── Step 5: Order columns per SDTM DS specification ────────────
    ds_vars = [
        "STUDYID", "DOMAIN", "USUBJID", "SUBJID", "DSSEQ",
        "DSTERM", "DSDECOD", "DSCAT", "DSSTDTC"
    ]
    ds = order_sdtm_columns(ds, ds_vars)
    # Keep only SDTM variables
    ds = ds[[c for c in ds_vars if c in ds.columns]]

    # ── Step 6: Validate dates ─────────────────────────────────────
    date_cols = ["DSSTDTC"]
    issues = validate_iso_dates(ds, date_cols)
    if issues:
        print(f"[DS] WARNING — ISO 8601 validation issues: {issues}")
    else:
        print("[DS] All dates pass ISO 8601 validation ✓")

    # ── Print summary ──────────────────────────────────────────────
    print(f"\n[DS] === SDTM DS Domain Summary ===")
    print(f"  Subjects:     {ds['USUBJID'].nunique()}")
    print(f"  Categories:   {ds['DSCAT'].value_counts().to_dict()}")
    print(f"  Events:       {ds['DSDECOD'].value_counts().to_dict()}")
    print(f"  Variables:    {list(ds.columns)}")
    print(f"  Dimensions:   {ds.shape}")

    return ds


def save_ds(ds: pd.DataFrame, output_dir: str = None):
    """Save DS as both CSV and XPT (SAS transport v5)."""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sdtm")
    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, "ds.csv")
    xpt_path = os.path.join(output_dir, "ds.xpt")

    ds.to_csv(csv_path, index=False)
    print(f"[DS] Saved CSV  → {csv_path}")

    # Save as SAS XPORT v5 using pyreadstat
    ds_xpt = ds.copy()
    ds_xpt["DSSEQ"] = pd.to_numeric(ds_xpt["DSSEQ"], errors="coerce")
    column_labels = {
        "STUDYID": "Study Identifier",
        "DOMAIN": "Domain Abbreviation",
        "USUBJID": "Unique Subject Identifier",
        "SUBJID": "Subject Identifier for the Study",
        "DSSEQ": "Sequence Number",
        "DSTERM": "Reported Term for the Disposition Event",
        "DSDECOD": "Standardized Disposition Term",
        "DSCAT": "Category for Disposition Event",
        "DSSTDTC": "Start Date/Time of Disposition Event",
    }
    labels = [column_labels.get(c, c) for c in ds_xpt.columns]

    try:
        pyreadstat.write_xport(
            ds_xpt, xpt_path,
            file_label="SDTM DS Domain",
            column_labels=labels,
            table_name="DS"
        )
        print(f"[DS] Saved XPT  → {xpt_path}")
    except Exception as e:
        print(f"[DS] XPT write warning: {e}")
        print(f"[DS] CSV output is available at {csv_path}")


# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ds = create_ds()
    save_ds(ds)
    print("\n[DS] ✓ DS domain creation complete.")
