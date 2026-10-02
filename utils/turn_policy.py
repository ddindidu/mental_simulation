"""Turn-numbering policy shared by eval/ and human_validation/.

  t = 0   the doctor's opening question. It is NOT a turn (never scored).
  t >= 1  one turn = (patient response t,
                      the doctor's disorder prediction after it,
                      the doctor's next question).
          The last turn T has no next question (the doctor gave the final
          diagnosis instead), so a T-turn episode has T patient responses,
          T predictions and T − 1 scored questions.

Raw simulation logs group the other way: doctor_memory.turns[k].doctor.question
(and *_result.json turns[k].doctor_question) is the question asked BEFORE
patient response k — i.e. the question of policy turn k − 1 (k = 1 holds the
opening question). Convert with the helpers below instead of re-deriving the
offset in each script.
"""
from __future__ import annotations

OPENING_TURN = 0


def policy_turns(raw_turns: list[dict], question_key: str = "doctor_question") -> tuple[str | None, list[dict]]:
    """Regroup raw per-patient-response records into policy turns.

    raw_turns: records sorted or sortable by "turn" (1-based patient response
    index), each holding the question that PRECEDED that response under
    `question_key` (e.g. *_result.json turns).

    Returns (opening_question, turns) where turns[i] is the original record
    for patient response t = i + 1, plus:
      "question": the doctor's question asked after response t (None for the
                  last turn).
    """
    ordered = sorted(raw_turns, key=lambda r: int(r["turn"]))
    opening = ordered[0].get(question_key) if ordered else None
    out = []
    for i, rec in enumerate(ordered):
        nxt = ordered[i + 1].get(question_key) if i + 1 < len(ordered) else None
        out.append({**rec, "turn": int(rec["turn"]), "question": nxt})
    return opening, out


def preceding_question_turn_to_policy(t: int) -> int:
    """Turn label of a question shown/rated under the raw 'question before
    response t' grouping -> its policy turn (t − 1; 0 = opening question)."""
    return t - 1
