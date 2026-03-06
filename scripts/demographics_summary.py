"""
demographics_summary.py — Generate publication-quality demographics summary
from the ADaM ADSL dataset.

Outputs:
  - output/demographics_summary.png  (multi-panel figure)
  - Console: formatted summary table (Table 14.1.1 style)
"""

import sys
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns
from collections import OrderedDict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────
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


def load_adsl(path: str = None) -> pd.DataFrame:
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "..", "data", "adam", "adsl.csv")
    adsl = pd.read_csv(path)
    adsl["AGE"] = pd.to_numeric(adsl["AGE"], errors="coerce")
    adsl["TRTDURD"] = pd.to_numeric(adsl["TRTDURD"], errors="coerce")
    return adsl


def generate_table_14_1_1(adsl: pd.DataFrame) -> str:
    """
    Generate Table 14.1.1-style demographics summary (console output).
    Mirrors the format used in FDA submission packages.
    """
    lines = []
    lines.append("=" * 90)
    lines.append("  Table 14.1.1 — Summary of Demographics and Baseline Characteristics")
    lines.append("  Safety Population")
    lines.append("=" * 90)

    safety = adsl[adsl["SAFFL"] == "Y"]
    treatments = safety["TRT01A"].unique()
    treatments = sorted(treatments, key=lambda x: ("Placebo" not in x, x))

    # Header
    header = f"{'Characteristic':<35}"
    for trt in treatments:
        n = len(safety[safety["TRT01A"] == trt])
        short = trt.replace("Xanomeline ", "Xan. ")
        header += f"{short + ' (N=' + str(n) + ')':<20}"
    n_total = len(safety)
    header += f"{'Total (N=' + str(n_total) + ')':<20}"
    lines.append(header)
    lines.append("-" * 90)

    # Age statistics
    lines.append("Age (years)")
    for stat_name, stat_func in [("  Mean (SD)", lambda g: f"{g.mean():.1f} ({g.std():.1f})"),
                                   ("  Median", lambda g: f"{g.median():.1f}"),
                                   ("  Min, Max", lambda g: f"{g.min():.0f}, {g.max():.0f}")]:
        row = f"{stat_name:<35}"
        for trt in treatments:
            grp = safety.loc[safety["TRT01A"] == trt, "AGE"]
            row += f"{stat_func(grp):<20}"
        row += f"{stat_func(safety['AGE']):<20}"
        lines.append(row)

    # Categorical summaries
    for var, label in [("SEX", "Sex"), ("RACE", "Race"), ("AGEGR1", "Age Group")]:
        lines.append(f"\n{label}")
        for cat in sorted(safety[var].dropna().unique()):
            row = f"  {cat:<33}"
            for trt in treatments:
                grp = safety[safety["TRT01A"] == trt]
                n_cat = (grp[var] == cat).sum()
                pct = 100 * n_cat / len(grp) if len(grp) > 0 else 0
                row += f"{n_cat:>3} ({pct:5.1f}%)     "
            n_total_cat = (safety[var] == cat).sum()
            pct_total = 100 * n_total_cat / len(safety)
            row += f"{n_total_cat:>3} ({pct_total:5.1f}%)"
            lines.append(row)

    # Completion status
    lines.append(f"\nStudy Completion")
    for status in ["Y", "N"]:
        label = "  Completed" if status == "Y" else "  Discontinued"
        row = f"{label:<35}"
        for trt in treatments:
            grp = safety[safety["TRT01A"] == trt]
            n_s = (grp["COMPLFL"] == status).sum()
            pct = 100 * n_s / len(grp) if len(grp) > 0 else 0
            row += f"{n_s:>3} ({pct:5.1f}%)     "
        n_s_total = (safety["COMPLFL"] == status).sum()
        pct_t = 100 * n_s_total / len(safety)
        row += f"{n_s_total:>3} ({pct_t:5.1f}%)"
        lines.append(row)

    lines.append("=" * 90)
    lines.append("  Source: ADaM ADSL | Population: Safety (SAFFL='Y')")
    return "\n".join(lines)


