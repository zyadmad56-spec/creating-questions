"""Interview contract that turns supplied settings into one normalized bank request.

The interview never invents a missing value. When required settings are absent,
:func:`normalize_settings` collects every missing item and raises
:class:`IncompleteSettingsError` so the agent asks for exactly those items once.
Already answered settings are reused without repetition.
"""

import copy
import json
import os
from pathlib import Path

QUESTION_TYPES = ("mcqs", "true_false", "essays")
DIFFICULTIES = ("easy", "medium", "hard")
SOURCE_MODES = {"source_only", "source_web_general", "pdf_only", "pdf_web_general"}
DELIVERABLES = {"docx", "pdf"}
PROGRAMMING_MODES = {"shared_code", "function_api", "mixed"}
ESSAY_STYLE_IDS = {"scenario", "completion", "bug_fix", "trace_explain"}
BLOCK_SPEC_FIELDS = ("count", "questions_per_block", "approx_code_lines")

SETTINGS_SCHEMA_VERSION = 1


class IncompleteSettingsError(Exception):
    """Raised with the list of settings the user must still supply."""

    def __init__(self, missing):
        self.missing = list(missing)
        super().__init__("Missing required settings: " + ", ".join(self.missing))


class SettingsMismatchError(Exception):
    """Raised when supplied settings contradict each other arithmetically."""


class SettingsCorruptError(Exception):
    """Raised when the local settings file exists but cannot be trusted."""

    def __init__(self, path, detail):
        self.path = str(path)
        self.detail = detail
        super().__init__(f"Local settings file {path} is unreadable ({detail}). "
                         "Fix or delete it manually; it was not overwritten.")


def is_nonnegative_int(value):
    return type(value) is int and value >= 0


def require_nonnegative_int(container, field, missing):
    value = container.get(field)
    if not is_nonnegative_int(value):
        missing.append(field)
        return None
    return value


def normalize_deliverable(supplied, missing):
    deliverable = supplied.get("deliverables")
    if deliverable is None:
        missing.append("deliverables (Word, PDF, or both)")
        return None
    if isinstance(deliverable, str):
        deliverable = [deliverable]
    if (not isinstance(deliverable, list) or not deliverable
            or set(deliverable) - DELIVERABLES or len(set(deliverable)) != len(deliverable)):
        raise SettingsMismatchError(
            "deliverables must be docx, pdf, or both, without repeats")
    return sorted(set(deliverable))


def normalize_format(supplied, missing):
    """Return {"profile_id": ..., "variant": ...} or None when Classic suffices.

    An absent format for a new interactive bank is a missing setting. Legacy
    machine-authored JSON bypasses this interview entirely and stays Classic.
    """
    format_choice = supplied.get("format")
    if format_choice is None:
        missing.append("format (a saved format, a supplied reference, Classic, or Card)")
        return None
    if isinstance(format_choice, str):
        format_choice = {"profile_id": format_choice}
    if not isinstance(format_choice, dict) or not format_choice.get("profile_id"):
        raise SettingsMismatchError("format must name a profile_id, optionally with a variant")
    if format_choice["profile_id"] == "card":
        format_choice = dict(format_choice, profile_id="builtin-card")
    normalized = {"profile_id": format_choice["profile_id"]}
    variant = format_choice.get("variant")
    if variant is not None:
        if variant not in {"monokai", "print"}:
            raise SettingsMismatchError("Card variant must be monokai or print")
        normalized["variant"] = variant
    elif normalized["profile_id"] == "builtin-card":
        missing.append("card variant (monokai or the print-friendly variant)")
    return normalized


def normalize_core_counts(supplied, missing):
    total = require_nonnegative_int(supplied, "total", missing)
    counts = {}
    for question_type in QUESTION_TYPES:
        counts[question_type] = require_nonnegative_int(supplied, question_type, missing)
    if total is None or any(count is None for count in counts.values()):
        return None, None
    if sum(counts.values()) != total:
        raise SettingsMismatchError(
            f"Type counts {counts} sum to {sum(counts.values())}, not the stated total {total}")
    return total, counts


def normalize_difficulty_counts(supplied, counts, missing):
    per_type = supplied.get("difficulty_counts")
    if not isinstance(per_type, dict):
        missing.append("difficulty_counts (integer easy/medium/hard counts per selected type)")
        return None
    normalized = {}
    for question_type in QUESTION_TYPES:
        if counts[question_type] == 0 and question_type not in per_type:
            normalized[question_type] = {difficulty: 0 for difficulty in DIFFICULTIES}
            continue
        quotas = per_type.get(question_type)
        if not isinstance(quotas, dict):
            missing.append(f"difficulty_counts.{question_type}")
            return None
        normalized[question_type] = {}
        for difficulty in DIFFICULTIES:
            normalized[question_type][difficulty] = require_nonnegative_int(
                quotas, difficulty, missing)
        if any(value is None for value in normalized[question_type].values()):
            return None
        if sum(normalized[question_type].values()) != counts[question_type]:
            raise SettingsMismatchError(
                f"{question_type} difficulty counts sum to "
                f"{sum(normalized[question_type].values())}, not {counts[question_type]}")
    return normalized


