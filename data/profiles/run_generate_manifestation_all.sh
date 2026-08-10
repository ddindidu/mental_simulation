#!/usr/bin/env bash
# Run 07_generate_manifestation.py over every persona file under
# add_manifestation/split_patients/ and write the manifestation-enriched result
# to the mirrored path under add_manifestation/. The split source is untouched.
#
# Config via env vars (all optional):
#   MODEL=gpt-5.1 TEMPERATURE=0.9 ./run_generate_manifestation_all.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODEL="${MODEL:-gpt-5.1}"
TEMPERATURE="${TEMPERATURE:-0.9}"

mapfile -t PROFILES < <(find add_manifestation/split_patients -type f -name "*.json" | sort)
TOTAL=${#PROFILES[@]}

if [ "$TOTAL" -eq 0 ]; then
    echo "No profile files found under split_patients/." >&2
    exit 1
fi

echo "Found $TOTAL persona files under split_patients/. model=$MODEL temperature=$TEMPERATURE"

i=0
for profile in "${PROFILES[@]}"; do
    i=$((i + 1))
    echo ""
    echo "===== [$i/$TOTAL] $profile ====="

    echo "--- 07_generate_manifestation.py ---"
    python3 07_generate_manifestation.py \
        --profile "$profile" \
        --model "$MODEL" \
        --temperature "$TEMPERATURE"

done

echo ""
echo "Done. Processed $TOTAL persona files -> add_manifestation/ (split_patients/ untouched)"
