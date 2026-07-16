# seagrass-blue-carbon-supplement

Supplementary Python script for seagrass biomass-based blue carbon analysis in West Bali National Park (code only; raw data not publicly shared).

## Requirements

- Python 3.10+
- Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Required Excel workbook structure

Prepare a single `.xlsx` workbook with one worksheet named `observations`.
Row 1 must contain the header names. The script normalizes capitalization and
spacing, but the following logical columns are required:

| Column | Required | Description |
| --- | --- | --- |
| `site` | Yes | Site or meadow name for each field observation |
| `species` | Yes | Seagrass species name |
| `biomass_g_m2` | Yes | Biomass in grams per square metre |
| `carbon_fraction` | Yes | Carbon fraction as a decimal between `0` and `1` |
| `station` | No | Station label |
| `transect` | No | Transect label |
| `sample_id` | No | Sample identifier |
| `area_ha` | No | Area represented by the observation in hectares |
| `notes` | No | Free-text notes |

Example worksheet:

| site | station | transect | sample_id | species | biomass_g_m2 | carbon_fraction | area_ha |
| --- | --- | --- | --- | --- | ---: | ---: | ---: |
| Sumber Kima | ST01 | T1 | SK-01 | *Enhalus acoroides* | 825 | 0.36 | 1.5 |
| Sumber Kima | ST01 | T1 | SK-02 | *Thalassia hemprichii* | 640 | 0.34 | 1.5 |
| Banyuwedang | ST02 | T2 | BW-01 | *Cymodocea rotundata* | 455 | 0.31 | 2.0 |

## Run the analysis

```bash
python Seagrass_blue_carbon_statistics_v1.0.py path/to/workbook.xlsx --output path/to/results.xlsx
```

If `--output` is omitted, the script writes
`<input_name>_statistics.xlsx` next to the source workbook.

## Output workbook

The generated workbook contains:

- `overall_summary`: total sample count and aggregate carbon metrics
- `site_summary`: descriptive statistics grouped by site
- `species_summary`: descriptive statistics grouped by species
- `observations_enriched`: original observations plus calculated carbon metrics
