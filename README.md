# PM2.5 Data Comparison Between OHNICS and RIVM

Compares a low-cost PM2.5 sensor with a RIVM reference station and draws the charts. It is part of an MSc thesis at ITC, University of Twente, on combining static, bicycle and UAV low-cost sensors. Before the field campaign, each sensor's error has to be known against a reference, and this repository does that comparison.

The scripts download hourly reference data from RIVM's Luchtmeetnet API and readings from an Ohnics sensor. They align the two time bases and report how well the sensor agrees with the reference at hourly, 4-hourly and daily resolution.

## Quick start

```bash
git clone https://github.com/LeXern/PM2.5-Data-Comparison-Between-OHNICS-and-RIVM.git
cd PM2.5-Data-Comparison-Between-OHNICS-and-RIVM
python3 -m venv .venv && source .venv/bin/activate
make install                 # pinned package versions from requirements.txt
make test
cp .env.example .env         # then fill in OHNICS_SENSOR_ID
make colocation DAYS=7       # download the last week and compare
```

## Steps

| Step | Command | Output |
|---|---|---|
| Download RIVM reference data | `make reference START=2026-09-03 END=2026-11-10` | `data/raw/rivm_NL10821_PM25.csv` |
| Download Ohnics readings | `make sensor DAYS=7` | `data/raw/ohnics_7d.csv` |
| Compare and chart | `make analysis DAYS=7` | `results/colocation_summary.md`, `results/colocation_stats.csv`, `figures/*.png` |

`make colocation` runs all three. Each module also runs on its own, for example:

```bash
python -m pm25colocation.rivm --station NL10821 --formula PM25 --start 2026-09-03 --end 2026-10-01
python -m pm25colocation.colocation --sensor my_sensor.csv --reference data/raw/rivm_NL10821_PM25.csv --lag 0 --periods none
```

Any sensor CSV with the columns `time` (UTC) and `pm25` works with the comparison.

## How the comparison works

- **Time base.** Luchtmeetnet stamps each hourly value at the end of its hour, in UTC. Sensor data at one hour or finer is averaged into hours stamped the same way. Coarser sensor data is compared with the reference averaged over the same interval.
- **Time offset.** The script tests offsets of −2 to +3 hours and applies the one with the highest R², unless `--lag` fixes it. A non-zero offset usually means the two sources label their intervals differently. The summary reports the test.
- **Aggregation.** 4-hourly and daily means need at least 75 % of their hours.
- **Statistics.** Number of pairs, means, bias, relative bias, RMSE, MAE, R², ordinary least squares, and orthogonal (Deming, λ = 1) regression, as used in EU equivalence testing. The median sensor/reference ratio is reported for concentration bands 0–5, 5–10 and ≥ 10 µg/m³.
- **Reference instrument.** `config/reference_periods.json` splits the statistics by instrument. Enschede-Winkelshorst changed from a BAM-1020 to a Palas Fidas 200 on 18 September 2026, and the two agree differently with low-cost sensors.

The charts are a time series of both sources, scatter plots with the 1:1 line and the fitted line for each resolution, and the sensor/reference ratio by concentration band.

API values are provisional until RIVM validates them. To use a validated monthly file instead, convert it to the same columns (`time` at the end of the hour in UTC, `value`) and pass it with `--reference`.

## Ohnics sensor ID

The Ohnics sensor stands at a private home, and its ID leads to its location, so it is not in this repository. Put it in `.env` as `OHNICS_SENSOR_ID`; `.env` and the downloaded Ohnics files are ignored by git.

`DAYS` sets the resolution on Ohnics' side: 1 gives 10-minute values for one day, 7 gives hourly values for a week, 30 gives 4-hourly values and 360 gives daily values. The endpoint is undocumented and may change, so keep the CSV files you analyse.

## Layout

```
config/reference_periods.json   reference-instrument periods at the station
pm25colocation/rivm.py          Luchtmeetnet download
pm25colocation/ohnics.py        Ohnics download
pm25colocation/colocation.py    alignment, statistics, summary and charts
tests/                          pytest suite with small API samples in tests/fixtures/
```

## Data sources and licences

- **Reference data:** RIVM, [Luchtmeetnet](https://www.luchtmeetnet.nl) open API, station NL10821 Enschede-Winkelshorst. Cite RIVM/Luchtmeetnet when you use it.
- **Ohnics data:** downloaded by the user from the sensor's endpoint, and not redistributed here.
- **Code:** MIT licence, see [LICENSE](LICENSE).
