"""Observable game rules and localhost API behavior using synthetic audited data."""

import copy
import json
import random
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from exam_game import ConflictError, ExamGame
from question_bank_data import validate_game_bank
from serve_exam_game import GameServer


def sample_bank():
    return json.loads((ROOT / "evals" / "files" / "sample_game.json").read_text(encoding="utf-8"))


class Clock:
    def __init__(self):
        self.now = 1000

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class GameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "session.json"
        self.bank = sample_bank()
        self.clock = Clock()
        self.game = ExamGame(self.bank, self.path, self.clock, random.Random(12))

    def act(self, action, **payload):
        return self.game.action({"action": action, "revision": self.game.view()["revision"], "payload": payload})

    def start(self, names=None):
        names = names or ["Alice", "Bob"]
        return self.act("start", mode="solo" if len(names) == 1 else "group", names=names, duration=10)

    def solve(self, correctness):
        view = self.game.view()
        _, question = self.game.catalog[view["question"]["id"]]
        for pid in view["answers"]:
            right = correctness[pid]
            if view["question"]["type"] == "essays":
                answer = "The response to be marked."
            elif right:
                answer = question["correct"]
            elif view["question"]["type"] == "mcqs":
                answer = next(letter for letter in "ABCD" if letter != question["correct"])
            else:
                answer = "False" if question["correct"] == "True" else "True"
            self.act("answer", player_id=pid, answer=answer)
        self.act("lock")
        if view["question"]["type"] == "essays":
            for pid in view["answers"]:
                self.act("mark_essay", player_id=pid, correct=correctness[pid])
        return self.game.view()

    def originals(self, correctness):
        for _ in range(3):
            self.solve(correctness)
            self.act("next")

    def test_setup_validates_roster_and_integer_time_without_partial_changes(self):
        for payload in [
            {"mode": "solo", "names": ["A", "B"], "duration": 10},
            {"mode": "group", "names": ["A"], "duration": 10},
            {"mode": "group", "names": ["A", " a "], "duration": 10},
            {"mode": "solo", "names": [" "], "duration": 10},
            {"mode": "solo", "names": ["A"], "duration": True},
            {"mode": "solo", "names": ["A"], "duration": 1.5},
            {"mode": "solo", "names": ["A"], "duration": 0},
        ]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.act("start", **payload)
            self.assertEqual(self.game.view()["phase"], "setup")
            self.assertEqual(self.game.view()["revision"], 0)

    def test_answer_key_hidden_until_every_response_is_locked(self):
        initial = self.start()
        self.assertNotIn("correct", initial["question"])
        self.assertNotIn("explanation", initial["question"])
        self.assertNotIn("sources", initial["question"])
        with self.assertRaises(ValueError):
            self.act("lock")
        _, q = self.game.catalog[initial["question"]["id"]]
        self.act("answer", player_id="p1", answer=q["correct"])
        with self.assertRaises(ValueError):
            self.act("lock")
        self.assertEqual(self.game.view()["players"][0]["score"], 0)
        self.act("answer", player_id="p2", answer="A" if q["correct"] != "A" else "D")
        view = self.act("lock")
        self.assertEqual(view["question"]["correct"], q["correct"])
        self.assertEqual(view["players"][0]["score"], 1)
        with self.assertRaises(ValueError):
            self.act("next_unknown")
        with self.assertRaises(ValueError):
            self.act("lock")

    def test_pause_preserves_time_and_allows_answers_and_refresh(self):
        self.start()
        self.clock.advance(3)
        paused = self.act("pause")
        self.assertEqual(paused["timer"]["remaining"], 7)
        self.clock.advance(100)
        self.act("answer", player_id="p1", answer="A")
        self.assertEqual(self.game.view()["timer"]["remaining"], 7)
        resumed = self.act("resume")
        self.assertEqual(resumed["timer"]["remaining"], 7)
        self.clock.advance(2)
        self.assertEqual(self.game.view()["timer"]["remaining"], 5)

    def test_review_requires_pause_and_only_completed_question_indexes(self):
        self.start()
        with self.assertRaises(ValueError):
            self.act("review", index=0)
        self.act("pause")
        for index in (0, -1, True, "0"):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.act("review", index=index)
        self.assertNotIn("correct", self.game.view()["question"])
        self.act("resume")
        self.solve({"p1": True, "p2": False})
        with self.assertRaises(ValueError):
            self.act("review", index=0)
        self.act("next")
        self.act("pause")
        for index in (1, -1, True):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.act("review", index=index)

    def test_paused_review_preserves_current_answers_time_scores_and_targets(self):
        self.start()
        original = self.game.view()["question"]["id"]
        self.solve({"p1": True, "p2": False})
        self.act("next")
        active = self.game.view()["question"]["id"]
        self.act("answer", player_id="p1", answer="True")
        self.clock.advance(3)
        paused = self.act("pause")
        history = copy.deepcopy(self.game.state["history"])
        reviewed = self.act("review", index=0)
        self.assertEqual(reviewed["question"]["id"], original)
        self.assertEqual(reviewed["active_question_id"], active)
        self.assertEqual(reviewed["review"], {"index": 0, "count": 1})
        self.assertIn("correct", reviewed["question"])
        self.assertEqual(reviewed["players"], paused["players"])
        self.assertEqual(reviewed["targets"], paused["targets"])
        self.assertFalse(reviewed["answers"]["p2"]["correct"])
        self.clock.advance(100)
        self.assertEqual(self.game.view()["timer"]["remaining"], 7)
        for action, payload in [("answer", {"player_id": "p1", "answer": "A"}), ("lock", {}), ("next", {})]:
            with self.subTest(action=action), self.assertRaises(ValueError):
                self.act(action, **payload)
        returned = self.act("review", index=None)
        self.assertEqual(returned["question"]["id"], active)
        self.assertNotIn("correct", returned["question"])
        self.assertEqual(returned["answers"]["p1"]["answer"], "True")
        self.assertEqual(self.game.state["history"], history)
        self.assertEqual(returned["timer"]["remaining"], 7)
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertIsNone(saved["review_index"])

    def test_resuming_from_review_returns_to_active_question(self):
        self.start(["Alice"])
        self.solve({"p1": True})
        self.act("next")
        active = self.game.view()["question"]["id"]
        self.act("pause")
        self.act("review", index=0)
        resumed = self.act("resume")
        self.assertFalse(resumed["timer"]["paused"])
        self.assertIsNone(resumed["review"]["index"])
        self.assertEqual(resumed["question"]["id"], active)
        self.assertNotIn("correct", resumed["question"])

    def test_review_in_retry_phase_restores_historical_player_and_attempt(self):
        self.start(["Alice"])
        self.originals({"p1": False})
        self.act("start_retries")
        self.solve({"p1": False})
        retry = copy.deepcopy(self.game.view()["retry"])
        prior = self.game.view()["question"]["id"]
        self.act("next")
        self.act("pause")
        reviewed = self.act("review", index=3)
        self.assertEqual(reviewed["stage"], "retries")
        self.assertEqual(reviewed["retry"], retry)
        self.assertEqual(reviewed["question"]["id"], prior)
        original = self.act("review", index=0)
        self.assertEqual(original["stage"], "originals")
        self.assertNotIn("retry", original)
        returned = self.act("review", index=None)
        self.assertEqual(returned["stage"], "retries")
        self.assertEqual(returned["retry"]["attempt"], 2)

    def test_expiry_accepts_late_host_entry_and_blanks_become_timeouts(self):
        self.start()
        self.clock.advance(11)
        self.assertEqual(self.game.view()["phase"], "question")
        self.assertNotIn("correct", self.game.view()["question"])
        self.act("answer", player_id="p1", answer="B")
        view = self.act("lock")
        self.assertTrue(view["answers"]["p2"]["timed_out"])
        self.assertFalse(view["answers"]["p2"]["correct"])
        self.assertEqual(len(view["targets"]["p2"]), 1)
        self.assertEqual(view["players"][1]["score"], 0)

    def test_essays_require_host_marking_before_feedback(self):
        self.start()
        for _ in range(2):
            self.solve({"p1": True, "p2": True})
            self.act("next")
        self.act("answer", player_id="p1", answer="Four equal sides")
        self.act("answer", player_id="p2", answer="Three sides")
        locked = self.act("lock")
        self.assertEqual(locked["phase"], "essay_marking")
        self.assertIn("model_answer", locked["question"])
        with self.assertRaises(ValueError):
            self.act("next")
        self.act("mark_essay", player_id="p1", correct=True)
        with self.assertRaises(ValueError):
            self.act("mark_essay", player_id="p1", correct=True)
        view = self.act("mark_essay", player_id="p2", correct=False)
        self.assertEqual(view["phase"], "feedback")
        self.assertEqual([p["score"] for p in view["players"]], [3, 2])

    def test_all_timeout_essay_skips_manual_marking(self):
        self.start(["Alice"])
        for _ in range(2):
            self.solve({"p1": True})
            self.act("next")
        self.clock.advance(11)
        self.assertEqual(self.act("lock")["phase"], "feedback")

    def test_all_correct_finishes_without_retries_and_shares_winners(self):
        self.start()
        self.originals({"p1": True, "p2": True})
        view = self.game.view()
        self.assertEqual(view["phase"], "complete")
        self.assertEqual(view["winners"], ["p1", "p2"])
        self.assertEqual([p["score"] for p in view["players"]], [3, 3])
        self.assertFalse(any(view["targets"].values()))

    def test_retries_are_deferred_targeted_and_do_not_change_winner(self):
        self.start()
        with self.assertRaises(ValueError):
            self.act("start_retries")
        self.originals({"p1": True, "p2": False})
        view = self.game.view()
        self.assertEqual(view["phase"], "original_results")
        self.assertEqual(view["winners"], ["p1"])
        self.assertEqual(len(view["targets"]["p2"]), 3)
        retry = self.act("start_retries")
        self.assertEqual(list(retry["answers"]), ["p2"])
        self.assertNotIn(retry["question"]["id"], self.game.state["original_order"])
        for _ in range(3):
            self.solve({"p2": True})
            self.act("next")
        view = self.game.view()
        self.assertEqual(view["phase"], "complete")
        self.assertEqual(view["winners"], ["p1"])
        self.assertEqual([p["score"] for p in view["players"]], [3, 0])
        self.assertTrue(all(t["status"] == "cleared" and t["attempts"] == 1 for t in view["targets"]["p2"]))

    def test_three_retry_timeouts_exhaust_target_then_move_to_other_players(self):
        self.start()
        self.originals({"p1": False, "p2": False})
        self.assertEqual(self.game.view()["winners"], ["p1", "p2"])
        first = self.act("start_retries")
        first_pool = []
        for i in range(3):
            view = self.game.view()
            self.assertEqual(view["retry"]["attempt"], i + 1)
            first_pool.append(view["question"]["id"])
            self.clock.advance(11)
            self.act("lock")
            self.act("next")
        self.assertEqual(len(set(first_pool)), 3)
        self.assertEqual(self.game.view()["targets"]["p1"][0]["status"], "unresolved")
        for _ in range(2):
            self.solve({"p1": True})
            self.act("next")
        second = self.game.view()
        self.assertEqual(second["retry"]["player_id"], "p2")
        self.assertEqual(second["question"]["id"], first["question"]["id"])

    def test_success_on_second_or_third_retry_clears_target(self):
        for success_at in (2, 3):
            with self.subTest(success_at=success_at):
                self.act("restart", confirmed=True)
                self.start(["Alice"])
                self.originals({"p1": False})
                self.act("start_retries")
                for attempt in range(1, success_at + 1):
                    self.solve({"p1": attempt == success_at})
                    self.act("next")
                progress = self.game.view()["targets"]["p1"][0]
                self.assertEqual(progress, {"id": "triangle-sides", "label": self.bank["learning_targets"]["triangle-sides"]["label"],
                                            "status": "cleared", "attempts": success_at})

    def test_matching_original_targets_deduplicate_and_correct_does_not_erase_miss(self):
        extra = copy.deepcopy(self.bank["mcqs"][0])
        extra.update(id="m-extra", question="How many edges form a triangular boundary?")
        self.bank["mcqs"].append(extra)
        self.bank["counts"]["mcqs"] = 2
        self.bank["difficulty_counts"]["mcqs"]["easy"] = 2
        self.game = ExamGame(self.bank, self.path, self.clock, random.Random(1))
        self.start(["Alice"])
        self.solve({"p1": False})
        self.act("next")
        self.solve({"p1": True})
        self.assertEqual(len(self.game.view()["targets"]["p1"]), 1)
        self.assertEqual(self.game.view()["targets"]["p1"][0]["attempts"], 0)

    def test_saved_state_and_fresh_launch(self):
        self.start()
        self.act("answer", player_id="p1", answer="A")
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(saved["answers"]["p1"]["answer"], "A")
        self.assertEqual(self.game.view()["phase"], "question")
        game = ExamGame(self.bank, self.path)
        self.assertEqual(game.view()["phase"], "setup")
        self.assertEqual(json.loads(self.path.read_text())["history"], [])

    def test_stale_requests_restart_confirmation_and_atomic_failure(self):
        self.start()
        old = self.game.view()["revision"]
        self.act("pause")
        with self.assertRaises(ConflictError):
            self.game.action({"action": "resume", "revision": old})
        with self.assertRaises(ValueError):
            self.act("restart")
        before = self.game.view()
        persist = self.game._persist
        self.game._persist = lambda: (_ for _ in ()).throw(OSError("Disk full"))
        with self.assertRaises(OSError):
            self.act("resume")
        self.assertEqual(self.game.view(), before)
        self.game._persist = persist
        self.assertEqual(self.act("restart", confirmed=True)["phase"], "setup")

    def test_shuffling_preserves_options_and_explanations_and_input(self):
        bank = copy.deepcopy(self.bank)
        view = self.start()
        q = view["question"]
        self.assertEqual([q["type"]], ["mcqs"])
        self.assertCountEqual([o["id"] for o in q["options"]], list("ABCD"))
        self.solve({"p1": True, "p2": True})
        shown = self.game.view()["question"]
        correct_option = next(o for o in shown["options"] if o["id"] == shown["correct"])
        self.assertEqual(correct_option["text"], "Three")
        self.assertIn("Three", shown["option_explanations"][shown["correct"]])
        self.assertEqual(self.bank, bank)


