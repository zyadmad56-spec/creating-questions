# Semantic evaluation record (Phase 7)

Evaluated on 27 October 2026 in the local QHNU environment (Python 3.14.7, Microsoft Word 16 COM for conversion, gcc 16.1.0 MSYS2 for C). The evaluation bank is entirely synthetic and public; its counts are test settings, not defaults. Builder: `evals/files/semantic/build_semantic_bank.py`, which also embeds **actual execution records** produced by the local runner at build time.

## Method

1. Build the deliberately varied synthetic bank (independent shared-code MCQs, a hard linked chain, a function/API item, all four essay styles, conceptual True/False).
2. Execute every executable variant through `qbank_execution` and record stdout/exit/exceptions; the manually derived keys from the planning examples were written **before** running and only compared afterwards.
3. Review each item question by question: source support, difficulty rationale, distractor rejection, state/reset semantics, and duplication.
4. Run the known-bad cases through the same review and record exclusion/repair.

## Question-by-question results

| Item | Review | Execution evidence |
|---|---|---|
| q_value (easy, independent) | Reset semantics stated ("Starting from Code Block N"); distractor 7 requires an unrequested advance call; AttributeError unsupported. | `print(c.value)` variant printed `4` — matches key. |
| q_return (easy, independent) | Distinguishes printed output from returned value; "None" distractor rejected because the appended statement is an expression, not a print of it. | Variant printed nothing — matches "No output". |
| q_advance (easy, independent) | Same baseline as q_value but a materially different skill (method call with display); not a rename duplicate. | Variant printed `7` — matches key. |
| q_isna (easy, function/API) | Single defensible answer after constraining the task to per-column missing-cell counting; describe/head/dropna fail the stated purpose. Namespace `data` is fixed. | Not applicable: conceptual API question, verified from the taught premises (recorded honestly as `not_applicable`). |
| q_score_a (hard, linked) | Multi-step trace; key derived by hand (score(4) = −1+4−1+16 = 18). | Appended `print(score(4))` printed `18`. |
| q_score_b (hard, linked, depends q_score_a) | Key computed from the CORRECT upstream value (18 // 3 = 6 → 53); the distractor 20 corresponds to using a mistaken `a = 60`-style propagation and is documented as a plausible-error explanation, never the key. | Appended `print(score(18 // 3))` printed `53`. |
| q_score_final (hard, linked, depends both) | Combines carried values with a fresh trace: 71 and score(3) = 2. | Printed `71 2` — matches key. |
| q_tf_advance (easy, True/False) | True claim decidable from executed variants; no negation cue. | Covered by executed q_advance variant (recorded `not_applicable` with pointer). |
| q_tf_print (medium, True/False) | False claim with a source-supported correction; the executed q_return variant is the evidence. | Same as above. |
| q_essay_scenario (easy, style A) | Interface specified without prescribing internals; reference solution executed; equivalent implementations accepted per the design rules. | Reference printed `3\n5` — matches the stated demonstration. |
| q_essay_completion (easy, style B) | Intentional gap preserved in the displayed block (`intentionally_incomplete` review status); the completed variant is a separate execution construction, never the displayed text. | Completed variant printed `3\n0`. |
| q_essay_bugfix (medium, style C) | The bug (method object instead of call) is real and taught; the model answer explains the call rather than just supplying parentheses; the displayed block keeps its `intentionally_invalid` status. | Repaired variant printed `3`. |
| q_essay_trace (hard, style D) | State advances only within this one question (explicit appended lines); checkpoints replace artificial inputs. Its block is a separate `b_counter_trace` copy so display numbers and `{{block:}}` references stay unambiguous. | Appended variant printed `7 10 10` — matches the manual trace. |

All execution records are embedded in `semantic_bank.json` with program hashes, runtime identity (Python 3.14.7), observed stdout, and per-case match flags. No execution record was hand-edited; the builder writes what the runner observed.

## Known-bad cases (all identified and excluded/repaired)

`semantic_review_cases.json` documents the five required defective drafts. Summary:

1. **Two valid API options** ("removes missing values": `dropna()` vs `dropna(axis=0)`) — both defensible; excluded and replaced by the constrained q_isna.
2. **Printed-key contradiction** (mockup line-9 defect: assignment asks for terminal output; printed key contradicts the shown code) — excluded; repaired questions reference code through stable line IDs.
3. **Inherited-constructor confusion** — two defensible options and outside-scope resolution rules; excluded in source-only mode.
4. **Return-versus-print ambiguity** — repaired into q_return by stating exactly what is appended and asking what is printed.
5. **False line reference** (cites line 13 of an 8-line listing) — excluded; accepted items resolve lines via `{{line:}}` tokens.

Re-running the audit on the repaired replacements: q_isna and q_return pass the same review; the other three cases stay excluded.

## Duplication and cue review

- The three Counter questions share one program but test different operations (attribute read; silent call; printed call) — materially different skills, allowed.
- The trace essay reuses the Counter program by design (state propagation is the skill); it is a different section, different item type, and its own block copy.
- No positional/length cues: correct answers were checked against the rendered 2×2 grids; letter distribution varies across the rendered bank and was not forced.

## Verdict

The synthetic bank passes validation, ordering, rendering (Card, Monokai), Word→PDF conversion, and per-variant execution with matching keys. The manually derived keys from the planning examples were confirmed by execution with one authoring fix (the trace variant initially deleted the instantiation line and was repaired before evaluation).

## Rendered artifacts

- `work/semantic/semantic_bank.docx` / `.pdf` (7 pages, seed 7) — inspected page by page: linked notice with final numbers, block headers, gutter alignment, chips, adaptive options, essay response lines, Model Answer table with reference solutions, test cases, and S1 source registry.
- Private course material was not used; all premises are the public synthetic teaching premises.
