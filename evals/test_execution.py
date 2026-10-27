"""Phase 6 acceptance checks: screened execution, variants, and honest limits."""

import copy
import json
import sys
import unittest
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = EVALS_DIR.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import qbank_execution  # noqa: E402
import qbank_schema  # noqa: E402
from test_schema import audited_counter_bank, hard_linked_bank  # noqa: E402

FIXTURE = EVALS_DIR / "files" / "schema" / "counter_bank.json"


def block_model(code_lines, language="python", question_overrides=None):
    """A minimal one-question v2 model for execution tests."""
    question = {"id": "q_run", "statement": "The block runs as shown.",
                "correct": "True", "difficulty": "easy",
                "code_block_id": "b_main",
                "explanation": "Because.", "answer_verified": True,
                "execution": {"status": "not_run", "execution_verified": False,
                              "cases": []},
                "sources": [{"kind": "document", "document": "synthetic.txt",
                             "locator": "line 1", "evidence": "Synthetic."}]}
    question.update(question_overrides or {})
    return {
        "schema_version": 2, "title": "Exec fixture", "source_mode": "source_only",
        "counts": {"mcqs": 0, "true_false": 1, "essays": 0},
        "difficulty_counts": {"mcqs": {"easy": 0, "medium": 0, "hard": 0},
                              "true_false": {"easy": 1, "medium": 0, "hard": 0},
                              "essays": {"easy": 0, "medium": 0, "hard": 0}},
        "programming": {"allow_hard_dependencies": False},
        "code_blocks": [{"id": "b_main", "language": language,
                         "origin": "authored_from_source", "review_status": "recovered",
                         "lines": [{"id": f"L{i}", "text": text}
                                   for i, text in enumerate(code_lines, 1)],
                         "sources": question["sources"]}],
        "groups": [], "mcqs": [], "true_false": [question], "essays": [],
    }


class ScreenTests(unittest.TestCase):
    def test_educational_code_passes_the_screen(self):
        allowed, violations = qbank_execution.screen_code("total = 1 + 2\nprint(total)\n")
        self.assertTrue(allowed)
        self.assertEqual(violations, [])

    def test_forbidden_capabilities_are_refused(self):
        cases = {
            "network": "import socket\nsocket.socket()\n",
            "process": "import subprocess\nsubprocess.run(['ls'])\n",
            "shell": "import os\nos.system('ls')\n",
            "file_write": "open('out.txt', 'w').write('x')\n",
            "dynamic_exec": "eval('1 + 1')\n",
            "fetch": "import urllib.request\nurllib.request.urlopen('http://x')\n",
        }
        for name, code in cases.items():
            with self.subTest(capability=name):
                allowed, violations = qbank_execution.screen_code(code)
                self.assertFalse(allowed, name)
                self.assertTrue(violations)

    def test_syntax_error_is_reported_not_faked(self):
        allowed, violations = qbank_execution.screen_code("def broken(:\n")
        self.assertFalse(allowed)
        self.assertIn("does not parse", violations[0])


