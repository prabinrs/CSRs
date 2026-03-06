"""
validate_core.py — CDISC Conformance Checks for SDTM and ADaM datasets.

Implements a subset of CDISC validation rules programmatically.
In production, this would integrate with the CDISC Open Rules Engine (CORE).

Validation categories:
  1. Structural checks (required variables, data types)
  2. Controlled terminology (CT) validation
  3. Cross-domain consistency
  4. ISO 8601 date conformance
  5. Population flag logic verification
"""

import sys
import os
import re
import json
from datetime import datetime
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ──────────────────────────────────────────────────────────────────────
# Controlled Terminology (CDISC CT 2023-12-15 subset)
# ──────────────────────────────────────────────────────────────────────
CT = {
    "SEX": {"F", "M", "U", "UNDIFFERENTIATED"},
    "RACE": {
        "WHITE", "BLACK OR AFRICAN AMERICAN", "ASIAN",
        "AMERICAN INDIAN OR ALASKA NATIVE",
        "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER",
        "MULTIPLE", "OTHER", "NOT REPORTED", "UNKNOWN",
    },
    "ETHNIC": {
        "HISPANIC OR LATINO", "NOT HISPANIC OR LATINO",
        "NOT REPORTED", "UNKNOWN", "",
    },
    "AGEU": {"YEARS", "MONTHS", "DAYS", "HOURS"},
    "NY": {"Y", "N", ""},
    "DSDECOD": {
        "COMPLETED", "ADVERSE EVENT", "DEATH",
        "WITHDRAWAL BY SUBJECT", "LOST TO FOLLOW-UP",
        "PHYSICIAN DECISION", "PROTOCOL VIOLATION",
        "LACK OF EFFICACY", "PREGNANCY", "OTHER",
    },
}

# Required variables per domain
REQUIRED_VARS = {
    "DM": ["STUDYID", "DOMAIN", "USUBJID", "SUBJID", "SITEID",
            "RFSTDTC", "AGE", "AGEU", "SEX", "RACE", "ARMCD", "ARM"],
    "ADSL": ["STUDYID", "USUBJID", "SUBJID", "SITEID",
             "AGE", "AGEU", "SEX", "RACE",
             "TRT01P", "TRT01PN", "TRT01A", "TRT01AN",
             "SAFFL", "ITTFL"],
}


class ValidationResult:
    """Container for a single validation finding."""
    def __init__(self, rule_id: str, severity: str, domain: str,
                 variable: str, message: str, records: list = None):
        self.rule_id = rule_id
        self.severity = severity  # ERROR, WARNING, NOTE
        self.domain = domain
        self.variable = variable
        self.message = message
        self.records = records or []

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "domain": self.domain,
            "variable": self.variable,
            "message": self.message,
            "affected_records": len(self.records),
        }

    def __repr__(self):
        icon = {"ERROR": "✗", "WARNING": "⚠", "NOTE": "ℹ"}.get(self.severity, "?")
        return f"  {icon} [{self.rule_id}] {self.severity}: {self.message}"


