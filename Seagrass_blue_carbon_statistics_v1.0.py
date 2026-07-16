# FILE: Seagrass_blue_carbon_statistics_v1.0.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Supplementary Python Script
Seagrass biomass-based blue carbon analysis in West Bali National Park

Version
-------
v1.0 (2026-07-16)
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from scipy import stats


SCRIPT_VERSION = "v1.0"
SCRIPT_DATE = "2026-07-16"

SPECIES_ORDER = ["EA", "TH", "HO"]
SPECIES_LABEL = {"EA": "E. acoroides", "TH": "T. hemprichii", "HO": "H. ovalis"}
SITE_ORDER = ["LBL", "TTR", "KSW"]
SPECIES_COLOR = {"EA": "#4C78A8", "TH": "#F2A541", "HO": "#7CBF6F"}
SITE_COLOR = {"LBL": "#808080", "TTR": "#A0A0A0", "KSW": "#C0C0C0"}

QUADRAT_AREA_M2 = 1.0
BIOMASS_SUBPLOT_AREA_M2 = 0.04

PLOT_CFG = {
    "font_family": "DejaVu Sans",
    "font_size": 15,
    "title_size": 18,
    "label_size": 20,
    "tick_size": 17,
    "legend_size": 16,
    "line_width": 2.2,
    "marker_size": 10,
    "capsize": 5,
    "grid_alpha": 0.30,
    "figure_dpi": 150,
    "save_dpi": 300,

    # Figure 4
    "fig4_size": (18, 6.2),
    "fig4_offsets": [-0.22, 0.0, 0.22],
    "fig4_panel_label_size": 16,
    "fig4_legend_loc": "upper left",
    "fig4_ylabel_default": 20,
    "fig4_ylabel_panelB": 17,

    # Figure S5 (vertical)
    "s5_size_vertical": (12, 16),
    "s5_panel_letter_size": 16,
    "s5_text_size": 13,
    "s5_note_size": 11,
    "s5_box_lw": 1.2,
}


