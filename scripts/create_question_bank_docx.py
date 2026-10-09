import argparse
import copy
import json
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = SKILL_DIR / "assets" / "Creating Questions.docx"
DIFFICULTIES = {"easy", "medium", "hard"}
SOURCE_MODES = {"source_only", "source_web_general", "pdf_only", "pdf_web_general"}
SECTION_INSTRUCTIONS = {
    "mcqs": "Choose one answer for each question.",
    "true_false": "Mark each statement True or False.",
    "essays": "Answer every part of each prompt in your own words."
}
SECTION_TITLES = {
    "en": {"mcqs": "Multiple Choice Questions", "true_false": "True or False Questions",
           "essays": "Essay Questions", "headers": ["No.", "Answer", "Explanation or correction", "Source"]}
}


def required_text(record, field):
    content = record.get(field)
    if not isinstance(content, str) or not content.strip():
        raise ValueError(f"{field} must be nonempty text")
    return content.strip()


def normalized_text(text):
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(normalized.split()).rstrip(".?!\u061f")


def validate_pdf_source(source):
    required_text(source, "document")
    page = source.get("pdf_page")
    if type(page) is not int or page < 1:
        raise ValueError("pdf_page must be a positive 1-based integer")


def validate_slides_source(source):
    required_text(source, "document")
    slide = source.get("slide")
    if type(slide) is not int or slide < 1:
        raise ValueError("slide must be a positive 1-based integer")


def validate_document_source(source):
    required_text(source, "document")
    required_text(source, "locator")
    if "page" in source and (type(source["page"]) is not int or source["page"] < 1):
        raise ValueError("page must be a positive 1-based integer when supplied")


def validate_web_source(source):
    required_text(source, "title")
    address = urlparse(required_text(source, "url"))
    if address.scheme not in {"http", "https"} or not address.netloc:
        raise ValueError("Web source must have a direct HTTP(S) URL")


def validate_general_source(source):
    required_text(source, "verified_against")


SOURCE_VALIDATORS = {"pdf": validate_pdf_source, "pdf_inference": validate_pdf_source,
                     "slides": validate_slides_source, "slides_inference": validate_slides_source,
                     "document": validate_document_source, "document_inference": validate_document_source,
                     "web": validate_web_source, "general": validate_general_source}


def validate_sources(question, source_mode):
    sources = question.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Each question needs nonempty sources")
    for source in sources:
        kind = source.get("kind")
        if kind not in SOURCE_VALIDATORS:
            raise ValueError(f"Unknown source kind: {kind}")
        if source_mode == "pdf_only" and kind not in {"pdf", "pdf_inference"}:
            raise ValueError("External sources are forbidden in pdf_only mode")
        if source_mode == "source_only" and kind in {"web", "general"}:
            raise ValueError("External sources are forbidden in source_only mode")
        required_text(source, "evidence")
        SOURCE_VALIDATORS[kind](source)


def validate_mcq(question):
    options = question.get("options")
    if not isinstance(options, list) or len(options) != 4:
        raise ValueError("MCQ needs exactly four options")
    if any(not isinstance(option, str) or not option.strip() for option in options):
        raise ValueError("MCQ options must be nonempty text")
    if len({normalized_text(option) for option in options}) != 4:
        raise ValueError("MCQ options must be distinct")
    if question.get("correct") not in {"A", "B", "C", "D"}:
        raise ValueError("MCQ correct must be A, B, C, or D")


def validate_true_false(question):
    if question.get("correct") not in {"True", "False"}:
        raise ValueError("True/False correct must be True or False")
    if question["correct"] == "False":
        required_text(question, "correction")


def validate_essay(question):
    points = question.get("model_answer")
    if not isinstance(points, list) or not points:
        raise ValueError("Essay needs a nonempty list of model-answer points")
    if any(not isinstance(point, str) or not point.strip() for point in points):
        raise ValueError("Essay answer points must be nonempty text")


QUESTION_VALIDATORS = {"mcqs": validate_mcq, "true_false": validate_true_false,
                       "essays": validate_essay}


def validate_counts(bank, section):
    questions = bank.get(section, [])
    expected = bank["counts"].get(section)
    quotas = bank["difficulty_counts"].get(section, {})
    if type(expected) is not int or expected < 0 or expected != len(questions):
        raise ValueError(f"Question count mismatch for {section}")
    if set(quotas) != DIFFICULTIES:
        raise ValueError(f"All three difficulty counts are required for {section}")
    if any(type(count) is not int or count < 0 for count in quotas.values()):
        raise ValueError("Difficulty counts must be nonnegative integers")
    if sum(quotas.values()) != expected:
        raise ValueError(f"Difficulty totals do not match {section}")
    observed = Counter(question.get("difficulty") for question in questions)
    if any(observed[difficulty] != quotas[difficulty] for difficulty in DIFFICULTIES):
        raise ValueError(f"Actual difficulty distribution does not match {section}")


