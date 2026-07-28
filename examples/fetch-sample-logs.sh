#!/usr/bin/env bash
# Download event logs from the pm4py repository into examples/data/.
#
# The logs are not vendored into this repo: they belong to pm4py (AGPL v3) and
# receipt.xes alone is 4 MB. examples/data/ is gitignored.
set -euo pipefail

BASE="https://raw.githubusercontent.com/process-intelligence-solutions/pm4py/release/tests/input_data"
DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/data"

# Small, hand-built teaching log (6 cases) through to a real municipality
# process (1434 cases) -- enough range to see where a discovered model stops
# being readable.
LOGS=(
  running-example.xes
  running-example.csv
  receipt.xes
  roadtraffic100traces.xes
  helpdesk.xes.gz
)

mkdir -p "$DEST"
for log in "${LOGS[@]}"; do
  if [[ -f "$DEST/$log" ]]; then
    echo "have  $log"
    continue
  fi
  echo "fetch $log"
  curl -fsSL "$BASE/$log" -o "$DEST/$log"
done

echo
echo "Logs in $DEST:"
ls -lh "$DEST"
