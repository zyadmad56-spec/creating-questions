"""Build the synthetic semantic-evaluation bank with REAL execution records.

Public synthetic fixtures only. The builder runs every executable variant
through the local runner and embeds the actual observations, then writes the
known-bad review cases that a reviewer must identify and exclude/repair.
"""

import json
import sys
from pathlib import Path

SEMANTIC_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SEMANTIC_DIR.parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import qbank_execution  # noqa: E402
import qbank_schema  # noqa: E402

PREMISE = ("Synthetic teaching premises (public fixture): Python constructors initialize "
           "instance attributes; methods access self; return passes a value without "
           "printing it; print writes its arguments; each independent question starts "
           "from the original code; range(1, n + 1) includes integers 1 through n; % "
           "gives the remainder; // is integer division for positive operands. The API "
           "premises teach isna(), sum(), dropna(), head(), and describe().")


def sources():
    return [{"kind": "document", "document": "Synthetic teaching premises",
             "locator": "CODE-SAMPLES.md, Synthetic teaching premises",
             "evidence": PREMISE}]


COUNTER_LINES = [
    {"id": "L1", "text": "class Counter:"},
    {"id": "L2", "text": "    def __init__(self, value):"},
    {"id": "L3", "text": "        self.value = value"},
    {"id": "L4", "text": "    def advance(self):"},
    {"id": "L5", "text": "        self.value += 3"},
    {"id": "L6", "text": "        return self.value"},
    {"id": "L7", "text": "c = Counter(4)"},
]

SCORE_LINES = [
    {"id": "L1", "text": "def score(n):"},
    {"id": "L2", "text": "    total = 0"},
    {"id": "L3", "text": "    for i in range(1, n + 1):"},
    {"id": "L4", "text": "        if i % 2 == 0:"},
    {"id": "L5", "text": "            total += i * i"},
    {"id": "L6", "text": "        else:"},
    {"id": "L7", "text": "            total -= 1"},
    {"id": "L8", "text": "    return total"},
]

COMPLETION_LINES = [
    {"id": "L1", "text": "class CourseRecord:"},
    {"id": "L2", "text": "    def __init__(self, hours):"},
    {"id": "L3", "text": "        self.hours = hours"},
    {"id": "L4", "text": ""},
    {"id": "L5", "text": "    def read_hours(self):"},
    {"id": "L6", "text": "        return ______"},
]

BUGFIX_LINES = [
    {"id": "L1", "text": "class CourseRecord:"},
    {"id": "L2", "text": "    def __init__(self, hours):"},
    {"id": "L3", "text": "        self.hours = hours"},
    {"id": "L4", "text": ""},
    {"id": "L5", "text": "    def read_hours(self):"},
    {"id": "L6", "text": "        return self.hours"},
    {"id": "L7", "text": ""},
    {"id": "L8", "text": "record = CourseRecord(3)"},
    {"id": "L9", "text": "print(record.read_hours)"},
]


def mcq(question_id, text, options, correct_id, difficulty, extra=None):
    record = {"id": question_id, "question": text, "difficulty": difficulty,
              "options": [{"id": option_id, "text": option_text}
                          for option_id, option_text in options],
              "correct_option_id": correct_id,
              "explanation": "See the synthetic premises and the executed record.",
              "answer_verified": True, "sources": sources(),
              "execution": {"status": "not_run", "execution_verified": False,
                            "reason": "Filled by the builder.", "cases": []}}
    record.update(extra or {})
    return record


