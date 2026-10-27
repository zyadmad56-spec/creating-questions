"""Schema version 2: normalize legacy and programming banks into one model.

An absent ``schema_version`` means the existing flat shape and is adapted, never
rejected or rewritten. Version 2 adds stable IDs, code blocks, groups,
dependencies, execution records, and reference tokens. Unsupported explicit
versions fail with a clear message before any output is written.
"""

import copy
import hashlib
import json
import re
import unicodedata
from collections import Counter
from urllib.parse import urlparse

SCHEMA_VERSION = 2
QUESTION_TYPES = ("mcqs", "true_false", "essays")
DIFFICULTIES = ("easy", "medium", "hard")
SOURCE_MODES = {"source_only", "source_web_general", "pdf_only", "pdf_web_general"}
EXECUTION_STATUSES = {"passed", "failed", "unavailable", "not_applicable", "not_run"}
ESSAY_STYLES = {"scenario", "completion", "bug_fix", "trace_explain"}
CODE_ORIGINS = {"extracted_from_source", "authored_from_source", "repaired_from_source"}
REVIEW_STATUSES = {"recovered", "needs_review", "intentionally_incomplete",
                   "intentionally_invalid", "unreadable"}
DEPENDENCY_MODES = {"independent", "linked", "linked_allowed"}
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
TOKEN_PATTERN = re.compile(r"\{\{(?:q|block|line):[A-Za-z0-9_:-]+\}\}")


class SchemaError(ValueError):
    """Raised for any invalid bank structure; the bank is left untouched."""


# ---------------------------------------------------------------------------
# Shared primitive validation (also used by the legacy formatter)
# ---------------------------------------------------------------------------

def required_text(record, field):
    content = record.get(field)
    if not isinstance(content, str) or not content.strip():
        raise SchemaError(f"{field} must be nonempty text")
    return content.strip()


def normalized_text(text):
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(normalized.split()).rstrip(".?!\u061f")


def validate_pdf_source(source):
    required_text(source, "document")
    page = source.get("pdf_page")
    if type(page) is not int or page < 1:
        raise SchemaError("pdf_page must be a positive 1-based integer")


def validate_slides_source(source):
    required_text(source, "document")
    slide = source.get("slide")
    if type(slide) is not int or slide < 1:
        raise SchemaError("slide must be a positive 1-based integer")


def validate_document_source(source):
    required_text(source, "document")
    required_text(source, "locator")
    if "page" in source and (type(source["page"]) is not int or source["page"] < 1):
        raise SchemaError("page must be a positive 1-based integer when supplied")


def validate_web_source(source):
    required_text(source, "title")
    address = urlparse(required_text(source, "url"))
    if address.scheme not in {"http", "https"} or not address.netloc:
        raise SchemaError("Web source must have a direct HTTP(S) URL")


def validate_general_source(source):
    required_text(source, "verified_against")


SOURCE_VALIDATORS = {"pdf": validate_pdf_source, "pdf_inference": validate_pdf_source,
                     "slides": validate_slides_source, "slides_inference": validate_slides_source,
                     "document": validate_document_source, "document_inference": validate_document_source,
                     "web": validate_web_source, "general": validate_general_source}


def validate_source_list(sources, source_mode):
    if not isinstance(sources, list) or not sources:
        raise SchemaError("Each question needs nonempty sources")
    for source in sources:
        kind = source.get("kind")
        if kind not in SOURCE_VALIDATORS:
            raise SchemaError(f"Unknown source kind: {kind}")
        if source_mode == "pdf_only" and kind not in {"pdf", "pdf_inference"}:
            raise SchemaError("External sources are forbidden in pdf_only mode")
        if source_mode == "source_only" and kind in {"web", "general"}:
            raise SchemaError("External sources are forbidden in source_only mode")
        required_text(source, "evidence")
        SOURCE_VALIDATORS[kind](source)


def code_hash(code_text):
    return hashlib.sha256(code_text.encode("utf-8")).hexdigest()


