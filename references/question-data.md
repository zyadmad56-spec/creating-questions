# Question data for the Word formatter

Save UTF-8 JSON in a task working directory. The template is resolved relative to the skill directory; use a Python environment with `python-docx`. Banks missing quotas or evidence are rejected; complete the audit before export.

## Bank settings

```json
{
  "title": "Subject Question Bank",
  "language": "en",
  "source_mode": "source_only",
  "counts": {"mcqs": 50, "true_false": 45, "essays": 5},
  "difficulty_counts": {
    "mcqs": {"easy": 20, "medium": 20, "hard": 10},
    "true_false": {"easy": 20, "medium": 5, "hard": 20},
    "essays": {"easy": 1, "medium": 2, "hard": 2}
  },
  "include_answer_key": true,
  "mcqs": [],
  "true_false": [],
  "essays": []
}
```

The empty arrays illustrate settings only: a usable bank must have exactly the declared counts. All three keys are required in `counts` and `difficulty_counts`, including zeros for unselected types. `language` defaults to `en`; only English output is supported. Translate source meaning faithfully before assembling question content, options, explanations, answer points, and evidence. Preserve original source identifiers and URLs. `include_answer_key` defaults to true; set it to false only on explicit request.

`source_mode` records the explicit user choice:

- `source_only`: PDF, slide, and document sources only. Web and general-knowledge records are forbidden.
- `source_web_general`: uploaded material plus authorized, clearly labeled web and verified general knowledge.
- `pdf_only`: supported for existing PDF banks; accepts only `pdf` and `pdf_inference` sources.
- `pdf_web_general`: supported for existing expanded PDF banks; external rows retain the "Outside PDF" label.

## Common fields

Every question has `difficulty` (`easy`, `medium`, or `hard`), nonempty `explanation`, a nonempty `sources` list, and `answer_verified: true` after the agent completes the source audit. Evidence is internal and is not printed verbatim in the final table. The explanation should justify the answer briefly rather than merely restate it.

## MCQ

```json
{
  "question": "Which description matches the rule in this chapter?",
  "options": ["First description", "Second description", "Third description", "Fourth description"],
  "correct": "B",
  "difficulty": "medium",
  "explanation": "Explain the decisive distinction using the source.",
  "answer_verified": true,
  "sources": [{"kind": "pdf", "document": "Subject.pdf", "pdf_page": 7,
               "locator": "Section 2 table", "evidence": "A concise verified paraphrase of the supporting passage."}]
}
```

Supply options without A-D labels; the formatter adds labels, randomly reorders options, and updates the correct letter. Avoid options that refer to positions, letter combinations, or "the above". Correct letters refer to **input** order; final Word answers refer to **final** order.

## True or False

```json
{
  "statement": "A clearly false statement according to the selected source.",
  "correct": "False",
  "correction": "The corrected statement as supported by the source.",
  "difficulty": "easy",
  "explanation": "Why the original statement is false.",
  "answer_verified": true,
  "sources": [{"kind": "pdf", "document": "Subject.pdf", "pdf_page": 8,
               "evidence": "Supporting rule and any relevant conditions."}]
}
```

Use the exact JSON strings `True` or `False`, not booleans. `correction` is required for `False`. The Word response line is `True / False` and the judgment is hidden until the answer table.

## Essay

```json
{
  "question": "Compare two processes described in the chapter.",
  "model_answer": ["First required comparison point.", "Second required comparison point."],
  "difficulty": "hard",
  "explanation": "The key distinction connecting these points.",
  "answer_verified": true,
  "sources": [{"kind": "pdf_inference", "document": "Subject.pdf", "pdf_page": 9,
               "evidence": "The first verified premise."},
              {"kind": "pdf_inference", "document": "Subject.pdf", "pdf_page": 10,
               "evidence": "The second verified premise."}]
}
```

## Sources

Each source must have `evidence`: a verified concise paraphrase or permitted short excerpt. Evidence must actually support the item; the formatter only checks that it is present.

- `pdf`: requires `document`, positive 1-based `pdf_page`, and `evidence`. Optional `printed_page` and `locator` disambiguate page numbering and passages.
- `pdf_inference`: same fields as `pdf`, printed as **Inference from PDF**. Supply all pages/premises needed for the deduction.
- `slides`: requires `document`, positive 1-based `slide`, and `evidence`. Optional `locator` identifies a diagram, table, or speaker note. Cite the original slide even when reading a converted PDF.
- `slides_inference`: same fields as `slides`, printed as **Inference from slides**.
- `document`: requires `document`, a nonempty `locator`, and `evidence`. Use a section/paragraph/table or original text line locator. Optional `page` must be a positive integer taken from actual stable pagination; do not invent Word pages.
- `document_inference`: same fields as `document`, printed as **Inference from source**.
- `web`: requires `title`, direct HTTP(S) `url`, and `evidence`. Allowed only in expanded modes; printed as **Outside uploaded material: Web** (or **Outside PDF: Web** for legacy PDF banks).
- `general`: requires `evidence` and `verified_against`, identifying the allowed source actually used to check the recollection. Allowed only in expanded modes; printed as **Outside uploaded material: General knowledge from model** (or **Outside PDF** for legacy banks). Add the verifying uploaded/web record so the reader can locate the check. Never fabricate verification or bypass source-only mode.

Examples for slides and manuscript sources:

```json
{"kind": "slides", "document": "Lecture.pptx", "slide": 12,
 "locator": "Comparison table", "evidence": "A verified supporting distinction."}
```

```json
{"kind": "document_inference", "document": "Paper.docx",
 "locator": "Results, Table 2", "evidence": "A verified premise for the deduction."}
```

The selected uploaded material controls course answers. A PDF controls a PDF-based bank. Exclude contradictory external claims. The formatter cannot detect source contradictions, invented locators, wrong answers, or semantic near-duplicates; it is not a factual-verification engine.

## Word layout and citations

The template provides page geometry, heading/list styles, and the answer-table style. Type sections start on separate pages after the first. The formatter uses explicit question numbers and A-D option labels, suppressing extra automatic bullets. Difficulty labels, sources, and answers remain outside the student question sections.

The **Model Answer** table follows all questions. Its header repeats, and its text uses 10-point type. Uploaded filenames appear once beside the key as S1, S2, and so on. Each row cites a short document ID and the actual PDF page, slide, or document locator. Inference labels remain visible. Identical citation labels within an answer row are consolidated; internal evidence remains in JSON. External references retain direct titles/URLs and explicit outside-source labels.

## Built-in checks and regression tests

The formatter checks counts and difficulty quotas per type, positive PDF/slide/page indices, document locators, allowed source kinds, evidence, single correct MCQ labels, distinct options, True/False judgments, false corrections, essay points, and normalized non-repeated stems. It validates before creating or overwriting output.

Run the functional tests from a writable directory. They use a `work/` folder for temporary DOCX files:

```text
python evals/test_formatter.py
```

`evals/files/sample_questions.json` is a synthetic formatter fixture, not a bank derived from a real university PDF and not a difficulty-quality benchmark.