def build_bank():
    execution_cases = {
        "q_value": [{"expected_stdout": "4\n"}],
        "q_return": [{"expected_stdout": ""}],
        "q_advance": [{"expected_stdout": "7\n"}],
        "q_score_a": [{"expected_stdout": "18\n"}],
        "q_score_b": [{"expected_stdout": "53\n"}],
        "q_score_final": [{"expected_stdout": "71 2\n"}],
    }
    variants = {
        "q_value": {"base_block_id": "b_counter", "reset": True,
                    "operations": [{"op": "append", "text": "print(c.value)"}]},
        "q_return": {"base_block_id": "b_counter", "reset": True,
                     "operations": [{"op": "append", "text": "c.advance()"}]},
        "q_advance": {"base_block_id": "b_counter", "reset": True,
                      "operations": [{"op": "append", "text": "print(c.advance())"}]},
        "q_score_a": {"base_block_id": "b_score", "reset": True,
                      "operations": [{"op": "append", "text": "print(score(4))"}]},
        "q_score_b": {"base_block_id": "b_score", "reset": True,
                      "operations": [{"op": "append", "text": "print(score(18 // 3))"}]},
        "q_score_final": {"base_block_id": "b_score", "reset": True,
                          "operations": [{"op": "append", "text":
                                          "print(18 + 53, score(53 % 5))"}]},
    }
    mcqs = [
        mcq("q_value", "Starting from Code Block {{block:b_counter}}, what is printed if "
             "`print(c.value)` is appended?",
             [("o_v4", "4"), ("o_v7", "7"), ("o_vnone", "No output"),
              ("o_verr", "AttributeError")], "o_v4", "easy",
             {"code_block_id": "b_counter", "variant": variants["q_value"],
              "explanation": "The constructor stores 4; nothing has advanced it."}),
        mcq("q_return", "Starting from Code Block {{block:b_counter}}, what is printed if "
             "only `c.advance()` is appended?",
             [("o_r4", "4"), ("o_r7", "7"), ("o_rnone", "None"),
              ("o_rsilent", "No output")], "o_rsilent", "easy",
             {"code_block_id": "b_counter", "variant": variants["q_return"],
              "explanation": "advance returns 7 but the appended statement does not print it."}),
        mcq("q_advance", "Starting from Code Block {{block:b_counter}}, what is printed if "
             "`print(c.advance())` is appended?",
             [("o_a4", "4"), ("o_a7", "7"), ("o_anone", "No output"),
              ("o_aerr", "TypeError")], "o_a7", "easy",
             {"code_block_id": "b_counter", "variant": variants["q_advance"],
              "explanation": "advance adds 3 to 4 and the print displays the returned 7."}),
        mcq("q_isna", "Which pandas expression counts missing cells separately for each "
             "column of the DataFrame `data`, using the taught missing-value check?",
             [("o_i1", "`data.describe()`"), ("o_i2", "`data.head()`"),
              ("o_i3", "`data.isna().sum()`"), ("o_i4", "`data.dropna()`")],
             "o_i3", "easy",
             {"explanation": "isna flags missing cells and sum counts the True flags "
                             "per column; describe summarizes, head previews, dropna removes rows.",
              "execution": {"status": "not_applicable", "execution_verified": False,
                            "reason": "Conceptual API question with no executable "
                                      "variant; verified through the source premises.",
                            "cases": []}}),
        mcq("q_score_a", "Using Code Block {{block:b_score}}, what is `a` after "
             "`a = score(4)`?",
             [("o_s18", "18"), ("o_s20", "20"), ("o_s16", "16"), ("o_s4", "4")],
             "o_s18", "hard",
             {"code_block_id": "b_score", "variant": variants["q_score_a"],
              "explanation": "score(4) = -1 + 4 - 1 + 16 = 18."}),
        mcq("q_score_b", "Using the correct value of `a` from the previous question, what "
             "is `b` after `b = score(a // 3)`?",
             [("o_t20", "20"), ("o_t53", "53"), ("o_t18", "18"), ("o_t36", "36")],
             "o_t53", "hard",
             {"code_block_id": "b_score", "variant": variants["q_score_b"],
              "depends_on": ["q_score_a"],
              "explanation": "a = 18, so score(6) = 4 + 16 + 36 - 2 = 53... computed as "
                             "-1 + 4 - 1 + 16 - 1 + 36 = 53.", }),
    ]
    mcqs[5]["explanation"] = "a = 18 and 18 // 3 = 6; score(6) = 53."
    mcqs.append(mcq(
        "q_score_final", "Using the correct values of `a` and `b`, what does "
        "`print(a + b, score(b % 5))` display?",
        [("o_u1", "71 2"), ("o_u2", "71 3"), ("o_u3", "53 2"), ("o_u4", "18 53")],
        "o_u1", "hard",
        {"code_block_id": "b_score", "variant": variants["q_score_final"],
         "depends_on": ["q_score_a", "q_score_b"],
         "explanation": "a + b = 71 and score(53 % 5) = score(3) = 2."}))

    true_false = [
        {"id": "q_tf_advance", "statement": "In the Counter program, calling "
         "`c.advance()` once changes `c.value` from 4 to 7.",
         "correct": "True", "difficulty": "easy",
         "explanation": "advance adds 3 to the stored value.",
         "answer_verified": True, "sources": sources(),
         "execution": {"status": "not_applicable", "execution_verified": False,
                       "reason": "Conceptual premise covered by the executed variants.",
                       "cases": []}},
        {"id": "q_tf_print", "statement": "According to the synthetic premises, a method "
         "that returns a value also prints it.",
         "correct": "False", "difficulty": "medium",
         "correction": "return passes a value back without printing it; print writes to "
                       "the terminal.",
         "explanation": "The executed q_return variant confirms no output when only "
                        "c.advance() is appended.",
         "answer_verified": True, "sources": sources(),
         "execution": {"status": "not_applicable", "execution_verified": False,
                       "reason": "Verified through the executed q_return variant.",
                       "cases": []}},
    ]

    essays = [
        {"id": "q_essay_scenario", "question": "A course record stores a course name and "
         "credit hours. Write class `CourseRecord` with a constructor accepting both "
         "values, method `get_hours()` returning its current hours, and method "
         "`set_hours(hours)` replacing them. Create one record and demonstrate reading "
         "the hours before and after one update.",
         "essay_style": "scenario", "difficulty": "easy",
         "model_answer": ["Constructor stores both values.", "get_hours returns the "
                          "current hours.", "set_hours replaces the hours.",
                          "A correct demonstration runs."],
         "reference_solution": "class CourseRecord:\n    def __init__(self, name, hours):\n"
          "        self.name = name\n        self.hours = hours\n\n    def get_hours(self):\n"
          "        return self.hours\n\n    def set_hours(self, hours):\n"
          "        self.hours = hours\n\nrecord = CourseRecord(\"AI\", 3)\n"
          "print(record.get_hours())\nrecord.set_hours(5)\nprint(record.get_hours())",
         "test_cases": [{"description": "initial 3 then update to 5", "expected": "3\n5"},
                        {"description": "initial 2 then update to 2", "expected": "2\n2"}],
         "explanation": "State, return, mutation, and demonstration.",
         "answer_verified": True, "sources": sources(),
         "execution": {"status": "not_run", "execution_verified": False,
                       "reason": "Reference solution executed by the builder.",
                       "cases": [{"expected_stdout": "3\n5\n"}]}},
        {"id": "q_essay_completion", "question": "Complete the missing expression in Code "
         "Block {{block:b_completion}} so `read_hours()` returns the hours stored in "
         "this instance, and explain the instance reference.",
         "essay_style": "completion", "difficulty": "easy",
         "code_block_id": "b_completion",
         "model_answer": ["`self.hours` is the missing expression.",
                          "self refers to the instance whose method was called."],
         "reference_solution": "self.hours",
         "test_cases": [{"description": "CourseRecord(3).read_hours()", "expected": "3"},
                        {"description": "CourseRecord(0).read_hours()", "expected": "0"}],
         "explanation": "The instance reference is required to reach the attribute.",
         "answer_verified": True, "sources": sources(),
         "execution": {"status": "not_run", "execution_verified": False,
                       "reason": "Completed variant executed by the builder.",
                       "cases": []}},
        {"id": "q_essay_bugfix", "question": "The final line of Code Block "
         "{{block:b_bugfix}} is intended to print the value returned by `read_hours()`. "
         "Correct that line and explain the mistake.",
         "essay_style": "bug_fix", "difficulty": "medium",
         "code_block_id": "b_bugfix",
         "model_answer": ["The line must call the method: `print(record.read_hours())`.",
                          "The original refers to the method object instead of calling it."],
         "reference_solution": "print(record.read_hours())",
         "test_cases": [{"description": "fixed line with hours=3", "expected": "3"},
                        {"description": "fixed line with hours=0", "expected": "0"}],
         "explanation": "Calling the method evaluates it; the bare name is the bound method.",
         "answer_verified": True, "sources": sources(),
         "execution": {"status": "not_run", "execution_verified": False,
                       "reason": "Repaired variant executed by the builder.",
                       "cases": []}},
        {"id": "q_essay_trace", "question": "Starting from Code Block "
         "{{block:b_counter_trace}}, exactly these three lines are appended in order:\n"
         "`x = c.advance()`\n`y = c.advance()`\n`print(x, y, c.value)`\n"
         "Give the printed output and explain the state after each method call.",
         "essay_style": "trace_explain", "difficulty": "hard",
         "code_block_id": "b_counter_trace",
         "variant": {"base_block_id": "b_counter_trace", "reset": True,
                     "operations": [{"op": "append", "text": "x = c.advance()"},
                                    {"op": "append", "text": "y = c.advance()"},
                                    {"op": "append", "text": "print(x, y, c.value)"}]},
         "model_answer": ["First call changes 4 to 7 and assigns x = 7.",
                          "Second call changes 7 to 10 and assigns y = 10.",
                          "Final state is 10; output is `7 10 10`."],
         "explanation": "State advances across the two calls within this one question.",
         "answer_verified": True, "sources": sources(),
         "execution": {"status": "not_run", "execution_verified": False,
                       "reason": "Exact appended variant executed by the builder.",
                       "cases": [{"expected_stdout": "7 10 10\n"}]}},
    ]

    return {
        "schema_version": 2,
        "title": "Synthetic Semantic Evaluation Bank",
        "language": "en",
        "source_mode": "source_only",
        "counts": {"mcqs": 7, "true_false": 2, "essays": 4},
        "difficulty_counts": {
            "mcqs": {"easy": 4, "medium": 0, "hard": 3},
            "true_false": {"easy": 1, "medium": 1, "hard": 0},
            "essays": {"easy": 2, "medium": 1, "hard": 1}},
        "include_answer_key": True,
        "programming": {"allow_hard_dependencies": True,
                        "content_mode": "mixed", "languages": ["python"]},
        "deliverables": ["docx"],
        "format": {"profile_id": "builtin-card", "variant": "monokai"},
        "code_blocks": [
            {"id": "b_counter", "language": "python", "version_hint": "3.x",
             "origin": "authored_from_source", "review_status": "recovered",
             "lines": COUNTER_LINES, "sources": sources()},
            {"id": "b_counter_trace", "language": "python", "version_hint": "3.x",
             "origin": "authored_from_source", "review_status": "recovered",
             "lines": COUNTER_LINES, "sources": sources()},
            {"id": "b_score", "language": "python", "version_hint": "3.x",
             "origin": "authored_from_source", "review_status": "recovered",
             "lines": SCORE_LINES, "sources": sources()},
            {"id": "b_completion", "language": "python", "version_hint": "3.x",
             "origin": "authored_from_source", "review_status": "intentionally_incomplete",
             "lines": COMPLETION_LINES, "sources": sources()},
            {"id": "b_bugfix", "language": "python", "version_hint": "3.x",
             "origin": "authored_from_source", "review_status": "intentionally_invalid",
             "lines": BUGFIX_LINES, "sources": sources()},
        ],
        "groups": [
            {"id": "g_counter", "type": "mcqs", "difficulty": "easy",
             "code_block_id": "b_counter", "dependency_mode": "independent",
             "question_ids": ["q_value", "q_return", "q_advance"]},
            {"id": "g_score", "type": "mcqs", "difficulty": "hard",
             "code_block_id": "b_score", "dependency_mode": "linked",
             "question_ids": ["q_score_a", "q_score_b", "q_score_final"],
             "dependencies": [
                 {"question_id": "q_score_b", "depends_on": ["q_score_a"]},
                 {"question_id": "q_score_final", "depends_on": ["q_score_a", "q_score_b"]}]},
        ],
        "mcqs": mcqs,
        "true_false": true_false,
        "essays": essays,
    }


