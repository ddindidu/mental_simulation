#!/usr/bin/env bash
# Run 04_generate_stressor.py over every profile JSON under add_persona/
# (recurses into whichever difficulty subfolders exist, e.g. add_persona/low/*.json),
# saving each result to add_stressor/only_stressor/<difficulty>/<profile_stem>_result.json.
#
# Config via env vars (all optional):
#   MODEL=gpt-5.1 TEMPERATURE=0.9 MAX_TOKENS=3000 ./run_generate_stressor_all.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODEL="${MODEL:-gpt-5.1}"
TEMPERATURE="${TEMPERATURE:-0.9}"
MAX_TOKENS="${MAX_TOKENS:-3000}"

mapfile -t PROFILES < <(find add_persona -type f -name "*.json" | sort)
TOTAL=${#PROFILES[@]}

if [ "$TOTAL" -eq 0 ]; then
    echo "No profile files found under add_persona/." >&2
    exit 1
fi

echo "Found $TOTAL profile files under add_persona/. model=$MODEL temperature=$TEMPERATURE max_tokens=$MAX_TOKENS"

i=0
for profile in "${PROFILES[@]}"; do
    i=$((i + 1))
    echo ""
    echo "===== [$i/$TOTAL] $profile ====="

    python3 04_generate_stressor.py \
        --profile "$profile" \
        --model "$MODEL" \
        --temperature "$TEMPERATURE" \
        --max-tokens "$MAX_TOKENS"
done

echo ""
echo "Done. Processed $TOTAL profiles -> temp/"
