"""
disposition_summary.py — Generate disposition summary table and figure
from the ADaM ADSL and ADDS datasets.

Outputs:
  - output/disposition_summary.png  (Sankey or Bar chart)
  - Console: formatted summary table (Table 14.1.2 style)
"""

import sys
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PALETTE = {
    "Placebo": "#7f8c8d",
    "Xanomeline Low Dose": "#3498db",
    "Xanomeline High Dose": "#e74c3c",
}
sns.set_theme(style="whitegrid", font_scale=1.1)
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "#fafafa",
    "font.family": "DejaVu Sans",
})


def load_adds(path: str = None) -> pd.DataFrame:
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "..", "data", "adam", "adds.csv")
    adds = pd.read_csv(path)
    return adds


def generate_table_14_1_2(adds: pd.DataFrame) -> str:
    """
    Generate Table 14.1.2-style disposition summary.
    """
    lines = []
    lines.append("=" * 90)
    lines.append("  Table 14.1.2 — Summary of Subject Disposition")
    lines.append("  ITT Population (ITTFL='Y')")
    lines.append("=" * 90)

    # Use ITT population if available, else just all records
    if "ITTFL" in adds.columns:
        itt = adds[adds["ITTFL"] == "Y"]
    else:
        itt = adds
        
    treatments = itt["TRT01A"].dropna().unique()
    treatments = sorted(treatments, key=lambda x: ("Placebo" not in x, x))

    header = f"{'Status/Reason':<35}"
    for trt in treatments:
        n = len(itt[itt["TRT01A"] == trt].drop_duplicates("USUBJID"))
        short = trt.replace("Xanomeline ", "Xan. ")
        header += f"{short + ' (N=' + str(n) + ')':<20}"
    n_total = len(itt.drop_duplicates("USUBJID"))
    header += f"{'Total (N=' + str(n_total) + ')':<20}"
    lines.append(header)
    lines.append("-" * 90)

    # Helper function to get counts
    def get_row_string(label, filter_condition):
        row = f"  {label:<33}"
        for trt in treatments:
            grp = itt[itt["TRT01A"] == trt]
            n_grp = len(grp[filter_condition(grp)])
            pct = 100 * n_grp / len(grp) if len(grp) > 0 else 0
            row += f"{n_grp:>3} ({pct:5.1f}%)     "
        n_total_cat = len(itt[filter_condition(itt)])
        pct_total = 100 * n_total_cat / n_total if n_total > 0 else 0
        row += f"{n_total_cat:>3} ({pct_total:5.1f}%)"
        return row

    # Randomized
    lines.append(get_row_string("Randomized", lambda df: df["USUBJID"].notnull()))
    
    # Completed
    lines.append(get_row_string("Completed Study", lambda df: df["AVALC"] == "COMPLETED"))

    # Discontinued
    lines.append("\n  Discontinued Study")
    lines.append(get_row_string("Any reason", lambda df: (df["AVALC"].notnull()) & (df["AVALC"] != "COMPLETED")))

    # Specific reasons
    reasons = itt.loc[(itt["AVALC"].notnull()) & (itt["AVALC"] != "COMPLETED"), "AVALC"].dropna().unique()
    for reason in sorted(reasons):
        lines.append(get_row_string(f"  {reason.title()}", lambda df: df["AVALC"] == reason))

    lines.append("=" * 90)
    lines.append("  Source: ADaM ADDS")
    return "\n".join(lines)


def create_disposition_figure(adds: pd.DataFrame, output_path: str):
    """
    Create a stacked bar chart of disposition status by treatment.
    """
    itt = adds[adds["ITTFL"] == "Y"].copy() if "ITTFL" in adds.columns else adds.copy()
    
    # Standardize statuses
    itt["Status"] = itt["AVALC"].apply(
        lambda x: "Completed" if x == "COMPLETED" else "Discontinued"
    )
    
    # Group and count
    counts = itt.groupby(["TRT01A", "Status"]).size().unstack(fill_value=0)
    
    # Order treatments
    order = sorted(counts.index, key=lambda x: ("Placebo" not in x, x))
    counts = counts.loc[order]
    
    # Plotting
    fig, ax = plt.subplots(figsize=(10, 6))
    
    bars_c = ax.bar(
        [t.replace("Xanomeline ", "Xan.\n") for t in order],
        counts.get("Completed", [0]*len(order)),
        label="Completed", color="#2ecc71", alpha=0.85
    )
    
    bars_d = ax.bar(
        [t.replace("Xanomeline ", "Xan.\n") for t in order],
        counts.get("Discontinued", [0]*len(order)),
        bottom=counts.get("Completed", [0]*len(order)),
        label="Discontinued", color="#e74c3c", alpha=0.85
    )
    
    # Add counts to bars
    for bars in [bars_c, bars_d]:
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_y() + h / 2,
                    f"{int(h)}",
                    ha="center", va="center", color="white", fontweight="bold"
                )

    ax.set_ylabel("Number of Subjects")
    ax.set_title("Subject Disposition by Treatment Arm", fontweight="bold")
    ax.legend(title="Status", framealpha=0.9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"[VIZ] Disposition figure → {output_path}")
    plt.close()


if __name__ == "__main__":
    adds = load_adds()
    table = generate_table_14_1_2(adds)
    print(table)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    os.makedirs(out_dir, exist_ok=True)
    create_disposition_figure(adds, os.path.join(out_dir, "disposition_summary.png"))

    with open(os.path.join(out_dir, "table_14_1_2.txt"), "w") as f:
        f.write(table)
    print(f"[VIZ] Table 14.1.2 → {os.path.join(out_dir, 'table_14_1_2.txt')}")
    print("[VIZ] Disposition summary complete.")
