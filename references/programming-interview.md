# Programming interview contract

This reference extends [the base interview](../SKILL.md) for material that contains programming. The base settings (scope, total, per-type counts, per-type difficulty counts, source mode) are never replaced. Ask in English, one stage at a time, and reuse every already answered setting. The helper `scripts/qbank_interview.py` normalizes a supplied-settings record and lists every still-missing item; it never invents one.

## 1. Deliverable and document format (before scope)

Two distinct settings, established at the start of every new bank:

- **Deliverable:** Word, PDF, or both. Reuse an explicit request; otherwise offer the existing Word default while asking. Never silently generate an extra PDF, and never substitute a separately drawn PDF for a requested Word file.
- **Appearance:** a saved local format, a supplied reference/template to reproduce, or a built-in format (Classic or Card). A remembered format may be offered first, but the user may choose a different format for every new bank. Output file type and visual theme are not interchangeable.

If the user selects Card, establish the variant: Monokai (default) or the print-friendly variant. If they supply a reference document, inspect it locally before promising a reproduction. Legacy machine-authored formatter JSON without a format setting stays Classic; interactive new banks always establish the format.

## 2. Programming content modes

Ask which mode (or mixture) the material supports:

- **Shared-code / snippet mode:** one code block shown once, followed by its related questions. A shared block normally carries at least two related questions; a one-question code example is a standalone snippet and stays supported.
- **Function/API mode:** questions about a function, method, parameter, attribute, or short expression, without a long shared program.

The absence of runnable source code does not forbid source-grounded examples built from taught constructs; the absence of any programming concepts forbids a programming bank. Language detection never authorizes browsing and never rewrites one language as another (SQL stays SQL; NoSQL engines are distinguished).

## 3. Block sizes and question density (shared-code mode)

For **each selected difficulty**, ask: how many blocks, how many questions each block should contain, and approximately how many code lines. Example wording: "For easy, medium, and hard code blocks, how many blocks would you like, how many questions should each contain, and approximately how many code lines would you like?"

- The requested size (including 10-, 50-, or 60-line requests) is an authoring target subject to source capacity and document width/height. Dense or long blocks reduce question quality and may split across pages; explain that implication and negotiate when needed. Never truncate code or shrink type to satisfy an arbitrary cap; there is no enforced line limit.
- Historical ranges (3–5 per block, 5–10 easy, 8–10 medium, 6–9 hard) are suggestions only. User-selected counts govern.
- Count **questions**, not blocks, toward the bank total. If only question totals and density are supplied, derive a proposed block allocation and resolve any remainder explicitly instead of inventing an extra block or changing the total.
- After reading the full selected scope, produce a feasible block allocation table. If the requested density cannot fit without repetition, show the supported alternatives and wait for the affected revision.

## 4. Hard-dependency preference (only when hard shared blocks are relevant)

Ask once: "May hard shared-code blocks contain linked questions, where a later answer uses an earlier correct result? Easy and medium questions remain independent."

- Reuse an explicit current choice. Otherwise apply the remembered choice from the local `settings.json` and state briefly that it was applied ("Applying the remembered hard-dependency preference: linked questions in hard shared blocks are enabled/disabled. Say the word to change it.").
- Missing settings mean ask; they never silently enable dependencies. Apply the persisted choice to later runs until the user changes it.
- The preference is permission, not a requirement: the blueprint marks every block independent or linked explicitly, and any dependent block prints the notice "Note: Questions X–Y are linked; later questions depend on the results of earlier ones." with final numbers.

`settings.json` lives at the installed skill root and is git-ignored. Schema: `{"settings_version": 1, "allow_hard_dependencies": true|false, "last_format_id": "..."}`. Writes are atomic; a corrupt or unsupported-version file is reported (raise `SettingsCorruptError` behavior: name the file and the defect) and never overwritten silently. Persist no private course code, answers, or document content in general settings. The bank JSON records the effective choice so a finished bank stays reproducible if the preference changes later.

## 5. Code-writing essay styles

When essays include programming, ask which styles the user wants, then the number of questions of each selected style and integer easy/medium/hard counts within each selected style. Style totals must sum back to the essay type's already agreed total and difficulty counts.

| ID | Style |
|---|---|
| scenario | Story/scenario → write a complete function or script. |
| completion | Complete the missing code. |
| bug_fix | Find and fix the bug. |
| trace_explain | Trace/explain code. |

Show the distribution before generation, for example: A=4, B=5, C=2, D=1 (12 essays). If some essays remain conventional (non-code), record their counts explicitly and never count a shared block twice.

## 6. Reconciliation before generation

Save a task-local normalized interview record (the `normalize_settings` output) covering: scope, deliverables, format, source mode, total, per-type counts, per-type difficulty counts, essay style/difficulty matrix, block sizes/densities, and the effective dependency setting. Validate every sum. Do not reopen the whole interview for one arithmetic error — explain the exact mismatch and ask only for the necessary revision. If capacity later changes the total, follow the renegotiation rules (revised type counts, then per-type difficulty counts) and revise any affected block/style allocation with the user.

## Interview fixtures

`evals/files/interview/*.json` are scripted contract cases (complete, partial, empty, no-code, function-only, mixed-language, all essay styles, remembered preference, infeasible density, style-matrix mismatch). `python evals/test_interview.py` proves each fixture resolves to exactly one normalized request or the precise missing/mismatched items.
