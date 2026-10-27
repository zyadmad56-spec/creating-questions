# Acceptance report — plan 0.1 programming questions upgrade

Recorded 27 October 2026. Environment: Windows 10.0.26200, Python 3.14.7, Microsoft Word 16.0 (COM), gcc 16.1.0 (MSYS2, C only), Pygments 2.20, python-docx/pypdf/python-pptx per `requirements.txt`, pywin32 per `requirements-dev.txt` (Windows only). LibreOffice: not installed (the fallback path exists but was not exercised). Every status below is one of: automated pass, manual pass, skipped, unavailable — never merged.

## Required existing suites

| Command | Result |
|---|---|
| `python evals/test_formatter.py` | **24 tests OK** (legacy regression retained) |
| `python evals/test_extraction.py` | **6 tests OK** (legacy extraction retained) |

## New suites

| Suite | Tests | Covers |
|---|---|---|
| `evals/test_interview.py` | 8 OK | A01–A03, A06: scripted interview fixtures, remembered preference, corrupt settings never overwritten. |
| `evals/test_code_recovery.py` | 13 OK | A05: synthetic PDF/PPTX/DOCX/MD code recovery, display-label mapping, layout mode, review states, locator retention. |
| `evals/test_blueprint.py` | 8 OK | A06–A07: allocation feasibility, linked permission, snippet reclassification, density warnings, conventional-essay reservation. |
| `evals/test_schema.py` | 16 OK | A11–A13: v2 normalization/validation (negative-case table), seeded ordering, manifest, token resolution. |
| `evals/test_layout.py` | 13 OK | A02, A14–A19: Card/Classic layout, chips, adaptive options, saved-format round trips, corrupt profiles, manifest-first, real Word PDF conversion. |
| `evals/test_execution.py` | 13 OK | A21–A22: screen refusals, timeouts, missing runtimes, variant construction, linked state, staleness, determinism, cleanup, real C compile+run. |

Total: 101 automated tests, all passing (27 October 2026 run).

## Acceptance matrix results

- **A01 English/retained interview** — automated pass (fixtures). No already-answered setting is asked twice; missing items are listed, never invented.
- **A02 deliverable/format choice, saved layouts** — automated pass (fixtures + profile round trips). The opening question and Card variant selection are contract-tested.
- **A03 no-code and function-only material** — automated pass (fixtures + q_isna in the semantic bank).
- **A04 language/dialect detection, unavailable runtimes** — automated pass for detection evidence and per-block metadata; **C# / Java / JavaScript / SQL / NoSQL execution is unavailable-by-design disclosure**: detection and first-class content are implemented, execution exists for Python and C (gcc present); other languages record `unavailable` honestly when their runtime is absent.
- **A05 text-first extraction** — automated pass; targeted visual inspection was performed only on the synthetic prototype pages; no private page was rendered.
- **A06 block arithmetic** — automated pass at interview, blueprint, and schema layers.
- **A07 independent reset and hard chains** — automated pass; chain keys verified by execution from correct upstream state.
- **A08 supported constructs, meaningful variation** — manual pass recorded in the semantic evaluation (construct inventory from the extractor constrains authoring; similarity review heuristic documented).
- **A09 one correct answer, plausible wrong options** — manual pass (semantic evaluation) including the two-valid-options negative case.
- **A10 source/key errors do not propagate** — manual pass (printed-key contradiction case excluded/repaired).
- **A11 essay styles and quotas** — automated pass (matrix validation) + manual review of all four styles with executed reference solutions.
- **A12 atomic shuffle and option correspondence** — automated pass (seeded ordering tests).
- **A13 stable references** — automated pass (token resolution tests, stale-line negative case).
- **A14 selectable code, separate per-block numbering** — automated pass (XML-level) + **manual pass** in the Gate A prototype: code-column copy produced byte-identical code for 9/10/100-line cards (blank lines, Unicode, quotes, long lines included); full-card selection includes the numbers by design.
- **A15 Monokai and print-friendly** — automated pass (tokens) + manual pass for Monokai page images; the print variant is implemented and token-tested but its rendered pages were not separately inspected (disclosed).
- **A16 long-code pagination** — manual pass: the 100-line card split across pages with the gutter continuing and no truncation; continuation headers for multi-chunk blocks are a formatter capability not exercised by a dedicated long fixture in this run (disclosed).
- **A17 PDF from finalized Word** — automated + manual pass: Word COM `ExportAsFixedFormat` converts the same DOCX; manifest saved first; PDF text contains the code; 7-page semantic bank converted.
- **A18 PDF copying** — partially verified: PDF text extraction and page-image review done; **in-viewer selection/copy was not automated** and requires a manual confirmation in the declared PDF viewer (disclosed limitation; the Word side is fully proven).
- **A19 saved custom formats** — automated pass (save/load round trip, corrupt profile preserved, built-in ids protected).
- **A20 Classic/legacy compatibility** — automated pass (all 24 legacy formatter tests, legacy v2 dispatch, template geometry tests).
- **A21 deterministic constrained execution** — automated pass; the educational screen + `-I` interpreter + temp dir + timeout is the audited-educational-code enforcement; OS-level sandboxing is NOT claimed (disclosed in the runtime record's `enforcement` field).
- **A22 distinct verification layers reported honestly** — automated pass (status enums; `not_applicable` vs `unavailable` vs `failed`); reports keep source audit separate from execution.
- **A23 local-only privacy, clean package** — verified by inspection at packaging time (Phase 8); no private course file is referenced by any committed fixture.
- **A24 truthful ledger** — this report and the phase ledger in the plan index.

## Manual visual and copy verification

Rendered and inspected page images: Gate A prototype (3 pages) and the semantic bank (7 pages): headers, gutter alignment, Monokai colors, chips, option grids, section boundaries, linked notice, Model Answer table (reference solutions, test cases, source registry). Copy checks in Word: 3/3 exact code-column copies; pasted text parsed and executed. **Not performed:** PDF in-viewer copy (needs manual confirmation), print-variant page inspection, dedicated continuation-header fixture.

## CI

`.github/workflows/tests.yml` runs all eight suites on Windows/Ubuntu with Python 3.10/3.12. The layout suite skips the Word COM conversion test where pywin32/Word is absent; the execution suite reports C as unavailable rather than failing where no compiler exists.