REVIEW_CASES = [
    {"case_id": "bad_two_valid_options",
     "draft": {"question": "Which pandas expression removes missing values?",
               "options": ["data.dropna()", "data.dropna(axis=0)", "data.isna().sum()",
                           "data.describe()"], "key": "A"},
     "finding": "Both A and B are correct as stated (axis=0 is the default), so the item "
                "has two defensible keys.",
     "disposition": "Excluded; repaired as q_isna with a task constrained to counting "
                    "missing cells per column, giving exactly one defensible answer."},
    {"case_id": "bad_printed_key_contradiction",
     "draft": {"question": "What is the exact output printed to the terminal after "
               "executing line 9 of the Demo listing?", "options": ["30", "10",
               "AttributeError", "No output"], "printed_key": "B"},
     "finding": "Line 9 is `obj = Demo()` — a bare assignment that prints nothing. The "
                "printed key (10) contradicts the shown code; this is the supplied "
                "mockup's content defect.",
     "disposition": "Excluded; the corrected reference asks about the print statement "
                    "through stable line IDs (see q_essay_trace and q_value)."},
    {"case_id": "bad_inherited_constructor",
     "draft": {"question": "Which constructor runs for class Child(Parent) with no "
               "__init__ of its own?", "options": ["Child's own", "Parent's inherited "
               "__init__", "object.__init__ only", "No constructor runs"], "key": "B or C"},
     "finding": "B and C are both defensible without the source stating the MRO rule, "
                "and the synthetic premises do not teach inheritance resolution.",
     "disposition": "Excluded; outside the taught scope in source-only mode."},
    {"case_id": "bad_return_vs_print",
     "draft": {"question": "What does the statement c.advance() produce?",
               "options": ["7", "None", "No output", "AttributeError"], "key": "C"},
     "finding": "Without stating whether the value is printed, assigned, or ignored, "
                "'No output' and 'returns 7 unused' are both defensible readings.",
     "disposition": "Repaired as q_return, which specifies that only c.advance() is "
                    "appended to the block and asks what is printed."},
    {"case_id": "bad_false_line_reference",
     "draft": {"question": "What is printed after executing line 13 of the score listing?"},
     "finding": "The score listing has 8 logical lines; prose line numbers drift from "
                "the rendered document and the cited line does not exist.",
     "disposition": "Excluded; all accepted items reference lines through stable "
                    "{{line:}}/{{block:}} tokens resolved from the manifest."},
]