def normalize_source_mode(supplied, missing):
    source_mode = supplied.get("source_mode")
    if source_mode is None:
        missing.append("source_mode (uploaded material only, or expanded)")
        return None
    if source_mode not in SOURCE_MODES:
        raise SettingsMismatchError(f"Unknown source_mode: {source_mode}")
    return source_mode


def normalize_scope(supplied, missing):
    scope = supplied.get("scope")
    if not scope:
        missing.append("scope (whole files or the specific chapters/pages/slides)")
        return None
    return scope


def normalize_block_spec(spec, difficulty, missing):
    if not isinstance(spec, dict):
        missing.append(f"programming.blocks.{difficulty}")
        return None
    normalized = {}
    for field in BLOCK_SPEC_FIELDS:
        value = require_nonnegative_int(spec, field, missing)
        if value is None:
            return None
        normalized[field] = value
    return normalized


def contributed_question_count(block_specs):
    return sum(spec["count"] * spec["questions_per_block"] for spec in block_specs.values())


def normalize_programming(supplied, counts, missing):
    """Normalize the programming block; returns None when no programming is requested."""
    programming = supplied.get("programming")
    if programming is None:
        return None
    if not isinstance(programming, dict):
        raise SettingsMismatchError("programming must be an object when present")

    content_mode = programming.get("content_mode")
    if content_mode not in PROGRAMMING_MODES:
        missing.append("programming.content_mode (shared code, function/API, or mixed)")
        content_mode = None

    languages = programming.get("languages")
    if not isinstance(languages, list) or not languages:
        missing.append("programming.languages (detected languages per block)")

    normalized = {"content_mode": content_mode, "languages": languages}

    if content_mode in ("shared_code", "mixed"):
        block_request = programming.get("blocks")
        if not isinstance(block_request, dict) or not block_request:
            missing.append("programming.blocks (count, questions per block, code size per difficulty)")
        else:
            blocks = {}
            for difficulty, spec in block_request.items():
                if difficulty not in DIFFICULTIES:
                    raise SettingsMismatchError(f"Unknown block difficulty: {difficulty}")
                normalized_spec = normalize_block_spec(spec, difficulty, missing)
                if normalized_spec is None:
                    return None
                blocks[difficulty] = normalized_spec
            normalized["blocks"] = blocks

    if content_mode in ("function_api", "mixed") and "blocks" not in normalized:
        normalized["blocks"] = {}

    if "blocks" in normalized:
        # Exact per-type allocation happens in the capacity blueprint; here a
        # block set is only rejected when it could not fit inside any one type.
        shared = contributed_question_count(normalized["blocks"])
        largest_type_total = max(counts[question_type] for question_type in QUESTION_TYPES)
        if shared > largest_type_total:
            raise SettingsMismatchError(
                f"Shared blocks request {shared} questions, more than the largest "
                f"question-type total ({largest_type_total}). Reduce block counts "
                "or raise the total; no questions may be invented.")
        normalized["shared_question_target"] = shared

    return normalized


def normalize_essay_styles(supplied, difficulty_counts, missing):
    """Normalize the essay style/difficulty matrix; None when essays are non-code only."""
    styles = supplied.get("essay_styles")
    if styles is None:
        return None
    if not isinstance(styles, dict) or set(styles) - ESSAY_STYLE_IDS:
        raise SettingsMismatchError(
            f"essay_styles keys must be among {sorted(ESSAY_STYLE_IDS)}")

    style_matrix = supplied.get("essay_style_difficulty_counts")
    if not isinstance(style_matrix, dict) or set(style_matrix) != set(styles):
        missing.append("essay_style_difficulty_counts matching the selected styles")
        return None

    normalized = {}
    for style, style_total in styles.items():
        quotas = style_matrix[style]
        if not isinstance(quotas, dict):
            missing.append(f"essay_style_difficulty_counts.{style}")
            return None
        normalized[style] = {}
        for difficulty in DIFFICULTIES:
            normalized[style][difficulty] = require_nonnegative_int(quotas, difficulty, missing)
        if any(value is None for value in normalized[style].values()):
            return None
        if sum(normalized[style].values()) != style_total:
            raise SettingsMismatchError(
                f"Essay style {style} difficulty counts sum to "
                f"{sum(normalized[style].values())}, not its stated count {style_total}")

    style_totals = {difficulty: sum(row[difficulty] for row in normalized.values())
                    for difficulty in DIFFICULTIES}
    for difficulty in DIFFICULTIES:
        if style_totals[difficulty] > difficulty_counts["essays"][difficulty]:
            raise SettingsMismatchError(
                f"Code essay styles request {style_totals[difficulty]} {difficulty} essays, "
                f"more than the essay difficulty quota {difficulty_counts['essays'][difficulty]}")

    conventional = {
        difficulty: difficulty_counts["essays"][difficulty] - style_totals[difficulty]
        for difficulty in DIFFICULTIES
    }
    return {"styles": normalized, "conventional_essay_counts": conventional}


