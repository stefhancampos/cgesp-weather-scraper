#!/bin/sh

cd /app/scraper

python3 cgesp_scraper.py \
    --station_code "${STATION_CODE:-1000840}" \
    --scan_interval "${SCAN_INTERVAL:-3600}" \
    --ha_url "${HA_URL:-http://supervisor/core}" \
    --ha_token "${HA_TOKEN}"