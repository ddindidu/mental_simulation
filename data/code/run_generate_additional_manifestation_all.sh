#!/usr/bin/env bash
# Run 09_generate_additional_manifestation.py for every completed patient
# manifestation under add_manifestation/low/. The Python script reads each
# manifestation-enriched JSON and writes the full profile plus add_requirements
# to the mirrored path under add_requirements/low/.
#
# Optional configuration:
#   MODEL=gpt-5.5 TEMPERATURE=0.9 MAX_ATTEMPTS=4 ./run_generate_additional_manifestation_all.sh
#
# A file whose call keeps failing is retried MAX_ATTEMPTS times and then listed in
# requirements_failed.txt, so one bad call never takes the whole batch down with it. Files that
# already have a result are skipped, so a run that dies partway can simply be started again.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODEL="${MODEL:-gpt-5.5}"
TEMPERATURE="${TEMPERATURE:-0.9}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-4}"
FAILED_LOG="requirements_failed.txt"
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

    out="add_requirements/${profile#add_manifestation/}"
    if [ -f "$out" ]; then
        echo "skipped (already generated): $out"
        continue
    fi

    attempt=1
    while : ; do
        if python3 09_generate_additional_manifestation.py \
            --profile "$profile" \
            --model "$MODEL" \
            --temperature "$TEMPERATURE"; then
            break
        fi
        if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
            echo "[FAILED after $MAX_ATTEMPTS attempts] $profile" >&2
            echo "$profile" >> "$FAILED_LOG"
            break
        fi
        echo "[retry $attempt/$MAX_ATTEMPTS] $profile" >&2
        attempt=$((attempt + 1))
        sleep 5
    done
done

echo ""
echo "Done. Processed $TOTAL files -> add_requirements/low/"
if [ -s "$FAILED_LOG" ]; then
    echo "$(wc -l < "$FAILED_LOG") file(s) failed; see $FAILED_LOG"
fi
