"""
create_adds.py — Generate ADaM ADDS (Disposition Analysis Dataset).

Reads:  data/sdtm/ds.csv, data/adam/adsl.csv
Output: data/adam/adds.csv, data/adam/adds.xpt

ADaM IG v1.3 — ADDS
Key derivations:
  1. PARAMCD/PARAM definition for Disposition
  2. AVAL / AVALC assignment
"""

import sys
import os
import pandas as pd
import pyreadstat

def create_adds(adsl_path: str = None, ds_path: str = None) -> pd.DataFrame:
    """
    Derive ADaM ADDS from SDTM DS and ADaM ADSL.
    """
    if adsl_path is None:
        adsl_path = os.path.join(os.path.dirname(__file__), "..", "data", "adam", "adsl.csv")
    if ds_path is None:
        ds_path = os.path.join(os.path.dirname(__file__), "..", "data", "sdtm", "ds.csv")

    print(f"[ADDS] Reading ADaM ADSL: {adsl_path}")
    adsl = pd.read_csv(adsl_path, dtype=str)

    print(f"[ADDS] Reading SDTM DS: {ds_path}")
    ds = pd.read_csv(ds_path, dtype=str)

    # ── Step 1: Merge ADSL with DS ─────────────────────────────────
    # We want to keep all ADSL subjects, but disposition is an event,
    # so we do an inner merge or left merge. usually disposition is one per subject.
    adds = adsl.merge(
        ds[["USUBJID", "DSSEQ", "DSTERM", "DSDECOD", "DSCAT", "DSSTDTC"]],
        on="USUBJID", how="left"
    )
    print(f"[ADDS] Merged ADSL + DS → {len(adds)} records")

    # ── Step 2: Derive Parameters (PARAMCD/PARAM) ──────────────────
    adds["PARAMCD"] = "DISP"
    adds["PARAM"] = "Subject Disposition"

    # ── Step 3: Derive Analysis Values (AVAL/AVALC) ────────────────
    adds["AVALC"] = adds["DSDECOD"]
    
    # Simple mapping for AVAL
    val_map = {
        "COMPLETED": 1,
        "ADVERSE EVENT": 2,
        "WITHDRAWAL BY SUBJECT": 3,
        "LOST TO FOLLOW-UP": 4
    }
    adds["AVAL"] = adds["AVALC"].map(val_map)

    # AVAL becomes 99 if missing or mapped unknown
    adds["AVAL"] = adds["AVAL"].fillna(99).astype(int)

    # ── Step 4: Select and order ADDS variables ────────────────────
    adsl_vars = list(adsl.columns)
    
    adds_vars = [
        "STUDYID", "USUBJID", "SUBJID", "SITEID",
        "AGE", "AGEGR1", "SEX", "RACE",
        "TRT01P", "TRT01A", "TRT01PN", "TRT01AN",
        "SAFFL", "ITTFL", "COMPLFL",
        "DSSEQ", "PARAMCD", "PARAM", "AVAL", "AVALC",
        "DSTERM", "DSDECOD", "DSCAT", "DSSTDTC"
    ]
    
    # Ensure all wanted vars exist and order them
    adds = adds[[c for c in adds_vars if c in adds.columns]]

    # ── Print summary ──────────────────────────────────────────────
    print(f"\n[ADDS] === ADaM ADDS Summary ===")
    print(f"  Total records:    {len(adds)}")
    print(f"  Distribution of AVALC:")
    print(adds['AVALC'].value_counts().to_string())
    print(f"  Variables:        {list(adds.columns)}")
    print(f"  Dimensions:       {adds.shape}")

    return adds


def save_adds(adds: pd.DataFrame, output_dir: str = None):
    """Save ADDS as CSV and XPT."""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "adam")
    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, "adds.csv")
    xpt_path = os.path.join(output_dir, "adds.xpt")

    adds.to_csv(csv_path, index=False)
    print(f"[ADDS] Saved CSV  → {csv_path}")

    adds_xpt = adds.copy()
    for col in adds_xpt.select_dtypes(include=["Int64", "int64", "int32"]).columns:
        adds_xpt[col] = adds_xpt[col].astype(float)
    for col in adds_xpt.select_dtypes(include=["object"]).columns:
        adds_xpt[col] = adds_xpt[col].fillna("")

    try:
        pyreadstat.write_xport(
            adds_xpt, xpt_path,
            file_label="ADaM ADDS Dataset",
            table_name="ADDS"
        )
        print(f"[ADDS] Saved XPT  → {xpt_path}")
    except Exception as e:
        print(f"[ADDS] XPT write warning: {e}")


# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    adds = create_adds()
    save_adds(adds)
    print("\n[ADDS] ✓ ADDS derivation complete.")
