"""
create_dm.py — Generate SDTM DM (Demographics) domain from raw EDC data.

Reads: data/raw/enrollment.csv
Output: data/sdtm/dm.csv, data/sdtm/dm.xpt

SDTM IG 3.4 — DM Domain
Key transformations:
  1. Map raw date fields to ISO 8601 (--DTC variables)
  2. Derive USUBJID from STUDYID + SUBJID
  3. Derive AGE from BRTHDTC and RFSTDTC
  4. Assign AGEU, AGEGR1 per protocol conventions
  5. Order variables per SDTM standard
"""

import sys
import os
import pandas as pd
import pyreadstat

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.cdash_utils import (
    to_iso8601, derive_age, assign_age_group,
    add_domain_keys, order_sdtm_columns, validate_iso_dates,
    STUDYID, DOMAIN_DM
)


def create_dm(raw_path: str = None) -> pd.DataFrame:
    """
    Transform raw enrollment data into SDTM DM domain.

    Returns
    -------
    pd.DataFrame
        SDTM-compliant DM dataset.
    """
    if raw_path is None:
        raw_path = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "enrollment.csv")

    print(f"[DM] Reading raw enrollment data: {raw_path}")
    raw = pd.read_csv(raw_path, dtype=str)
    print(f"[DM] Loaded {len(raw)} subjects from raw data")

    # ── Step 1: Add domain identifiers ─────────────────────────────
    dm = add_domain_keys(raw, domain=DOMAIN_DM)

    # ── Step 2: Convert dates to ISO 8601 ──────────────────────────
    date_map = {
        "BRTHDTC": "BRTHDT",   # Birth Date
        "RFSTDTC": "RFSTDTC",  # First Study Treatment Date
        "RFENDTC": "RFENDTC",  # Last Study Treatment Date
        "DMDTC":   "ENRDT",    # Date of DM collection (Enrollment Date)
    }
    for sdtm_var, raw_var in date_map.items():
        if raw_var in dm.columns:
            dm[sdtm_var] = dm[raw_var].apply(to_iso8601)
        elif sdtm_var not in dm.columns:
            dm[sdtm_var] = None

    # ── Step 3: Derive AGE and age groups ──────────────────────────
    dm["AGE"] = dm.apply(
        lambda r: derive_age(r["BRTHDTC"], r["RFSTDTC"]), axis=1
    )
    dm["AGEU"] = "YEARS"
    dm["AGEGR1"] = dm["AGE"].apply(assign_age_group)

    # ── Step 4: Map standard variables ─────────────────────────────
    dm["RFXSTDTC"] = dm["RFSTDTC"]  # Date of First Exposure
    dm["RFXENDTC"] = dm["RFENDTC"]  # Date of Last Exposure

    # ── Step 5: Order columns per SDTM DM specification ────────────
    dm_vars = [
        "STUDYID", "DOMAIN", "USUBJID", "SUBJID", "SITEID",
        "RFSTDTC", "RFENDTC", "RFXSTDTC", "RFXENDTC",
        "BRTHDTC", "DMDTC",
        "AGE", "AGEU", "AGEGR1",
        "SEX", "RACE", "ETHNIC", "COUNTRY",
        "ARMCD", "ARM",
    ]
    dm = order_sdtm_columns(dm, dm_vars)
    # Keep only SDTM variables
    dm = dm[[c for c in dm_vars if c in dm.columns]]

    # ── Step 6: Validate dates ─────────────────────────────────────
    date_cols = ["BRTHDTC", "RFSTDTC", "RFENDTC", "RFXSTDTC", "RFXENDTC", "DMDTC"]
    issues = validate_iso_dates(dm, date_cols)
    if issues:
        print(f"[DM] WARNING — ISO 8601 validation issues: {issues}")
    else:
        print("[DM] All dates pass ISO 8601 validation ✓")

    # ── Print summary ──────────────────────────────────────────────
    print(f"\n[DM] === SDTM DM Domain Summary ===")
    print(f"  Subjects:     {dm['USUBJID'].nunique()}")
    print(f"  Sites:        {dm['SITEID'].nunique()}")
    print(f"  Arms:         {dm['ARM'].value_counts().to_dict()}")
    print(f"  Age range:    {dm['AGE'].min()} – {dm['AGE'].max()} years")
    print(f"  Variables:    {list(dm.columns)}")
    print(f"  Dimensions:   {dm.shape}")

    return dm


def save_dm(dm: pd.DataFrame, output_dir: str = None):
    """Save DM as both CSV and XPT (SAS transport v5)."""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sdtm")
    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, "dm.csv")
    xpt_path = os.path.join(output_dir, "dm.xpt")

    dm.to_csv(csv_path, index=False)
    print(f"[DM] Saved CSV  → {csv_path}")

    # Save as SAS XPORT v5 using pyreadstat
    # Ensure AGE is numeric for XPT
    dm_xpt = dm.copy()
    dm_xpt["AGE"] = pd.to_numeric(dm_xpt["AGE"], errors="coerce")
    column_labels = {
        "STUDYID": "Study Identifier",
        "DOMAIN": "Domain Abbreviation",
        "USUBJID": "Unique Subject Identifier",
        "SUBJID": "Subject Identifier for the Study",
        "SITEID": "Study Site Identifier",
        "RFSTDTC": "Subject Reference Start Date/Time",
        "RFENDTC": "Subject Reference End Date/Time",
        "RFXSTDTC": "Date/Time of First Study Treatment",
        "RFXENDTC": "Date/Time of Last Study Treatment",
        "BRTHDTC": "Date/Time of Birth",
        "DMDTC": "Date/Time of Collection",
        "AGE": "Age",
        "AGEU": "Age Units",
        "AGEGR1": "Pooled Age Group 1",
        "SEX": "Sex",
        "RACE": "Race",
        "ETHNIC": "Ethnicity",
        "COUNTRY": "Country",
        "ARMCD": "Planned Arm Code",
        "ARM": "Description of Planned Arm",
    }
    labels = [column_labels.get(c, c) for c in dm_xpt.columns]

    try:
        pyreadstat.write_xport(
            dm_xpt, xpt_path,
            file_label="SDTM DM Domain",
            column_labels=labels,
            table_name="DM"
        )
        print(f"[DM] Saved XPT  → {xpt_path}")
    except Exception as e:
        print(f"[DM] XPT write warning: {e}")
        print(f"[DM] CSV output is available at {csv_path}")


# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    dm = create_dm()
    save_dm(dm)
    print("\n[DM] ✓ DM domain creation complete.")