def effective_program(model, base_block_id, variant=None):
    """Exact effective code for a question: baseline lines plus variant operations.

    Operations reference stable line IDs (append, replace, insert_after,
    delete). Returns (code_text, line_id_to_number map for the effective text).
    """
    block = model["code_blocks"][base_block_id]
    lines = list(block["lines"])
    if variant:
        if variant.get("base_block_id") and variant["base_block_id"] != base_block_id:
            raise SchemaError(f"Variant base block {variant['base_block_id']} does not "
                              f"match {base_block_id}")
        for operation in variant.get("operations") or []:
            op = operation.get("op")
            line_id = operation.get("line_id")
            position = next((index for index, line in enumerate(lines)
                             if line["id"] == line_id), None)
            if op in ("replace", "delete", "insert_after") and position is None:
                raise SchemaError(f"Unknown line id {line_id!r} for {op} in block {base_block_id}")
            if op == "append":
                lines.append({"id": f"_{len(lines) + 1}", "text": operation.get("text", "")})
            elif op == "replace":
                lines[position] = {"id": line_id, "text": operation.get("text", "")}
            elif op == "delete":
                del lines[position]
            elif op == "insert_after":
                lines.insert(position + 1,
                             {"id": f"_{position + 2}", "text": operation.get("text", "")})
    text = "\n".join(line["text"] for line in lines)
    numbers = {line["id"]: index for index, line in enumerate(lines, 1)}
    return text, numbers


# ---------------------------------------------------------------------------
# Legacy (versionless) validation and adapter
# ---------------------------------------------------------------------------

def validate_legacy_mcq(question):
    options = question.get("options")
    if not isinstance(options, list) or len(options) != 4:
        raise SchemaError("MCQ needs exactly four options")
    if any(not isinstance(option, str) or not option.strip() for option in options):
        raise SchemaError("MCQ options must be nonempty text")
    if len({normalized_text(option) for option in options}) != 4:
        raise SchemaError("MCQ options must be distinct")
    if question.get("correct") not in {"A", "B", "C", "D"}:
        raise SchemaError("MCQ correct must be A, B, C, or D")


def validate_legacy_true_false(question):
    if question.get("correct") not in {"True", "False"}:
        raise SchemaError("True/False correct must be True or False")
    if question["correct"] == "False":
        required_text(question, "correction")


def validate_legacy_essay(question):
    points = question.get("model_answer")
    if not isinstance(points, list) or not points:
        raise SchemaError("Essay needs a nonempty list of model-answer points")
    if any(not isinstance(point, str) or not point.strip() for point in points):
        raise SchemaError("Essay answer points must be nonempty text")


LEGACY_QUESTION_VALIDATORS = {"mcqs": validate_legacy_mcq, "true_false": validate_legacy_true_false,
                              "essays": validate_legacy_essay}


def validate_legacy_question(question, section, source_mode):
    stem_field = "statement" if section == "true_false" else "question"
    required_text(question, stem_field)
    required_text(question, "explanation")
    if question.get("difficulty") not in DIFFICULTIES:
        raise SchemaError("Invalid question difficulty")
    if question.get("answer_verified") is not True:
        raise SchemaError("Complete the source-based answer audit before exporting")
    validate_source_list(question.get("sources"), source_mode)
    LEGACY_QUESTION_VALIDATORS[section](question)


def validate_legacy_bank(bank):
    """Validate the original flat bank shape (kept for the compatible CLI)."""
    required_text(bank, "title")
    if bank.get("source_mode") not in SOURCE_MODES:
        raise SchemaError("Explicit source_mode is required")
    for field in ("counts", "difficulty_counts"):
        if not isinstance(bank.get(field), dict) or set(bank[field]) != set(QUESTION_TYPES):
            raise SchemaError(f"{field} must contain mcqs, true_false, and essays")
    if bank.get("language", "en") != "en":
        raise SchemaError("language must be en; this skill produces English output")
    if type(bank.get("include_answer_key", True)) is not bool:
        raise SchemaError("include_answer_key must be a boolean")
    seen_stems = set()
    for section in QUESTION_TYPES:
        validate_legacy_counts(bank, section)
        for question in bank.get(section, []):
            validate_legacy_question(question, section, bank["source_mode"])
            stem = normalized_text(question.get("question", question.get("statement", "")))
            if stem in seen_stems:
                raise SchemaError(f"Repeated question: {stem}")
            seen_stems.add(stem)
    if sum(bank["counts"].values()) < 1:
        raise SchemaError("A question bank must contain at least one question")


