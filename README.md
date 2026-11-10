# PM2.5 Data Comparison Between OHNICS and RIVM

Compares a low-cost PM2.5 sensor with a RIVM reference station and draws the charts. It is part of an MSc thesis at ITC, University of Twente, on combining static, bicycle and UAV low-cost sensors. Before the field campaign, each sensor's error has to be known against a reference, and this repository does that comparison.

It was built for Ohnics sensors in Twente against the Enschede-Winkelshorst station. It works for any sensor on RIVM's Samen Meten portal and any Luchtmeetnet station in the Netherlands (see [Using it elsewhere](#using-it-elsewhere)).

## Quick start

```bash
git clone https://github.com/LeXern/PM2.5-Data-Comparison-Between-OHNICS-and-RIVM.git
cd PM2.5-Data-Comparison-Between-OHNICS-and-RIVM
python3 -m venv .venv && source .venv/bin/activate
make install                 # pinned package versions from requirements.txt
make test
make colocation SENSOR=OHN_tw-4222 STATION=NL10821 START=2026-09-19 END=2026-10-01
```

The last command downloads both datasets, compares them and writes `results/colocation_summary.md`, `results/colocation_stats.csv` and three charts in `figures/`. No login is needed.

## Where the data comes from

| Source | What it gives | Access | Command |
|---|---|---|---|
| RIVM [Luchtmeetnet](https://www.luchtmeetnet.nl) | Hourly reference PM2.5 from any national station | Open | `make reference STATION=… START=… END=…` |
| RIVM [Samen Meten](https://samenmeten.rivm.nl/dataportaal/) | Hourly PM2.5 from citizen and research sensors, including every Ohnics unit (`OHN_…`), for any date range. Both the sensor's own values and RIVM's calibrated version | Open | `make sensor SENSOR=… START=… END=…` |
| Ohnics open feed | Recent readings only: 10-minute values for the last day, hourly for the last 7–14 days, coarser beyond | Open; needs the sensor ID in `.env` | `make ohnics DAYS=7` |
| Ohnics dashboard | 1-minute readings for any date range | Login, given by the sensor owner | Download the CSV there, then see [Your own CSV](#your-own-csv) |

Samen Meten is the main route because it is open and covers any period. The Ohnics feed is a quick check of the last few days. The dashboard has the finest data, but only people with a login can use it.

The Ohnics values on Samen Meten (`pm25`) and from the Ohnics feed are the sensor's own readings, without RIVM's correction. Use `--calibrated` with the Samen Meten download to compare RIVM's calibrated series (`pm25_kal`) instead.

## Using it elsewhere

### 1. Pick a sensor

Find it on the [Samen Meten data portal](https://samenmeten.rivm.nl/dataportaal/) map. Its name looks like `OHN_tw-4222` for Ohnics units, and other networks use other prefixes. Then:

```bash
make info SENSOR=OHN_tw-4222
```

This prints the sensor's series, its location and **the nearest PM2.5 reference station that RIVM itself pairs it with** (`pm25closecode`).

### 2. Pick the reference station

Use the station code from step 1, or choose one on [luchtmeetnet.nl](https://www.luchtmeetnet.nl/stations): the code is the `NL…` number on the station's page. Check that the station measures PM2.5, because many stations only measure NO₂ or PM10. The station's page lists its components, as does `https://api.luchtmeetnet.nl/open_api/stations/<code>`.

### 3. Run it

```bash
make colocation SENSOR=OHN_tw-4222 STATION=NL10821 START=2026-09-19 END=2026-10-01
```

`START` and `END` are dates in UTC; `END` is not included. Without them the last 14 days are used.

### 4. Reference periods

`config/reference_periods.json` splits the statistics at an instrument change. It belongs to NL10821, where a BAM-1020 was replaced by a Palas Fidas 200 on 18 September 2026, and it is skipped automatically for any other station. If your station changed instruments too, copy the file, set `station` and the periods, and pass it with `--periods`. Otherwise nothing needs doing.

### Your own CSV

Any CSV with a time column and a PM2.5 column works, for example a dashboard export:

```bash
python -m pm25colocation.colocation \
    --sensor my_export.csv --time-col "timestamp" --pm-col "pm2_5" --sensor-tz Europe/Amsterdam \
    --reference data/raw/rivm_NL10821_PM25.csv --sensor-name "Ohnics (dashboard)"
```

`--sensor-tz` matters only when the times carry no time zone. Run `make reference` first for the same dates.

## How the comparison works

- **Time base.** Luchtmeetnet stamps each hourly value at the end of its hour, in UTC. Sensor data at one hour or finer is averaged into hours stamped the same way. Coarser sensor data is compared with the reference averaged over the same interval.
- **Time offset.** The script tests offsets of −2 to +3 hours and applies the one with the highest R², unless `--lag` fixes it. A non-zero offset usually means the two sources label their intervals differently. The summary reports the test.
- **Aggregation.** 4-hourly and daily means need at least 75 % of their hours.
- **Statistics.** Number of pairs, means, bias, relative bias, RMSE, MAE, R², ordinary least squares, and orthogonal (Deming, λ = 1) regression, as used in EU equivalence testing. The median sensor/reference ratio is reported for concentration bands 0–5, 5–10 and ≥ 10 µg/m³.
- **Charts.** A time series of both sources, scatter plots with the 1:1 line and the fitted line for each resolution, and the sensor/reference ratio by concentration band.

API values are provisional until RIVM validates them. To use a validated monthly file instead, convert it to the same columns (`time` at the end of the hour in UTC, `value`, `station`) and pass it with `--reference`.

## Privacy

Some sensors stand at private homes. Downloaded sensor files (`data/raw/ohnics_*`, `data/raw/samenmeten_*`) and `.env` are ignored by git. Publish a sensor's data only with its owner's consent.

## Layout

```
config/reference_periods.json   instrument periods at NL10821
pm25colocation/rivm.py          Luchtmeetnet reference download
pm25colocation/samenmeten.py    Samen Meten sensor download and sensor info
pm25colocation/ohnics.py        Ohnics open-feed download
pm25colocation/colocation.py    alignment, statistics, summary and charts
tests/                          pytest suite with small API samples in tests/fixtures/
```

## Data sources and licences

- **Reference data:** RIVM, Luchtmeetnet open API. Cite RIVM/Luchtmeetnet when you use it.
- **Sensor data:** RIVM Samen Meten and Ohnics. Not redistributed here.
- **Code:** MIT licence, see [LICENSE](LICENSE).
