# 이거 복붙하기~!
# doctors alias
# gpt-5.4
# gpt-5.4-mini
# gemini-3.8-flash
# gemini-3.1-flash-lite


#!/bin/bash
set -e
cd "$(dirname "$0")/.."

# patient, judge = gpt-5.5 (run_all_doctors_profiles.py 기본값이라 별도 플래그 불필요)
python3 script/run_all_doctors_profiles.py \
  --profiles-root data/v2_final_profiles \
  --doctors gpt-5.4 \
  --styles plain verbose reserved tangent pleasing \
  --workers 4

# patient, judge = gemini-3.1-pro-preview
python3 script/run_all_doctors_profiles.py \
  --profiles-root data/v2_final_profiles \
  --doctors gpt-5.4 \
  --styles plain verbose reserved tangent pleasing \
  --workers 4 \
  --patient-model gemini-3.1-pro-preview \
  --patient-provider gemini \
  --judge-model gemini-3.1-pro-preview \
  --judge-provider gemini