def ensure_dirs(outdir: Path) -> Dict[str, Path]:
    dirs = {
        "root": outdir,
        "data": outdir / "01_processed_data",
        "tables": outdir / "02_tables",
        "stats": outdir / "03_statistics",
        "figures": outdir / "04_figures",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def save_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig")


def mean_sd(series: pd.Series) -> str:
    return f"{series.mean():.2f} ± {series.std(ddof=1):.2f}"


def p_format(p: float) -> str:
    if pd.isna(p):
        return ""
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"


def bonferroni(p_values: Iterable[float]) -> List[float]:
    p_values = list(p_values)
    m = len(p_values)
    return [min(p * m, 1.0) for p in p_values]


def set_figure_style() -> None:
    plt.rcParams.update({
        "font.family": PLOT_CFG["font_family"],
        "font.size": PLOT_CFG["font_size"],
        "figure.dpi": PLOT_CFG["figure_dpi"],
        "axes.titlesize": PLOT_CFG["title_size"],
        "axes.labelsize": PLOT_CFG["label_size"],
        "xtick.labelsize": PLOT_CFG["tick_size"],
        "ytick.labelsize": PLOT_CFG["tick_size"],
        "legend.fontsize": PLOT_CFG["legend_size"],
    })


def save_fig(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=PLOT_CFG["save_dpi"], bbox_inches="tight")
    plt.close(fig)


def load_input_workbook(input_xlsx: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if not input_xlsx.exists():
        raise FileNotFoundError(f"Input workbook not found: {input_xlsx}")

    required_raw = ["SampleID", "Site", "Line", "Species", "Part", "PartLabel", "Wet_g", "Dry_g", "Ash_g"]
    required_struct = [
        "SampleID", "Site", "Line", "Species", "Shoot_count", "Density",
        "Substrate", "LeafArea_cm2", "Estimated_LAI", "Pressure_Category"
    ]

    def read_sheet_with_detected_header(sheet_name: str, required_cols: list[str]) -> pd.DataFrame:
        preview = pd.read_excel(input_xlsx, sheet_name=sheet_name, header=None, nrows=20)
        header_row = None
        required_set = set(required_cols)
        for idx in range(len(preview)):
            row_values = [str(x).strip() for x in preview.iloc[idx].dropna().tolist()]
            if required_set.issubset(set(row_values)):
                header_row = idx
                break

        if header_row is None:
            raise ValueError(
                f"Could not locate the header row for sheet '{sheet_name}'. "
                f"Expected columns: {required_cols}"
            )

        df = pd.read_excel(input_xlsx, sheet_name=sheet_name, header=header_row)
        df = df.dropna(how="all").copy()
        df.columns = [str(c).strip() for c in df.columns]

        missing = set(required_cols).difference(df.columns)
        if missing:
            raise ValueError(f"Missing columns in {sheet_name}: {sorted(missing)}")

        return df[required_cols].copy()

    raw = read_sheet_with_detected_header("Raw_Compartment_Data", required_raw)
    structural = read_sheet_with_detected_header("Structural_Data", required_struct)

    raw = raw[raw["SampleID"].notna()].copy()
    structural = structural[structural["SampleID"].notna()].copy()

    raw["Line"] = raw["Line"].astype(int)
    structural["Line"] = structural["Line"].astype(int)

    for col in ["Wet_g", "Dry_g", "Ash_g"]:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")

    for col in ["Shoot_count", "Density", "LeafArea_cm2", "Estimated_LAI"]:
        structural[col] = pd.to_numeric(structural[col], errors="coerce")

    return raw, structural


def recalculate_compartment_data(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["Biomass_gDW_m2"] = df["Dry_g"] / BIOMASS_SUBPLOT_AREA_M2
    df["Biomass_MgDW_ha"] = df["Biomass_gDW_m2"] * 0.01
    df["LOI_pct"] = (df["Dry_g"] - df["Ash_g"]) / df["Dry_g"] * 100
    df["Corg_pct"] = np.where(
        df["LOI_pct"] <= 20,
        0.40 * df["LOI_pct"] - 0.21,
        0.43 * df["LOI_pct"] - 0.33,
    )
    df["CStock_gC_m2"] = df["Biomass_gDW_m2"] * df["Corg_pct"] / 100
    df["CStock_MgC_ha"] = df["CStock_gC_m2"] * 0.01
    return df


def recalculate_structural_data(structural: pd.DataFrame) -> pd.DataFrame:
    df = structural.copy()
    df["Density"] = df["Shoot_count"] / QUADRAT_AREA_M2
    df["Estimated_LAI"] = df["Density"] * df["LeafArea_cm2"] / 10000
    return df


def build_species_level_data(compartment: pd.DataFrame, structural: pd.DataFrame) -> pd.DataFrame:
    index_cols = ["Site", "Line", "Species"]

    ag = compartment[compartment["Part"] == "AG"].copy()
    bg = compartment[compartment["Part"] == "BG"].copy()

    ag_cols = index_cols + ["Biomass_gDW_m2", "CStock_gC_m2", "Corg_pct", "LOI_pct"]
    bg_cols = index_cols + ["Biomass_gDW_m2", "CStock_gC_m2", "Corg_pct", "LOI_pct"]

    ag = ag[ag_cols].rename(columns={
        "Biomass_gDW_m2": "Biomass_AG",
        "CStock_gC_m2": "CStock_AG",
        "Corg_pct": "Corg_AG",
        "LOI_pct": "LOI_AG",
    })
    bg = bg[bg_cols].rename(columns={
        "Biomass_gDW_m2": "Biomass_BG",
        "CStock_gC_m2": "CStock_BG",
        "Corg_pct": "Corg_BG",
        "LOI_pct": "LOI_BG",
    })

    df = pd.merge(ag, bg, on=index_cols, how="inner", validate="one_to_one")
    df["Total_Biomass"] = df["Biomass_AG"] + df["Biomass_BG"]
    df["BG_Biomass_Fraction_pct"] = df["Biomass_BG"] / df["Total_Biomass"] * 100
    df["Total_CStock"] = df["CStock_AG"] + df["CStock_BG"]
    df["BG_C_Fraction_pct"] = df["CStock_BG"] / df["Total_CStock"] * 100

    s = structural[[
        "SampleID", "Site", "Line", "Species", "Density",
        "LeafArea_cm2", "Estimated_LAI", "Substrate", "Pressure_Category"
    ]].copy()

    df = pd.merge(df, s, on=index_cols, how="left", validate="one_to_one")
    df["SampleID"] = df["Site"].astype(str) + "-" + df["Species"].astype(str) + "-" + df["Line"].astype(str)

    cols = [
        "SampleID", "Site", "Line", "Species", "Density", "LeafArea_cm2", "Estimated_LAI",
        "Substrate", "Pressure_Category",
        "Biomass_AG", "Biomass_BG", "Total_Biomass", "BG_Biomass_Fraction_pct",
        "Corg_AG", "Corg_BG", "LOI_AG", "LOI_BG",
        "CStock_AG", "CStock_BG", "Total_CStock", "BG_C_Fraction_pct",
    ]
    return df[cols].sort_values(["Site", "Line", "Species"]).reset_index(drop=True)


def make_table1_biomass(species_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sp in SPECIES_ORDER:
        sub = species_df[species_df["Species"] == sp]
        rows.append({
            "Species": SPECIES_LABEL[sp],
            "AG biomass (g DW m^-2)": mean_sd(sub["Biomass_AG"]),
            "BG biomass (g DW m^-2)": mean_sd(sub["Biomass_BG"]),
            "Total biomass (g DW m^-2)": mean_sd(sub["Total_Biomass"]),
            "BG biomass fraction (%)": mean_sd(sub["BG_Biomass_Fraction_pct"]),
        })
    return pd.DataFrame(rows)


def make_table2_cstock(species_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sp in SPECIES_ORDER:
        sub = species_df[species_df["Species"] == sp]
        rows.append({
            "Species": SPECIES_LABEL[sp],
            "AG C stock (g C m^-2)": mean_sd(sub["CStock_AG"]),
            "BG C stock (g C m^-2)": mean_sd(sub["CStock_BG"]),
            "Total C stock (g C m^-2)": mean_sd(sub["Total_CStock"]),
            "BG C fraction (%)": mean_sd(sub["BG_C_Fraction_pct"]),
        })
    return pd.DataFrame(rows)


def kruskal_by_group(df: pd.DataFrame, value_col: str, group_col: str) -> Tuple[float, float]:
    groups = [g[value_col].dropna().values for _, g in df.groupby(group_col)]
    if len(groups) < 2:
        return np.nan, np.nan
    h, p = stats.kruskal(*groups)
    return h, p


def make_table_s2_kruskal(species_df: pd.DataFrame, structural: pd.DataFrame, compartment: pd.DataFrame) -> pd.DataFrame:
    tests = []

    def add_test(label: str, df: pd.DataFrame, value_col: str, group_col: str):
        h, p = kruskal_by_group(df, value_col, group_col)
        tests.append({
            "Response variable": label,
            "Grouping factor": "Species" if group_col == "Species" else "Site",
            "H": round(h, 2),
            "df": df[group_col].nunique() - 1,
            "p-value": p_format(p),
            "Interpretation": "Significant" if p < 0.05 else "Not significant",
        })

    add_test("Shoot density", structural, "Density", "Species")
    add_test("Shoot density", structural, "Density", "Site")
    add_test("Estimated leaf area per shoot", structural, "LeafArea_cm2", "Species")
    add_test("Estimated LAI", structural, "Estimated_LAI", "Species")
    add_test("Total biomass", species_df, "Total_Biomass", "Species")
    add_test("Total biomass", species_df, "Total_Biomass", "Site")
    add_test("BG biomass fraction", species_df, "BG_Biomass_Fraction_pct", "Site")
    add_test("%Corg", compartment, "Corg_pct", "Species")
    add_test("%Corg", compartment, "Corg_pct", "Site")
    add_test("Total C stock", species_df, "Total_CStock", "Species")
    add_test("Total C stock", species_df, "Total_CStock", "Site")
    add_test("BG C fraction", species_df, "BG_C_Fraction_pct", "Site")
    return pd.DataFrame(tests)


def mean_ci(df: pd.DataFrame, value_col: str, group_cols: List[str]) -> pd.DataFrame:
    g = df.groupby(group_cols)[value_col].agg(["mean", "std", "count"]).reset_index()
    g["ci95"] = 1.96 * g["std"] / np.sqrt(g["count"])
    return g


def plot_figure4_structural(structural: pd.DataFrame, outdir: Path) -> None:
    panels = [
        ("Density", "Shoot density (shoots m$^{-2}$)", "A"),
        ("LeafArea_cm2", "Estimated leaf area per shoot (cm$^2$ shoot$^{-1}$)", "B"),
        ("Estimated_LAI", "Estimated LAI", "C"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=PLOT_CFG["fig4_size"])
    x = np.arange(len(SITE_ORDER))
    offsets = PLOT_CFG["fig4_offsets"]

    for idx, (ax, (value_col, ylabel, panel_letter)) in enumerate(zip(axes, panels)):
        g = mean_ci(structural, value_col, ["Site", "Species"])

        for k, sp in enumerate(SPECIES_ORDER):
            sub = g[g["Species"] == sp].set_index("Site").reindex(SITE_ORDER).reset_index()
            ax.errorbar(
                x + offsets[k], sub["mean"], yerr=sub["ci95"],
                fmt="o",
                capsize=PLOT_CFG["capsize"],
                linewidth=PLOT_CFG["line_width"],
                markersize=PLOT_CFG["marker_size"],
                color=SPECIES_COLOR[sp],
                label=SPECIES_LABEL[sp],
            )

        ax.set_xticks(x)
        ax.set_xticklabels(SITE_ORDER, fontsize=PLOT_CFG["tick_size"])
        ylab_size = PLOT_CFG["fig4_ylabel_panelB"] if panel_letter == "B" else PLOT_CFG["fig4_ylabel_default"]
        ax.set_ylabel(ylabel, fontsize=ylab_size)
        ax.tick_params(axis="y", labelsize=PLOT_CFG["tick_size"])
        ax.grid(axis="y", alpha=PLOT_CFG["grid_alpha"])
        ax.text(0.02, 0.98, panel_letter, transform=ax.transAxes,
                ha="left", va="top", fontsize=PLOT_CFG["fig4_panel_label_size"], fontweight="bold")

        if idx == 2:
            ax.legend(frameon=False, fontsize=PLOT_CFG["legend_size"], loc=PLOT_CFG["fig4_legend_loc"])

    fig.tight_layout()
    fig.savefig(outdir / "Figure4_ABC_combined.png", dpi=PLOT_CFG["save_dpi"], bbox_inches="tight")
    plt.close(fig)


def plot_supplementary_figures(species_df: pd.DataFrame, compartment: pd.DataFrame, outdir: Path) -> None:
    # S1 A+B
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.6))
    for ax, (col, ylabel, letter) in zip(axes, [
        ("BG_Biomass_Fraction_pct", "BG biomass fraction (%)", "A"),
        ("BG_C_Fraction_pct", "BG carbon fraction (%)", "B"),
    ]):
        data = [species_df[species_df["Species"] == sp][col] for sp in SPECIES_ORDER]
        bp = ax.boxplot(data, patch_artist=True, showfliers=True)
        for patch, sp in zip(bp["boxes"], SPECIES_ORDER):
            patch.set_facecolor(SPECIES_COLOR[sp]); patch.set_alpha(0.8)
        ax.set_xticklabels([SPECIES_LABEL[sp] for sp in SPECIES_ORDER], fontstyle="italic", fontsize=PLOT_CFG["tick_size"])
        ax.set_ylabel(ylabel, fontsize=PLOT_CFG["label_size"])
        ax.tick_params(axis="y", labelsize=PLOT_CFG["tick_size"])
        ax.grid(axis="y", alpha=PLOT_CFG["grid_alpha"])
        ax.text(0.02, 0.98, letter, transform=ax.transAxes, ha="left", va="top", fontsize=16, fontweight="bold")
    fig.tight_layout()
    fig.savefig(outdir / "FigureS1_AB_combined.png", dpi=PLOT_CFG["save_dpi"], bbox_inches="tight")
    plt.close(fig)

    # S2 A+B
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.6))
    for ax, (col, ylabel, letter) in zip(axes, [
        ("Total_Biomass", "Total biomass (g DW m$^{-2}$)", "A"),
        ("Total_CStock", "Total C stock (g C m$^{-2}$)", "B"),
    ]):
        data = [species_df[species_df["Site"] == site][col] for site in SITE_ORDER]
        bp = ax.boxplot(data, patch_artist=True, showfliers=True)
        for patch, site in zip(bp["boxes"], SITE_ORDER):
            patch.set_facecolor(SITE_COLOR[site]); patch.set_alpha(0.8)
        ax.set_xticklabels(SITE_ORDER, fontsize=PLOT_CFG["tick_size"])
        ax.set_ylabel(ylabel, fontsize=PLOT_CFG["label_size"])
        ax.tick_params(axis="y", labelsize=PLOT_CFG["tick_size"])
        ax.grid(axis="y", alpha=PLOT_CFG["grid_alpha"])
        ax.text(0.02, 0.98, letter, transform=ax.transAxes, ha="left", va="top", fontsize=16, fontweight="bold")
    fig.tight_layout()
    fig.savefig(outdir / "FigureS2_AB_combined.png", dpi=PLOT_CFG["save_dpi"], bbox_inches="tight")
    plt.close(fig)

    # S3 A+B+C+D
    fig, axes = plt.subplots(2, 2, figsize=(14.5, 11.0))
    axes = axes.flatten()
    rels = [
        ("Density", "Shoot density (shoots m$^{-2}$)", "A"),
        ("LeafArea_cm2", "Estimated leaf area per shoot (cm$^2$ shoot$^{-1}$)", "B"),
        ("Estimated_LAI", "Estimated LAI", "C"),
        ("BG_Biomass_Fraction_pct", "BG biomass fraction (%)", "D"),
    ]
    for ax, (xcol, xlabel, letter) in zip(axes, rels):
        for sp in SPECIES_ORDER:
            sub = species_df[species_df["Species"] == sp]
            ax.scatter(sub[xcol], sub["Total_CStock"], color=SPECIES_COLOR[sp], s=44, alpha=0.85, label=SPECIES_LABEL[sp])
        ax.set_xlabel(xlabel, fontsize=PLOT_CFG["label_size"])
        ax.set_ylabel("Total C stock (g C m$^{-2}$)", fontsize=PLOT_CFG["label_size"])
        ax.tick_params(axis="both", labelsize=PLOT_CFG["tick_size"])
        ax.grid(alpha=PLOT_CFG["grid_alpha"])
        ax.text(0.02, 0.98, letter, transform=ax.transAxes, ha="left", va="top", fontsize=16, fontweight="bold")
    axes[0].legend(frameon=False, fontsize=PLOT_CFG["legend_size"], loc="best")
    fig.tight_layout()
    fig.savefig(outdir / "FigureS3_ABCD_combined.png", dpi=PLOT_CFG["save_dpi"], bbox_inches="tight")
    plt.close(fig)

    # S4 A+B
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.6))
    for ax, (col, xlabel, letter, color) in zip(axes, [
        ("LOI_pct", "LOI (%)", "A", "#7DA9D1"),
        ("Corg_pct", "LOI-derived %Corg", "B", "#F2B880"),
    ]):
        ax.hist(compartment[col], bins=12, color=color, edgecolor="white")
        ax.set_xlabel(xlabel, fontsize=PLOT_CFG["label_size"])
        ax.set_ylabel("Frequency", fontsize=PLOT_CFG["label_size"])
        ax.tick_params(axis="both", labelsize=PLOT_CFG["tick_size"])
        ax.grid(axis="y", alpha=PLOT_CFG["grid_alpha"])
        ax.text(0.02, 0.98, letter, transform=ax.transAxes, ha="left", va="top", fontsize=16, fontweight="bold")
    fig.tight_layout()
    fig.savefig(outdir / "FigureS4_AB_combined.png", dpi=PLOT_CFG["save_dpi"], bbox_inches="tight")
    plt.close(fig)


