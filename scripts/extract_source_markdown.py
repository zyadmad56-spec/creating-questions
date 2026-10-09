"""Extract study material without rendering pages or uploading images."""

import argparse
import json
from pathlib import Path


def markdown_table(rows):
    if not rows:
        return ""
    cells = [[str(value).replace("|", "\\|").replace("\n", "<br>") for value in row] for row in rows]
    lines = ["| " + " | ".join(cells[0]) + " |",
             "| " + " | ".join("---" for _ in cells[0]) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in cells[1:])
    return "\n".join(lines)


def extract_pdf(path):
    from pypdf import PdfReader

    reader = PdfReader(path)
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("The PDF is encrypted. Provide an accessible copy.")
    parts, review = [], []
    for number, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        parts.append(f"## PDF page {number}\n\n" + (text or "[No extractable text on this page.]"))
        if len(text.split()) < 15:
            review.append({"pdf_page": number, "reason": "Little or no extracted text; check relevance before OCR or a targeted page view."})
    return parts, review, len(reader.pages)


def extract_slide_shapes(shapes):
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    parts, review = [], []
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            nested, notices = extract_slide_shapes(shape.shapes)
            parts.extend(nested)
            review.extend(notices)
        elif shape.has_table:
            parts.append(markdown_table([[cell.text for cell in row.cells] for row in shape.table.rows]))
        elif shape.has_text_frame:
            text = "\n".join(p.text for p in shape.text_frame.paragraphs).strip()
            if text:
                parts.append(text)
        elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            review.append(f"Picture present: {shape.name}; its contents were not interpreted.")
        elif getattr(shape, "has_chart", False):
            review.append(f"Chart present: {shape.name}; values need a source check if used.")
    return parts, review


def extract_pptx(path):
    from pptx import Presentation

    deck = Presentation(path)
    parts, review = [], []
    for number, slide in enumerate(deck.slides, 1):
        content, notices = extract_slide_shapes(slide.shapes)
        if slide.has_notes_slide:
            frame = slide.notes_slide.notes_text_frame
            notes = frame.text.strip() if frame is not None else ""
            if notes:
                content.append("### Speaker notes\n\n" + notes)
        if not content:
            content.append("[No extractable text or tables on this slide.]")
            notices.append("No text or tables extracted; check this slide if it belongs to the selected scope.")
        parts.append(f"## Slide {number}\n\n" + "\n\n".join(content))
        if notices:
            review.append({"slide": number, "reasons": notices})
    return parts, review, len(deck.slides)


def extract_docx(path):
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(path)
    parts, review = [], []
    paragraph_number = table_number = 0
    for node in document.element.body:
        if node.tag == qn("w:p"):
            paragraph_number += 1
            paragraph = Paragraph(node, document)
            if paragraph.text.strip():
                parts.append(f"## Paragraph {paragraph_number}\n\n{paragraph.text}")
            if node.findall(".//" + qn("w:drawing")) or node.findall(".//" + qn("w:pict")):
                review.append({"locator": f"Paragraph {paragraph_number}",
                               "reason": "Drawing or image present; inspect only if it contains needed evidence."})
        elif node.tag == qn("w:tbl"):
            table_number += 1
            table = Table(node, document)
            parts.append(f"## Table {table_number}\n\n" + markdown_table([[cell.text for cell in row.cells] for row in table.rows]))
            if node.findall(".//" + qn("w:drawing")) or node.findall(".//" + qn("w:pict")):
                review.append({"locator": f"Table {table_number}", "reason": "Drawing or image present in this table."})
    return parts, review, paragraph_number + table_number


def extract_text(path):
    text = path.read_text(encoding="utf-8-sig")
    return ["## Original document text\n\n" + text], [], len(text.splitlines())


EXTRACTORS = {".pdf": extract_pdf, ".pptx": extract_pptx, ".docx": extract_docx,
              ".md": extract_text, ".txt": extract_text}


def extract_source(source_path, output_path):
    source, output = Path(source_path), Path(output_path)
    if source.resolve() == output.resolve():
        raise ValueError("The extraction must not overwrite its source.")
    if source.suffix.lower() == ".ppt":
        raise ValueError("Legacy .ppt needs conversion to .pptx or PDF using an available presentation tool. The extractor cannot read .ppt directly.")
    extractor = EXTRACTORS.get(source.suffix.lower())
    if extractor is None:
        raise ValueError("Supported extraction inputs: PDF, PPTX, DOCX, Markdown, UTF-8 text.")
    parts, review, units = extractor(source)
    summary = {"document": source.name, "format": source.suffix.lower(), "units": units,
               "review_candidates": review, "images_rendered": 0,
               "note": "Review flags are candidates, not a command to render all flagged units. Text extraction can miss diagrams, equations, or complex layout even on unflagged pages."}
    heading = f"# Extracted source: {source.name}\n\nOriginal page, slide, paragraph, and table identifiers below refer to the uploaded source. For text files, cite original section headings or line numbers.\n\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(heading + "\n\n".join(parts) + "\n", encoding="utf-8")
    report_path = output.with_suffix(".extraction.json")
    if report_path.resolve() == source.resolve():
        raise ValueError("The extraction report must not overwrite its source.")
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**summary, "markdown_path": str(output), "report_path": str(report_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_file")
    parser.add_argument("output_markdown")
    arguments = parser.parse_args()
    try:
        print(json.dumps(extract_source(arguments.source_file, arguments.output_markdown), ensure_ascii=False))
    except (ValueError, OSError, ImportError) as error:
        parser.exit(1, f"Extraction failed: {error}\n")


if __name__ == "__main__":
    main()