def validate_legacy_counts(bank, section):
    questions = bank.get(section, [])
    expected = bank["counts"].get(section)
    quotas = bank["difficulty_counts"].get(section, {})
    if type(expected) is not int or expected < 0 or expected != len(questions):
        raise SchemaError(f"Question count mismatch for {section}")
    if set(quotas) != set(DIFFICULTIES):
        raise SchemaError(f"All three difficulty counts are required for {section}")
    if any(type(count) is not int or count < 0 for count in quotas.values()):
        raise SchemaError("Difficulty counts must be nonnegative integers")
    if sum(quotas.values()) != expected:
        raise SchemaError(f"Difficulty totals do not match {section}")
    observed = Counter(question.get("difficulty") for question in questions)
    if any(observed[difficulty] != quotas[difficulty] for difficulty in DIFFICULTIES):
        raise SchemaError(f"Actual difficulty distribution does not match {section}")


def adapt_legacy_bank(bank):
    """Assign stable IDs and singleton render context to the existing shape.

    The input bank is deep-copied; the caller's JSON is never rewritten.
    """
    model = copy.deepcopy(bank)
    model["schema_version"] = 1
    model.setdefault("language", "en")
    model.setdefault("include_answer_key", True)
    model["code_blocks"] = {}
    model["groups"] = {}
    model["questions"] = {}
    model["sections"] = {}
    counters = {question_type: 0 for question_type in QUESTION_TYPES}
    for question_type in QUESTION_TYPES:
        model["sections"][question_type] = []
        for question in model.get(question_type, []):
            counters[question_type] += 1
            question_id = f"q_{question_type.rstrip('s')}_{counters[question_type]:03d}"
            question["id"] = question_id
            question["section"] = question_type
            question["depends_on"] = []
            question["code_block_id"] = None
            question["variant"] = None
            question["execution"] = {"status": "not_run", "execution_verified": False,
                                     "reason": "Legacy bank: execution records do not apply.",
                                     "cases": []}
            model["questions"][question_id] = question
            model["sections"][question_type].append(question_id)
    return model


# ---------------------------------------------------------------------------
# Version 2 normalization
# ---------------------------------------------------------------------------

def check_id(value, namespace):
    if not isinstance(value, str) or not ID_PATTERN.match(value):
        raise SchemaError(f"{namespace} id {value!r} must match {ID_PATTERN.pattern}")
    return value


def normalize_code_block(block, source_mode):
    block_id = check_id(block.get("id"), "code block")
    language = required_text(block, "language")
    lines = block.get("lines")
    if not isinstance(lines, list) or not lines:
        raise SchemaError(f"Code block {block_id} needs a nonempty lines list")
    line_ids = set()
    normalized_lines = []
    for line in lines:
        line_id = check_id(line.get("id"), "code line")
        if line_id in line_ids:
            raise SchemaError(f"Duplicate line id {line_id} in code block {block_id}")
        line_ids.add(line_id)
        text = line.get("text")
        if not isinstance(text, str):
            raise SchemaError(f"Line {line_id} in block {block_id} must be text")
        if TOKEN_PATTERN.search(text):
            raise SchemaError(f"Reference tokens are forbidden inside code line {line_id}")
        normalized_lines.append({"id": line_id, "text": text})
    code_text = "\n".join(line["text"] for line in normalized_lines)
    if block.get("origin") not in CODE_ORIGINS:
        raise SchemaError(f"Code block {block_id} origin must be one of {sorted(CODE_ORIGINS)}")
    if block.get("review_status") not in REVIEW_STATUSES:
        raise SchemaError(f"Code block {block_id} review_status must be one of "
                          f"{sorted(REVIEW_STATUSES)}")
    validate_source_list(block.get("sources"), source_mode)
    return {"id": block_id, "language": language,
            "version_hint": block.get("version_hint"),
            "origin": block["origin"], "review_status": block["review_status"],
            "lines": normalized_lines, "sources": block["sources"],
            "code_hash": code_hash(code_text)}


def normalize_options(question, question_id):
    options = question.get("options")
    if not isinstance(options, list) or len(options) != 4:
        raise SchemaError(f"MCQ {question_id} needs exactly four options")
    seen = set()
    normalized = []
    for option in options:
        if isinstance(option, str):
            option = {"id": None, "text": option}
        option_id = option.get("id") or f"{question_id}_o{len(normalized) + 1}"
        check_id(option_id, "option")
        if option_id in seen:
            raise SchemaError(f"Duplicate option id {option_id} in {question_id}")
        seen.add(option_id)
        text = option.get("text")
        if not isinstance(text, str) or not text.strip():
            raise SchemaError(f"Option {option_id} must be nonempty text")
        normalized.append({"id": option_id, "text": text})
    if len({normalized_text(option["text"]) for option in normalized}) != 4:
        raise SchemaError(f"MCQ {question_id} options must be distinct")
    correct_id = question.get("correct_option_id")
    if correct_id not in seen:
        raise SchemaError(f"Unknown correct_option_id for {question_id}: {correct_id!r}")
    return normalized, correct_id