def draw_concept_panel_on_axis(ax, boxes: list, arrows: list, note: str, panel_letter: str) -> None:
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.6)
    ax.axis("off")

    ax.text(0.01, 0.98, panel_letter, transform=ax.transAxes,
            ha="left", va="top", fontsize=PLOT_CFG["s5_panel_letter_size"], fontweight="bold")

    for x, y, w, h, text in boxes:
        patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04",
                               facecolor="white", edgecolor="black", linewidth=PLOT_CFG["s5_box_lw"])
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=PLOT_CFG["s5_text_size"])

    for x1, y1, x2, y2 in arrows:
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", lw=1.2, color="black"))

    if note:
        ax.text(5, 0.35, note, ha="center", va="center", fontsize=PLOT_CFG["s5_note_size"])


def plot_figure_s5(outdir: Path) -> None:
    # Vertical A-B-C
    fig, axes = plt.subplots(3, 1, figsize=PLOT_CFG["s5_size_vertical"])

    draw_concept_panel_on_axis(
        axes[0],
        boxes=[
            (1.0, 1.8, 2.8, 1.05, "Meadow presence / cover /\nshoot density"),
            (5.2, 1.8, 2.8, 1.05, "Assumed carbon\ncontribution"),
        ],
        arrows=[(3.85, 2.33, 5.15, 2.33)],
        note="Risk: species effects and biomass allocation are obscured.",
        panel_letter="A",
    )

    draw_concept_panel_on_axis(
        axes[1],
        boxes=[
            (0.4, 1.6, 1.6, 1.1, "Species\ncomposition"),
            (2.3, 1.6, 2.0, 1.1, "Structural traits\n(density, leaf area,\nestimated LAI)"),
            (4.6, 1.6, 2.0, 1.1, "AG/BG biomass\nallocation"),
            (6.9, 1.6, 1.7, 1.1, "Sample-specific\n%Corg"),
            (8.9, 1.6, 0.9, 1.1, "Carbon\nstock"),
        ],
        arrows=[(2.02, 2.15, 2.28, 2.15), (4.32, 2.15, 4.58, 2.15), (6.62, 2.15, 6.88, 2.15), (8.62, 2.15, 8.88, 2.15)],
        note="",
        panel_letter="B",
    )

    draw_concept_panel_on_axis(
        axes[2],
        boxes=[
            (0.2, 2.55, 1.45, 0.85, "Biomass\ncarbon"),
            (1.95, 2.55, 2.0, 0.85, "Sediment Corg +\ndry bulk density"),
            (4.25, 2.55, 1.45, 0.85, "Sediment\ndepth"),
            (6.0, 2.55, 1.45, 0.85, "Meadow\nextent"),
            (7.75, 2.55, 1.95, 0.85, "Temporal\nmonitoring /\nburial rate"),
            (3.1, 0.90, 3.8, 0.85, "Total ecosystem blue carbon stock\n(not estimated in the present study)"),
        ],
        arrows=[(1.67, 2.98, 1.93, 2.98), (3.97, 2.98, 4.23, 2.98), (5.72, 2.98, 5.98, 2.98),
                (7.47, 2.98, 7.73, 2.98), (4.99, 2.50, 4.99, 1.80)],
        note="Sediment-integrated accounting remains a future step.",
        panel_letter="C",
    )

    fig.tight_layout()
    fig.savefig(outdir / "FigureS5_ABC_combined_vertical.png", dpi=PLOT_CFG["save_dpi"], bbox_inches="tight")
    plt.close(fig)