def resolve_hard_dependency_preference(programming, remembered):
    """Return (effective_choice_or_None, asked_flag, applied_remembered_flag).

    Missing settings mean ask; they never silently enable dependencies.
    """
    if "allow_hard_dependencies" in programming:
        choice = programming["allow_hard_dependencies"]
        if type(choice) is not bool:
            raise SettingsMismatchError("allow_hard_dependencies must be a boolean")
        return choice, False, False
    if remembered and "allow_hard_dependencies" in remembered:
        return remembered["allow_hard_dependencies"], False, True
    return None, True, False


def normalize_settings(supplied, remembered=None):
    """Validate supplied interview settings and return the normalized record.

    Raises IncompleteSettingsError listing every still-missing setting, or
    SettingsMismatchError on arithmetic contradictions. Supplied settings are
    never silently replaced; the conversation supplies the rest.
    """
    missing = []
    record = {}
    record["scope"] = normalize_scope(supplied, missing)
    record["deliverables"] = normalize_deliverable(supplied, missing)
    record["format"] = normalize_format(supplied, missing)
    record["source_mode"] = normalize_source_mode(supplied, missing)
    total, counts = normalize_core_counts(supplied, missing)
    record["total"], record["counts"] = total, counts
    if counts is not None:
        record["difficulty_counts"] = normalize_difficulty_counts(supplied, counts, missing)
    else:
        missing.append("difficulty_counts (integer easy/medium/hard counts per selected type)")

    programming = None
    if counts is not None and record["difficulty_counts"] is not None:
        programming = normalize_programming(supplied, counts, missing)
        if programming is not None and programming.get("content_mode") is not None:
            if programming.get("blocks"):
                preference, asked, remembered_applied = resolve_hard_dependency_preference(
                    supplied.get("programming") or {}, remembered)
                if preference is None:
                    missing.append(
                        "allow_hard_dependencies (may hard shared blocks contain linked questions?)")
                record["hard_dependency"] = {
                    "effective": preference,
                    "must_ask": asked,
                    "applied_remembered": remembered_applied,
                }
                if preference is not None:
                    programming["allow_hard_dependencies"] = preference
            raw_programming = supplied.get("programming") or {}
            styles = normalize_essay_styles(
                raw_programming, record["difficulty_counts"], missing)
            if styles is not None:
                programming["essay_styles"] = styles["styles"]
                programming["conventional_essay_counts"] = styles["conventional_essay_counts"]
    record["programming"] = programming

    if missing:
        raise IncompleteSettingsError(missing)
    return record


def load_settings(settings_path):
    """Read the remembered local settings; raises SettingsCorruptError when damaged."""
    path = Path(settings_path)
    if not path.exists():
        return {}
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SettingsCorruptError(path, error) from error
    if not isinstance(settings, dict):
        raise SettingsCorruptError(path, "settings root is not an object")
    version = settings.get("settings_version")
    if version != SETTINGS_SCHEMA_VERSION:
        raise SettingsCorruptError(path, f"unsupported settings_version: {version!r}")
    preference = settings.get("allow_hard_dependencies")
    if preference is not None and type(preference) is not bool:
        raise SettingsCorruptError(path, "allow_hard_dependencies must be a boolean")
    if "last_format_id" in settings and not isinstance(settings["last_format_id"], str):
        raise SettingsCorruptError(path, "last_format_id must be a string")
    return settings


def save_settings(settings, settings_path):
    """Persist remembered settings atomically; a corrupt file is never overwritten."""
    path = Path(settings_path)
    if path.exists():
        load_settings(path)
    payload = {"settings_version": SETTINGS_SCHEMA_VERSION}
    allowed_keys = {"allow_hard_dependencies", "last_format_id"}
    payload.update({key: value for key, value in settings.items()
                    if key in allowed_keys and value is not None})
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return payload


def remembered_choice_summary(remembered):
    """One-line statement used when a remembered preference is applied."""
    if not remembered or "allow_hard_dependencies" not in remembered:
        return ""
    state = "enabled" if remembered["allow_hard_dependencies"] else "disabled"
    return (f"Applying the remembered hard-dependency preference: linked questions in "
            f"hard shared blocks are {state}. Say the word to change it.")
