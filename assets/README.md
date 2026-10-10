# Output assets

## Word template

`Creating Questions.docx` is a blank template. It preserves the page size, margins, heading styles, list styles, and answer-table style used by the formatter.

The formatter replaces the template body with the audited questions and Model Answer table. The template contains no lecture content or student question bank.

To change the document's appearance, edit the template's styles and page setup, then run the formatter tests before generating a bank.

## Browser interface

`exam-game/` contains the local game's HTML, CSS, and JavaScript, served by the Python runner. Course questions come from the authored exam JSON. No external assets or build step are required.

The interface defaults to white and blue, with a header button for dark navy and blue. Theme colors are CSS variables in `style.css`; `app.js` stores the browser preference under `exam-night-theme`. Theme changes do not call the game API. The countdown clock and paused question review work in both themes.
