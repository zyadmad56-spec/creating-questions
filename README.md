# creating-questions

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Tests](https://github.com/zyadmad56-spec/creating-questions/actions/workflows/tests.yml/badge.svg)

Turn your lecture notes into a Word question bank with multiple-choice, True/False, and essay questions. Set the counts and difficulty for each type, then use the Model Answer table to check your work against the uploaded material.

The skill accepts PDFs, PowerPoint slides, and research papers. It reads extracted text first and uses a page or slide image only when needed evidence is missing or unclear. Questions, answers, prompts, and documentation are in English.

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

A student-only document is available when you explicitly request it. The agent still checks the answers internally. PDF output requires an available document renderer and an explicit request.

## 3. The conversation before generation

Attach the material and invoke `$creating-questions`. The agent collects these settings one stage at a time:

1. Which files, chapters, pages, slides, or paper sections to cover.
2. The total number of questions.
3. MCQ, True/False, essay, or a mixed bank. A mixed bank needs exact counts per type.
4. Easy, medium, and hard counts separately for each selected type.
5. Uploaded material only, or uploaded material plus the web and general knowledge.

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

Each run writes Markdown and an `.extraction.json` report. The helper preserves original source identifiers, leaves the input unchanged, and renders no images. A scan or image-only slide gets a review notice rather than invented text. The agent decides which selected units need local OCR, another parser, or a targeted visual check.

The extractor does not perform OCR, interpret pictures, fully decode SmartArt, or guarantee complete equation/table extraction. A page with readable text can still contain a needed figure. See [source reading](references/source-reading.md) for the checks and citation rules.

### Audited question data and Word export

The agent saves distinct concepts and evidence in task-local `master_facts.txt`, then drafts the question data. Before export it solves each item again from its supporting source: correct choice and distractors, True/False judgment and correction, or every essay answer point.

The JSON records counts, difficulty, answers, explanations, evidence, and locators. Set `answer_verified: true` only after that review. The flag records a completed audit; it does not establish correctness by itself.

```bash
python scripts/create_question_bank_docx.py questions.json Subject_Question_Bank.docx
```

The formatter rejects count mismatches, missing evidence, invalid answers, malformed locators, unauthorized source kinds, and normalized duplicate stems before writing the output. It does not detect all semantic duplicates or establish whether citations support an answer. The agent checks the cited evidence and compares what each question tests.

Use `source_only` or `source_web_general` for mixed document formats. Existing `pdf_only` and `pdf_web_general` banks remain supported. Read the [JSON schema and source examples](references/question-data.md) before assembling a bank.

The agent checks the saved document's numbering, answer correspondence, source locators, and type/difficulty counts. It inspects rendered Word layout when a renderer is available. If rendering is unavailable, it discloses that limitation and performs structural checks.

### Repository layout

```text
creating-questions/
  README.md
  SKILL.md                         # Agent workflow and question rules
  LICENSE
  requirements.txt
  agents/openai.yaml               # Skill display and default prompt
  assets/Creating Questions.docx    # Academic Word template
  scripts/
    extract_source_markdown.py     # Text extraction with source locators
    create_question_bank_docx.py   # Validation, shuffling, and Word export
  references/
    source-reading.md              # Reading paths and targeted review
    question-data.md               # JSON schema and citation records
  evals/
    test_extraction.py             # Parser behavior and source preservation
    test_formatter.py              # Validation and saved Word correspondence
    evals.json                    # Agent behavior scenarios
    files/sample_questions.json    # Synthetic formatter fixture
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

Run both functional suites from a writable folder:

```bash
python evals/test_formatter.py
python evals/test_extraction.py
```

The tests check extraction locators, tables/notes, input preservation, scanned-page notices, mode restrictions, difficulty quotas, duplicate rejection, shuffled answer correspondence, template geometry, and Word citation layout. They use synthetic data. They do not establish factual correctness for a real course, full extraction of every possible file, or visual layout in every Word viewer.

GitHub Actions runs the suites for pushes and pull requests on Windows and Ubuntu with Python 3.10 and 3.12. The workflow tests the helpers; it does not publish generated banks.

OCR, legacy PPT conversion, and Word-to-PDF rendering depend on tools available in the agent's environment. Difficult layouts need targeted review. A source audit reduces errors but does not justify a promise of 100% infallibility.
