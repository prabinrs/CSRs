"""
cdash_utils.py — Common CDISC transformation utilities.
Reusable functions for ISO 8601 date conversion, STUDYID assignment,
age derivation, and SDTM-compliant variable formatting.
"""

import pandas as pd
from datetime import datetime, date
from typing import Optional


# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────
STUDYID = "CDISCPILOT01"
DOMAIN_DM = "DM"
CDISC_VERSION = "SDTMIG 3.4"


# ──────────────────────────────────────────────────────────────────────
# Date Functions
# ──────────────────────────────────────────────────────────────────────
def to_iso8601(date_val, partial: bool = False) -> Optional[str]:
    """
    Convert a date value to ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDThh:mm:ss).

    Parameters
    ----------
    date_val : str, datetime, date, pd.Timestamp, or None
        Input date in various formats.
    partial : bool
        If True, allows partial dates (YYYY or YYYY-MM).

    Returns
    -------
    str or None
        ISO 8601 formatted date string, or None if input is null/invalid.

    Examples
    --------
    >>> to_iso8601("2023-10-25")
    '2023-10-25'
    >>> to_iso8601("10/25/2023")
    '2023-10-25'
    >>> to_iso8601(None)
    None
    """
    if date_val is None or (isinstance(date_val, float) and pd.isna(date_val)):
        return None
    if isinstance(date_val, str) and date_val.strip() == "":
        return None

    try:
        if isinstance(date_val, (datetime, date)):
            return date_val.strftime("%Y-%m-%d")
        if isinstance(date_val, pd.Timestamp):
            return date_val.strftime("%Y-%m-%d")
        # Try common formats
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d%b%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(str(date_val).strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        # Fall back to pandas parser
        return pd.to_datetime(date_val).strftime("%Y-%m-%d")
    except Exception:
        return None


def derive_age(birth_date: str, ref_date: str) -> Optional[int]:
    """
    Derive age in years at the reference date.

    Follows CDISC SDTM convention: AGE = floor((RFSTDTC - BRTHDTC) / 365.25).

    Parameters
    ----------
    birth_date : str
        ISO 8601 birth date (YYYY-MM-DD).
    ref_date : str
        ISO 8601 reference date (YYYY-MM-DD), typically RFSTDTC.

    Returns
    -------
    int or None
    """
    try:
        bd = pd.to_datetime(birth_date)
        rd = pd.to_datetime(ref_date)
        age = int((rd - bd).days / 365.25)
        return age if age >= 0 else None
    except Exception:
        return None


def assign_age_group(age: Optional[int]) -> Optional[str]:
    """
    Assign age group per standard protocol convention.

    Groups: <65, 65-80, >80
    """
    if age is None or pd.isna(age):
        return None
    if age < 65:
        return "<65"
    elif age <= 80:
        return "65-80"
    else:
        return ">80"


# ──────────────────────────────────────────────────────────────────────
# SDTM Helpers
# ──────────────────────────────────────────────────────────────────────
def add_domain_keys(df: pd.DataFrame, domain: str, studyid: str = STUDYID) -> pd.DataFrame:
    """
    Add STUDYID, DOMAIN, and USUBJID columns to a dataframe.
    USUBJID = STUDYID + '-' + SUBJID (CDISC standard).
    """
    df = df.copy()
    df["STUDYID"] = studyid
    df["DOMAIN"] = domain
    df["USUBJID"] = df["STUDYID"] + "-" + df["SUBJID"].astype(str)
    return df


def order_sdtm_columns(df: pd.DataFrame, domain_vars: list) -> pd.DataFrame:
    """
    Reorder columns following SDTM convention: key identifiers first,
    then domain-specific variables.
    """
    key_vars = ["STUDYID", "DOMAIN", "USUBJID"]
    ordered = key_vars + [v for v in domain_vars if v in df.columns and v not in key_vars]
    remaining = [c for c in df.columns if c not in ordered]
    return df[ordered + remaining]


def validate_iso_dates(df: pd.DataFrame, date_cols: list) -> dict:
    """
    Validate that date columns conform to ISO 8601 format.

    Returns
    -------
    dict
        {column_name: list of row indices with invalid dates}
    """
    iso_pattern = r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?)?$"
    issues = {}
    for col in date_cols:
        if col not in df.columns:
            continue
        non_null = df[col].dropna()
        invalid = non_null[~non_null.astype(str).str.match(iso_pattern)]
        if len(invalid) > 0:
            issues[col] = invalid.index.tolist()
    return issues


def compute_duration_days(start_date: str, end_date: str) -> Optional[int]:
    """
    Compute duration in days between two ISO 8601 dates.
    Duration = (end - start) + 1 (per CDISC convention, inclusive).
    """
    try:
        s = pd.to_datetime(start_date)
        e = pd.to_datetime(end_date)
        return int((e - s).days) + 1
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────
# Population Flags
# ──────────────────────────────────────────────────────────────────────
def derive_safety_flag(row: pd.Series) -> str:
    """
    Derive Safety Population Flag (SAFFL).
    Y if subject received at least one dose of study drug (RFSTDTC is not null).
    """
    return "Y" if pd.notna(row.get("RFSTDTC")) and str(row.get("RFSTDTC")).strip() != "" else "N"


def derive_itt_flag(row: pd.Series) -> str:
    """
    Derive Intent-to-Treat Population Flag (ITTFL).
    Y if subject was randomized (has an ARM assignment).
    """
    return "Y" if pd.notna(row.get("ARM")) and str(row.get("ARM")).strip() != "" else "N"


def derive_comp_flag(row: pd.Series) -> str:
    """
    Derive Completers Population Flag (COMPLFL).
    Y if subject completed the study.
    """
    return "Y" if row.get("DSDECOD") == "COMPLETED" else "N"