class CDISCValidator:
    """
    Programmatic CDISC conformance checker.

    Implements rules inspired by CDISC CORE for DM and ADSL domains.
    """

    def __init__(self):
        self.findings = []

    def _add(self, rule_id, severity, domain, variable, message, records=None):
        self.findings.append(
            ValidationResult(rule_id, severity, domain, variable, message, records)
        )

    # ── Structural Checks ──────────────────────────────────────────
    def check_required_variables(self, df: pd.DataFrame, domain: str):
        """SD0001: Check that all required variables are present."""
        required = REQUIRED_VARS.get(domain, [])
        missing = [v for v in required if v not in df.columns]
        if missing:
            self._add("SD0001", "ERROR", domain, ",".join(missing),
                       f"Missing required variable(s): {missing}")
        else:
            self._add("SD0001", "NOTE", domain, "-",
                       f"All {len(required)} required variables present ✓")

    def check_no_duplicate_subjects(self, df: pd.DataFrame, domain: str):
        """SD0002: Check for duplicate USUBJIDs."""
        if "USUBJID" not in df.columns:
            return
        dupes = df[df.duplicated(subset=["USUBJID"], keep=False)]
        if len(dupes) > 0:
            self._add("SD0002", "ERROR", domain, "USUBJID",
                       f"Duplicate USUBJID found: {dupes['USUBJID'].unique().tolist()}",
                       dupes.index.tolist())
        else:
            self._add("SD0002", "NOTE", domain, "USUBJID",
                       "No duplicate USUBJIDs ✓")

    def check_null_key_variables(self, df: pd.DataFrame, domain: str):
        """SD0003: Key identifier variables must not be null."""
        key_vars = ["STUDYID", "USUBJID"]
        for var in key_vars:
            if var in df.columns:
                nulls = df[df[var].isna() | (df[var].astype(str).str.strip() == "")]
                if len(nulls) > 0:
                    self._add("SD0003", "ERROR", domain, var,
                               f"Null values in {var}: {len(nulls)} records",
                               nulls.index.tolist())

    # ── Controlled Terminology ─────────────────────────────────────
    def check_controlled_terminology(self, df: pd.DataFrame, domain: str):
        """CT0001: Validate values against CDISC controlled terminology."""
        ct_checks = {"DM": ["SEX", "RACE", "ETHNIC", "AGEU"],
                      "ADSL": ["SEX", "RACE"]}
        vars_to_check = ct_checks.get(domain, [])

        for var in vars_to_check:
            if var not in df.columns:
                continue
            allowed = CT.get(var, set())
            actual = set(df[var].dropna().unique())
            invalid = actual - allowed
            if invalid:
                self._add("CT0001", "ERROR", domain, var,
                           f"Non-CT values in {var}: {invalid}")
            else:
                self._add("CT0001", "NOTE", domain, var,
                           f"{var} controlled terminology valid ✓")

    # ── ISO 8601 Date Checks ───────────────────────────────────────
    def check_iso8601_dates(self, df: pd.DataFrame, domain: str):
        """DT0001: All --DTC variables must be ISO 8601 formatted."""
        iso_pattern = r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?)?$"
        date_cols = [c for c in df.columns if c.endswith("DTC") or c.endswith("DT")]

        for col in date_cols:
            non_null = df[col].dropna()
            if len(non_null) == 0:
                continue
            invalid = non_null[~non_null.astype(str).str.match(iso_pattern)]
            if len(invalid) > 0:
                self._add("DT0001", "ERROR", domain, col,
                           f"Non-ISO 8601 dates in {col}: {len(invalid)} values",
                           invalid.index.tolist())
            else:
                self._add("DT0001", "NOTE", domain, col,
                           f"{col} dates are ISO 8601 compliant ✓")

    # ── DM-Specific Checks ─────────────────────────────────────────
    def check_dm_age_derivation(self, df: pd.DataFrame):
        """DM0001: AGE must be consistent with BRTHDTC and RFSTDTC."""
        if not all(c in df.columns for c in ["AGE", "BRTHDTC", "RFSTDTC"]):
            return
        issues = []
        for idx, row in df.iterrows():
            try:
                bd = pd.to_datetime(row["BRTHDTC"])
                rd = pd.to_datetime(row["RFSTDTC"])
                expected = int((rd - bd).days / 365.25)
                actual = int(float(row["AGE"]))
                if abs(expected - actual) > 1:  # Allow 1-year tolerance
                    issues.append(idx)
            except Exception:
                continue
        if issues:
            self._add("DM0001", "WARNING", "DM", "AGE",
                       f"AGE inconsistent with BRTHDTC/RFSTDTC for {len(issues)} subjects",
                       issues)
        else:
            self._add("DM0001", "NOTE", "DM", "AGE",
                       "AGE derivation consistent ✓")

    # ── ADSL-Specific Checks ───────────────────────────────────────
    def check_adsl_population_flags(self, df: pd.DataFrame):
        """AD0001: Population flags must be Y or N."""
        flag_vars = ["SAFFL", "ITTFL", "COMPLFL"]
        for var in flag_vars:
            if var not in df.columns:
                continue
            invalid = df[~df[var].isin(["Y", "N"])]
            if len(invalid) > 0:
                self._add("AD0001", "ERROR", "ADSL", var,
                           f"Invalid flag values in {var}: {invalid[var].unique().tolist()}")
            else:
                self._add("AD0001", "NOTE", "ADSL", var,
                           f"{var} population flag values valid ✓")

    def check_adsl_trt_consistency(self, df: pd.DataFrame):
        """AD0002: TRT01PN must be consistent with TRT01P."""
        if not all(c in df.columns for c in ["TRT01P", "TRT01PN"]):
            return
        # Every unique TRT01P should map to exactly one TRT01PN
        mapping = df.groupby("TRT01P")["TRT01PN"].nunique()
        inconsistent = mapping[mapping > 1]
        if len(inconsistent) > 0:
            self._add("AD0002", "ERROR", "ADSL", "TRT01P/TRT01PN",
                       f"Inconsistent TRT01P→TRT01PN mapping: {inconsistent.to_dict()}")
        else:
            self._add("AD0002", "NOTE", "ADSL", "TRT01P/TRT01PN",
                       "Treatment variable mapping consistent ✓")

    def check_adsl_trtdurd(self, df: pd.DataFrame):
        """AD0003: TRTDURD must equal TRTEDT - TRTSDT + 1."""
        if not all(c in df.columns for c in ["TRTDURD", "TRTSDT", "TRTEDT"]):
            return
        issues = []
        for idx, row in df.iterrows():
            try:
                s = pd.to_datetime(row["TRTSDT"])
                e = pd.to_datetime(row["TRTEDT"])
                expected = (e - s).days + 1
                actual = int(float(row["TRTDURD"]))
                if expected != actual:
                    issues.append(idx)
            except Exception:
                continue
        if issues:
            self._add("AD0003", "ERROR", "ADSL", "TRTDURD",
                       f"TRTDURD inconsistent with dates: {len(issues)} subjects", issues)
        else:
            self._add("AD0003", "NOTE", "ADSL", "TRTDURD",
                       "Treatment duration derivation consistent ✓")

    # ── Run All ────────────────────────────────────────────────────
    def validate_dm(self, dm: pd.DataFrame) -> list:
        """Run all DM validation rules."""
        self.findings = []
        self.check_required_variables(dm, "DM")
        self.check_no_duplicate_subjects(dm, "DM")
        self.check_null_key_variables(dm, "DM")
        self.check_controlled_terminology(dm, "DM")
        self.check_iso8601_dates(dm, "DM")
        self.check_dm_age_derivation(dm)
        return self.findings

    def validate_adsl(self, adsl: pd.DataFrame) -> list:
        """Run all ADSL validation rules."""
        self.findings = []
        self.check_required_variables(adsl, "ADSL")
        self.check_no_duplicate_subjects(adsl, "ADSL")
        self.check_null_key_variables(adsl, "ADSL")
        self.check_controlled_terminology(adsl, "ADSL")
        self.check_adsl_population_flags(adsl)
        self.check_adsl_trt_consistency(adsl)
        self.check_adsl_trtdurd(adsl)
        return self.findings


