# evaluate_turns_strict.py — TP/FP/FN/TN 기준과 계산

## 1. 기본 설정

```
N_classes = 23                          # 전체 질병 (D001~D023)
predicted = {해당 턴에서 의사 LLM이 낸 candidates (질병 ID 집합)}
truth_set = {ground_truth} ∪ {Method B 기준 plausible 질병}
```

## 2. Method B truth_set 판정

[`evaluate_turns_strict.py:174-196`](evaluate_turns_strict.py#L174-L196)

모든 질병 D에 대해 (gt는 항상 포함):

```
feasible(D)  = 모든 must_include 그룹 G에서  |G.pool − denied_cumulative| ≥ min_count
supported(D) = 적어도 하나의 must_include 그룹 G에서  G.pool ∩ confirmed_cumulative ≠ ∅

D ∈ truth_set  ⇔  feasible(D) AND supported(D)
```

- **feasible**: denial로 인해 min_count 달성이 이론상 불가능하지 않은가
- **supported**: 확정된 증상이 적어도 하나의 그룹 풀과 겹쳐 "양성 증거"가 있는가

## 3. TP/FP/FN/TN 집합 연산

| 항목 | 정의 | 의미 |
|------|------|------|
| **TP** | \|predicted ∩ truth_set\| | 의사가 예측했고 실제로 plausible한 질병 수 |
| **FP** | \|predicted − truth_set\| | 의사가 예측했지만 plausible하지 않은 질병 수 |
| **FN** | \|truth_set − predicted\| | plausible한데 의사가 놓친 질병 수 |
| **TN** | N_classes − \|predicted ∪ truth_set\| | 의사도 안 넣고 plausible도 아닌 질병 (올바르게 제외) |

---

## 4. 구체 예시: D001_1 turn 1

```
gt              = D001
confirmed_cum   = {S006}        (inattention 증상)
denied_cum      = {}            (첫 턴이라 denial 없음)
예측 (의사)    = {D001, D002, D011, D013}
```

**Method B로 truth_set 판정**:
- D001, D002, D003 (ADHD 3종): inattention 풀에 S006 있음 → supported ✓, denial 없음 → feasible ✓ → **포함**
- D004~D023: inattention/우울/불안 풀에 S006 없음 → supported ✗ → **제외**

```
truth_set = {D001, D002, D003}
```

**집합 연산**:

```
predicted ∩ truth_set = {D001, D002}                  →  TP = 2
predicted − truth_set = {D011, D013}                  →  FP = 2
truth_set − predicted = {D003}                        →  FN = 1
predicted ∪ truth_set = {D001, D002, D003, D011, D013}  (5개)
TN = 23 − 5                                           →  TN = 18
```

**지표** (샘플별, [`evaluate_turns_strict.py:334-336`](evaluate_turns_strict.py#L334-L336)):

```
Precision = TP / |predicted|  = 2 / 4 = 0.500
Recall    = TP / |truth_set|  = 2 / 3 = 0.667
Accuracy  = (TP + TN) / N     = (2 + 18) / 23 = 0.870
```

---

## 5. 다른 예시: D002_1 turn 3 (denial이 있는 경우)

```
gt              = D002
confirmed_cum   = {S001}                                   (inattention)
denied_cum      = {S024, S025, S010, S012, S018, S056}    (우울/불안/과잉행동 부정)
예측 (의사)    = {D002} (의사가 inattentive ADHD로 좁힘)
```

**Method B truth_set**:
- D001 (ADHD Combined): hyperactivity 그룹 pool 10개 중 3개(S010, S012, S018) denial, 남은 7개로 min_count=5 가능 → feasible ✓, inattention에 S001 있음 → supported ✓ → **포함**
- D002 (ADHD Inattentive): **포함** (gt)
- D003 (ADHD Hyperactive): inattention 그룹 min_count=5에 S001 하나만 → supported ✓, feasible ✓ → **포함**
- D013 (MDD): S024, S025 denial, 남은 pool 7개 ≥ min_count=5 → feasible ✓, 하지만 S001은 pool에 없음 → supported ✗ → **제외**
- D011 (GAD): S056 denial, pool에 S001 없음 → supported ✗ → **제외**

```
truth_set = {D001, D002, D003}
```

```
TP = |{D002} ∩ {D001, D002, D003}|   = 1
FP = |{D002} − truth|                 = 0
FN = |truth − {D002}|                 = 2 (D001, D003)
TN = 23 − |{D001, D002, D003}|        = 20

Precision = 1/1 = 1.000    ← 좁혀질수록 상승 ✓
Recall    = 1/3 = 0.333
Accuracy  = (1 + 20) / 23  = 0.913
```

---

## 6. 턴별 집계 (micro-averaged)

[`evaluate_turns_strict.py:348-356`](evaluate_turns_strict.py#L348-L356)

N개 샘플을 한 turn에서 합칠 때:

```
Precision = ΣTP / Σ|predicted|
Recall    = ΣTP / Σ|truth_set|
Accuracy  = (ΣTP + ΣTN) / (ΣTP + ΣFP + ΣFN + ΣTN)
```

실제 결과 **Turn 1**:
- N=229, ΣTP=514, Σ|predicted|=514+188=702 → Precision = 514/702 = **0.732** ✓
- Σ|truth_set|=514+287=801 → Recall = 514/801 = **0.642** ✓
- denom = 514+188+287+4478(=TN총합) → Accuracy = (514+4478)/5467 = **0.910** ✓

---

## 7. 핵심 직관

- Turn이 진행될수록 **denial ↑, confirmed ↑** → truth_set이 "지지받고 배제되지 않은" 질병으로 정제됨
- 의사가 동시에 후보를 좁혀감 → **Precision 상승** (73% → 92%)
- 단, truth_set도 confirmed 증상이 쌓이며 **함께 커짐** (3.5 → 9.1) → Recall은 상대적으로 낮아짐
