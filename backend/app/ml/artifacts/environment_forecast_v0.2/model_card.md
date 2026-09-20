# Environment Forecast V0.2 Model Card

## Status
Forecast service: **ready**. Registered methods are selected per target and horizon from three rolling validation folds and may include the honest `seasonal_24` baseline. ML candidate: **ready**. A ready forecast service does not imply that deep learning passed validation.

## Data
Autonomous Greenhouse Challenge, Second Edition (2019), cherry tomato, Bleiswijk, Netherlands; DOI `10.4121/uuid:88d22c60-21b3-4ea8-90db-20249a5be2a7`; CC0 1.0. V0.1 artifacts and its `under_evaluation` conclusion are preserved. AGC4 is a repeated external benchmark, not a new unseen test.

## Method
The seasonal baseline for horizon h is the observed value at target time minus 24 hours. Residual models learn `actual - seasonal`; recurrent models contain an explicit skip connection. Champions are selected by rolling-validation MAE, then RMSE/stability and simplicity within 1%. Prediction intervals are rolling-residual 5th/95th percentiles.

## Product contract
Deployment-compatible temperature/humidity uses only SQLite-available 24-hour temperature, humidity and time features. Research-rich historical weather and controls are `research_only`. PAR is trained and reported separately in µmol/m²/s; SQLite klx never enters that model and API PAR is null.

## Limitations
Not locally calibrated for Shenxian melon; statistical extremes are not crop risks; tomato rules are unavailable; no automatic hardware control; predictions do not replace agronomic judgment.
