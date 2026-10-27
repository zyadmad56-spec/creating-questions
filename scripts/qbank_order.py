"""Finalize render order once: shuffle render units, resolve references, manifest.

Shuffling moves whole render units (code groups stay atomic and keep their
internal order), then shuffles MCQ options, assigns continuous question numbers
and sequential block numbers, and resolves reference tokens to final numbers.
The manifest is the single source for both DOCX rendering and any PDF derived
from it; a retry must reuse the manifest rather than reshuffle.
"""

import random

from qbank_schema import QUESTION_TYPES, TOKEN_PATTERN, SchemaError, validate_model

LETTERS = "ABCD"


def render_units(model):
    """Groups are atomic units; every standalone question is a singleton."""
    grouped = {qid for group in model["groups"].values() for qid in group["question_ids"]}
    units = {section: [] for section in QUESTION_TYPES}
    for group_id, group in model["groups"].items():
        units[group["type"]].append({"kind": "group", "id": group_id,
                                     "question_ids": list(group["question_ids"]),
                                     "code_block_id": group.get("code_block_id")})
    for section in QUESTION_TYPES:
        for question_id in model["sections"][section]:
            if question_id in grouped:
                continue
            units[section].append({
                "kind": "standalone", "id": question_id,
                "question_ids": [question_id],
                "code_block_id": model["questions"][question_id].get("code_block_id")})
    return units


def shuffle_options(model, rng):
    """Shuffle MCQ options; returns {question_id: {option_id: final letter}} for v2."""
    letters_by_question = {}
    for question_id, question in model["questions"].items():
        if question["section"] != "mcqs":
            continue
        if model.get("schema_version") == 1:
            correct_text = question["options"][LETTERS.index(question["correct"])]
            rng.shuffle(question["options"])
            question["correct"] = LETTERS[question["options"].index(correct_text)]
        else:
            rng.shuffle(question["options"])
            letters_by_question[question_id] = {
                option["id"]: letter for letter, option in zip(LETTERS, question["options"])}
    return letters_by_question


def block_line_numbers(block):
    return {line["id"]: index for index, line in enumerate(block["lines"], 1)}


def resolve_tokens(text, question_numbers, block_numbers, block_line_maps):
    def replace(match):
        kind, _, target = match.group(0)[2:-2].partition(":")
        if kind == "q":
            return str(question_numbers[target])
        if kind == "block":
            return str(block_numbers[target])
        block_id, _, line_id = target.partition(":")
        return str(block_line_maps[block_id][line_id])

    return TOKEN_PATTERN.sub(replace, text)


def resolve_question_text(question, question_numbers, block_numbers, block_line_maps):
    fields = ["question", "statement", "explanation", "correction"]
    for field in fields:
        text = question.get(field)
        if isinstance(text, str) and TOKEN_PATTERN.search(text):
            question[field] = resolve_tokens(text, question_numbers, block_numbers, block_line_maps)
    for option in question.get("options") or []:
        if isinstance(option, dict) and TOKEN_PATTERN.search(option["text"]):
            option["text"] = resolve_tokens(option["text"], question_numbers,
                                            block_numbers, block_line_maps)
    points = question.get("model_answer")
    if isinstance(points, list):
        question["model_answer"] = [
            resolve_tokens(point, question_numbers, block_numbers, block_line_maps)
            if isinstance(point, str) else point for point in points]


def source_registry(sections_order, model):
    """Stable S1..Sn identifiers for uploaded sources, in final question order."""
    registry = {}
    for section in QUESTION_TYPES:
        for question_id in sections_order[section]:
            for source in model["questions"][question_id]["sources"]:
                if source["kind"] in {"web", "general"}:
                    continue
                key = (source["document"], source["kind"].removesuffix("_inference"))
                if key not in registry:
                    registry[key] = f"S{len(registry) + 1}"
    return registry


def finalize_order(model, seed=None):
    """Validate and finalize the order; returns (sections order, manifest)."""
    validate_model(model, final=True)
    rng = random.Random(seed)
    units = render_units(model)
    letters_by_question = shuffle_options(model, rng)

    question_numbers = {}
    sections_order = {section: [] for section in QUESTION_TYPES}
    unit_records = {section: [] for section in QUESTION_TYPES}
    for section in QUESTION_TYPES:
        section_units = list(units[section])
        rng.shuffle(section_units)
        for unit in section_units:
            numbers = {}
            for question_id in unit["question_ids"]:
                question_numbers[question_id] = len(question_numbers) + 1
                numbers[question_id] = question_numbers[question_id]
                sections_order[section].append(question_id)
            unit_records[section].append({**unit, "numbers": numbers})

    block_numbers, block_line_maps, block_hashes = {}, {}, {}
    block_units = {}
    for section in QUESTION_TYPES:
        for unit in unit_records[section]:
            block_id = unit["code_block_id"]
            if not block_id:
                continue
            if block_id in block_units:
                raise SchemaError(f"Code block {block_id} renders in more than one place; "
                                  "group its questions or use one shared block.")
            block_units[block_id] = unit
            block_numbers[block_id] = len(block_numbers) + 1
            block = model["code_blocks"][block_id]
            block_line_maps[block_id] = block_line_numbers(block)
            block_hashes[block_id] = block["code_hash"]

    for question in model["questions"].values():
        resolve_question_text(question, question_numbers, block_numbers, block_line_maps)

    linked_groups = []
    for group_id, group in model["groups"].items():
        if group.get("dependency_mode") == "linked":
            numbers = [question_numbers[qid] for qid in group["question_ids"]]
            linked_groups.append({"group_id": group_id, "first_question": min(numbers),
                                  "last_question": max(numbers)})

    manifest = {
        "schema_version": model.get("schema_version"),
        "title": model["title"],
        "source_mode": model["source_mode"],
        "format": model.get("format"),
        "deliverables": model.get("deliverables", ["docx"]),
        "seed": seed,
        "counts": model["counts"],
        "difficulty_counts": model["difficulty_counts"],
        "question_numbers": question_numbers,
        "sections": {section: [{"kind": unit["kind"], "unit_id": unit["id"],
                                "code_block_id": unit["code_block_id"],
                                "questions": unit["numbers"]}
                               for unit in unit_records[section]]
                     for section in QUESTION_TYPES},
        "option_letters": letters_by_question,
        "blocks": {block_id: {"display_number": block_numbers[block_id],
                              "line_numbers": block_line_maps[block_id],
                              "code_hash": block_hashes[block_id],
                              "language": model["code_blocks"][block_id]["language"],
                              "version_hint": model["code_blocks"][block_id]["version_hint"]}
                   for block_id in block_numbers},
        "linked_groups": linked_groups,
        "sources": {f"{identifier}": {"document": document, "kind": kind}
                    for (document, kind), identifier in source_registry(sections_order, model).items()},
    }
    return sections_order, manifest
