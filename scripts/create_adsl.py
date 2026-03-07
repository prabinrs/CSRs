"""
create_adsl.py — Generate ADaM ADSL (Subject-Level Analysis Dataset).

Reads:  data/sdtm/dm.csv, data/raw/disposition.csv
Output: data/adam/adsl.csv, data/adam/adsl.xpt

ADaM IG v1.3 — ADSL
Key derivations:
  1. Traceability: every ADSL variable traces to an SDTM source
  2. Population flags: SAFFL, ITTFL, COMPLFL
  3. Treatment variables: TRT01P, TRT01A, TRT01PN, TRT01AN
  4. Analysis age groups: AGEGR1, AGEGR1N
  5. Study day derivation: TRTDURD (treatment duration in days)
"""

import sys
import os
import pandas as pd
import pyreadstat

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.cdash_utils import (
    derive_safety_flag, derive_itt_flag, derive_comp_flag,
    compute_duration_days, STUDYID
)


# ──────────────────────────────────────────────────────────────────────
# Traceability Mapping (ADaM → SDTM)
# ──────────────────────────────────────────────────────────────────────
TRACEABILITY = {
    "STUDYID":  {"source": "DM.STUDYID",   "derivation": "Direct copy"},
    "USUBJID":  {"source": "DM.USUBJID",   "derivation": "Direct copy"},
    "SUBJID":   {"source": "DM.SUBJID",    "derivation": "Direct copy"},
    "SITEID":   {"source": "DM.SITEID",    "derivation": "Direct copy"},
    "AGE":      {"source": "DM.AGE",       "derivation": "Direct copy from SDTM DM"},
    "AGEU":     {"source": "DM.AGEU",      "derivation": "Direct copy"},
    "AGEGR1":   {"source": "DM.AGEGR1",    "derivation": "Derived from AGE: <65, 65-80, >80"},
    "AGEGR1N":  {"source": "DM.AGE",       "derivation": "Numeric code: <65=1, 65-80=2, >80=3"},
    "SEX":      {"source": "DM.SEX",       "derivation": "Direct copy"},
    "SEXN":     {"source": "DM.SEX",       "derivation": "Numeric code: F=1, M=2"},
    "RACE":     {"source": "DM.RACE",      "derivation": "Direct copy"},
    "RACEN":    {"source": "DM.RACE",      "derivation": "Numeric code per protocol"},
    "ETHNIC":   {"source": "DM.ETHNIC",    "derivation": "Direct copy"},
    "COUNTRY":  {"source": "DM.COUNTRY",   "derivation": "Direct copy"},
    "TRT01P":   {"source": "DM.ARM",       "derivation": "Planned Treatment = ARM"},
    "TRT01PN":  {"source": "DM.ARMCD",     "derivation": "Numeric: PBO=0, TRT01=1, TRT02=2"},
    "TRT01A":   {"source": "DM.ARM",       "derivation": "Actual Treatment = ARM (no crossover)"},
    "TRT01AN":  {"source": "DM.ARMCD",     "derivation": "Same as TRT01PN"},
    "TRTSDT":   {"source": "DM.RFSTDTC",   "derivation": "Treatment start = RFSTDTC"},
    "TRTEDT":   {"source": "DM.RFENDTC",   "derivation": "Treatment end = RFENDTC"},
    "TRTDURD":  {"source": "DM.RFSTDTC, DM.RFENDTC", "derivation": "TRTEDT - TRTSDT + 1"},
    "SAFFL":    {"source": "DM.RFSTDTC",   "derivation": "Y if RFSTDTC non-null (received dose)"},
    "ITTFL":    {"source": "DM.ARM",       "derivation": "Y if randomized (ARM non-null)"},
    "COMPLFL":  {"source": "DS.DSDECOD",   "derivation": "Y if DSDECOD='COMPLETED'"},
    "DCDECOD":  {"source": "DS.DSDECOD",   "derivation": "Standardized disposition code"},
    "DCSREAS":  {"source": "DS.DSTERM",    "derivation": "Reason for discontinuation"},
}