class ValidationTests(unittest.TestCase):
    def test_complete_fixture(self):
        validate_game_bank(sample_bank())

    def test_malformed_json_shapes_report_validation_errors(self):
        cases = [("source_mode", []), ("mcqs", {}), ("learning_targets", []),
                 ("difficulty_counts", {"mcqs": [], "true_false": {}, "essays": {}})]
        for field, value in cases:
            with self.subTest(field=field):
                bank = sample_bank()
                bank[field] = value
                with self.assertRaises(ValueError):
                    validate_game_bank(bank)
        for field in ("correct", "difficulty"):
            bank = sample_bank()
            bank["mcqs"][0][field] = []
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_game_bank(bank)

    def test_reject_invalid_html_contract(self):
        for scenario in ("version", "id", "target", "count", "duplicate", "type", "difficulty", "feedback", "audit", "source", "unused", "matching"):
            with self.subTest(scenario=scenario):
                bank = sample_bank()
                target = bank["learning_targets"]["triangle-sides"]
                q = target["retries"][0]
                if scenario == "version": bank["game_version"] = True
                elif scenario == "id": q["id"] = bank["mcqs"][0]["id"]
                elif scenario == "target": bank["mcqs"][0]["target_id"] = "missing"
                elif scenario == "count": target["retries"].pop()
                elif scenario == "duplicate": q["question"] = bank["mcqs"][0]["question"].upper()
                elif scenario == "type": target["question_type"] = "essays"
                elif scenario == "difficulty": q["difficulty"] = "medium"
                elif scenario == "feedback": q["option_explanations"]["A"] = ""
                elif scenario == "audit": q["answer_verified"] = False
                elif scenario == "source": q["sources"][0] = {"kind": "web", "url": "https://example.org", "title": "Web", "evidence": "Outside"}
                elif scenario == "unused": bank["mcqs"] = []; bank["counts"]["mcqs"] = 0; bank["difficulty_counts"]["mcqs"]["easy"] = 0
                elif scenario == "matching": bank["learning_targets"]["copy"] = copy.deepcopy(target)
                with self.assertRaises(ValueError):
                    validate_game_bank(bank)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.exam = Path(self.tmp.name) / "exam.json"
        self.exam.write_text(json.dumps(sample_bank()), encoding="utf-8")
        self.server = GameServer(self.exam)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, path, body=None, headers=None):
        headers = headers or {}
        if body is not None:
            body = json.dumps(body).encode()
            headers = {"Content-Type": "application/json", "X-CSRF-Token": self.server.token, **headers}
        request = Request(self.server.origin + path, data=body, headers=headers)
        try:
            response = urlopen(request, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers

    def test_static_and_state_do_not_expose_exam_or_future_answers(self):
        status, data, headers = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"app.js", data)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.request("/exam.json")[0], 404)
        self.assertEqual(self.request("/session.json")[0], 404)
        self.assertEqual(self.request("/../evals/files/sample_game.json")[0], 404)
        status, data, _ = self.request("/api/state")
        self.assertEqual(json.loads(data)["phase"], "setup")
        self.assertNotIn(b"learning_targets", data)
        self.assertNotIn(b"option_explanations", data)

    def test_local_api_rejects_other_origins_and_missing_tokens(self):
        action = {"action": "start", "revision": 0, "payload": {"mode": "solo", "names": ["A"], "duration": 1}}
        self.assertEqual(self.request("/api/action", action, {"X-CSRF-Token": ""})[0], 403)
        self.assertEqual(self.request("/api/action", action, {"Origin": "https://example.org"})[0], 403)
        self.assertEqual(self.request("/api/state", headers={"Host": "example.org"})[0], 403)
        status, data, _ = self.request("/api/action", action)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["phase"], "question")
        self.assertNotIn(b"option_explanations", data)
        self.assertEqual(self.request("/api/action", action)[0], 409)
        refreshed = json.loads(self.request("/api/state")[1])
        self.assertEqual(refreshed["phase"], "question")
        self.assertEqual(refreshed["revision"], 1)

    def test_concurrent_mutations_only_accept_one_revision(self):
        request = {"action": "start", "revision": 0, "payload": {"mode": "solo", "names": ["A"], "duration": 10}}
        statuses = []
        workers = [threading.Thread(target=lambda: statuses.append(self.request("/api/action", request)[0])) for _ in range(2)]
        for thread in workers: thread.start()
        for thread in workers: thread.join(5)
        self.assertCountEqual(statuses, [200, 409])

    def test_directory_cannot_be_shared_by_two_servers(self):
        with self.assertRaises(ValueError):
            GameServer(self.exam)
        self.assertEqual(self.server.game.view()["phase"], "setup")

    def test_bad_bank_does_not_reset_existing_session(self):
        session = self.exam.with_name("session.json")
        before = session.read_bytes()
        self.exam.write_text('{"title":"bad"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            GameServer(self.exam)
        self.assertEqual(session.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
