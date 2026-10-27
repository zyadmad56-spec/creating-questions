# Source audit and local execution contract

Execution evidence and source evidence are separate layers. The selected uploaded material controls which concepts may be tested; execution verifies the behavior of the exact effective program. A formatter pass, a parse success, or a screenshot of an old run is never execution evidence.

## Runtime discovery, never assumption

`qbank_execution.discover_runtime(language)` locates a local interpreter/compiler and records its identity (language, version string, executable path, standard, enforcement level). Python uses the running interpreter; C uses gcc/clang with `-std=c11` and `-Wall -Wextra`; C++ the analogous `-std=c++17` when configured. A missing runtime produces `status: "unavailable"` with that reason — it never changes the source language or claims untested languages were verified. Version-sensitive questions must name the environment or be rewritten/excluded; C/C++ compiler runs do not prove undefined or implementation-defined behavior portable.

## The educational screen and its honest limits

`screen_code(code, language)` parses the program and refuses anything outside the audited educational contract: network/process/threading modules, file and dynamic-execution APIs (`open`, `eval`, `exec`, `compile`, `__import__`, `os.system`, and similar). Enforcement for Python is: the static screen + isolated interpreter (`-I`) + a fresh temporary working directory + a bounded timeout with a minimal environment. For C/C++ it is: compile in a temp directory with warnings, run the temp binary. This contract covers **audited educational code only** — the agent must already have reviewed the program and removed unrelated operations. A snippet that fails the screen is recorded as `unavailable` with the violation list; it is never executed and never claimed to be sandboxed at OS level.

Execution artifacts are cleaned after evidence is collected; scratch directories are task-local and removed.

## Deterministic examples

Exact-output items avoid live downloads, random/time-dependent values, external services, and locale-dependent formatting. Seed randomness when legitimately needed, provide fixed fixtures and explicit stdin, and prefer a small explicit DataFrame over any downloaded dataset. If a library is absent, report the absence instead of inventing output. For SQL, name the dialect, schema, seed rows, and an explicit ordering contract; for NoSQL, name the engine — a handwritten simulation is not an executed query.

## Verify the exact variant

`qbank_schema.effective_program(model, block_id, variant)` builds the exact effective program from stable line IDs (`append`, `replace`, `insert_after`, `delete`) and returns its text plus line-number map. `run_question(model, question)` runs that program and returns a record: `program_hash`, runtime identity, `status` (`passed`, `failed`, `unavailable`, `not_applicable`, `not_run`), `execution_verified`, reason, and per-case observations (stdout, stderr, exit status, timeout).

- Independent questions reset to the baseline; each variant is reconstructed fresh.
- Linked chains run through the correct upstream state; the record must show each transition. Keys are computed from correct upstream results, never from a student's mistaken choice.
- An expected exception is a legitimate verified answer (`{"expected_exception": "KeyError"}`); a nonzero exit alone is not automatically a failure.
- Compare only what the prompt asks about; ignore only explicitly irrelevant traceback/path text.

## Records and freshness

A passed record stores the exact `program_hash` of the effective program. `stale_execution_records(model)` lists questions whose recorded hash no longer matches their current code — authoring changes invalidate earlier execution evidence, and the stale list must be re-run before export. A version string, command, or expected-output field is not evidence that a command ran; only the recorded observation with a matching case is.

## Source/key conflicts

Compare printed source answers with the actually shown code and inspected premises. For a contradiction, keep a Source issue with the uploaded locator, the original wording/key, the observed or reasoned conflict, and the disposition. Never reproduce a wrong printed key; never silently import outside facts in source-only mode. Exclude unresolved items and reconcile quotas; if execution is unavailable, mark the conflict suspected and unresolved rather than empirically proven.

## Records in the bank

Each executable question carries `execution: {status, execution_verified, reason, program_hash, cases}`. Schema validation enforces that only `passed` carries `execution_verified: true`. `execution_verified: false` coexists legally with a completed source audit — the final report must disclose the limitation, and exact-output items whose result cannot be defensibly audited must be excluded rather than guessed.
