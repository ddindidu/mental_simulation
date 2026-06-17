#!/bin/bash
set -e
cd "$(dirname "$0")/.."

PATIENT_MODELS=("gemini-3.5-flash")
DOCTOR_MODELS=("gemini-3.5-flash")

# 특정 프로필 파일을 지정하려면 아래 배열에 경로를 추가하세요.
# SYMPTOM_PROFILES=("data/symptom_profiles/sample_profile.json")
# 비워두면 config.json의 patient.use_knowledge_graph 설정을 따릅니다.
SYMPTOM_PROFILES=()

MAX_TURNS=""
OUTPUT_DIR="data/results"
VERBOSE=""

OUT="$OUTPUT_DIR"

for P in "${PATIENT_MODELS[@]}"; do
  for D in "${DOCTOR_MODELS[@]}"; do
    if [[ ${#SYMPTOM_PROFILES[@]} -eq 0 ]]; then
      echo "Running patient=$P doctor=$D (KG mode)${MAX_TURNS:+ max_turns=$MAX_TURNS}"

      ARGS=(python3 simulate.py --output-dir "$OUT" --patient-model "$P" --doctor-model "$D")
      [[ -n "$MAX_TURNS" ]] && ARGS+=(--max-turns "$MAX_TURNS")
      [[ "$VERBOSE" == "1" ]] && ARGS+=(--verbose)

      "${ARGS[@]}"
    else
      for PROF in "${SYMPTOM_PROFILES[@]}"; do
        [[ -f "$PROF" ]] || { echo "없는 프로필: $PROF" >&2; exit 1; }

        echo "Running patient=$P doctor=$D profile=$PROF${MAX_TURNS:+ max_turns=$MAX_TURNS}"

        ARGS=(python3 simulate.py --profile "$PROF" --output-dir "$OUT" --patient-model "$P" --doctor-model "$D")
        [[ -n "$MAX_TURNS" ]] && ARGS+=(--max-turns "$MAX_TURNS")
        [[ "$VERBOSE" == "1" ]] && ARGS+=(--verbose)

        "${ARGS[@]}"
      done
    fi
  done
done
