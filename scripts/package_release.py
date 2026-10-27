"""Package the reusable skill into a clean local ZIP with a verified manifest.

Only reusable assets ship: skill documentation, templates, helper code, tests,
synthetic fixtures, dependency declarations, license, and CI configuration.
Private course material, local preferences, and generated artifacts are
excluded by allowlist — the manifest lists exactly what is inside.
"""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]

INCLUDE_PATTERNS = [
    "SKILL.md", "README.md", "LICENSE", "requirements.txt", "requirements-dev.txt",
    ".gitignore", "agents/*", "assets/*",
    "scripts/*.py", "references/*.md",
    "evals/*.py", "evals/*.json", "evals/*.md",
    "evals/files/*.py", "evals/files/*.json",
    "evals/files/interview/*.json", "evals/files/schema/*.json",
    "evals/files/semantic/*.py", "evals/files/semantic/*.json",
    "evals/files/semantic/*.md",
    "evals/files/copy_prototype/*.py", "evals/files/copy_prototype/*.md",
    "evals/files/copy_prototype/*.png",
    ".github/workflows/*.yml",
]

EXCLUDE_TOKENS = ("settings.json", "formats/", "work/", "__pycache__", ".venv",
                  "*.docx.bak")


def matches_any(relative_path, patterns):
    path = Path(relative_path)
    return any(path.match(pattern) for pattern in patterns)


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_files():
    collected = []
    for path in sorted(SKILL_DIR.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(SKILL_DIR).as_posix()
        if any(token in relative for token in EXCLUDE_TOKENS):
            continue
        if matches_any(relative, INCLUDE_PATTERNS):
            collected.append((relative, path))
    return collected


def private_scan(entries):
    """Fail loudly if anything that must never ship is about to be packaged.

    The blank template asset (assets/Creating Questions.docx) is an allowed
    reusable file; generated banks and private material are not.
    """
    problems = []
    for relative, _ in entries:
        lowered = relative.lower()
        if lowered.endswith(".pdf") or lowered.endswith(".extraction.json"):
            problems.append(relative)
        if "question_bank" in lowered and lowered.endswith(".docx"):
            problems.append(relative)
        if lowered == "settings.json":
            problems.append(relative)
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_zip", help="Path of the local release ZIP to create")
    arguments = parser.parse_args()
    output_zip = Path(arguments.output_zip)
    entries = collect_files()
    problems = private_scan(entries)
    if problems:
        raise SystemExit("Refusing to package private or generated files: "
                         + ", ".join(problems))
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    manifest_entries = []
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative, path in entries:
            archive.write(path, arcname=f"creating-questions/{relative}")
            manifest_entries.append({"path": relative, "sha256": sha256_of(path)})
    manifest = {
        "package": "creating-questions",
        "source_skill": str(SKILL_DIR),
        "zip": str(output_zip),
        "zip_sha256": sha256_of(output_zip),
        "excluded_by_design": [
            "real course PDFs and images", "extracted course text", "real banks",
            "local settings.json", "saved formats library", "generated DOCX/PDF output",
            "execution outputs containing course data",
        ],
        "files": manifest_entries,
    }
    manifest_path = output_zip.with_suffix(".zip.manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    print(f"packaged {len(entries)} files into {output_zip}")
    print(f"manifest: {manifest_path}")


if __name__ == "__main__":
    main()
