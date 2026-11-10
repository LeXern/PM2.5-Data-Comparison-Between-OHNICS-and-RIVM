# Compare a sensor with a RIVM reference station:
#   make install
#   make colocation SENSOR=OHN_tw-4222 STATION=NL10821 START=2026-09-19 END=2026-10-01
PY      ?= python3
SENSOR  ?= OHN_tw-4222
STATION ?= NL10821
DAYS    ?= 14
START   ?= $(shell $(PY) -c "import datetime as d; print((d.date.today() - d.timedelta(days=$(DAYS))).isoformat())")
END     ?= $(shell $(PY) -c "import datetime as d; print((d.date.today() + d.timedelta(days=1)).isoformat())")
SENSOR_CSV ?= data/raw/samenmeten_$(SENSOR)_pm25.csv

.PHONY: install test info reference sensor ohnics analysis colocation

install:
	$(PY) -m pip install -r requirements.txt

test:
	$(PY) -m pytest -q

info:                  ## show a Samen Meten sensor's series and nearest reference station
	$(PY) -m pm25colocation.samenmeten --info $(SENSOR)

reference:             ## RIVM hourly PM2.5 at STATION for START..END
	$(PY) -m pm25colocation.rivm --station $(STATION) --start $(START) --end $(END)

sensor:                ## hourly PM2.5 of SENSOR from Samen Meten for START..END
	$(PY) -m pm25colocation.samenmeten --sensor $(SENSOR) --start $(START) --end $(END)

ohnics:                ## recent readings from the Ohnics feed (sensor ID in .env); then use SENSOR_CSV=data/raw/ohnics_$(DAYS)d.csv
	$(PY) -m pm25colocation.ohnics --days $(DAYS)

analysis:              ## compare SENSOR_CSV with the STATION file and draw the charts
	$(PY) -m pm25colocation.colocation --sensor $(SENSOR_CSV) --reference data/raw/rivm_$(STATION)_PM25.csv --sensor-name $(SENSOR)

colocation: reference sensor analysis