def fill_execution_records(bank):
    model = qbank_schema.normalize_bank(json.loads(json.dumps(bank)))
    for section in ("mcqs", "true_false", "essays"):
        for question in bank[section]:
            if question["execution"].get("status") == "not_applicable":
                continue
            if question.get("essay_style") == "scenario":
                code_text = question["reference_solution"]
                observation = qbank_execution.run_python(code_text)
                record = {"status": "passed" if observation["stdout"] == "3\n5\n" else "failed",
                          "execution_verified": observation["stdout"] == "3\n5\n",
                          "reason": None, "program_hash": qbank_schema.code_hash(code_text),
                          "cases": [{"description": "reference solution",
                                     "expected_stdout": "3\n5\n", "observed": observation,
                                     "match": observation["stdout"] == "3\n5\n"}],
                          "runtime": qbank_execution.discover_runtime("python")}
            elif question.get("essay_style") == "completion":
                completed = {"base_block_id": "b_completion",
                             "operations": [{"op": "replace", "line_id": "L6",
                                             "text": "        return self.hours"},
                                            {"op": "append", "text": "print(CourseRecord(3).read_hours())\nprint(CourseRecord(0).read_hours())"}]}
                code_text, _ = qbank_schema.effective_program(model, "b_completion", completed)
                observation = qbank_execution.run_python(code_text)
                matched = observation["stdout"] == "3\n0\n"
                record = {"status": "passed" if matched else "failed",
                          "execution_verified": matched, "reason": None,
                          "program_hash": qbank_schema.code_hash(code_text),
                          "cases": [{"description": "completed gap", "expected_stdout": "3\n0\n",
                                     "observed": observation, "match": matched}],
                          "runtime": qbank_execution.discover_runtime("python")}
            elif question.get("essay_style") == "bug_fix":
                repaired = {"base_block_id": "b_bugfix",
                            "operations": [{"op": "replace", "line_id": "L9",
                                            "text": "print(record.read_hours())"}]}
                code_text, _ = qbank_schema.effective_program(model, "b_bugfix", repaired)
                observation = qbank_execution.run_python(code_text)
                matched = observation["stdout"] == "3\n"
                record = {"status": "passed" if matched else "failed",
                          "execution_verified": matched, "reason": None,
                          "program_hash": qbank_schema.code_hash(code_text),
                          "cases": [{"description": "repaired line", "expected_stdout": "3\n",
                                     "observed": observation, "match": matched}],
                          "runtime": qbank_execution.discover_runtime("python")}
            else:
                runtime = qbank_execution.discover_runtime("python")
                record = qbank_execution.run_question(model, question, runtime=runtime)
            record.setdefault("runtime", qbank_execution.discover_runtime("python"))
            question["execution"] = record
    return bank


def main():
    bank = fill_execution_records(build_bank())
    model = qbank_schema.normalize_bank(json.loads(json.dumps(bank)))
    qbank_schema.validate_model(model, final=True)
    (SEMANTIC_DIR / "semantic_bank.json").write_text(
        json.dumps(bank, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (SEMANTIC_DIR / "semantic_review_cases.json").write_text(
        json.dumps(REVIEW_CASES, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = []
    for section in ("mcqs", "true_false", "essays"):
        for question in bank[section]:
            execution = question["execution"]
            summary.append(f"{question['id']}: execution={execution['status']} "
                           f"verified={execution['execution_verified']}")
    print("\n".join(summary))


if __name__ == "__main__":
    main()