def normalize_execution(question_id, execution):
    record = execution or {"status": "not_run", "execution_verified": False}
    status = record.get("status")
    if status not in EXECUTION_STATUSES:
        raise SchemaError(f"Execution status for {question_id} must be one of "
                          f"{sorted(EXECUTION_STATUSES)}, got {status!r}")
    if type(record.get("execution_verified")) is not bool:
        raise SchemaError(f"execution_verified for {question_id} must be a boolean")
    if status == "passed" and not record["execution_verified"]:
        raise SchemaError(f"A passed execution record for {question_id} must be verified")
    if status in {"not_run", "unavailable", "not_applicable", "failed"} \
            and record["execution_verified"]:
        raise SchemaError(f"Execution status {status} cannot be execution_verified for {question_id}")
    return record


def normalize_v2_question(question, section, source_mode):
    question_id = check_id(question.get("id"), "question")
    if section == "true_false":
        required_text(question, "statement")
        if question.get("correct") not in {"True", "False"}:
            raise SchemaError(f"True/False correct must be True or False for {question_id}")
        if question["correct"] == "False":
            required_text(question, "correction")
    else:
        required_text(question, "question")
    required_text(question, "explanation")
    if question.get("difficulty") not in DIFFICULTIES:
        raise SchemaError(f"Invalid difficulty for {question_id}")
    validate_source_list(question.get("sources"), source_mode)
    normalized = copy.deepcopy(question)
    normalized["section"] = section
    normalized["depends_on"] = list(question.get("depends_on") or [])
    if section == "mcqs":
        options, correct_id = normalize_options(question, question_id)
        normalized["options"] = options
        normalized["correct_option_id"] = correct_id
    if section == "essays":
        points = question.get("model_answer")
        if not isinstance(points, list) or not points or any(
                not isinstance(point, str) or not point.strip() for point in points):
            raise SchemaError(f"Essay {question_id} needs nonempty model-answer points")
        style = question.get("essay_style")
        if style is not None and style not in ESSAY_STYLES:
            raise SchemaError(f"Essay {question_id} style must be one of {sorted(ESSAY_STYLES)}")
    normalized["execution"] = normalize_execution(question_id, question.get("execution"))
    return normalized


def normalize_v2_bank(bank):
    source_mode = bank.get("source_mode")
    if source_mode not in SOURCE_MODES:
        raise SchemaError("Explicit source_mode is required")
    model = copy.deepcopy(bank)
    model["code_blocks"] = {}
    for block in bank.get("code_blocks") or []:
        normalized = normalize_code_block(block, source_mode)
        model["code_blocks"][normalized["id"]] = normalized
    model["questions"] = {}
    model["sections"] = {}
    for section in QUESTION_TYPES:
        model["sections"][section] = []
        for question in bank.get(section) or []:
            normalized = normalize_v2_question(question, section, source_mode)
            question_id = normalized["id"]
            if question_id in model["questions"]:
                raise SchemaError(f"Duplicate question id: {question_id}")
            model["questions"][question_id] = normalized
            model["sections"][section].append(question_id)
    model["groups"] = {}
    for group in bank.get("groups") or []:
        group_id = check_id(group.get("id"), "group")
        if group_id in model["groups"]:
            raise SchemaError(f"Duplicate group id: {group_id}")
        model["groups"][group_id] = copy.deepcopy(group)
    return model


def normalize_bank(bank):
    """Normalize any supported schema version into the internal model."""
    if not isinstance(bank, dict):
        raise SchemaError("A bank must be a JSON object")
    version = bank.get("schema_version", 1)
    if version in (1, None):
        return adapt_legacy_bank(bank)
    if version == SCHEMA_VERSION:
        return normalize_v2_bank(bank)
    raise SchemaError(f"Unsupported schema_version: {version!r}. "
                      f"Supported: absent/1 (legacy) or {SCHEMA_VERSION}.")


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------

