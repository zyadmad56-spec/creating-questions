# Local HTML exam mode

Read this reference only when the user selects HTML. Shared source-reading, authoring, evidence, and audit rules in `SKILL.md` still apply to originals and retries.

## Author and audit the full game

1. Use the existing bank schema in `question-data.md` for original questions and quotas. Add `game_version: 1`, stable `id` and `target_id` fields on every question, and `learning_targets` as described below.
2. Map each original to its concept and tested angle using the source-backed facts. A target has one question type and difficulty. Originals sharing that identity share one target; different angles, types, or difficulties have separate targets.
3. Prepare exactly three alternate questions per target before export. Preserve type and comparable difficulty while changing the application, scenario, or reasoning substantively. Audit every variant and reject cosmetic and semantic duplicates across originals and retries.
4. For MCQs, supply source-verified `option_explanations` for all four canonical input options. Explain why each wrong choice fails and why the right choice holds under the question's conditions. Keep the common correct-answer `explanation` too.
5. Estimate capacity for originals **and** retry pools. If the source cannot support a complete pool, identify the bottleneck and wait for revised selection/counts or explicitly expanded scope/sources. Reopen type/difficulty settings when counts change. Original counts exclude retries; adding players does not multiply pools.
6. Save UTF-8 `exam.json` in a user-writable task-local game directory. Validate before launch. The validator checks structure, not factual truth or semantic distinctness.

## Additional JSON fields

The original `title`, source policy, counts, difficulty counts, and all three question arrays remain required. See `evals/files/sample_game.json` for a complete synthetic fixture, not course content.

```json
{
  "game_version": 1,
  "learning_targets": {
    "triangle-side-count-easy-mcq": {
      "concept_id": "triangle",
      "angle": "count straight sides",
      "label": "Triangle: straight-side count",
      "question_type": "mcqs",
      "difficulty": "easy",
      "retries": ["three complete question objects go here"]
    }
  }
}
```

The example is an extension fragment, not a valid bank. `question_type` is exactly `mcqs`, `true_false`, or `essays`. Every retry is a complete audited question record of that type, with its own globally unique `id` and the containing `target_id`. Retry difficulty must equal its target difficulty. Every target must be referenced by an original question.

On each MCQ original and retry, add:

```json
{
  "id": "q-001",
  "target_id": "triangle-side-count-easy-mcq",
  "option_explanations": {
    "A": "Why the first input option is wrong or right.",
    "B": "Why the second input option is wrong or right.",
    "C": "Why the third input option is wrong or right.",
    "D": "Why the fourth input option is wrong or right."
  }
}
```

`correct` and these explanation keys refer to input option order. The server shuffles display positions while preserving canonical option identities. For True/False and essays, use the existing explanations, false corrections, and model-answer points. `include_answer_key` controls document export only; game answers are retained internally and revealed after lock.

## Validate and launch

Use the script in the installed skill directory, not a copy of the generated exam's folder:

```text
python <skill-directory>/scripts/serve_exam_game.py <game-directory>/exam.json --validate-only
python <skill-directory>/scripts/serve_exam_game.py <game-directory>/exam.json
```

Quote paths containing spaces. The server needs only Python 3.10+ and the installed skill's scripts/assets. It prints an available `http://127.0.0.1:<port>` address; open that address in a browser and keep the process running. Tell the user how to relaunch using their actual paths and how to stop with Ctrl+C. Include these commands in a task-local launch note. Check setup and a synthetic test session without submitting or marking the user's real exam for them.

The first browser screen collects solo/group mode, names, and seconds per question. Do not add these to the generation interview. Names must be unique (case-insensitive), nonempty, and at most 80 characters. Duration is an integer from 1 to 86400 seconds; the editable browser default is 60. Solo has one player; group has at least two.

## Host flow and limits

- The interface starts in white and blue. The header's Dark mode/Light mode button switches to navy and blue or back. The browser saves this preference when local storage is available; toggling it preserves answers, drafts, scores, and timer state. It is independent of session resets.
- The host shares one screen, optionally through Discord. Friends answer aloud or in shared chat, and the host saves their responses. There is no Discord connector or separate-device joining.
- Originals use MCQ → True/False → essay sections, shuffled within each section. Correct originals earn one point; essay correctness is decided by the host against the model answer, without partial credit.
- Pause freezes only the timer; answer entry remains usable. Expiry leaves answers hidden and permits host entry. An early lock requires every answer; after expiry, blanks become timeouts on lock. Save draft responses before locking.
- The clock shows minutes/seconds (hours for longer durations). While paused, Previous/Next browse completed questions and their locked results. Return to current question preserves the pause; Resume current question returns and resumes. Review never changes scores or retry progress. Refresh retains the selected review; unsaved current drafts survive navigation within the same browser tab.
- After lock, reveal the correct answer and explanations. Essays require host marking before advancing. Feedback and marking are untimed. The host explicitly advances.
- Highest original score wins; ties share victory. Retry success never changes scores.
- After all originals, revisit each player's missed targets, one player at a time. A target with any wrong/timeout original is queued once. A correct original on that same target does not erase a miss.
- Matching targets share a three-question pool and session order. Later players may have heard its explanations. One correct retry clears a target; three incorrect/timed-out retries leave it unresolved. Continue other targets and players, then show learning progress.
- `session.json` is authoritative and resets on each server launch. Browser refresh retains the running session. Restart Game clears progress after confirmation. One server may own a game directory at a time; the exam file is never modified.

## Verification

Validate the bank structurally and audit sources separately. Check readable questions in both themes, named responses, pause/resume and review, hidden keys before lock, host essay marking, and original/retry progress. Use synthetic data for gameplay checks; generated exams still need a source audit.
