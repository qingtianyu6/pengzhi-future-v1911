# Environment Forecast V0.1 Model Card

## Purpose
Forecast greenhouse air temperature, relative humidity and PAR for hours 1–6 from the previous 24 hourly observations. Status: **under_evaluation**; selected model: **gru**.

## Data and licence
Trained on Autonomous Greenhouse Challenge, Second Edition (2019), cherry tomato, Netherlands, DOI `10.4121/uuid:88d22c60-21b3-4ea8-90db-20249a5be2a7`, CC0 1.0. The fourth challenge dwarf-tomato data is reported separately as external validation.

## Inputs and outputs
Inputs are hourly temperature, relative humidity and cyclical time features over 24 hours. Outputs are temperature (°C), humidity (%) and PAR (µmol/m²/s) at six horizons. Validation residual 5th/95th percentiles form empirical prediction intervals. All preprocessing statistics are fitted on training data only.

## Evaluation
Time split is 70%/15%/15% within each compartment. Full per-target/per-horizon metrics are in `metrics.json` and `model_comparison.csv`; no test data were used for parameter search. Selected formal model wins 14/18 target-horizon comparisons against persistence with mean relative MAE improvement 20.40%.

## Limitations and prohibited uses
This is public real tomato-greenhouse validation, not Shenxian melon field validation. It is not suitable for direct device control, safety-critical automation, non-hourly inputs, missing 24-hour histories, or interpreting PAR as klx. It cannot replace an agronomist. Tomato risk rules are unavailable, so the API returns `rules_unavailable`. Cross-crop use requires local calibration; Shenxian melon calibration still needs representative local sensor data, units, management actions and outcomes. Model version: v0.1.