def validate_question(question, section, source_mode):
    stem_field = "statement" if section == "true_false" else "question"
    required_text(question, stem_field)
    required_text(question, "explanation")
    if question.get("difficulty") not in DIFFICULTIES:
        raise ValueError("Invalid question difficulty")
    if question.get("answer_verified") is not True:
        raise ValueError("Complete the source-based answer audit before exporting")
    validate_sources(question, source_mode)
    QUESTION_VALIDATORS[section](question)


def validate_sections(bank):
    seen_stems = set()
    for section in QUESTION_VALIDATORS:
        validate_counts(bank, section)
        for question in bank.get(section, []):
            validate_question(question, section, bank["source_mode"])
            stem = normalized_text(question.get("question", question.get("statement", "")))
            if stem in seen_stems:
                raise ValueError(f"Repeated question: {stem}")
            seen_stems.add(stem)


def validate_bank(bank):
    required_text(bank, "title")
    if bank.get("source_mode") not in SOURCE_MODES:
        raise ValueError("Explicit source_mode is required")
    for field in ("counts", "difficulty_counts"):
        if not isinstance(bank.get(field), dict) or set(bank[field]) != set(QUESTION_VALIDATORS):
            raise ValueError(f"{field} must contain mcqs, true_false, and essays")
    if bank.get("language", "en") not in SECTION_TITLES:
        raise ValueError("language must be en; this skill produces English output")
    if type(bank.get("include_answer_key", True)) is not bool:
        raise ValueError("include_answer_key must be a boolean")
    validate_sections(bank)
    if sum(bank["counts"].values()) < 1:
        raise ValueError("A question bank must contain at least one question")


def shuffled_sections(bank):
    sections = copy.deepcopy({section: bank.get(section, []) for section in QUESTION_VALIDATORS})
    rng = random.SystemRandom()
    for section, questions in sections.items():
        rng.shuffle(questions)
        if section == "mcqs":
            for question in questions:
                correct_text = question["options"]["ABCD".index(question["correct"])]
                rng.shuffle(question["options"])
                question["correct"] = "ABCD"[question["options"].index(correct_text)]
    return sections


def clear_body(document):
    for child in list(document._body._element):
        if child.tag != qn("w:sectPr"):
            document._body._element.remove(child)


def set_text_direction(paragraph):
    if re.search(r"[\u0600-\u06ff]", paragraph.text):
        paragraph._p.get_or_add_pPr().append(OxmlElement("w:bidi"))


def add_question(document, number, stem):
    paragraph = document.add_paragraph(style="List Number")
    # Explicit numbering keeps section headings and answer rows in agreement.
    num_properties = paragraph._p.get_or_add_pPr().get_or_add_numPr()
    num_properties.get_or_add_numId().val = 0
    paragraph.add_run(f"{number}. {stem.strip()}").bold = True
    paragraph.paragraph_format.keep_with_next = True
    set_text_direction(paragraph)


def add_mcq_body(document, question):
    for letter, option in zip("ABCD", question["options"]):
        paragraph = document.add_paragraph(f"{letter}) {option.strip()}", style="List Bullet 2")
        paragraph._p.get_or_add_pPr().get_or_add_numPr().get_or_add_numId().val = 0
        paragraph.paragraph_format.keep_with_next = letter != "D"
        set_text_direction(paragraph)


def add_true_false_body(document, question):
    document.add_paragraph("True / False")


def add_essay_body(document, question):
    document.add_paragraph("................................................................................")


QUESTION_RENDERERS = {"mcqs": add_mcq_body, "true_false": add_true_false_body,
                      "essays": add_essay_body}


def question_answer(question, section):
    if section == "mcqs":
        letter = question["correct"]
        return f"{letter}) {question['options']['ABCD'.index(letter)].strip()}"
    if section == "true_false":
        return question["correct"]
    return "\n".join(f"• {point.strip()}" for point in question["model_answer"])


def source_key(source):
    return source["document"], source["kind"].removesuffix("_inference")


def source_registry(sections):
    registry = {}
    for questions in sections.values():
        for question in questions:
            for source in question["sources"]:
                if source["kind"] not in {"web", "general"}:
                    key = source_key(source)
                    if key not in registry:
                        registry[key] = f"S{len(registry) + 1}"
    return registry


