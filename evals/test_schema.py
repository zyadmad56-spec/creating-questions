"""Phase 4 acceptance checks: normalization, validation, ordering, and manifest."""

import copy
import json
import sys
import unittest
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = EVALS_DIR.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import qbank_order  # noqa: E402
import qbank_schema  # noqa: E402

FIXTURE = EVALS_DIR / "files" / "schema" / "counter_bank.json"


def counter_bank():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def audited_counter_bank():
    bank = counter_bank()
    for question in bank["mcqs"]:
        question["answer_verified"] = True
        question["execution"] = {"status": "not_applicable", "execution_verified": False,
                                 "reason": "Unit test", "cases": []}
    return bank


def hard_linked_bank():
    """The counter bank as an authorized hard linked group."""
    bank = audited_counter_bank()
    for question in bank["mcqs"]:
        question["difficulty"] = "hard"
    bank["groups"][0]["difficulty"] = "hard"
    bank["groups"][0]["dependency_mode"] = "linked"
    bank["difficulty_counts"]["mcqs"] = {"easy": 0, "medium": 0, "hard": 2}
    bank["programming"] = {"allow_hard_dependencies": True}
    return bank


def block(language, lines):
    return {"id": "b_main", "language": language, "version_hint": None,
            "origin": "authored_from_source", "review_status": "recovered",
            "lines": [{"id": f"L{index}", "text": text} for index, text in enumerate(lines, 1)],
            "sources": [{"kind": "document", "document": "synthetic.txt",
                         "locator": "synthetic teaching lines",
                         "evidence": "Synthetic evidence for the test."}]}


class NormalizationTests(unittest.TestCase):
    def test_legacy_bank_is_adapted_without_rewriting_the_input(self):
        bank = json.loads((EVALS_DIR / "files" / "sample_questions.json").read_text(encoding="utf-8"))
        original = copy.deepcopy(bank)
        model = qbank_schema.normalize_bank(bank)
        self.assertEqual(bank, original, "Normalizing must not rewrite the caller's JSON")
        self.assertEqual(model["schema_version"], 1)
        self.assertEqual(len(model["questions"]), 6)
        self.assertTrue(all(qid in model["questions"] for qid in model["sections"]["mcqs"]))
        self.assertEqual(model["questions"]["q_mcq_001"]["section"], "mcqs")

    def test_unsupported_explicit_version_is_rejected(self):
        bank = counter_bank()
        bank["schema_version"] = 3
        with self.assertRaisesRegex(qbank_schema.SchemaError, "Unsupported schema_version"):
            qbank_schema.normalize_bank(bank)

    def test_v2_draft_normalizes_but_final_export_requires_the_audit(self):
        model = qbank_schema.normalize_bank(counter_bank())
        qbank_schema.validate_model(model, final=False)
        with self.assertRaisesRegex(qbank_schema.SchemaError, "answer audit"):
            qbank_schema.validate_model(model, final=True)

    def test_execution_status_and_verification_must_agree(self):
        bank = audited_counter_bank()
        bank["mcqs"][0]["execution"] = {"status": "passed", "execution_verified": False}
        with self.assertRaisesRegex(qbank_schema.SchemaError, "must be verified"):
            qbank_schema.normalize_bank(bank)
        bank["mcqs"][0]["execution"] = {"status": "unavailable", "execution_verified": True}
        with self.assertRaisesRegex(qbank_schema.SchemaError, "cannot be execution_verified"):
            qbank_schema.normalize_bank(bank)

    def test_tokens_are_rejected_inside_code_lines(self):
        bank = audited_counter_bank()
        bank["code_blocks"][0]["lines"][0]["text"] = "class {{q:q_value}}:"
        with self.assertRaisesRegex(qbank_schema.SchemaError, "forbidden inside code"):
            qbank_schema.normalize_bank(bank)

    def test_code_hash_changes_when_code_changes(self):
        self.assertNotEqual(qbank_schema.code_hash("a = 1"), qbank_schema.code_hash("a = 2"))


def mutated_bank(**changes):
    """Apply call-time mutations to a fresh audited counter bank."""
    bank = audited_counter_bank()
    for dotted, value in changes.items():
        target = bank
        parts = dotted.split(".")
        for part in parts[:-1]:
            target = target[int(part)] if isinstance(target, list) else target[part]
        if isinstance(target, list):
            index = int(parts[-1])
            if value is KeyError:
                del target[index]
            else:
                target[index] = value
        elif value is KeyError:
            del target[parts[-1]]
        else:
            target[parts[-1]] = value
    return bank


