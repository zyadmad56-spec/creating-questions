"""Phase 3 acceptance checks: block allocation, capacity, and dependency permission."""

import copy
import json
import sys
import unittest
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = EVALS_DIR.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import qbank_blueprint  # noqa: E402
import qbank_interview  # noqa: E402

FIXTURE_DIR = EVALS_DIR / "files" / "interview"


def normalized_fixture(fixture_name, mutations=None):
    """Load a fixture's supplied settings, apply nested mutations, re-normalize."""
    fixture = json.loads((FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"))
    supplied = copy.deepcopy(fixture["supplied"])
    for dotted, value in (mutations or {}).items():
        target = supplied
        parts = dotted.split(".")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
    return qbank_interview.normalize_settings(supplied, copy.deepcopy(fixture.get("remembered")))


class BlueprintAllocationTests(unittest.TestCase):
    def test_blocks_fill_quotas_and_remainder_is_explicit(self):
        record = normalized_fixture("complete_programming.json")
        blueprint = qbank_blueprint.build_blueprint(record)
        self.assertEqual(len(blueprint["blocks"]), 3)
        for block in blueprint["blocks"]:
            self.assertEqual(block["type"], "mcqs")
            self.assertEqual(block["questions_target"], 2)
        self.assertTrue(qbank_blueprint.blueprint_covers_totals(record, blueprint))
        self.assertEqual(blueprint["standalone_targets"]["mcqs"],
                         {"easy": 0, "medium": 0, "hard": 0})
        self.assertEqual(blueprint["standalone_targets"]["true_false"],
                         {"easy": 1, "medium": 0, "hard": 1})
        self.assertEqual(blueprint["standalone_targets"]["essays"],
                         {"easy": 1, "medium": 2, "hard": 1})

    def test_hard_blocks_are_marked_linked_only_with_permission(self):
        allowed = qbank_blueprint.build_blueprint(normalized_fixture("complete_programming.json"))
        self.assertTrue(allowed["linked_permission"])
        hard_modes = {block["dependency_mode"] for block in allowed["blocks"]
                      if block["difficulty"] == "hard"}
        self.assertEqual(hard_modes, {"linked_allowed"})

        denied = qbank_blueprint.build_blueprint(
            normalized_fixture("complete_programming.json",
                               {"programming.allow_hard_dependencies": False}))
        self.assertFalse(denied["linked_permission"])
        self.assertTrue(all(block["dependency_mode"] == "independent"
                            for block in denied["blocks"]))

    def test_blocks_that_overdraw_a_type_quota_are_rejected_at_allocation(self):
        # The interview passes (4 shared easy questions fit the 4-question MCQ
        # total), but two easy blocks of 2 cannot both fit the 2-question easy quota.
        record = normalized_fixture("remembered_preference.json", {
            "programming.blocks": {"easy": {"count": 2, "questions_per_block": 2,
                                            "approx_code_lines": 10}},
        })
        with self.assertRaisesRegex(qbank_blueprint.SettingsMismatchError,
                                    "room for this easy block"):
            qbank_blueprint.build_blueprint(record)

    def test_interview_rejects_shared_blocks_larger_than_any_type_total(self):
        with self.assertRaises(qbank_interview.SettingsMismatchError):
            normalized_fixture("infeasible_density.json")

    def test_single_question_block_is_reported_as_a_snippet(self):
        record = normalized_fixture("remembered_preference.json", {
            "programming.blocks": {
                "easy": {"count": 2, "questions_per_block": 1, "approx_code_lines": 10}},
        })
        blueprint = qbank_blueprint.build_blueprint(record)
        self.assertTrue(any("standalone snippet" in warning for warning in blueprint["warnings"]))
        self.assertTrue(qbank_blueprint.blueprint_covers_totals(record, blueprint))

    def test_dense_block_produces_a_negotiation_warning(self):
        record = normalized_fixture("remembered_preference.json", {
            "total": 12,
            "mcqs": 8,
            "difficulty_counts.mcqs": {"easy": 2, "medium": 1, "hard": 5},
            "programming.blocks": {
                "easy": {"count": 1, "questions_per_block": 2, "approx_code_lines": 10},
                "hard": {"count": 1, "questions_per_block": 5, "approx_code_lines": 14}},
        })
        blueprint = qbank_blueprint.build_blueprint(record)
        self.assertTrue(any("capacity negotiation" in warning for warning in blueprint["warnings"]))
        self.assertTrue(qbank_blueprint.blueprint_covers_totals(record, blueprint))

    def test_non_programming_bank_has_no_blocks(self):
        record = normalized_fixture("no_code_material.json")
        blueprint = qbank_blueprint.build_blueprint(record)
        self.assertEqual(blueprint["blocks"], [])
        self.assertTrue(qbank_blueprint.blueprint_covers_totals(record, blueprint))

    def test_essay_blocks_cannot_take_conventional_essay_slots(self):
        # One easy essay is reserved as conventional (non-code), leaving essay
        # easy room 1; with MCQ and True/False easy rooms also below the block
        # size, an easy block of 2 has nowhere to go.
        record = normalized_fixture("all_essay_styles.json", {
            "total": 13,
            "essays": 7,
            "difficulty_counts.essays": {"easy": 2, "medium": 3, "hard": 2},
            "programming.content_mode": "mixed",
            "programming.allow_hard_dependencies": False,
            "programming.blocks": {"easy": {"count": 1, "questions_per_block": 2,
                                            "approx_code_lines": 10}},
        })
        with self.assertRaises(qbank_blueprint.SettingsMismatchError):
            qbank_blueprint.build_blueprint(record)


if __name__ == "__main__":
    unittest.main()