def source_label(source, registry=None, source_mode="pdf_only"):
    kind = source["kind"]
    if kind not in {"web", "general"}:
        identifier = registry[source_key(source)] if registry else source["document"]
        base_kind = kind.removesuffix("_inference")
        label = f"{identifier}: "
        if base_kind == "pdf":
            label += f"PDF page {source['pdf_page']}"
        elif base_kind == "slides":
            label += f"slide {source['slide']}"
        else:
            if source.get("page"):
                label += f"page {source['page']}, "
            label += source["locator"]
        if source.get("printed_page"):
            label += f", printed page {source['printed_page']}"
        if base_kind != "document" and source.get("locator"):
            label += f", {source['locator']}"
        if kind.endswith("_inference"):
            origin = {"pdf": "PDF", "slides": "slides", "document": "source"}[base_kind]
            label += f"\nInference from {origin}"
        return label
    outside = "Outside PDF" if source_mode.startswith("pdf_") else "Outside uploaded material"
    if kind == "web":
        return f"{outside}: Web: {source['title']}\n{source['url']}"
    return f"{outside}: General knowledge from model; checked against {source['verified_against']}"


def answer_row(question, section, number, registry=None, source_mode="pdf_only"):
    explanation = question["explanation"].strip()
    if section == "true_false" and question["correct"] == "False":
        explanation = "Correction: " + question["correction"].strip()
    labels = list(dict.fromkeys(source_label(source, registry, source_mode) for source in question["sources"]))
    return [str(number), question_answer(question, section), explanation,
            "\n".join(labels)]


def add_question_sections(document, sections, language, registry=None, source_mode="pdf_only"):
    answers = []
    for section, questions in sections.items():
        if not questions:
            continue
        heading = document.add_paragraph(SECTION_TITLES[language][section], style="Heading 1")
        if answers:
            heading.paragraph_format.page_break_before = True
        set_text_direction(heading)
        instruction = document.add_paragraph(SECTION_INSTRUCTIONS[section])
        instruction.paragraph_format.keep_with_next = True
        for question in questions:
            number = len(answers) + 1
            stem = question.get("question", question.get("statement"))
            add_question(document, number, stem)
            QUESTION_RENDERERS[section](document, question)
            answers.append(answer_row(question, section, number, registry, source_mode))
    return answers


def fill_answer_cells(cells, content):
    for cell, text in zip(cells, content):
        cell.text = text
        for paragraph in cell.paragraphs:
            set_text_direction(paragraph)
            paragraph.paragraph_format.space_after = Pt(3)
            for run in paragraph.runs:
                run.font.size = Pt(10)


def add_answer_key(document, answers, language, registry=None):
    document.add_page_break()
    document.add_paragraph("Model Answer", style="Heading 1")
    if registry:
        document.add_paragraph("Source references below identify the uploaded files. PDF pages and slides use 1-based numbering. Inference labels identify applications or deductions from the cited material.")
        for (name, _), identifier in registry.items():
            document.add_paragraph(f"{identifier}: {name}")
    table = document.add_table(rows=1, cols=4)
    table.style = "Light Grid Accent 1"
    table.autofit = False
    for column, width in zip(table.columns, (0.45, 1.65, 1.8, 2.1)):
        column.width = Inches(width)
    header = table.rows[0]
    for cell, column in zip(header.cells, table.columns):
        cell.width = column.width
    header._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    fill_answer_cells(header.cells, SECTION_TITLES[language]["headers"])
    for cell in header.cells:
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True
    for answer in answers:
        fill_answer_cells(table.add_row().cells, answer)


def build_docx(bank, output_path, template_path=DEFAULT_TEMPLATE):
    validate_bank(bank)
    document = Document(str(template_path))
    clear_body(document)
    title = document.add_paragraph(bank["title"].strip(), style="Title")
    set_text_direction(title)
    language = bank.get("language", "en")
    document.add_paragraph(f"{sum(bank['counts'].values())} questions: {bank['counts']['mcqs']} multiple choice, {bank['counts']['true_false']} True/False, and {bank['counts']['essays']} essay.")
    sections = shuffled_sections(bank)
    registry = source_registry(sections)
    answers = add_question_sections(document, sections, language, registry, bank["source_mode"])
    if bank.get("include_answer_key", True):
        add_answer_key(document, answers, language, registry)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))


def main():
    parser = argparse.ArgumentParser(description="Export an audited document or slide question bank as DOCX.")
    parser.add_argument("input_json")
    parser.add_argument("output_docx")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    arguments = parser.parse_args()
    with open(arguments.input_json, encoding="utf-8") as question_file:
        bank = json.load(question_file)
    build_docx(bank, arguments.output_docx, Path(arguments.template))


if __name__ == "__main__":
    main()
