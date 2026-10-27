# Programming question design rules

These rules extend the base authoring rules in [SKILL.md](../SKILL.md) for programming content. Every authored item still needs inspected source evidence and one defensible answer. Work from a feasible [blueprint](#1-plan-coverage-and-capacity-before-drafting) built by `scripts/qbank_blueprint.py` from the normalized interview record.

## 1. Plan coverage and capacity before drafting

Create a blueprint with one row per standalone question or shared code block: language/version, source concepts and locators, question type, difficulty, mode, requested question count, approximate code length, dependency mode, and essay style if relevant. One shared block contributes its individual questions to the total; a block is homogeneous in both type and difficulty — never place MCQ and True/False questions in one group. The same taught concept may appear in different blocks when it tests a materially different skill; avoid repeating the same program or underlying test across sections.

Check feasibility by type, difficulty, essay style, block density, language, and source coverage. If a requested block can support fewer distinct tests than requested (for example 12 distinct tests for 20 questions), show the limitation and renegotiate the allocation — never manufacture paraphrases. Count questions, not blocks, toward the bank total. A shared block normally carries at least two related questions; a one-question code example is a standalone snippet and must not be labeled a shared block to satisfy a requested block count.

## 2. Difficulty is a reasoning distinction

| Difficulty | Code expectations | Relationship between questions |
|---|---|---|
| easy | Short, direct application of a taught rule; changed names or values may suffice for the teaching purpose. | Every question independent. |
| medium | A changed structure, data set, or scenario applying taught rules, such as altered loop bounds or combining nearby operations. | Every question independent. |
| hard | New source-grounded logic combining supported constructs and conditions; may require a multi-step trace or synthesis. | Independent or explicitly linked, per the effective user setting. |

Never equate code length with difficulty, and never substitute syntax ambiguity for reasoning. A short snippet can be hard; a 50-line listing can support easy questions.

## 3. Author new code within the source scope

Source-only mode permits invented scenarios and original code when every rule needed to solve them is taught in the selected scope. Preserve the original source snippet as evidence; label new code as authored and cite the relevant concepts as an inference. Never present authored code as a verbatim extract.

Change more than variable names: vary data, control flow, task, or the combination of taught constructs. Review token-normalized similarity to catch rename-only duplicates — an approximate 70% similarity is a review heuristic to calibrate, not a pass/fail threshold; do not reject every short canonical API expression as duplication. If the material explains suitable APIs but shows no code, create code from those constructs. If it lacks the needed rules too, renegotiate capacity or source permissions. Expanded mode permits relevant external constructs only with the existing explicit outside-source labels and verification.

## 4. Make state and modifications explicit

Independent questions reset to the displayed baseline. Statements such as "after adding this line" or "if line 13 is changed" apply to **that question only** unless a linked chain explicitly says otherwise. State whether a call's return value is printed, ignored, assigned, or used later, and distinguish no output, an empty printed line, a returned value, and an exception.

For linked hard blocks, record the dependency IDs, the exact state transition or correct value carried forward, and the fixed question order. Never make the author's correct answer depend on a student's mistaken answer: an MCQ distractor may represent a plausible propagated error, but the key is always computed from the correct upstream result. Verify the entire chain plus each transition. Print the agreed notice above the block with final numbers — "Note: Questions X–Y are linked; later questions depend on the results of earlier ones." — never signal a chain only through an answer explanation. If a later question would directly reveal the earlier answer, review whether it still tests a meaningful distinct step.

## 5. Build strong function/API questions

Function, method, attribute, parameter, and expression questions are first-class content even without a long listing. Each correct answer and each distractor needs a reason tied to the exact namespace and context. If `drop`, `pop`, and `del` could all work in a broad task, constrain the task until one answer is defensible, or replace the item. Do not inherit flawed source MCQs unquestioningly; qualify namespaces when similar functions exist in multiple libraries, and distinguish a property from a callable method when the task depends on real behavior.

## 6. Author code-writing essays

Honor the selected style/difficulty matrix from the interview:

- **scenario:** a story prompt specifying inputs, outputs, constraints, and the taught behavior without prescribing an unnecessary solution shape.
- **completion:** preserve the intentional gap; never execute the fragment before inserting a solution.
- **bug_fix:** identify the required behavior without silently changing the problem; the model answer explains the mistake, not just the fixed line.
- **trace_explain:** distinguish exact output from conceptual explanation; use concrete trace/check points instead of artificial extra inputs.

Model answers contain a reference solution where applicable, concise reasoning, 2–3 useful test cases when meaningful, expected results, and any edge conditions the source requires. Accept equivalent correct implementations rather than treating reference text as the only answer. A hard scenario may carry numbered subparts within one essay item; the count contract must say whether subparts are one question or separate items before generation. Keep solutions and expected answers after all questions in the Model Answer table; long solutions use a clearly labeled solution continuation attached to the matching answer row.

## 7. Audit sources and source issues

The selected source controls which concepts may be tested; execution evidence only verifies behavior. For an executable-code question, a printed key that conflicts with the actually shown code is **not** a reason to emit a wrong answer: record a Source issue and either exclude the unresolved item or author a clearly specified, source-supported replacement. Never silently rewrite the original source or import an external fact in source-only mode.

Source issues live in the internal audit and in a short **Source issues** note near the Model Answer when relevant — never beside the student questions. Explain ambiguous source options, source/key conflicts, and version-sensitive claims with locators. If execution is unavailable, mark the conflict suspected and unresolved; do not claim empirical proof.

## 8. Review duplication and cues across the whole bank

Compare effective context: code + inputs + mutation + question intent. Repeated wording such as "What is the output?" may be legitimate across different programs; renaming variables in the same program may still be a duplicate. Keep mechanical checks (exact duplicates) and conceptual review separate.

MCQs keep four independent A–D choices and one correct answer; avoid positional references ("A and C", "all of the above"), unsupported options, length cues, and forced letter patterns. True/False items keep source-supported corrections for false statements and never use negation as a cue. Natural answer runs remain allowed.

## Audited planning examples

`evals/files/semantic/` contains the synthetic public examples from the plan (independent Counter MCQs, the linked score chain, a function/API item, all four essay styles, and the known-bad review cases). Their manually derived keys are re-audited and executed in the Phase 7 evaluation record; they are fixtures, not a generated bank and not default counts. The supplied visual mockup's line-reference defect (asking for output "after executing line 9" when line 9 is a bare assignment) is corrected in the generated test content through stable line IDs.
