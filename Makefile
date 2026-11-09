# Download, compare and chart: `make install`, then `make colocation DAYS=7`.
PY    ?= python3
DAYS  ?= 7
START ?= $(shell $(PY) -c "import datetime as d; print((d.date.today() - d.timedelta(days=$(DAYS) + 1)).isoformat())")
END   ?= $(shell $(PY) -c "import datetime as d; print((d.date.today() + d.timedelta(days=1)).isoformat())")

.PHONY: install test reference sensor analysis colocation

install:
	$(PY) -m pip install -r requirements.txt

test:
	$(PY) -m pytest -q

reference:             ## RIVM hourly PM2.5 for START..END (needs internet)
	$(PY) -m pm25colocation.rivm --start $(START) --end $(END)

sensor:                ## Ohnics readings for the last DAYS days (needs internet and .env)
	$(PY) -m pm25colocation.ohnics --days $(DAYS)

analysis:              ## compare the downloaded files and draw the charts
	$(PY) -m pm25colocation.colocation --sensor data/raw/ohnics_$(DAYS)d.csv --reference data/raw/rivm_NL10821_PM25.csv

colocation: reference sensor analysis
