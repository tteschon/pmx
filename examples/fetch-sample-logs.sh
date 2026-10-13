#!/usr/bin/env bash
# Download event logs from the pm4py repository into examples/data/.
#
# The logs are not vendored into this repo: they belong to pm4py (AGPL v3) and
# receipt.xes alone is 4 MB. examples/data/ is gitignored.
#
# tests/test_sample_logs.py pins the figures the docs quote for these logs, so
# the inputs must not move under it: the URL is a pm4py commit rather than a
# branch, and every file is checked against its SHA-256 -- including one
# already on disk, which may be a stale or truncated copy. To move to newer
# logs, change PM4PY_COMMIT, update the hashes, and expect those tests to
# need new numbers.
set -euo pipefail

PM4PY_COMMIT="635d8ff49888ecdf6eece5e729eb0b0ee0710a47"
BASE="https://raw.githubusercontent.com/process-intelligence-solutions/pm4py/${PM4PY_COMMIT}/tests/input_data"
DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/data"

# Small, hand-built teaching log (6 cases) through to a real municipality
# process (1434 cases) -- enough range to see where a discovered model stops
# being readable.
LOGS=(
  "663cd7b1da01cd024291e527a46079e0e7676fcf3a81ca8f5dee070b073c5df9  running-example.xes"
  "9adbd697dfb047f657c16391ddfe54cbea89c664e3a5d64c36a110742760c355  running-example.csv"
  "68db5ea68726096978809a6d8503bba333303dbaac457354b8733b5b198f8d39  receipt.xes"
  "ef6879f823acb00d7e856a7810ddb330603367af95210524a1e30f982ffa6766  roadtraffic100traces.xes"
  "fb133a5b70711d523bdbb95279d6bd86d975661ad3d23d23129bfe5121cea453  helpdesk.xes.gz"
)

verify() {
  (cd "$DEST" && echo "$1" | shasum -a 256 --check --status)
}

mkdir -p "$DEST"
for entry in "${LOGS[@]}"; do
  log="${entry##* }"
  if [[ -f "$DEST/$log" ]] && verify "$entry"; then
    echo "have  $log"
    continue
  fi
  echo "fetch $log"
  curl -fsSL "$BASE/$log" -o "$DEST/$log"
  if ! verify "$entry"; then
    echo "error: $log does not match its pinned SHA-256" >&2
    exit 1
  fi
done

echo
echo "Logs in $DEST:"
ls -lh "$DEST"