def validate_model_counts(model, section):
    questions = model["sections"].get(section, [])
    expected = model["counts"].get(section)
    quotas = model["difficulty_counts"].get(section, {})
    if type(expected) is not int or expected < 0 or expected != len(questions):
        raise SchemaError(f"Question count mismatch for {section}")
    if set(quotas) != set(DIFFICULTIES):
        raise SchemaError(f"All three difficulty counts are required for {section}")
    if any(type(count) is not int or count < 0 for count in quotas.values()):
        raise SchemaError("Difficulty counts must be nonnegative integers")
    if sum(quotas.values()) != expected:
        raise SchemaError(f"Difficulty totals do not match {section}")
    observed = Counter(model["questions"][qid]["difficulty"] for qid in questions)
    if any(observed[difficulty] != quotas[difficulty] for difficulty in DIFFICULTIES):
        raise SchemaError(f"Actual difficulty distribution does not match {section}")


def validate_group(group_id, group, model, seen_members):
    members = group.get("question_ids")
    if not isinstance(members, list) or len(members) < 2:
        raise SchemaError(f"Group {group_id} needs at least two questions")
    group_type = group.get("type")
    if group_type not in QUESTION_TYPES:
        raise SchemaError(f"Group {group_id} type must be one of {QUESTION_TYPES}")
    if group.get("difficulty") not in DIFFICULTIES:
        raise SchemaError(f"Group {group_id} difficulty must be one of {DIFFICULTIES}")
    if group.get("dependency_mode") not in DEPENDENCY_MODES:
        raise SchemaError(f"Group {group_id} dependency_mode must be one of {sorted(DEPENDENCY_MODES)}")
    code_block_id = group.get("code_block_id")
    if code_block_id is not None and code_block_id not in model["code_blocks"]:
        raise SchemaError(f"Group {group_id} references unknown code block {code_block_id}")
    for question_id in members:
        if question_id not in model["questions"]:
            raise SchemaError(f"Group {group_id} references unknown question {question_id}")
        question = model["questions"][question_id]
        if question["section"] != group_type:
            raise SchemaError(f"Group {group_id} mixes sections: {question_id} is {question['section']}")
        if question["difficulty"] != group["difficulty"]:
            raise SchemaError(f"Group {group_id} mixes difficulties: {question_id}")
        if question.get("code_block_id") and question["code_block_id"] != code_block_id:
            raise SchemaError(f"Question {question_id} points at a different code block than {group_id}")
        if question_id in seen_members:
            raise SchemaError(f"Question {question_id} appears in more than one group")
        seen_members.add(question_id)
    linked = group["dependency_mode"] == "linked"
    if linked:
        if group["difficulty"] != "hard":
            raise SchemaError(f"Linked dependencies are hard only: {group_id}")
        if not code_block_id:
            raise SchemaError(f"Linked group {group_id} needs a shared code block")
        permission = (model.get("programming") or {}).get("allow_hard_dependencies")
        if permission is not True:
            raise SchemaError(f"Linked group {group_id} requires the hard-dependency permission")
    validate_dependencies(group_id, group, model)


def validate_dependencies(group_id, group, model):
    members = group["question_ids"]
    position = {question_id: index for index, question_id in enumerate(members)}
    linked = group["dependency_mode"] == "linked"
    graph = {question_id: list(model["questions"][question_id]["depends_on"]) for question_id in members}
    for entry in group.get("dependencies") or []:
        dependent = entry.get("question_id")
        if dependent not in graph:
            raise SchemaError(f"Group {group_id} dependency names unknown question {dependent}")
        if graph[dependent] and graph[dependent] != list(entry.get("depends_on") or []):
            raise SchemaError(f"Contradictory dependency records for {dependent} in {group_id}")
        graph[dependent] = list(entry.get("depends_on") or [])
    for dependent, upstream in graph.items():
        if upstream and not linked:
            raise SchemaError(f"Question {dependent} declares dependencies but group "
                              f"{group_id} is not linked")
        for source in upstream:
            if source not in position:
                raise SchemaError(f"Dependency {source} of {dependent} is outside group {group_id}")
            if position[source] >= position[dependent]:
                raise SchemaError(f"Dependency {source} must precede {dependent} in {group_id}")


def validate_variant(model):
    for question_id, question in model["questions"].items():
        variant = question.get("variant")
        if variant is None:
            continue
        base_id = variant.get("base_block_id")
        if base_id not in model["code_blocks"]:
            raise SchemaError(f"Variant of {question_id} references unknown block {base_id}")
        if question.get("code_block_id") not in (None, base_id):
            raise SchemaError(f"Variant of {question_id} contradicts its code_block_id")
        block_lines = {line["id"] for line in model["code_blocks"][base_id]["lines"]}
        for operation in variant.get("operations") or []:
            op = operation.get("op")
            if op == "append":
                continue
            if op in ("replace", "delete", "insert_after"):
                if operation.get("line_id") not in block_lines:
                    raise SchemaError(f"Variant of {question_id} uses unknown line "
                                      f"{operation.get('line_id')} of {base_id}")
            else:
                raise SchemaError(f"Unknown variant operation {op!r} in {question_id}")


