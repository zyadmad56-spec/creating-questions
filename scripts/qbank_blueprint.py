"""Capacity blueprint: turn a normalized interview record into a feasible plan.

One row per shared block or standalone slot. The blueprint never changes the
agreed totals; when a request cannot fit, it reports the supported
alternatives instead of inventing questions.
"""

from qbank_interview import QUESTION_TYPES, DIFFICULTIES, SettingsMismatchError

TYPE_PRIORITY = ("mcqs", "true_false", "essays")
SHARED_BLOCK_MIN_QUESTIONS = 2
# Rough authoring heuristic: one distinct test per ~3 code lines, floor 4.
DENSITY_LINES_PER_QUESTION = 3


def remaining_quota_map(difficulty_counts, conventional_essays=None):
    remaining = {question_type: dict(difficulty_counts[question_type])
                 for question_type in QUESTION_TYPES}
    if conventional_essays:
        for difficulty in DIFFICULTIES:
            remaining["essays"][difficulty] -= conventional_essays[difficulty]
    return remaining


def choose_block_type(remaining, difficulty, questions_target):
    """Pick the type with room for the whole block; ties follow TYPE_PRIORITY."""
    fits = [question_type for question_type in TYPE_PRIORITY
            if remaining[question_type][difficulty] >= questions_target]
    if not fits:
        available = {question_type: remaining[question_type][difficulty]
                     for question_type in TYPE_PRIORITY}
        raise SettingsMismatchError(
            f"No question type has room for this {difficulty} block of {questions_target} "
            f"questions (remaining: {available}). Reduce questions per block, the block "
            "count, or raise the affected total.")
    return max(fits, key=lambda question_type: (remaining[question_type][difficulty],
                                                -TYPE_PRIORITY.index(question_type)))


def density_warnings(spec):
    questions = spec["questions_per_block"]
    lines = spec["approx_code_lines"]
    if questions == 0:
        return []
    if lines == 0:
        return [f"A {questions}-question block was requested with no code lines; "
                "confirm this is a function/API-only allocation."]
    if questions > max(4, lines // DENSITY_LINES_PER_QUESTION):
        return [f"{questions} questions on about {lines} code lines may repeat tests; "
                "expect a capacity negotiation or extra standalone questions."]
    return []


def build_blueprint(record):
    """Return the block/standalone plan for a normalized interview record."""
    programming = record.get("programming")
    if programming is None:
        return {"blocks": [], "standalone_targets": record["difficulty_counts"],
                "essay_styles": None, "warnings": ["Non-programming bank; no code blocks."]}

    blocks = []
    warnings = []
    conventional = programming.get("conventional_essay_counts") or {}
    remaining = remaining_quota_map(record["difficulty_counts"], conventional)
    linked_permission = bool(programming.get("allow_hard_dependencies"))
    block_request = programming.get("blocks") or {}
    languages = programming.get("languages") or [None]

    for difficulty in DIFFICULTIES:
        spec = block_request.get(difficulty)
        if spec is None or spec["count"] == 0:
            continue
        warnings.extend(density_warnings(spec))
        for block_index in range(1, spec["count"] + 1):
            if spec["questions_per_block"] < SHARED_BLOCK_MIN_QUESTIONS:
                warnings.append(
                    f"A one-question {difficulty} block is a standalone snippet, "
                    "not a shared block; it will not count as a shared block.")
            questions_target = spec["questions_per_block"]
            question_type = choose_block_type(remaining, difficulty, questions_target)
            remaining[question_type][difficulty] -= questions_target
            dependency_mode = "independent"
            if difficulty == "hard" and linked_permission:
                dependency_mode = "linked_allowed"
            blocks.append({
                "id": f"b_{difficulty}_{block_index}",
                "type": question_type,
                "difficulty": difficulty,
                "language": languages[(len(blocks)) % len(languages)],
                "questions_target": questions_target,
                "approx_code_lines": spec["approx_code_lines"],
                "dependency_mode": dependency_mode,
                "essay_style": None,
            })

    standalone_targets = remaining
    for difficulty in DIFFICULTIES:
        standalone_targets["essays"][difficulty] += conventional.get(difficulty, 0)
    for question_type in QUESTION_TYPES:
        for difficulty in DIFFICULTIES:
            if remaining[question_type][difficulty] < 0:
                raise SettingsMismatchError(
                    f"Block plan overdraws {question_type} {difficulty} quota by "
                    f"{-remaining[question_type][difficulty]} questions.")

    return {"blocks": blocks, "standalone_targets": standalone_targets,
            "essay_styles": programming.get("essay_styles"),
            "linked_permission": linked_permission,
            "languages": languages, "warnings": warnings}


def blueprint_covers_totals(record, blueprint):
    """Every requested question is in a block or an explicit standalone slot."""
    for question_type in QUESTION_TYPES:
        for difficulty in DIFFICULTIES:
            block_total = sum(block["questions_target"] for block in blueprint["blocks"]
                              if block["type"] == question_type
                              and block["difficulty"] == difficulty)
            standalone = blueprint["standalone_targets"][question_type][difficulty]
            if block_total + standalone != record["difficulty_counts"][question_type][difficulty]:
                return False
    return True