class ValidationTests(unittest.TestCase):
    def validate_rejection(self, bank, message):
        with self.assertRaisesRegex(qbank_schema.SchemaError, message):
            model = qbank_schema.normalize_bank(bank)
            qbank_schema.validate_model(model, final=True)

    def test_negative_cases_from_the_schema_contract(self):
        cross_section = mutated_bank()
        cross_section["mcqs"] = [cross_section["mcqs"][0]]
        tf_question = {key: value for key, value in cross_section["mcqs"][0].items()}
        tf_question.update({"id": "q_tf", "statement": "Counter starts at four.",
                            "correct": "True", "question": None})
        cross_section["true_false"] = [tf_question]
        cross_section["counts"] = {"mcqs": 1, "true_false": 1, "essays": 0}
        cross_section["difficulty_counts"] = {
            "mcqs": {"easy": 1, "medium": 0, "hard": 0},
            "true_false": {"easy": 1, "medium": 0, "hard": 0},
            "essays": {"easy": 0, "medium": 0, "hard": 0}}
        cross_section["groups"][0] = {"id": "g_mixed", "type": "true_false", "difficulty": "easy",
                                      "code_block_id": "b_counter",
                                      "dependency_mode": "independent",
                                      "question_ids": ["q_value", "q_tf"]}
        cases = [
            (mutated_bank(**{"mcqs.0.correct_option_id": "o_missing"}), "correct_option_id"),
            (mutated_bank(**{"groups.0.question_ids": ["q_value", "q_value"]}),
             "more than one group"),
            (mutated_bank(**{"groups.0.difficulty": "medium",
                             "groups.0.dependency_mode": "linked",
                             "mcqs.0.difficulty": "medium",
                             "mcqs.1.difficulty": "medium",
                             "difficulty_counts.mcqs": {"easy": 0, "medium": 2, "hard": 0}}),
             "hard only"),
            (mutated_bank(**{"groups.0.dependency_mode": "linked",
                             "groups.0.difficulty": "hard",
                             "mcqs.0.difficulty": "hard",
                             "mcqs.1.difficulty": "hard",
                             "difficulty_counts.mcqs": {"easy": 0, "medium": 0, "hard": 2},
                             "groups.0.dependencies": [
                                 {"question_id": "q_return", "depends_on": ["q_value"]}],
                             "mcqs.1.depends_on": ["q_value"],
                             "programming": {"allow_hard_dependencies": False}}),
             "hard-dependency permission"),
            (mutated_bank(**{"groups.0.dependency_mode": "linked",
                             "groups.0.difficulty": "hard",
                             "mcqs.0.difficulty": "hard",
                             "mcqs.1.difficulty": "hard",
                             "difficulty_counts.mcqs": {"easy": 0, "medium": 0, "hard": 2},
                             "groups.0.dependencies": [
                                 {"question_id": "q_value", "depends_on": ["q_return"]}],
                             "mcqs.0.depends_on": ["q_return"],
                             "programming": {"allow_hard_dependencies": True}}),
             "must precede"),
            (cross_section, "mixes sections"),
            (mutated_bank(**{"code_blocks.0.id": "b_unused",
                             "groups": [],
                             "mcqs.0.code_block_id": None,
                             "mcqs.1.code_block_id": None,
                             "mcqs.0.variant": None,
                             "mcqs.1.variant": None}), "Orphaned code block"),
            (mutated_bank(**{"mcqs.0.question": "See {{q:q_ghost}} for details."}),
             "Unresolvable reference token"),
            (mutated_bank(**{"mcqs.0.variant": {"base_block_id": "b_counter", "reset": True,
                                                "operations": [{"op": "replace", "line_id": "L99",
                                                                "text": "x = 1"}]}}),
             "unknown line"),
        ]
        for index, (bank, message) in enumerate(cases):
            with self.subTest(case=index, message=message):
                self.validate_rejection(bank, message)

    def test_forward_reference_inside_a_linked_group_is_rejected(self):
        # Dependencies must point to earlier members, which makes cycles and
        # future references structurally impossible in a linked group.
        bank = hard_linked_bank()
        bank["mcqs"][0]["depends_on"] = ["q_return"]
        bank["groups"][0]["dependencies"] = [
            {"question_id": "q_value", "depends_on": ["q_return"]}]
        self.validate_rejection(bank, "must precede")

    def test_block_rendered_in_two_places_is_rejected(self):
        bank = audited_counter_bank()
        bank["groups"] = []
        bank["mcqs"][1]["code_block_id"] = "b_counter"
        model = qbank_schema.normalize_bank(bank)
        qbank_schema.validate_model(model, final=True)
        with self.assertRaisesRegex(qbank_schema.SchemaError, "more than one place"):
            qbank_order.finalize_order(model, seed=1)