def check_tokens(text, model):
    for match in TOKEN_PATTERN.finditer(text):
        token = match.group(0)
        kind, _, target = token[2:-2].partition(":")
        if kind == "q" and target in model["questions"]:
            continue
        if kind == "block" and target in model["code_blocks"]:
            continue
        if kind == "line":
            block_id, _, line_id = target.partition(":")
            block = model["code_blocks"].get(block_id)
            if block and any(line["id"] == line_id for line in block["lines"]):
                continue
        raise SchemaError(f"Unresolvable reference token {token}")


def validate_references(model):
    used_blocks = set()
    for question in model["questions"].values():
        if question.get("code_block_id"):
            used_blocks.add(question["code_block_id"])
    for group in model["groups"].values():
        if group.get("code_block_id"):
            used_blocks.add(group["code_block_id"])
    for block_id in model["code_blocks"]:
        if block_id not in used_blocks:
            raise SchemaError(f"Orphaned code block: {block_id}")

    for question in model["questions"].values():
        for field in ("question", "statement", "explanation"):
            text = question.get(field)
            if isinstance(text, str):
                check_tokens(text, model)
        for option in question.get("options") or []:
            if isinstance(option, dict):
                check_tokens(option["text"], model)


def validate_essay_styles(model):
    programming = model.get("programming") or {}
    style_counts = programming.get("essay_styles")
    if not style_counts:
        return
    matrix = programming.get("essay_style_difficulty_counts")
    if not isinstance(matrix, dict) or set(matrix) != set(style_counts):
        raise SchemaError("essay_style_difficulty_counts must match the selected styles")
    essays = [model["questions"][qid] for qid in model["sections"]["essays"]]
    observed = Counter(essay.get("essay_style") for essay in essays)
    for style, count in style_counts.items():
        if observed[style] != count:
            raise SchemaError(f"Essay style {style} count is {observed[style]}, expected {count}")
    for style, quotas in matrix.items():
        observed_difficulties = Counter(essay["difficulty"] for essay in essays
                                        if essay.get("essay_style") == style)
        for difficulty in DIFFICULTIES:
            if observed_difficulties[difficulty] != quotas.get(difficulty, 0):
                raise SchemaError(
                    f"Essay style {style} difficulty {difficulty} does not match its matrix")


def validate_model(model, final=False):
    """Validate the normalized model; final=True requires the completed audit."""
    required_text(model, "title")
    if model.get("source_mode") not in SOURCE_MODES:
        raise SchemaError("Explicit source_mode is required")
    for field in ("counts", "difficulty_counts"):
        if not isinstance(model.get(field), dict) or set(model[field]) != set(QUESTION_TYPES):
            raise SchemaError(f"{field} must contain mcqs, true_false, and essays")
    if model.get("language", "en") != "en":
        raise SchemaError("language must be en; this skill produces English output")
    if type(model.get("include_answer_key", True)) is not bool:
        raise SchemaError("include_answer_key must be a boolean")
    if model.get("schema_version") == 1:
        seen_stems = set()
        for section in QUESTION_TYPES:
            validate_model_counts(model, section)
            for question_id in model["sections"][section]:
                question = model["questions"][question_id]
                validate_legacy_question(question, section, model["source_mode"])
                stem = normalized_text(question.get("question", question.get("statement", "")))
                if stem in seen_stems:
                    raise SchemaError(f"Repeated question: {stem}")
                seen_stems.add(stem)
        if sum(model["counts"].values()) < 1:
            raise SchemaError("A question bank must contain at least one question")
        return
    for section in QUESTION_TYPES:
        validate_model_counts(model, section)
        if final:
            for question_id in model["sections"][section]:
                if model["questions"][question_id].get("answer_verified") is not True:
                    raise SchemaError(f"Complete the source-based answer audit for "
                                      f"{question_id} before exporting")
    seen_members = set()
    for group_id, group in model["groups"].items():
        validate_group(group_id, group, model, seen_members)
    validate_variant(model)
    validate_references(model)
    validate_essay_styles(model)
    if sum(model["counts"].values()) < 1:
        raise SchemaError("A question bank must contain at least one question")
