"""Phase 1 acceptance checks: scripted interview fixtures and settings persistence."""

import copy
import importlib.util
import json
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "qbank_interview.py"
SPEC = importlib.util.spec_from_file_location("qbank_interview", SCRIPT)
qbank_interview = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qbank_interview)

FIXTURE_DIR = Path(__file__).resolve().parent / "files" / "interview"


def load_fixtures():
    return [json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(FIXTURE_DIR.glob("*.json"))]


def read_path(record, dotted):
    value = record
    for part in dotted.split("."):
        value = value[part]
    return value


class InterviewFixtureTests(unittest.TestCase):
    def test_each_fixture_produces_its_documented_contract_result(self):
        for fixture in load_fixtures():
            with self.subTest(fixture=fixture["name"]):
                expectation = fixture["expect"]
                if expectation == "ok":
                    record = qbank_interview.normalize_settings(
                        copy.deepcopy(fixture["supplied"]), fixture["remembered"])
                    for dotted, expected in fixture.get("assert", {}).items():
                        if dotted == "hard_dependency" and expected is None:
                            self.assertNotIn("hard_dependency", record)
                        else:
                            self.assertEqual(read_path(record, dotted), expected,
                                             f"{fixture['name']}: {dotted}")
                elif expectation == "missing":
                    with self.assertRaises(qbank_interview.IncompleteSettingsError) as caught:
                        qbank_interview.normalize_settings(
                            copy.deepcopy(fixture["supplied"]), fixture["remembered"])
                    self.assertEqual(len(caught.exception.missing), fixture["missing_count"])
                elif expectation == "mismatch":
                    with self.assertRaisesRegex(
                            qbank_interview.SettingsMismatchError, fixture["error_contains"]):
                        qbank_interview.normalize_settings(
                            copy.deepcopy(fixture["supplied"]), fixture["remembered"])
                else:
                    self.fail(f"Unknown expectation {expectation!r}")

    def test_missing_list_never_repeats_an_answered_setting(self):
        for fixture in load_fixtures():
            if fixture["expect"] != "missing":
                continue
            with self.subTest(fixture=fixture["name"]):
                with self.assertRaises(qbank_interview.IncompleteSettingsError) as caught:
                    qbank_interview.normalize_settings(
                        copy.deepcopy(fixture["supplied"]), fixture["remembered"])
                for supplied_key in fixture["supplied"]:
                    self.assertNotIn(supplied_key, " ".join(caught.exception.missing),
                                     f"{supplied_key} was supplied but asked again")

    def test_hard_blocks_without_any_preference_are_asked_not_enabled(self):
        supplied = {
            "scope": "Pages 1-5", "deliverables": "docx", "format": "classic",
            "source_mode": "source_only", "total": 4, "mcqs": 4, "true_false": 0,
            "essays": 0,
            "difficulty_counts": {"mcqs": {"easy": 2, "medium": 0, "hard": 2},
                                  "true_false": {"easy": 0, "medium": 0, "hard": 0},
                                  "essays": {"easy": 0, "medium": 0, "hard": 0}},
            "programming": {"content_mode": "shared_code", "languages": ["python"],
                            "blocks": {"hard": {"count": 1, "questions_per_block": 2,
                                                "approx_code_lines": 10}}},
        }
        with self.assertRaises(qbank_interview.IncompleteSettingsError) as caught:
            qbank_interview.normalize_settings(supplied)
        self.assertIn("allow_hard_dependencies", caught.exception.missing[0])


class SettingsPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.scratch = Path.cwd() / "work" / "settings_persistence"
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.scratch / "settings.json"
        self.addCleanup(lambda: qbank_interview.save_settings(
            {"allow_hard_dependencies": True}, self.settings_path))
        self.addCleanup(self.settings_path.unlink, missing_ok=True)

    def test_saved_settings_round_trip_and_apply_to_later_runs(self):
        qbank_interview.save_settings(
            {"allow_hard_dependencies": True, "last_format_id": "builtin-card"},
            self.settings_path)
        settings = qbank_interview.load_settings(self.settings_path)
        self.assertEqual(settings["allow_hard_dependencies"], True)
        self.assertEqual(settings["last_format_id"], "builtin-card")

    def test_corrupt_settings_are_reported_and_never_overwritten(self):
        self.settings_path.write_text('{"settings_version": 1, "allow_hard": ', encoding="utf-8")
        damaged = self.settings_path.read_text(encoding="utf-8")
        with self.assertRaises(qbank_interview.SettingsCorruptError):
            qbank_interview.load_settings(self.settings_path)
        with self.assertRaises(qbank_interview.SettingsCorruptError):
            qbank_interview.save_settings({"allow_hard_dependencies": True},
                                          self.settings_path)
        self.assertEqual(self.settings_path.read_text(encoding="utf-8"), damaged)

    def test_unsupported_settings_version_is_rejected(self):
        self.settings_path.write_text('{"settings_version": 99}', encoding="utf-8")
        with self.assertRaisesRegex(qbank_interview.SettingsCorruptError, "settings_version"):
            qbank_interview.load_settings(self.settings_path)

    def test_missing_settings_file_means_ask_not_default(self):
        self.assertEqual(qbank_interview.load_settings(self.scratch / "absent.json"), {})

    def test_remembered_choice_summary_states_the_applied_preference(self):
        summary = qbank_interview.remembered_choice_summary(
            {"allow_hard_dependencies": True})
        self.assertIn("enabled", summary)
        self.assertEqual(qbank_interview.remembered_choice_summary({}), "")


if __name__ == "__main__":
    unittest.main()
