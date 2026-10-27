# creating-questions

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Tests](https://github.com/zyadmad56-spec/creating-questions/actions/workflows/tests.yml/badge.svg)

Turn your lecture notes into a Word question bank with multiple-choice, True/False, and essay questions. Set the counts and difficulty for each type, then use the Model Answer table to check your work against the uploaded material. For programming material, the bank adds shared code blocks with their own line-number gutters, function/API questions, code-writing essays, and locally executed answer verification.

The skill accepts PDFs, PowerPoint slides, and research papers. It reads extracted text first and uses a page or slide image only when needed evidence is missing or unclear. Deliverables are Word, PDF, or both — the PDF is converted from the finalized Word file, never redrawn. Questions, answers, prompts, and documentation are in English.

## Quick install

Install the skill with the [Skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add zyadmad56-spec/creating-questions
```

For Codex, install it globally so it is available across projects:

```bash
npx skills add zyadmad56-spec/creating-questions --agent codex --global
```

Attach your material and ask the agent to use `$creating-questions`. The Python helpers also need the libraries listed in [Local Python setup](#local-python-setup).

## 1. How the workflow fits together

The agent handles the conversation, reads your material, writes the questions, and checks their answers. Two Python helpers handle repeatable file operations:

- `extract_source_markdown.py` extracts source text and tables into Markdown with original locators. It also reports units that may need a closer look.
- `create_question_bank_docx.py` validates the audited question data, shuffles questions and MCQ choices, and writes the Word file using the included template.

The formatter cannot determine whether an answer is factually right. The agent must verify it against the cited passage, table, or figure before export. Likewise, a successful extraction does not prove that every diagram or equation was captured.

### Supported material

| Input | Reading path | Answer references |
| --- | --- | --- |
| PDF lecture or book chapter | Extract text with original PDF page headings; check specific missing content when needed. | Filename and 1-based PDF page; optional printed page or section. |
| PowerPoint `.pptx` | Extract slide text, tables, grouped text, and existing speaker notes. | Filename and original slide number. |
| Legacy PowerPoint `.ppt` | Convert to PPTX or PDF using an available presentation tool, then extract. The helper cannot read binary PPT directly. | Original slide number, including after conversion. |
| Research paper in PDF | Read the selected methods, findings, and limitations with their supporting tables. | PDF page plus section, table, or figure when useful. |
| Paper or notes in DOCX | Extract paragraphs and tables in body order. | Section, paragraph, or table; a page only when actual pagination is available. |
| Markdown or UTF-8 text | Read the original text. | Original heading or line locator. |

If an input needs conversion or OCR and the environment cannot provide it, the agent asks for a readable export. It should not claim to have understood inaccessible content.

## 2. What the Word file contains

The default output is one document named after the subject:

```text
Subject_Question_Bank.docx
  Title and question totals
  Multiple Choice Questions
  True or False Questions
  Essay Questions
  Model Answer
    Source file legend
    Answer table
```

Only selected types appear. Numbering continues across sections. The first section starts below the title; later types start on new pages. Difficulty levels are mixed within each section and stay hidden from the student.

Every MCQ has four choices and one defensible answer. The key prints its final letter and option text, so reordering choices cannot leave an old letter behind. True/False answers include a correction for every false statement. Essay answers list the points a correct response should cover.

The Model Answer table comes after all questions:

| Column | Contents |
| --- | --- |
| No. | The matching question number. |
| Answer | Final MCQ letter/text, True/False judgment, or essay points. |
| Explanation or correction | A brief reason or the corrected false statement. |
| Source | Uploaded document ID with a page, slide, or section locator; inference or outside-source labels where applicable. |

The key identifies uploaded files once as S1, S2, and so on. Rows use those short IDs instead of repeating a long filename. The table uses 10-point text and repeats its header across pages. The formatter preserves the template's page size, margins, heading/list styles, and table style.

A student-only document is available when you explicitly request it. The agent still checks the answers internally. PDF output requires an available local renderer (Microsoft Word via COM, or LibreOffice) and an explicit request; the PDF is converted from the same finalized Word file, so its order, numbers, and answers always match. When no converter is available the agent keeps the DOCX and reports the unmet PDF requirement.

### Document formats

**Classic** preserves the academic template exactly and is the default for existing banks. **Card** adds code-specific design for programming banks: a light header bar (`Code Block 1 — Questions 1 to 4` / `Language: Python 3.x`), a dark Monokai code area (or a print-friendly light variant), syntax coloring that never changes the characters, a separate per-block line-number gutter, inline code chips in prompts and options, and choices laid out two by two when short or one per row when long.

Code stays real, selectable text. Selecting the code column (click in the first code line, extend to the last) and copying yields exactly the program — the gutter numbers are a separate table column and are not part of the code text. Copying the full card includes the numbers by design. Saved custom formats live in a local, git-ignored `formats/` library; see [saved formats](references/saved-formats.md).

## 3. The conversation before generation

Attach the material and invoke `$creating-questions`. The agent first asks two appearance questions — "Would you like Word, PDF, or both? Which document format should I use: a saved format, your reference/template, Classic, or Card?" — and then collects these settings one stage at a time:

1. Which files, chapters, pages, slides, or paper sections to cover.
2. The total number of questions.
3. MCQ, True/False, essay, or a mixed bank. A mixed bank needs exact counts per type.
4. Easy, medium, and hard counts separately for each selected type.
5. Uploaded material only, or uploaded material plus the web and general knowledge.

If the material contains programming, the interview extends: shared code blocks, function/API questions, or a mixture; per-difficulty block counts, questions per block, and approximate code size; whether hard shared blocks may contain linked questions (asked once, remembered locally, changeable anytime); and, for code essays, which of the four styles (scenario, complete-the-code, find-and-fix, trace/explain) with counts and difficulty per style.

The agent uses settings you've already supplied and asks only for what's missing. Each type's difficulty counts must add up to its question count, and the type counts must add up to the total.

For example:

| Type | Total | Easy | Medium | Hard |
| --- | ---: | ---: | ---: | ---: |
| MCQ | 80 | 30 | 30 | 20 |
| True/False | 50 | 20 | 10 | 20 |
| Essay | 20 | 5 | 10 | 5 |
| Total | 150 | 55 | 50 | 45 |

You can provide everything in one message:

```text
Use $creating-questions with the whole attached lecture PDF. Use the PDF only.
Create 150 questions: 80 MCQ, 50 True/False, and 20 essay.
MCQ: 30 easy, 30 medium, 20 hard.
True/False: 20 easy, 10 medium, 20 hard.
Essay: 5 easy, 10 medium, 5 hard.
```

If the material cannot support the requested count or difficulty, the agent explains the estimated limit. You choose the revised total, type counts, and difficulty counts. It does not silently reduce the bank or fill it with cosmetic rewrites.

### Difficulty and question variety

Easy questions test recall or basic understanding. Medium questions ask for application, classification, or comparison. Hard questions combine supported ideas in a scenario, condition, or reasoning task. Confusing language and facts absent from the material do not count as difficulty.

The skill checks for guessing cues. The correct MCQ choice should not consistently be the longest, the most detailed, or the only phrase copied from the source. Wrong choices should reflect plausible misunderstandings. In True/False questions, "not" does not automatically mean false; negative statements can be true.

Answer letters and truth values may repeat. The formatter shuffles naturally, without forcing equal letter counts or a predictable alternating pattern. Questions can reuse a concept when they test a different application, condition, or comparison. The agent rejects simple rewrites of the same question, including across question types.

### Source policy

In uploaded-material-only mode, factual premises and answers must follow the selected files. Illustrative scenarios are allowed if the source supplies every rule needed to solve them. Deductions carry an inference label and the supporting locators.

In expanded mode, external information must stay within the subject scope. The key labels web material as an outside source and includes a direct title/URL. The agent checks model recollections against an allowed reference and labels them as general knowledge. It cannot attribute them to an uploaded page.

The uploaded material controls the course answer. For a PDF-based bank, the PDF remains the first and final reference when outside information disagrees. Contradictory or ambiguous passages within the selected files need clarification or exclusion.

For research papers, questions retain the reported population, assumptions, uncertainty, and limitations. An association does not become a causal claim, and a hypothesis does not become a finding.

## 4. Technical guide

### Text extraction before images

Run the extractor in the repository or installed skill folder:

```bash
python scripts/extract_source_markdown.py lecture.pdf work/lecture.md
python scripts/extract_source_markdown.py slides.pptx work/slides.md
python scripts/extract_source_markdown.py paper.docx work/paper.md
```

Each run writes Markdown and an `.extraction.json` report. The helper preserves original source identifiers, leaves the input unchanged, and renders no images. When the material contains code, the report additionally lists recovered code candidates (with detected language and evidence, printed display-number labels mapped to line indexes, and a review status), a construct inventory per language, and Python syntax-check results. For PDFs, `--layout auto` (or explicit pages such as `--layout 4,7`) re-extracts only code-bearing pages in layout mode so flattened indentation can be recovered under its own locator. A scan or image-only slide gets a review notice rather than invented text. The agent decides which selected units need local OCR, another parser, or a targeted visual check.

The extractor does not perform OCR, interpret pictures, fully decode SmartArt, or guarantee complete equation/table extraction. Recovered code is recovery assistance, not proof of correct syntax or reading order. See [source reading](references/source-reading.md) for the checks and citation rules.

### Audited question data and Word export

The agent saves distinct concepts and evidence in task-local `master_facts.txt`, then drafts the question data. Before export it solves each item again from its supporting source: correct choice and distractors, True/False judgment and correction, or every essay answer point.

The JSON records counts, difficulty, answers, explanations, evidence, and locators. Set `answer_verified: true` only after that review. The flag records a completed audit; it does not establish correctness by itself.

```bash
python scripts/create_question_bank_docx.py questions.json Subject_Question_Bank.docx
python scripts/create_question_bank_docx.py questions.json Subject_Question_Bank.docx \
    --format builtin-card --variant monokai
python scripts/create_question_bank_docx.py questions.json Subject_Question_Bank.docx \
    --format builtin-card --pdf Subject_Question_Bank.pdf
```

The formatter rejects count mismatches, missing evidence, invalid answers, malformed locators, unauthorized source kinds, inconsistent groups or dependencies, and normalized duplicate stems before writing the output. Version-2 banks (with `schema_version: 2`) add stable IDs, code blocks, groups, dependency chains, essay styles, and execution records; legacy JSON keeps working unchanged. A render manifest (`Subject_Question_Bank.manifest.json`) is saved beside the DOCX with the final order, option letters, block/line numbers, and code hashes — a PDF request converts that same document rather than reshuffling. The formatter does not detect all semantic duplicates or establish whether citations support an answer. The agent checks the cited evidence and compares what each question tests.

Use `source_only` or `source_web_general` for mixed document formats. Existing `pdf_only` and `pdf_web_general` banks remain supported. Read the [JSON schema and source examples](references/question-data.md) before assembling a bank.

The agent checks the saved document's numbering, answer correspondence, source locators, and type/difficulty counts. It inspects rendered Word layout when a renderer is available. If rendering is unavailable, it discloses that limitation and performs structural checks.

### Repository layout

```text
creating-questions/
  README.md
  SKILL.md                         # Agent workflow and question rules
  LICENSE
  requirements.txt
  requirements-dev.txt             # Optional Windows COM dependencies
  agents/openai.yaml               # Skill display and default prompt
  assets/Creating Questions.docx    # Academic Word template
  scripts/
    extract_source_markdown.py     # Text extraction, code recovery, language detection
    create_question_bank_docx.py   # CLI: validation, shuffling, Word/PDF export
    qbank_interview.py             # Interview contract and local settings
    qbank_blueprint.py             # Capacity and block allocation
    qbank_schema.py                # Schema v1/v2 model, validation, variants
    qbank_order.py                 # Final ordering, references, render manifest
    qbank_formats.py               # Built-in and saved format profiles
    qbank_render.py                # Card code cards, chips, DOCX-to-PDF
    qbank_document.py              # Version-2 document assembly
    qbank_execution.py             # Screened local execution of variants
  references/
    source-reading.md              # Reading paths, code recovery, targeted review
    question-data.md               # Legacy and version-2 JSON schemas
    programming-interview.md       # Programming interview contract
    programming-design.md          # Programming authoring rules
    programming-execution.md       # Execution and audit contract
    saved-formats.md               # Format profiles and local settings
    troubleshooting.md             # Recovery steps
  evals/
    test_formatter.py              # Legacy validation and Word correspondence
    test_extraction.py             # Parser behavior and source preservation
    test_interview.py              # Interview fixtures and settings persistence
    test_blueprint.py              # Capacity allocation
    test_schema.py                 # Model validation and ordering
    test_code_recovery.py          # Code recovery fixtures
    test_execution.py              # Screened execution
    test_layout.py                 # Card layout, formats, PDF path
    ACCEPTANCE-REPORT.md           # Plan 0.1 acceptance matrix results
    files/                         # Synthetic public fixtures
  .github/workflows/tests.yml
```

Your lecture files, extracted text, working facts, and generated banks belong in your own working folder. This repository contains a blank template and synthetic fixtures, not a student's source material.

## 5. Installation and use

### Install the agent skill

Use the Skills CLI to discover or install the skill:

```bash
npx skills add zyadmad56-spec/creating-questions --list
npx skills add zyadmad56-spec/creating-questions
```

You can select an agent or install globally:

```bash
npx skills add zyadmad56-spec/creating-questions --agent codex
npx skills add zyadmad56-spec/creating-questions --agent claude-code
npx skills add zyadmad56-spec/creating-questions --agent cursor
npx skills add zyadmad56-spec/creating-questions --global
```

The [Skills CLI](https://github.com/vercel-labs/skills) installs the skill files. The Python helpers also need their libraries in the environment your agent uses. Some agent runtimes already include them; otherwise install the requirements below.

### Local Python setup

Install Python 3.10 or newer and Git, then clone the repository:

```bash
git clone https://github.com/zyadmad56-spec/creating-questions.git
cd creating-questions
python -m venv .venv
```

Activate it in Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux, use `python3` to create the environment if needed, then activate it:

```bash
source .venv/bin/activate
```

Install the helper dependencies:

```bash
python -m pip install -r requirements.txt
```

Optional, Windows only: `python -m pip install -r requirements-dev.txt` adds `pywin32` for Word COM PDF conversion and the automated copy checks. Without it, Word output still works and PDF conversion is reported as unavailable.

This is an agent skill with file-processing helpers. It does not provide a standalone AI question generator or a hosted service. Your agent reads `SKILL.md` and performs the interview, authoring, and source audit.

### Example requests

```text
Use $creating-questions to make revision questions from the whole attached PPTX.

Use $creating-questions with the attached research paper. Cover Methods, Results,
and Discussion using only that paper. Make 20 MCQ questions:
5 easy, 10 medium, and 5 hard.

Use $creating-questions with pages 4-18 of the PDF. Create a student-only Word bank.
```

The agent asks only for settings missing from the request. Attaching a file or installing the skill does not authorize browsing external sources; the source choice must be explicit.

## 6. Tests and practical limits

Run the functional suites from a writable folder:

```bash
python evals/test_formatter.py
python evals/test_extraction.py
python evals/test_interview.py
python evals/test_blueprint.py
python evals/test_schema.py
python evals/test_code_recovery.py
python evals/test_execution.py
python evals/test_layout.py
```

The tests check extraction locators and code recovery, tables/notes, input preservation, mode restrictions, difficulty quotas, group/dependency rules, seeded ordering with stable references, interview fixtures and settings persistence, screened execution (output, exceptions, timeouts, refusals), Card layout and saved-format round trips, and Word citation layout. They use synthetic data only. They do not establish factual correctness for a real course, full extraction of every possible file, OS-level sandboxing, or visual layout in every Word/PDF viewer; the recorded copy and conversion evidence lives in `evals/files/copy_prototype/PROTOTYPE-REPORT.md` and `evals/ACCEPTANCE-REPORT.md`.

GitHub Actions runs the suites for pushes and pull requests on Windows and Ubuntu with Python 3.10 and 3.12. Renderer and compiler integrations (Word COM, gcc) are exercised only where available and are reported honestly elsewhere. The workflow tests the helpers; it does not publish generated banks.

OCR, legacy PPT conversion, and Word-to-PDF rendering depend on tools available in the agent's environment. Difficult layouts need targeted review. A source audit reduces errors but does not justify a promise of 100% infallibility.
