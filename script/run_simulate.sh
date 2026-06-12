#!/bin/bash
set -e
cd "$(dirname "$0")/.."

PATIENT_MODELS=("gpt-4o-mini")
DOCTOR_MODELS=("gpt-4o-mini")
SYMPTOM_PROFILES=(
  "data/profiles/symptom_profile.json"
)

MAX_TURNS=""
OUTPUT_DIR="data/results"
VERBOSE=""

OUT="$OUTPUT_DIR"

for P in "${PATIENT_MODELS[@]}"; do
  for D in "${DOCTOR_MODELS[@]}"; do
    for PROF in "${SYMPTOM_PROFILES[@]}"; do
      [[ -f "$PROF" ]] || { echo "없는 프로필: $PROF" >&2; exit 1; }

      echo "Running patient=$P doctor=$D profile=$PROF${MAX_TURNS:+ max_turns=$MAX_TURNS}"

      ARGS=(python3 simulate.py --profile "$PROF" --output-dir "$OUT" --patient-model "$P" --doctor-model "$D")
      [[ -n "$MAX_TURNS" ]] && ARGS+=(--max-turns "$MAX_TURNS")
      [[ "$VERBOSE" == "1" ]] && ARGS+=(--verbose)

      "${ARGS[@]}"
    done
  done
done