def create_demographics_figure(adsl: pd.DataFrame, output_path: str):
    """
    Create a 2×2 multi-panel demographics summary figure.

    Panels:
      [A] Age distribution by treatment (boxplot + strip)
      [B] Sex distribution by treatment (stacked bar)
      [C] Race distribution (horizontal bar)
      [D] Treatment duration by arm (boxplot)
    """
    safety = adsl[adsl["SAFFL"] == "Y"].copy()

    fig = plt.figure(figsize=(16, 12))
    gs = gridspec.GridSpec(2, 2, hspace=0.35, wspace=0.30,
                           left=0.08, right=0.95, top=0.92, bottom=0.06)

    fig.suptitle("Demographics Summary — Safety Population (ADSL)",
                 fontsize=16, fontweight="bold", y=0.97)
    fig.text(0.5, 0.94, "Study CDISCPILOT01 | Python SDTM/ADaM Pipeline Demo",
             ha="center", fontsize=10, color="#7f8c8d")

    # ── Panel A: Age Distribution ──────────────────────────────────
    ax_a = fig.add_subplot(gs[0, 0])
    order = sorted(safety["TRT01A"].unique(), key=lambda x: ("Placebo" not in x, x))
    colors = [PALETTE.get(t, "#95a5a6") for t in order]

    bp = ax_a.boxplot(
        [safety.loc[safety["TRT01A"] == t, "AGE"].dropna() for t in order],
        labels=[t.replace("Xanomeline ", "Xan.\n") for t in order],
        patch_artist=True, widths=0.6,
        boxprops=dict(linewidth=1.5),
        medianprops=dict(color="black", linewidth=2),
    )
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    for i, trt in enumerate(order):
        ages = safety.loc[safety["TRT01A"] == trt, "AGE"].dropna()
        ax_a.scatter(
            [i + 1] * len(ages), ages,
            color=colors[i], alpha=0.5, s=40, zorder=3, edgecolor="white", linewidth=0.5
        )

    ax_a.set_ylabel("Age (years)")
    ax_a.set_title("A. Age Distribution by Treatment", fontweight="bold", loc="left")
    ax_a.spines["top"].set_visible(False)
    ax_a.spines["right"].set_visible(False)

    # ── Panel B: Sex Distribution ──────────────────────────────────
    ax_b = fig.add_subplot(gs[0, 1])
    sex_counts = safety.groupby(["TRT01A", "SEX"]).size().unstack(fill_value=0)
    sex_pct = sex_counts.div(sex_counts.sum(axis=1), axis=0) * 100
    sex_pct = sex_pct.reindex(order)

    bars_f = ax_b.barh(range(len(order)),
                        sex_pct.get("F", [0]*len(order)),
                        color="#e91e63", alpha=0.7, label="Female", height=0.5)
    bars_m = ax_b.barh(range(len(order)),
                        sex_pct.get("M", [0]*len(order)),
                        left=sex_pct.get("F", [0]*len(order)),
                        color="#2196f3", alpha=0.7, label="Male", height=0.5)

    ax_b.set_yticks(range(len(order)))
    ax_b.set_yticklabels([t.replace("Xanomeline ", "Xan. ") for t in order])
    ax_b.set_xlabel("Percentage (%)")
    ax_b.set_title("B. Sex Distribution by Treatment", fontweight="bold", loc="left")
    ax_b.legend(loc="lower right", framealpha=0.9)
    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)

    # ── Panel C: Race Distribution ─────────────────────────────────
    ax_c = fig.add_subplot(gs[1, 0])
    race_counts = safety["RACE"].value_counts().sort_values()
    race_colors = sns.color_palette("Set2", n_colors=len(race_counts))
    bars = ax_c.barh(range(len(race_counts)), race_counts.values,
                      color=race_colors, alpha=0.85, height=0.6)

    ax_c.set_yticks(range(len(race_counts)))
    labels = [r[:25] + "…" if len(r) > 25 else r for r in race_counts.index]
    ax_c.set_yticklabels(labels, fontsize=9)
    ax_c.set_xlabel("Number of Subjects")
    ax_c.set_title("C. Race Distribution (All Treatments)", fontweight="bold", loc="left")

    for bar, val in zip(bars, race_counts.values):
        ax_c.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2,
                  f" n={val}", va="center", fontsize=9)

    ax_c.spines["top"].set_visible(False)
    ax_c.spines["right"].set_visible(False)

    # ── Panel D: Treatment Duration ────────────────────────────────
    ax_d = fig.add_subplot(gs[1, 1])
    dur_data = [safety.loc[safety["TRT01A"] == t, "TRTDURD"].dropna() for t in order]
    bp2 = ax_d.boxplot(
        dur_data,
        labels=[t.replace("Xanomeline ", "Xan.\n") for t in order],
        patch_artist=True, widths=0.6,
        medianprops=dict(color="black", linewidth=2),
    )
    for patch, color in zip(bp2["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax_d.set_ylabel("Duration (days)")
    ax_d.set_title("D. Treatment Duration by Arm", fontweight="bold", loc="left")
    ax_d.spines["top"].set_visible(False)
    ax_d.spines["right"].set_visible(False)

    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"[VIZ] Demographics figure → {output_path}")
    plt.close()


# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    adsl = load_adsl()
    table = generate_table_14_1_1(adsl)
    print(table)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    os.makedirs(out_dir, exist_ok=True)
    create_demographics_figure(adsl, os.path.join(out_dir, "demographics_summary.png"))

    # Save table to text file
    with open(os.path.join(out_dir, "table_14_1_1.txt"), "w") as f:
        f.write(table)
    print(f"[VIZ] Table 14.1.1 → {os.path.join(out_dir, 'table_14_1_1.txt')}")
    print("[VIZ] Demographics summary complete.")
