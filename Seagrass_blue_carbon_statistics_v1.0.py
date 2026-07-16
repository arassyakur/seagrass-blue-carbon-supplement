#!/usr/bin/env python3

from __future__ import annotations

import argparse
import math
import re
import statistics
import sys
from pathlib import Path

from openpyxl import Workbook, load_workbook

REQUIRED_COLUMNS = ("site", "species", "biomass_g_m2", "carbon_fraction")
OPTIONAL_COLUMNS = ("station", "transect", "sample_id", "area_ha", "notes")
SUMMARY_HEADERS = (
    "group",
    "sample_count",
    "mean_biomass_g_m2",
    "sd_biomass_g_m2",
    "min_biomass_g_m2",
    "max_biomass_g_m2",
    "mean_carbon_stock_mg_c_ha",
    "sd_carbon_stock_mg_c_ha",
    "min_carbon_stock_mg_c_ha",
    "max_carbon_stock_mg_c_ha",
    "total_carbon_mg_c",
)


class WorkbookValidationError(ValueError):
    pass


def normalize_header(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run descriptive seagrass blue carbon statistics from an Excel workbook."
    )
    parser.add_argument("workbook", help="Path to the input .xlsx workbook")
    parser.add_argument(
        "--output",
        help="Path to the output .xlsx workbook (default: <input>_statistics.xlsx)",
    )
    return parser.parse_args()


def load_observations(workbook_path: Path) -> list[dict[str, object]]:
    workbook = load_workbook(workbook_path, data_only=True)
    sheet = workbook["observations"] if "observations" in workbook.sheetnames else workbook.active

    header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if not header_row:
        raise WorkbookValidationError("The workbook does not contain a header row.")

    header_lookup: dict[str, int] = {}
    ordered_headers: list[str] = []
    for index, cell_value in enumerate(header_row):
        normalized = normalize_header(cell_value)
        if not normalized:
            continue
        if normalized not in header_lookup:
            header_lookup[normalized] = index
            ordered_headers.append(normalized)

    missing = [column for column in REQUIRED_COLUMNS if column not in header_lookup]
    if missing:
        raise WorkbookValidationError(
            "The workbook is missing required columns: " + ", ".join(missing)
        )

    observations: list[dict[str, object]] = []
    for row_number, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
        if all(value in (None, "") for value in row):
            continue

        observation = {
            column: row[index] if index < len(row) else None
            for column, index in header_lookup.items()
        }
        observation["site"] = str(observation["site"]).strip()
        observation["species"] = str(observation["species"]).strip()

        if not observation["site"] or not observation["species"]:
            raise WorkbookValidationError(
                f"Row {row_number} must contain non-empty site and species values."
            )

        biomass = parse_number(observation["biomass_g_m2"], row_number, "biomass_g_m2")
        carbon_fraction = parse_number(
            observation["carbon_fraction"], row_number, "carbon_fraction"
        )
        if biomass < 0:
            raise WorkbookValidationError(f"Row {row_number} has a negative biomass_g_m2.")
        if not 0 <= carbon_fraction <= 1:
            raise WorkbookValidationError(
                f"Row {row_number} has carbon_fraction outside the range 0-1."
            )

        area = observation.get("area_ha")
        parsed_area = None
        if area not in (None, ""):
            parsed_area = parse_number(area, row_number, "area_ha")
            if parsed_area < 0:
                raise WorkbookValidationError(f"Row {row_number} has a negative area_ha.")

        carbon_stock = biomass * carbon_fraction * 0.01
        total_carbon = carbon_stock * parsed_area if parsed_area is not None else None

        cleaned = {
            column: observation.get(column)
            for column in (*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS)
            if column in observation or column in OPTIONAL_COLUMNS
        }
        cleaned["biomass_g_m2"] = biomass
        cleaned["carbon_fraction"] = carbon_fraction
        cleaned["area_ha"] = parsed_area
        cleaned["carbon_stock_mg_c_ha"] = carbon_stock
        cleaned["total_carbon_mg_c"] = total_carbon
        observations.append(cleaned)

    if not observations:
        raise WorkbookValidationError("The workbook does not contain any observation rows.")

    return observations


