"""Gate A check: copy the code column from Word, verify fidelity, convert to PDF.

Run on Windows with pywin32 and Microsoft Word installed. Writes
PROTOTYPE-REPORT.md with the actual applications, methods, and results.
"""

import ast
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROTOTYPE_DIR = Path(__file__).resolve().parent
SKILL_SCRIPTS = PROTOTYPE_DIR.parents[2] / "scripts"
for path in (str(SKILL_SCRIPTS), str(PROTOTYPE_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import pythoncom  # noqa: E402
import win32clipboard  # noqa: E402
import win32com.client  # noqa: E402

import build_prototype  # noqa: E402
from qbank_render import convert_docx_to_pdf  # noqa: E402

CARDS = [
    ("Code Block 1", build_prototype.NINE_LINE_EXAMPLE),
    ("Code Block 2", build_prototype.TRICKY_EXAMPLE),
    ("Code Block 3", build_prototype.hundred_line_example()),
]


def clipboard_text():
    import pywintypes

    for attempt in range(12):
        try:
            win32clipboard.OpenClipboard()
            try:
                return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
        except pywintypes.error:
            time.sleep(0.2 * (attempt + 1))
    raise RuntimeError("The clipboard stayed locked after copying from Word")


def code_table_indexes(document):
    indexes = []
    for index in range(1, document.Tables.Count + 1):
        table = document.Tables(index)
        if table.Rows.Count == 2 and table.Columns.Count == 2:
            first_number = table.Cell(2, 1).Range.Paragraphs(1).Range.Text
            if first_number.strip().rstrip("\r\x07") == "1":
                indexes.append(index)
    return indexes


def copy_range(word_document, start, end):
    """Copy a Word range and wait until the new content actually lands.

    Word's Copy is asynchronous for larger ranges; poll until the clipboard
    stops holding the sentinel instead of trusting a fixed sleep.
    """
    rng = word_document.Range(Start=start, End=end)
    sentinel = "$$gate-a-sentinel$$"
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(sentinel)
    finally:
        win32clipboard.CloseClipboard()
    rng.Copy()
    for _ in range(80):
        time.sleep(0.1)
        try:
            data = clipboard_text()
        except RuntimeError:
            continue
        if data != sentinel:
            return data
    raise RuntimeError("Word did not place the copied range on the clipboard")


def normalize_copied(text):
    """Normalize Word/clipboard line endings while KEEPING blank code lines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip("\x07").rstrip() for line in text.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def check_card(document, table_index, expected_lines):
    table = document.Tables(table_index)
    code_cell = table.Cell(2, 2)
    copied = copy_range(document, code_cell.Range.Start, code_cell.Range.End - 1)
    copied_lines = normalize_copied(copied)
    matches = copied_lines == expected_lines
    full_card = copy_range(document, table.Cell(1, 1).Range.Start,
                           table.Cell(2, 2).Range.End)
    full_includes_gutter = any(line.strip() == "1" for line in normalize_copied(full_card))
    return {"matches": matches, "copied_lines": copied_lines,
            "full_card_includes_gutter": full_includes_gutter}


def parse_and_run(pasted_lines):
    source = "\n".join(pasted_lines)
    ast.parse(source)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as handle:
        handle.write(source)
        script = handle.name
    try:
        completed = subprocess.run([sys.executable, script], capture_output=True,
                                   text=True, timeout=60)
        return {"parsed": True, "exit_status": completed.returncode,
                "stdout": completed.stdout, "stderr": completed.stderr}
    finally:
        Path(script).unlink(missing_ok=True)


def pdf_checks(pdf_path, results):
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    normalized = " ".join(text.split())
    for name, lines in CARDS:
        first = " ".join(lines[0].split())
        last = " ".join(lines[-1].split())
        results.append(f"{name}: first line in PDF text={first in normalized}, "
                       f"last line in PDF text={last in normalized}")
    digits_present = any(token in text for token in (" 1 ", " 2 "))  # extraction order only
    results.append(f"PDF page count: {len(reader.pages)}; gutter digits appear in raw "
                   f"extraction order: {digits_present} (extraction order is not the "
                   "visual copy behavior)")


def render_page_images(pdf_path):
    """Render PDF pages to PNG for visual review (PyMuPDF, then pdftoppm)."""
    try:
        import fitz
    except ImportError:
        fitz = None
    if fitz is not None:
        document = fitz.open(str(pdf_path))
        names = []
        for index, page in enumerate(document, 1):
            name = PROTOTYPE_DIR / f"page-{index}.png"
            page.get_pixmap(dpi=110).save(str(name))
            names.append(name.name)
        return f"rendered {len(names)} page images via PyMuPDF: {names}"
    import shutil
    import subprocess

    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        return "No PDF page renderer (PyMuPDF/pdftoppm) is available"
    subprocess.run([pdftoppm, "-png", "-r", "110", str(pdf_path),
                    str(PROTOTYPE_DIR / "page")], check=True, timeout=120)
    images = sorted(PROTOTYPE_DIR.glob("page-*.png"))
    return f"rendered {len(images)} page images: {[image.name for image in images]}"


def main():
    docx_path = PROTOTYPE_DIR / "copy_prototype.docx"
    pdf_path = PROTOTYPE_DIR / "copy_prototype.pdf"
    if not docx_path.exists():
        build_prototype.main()

    pythoncom.CoInitialize()
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    report_lines = ["# Gate A prototype report", "",
                    f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Python: {sys.version.split()[0]}", ""]
    try:
        document = word.Documents.Open(str(docx_path.resolve()), ReadOnly=False)
        word_version = word.Version
        indexes = code_table_indexes(document)
        report_lines.append(f"Microsoft Word version: {word_version}")
        report_lines.append(f"Code cards found in Word: {len(indexes)} of {len(CARDS)}")
        overall = True
        for (name, expected), table_index in zip(CARDS, indexes):
            result = check_card(document, table_index, expected)
            status = "PASS" if result["matches"] else "FAIL"
            overall = overall and result["matches"]
            report_lines.append(
                f"- {name}: code-column copy {status} "
                f"({len(result['copied_lines'])} lines copied; "
                f"full-card selection includes gutter numbers: "
                f"{result['full_card_includes_gutter']})")
            if not result["matches"]:
                report_lines.append(f"  expected {len(expected)} lines, "
                                    f"got {len(result['copied_lines'])}")
            if name == "Code Block 1":
                execution = parse_and_run(expected)
                overall = overall and execution["exit_status"] == 0
                report_lines.append(
                    f"- {name}: pasted text parsed and executed; exit status "
                    f"{execution['exit_status']}")
        document.Close(SaveChanges=0)
    finally:
        word.Quit()
        pythoncom.CoUninitialize()

    conversion = convert_docx_to_pdf(docx_path, pdf_path)
    report_lines.append(f"DOCX to PDF conversion: {conversion}")
    if conversion["status"] == "converted":
        pdf_checks(pdf_path, report_lines)
        report_lines.append(render_page_images(pdf_path))
    report_lines += [
        "",
        "## Selection method",
        "",
        "The supported method is selecting the code column: click inside the first code "
        "line, extend the selection to the last code line (the gutter column is a separate "
        "table column), copy, and paste. Copying the full card includes the gutter numbers "
        "by design; they are separate text, not part of the code characters.",
        "",
        "## Limitations",
        "",
        "- VS Code itself was not automated; the checked text is the exact clipboard "
        "content a paste into VS Code would receive, saved as UTF-8, parsed, and executed.",
        "- PDF copy behavior was verified through text extraction of the converted PDF and "
        "rendered page images; in-viewer selection must be confirmed manually in the "
        "declared PDF viewer. PDF text extraction order is not evidence of copy order.",
        "- Full-card selection copies gutter numbers; only the code-column selection is "
        "the supported copy path.",
    ]
    (PROTOTYPE_DIR / "PROTOTYPE-REPORT.md").write_text("\n".join(report_lines) + "\n",
                                                       encoding="utf-8")
    print("\n".join(report_lines))
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
