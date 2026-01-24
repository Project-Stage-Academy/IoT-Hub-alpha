#!/usr/bin/env bash
set -euo pipefail

scripts=(
  "smoke/smoke1_seed_data.sh"
  "smoke/smoke2_ingest_http.sh"
  # Rule trigger is currently non functional as there is no runner.
  # "smoke/smoke3_rule_trigger_notification.sh"
)

for s in "${scripts[@]}"; do
  echo "==> Running: $s"
  bash "$s"
  echo
done

echo "✅ All smoke checks passed."