def parse_number(value: object, row_number: int, column_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise WorkbookValidationError(
            f"Row {row_number} has a non-numeric value for {column_name}: {value!r}"
        ) from exc

    if math.isnan(number) or math.isinf(number):
        raise WorkbookValidationError(
            f"Row {row_number} has an invalid numeric value for {column_name}: {value!r}"
        )
    return number


def summarize(observations: list[dict[str, object]], key: str) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for observation in observations:
        grouped.setdefault(str(observation[key]), []).append(observation)

    summary_rows: list[dict[str, object]] = []
    for group_name in sorted(grouped):
        rows = grouped[group_name]
        biomasses = [float(row["biomass_g_m2"]) for row in rows]
        carbon_stocks = [float(row["carbon_stock_mg_c_ha"]) for row in rows]
        total_carbon = sum(
            float(row["total_carbon_mg_c"])
            for row in rows
            if row["total_carbon_mg_c"] is not None
        )
        summary_rows.append(
            {
                "group": group_name,
                "sample_count": len(rows),
                "mean_biomass_g_m2": statistics.mean(biomasses),
                "sd_biomass_g_m2": statistics.stdev(biomasses) if len(biomasses) > 1 else 0.0,
                "min_biomass_g_m2": min(biomasses),
                "max_biomass_g_m2": max(biomasses),
                "mean_carbon_stock_mg_c_ha": statistics.mean(carbon_stocks),
                "sd_carbon_stock_mg_c_ha": statistics.stdev(carbon_stocks)
                if len(carbon_stocks) > 1
                else 0.0,
                "min_carbon_stock_mg_c_ha": min(carbon_stocks),
                "max_carbon_stock_mg_c_ha": max(carbon_stocks),
                "total_carbon_mg_c": total_carbon,
            }
        )
    return summary_rows


def overall_summary(observations: list[dict[str, object]]) -> list[tuple[str, object]]:
    biomasses = [float(row["biomass_g_m2"]) for row in observations]
    carbon_stocks = [float(row["carbon_stock_mg_c_ha"]) for row in observations]
    total_carbon = sum(
        float(row["total_carbon_mg_c"])
        for row in observations
        if row["total_carbon_mg_c"] is not None
    )
    return [
        ("sample_count", len(observations)),
        ("site_count", len({str(row["site"]) for row in observations})),
        ("species_count", len({str(row["species"]) for row in observations})),
        ("mean_biomass_g_m2", statistics.mean(biomasses)),
        ("mean_carbon_stock_mg_c_ha", statistics.mean(carbon_stocks)),
        ("total_carbon_mg_c", total_carbon),
    ]


def write_results(output_path: Path, observations: list[dict[str, object]]) -> None:
    workbook = Workbook()

    overall_sheet = workbook.active
    overall_sheet.title = "overall_summary"
    overall_sheet.append(("metric", "value"))
    for row in overall_summary(observations):
        overall_sheet.append(row)

    append_summary_sheet(workbook, "site_summary", summarize(observations, "site"))
    append_summary_sheet(workbook, "species_summary", summarize(observations, "species"))

    observation_headers = [
        "site",
        "station",
        "transect",
        "sample_id",
        "species",
        "biomass_g_m2",
        "carbon_fraction",
        "area_ha",
        "notes",
        "carbon_stock_mg_c_ha",
        "total_carbon_mg_c",
    ]
    observation_sheet = workbook.create_sheet("observations_enriched")
    observation_sheet.append(observation_headers)
    for observation in observations:
        observation_sheet.append([observation.get(header) for header in observation_headers])

    workbook.save(output_path)


def append_summary_sheet(
    workbook: Workbook, sheet_name: str, summary_rows: list[dict[str, object]]
) -> None:
    sheet = workbook.create_sheet(sheet_name)
    sheet.append(SUMMARY_HEADERS)
    for row in summary_rows:
        sheet.append([row[header] for header in SUMMARY_HEADERS])


def main() -> int:
    args = parse_args()
    workbook_path = Path(args.workbook).expanduser().resolve()
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else workbook_path.with_name(f"{workbook_path.stem}_statistics.xlsx")
    )

    try:
        observations = load_observations(workbook_path)
        write_results(output_path, observations)
    except FileNotFoundError:
        print(f"Input workbook not found: {workbook_path}", file=sys.stderr)
        return 1
    except WorkbookValidationError as exc:
        print(f"Workbook validation failed: {exc}", file=sys.stderr)
        return 1

    print(f"Processed {len(observations)} observations.")
    print(f"Results written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
