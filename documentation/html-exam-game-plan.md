# Local HTML Exam Game

## Purpose

Add an HTML game mode alongside Word and PDF output. The game runs on the host's device through a Python localhost server. Players share its screen through Discord, and the host records their answers. No AI service or internet connection is required during play.

This document records the agreed implementation plan. Separate-device Wi-Fi play and Discord integration are outside this version.

## Question generation and data

- Ask for Word, PDF, or HTML output when the request does not specify it. Preserve the existing scope, source authorization, question-count, difficulty, extraction, and answer-audit workflow.
- Keep existing Word generation compatible. PDF uses the existing document-to-PDF workflow when conversion is available; explain unavailable conversion without silently substituting another format.
- HTML supports MCQ, True/False, and essays. Generate and verify all answers, explanations, and retry questions before launching the app.
- Extend HTML banks with stable question IDs and learning-target records identifying **concept, tested angle, question type, and difficulty**. Original questions with the same target share one retry pool.
- Require exactly three retry variants per target. Preserve the original question type and comparable difficulty; change the scenario, application, or reasoning substantively. Cosmetic rewrites are insufficient.
- Original counts and difficulty quotas exclude retry variants. Audit variants against the same authorized sources and check duplicates across originals and variants.
- Add MCQ explanations keyed to canonical options, explaining why each distractor is wrong. Retain the verified explanation for the correct answer. True/False feedback includes the supported judgment and correction; essays include model-answer points and explanatory reasoning.
- If three valid variants cannot be prepared, explain the affected targets and renegotiate question selection, counts, or authorized source scope before export. Do not silently reduce retries or introduce outside facts.
- Export an audited `exam.json` and launch instructions into a task-local game directory. Legacy document banks remain valid without the new HTML fields.

## Game behavior

### Setup and original exam

- Browser setup collects solo/group mode, player names, and one positive integer duration in seconds. Solo requires one player; group requires at least two. Reject blank or duplicate names.
- Use a quiz-show presentation: large questions, visible timer, named player cards, scores, and winner display. Use local assets without external fonts, scripts, or services.
- Default to white and blue. Add a Dark mode/Light mode button in the header for near-black backgrounds, charcoal panels, and red accents. Remember the theme in browser local storage when available; switching must preserve current answers, unsaved drafts, timer state, scores, and review position. Theme preference is independent of session resets.
- Use a clock-style countdown with a dial and minutes/seconds (hours when needed).
- Preserve MCQ → True/False → essay sections, omitting unused types. Shuffle questions within sections and shuffle MCQ options while preserving answer and explanation correspondence.
- Start the timer when a question appears. The host records each player's answer; entries remain editable until lock.
- Pause freezes only the timer. Questions and answer controls remain visible and usable. Resume continues from the saved remaining time.
- While paused, Previous/Next browse completed questions with their recorded responses and explanations. Return to current question preserves the pause and response drafts; resuming from review returns to the current question. Completed responses remain locked, and review does not change scores or retry attempts.
- Timer expiry signals that time has ended but does not freeze entry, reveal results, or advance. The host may finish recording answers.
- Allow an early lock only when every player has answered. After expiry, locking marks unanswered players timed out. Every player must therefore have an answer or timeout before results appear.
- Automatically grade MCQ and True/False. For essays, lock all responses first, show the model answer, and require the host to mark every submitted response correct or incorrect. Timeouts are incorrect without marking.
- Award one point for each correct original answer; otherwise award zero. No partial credit, penalties, or speed scoring.
- After grading, show player results, the correct answer, explanations, and source references. Essay feedback shows expected answer points; it does not claim automated diagnosis of the submitted prose.
- Explanations and essay marking are untimed. The host explicitly advances to the next question.

### Results and retries