def run_workflow(input_xlsx: Path, output_dir: Path) -> None:
    dirs = ensure_dirs(output_dir)
    set_figure_style()

    print(f"[{SCRIPT_VERSION}] Reading input workbook: {input_xlsx}")
    raw, structural_raw = load_input_workbook(input_xlsx)

    print("Recalculating compartment and structural data...")
    compartment = recalculate_compartment_data(raw)
    structural = recalculate_structural_data(structural_raw)
    species_df = build_species_level_data(compartment, structural)

    save_csv(compartment, dirs["data"] / "compartment_recalculated.csv")
    save_csv(structural, dirs["data"] / "structural_recalculated.csv")
    save_csv(species_df, dirs["data"] / "species_level_recalculated.csv")

    print("Creating tables...")
    tables = {
        "Table1_biomass_allocation": make_table1_biomass(species_df),
        "Table2_biomass_based_carbon_stock": make_table2_cstock(species_df),
        "TableS2_kruskal_wallis": make_table_s2_kruskal(species_df, structural, compartment),
    }
    for name, df in tables.items():
        save_csv(df, dirs["tables"] / f"{name}.csv")

    print("Creating figures...")
    plot_figure4_structural(structural, dirs["figures"])
    plot_supplementary_figures(species_df, compartment, dirs["figures"])
    plot_figure_s5(dirs["figures"])

    summary_lines = [
        f"Seagrass biomass-based blue carbon analysis ({SCRIPT_VERSION})",
        "============================================================",
        f"Script date: {SCRIPT_DATE}",
        f"Input file: {input_xlsx}",
        f"Output folder: {output_dir}",
        "",
        f"Compartment-level observations: {len(compartment)}",
        f"Species-level sampling units: {len(species_df)}",
        "",
        "Generated figure files:",
        "- Figure4_ABC_combined.png",
        "- FigureS1_AB_combined.png",
        "- FigureS2_AB_combined.png",
        "- FigureS3_ABCD_combined.png",
        "- FigureS4_AB_combined.png",
        "- FigureS5_ABC_combined_vertical.png",
    ]
    (output_dir / "RUN_SUMMARY.txt").write_text("\n".join(summary_lines), encoding="utf-8")

    print("\nWorkflow completed.")
    print(f"Outputs written to: {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reproduce seagrass biomass-based blue carbon data processing and combined figures."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("Seagrass_Data_Figures_Tables_Traceable_Workbook.xlsx"),
        help="Path to input Excel workbook.",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("seagrass_python_outputs"),
        help="Output directory.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    args = parse_args()
    run_workflow(args.input, args.outdir)