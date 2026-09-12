#!/usr/bin/env bash
# Run 08_generate_manifestation.py over every persona file under
# split_patients/ and write the manifestation-enriched result
# to the mirrored path under add_manifestation/. The split source is untouched.
#
# Config via env vars (all optional):
#   MODEL=gpt-5.5 TEMPERATURE=0.9 MAX_ATTEMPTS=4 ./run_generate_manifestation_all.sh
#
# A persona file whose call keeps failing is retried MAX_ATTEMPTS times and then listed in
# manifestation_failed.txt, so one bad call never takes the whole batch down with it. Files that
# already have a result are skipped, so a run that dies partway can simply be started again.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODEL="${MODEL:-gpt-5.5}"
TEMPERATURE="${TEMPERATURE:-0.9}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-4}"
FAILED_LOG="manifestation_failed.txt"

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

    out="add_manifestation/${profile#add_manifestation/split_patients/}"
    if [ -f "$out" ]; then
        echo "skipped (already generated): $out"
        continue
    fi

    echo "--- 08_generate_manifestation.py ---"
    attempt=1
    while : ; do
        if python3 08_generate_manifestation.py \
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
echo "Done. Processed $TOTAL persona files -> add_manifestation/ (split_patients/ untouched)"
if [ -s "$FAILED_LOG" ]; then
    echo "$(wc -l < "$FAILED_LOG") persona file(s) failed; see $FAILED_LOG"
fi
