# creating-questions

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Tests](https://github.com/zyadmad56-spec/creating-questions/actions/workflows/tests.yml/badge.svg)

Create revision questions from your lecture notes, slides, or research papers. Choose a Word question bank, a PDF, or a local HTML exam game. All three support multiple-choice, True/False, and essay questions, with counts and difficulty set separately for each type.

The agent writes and checks the questions against your selected sources. Python helpers extract text, validate the question data, and produce the chosen output. Questions, explanations, and the interface are in English.

## Install and start

Install with the [Skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add zyadmad56-spec/creating-questions
```

For Codex, install globally to use the skill across projects:

```bash
npx skills add zyadmad56-spec/creating-questions --agent codex --global
```

The CLI also supports agents such as `claude-code` and `cursor`. Use `--list` to inspect available skills before installing.

Attach your study material and ask your agent to use `$creating-questions`. It collects any missing settings in this order:

1. Word, PDF, or HTML output.
2. Files and chapters, pages, slides, or paper sections to cover.
3. Total number of original questions.
4. Question types and exact counts for each type.
5. Easy, medium, and hard counts for each selected type.
6. Uploaded material only, or uploaded material plus the web and general knowledge.

Each difficulty allocation must add up to its type count; type counts must add up to the total. Settings you supply in the request are reused. HTML play mode, player names, and the timer are chosen later in the browser.

```text
Use $creating-questions with the whole attached lecture PDF, using only that PDF.
Make an HTML game with 20 originals: 10 MCQ, 6 True/False, and 4 essays.
MCQ: 3 easy, 5 medium, 2 hard.
True/False: 2 easy, 3 medium, 1 hard.
Essay: 1 easy, 2 medium, 1 hard.
```

For a document, request Word or PDF instead. You can also request a student-only document without the answer key. PDF export needs a document renderer in the agent's environment.

## Play an HTML exam

The game runs on the host's device and opens in a browser. Choose solo or group play, enter player names, and set the time allowed per question. The default is 60 seconds; any whole number from 1 to 86400 is accepted. Group play needs at least two unique names.

Friends share the host's screen, optionally through Discord. They answer aloud or in shared chat, and the host records their responses in the player cards. This version uses one browser session; friends do not join from separate devices.

The interface starts in white and blue. Use **Dark mode** in the header to switch to navy and blue, or **Light mode** to switch back. The browser remembers your choice when local storage is available. Switching themes leaves the game and any unsaved responses intact.

### During a question

- The countdown shows a clock dial and minutes/seconds, with hours for longer durations.
- Save each player's answer before locking. Responses can be updated until lock.
- Pause freezes the timer and leaves answer entry available. While paused, Previous/Next let you review completed questions, recorded responses, and explanations. Return to the current question to keep it paused, or resume directly from review. Completed answers stay locked; scores, retry attempts, and remaining time are preserved.
- An early lock requires every player to have answered. When time expires, the host can finish recording responses. Locking then treats any blanks as timeouts.
- Answers stay hidden until lock. MCQ and True/False are graded automatically. The host marks essays correct or incorrect against the model answer.
- Feedback explains the correct answer and why each MCQ distractor fails. Marking and explanations are untimed; the host advances when ready.

Originals appear in MCQ, True/False, then essay sections, shuffled within each section. MCQ choices are shuffled too. Each correct original earns one point; the highest original score wins, with shared winners for ties.

### Practice missed concepts

After all originals, each player revisits their missed learning targets. A target identifies a concept, tested angle, question type, and difficulty. Any wrong or timed-out original queues that target once, even if the player answered another original on the same target correctly.

The agent prepares three different, audited retry questions per target before launch. Players take turns through their queues. One correct retry clears the target; three incorrect or timed-out retries leave it unresolved and move on to the next target. This limit is three retries **after** the original miss. Practice does not change the competition scores.

Players with matching targets use the same pool, so later players may hear an explanation before their turn. The final screen shows scores and each player's cleared or unresolved targets.

### Launch a prepared game

Run these commands from the repository or installed skill directory, using the actual path to your authored bank:

```text
python scripts/serve_exam_game.py /path/to/game/exam.json --validate-only
python scripts/serve_exam_game.py /path/to/game/exam.json
```

Quote paths containing spaces. Keep the game data in a writable folder. Open the `http://127.0.0.1:<port>` address printed by the server and leave the process running while playing. Ctrl+C stops it.

The server saves progress in `session.json` beside the exam. Browser refresh keeps the running session; every server launch starts a fresh game. **Restart game** clears progress after confirmation. The exam file is preserved, and only one server may own a game directory at a time.

The HTML runner uses Python 3.10+ and the standard library. Keep the installed scripts and browser assets available. Gameplay needs no internet connection, AI service, Node build, or document libraries.

To try the synthetic three-question demo:

```text
python -c "from pathlib import Path; import shutil; Path('work/demo').mkdir(parents=True, exist_ok=True); shutil.copyfile('evals/files/sample_game.json', 'work/demo/exam.json')"
python scripts/serve_exam_game.py work/demo/exam.json
```

This copies the fixture into a working folder so session files stay out of `evals/`. For authoring details, see the [HTML schema and host workflow](references/html-game.md) and [implementation plan](documentation/html-exam-game-plan.md).

## Word and PDF output

The Word bank uses the bundled template and contains the selected question sections followed by a Model Answer table. Numbering continues across sections. Later question types start on new pages, and difficulty labels are hidden from students.

Every MCQ has four choices and one defensible answer. Its key gives the final shuffled letter and option text. False statements include corrections; essay answers list the required points.

| Model Answer column | Contents |
| --- | --- |
| No. | Matching question number. |
| Answer | MCQ letter and text, True/False judgment, or essay points. |
| Explanation or correction | Reason for the answer or corrected false statement. |
| Source | Document ID and page, slide, section, or other verified locator. Inferences and outside sources are labeled. |

Uploaded files are listed once as S1, S2, and so on. The table uses these IDs, 10-point text, and a repeating header. The formatter preserves the template's page size, margins, heading/list styles, and table style.

PDF mode converts the audited Word intermediate using an available renderer. If conversion is unavailable, the agent explains the limitation and asks you to choose another format. Student-only output omits the visible key while retaining audited answers internally.

## Sources and question quality

| Input | Reading and citations |
| --- | --- |
| PDF lecture, chapter, or paper | Extract text first; cite original 1-based PDF pages, with sections or figure/table numbers where useful. |
| PowerPoint `.pptx` | Extract slide text, tables, grouped text, and existing notes; cite original slide numbers. |
| Legacy PowerPoint `.ppt` | Convert with an available presentation tool before extraction; preserve original slide locators. |
| DOCX paper or notes | Extract paragraphs and tables in body order; cite sections, paragraphs, or tables. Use pages only when actual pagination is available. |
| Markdown or UTF-8 text | Read directly; cite headings or line locators. |

The agent reviews a page, slide, or figure only when needed evidence is missing or unclear in extracted text. Scans may need OCR. If a required conversion or reading tool is unavailable, it asks for a readable export.

In uploaded-material-only mode, every factual premise and answer must follow the selected files. Illustrative scenarios can apply those rules; deductions include an inference label and supporting locators. Expanded mode labels outside information and records the references used to verify it. Uploading a file does not authorize web research by itself.

The selected uploaded material controls the course answer when outside sources disagree. Conflicts within the selected material require clarification or exclusion. Paper questions retain the study's population, assumptions, uncertainty, and limitations; an association must not become a causal claim.

Easy questions test recall or basic understanding. Medium questions require application, comparison, or classification. Hard questions combine supported ideas through a scenario or reasoning task. Ambiguity and obscure wording do not make a question harder.

Distractors should reflect plausible misunderstandings without giving away the answer through length or wording. Answer letters and truth values can repeat; shuffling does not force equal letter counts or alternating patterns. Reusing a concept is allowed when the question tests a different application or angle. Cosmetic rewrites are rejected across originals and retries.

If the material cannot support the requested counts, difficulty, or complete HTML retry pools, the agent explains the bottleneck and asks for revised settings or expanded source scope. It rechecks type and difficulty allocations when counts change.

## Python setup and authoring tools

Text extraction and Word export need the packages in `requirements.txt`. Some agent runtimes already provide them. Otherwise, install Python 3.10+ and Git, then:

```bash
git clone https://github.com/zyadmad56-spec/creating-questions.git
cd creating-questions
python -m venv .venv
```

Activate the environment in Windows PowerShell with `.\.venv\Scripts\Activate.ps1`, or on macOS/Linux with `source .venv/bin/activate`. Use `python3` to create the environment where required. Then install the libraries:

```bash
python -m pip install -r requirements.txt
```

Extract source text before authoring:

```bash
python scripts/extract_source_markdown.py lecture.pdf work/lecture.md
python scripts/extract_source_markdown.py slides.pptx work/slides.md
python scripts/extract_source_markdown.py paper.docx work/paper.md
```

Each run writes Markdown and an `.extraction.json` report while leaving the source unchanged. The helper does not render images, perform OCR, or interpret diagrams. Equations, SmartArt, and difficult tables may need targeted review. See [source reading](references/source-reading.md).

The agent records source-backed concepts in task-local `master_facts.txt`, then authors the question JSON. It independently solves each question from its cited evidence before setting `answer_verified: true`. That flag records the audit; the validator checks structure rather than factual truth or all semantic duplicates.

```bash
python scripts/create_question_bank_docx.py questions.json Subject_Question_Bank.docx
```

The formatter checks counts, evidence records, answers, locators, source permissions, and normalized duplicate stems. The agent checks the saved document and rendered layout when a renderer is available. See the [question data schema](references/question-data.md) for `source_only` and `source_web_general` modes; legacy `pdf_only` and `pdf_web_general` banks remain supported.

## Repository layout

```text
SKILL.md                          Agent workflow and question rules
agents/openai.yaml                Skill display and default prompt
assets/Creating Questions.docx     Blank Word template
assets/exam-game/                 Local HTML, CSS, and JavaScript interface
scripts/extract_source_markdown.py Source extraction with locators
scripts/create_question_bank_docx.py Word export and shuffling
scripts/question_bank_data.py      Shared validation and citations
scripts/exam_game.py               Game state, grading, timers, and retries
scripts/serve_exam_game.py          Local server and launch command
references/                       Source reading and data schemas
documentation/html-exam-game-plan.md Agreed behavior and acceptance checks
evals/                            Python tests, browser smoke test, and synthetic fixtures
.github/workflows/tests.yml        Windows/Ubuntu Python and browser CI
```

Keep lecture files, working facts, generated banks, and session state in your own working folder. The repository ships a blank template and synthetic fixtures.

## Tests

Run all three Python suites from the repository:

```bash
python evals/test_formatter.py
python evals/test_extraction.py
python evals/test_game.py
```

They cover document compatibility, extraction locators, validation, scoring, timers, paused review, retries, and the local API. The browser smoke test checks the complete solo/group workflow, light/dark persistence, unsaved drafts, refresh, host essay marking, timeouts, ties, and mobile layout:

```bash
npm install --no-save --no-package-lock playwright
npx playwright install chromium
node evals/browser_smoke.cjs
```

Node and Playwright are development-only dependencies. GitHub Actions runs the Python suites on Windows and Ubuntu with Python 3.10/3.12, plus the browser smoke test on Ubuntu. Tests use synthetic data; real exams still need a source audit. OCR, legacy PPT conversion, and Word-to-PDF rendering depend on the tools available to the agent.