def print_validation_report(findings: list, domain: str):
    """Print formatted validation report."""
    print(f"\n{'=' * 70}")
    print(f"  CDISC CONFORMANCE REPORT — {domain}")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}")
    print(f"{'=' * 70}")

    errors = [f for f in findings if f.severity == "ERROR"]
    warnings = [f for f in findings if f.severity == "WARNING"]
    notes = [f for f in findings if f.severity == "NOTE"]

    print(f"\n  Summary: {len(errors)} Errors | {len(warnings)} Warnings | {len(notes)} Passed\n")

    if errors:
        print("  ERRORS:")
        for f in errors:
            print(f"  {f}")
    if warnings:
        print("\n  WARNINGS:")
        for f in warnings:
            print(f"  {f}")
    print("\n  PASSED CHECKS:")
    for f in notes:
        print(f"  {f}")

    status = "FAIL" if errors else ("REVIEW" if warnings else "PASS")
    print(f"\n  Overall Status: {status}")
    print(f"{'=' * 70}")
    return status


def generate_json_report(findings: list, domain: str, output_path: str):
    """Export validation results as JSON (machine-readable)."""
    report = {
        "domain": domain,
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "errors": len([f for f in findings if f.severity == "ERROR"]),
            "warnings": len([f for f in findings if f.severity == "WARNING"]),
            "passed": len([f for f in findings if f.severity == "NOTE"]),
        },
        "findings": [f.to_dict() for f in findings],
    }
    with open(output_path, "w") as fp:
        json.dump(report, fp, indent=2)
    print(f"[VALIDATE] JSON report → {output_path}")


# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    base = os.path.join(os.path.dirname(__file__), "..")

    # Validate DM
    dm_path = os.path.join(base, "data", "sdtm", "dm.csv")
    if os.path.exists(dm_path):
        dm = pd.read_csv(dm_path, dtype=str)
        validator = CDISCValidator()
        dm_findings = validator.validate_dm(dm)
        dm_status = print_validation_report(dm_findings, "SDTM DM")
        generate_json_report(dm_findings, "DM",
                             os.path.join(base, "output", "dm_validation.json"))

    # Validate ADSL
    adsl_path = os.path.join(base, "data", "adam", "adsl.csv")
    if os.path.exists(adsl_path):
        adsl = pd.read_csv(adsl_path, dtype=str)
        validator = CDISCValidator()
        adsl_findings = validator.validate_adsl(adsl)
        adsl_status = print_validation_report(adsl_findings, "ADaM ADSL")
        generate_json_report(adsl_findings, "ADSL",
                             os.path.join(base, "output", "adsl_validation.json"))

    print("\n[VALIDATE] ✓ Validation complete.")