- Finish every original question before beginning retries.
- Declare the player or players with the highest original score winners. Equal highest scores produce shared winners, including an all-zero tie.
- Create each player's retry queue from targets with at least one incorrect or timed-out original answer. Deduplicate targets; a correct original answer on the same target does not cancel another missed answer.
- Process players in roster order, finishing one player's queue before moving to the next. Order their targets by first missed occurrence.
- Only the active player answers a retry. Use the same timer, pause, lock, essay-marking, and feedback behavior.
- Players with matching targets use the same prepared pool. Different angles, types, or difficulties use separate pools. Select a fixed variant order per session and reuse it for matching players.
- One correct retry clears that target. An incorrect or timed-out retry consumes an attempt. After three unsuccessful retries, mark the target unresolved and continue to the next target.
- The three-attempt limit applies **after** the original miss: one original miss plus up to three retry questions.
- Retries never change competition scores or winners. Finish with each player's scores and cleared/unresolved targets. Skip the retry phase when nobody has missed targets.

## Architecture and interfaces

- Extract dependency-light validation and shared question-data utilities from the Word formatter. Preserve its CLI, callable interfaces, supported source modes, and existing test imports.
- Add a Python server runner using the standard library, serving local HTML/CSS/JavaScript and owning grading, scores, timers, and progression. Avoid a Node build requirement.
- The runner accepts the audited exam JSON path, validates it before starting, binds to `127.0.0.1`, selects an available port, and prints the browser URL and shutdown instructions.
- Maintain one host-controlled session. Player devices do not connect independently in this version.
- Persist authoritative session state in `session.json` beside the exam data. Every server launch starts fresh; browser refresh restores the running session. Keep the exam JSON unchanged.
- Offer an explicit Restart Game action with confirmation; reset session state and return to setup.
- Store phase, original/retry stage, roster, stable presentation order, active question, answer drafts, grading, scores, timer state, and per-player target progress.
- Use server-controlled elapsed time, excluding pauses. Refreshing the page or delaying browser updates must not reset or extend the timer.
- Provide `GET /api/state` and `POST /api/action`. Actions cover setup/start, answer entry, pause/resume, lock, essay marking, next, start retries, and restart.
- Add a paused `review` action selecting a completed-history index or returning to the current question. Persist the selected review and expose only completed questions; reject answer entry and locking while reviewing.
- Include a session revision in mutations. Serialize changes, reject stale actions, and prevent duplicate scoring or advancement. Persist updates atomically.
- Return only the active view's necessary data. Do not send answer keys or future retry content before their reveal phase. Render question and player text safely and restrict mutation requests to the local app.
- Update the skill instructions, README, display metadata, schema reference, and behavior evaluations to describe the three modes, launch process, manual answer recording, and retry requirements.

## Validation and acceptance

- **Document compatibility:** existing formatter and extraction suites pass; old banks, source policies, student-only output, and shuffled answer correspondence remain supported.
- **HTML validation:** reject missing IDs, invalid target links, malformed pools, incorrect variant counts, duplicate content, missing feedback, unsupported sources, and incomplete audits.
- **Question barriers:** no results appear before lock; no early lock with unanswered players; expiry permits host entry, and remaining blanks become timeouts at lock.
- **Timers:** verify elapsed time, pause with usable controls, resume, expiry, refresh, and untimed feedback/marking.
- **Themes:** verify light default, accessible toggle, dark/light readability, preference persistence across refresh and game restart, graceful operation without local storage, mobile layout, and unchanged game state/drafts during switching.
- **Paused navigation:** verify backward/forward review, return/resume, preserved remaining time and active drafts, history bounds, locked results, refresh, and unchanged scores/attempts in original and retry stages.
- **Scoring:** verify automatic marking, host-marked essays, zero-point timeouts, one point per correct original, shared winners, and unchanged scores during retries.
- **Retries:** verify deferred start, targeted queues, deduplication, shared pools, player ordering, success on attempts one through three, timeout consumption, and stopping after three failed retries.
- **Persistence:** refresh retains progress; server relaunch and confirmed restart clear it; duplicate/stale requests cannot award points twice.
- **Browser checks:** exercise a complete mixed-type solo game and group game with synthetic data, including pause, timeout, essay marking, tied winners, and exhausted retries. Check screen-share readability and keyboard access.
- Extend the existing Windows/Ubuntu Python CI matrix with server and game-logic tests. Add a headless browser smoke test on Ubuntu for the visible workflow.
- Delivery is accepted when these checks pass, this implementation document is saved in `documentation/`, and a generated game launches locally with no gameplay network dependencies.
