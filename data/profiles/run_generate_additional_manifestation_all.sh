#!/usr/bin/env bash
# Run 08_generate_additional_manifestation.py for every completed patient
# manifestation under add_manifestation/low/. The Python script reads each
# manifestation-enriched JSON and writes the full profile plus add_requirements
# to the mirrored path under add_requirements/low/.
#
# Optional configuration:
#   MODEL=gpt-5.1 TEMPERATURE=0.9 ./run_generate_additional_manifestation_all.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODEL="${MODEL:-gpt-5.1}"
TEMPERATURE="${TEMPERATURE:-0.9}"
INPUT_ROOT="add_manifestation/low"

mapfile -t PROFILES < <(find "$INPUT_ROOT" -type f -name "*.json" | sort)
TOTAL=${#PROFILES[@]}

if [ "$TOTAL" -eq 0 ]; then
    echo "No manifestation files found under $INPUT_ROOT." >&2
    exit 1
fi

echo "Found $TOTAL manifestation files. model=$MODEL temperature=$TEMPERATURE"

i=0
for profile in "${PROFILES[@]}"; do
    i=$((i + 1))
    echo ""
    echo "===== [$i/$TOTAL] $profile ====="

    python3 08_generate_additional_manifestation.py \
        --profile "$profile" \
        --model "$MODEL" \
        --temperature "$TEMPERATURE"
done

echo ""
echo "Done. Processed $TOTAL files -> add_requirements/low/"
