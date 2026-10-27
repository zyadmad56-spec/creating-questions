# Saved formats and local settings

## Format selection

Every new bank establishes two settings at the start: the deliverable (Word, PDF, or both) and the appearance. Available appearances are listed by `qbank_formats.list_available_formats(root)`: the built-ins **Classic** and **Card** (with `monokai` and `print` variants) plus any saved formats in the local library. A remembered format may be offered first; the user may choose differently for every bank. Output file type and visual theme are separate choices.

## Built-in profiles

- **Classic** — the original academic template and four-column answer table. It is the default for legacy (versionless) formatter JSON and remains available for version-2 banks. Version-2 code rendered in Classic appears as plain selectable monospace text without a gutter.
- **Card** — academic document foundation plus code cards: light header bar (`Code Block N — Questions X to Y` / `Language: <language>`), dark Monokai code area with a separate per-block gutter, Pygments syntax runs that never change characters, backtick inline-code chips, and adaptive option layout (two by two when short, one per row when long). The `print` variant swaps to a light, print-friendly palette.

## The saved-format library

The library lives at `<skill root>/formats/` and is git-ignored. Each format is a directory containing `format.json` and optionally `template.docx`:

```json
{
  "format_version": 1,
  "id": "my-card",
  "name": "My Card",
  "variants": ["monokai", "print"],
  "code_font": "Consolas",
  "code_font_size_pt": 9.5,
  "option_layout": "adaptive",
  "colors": {"monokai": {"code": "272823", "gutter": "1e1e1e", "header": "e3e8ef",
                          "chip": "f2f5f9", "gutter_text": "8f908a",
                          "code_text": "f8f8f2", "highlighter": "monokai"}}
}
```

Rules enforced by `qbank_formats.py`:

- Profiles are declarative layout data only. Runtime paths and converter commands are never read from a profile, and no uploaded file can specify executable commands.
- `format_version` must match; unsupported versions fail with a clear message.
- Saved ids may not shadow built-ins; a name collision with a built-in is rejected.
- A missing or unreadable `format.json` raises a specific `FormatError` and the damaged file is preserved, never silently replaced.
- Saving is atomic (staging directory, then rename) and happens only when the user asks to remember a format or approves saving it. Do not save a private exam as a reusable template.

Save/load round trips reproduce the same layout tokens: tests cover the token mapping, corrupt-file preservation, and the built-in protection.

## Local settings.json

`<skill root>/settings.json` (git-ignored) stores the remembered hard-dependency preference and the last format id:

```json
{"settings_version": 1, "allow_hard_dependencies": true, "last_format_id": "builtin-card"}
```

Writes are atomic. A corrupt or unsupported-version file is reported (naming the file and defect) and never overwritten; missing settings mean ask, not default. The bank JSON records the effective choice so a finished bank stays reproducible after the preference changes.
