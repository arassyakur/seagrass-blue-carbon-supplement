# Seagrass Blue Carbon Supplementary Code (West Bali National Park)

This repository contains the supplementary Python script used for biomass-based blue carbon analysis in seagrass meadows from West Bali National Park.

## Main file
- `Seagrass_blue_carbon_statistics_v1.0.py`

## Input workbook (expected default name)
- `Seagrass_Data_Figures_Tables_Traceable_Workbook.xlsx`

Required sheets:
1. `Raw_Compartment_Data`
2. `Structural_Data`

## Required columns

### Sheet: Raw_Compartment_Data
- SampleID
- Site
- Line
- Species
- Part
- PartLabel
- Wet_g
- Dry_g
- Ash_g

### Sheet: Structural_Data
- SampleID
- Site
- Line
- Species
- Shoot_count
- Density
- Substrate
- LeafArea_cm2
- Estimated_LAI
- Pressure_Category

## How to run

```bash
python Seagrass_blue_carbon_statistics_v1.0.py --input Seagrass_Data_Figures_Tables_Traceable_Workbook.xlsx --outdir seagrass_python_outputs
```
