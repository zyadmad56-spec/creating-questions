"""Format profiles: built-in Classic/Card plus the local saved-format library.

Profiles are declarative layout data only. Runtime paths and converter commands
belong to trusted local code, never to uploaded profiles or bank records.
"""

import json
import shutil
from pathlib import Path

FORMAT_VERSION = 1

CLASSIC_PROFILE = {
    "format_version": FORMAT_VERSION,
    "id": "classic",
    "name": "Classic",
    "description": "The original academic template with the four-column answer table.",
}

CARD_PROFILE = {
    "format_version": FORMAT_VERSION,
    "id": "builtin-card",
    "name": "Card",
    "variants": ["monokai", "print"],
    "code_font": "Consolas",
    "code_font_size_pt": 9.5,
    "chip_font_size_pt": 9.5,
    "option_layout": "adaptive",
    "option_short_threshold": 24,
    "line_numbers": "per_block_gutter",
    "colors": {
        "monokai": {"code": "272823", "gutter": "1e1e1e", "header": "e3e8ef",
                    "chip": "f2f5f9", "gutter_text": "8f908a",
                    "code_text": "f8f8f2", "highlighter": "monokai"},
        "print": {"code": "f6f8fa", "gutter": "e9edf3", "header": "e3e8ef",
                  "chip": "e9edf3", "gutter_text": "57606a",
                  "code_text": "24292f", "highlighter": "friendly"},
    },
}

BUILTIN_PROFILES = {profile["id"]: profile for profile in (CLASSIC_PROFILE, CARD_PROFILE)}


class FormatError(ValueError):
    """Raised for missing, corrupt, or invalid format profiles; files are preserved."""


def formats_root(skill_dir):
    """Local, git-ignored saved-format library at the installed skill root."""
    return Path(skill_dir) / "formats"


def list_available_formats(root=None):
    available = sorted(BUILTIN_PROFILES)
    if root is not None:
        root = Path(root)
        if root.exists():
            for directory in sorted(root.iterdir()):
                if (directory / "format.json").exists():
                    available.append(directory.name)
    return available


def validate_profile(profile):
    if not isinstance(profile, dict):
        raise FormatError("A format profile must be a JSON object")
    version = profile.get("format_version")
    if version != FORMAT_VERSION:
        raise FormatError(f"Unsupported format_version {version!r}; expected {FORMAT_VERSION}")
    profile_id = profile.get("id")
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise FormatError("A format profile needs a nonempty id")
    if profile_id in BUILTIN_PROFILES:
        raise FormatError(f"'{profile_id}' is a built-in format id; choose another name")
    for key in ("code_font",):
        if profile.get(key) is not None and not isinstance(profile[key], str):
            raise FormatError(f"profile.{key} must be a string")
    colors = profile.get("colors")
    if colors is not None and not isinstance(colors, dict):
        raise FormatError("profile.colors must be an object of variant to token colors")
    return profile


def load_saved_profile(name, root):
    directory = Path(root) / name
    profile_path = directory / "format.json"
    if not profile_path.exists():
        raise FormatError(f"Saved format '{name}' was not found in {directory}")
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise FormatError(f"Saved format '{name}' is unreadable ({error}); "
                          "it was not modified.") from error
    validate_profile(profile)
    template = directory / "template.docx"
    if profile.get("template") and not template.exists():
        raise FormatError(f"Saved format '{name}' references a missing template.docx")
    profile["directory"] = str(directory)
    return profile


def resolve_format(profile_id, variant=None, root=None):
    """Resolve a built-in or saved profile; saved formats win over built-ins."""
    if profile_id in (None, "", "classic"):
        return {"profile": CLASSIC_PROFILE, "variant": None}
    if profile_id == "builtin-card" or profile_id == "card":
        profile = CARD_PROFILE
    elif root is not None:
        profile = load_saved_profile(profile_id, root)
    else:
        raise FormatError(f"Unknown format '{profile_id}'. Available: "
                          f"{', '.join(list_available_formats(root))}")
    resolved_variant = variant
    if profile is CARD_PROFILE:
        resolved_variant = variant or "monokai"
        if resolved_variant not in profile["variants"]:
            raise FormatError(f"Card variant must be one of {profile['variants']}")
    return {"profile": profile, "variant": resolved_variant}


def save_format(profile, root, template_source=None):
    """Persist an approved custom format into the local library atomically."""
    validate_profile(profile)
    directory = Path(root) / profile["id"]
    staging = directory.with_name(directory.name + ".tmp")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    (staging / "format.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if template_source is not None:
        shutil.copyfile(template_source, staging / "template.docx")
    if directory.exists():
        shutil.rmtree(directory)
    staging.rename(directory)
    return directory


def card_tokens(profile, variant):
    colors = (profile.get("colors") or {}).get(variant)
    if not colors:
        raise FormatError(f"Card profile has no colors for variant {variant!r}")
    return {"font": profile.get("code_font", "Consolas"),
            "font_size_pt": profile.get("code_font_size_pt", 9.5),
            "chip_font_size_pt": profile.get("chip_font_size_pt", 9.5),
            "option_layout": profile.get("option_layout", "adaptive"),
            "option_short_threshold": profile.get("option_short_threshold", 24),
            **colors}
