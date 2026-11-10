# PM2.5 Data Comparison Between OHNICS and RIVM

Compares a low-cost PM2.5 sensor with a RIVM reference station and draws the charts. It is part of an MSc thesis at ITC, University of Twente, on combining static, bicycle and UAV low-cost sensors. Before the field campaign, each sensor's error has to be known against a reference, and this repository does that comparison.

It was built for Ohnics sensors in Twente against the Enschede-Winkelshorst station. It works for any sensor on RIVM's Samen Meten portal and any Luchtmeetnet station in the Netherlands (see [Using it elsewhere](#using-it-elsewhere)).

**What you need:** Python 3.12 or 3.13 (the versions it was tested with) and an internet connection. No login is needed except for the Ohnics dashboard. For a few weeks of data, each command below finishes within a minute.

**Contents:** [Windows](#setup-on-windows) · [macOS and Linux](#setup-on-macos-and-linux) · [Data sources](#where-the-data-comes-from) · [Using it elsewhere](#using-it-elsewhere) · [How the comparison works](#how-the-comparison-works) · [Troubleshooting](#troubleshooting)

## Setup on Windows

These steps use Command Prompt and need no extra software besides Python.

**1. Check Python.** Press the Windows key, type `cmd`, press Enter, and run:

```
python --version
```

It should print `Python 3.12` or `Python 3.13`. Newer versions may work, but some packages may not support them yet. If it says `'python' is not recognized`, install Python from [python.org/downloads](https://www.python.org/downloads/). On the first screen of the installer, tick **Add python.exe to PATH**. Then close Command Prompt, open a new one and check again.

**2. Download the code.** On this page, click the green **Code** button, then **Download ZIP**. In File Explorer, right-click the ZIP in your Downloads folder, choose **Extract All…**, and extract it to your Documents folder. This creates the folder `PM2.5-Data-Comparison-Between-OHNICS-and-RIVM-main`.

If you have git installed, you can instead run `git clone https://github.com/LeXern/PM2.5-Data-Comparison-Between-OHNICS-and-RIVM.git`. The folder is then called `PM2.5-Data-Comparison-Between-OHNICS-and-RIVM`, without `-main`.

**3. Set up a separate Python environment for this project.** In Command Prompt, run these one at a time. Replace `<you>` with your Windows user name; `cd %USERPROFILE%\Documents` also works.

```
cd C:\Users\<you>\Documents\PM2.5-Data-Comparison-Between-OHNICS-and-RIVM-main
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q
```

- After `activate`, the line in Command Prompt starts with `(.venv)`. All later commands must run while it shows `(.venv)`.
- `pip install` downloads the exact package versions this project was tested with. It takes one to two minutes the first time.
- The last command runs the tests. It should end with `13 passed`.

**4. Run a first comparison** (FieldLab tower sensor against Enschede-Winkelshorst, 19–30 September 2026):

```
python -m pm25colocation.rivm --start 2026-09-19 --end 2026-10-01
python -m pm25colocation.samenmeten --sensor OHN_tw-4222 --start 2026-09-19 --end 2026-10-01
python -m pm25colocation.colocation --sensor data\raw\samenmeten_OHN_tw-4222_pm25.csv --reference data\raw\rivm_NL10821_PM25.csv --sensor-name OHN_tw-4222
```

The last command prints `lag -1 h` and the location of the report. It writes:

- **`results\colocation_report.html`: start here.** One page with all tables and charts and a short explanation of each. Double-click it in File Explorer and it opens in your web browser. No other software is needed.
- `results\colocation_stats.csv`: the numbers as a spreadsheet, for further work. It opens in Excel, LibreOffice Calc or Google Sheets (File → Import); without one of those, it opens as plain text.
- `results\colocation_summary.md`: the same tables as plain text in Markdown. Notepad shows it with the table markup visible; editors such as VS Code can show it formatted. You do not need this file if you use the report.
- `figures\colocation_timeseries.png`, `figures\colocation_scatter.png` and `figures\colocation_ratio_by_concentration.png`: the charts as separate images, for slides or documents. They open in any image viewer.

For this example the report should show a bias of about −1.6 µg/m³ and R² of 0.85 (hourly), 0.88 (4-hourly) and 0.96 (daily).

**Every later session:** open Command Prompt, run the `cd` line from step 3, then `.venv\Scripts\activate`. Steps 1–3 only need doing once.

## Setup on macOS and Linux

In a terminal:

```bash
git clone https://github.com/LeXern/PM2.5-Data-Comparison-Between-OHNICS-and-RIVM.git
cd PM2.5-Data-Comparison-Between-OHNICS-and-RIVM
python3 -m venv .venv
source .venv/bin/activate
make install
make test
make colocation SENSOR=OHN_tw-4222 STATION=NL10821 START=2026-09-19 END=2026-10-01
```

`make colocation` runs the three commands from Windows step 4 in one go. Open `results/colocation_report.html` in a browser to see the results. The other `make` targets are listed in the [Makefile](Makefile): `info`, `reference`, `sensor`, `ohnics` and `analysis`. Each takes the settings `SENSOR`, `STATION`, `START`, `END` and `DAYS`. Without `START` and `END`, the last 14 days are used. Every `make` target is a shortcut for one of the `python -m …` commands shown in this README, so those work on macOS and Linux too.

## Where the data comes from

| Source | What it gives | Access | Command |
|---|---|---|---|
| RIVM [Luchtmeetnet](https://www.luchtmeetnet.nl) | Hourly reference PM2.5 from any national station | Open | `python -m pm25colocation.rivm --station NL10821 --start 2026-09-19 --end 2026-10-01` |
| RIVM [Samen Meten](https://samenmeten.rivm.nl/dataportaal/) | Hourly PM2.5 from citizen and research sensors for any date range, including every Ohnics unit (names start with `OHN_`). Both the sensor's own values and RIVM's calibrated version | Open | `python -m pm25colocation.samenmeten --sensor OHN_tw-4222 --start 2026-09-19 --end 2026-10-01` |
| Ohnics open feed | Recent readings only: 10-minute values for the last day, hourly for the last 7 or 14 days, coarser beyond | Open, but needs the sensor ID in `.env` (see [below](#ohnics-open-feed)) | `python -m pm25colocation.ohnics --days 7` |
| Ohnics dashboard | 1-minute readings for any date range | Login from the sensor's owner | Download the CSV from the dashboard, then see [Your own CSV](#your-own-csv) |

Samen Meten is the main route because it is open and covers any period. The Ohnics feed is a quick check of the last few days. The dashboard has the finest data, but only people with a login can use it.

The values from Samen Meten (`pm25`) and from the Ohnics feed are the sensor's own readings, without RIVM's correction. To compare RIVM's calibrated series (`pm25_kal`) instead, add `--calibrated` to the Samen Meten command; the file is then named `..._pm25_kal.csv`.

**Dates:** `--start` and `--end` are dates written as `YYYY-MM-DD`, in UTC. The end date is not included, so `--start 2026-09-19 --end 2026-10-01` covers 19 up to and including 30 September. The reference download must cover the same dates as the sensor download.

### Ohnics open feed

The feed needs the sensor's ID, which goes in a file called `.env` in the project folder. The ID is kept out of this repository because some sensors stand at private homes.

On Windows, in the project folder with `(.venv)` active:

```
copy .env.example .env
notepad .env
```

In Notepad, change the line to `OHNICS_SENSOR_ID=` followed by the ID, for example `OHNICS_SENSOR_ID=tw-4222`, with no spaces or quotes. Save with **Ctrl+S** (not *Save As*, which can rename the file to `.env.txt`), then close Notepad. On macOS or Linux, run `cp .env.example .env` and edit the file in any text editor.

Then download a week and compare it with the reference for the same days. Set `--start` to eight days before today and `--end` to tomorrow:

```
python -m pm25colocation.ohnics --days 7
python -m pm25colocation.rivm --start 2026-11-02 --end 2026-11-11
python -m pm25colocation.colocation --sensor data\raw\ohnics_7d.csv --reference data\raw\rivm_NL10821_PM25.csv --sensor-name Ohnics
```

`--days` sets both the period and the resolution: `1` gives 10-minute values for the last day, `7` or `14` hourly values, `30` 4-hourly values, and `90` or `360` daily values. The endpoint is undocumented and may change, so keep the CSV files you analyse.

## Using it elsewhere

### 1. Pick a sensor

Open the [Samen Meten data portal](https://samenmeten.rivm.nl/dataportaal/), find the sensor on the map or with the search box, and note its name exactly as shown, including capitals (for example `OHN_tw-4222`; other networks use other prefixes). Then run:

```
python -m pm25colocation.samenmeten --info OHN_tw-4222
```

It prints the sensor's series, its location and the reference stations RIVM pairs it with. The first one, `Nearest PM2.5 reference station`, is the one to use in step 2.

### 2. Pick the reference station

Use the station code from step 1. To choose another station, find it on [luchtmeetnet.nl](https://www.luchtmeetnet.nl/stations); its code is the `NL…` number on the station's page. Many stations only measure NO₂ or PM10, so check that it measures PM2.5: open `https://api.luchtmeetnet.nl/open_api/stations/<code>` in a browser and look for `"PM25"` in the `components` list.

### 3. Run it

Replace the sensor name, station code and dates:

```
python -m pm25colocation.rivm --station NL10821 --start 2026-09-19 --end 2026-10-01
python -m pm25colocation.samenmeten --sensor OHN_tw-4222 --start 2026-09-19 --end 2026-10-01
python -m pm25colocation.colocation --sensor data\raw\samenmeten_OHN_tw-4222_pm25.csv --reference data\raw\rivm_NL10821_PM25.csv --sensor-name OHN_tw-4222
```

The download commands print the name of the file they wrote; use those names in the last command. On macOS and Linux, write the paths with `/` instead of `\`, or use `make colocation SENSOR=… STATION=… START=… END=…`.

Each run overwrites the files in `results` and `figures`. To keep a run, copy those two folders somewhere else first. The HTML report contains its charts, so copying `colocation_report.html` alone is enough to keep the full result.

### 4. Reference periods

`config/reference_periods.json` splits the statistics at an instrument change. It belongs to station NL10821, where a BAM-1020 was replaced by a Palas Fidas 200 on 18 September 2026. For any other station it is skipped, and the comparison prints a line saying so. If your station also changed instruments, copy the file, set `station` and the periods, and add `--periods your_file.json` to the comparison command. If it did not, nothing needs doing.

### Your own CSV

Any CSV with one column of times and one of PM2.5 values works, for example an Ohnics dashboard export. Tell the comparison the exact column names, as written in the first row of the file:

```
python -m pm25colocation.colocation --sensor my_export.csv --time-col "timestamp" --pm-col "pm2_5" --sensor-tz Europe/Amsterdam --reference data\raw\rivm_NL10821_PM25.csv --sensor-name "Ohnics dashboard"
```

- `--time-col` and `--pm-col`: the column names. Put them in quotes if they contain spaces.
- `--sensor-tz`: the time zone of the times, used only when they carry none (no `Z` or `+01:00` at the end). Use `Europe/Amsterdam` for Dutch local time and `UTC` for UTC.
- Download the reference for the same dates first, with the `rivm` command above.

## How the comparison works

- **Time base.** Luchtmeetnet stamps each hourly value at the end of its hour, in UTC. Sensor data at one hour or finer is averaged into hours stamped the same way. Coarser sensor data is compared with the reference averaged over the same interval.
- **Time offset.** Sources label their hours differently: Samen Meten stamps the end of the hour, and the Ohnics feed the start. The script tests offsets of −2 to +3 hours and applies the one with the highest R². It prints the offset it chose (`lag -1 h`), and the summary lists the test. To fix the offset yourself, add `--lag 0` (or another whole number of hours).
- **Aggregation.** 4-hourly and daily means need at least 75 % of their hours.
- **Statistics.** Number of pairs, means, bias, relative bias, RMSE, MAE, R², ordinary least squares, and orthogonal (Deming, λ = 1) regression, as used in EU equivalence testing. The median sensor/reference ratio is reported for concentration bands 0–5, 5–10 and ≥ 10 µg/m³.
- **Charts.** A time series of both sources, scatter plots with the 1:1 line and the fitted line for each resolution, and the sensor/reference ratio by concentration band.

The reference values from the API are provisional until RIVM validates them. To use a validated monthly file instead, save it as a CSV with the columns `time` (end of the hour, UTC), `value` and `station`, and pass it with `--reference`.

## Troubleshooting

| Message | Cause and fix |
|---|---|
| `PermissionError` when writing a file | The file is open in another program, usually a CSV in Excel. Windows does not let a file be overwritten while another program has it open. Close it and run the command again. |
| `'python' is not recognized` | Python is not installed or not on PATH. See Windows step 1. |
| `No module named pm25colocation` | The command was run outside the project folder. `cd` into it first. |
| `No module named pandas` (or another package) | The environment is not active. Run `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (macOS/Linux). |
| `Set OHNICS_SENSOR_ID in your environment or in .env` | `.env` is missing or has another name. Run `dir /a` (Windows) or `ls -a` (macOS/Linux) in the project folder: the file must be listed as `.env`, not `.env.txt`. If it is `.env.txt`, run `ren .env.txt .env`. |
| `No sensor called … on Samen Meten` | The name is misspelled. Copy it exactly from the portal, including capitals. |
| `HTTPError: 400 Client Error` or `503` | The server had a short hiccup. The scripts already try each request up to four times; if it still fails, wait a minute and run the command again. |
| `sensor and reference do not overlap in time` | The two files cover different dates. Download both for the same `--start` and `--end`. |
| `reference periods … are for NL10821, not …` | Information only: the instrument split is skipped for other stations. See [Reference periods](#4-reference-periods). |

## Privacy

Some sensors stand at private homes. Downloaded sensor files (`data/raw/ohnics_*`, `data/raw/samenmeten_*`) and `.env` are ignored by git. Publish a sensor's data only with its owner's consent.

## Layout

```
config/reference_periods.json   instrument periods at NL10821
pm25colocation/rivm.py          Luchtmeetnet reference download
pm25colocation/samenmeten.py    Samen Meten sensor download and sensor info
pm25colocation/ohnics.py        Ohnics open-feed download
pm25colocation/colocation.py    alignment, statistics, charts, HTML report and summary
pm25colocation/_http.py         retries for the downloads
tests/                          automated tests, with small API samples in tests/fixtures/
```

## Data sources and licences

- **Reference data:** RIVM, Luchtmeetnet open API. Cite RIVM/Luchtmeetnet when you use it.
- **Sensor data:** RIVM Samen Meten and Ohnics. Not redistributed here.
- **Code:** MIT licence, see [LICENSE](LICENSE).
