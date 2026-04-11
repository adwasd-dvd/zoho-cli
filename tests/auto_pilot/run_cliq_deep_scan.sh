#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

echo "[SCAP] Cliq deep scan starting..."
echo "[SCAP] Python: $(python3.11 --version)"

mkdir -p tests/auto_pilot/reports

python3.11 -m pytest -q \
  tests/auto_pilot/scenarios/test_social.py \
  tests/auto_pilot/scenarios/test_messaging.py \
  --maxfail=1 \
  --disable-warnings \
  --junitxml=tests/auto_pilot/reports/cliq_deep_scan.junit.xml

echo "[SCAP] Done. JUnit report: tests/auto_pilot/reports/cliq_deep_scan.junit.xml"