class ExecutionTests(unittest.TestCase):
    def run_question(self, model, **kwargs):
        normalized = qbank_schema.normalize_bank(copy.deepcopy(model))
        return qbank_execution.run_question(normalized, normalized["true_false"][0], **kwargs)

    def test_exact_output_and_return_only_are_distinguished(self):
        printing = self.run_question(block_model(
            ["c = 4", "print(c)"],
            question_overrides={"execution": {"status": "not_run",
                                              "execution_verified": False,
                                              "cases": [{"expected_stdout": "4\n"}]}}))
        self.assertEqual(printing["status"], "passed")
        self.assertTrue(printing["execution_verified"])
        self.assertEqual(printing["cases"][0]["match"], True)

        silent = self.run_question(block_model(
            ["def f():", "    return 7", "f()"],
            question_overrides={"execution": {"status": "not_run",
                                              "execution_verified": False,
                                              "cases": [{"expected_stdout": ""}]}}))
        self.assertEqual(silent["status"], "passed")

        wrong = self.run_question(block_model(
            ["print(2 + 2)"],
            question_overrides={"execution": {"status": "not_run",
                                              "execution_verified": False,
                                              "cases": [{"expected_stdout": "5\n"}]}}))
        self.assertEqual(wrong["status"], "failed")
        self.assertFalse(wrong["execution_verified"])

    def test_expected_exception_is_a_verified_answer(self):
        record = self.run_question(block_model(
            ["value = {'a': 1}", "print(value['missing'])"],
            question_overrides={"execution": {"status": "not_run",
                                              "execution_verified": False,
                                              "cases": [{"expected_exception": "KeyError"}]}}))
        self.assertEqual(record["status"], "passed")
        self.assertEqual(record["cases"][0]["match"], True)

    def test_screen_refusal_is_recorded_as_unavailable_not_passed(self):
        record = self.run_question(block_model(
            ["import socket", "print('no')"]))
        self.assertEqual(record["status"], "unavailable")
        self.assertFalse(record["execution_verified"])
        self.assertIn("screen", record["reason"])

    def test_timeout_is_recorded(self):
        record = self.run_question(block_model(["while True:", "    x = 1"]),
                                   timeout_s=2)
        self.assertEqual(record["status"], "failed")
        self.assertIn("timeout", record["cases"][0]["observation"]["stderr"])

    def test_missing_runtime_is_honest(self):
        record = self.run_question(block_model(
            ["int main(void){return 0;}", ""], language="c"))
        if record["status"] == "passed":
            self.assertTrue(record["execution_verified"])
            self.assertIn("gcc", record["runtime"]["executable"])
        else:
            self.assertEqual(record["status"], "unavailable")
            self.assertIn("No local c runtime", record["reason"])

    def test_variant_operations_build_the_exact_effective_program(self):
        model = qbank_schema.normalize_bank(audited_counter_bank())
        question = model["questions"]["q_value"]
        code_text, numbers = qbank_schema.effective_program(
            model, "b_counter", question["variant"])
        self.assertEqual(code_text.splitlines()[-1], "print(c.value)")
        self.assertEqual(numbers["L1"], 1)
        replaced, _ = qbank_schema.effective_program(model, "b_counter", {
            "base_block_id": "b_counter",
            "operations": [{"op": "replace", "line_id": "L5", "text": "        self.value += 10"}]})
        self.assertIn("self.value += 10", replaced)
        self.assertNotIn("+= 3", replaced)
        inserted, _ = qbank_schema.effective_program(model, "b_counter", {
            "base_block_id": "b_counter",
            "operations": [{"op": "insert_after", "line_id": "L3", "text": "    # note"}]})
        self.assertEqual(inserted.splitlines()[3], "    # note")
        deleted, _ = qbank_schema.effective_program(model, "b_counter", {
            "base_block_id": "b_counter",
            "operations": [{"op": "delete", "line_id": "L7"}]})
        self.assertNotIn("c = Counter(4)", deleted)

    def test_variant_execution_runs_the_exact_variant(self):
        model = qbank_schema.normalize_bank(audited_counter_bank())
        question = model["questions"]["q_value"]
        question["execution"]["cases"] = [{"expected_stdout": "4\n"}]
        record = qbank_execution.run_question(model, question)
        self.assertEqual(record["status"], "passed")

    def test_linked_chain_runs_through_correct_upstream_state(self):
        model = qbank_schema.normalize_bank(hard_linked_bank())
        baseline = qbank_schema.effective_program(model, "b_counter")
        first = qbank_execution.run_question(model, model["questions"]["q_value"])
        self.assertEqual(first["status"], "passed")
        chain_code, _ = qbank_schema.effective_program(model, "b_counter", {
            "base_block_id": "b_counter", "reset": False,
            "operations": [{"op": "append", "text": "print(c.advance())\nprint(c.value)"}]})
        allowed, _ = qbank_execution.screen_code(chain_code)
        self.assertTrue(allowed)
        observation = qbank_execution.run_python(chain_code)
        self.assertEqual(observation["stdout"], "7\n7\n")
        del baseline

    def test_stale_passed_records_are_flagged(self):
        model = qbank_schema.normalize_bank(audited_counter_bank())
        question = model["questions"]["q_value"]
        question["execution"] = {"status": "passed", "execution_verified": True,
                                 "program_hash": "0" * 64, "cases": [], "reason": None}
        self.assertEqual(qbank_execution.stale_execution_records(model), ["q_value"])
        code_text, _ = qbank_schema.effective_program(model, "b_counter", question["variant"])
        question["execution"]["program_hash"] = qbank_schema.code_hash(code_text)
        self.assertEqual(qbank_execution.stale_execution_records(model), [])

    def test_runs_are_deterministic_and_leave_no_artifacts(self):
        model = block_model(["print(sorted({3, 1, 2}))"])
        first = self.run_question(model)
        second = self.run_question(copy.deepcopy(model))
        self.assertEqual(first["cases"][0]["observation"]["stdout"],
                         second["cases"][0]["observation"]["stdout"])
        remaining = list(Path(tempfile_root()).glob("qbank_exec_*"))
        self.assertEqual(remaining, [], "Execution scratch directories must be cleaned")


def tempfile_root():
    import tempfile
    return tempfile.gettempdir()


if __name__ == "__main__":
    unittest.main()