def create_adsl(dm_path: str = None, ds_path: str = None) -> pd.DataFrame:
    """
    Derive ADaM ADSL from SDTM DM and raw disposition.
    """
    if dm_path is None:
        dm_path = os.path.join(os.path.dirname(__file__), "..", "data", "sdtm", "dm.csv")
    if ds_path is None:
        ds_path = os.path.join(os.path.dirname(__file__), "..", "data", "sdtm", "ds.csv")

    print(f"[ADSL] Reading SDTM DM: {dm_path}")
    dm = pd.read_csv(dm_path, dtype=str)

    print(f"[ADSL] Reading disposition data: {ds_path}")
    ds = pd.read_csv(ds_path, dtype=str)

    # ── Step 1: Merge DM with Disposition ──────────────────────────
    adsl = dm.merge(
        ds[["SUBJID", "DSSTDTC", "DSTERM", "DSDECOD"]],
        on="SUBJID", how="left", suffixes=("", "_DS")
    )
    print(f"[ADSL] Merged DM + DS → {len(adsl)} records")

    # ── Step 2: Treatment variables ────────────────────────────────
    adsl["TRT01P"] = adsl["ARM"]
    adsl["TRT01A"] = adsl["ARM"]  # Actual = Planned (no crossover study)

    armcd_map = {"PBO": 0, "TRT01": 1, "TRT02": 2}
    adsl["TRT01PN"] = adsl["ARMCD"].map(armcd_map)
    adsl["TRT01AN"] = adsl["TRT01PN"]

    # ── Step 3: Dates ──────────────────────────────────────────────
    adsl["TRTSDT"] = adsl["RFSTDTC"]
    adsl["TRTEDT"] = adsl["RFENDTC"]

    # Treatment duration
    adsl["TRTDURD"] = adsl.apply(
        lambda r: compute_duration_days(r["TRTSDT"], r["TRTEDT"]), axis=1
    )

    # ── Step 4: Numeric codes ──────────────────────────────────────
    sex_map = {"F": 1, "M": 2}
    adsl["SEXN"] = adsl["SEX"].map(sex_map)

    agegr_map = {"<65": 1, "65-80": 2, ">80": 3}
    adsl["AGEGR1N"] = adsl["AGEGR1"].map(agegr_map)

    race_map = {
        "WHITE": 1, "BLACK OR AFRICAN AMERICAN": 2, "ASIAN": 3,
        "AMERICAN INDIAN OR ALASKA NATIVE": 4,
        "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER": 5,
        "MULTIPLE": 6, "OTHER": 7, "NOT REPORTED": 8,
    }
    adsl["RACEN"] = adsl["RACE"].map(race_map)

    # ── Step 5: Population flags ───────────────────────────────────
    adsl["SAFFL"] = adsl.apply(derive_safety_flag, axis=1)
    adsl["ITTFL"] = adsl.apply(derive_itt_flag, axis=1)
    adsl["COMPLFL"] = adsl.apply(derive_comp_flag, axis=1)

    # ── Step 6: Disposition ────────────────────────────────────────
    adsl["DCDECOD"] = adsl["DSDECOD"]
    adsl["DCSREAS"] = adsl.apply(
        lambda r: r["DSTERM"] if r.get("DSDECOD") != "COMPLETED" else "", axis=1
    )

    # ── Step 7: Select and order ADSL variables ────────────────────
    adsl_vars = [
        "STUDYID", "USUBJID", "SUBJID", "SITEID",
        "AGE", "AGEU", "AGEGR1", "AGEGR1N",
        "SEX", "SEXN", "RACE", "RACEN", "ETHNIC", "COUNTRY",
        "TRT01P", "TRT01PN", "TRT01A", "TRT01AN",
        "TRTSDT", "TRTEDT", "TRTDURD",
        "SAFFL", "ITTFL", "COMPLFL",
        "DCDECOD", "DCSREAS",
    ]
    adsl = adsl[[c for c in adsl_vars if c in adsl.columns]]

    # Ensure AGE is numeric
    adsl["AGE"] = pd.to_numeric(adsl["AGE"], errors="coerce").astype("Int64")
    adsl["TRTDURD"] = pd.to_numeric(adsl["TRTDURD"], errors="coerce").astype("Int64")

    # ── Print summary ──────────────────────────────────────────────
    print(f"\n[ADSL] === ADaM ADSL Summary ===")
    print(f"  Subjects:         {adsl['USUBJID'].nunique()}")
    print(f"  Safety Pop (Y):   {(adsl['SAFFL']=='Y').sum()}")
    print(f"  ITT Pop (Y):      {(adsl['ITTFL']=='Y').sum()}")
    print(f"  Completers (Y):   {(adsl['COMPLFL']=='Y').sum()}")
    print(f"  Treatment groups: {adsl['TRT01P'].value_counts().to_dict()}")
    print(f"  Mean age:         {adsl['AGE'].mean():.1f} years")
    print(f"  Variables:        {list(adsl.columns)}")
    print(f"  Dimensions:       {adsl.shape}")

    return adsl


def save_adsl(adsl: pd.DataFrame, output_dir: str = None):
    """Save ADSL as CSV and XPT."""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "adam")
    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, "adsl.csv")
    xpt_path = os.path.join(output_dir, "adsl.xpt")

    adsl.to_csv(csv_path, index=False)
    print(f"[ADSL] Saved CSV  → {csv_path}")

    adsl_xpt = adsl.copy()
    for col in adsl_xpt.select_dtypes(include=["Int64"]).columns:
        adsl_xpt[col] = adsl_xpt[col].astype(float)
    for col in adsl_xpt.select_dtypes(include=["object"]).columns:
        adsl_xpt[col] = adsl_xpt[col].fillna("")

    try:
        pyreadstat.write_xport(
            adsl_xpt, xpt_path,
            file_label="ADaM ADSL Dataset",
            table_name="ADSL"
        )
        print(f"[ADSL] Saved XPT  → {xpt_path}")
    except Exception as e:
        print(f"[ADSL] XPT write warning: {e}")


def print_traceability():
    """Print the full traceability table."""
    print("\n" + "=" * 80)
    print("ADSL TRACEABILITY TABLE — ADaM Variable → SDTM Source")
    print("=" * 80)
    print(f"{'ADaM Variable':<15} {'SDTM Source':<30} {'Derivation'}")
    print("-" * 80)
    for var, info in TRACEABILITY.items():
        print(f"{var:<15} {info['source']:<30} {info['derivation']}")
    print("=" * 80)


# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print_traceability()
    adsl = create_adsl()
    save_adsl(adsl)
    print("\n[ADSL] ✓ ADSL derivation complete.")
