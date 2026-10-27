# Troubleshooting and recovery

Concrete recovery steps for the failure modes the skill can actually hit. Every case preserves user files; nothing is silently overwritten.

## Missing PDF renderer

**Symptom:** `--pdf` used, result reports `{"status": "unavailable", ...}`.

**Meaning:** No local Microsoft Word (COM) or LibreOffice (`soffice` on PATH) converter was available. The finalized DOCX is kept and is still the deliverable of record.

**Recovery:** Install or repair Microsoft Word, or install LibreOffice and ensure `soffice` is on PATH, then re-run the same command — the DOCX is re-converted, never re-shuffled (the render manifest beside it is reused). Never accept a separately drawn PDF as a substitute; do not upload the document to an external conversion service.

## Word COM conversion fails

**Symptom:** `Microsoft Word COM conversion failed: ...` in the unavailable reason.

**Recovery:** Close open Word dialogs/instances, confirm the DOCX opens in Word manually, then retry. On Windows, `pywin32` must be installed in the same Python environment (`pip install -r requirements-dev.txt`). Record the exact COM error if it persists; conversion is only claimed when `verify_pdf` confirms a non-empty PDF with at least one page.

## Damaged or ambiguous code extraction

**Symptom:** `code_candidates` entries with `review_status: needs_review`, syntax-check failures, or unreadable locators.

**Recovery:** Follow the escalation order in [source-reading.md](source-reading.md): inspect the extracted Markdown → retry with `--layout auto` or explicit pages for PDFs → local OCR for scans → one targeted page/slide/region view. Log what you inspected in `targeted_reviews`. Stop dependent generation for regions that stay unreadable; a fill-the-gap exercise, pseudocode, or deliberately broken program is legitimate content and must be preserved, not repaired.

## Corrupt local settings

**Symptom:** `SettingsCorruptError: Local settings file ... is unreadable (...)`.

**Recovery:** The file is named in the error. Fix the JSON by hand or delete it; the skill never overwrites it automatically. After removal, the next bank asks the hard-dependency question again (missing settings mean ask). The same policy applies to a corrupt saved-format profile (`FormatError ... unreadable; it was not modified`).

## Missing or invalid saved format

**Symptom:** `Saved format '...' was not found` / `Unsupported format_version` / references a missing `template.docx`.

**Recovery:** Choose another format or repair the profile directory (`format.json` + optional `template.docx`) under `<skill root>/formats/`. Built-in ids cannot be shadowed; rename the custom format instead.

## Unresolved source conflicts

**Symptom:** A printed answer key contradicts the executable code, or two premises disagree.

**Recovery:** Keep the Source issue record (locator, original wording/key, observed conflict, disposition), exclude the unresolved item, and reconcile quotas through the capacity renegotiation. If execution is unavailable, mark the conflict suspected and unresolved — do not claim it was empirically proven and never reproduce a wrong printed key.

## Unverified or stale execution records

**Symptom:** `stale_execution_records(model)` lists questions, or export rejects a `passed` record.

**Recovery:** Re-run `qbank_execution.run_question` for the listed questions after the code changed; authoring edits invalidate earlier evidence by hash. A missing runtime is recorded as `unavailable` — complete the source audit instead and disclose the limitation rather than guessing exact outputs.

## Fonts and rendering

Consolas (or the profile's `code_font`) must be installed for correct code metrics; a missing font falls back to a system monospace and page images may shift. Verify installed fonts before claiming visual fidelity, and inspect the rendered page images after any format change.