class OrderingTests(unittest.TestCase):
    def setUp(self):
        self.model = qbank_schema.normalize_bank(audited_counter_bank())

    def test_manifest_records_numbers_blocks_lines_and_letters(self):
        sections_order, manifest = qbank_order.finalize_order(self.model, seed=7)
        self.assertEqual(sorted(manifest["question_numbers"].values()), [1, 2])
        block = manifest["blocks"]["b_counter"]
        self.assertEqual(block["display_number"], 1)
        self.assertEqual(block["line_numbers"]["L1"], 1)
        self.assertEqual(block["line_numbers"]["L7"], 7)
        self.assertEqual(len(block["code_hash"]), 64)
        letters = manifest["option_letters"]["q_value"]
        self.assertEqual(sorted(letters.values()), list("ABCD"))
        correct_letter = next(letter for option_id, letter in letters.items()
                              if option_id == "q_value_o1" or option_id == "o_value_4")
        self.assertIn(correct_letter, "ABCD")

    def test_group_stays_contiguous_and_every_question_appears_once(self):
        sections_order, manifest = qbank_order.finalize_order(self.model, seed=3)
        all_numbers = sorted(manifest["question_numbers"].values())
        self.assertEqual(all_numbers, [1, 2])
        numbers = [manifest["question_numbers"][qid] for qid in sections_order["mcqs"]]
        self.assertEqual(sorted(numbers), [1, 2])

    def test_option_letters_track_the_correct_option_after_shuffle(self):
        _, manifest = qbank_order.finalize_order(self.model, seed=11)
        for question_id in self.model["sections"]["mcqs"]:
            question = self.model["questions"][question_id]
            letters = manifest["option_letters"][question_id]
            self.assertEqual(sorted(letters.values()), list("ABCD"))
            letter = letters[question["correct_option_id"]]
            self.assertIn(letter, "ABCD")
            correct_option = next(option for option in question["options"]
                                  if option["id"] == question["correct_option_id"])
            self.assertTrue(correct_option["text"].strip())

    def test_different_seeds_can_reorder_units(self):
        orders = []
        for seed in range(1, 13):
            bank = audited_counter_bank()
            bank["groups"] = []
            bank["code_blocks"] = []
            for question in bank["mcqs"]:
                question["code_block_id"] = None
                question["variant"] = None
                question["question"] = f"Plain seeded question {question['id']}?"
            sections_order, _ = qbank_order.finalize_order(
                qbank_schema.normalize_bank(bank), seed=seed)
            orders.append(tuple(sections_order["mcqs"]))
        self.assertGreater(len(set(orders)), 1, "Seeded shuffles should vary")

    def test_tokens_resolve_to_final_numbers_without_leftovers(self):
        sections_order, manifest = qbank_order.finalize_order(self.model, seed=5)
        for question_id in sections_order["mcqs"]:
            question = self.model["questions"][question_id]
            self.assertNotIn("{{", question["question"])
        number = manifest["question_numbers"]["q_value"]
        self.assertIn(str(number), self.model["questions"]["q_value"]["question"])

    def test_line_tokens_resolve_to_logical_line_numbers(self):
        model = qbank_schema.normalize_bank(audited_counter_bank())
        model["questions"]["q_value"]["question"] = \
            "What happens at line {{line:b_counter:L5}} of block {{block:b_counter}}?"
        _, manifest = qbank_order.finalize_order(model, seed=2)
        self.assertIn("line 5 of block 1", model["questions"]["q_value"]["question"])

    def test_linked_group_manifest_carries_the_notice_range(self):
        model = qbank_schema.normalize_bank(hard_linked_bank())
        model["groups"]["g_counter"]["dependencies"] = [
            {"question_id": "q_return", "depends_on": ["q_value"]}]
        model["questions"]["q_return"]["depends_on"] = ["q_value"]
        _, manifest = qbank_order.finalize_order(model, seed=9)
        self.assertEqual(len(manifest["linked_groups"]), 1)
        linked = manifest["linked_groups"][0]
        self.assertEqual(linked["last_question"] - linked["first_question"], 1)


if __name__ == "__main__":
    unittest.main()
