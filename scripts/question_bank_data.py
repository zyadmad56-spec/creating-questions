"""Shared, dependency-free validation and citation formatting for exam banks."""

import unicodedata
from collections import Counter
from urllib.parse import urlparse

DIFFICULTIES = {"easy", "medium", "hard"}
SOURCE_MODES = {"source_only", "source_web_general", "pdf_only", "pdf_web_general"}


def required_text(record, field):
    if not isinstance(record, dict):
        raise ValueError("Records must be JSON objects")
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
        if not isinstance(source, dict):
            raise ValueError("Sources must be JSON objects")
        kind = source.get("kind")
        if not isinstance(kind, str) or kind not in SOURCE_VALIDATORS:
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
    if not isinstance(question.get("correct"), str) or question["correct"] not in {"A", "B", "C", "D"}:
        raise ValueError("MCQ correct must be A, B, C, or D")


def validate_true_false(question):
    if not isinstance(question.get("correct"), str) or question["correct"] not in {"True", "False"}:
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
    if not isinstance(questions, list) or any(not isinstance(q, dict) for q in questions):
        raise ValueError(f"{section} must be a list of question objects")
    expected = bank["counts"].get(section)
    quotas = bank["difficulty_counts"].get(section, {})
    if type(expected) is not int or expected < 0 or expected != len(questions):
        raise ValueError(f"Question count mismatch for {section}")
    if not isinstance(quotas, dict) or set(quotas) != DIFFICULTIES:
        raise ValueError(f"All three difficulty counts are required for {section}")
    if any(type(count) is not int or count < 0 for count in quotas.values()):
        raise ValueError("Difficulty counts must be nonnegative integers")
    if sum(quotas.values()) != expected:
        raise ValueError(f"Difficulty totals do not match {section}")
    if any(not isinstance(question.get("difficulty"), str) for question in questions):
        raise ValueError("Question difficulty must be text")
    observed = Counter(question.get("difficulty") for question in questions)
    if any(observed[difficulty] != quotas[difficulty] for difficulty in DIFFICULTIES):
        raise ValueError(f"Actual difficulty distribution does not match {section}")


def validate_question(question, section, source_mode):
    stem_field = "statement" if section == "true_false" else "question"
    required_text(question, stem_field)
    required_text(question, "explanation")
    if not isinstance(question.get("difficulty"), str) or question["difficulty"] not in DIFFICULTIES:
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
    if not isinstance(bank.get("source_mode"), str) or bank["source_mode"] not in SOURCE_MODES:
        raise ValueError("Explicit source_mode is required")
    for field in ("counts", "difficulty_counts"):
        if not isinstance(bank.get(field), dict) or set(bank[field]) != set(QUESTION_VALIDATORS):
            raise ValueError(f"{field} must contain mcqs, true_false, and essays")
    if bank.get("language", "en") != "en":
        raise ValueError("language must be en; this skill produces English output")
    if type(bank.get("include_answer_key", True)) is not bool:
        raise ValueError("include_answer_key must be a boolean")
    validate_sections(bank)
    if sum(bank["counts"].values()) < 1:
        raise ValueError("A question bank must contain at least one question")


def validate_game_bank(bank):
    """Validate the additional offline-game contract, without claiming semantic truth."""
    validate_bank(bank)
    if any(section not in bank for section in QUESTION_VALIDATORS):
        raise ValueError("HTML banks require all three original question arrays, including empty arrays")
    if type(bank.get("game_version")) is not int or bank["game_version"] != 1:
        raise ValueError("HTML banks require game_version: 1")
    targets = bank.get("learning_targets")
    if not isinstance(targets, dict) or not targets:
        raise ValueError("HTML banks require nonempty learning_targets")
    identities, ids, stems, used = set(), set(), set(), set()

    def check_item(question, section, target_id):
        validate_question(question, section, bank["source_mode"])
        qid = required_text(question, "id")
        if qid != question["id"] or qid in ids:
            raise ValueError("Question IDs must be unique and have no surrounding whitespace")
        ids.add(qid)
        if question.get("target_id") != target_id:
            raise ValueError("Question target_id must match its learning target")
        target = targets[target_id]
        if section != target["question_type"] or question["difficulty"] != target["difficulty"]:
            raise ValueError("A learning target must have one question type and difficulty")
        stem = normalized_text(question.get("statement") if section == "true_false" else question["question"])
        if stem in stems:
            raise ValueError("Original and retry question stems must be distinct")
        stems.add(stem)
        if section == "mcqs":
            reasons = question.get("option_explanations")
            if not isinstance(reasons, dict) or set(reasons) != set("ABCD"):
                raise ValueError("HTML MCQs require option_explanations for A, B, C, D")
            for letter in "ABCD":
                required_text(reasons, letter)

    for target_id, target in targets.items():
        if not isinstance(target_id, str) or not target_id.strip() or target_id != target_id.strip():
            raise ValueError("Learning target IDs must be nonempty text without surrounding whitespace")
        concept = required_text(target, "concept_id")
        angle = required_text(target, "angle")
        required_text(target, "label")
        section, difficulty = target.get("question_type"), target.get("difficulty")
        if (not isinstance(section, str) or section not in QUESTION_VALIDATORS
                or not isinstance(difficulty, str) or difficulty not in DIFFICULTIES):
            raise ValueError("Invalid learning target question_type or difficulty")
        identity = (normalized_text(concept), normalized_text(angle), section, difficulty)
        if identity in identities:
            raise ValueError("Matching learning targets must share one retry pool")
        identities.add(identity)
        retries = target.get("retries")
        if not isinstance(retries, list) or len(retries) != 3:
            raise ValueError("Every learning target requires exactly three retry variants")
        for question in retries:
            check_item(question, section, target_id)

    for section in QUESTION_VALIDATORS:
        for question in bank.get(section, []):
            target_id = question.get("target_id")
            if not isinstance(target_id, str) or target_id not in targets:
                raise ValueError("Original question references an unknown learning target")
            used.add(target_id)
            check_item(question, section, target_id)
    if used != set(targets):
        raise ValueError("Every learning target must be used by an original question")


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
