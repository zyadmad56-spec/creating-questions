"""Authoritative local exam state. Browser views never contain unrevealed answers."""

import copy
import json
import os
import random
import threading
import time
from pathlib import Path

from question_bank_data import QUESTION_VALIDATORS, source_label, validate_game_bank


class ConflictError(ValueError):
    """An action was based on an outdated view of the game."""


class ExamGame:
    def __init__(self, bank, state_path, clock=time.monotonic, rng=None):
        validate_game_bank(bank)
        self.bank = copy.deepcopy(bank)
        self.path = Path(state_path)
        self.clock = clock
        self.rng = rng or random.SystemRandom()
        self.mutex = threading.RLock()
        self.catalog = {}
        for section in QUESTION_VALIDATORS:
            for question in self.bank.get(section, []):
                self.catalog[question["id"]] = (section, question)
        for target in self.bank["learning_targets"].values():
            for question in target["retries"]:
                self.catalog[question["id"]] = (target["question_type"], question)
        self._reset(0)
        self._persist()

    def _reset(self, revision):
        order = []
        for section in QUESTION_VALIDATORS:
            ids = [q["id"] for q in self.bank.get(section, [])]
            self.rng.shuffle(ids)
            order.extend(ids)
        option_orders = {}
        for qid, (section, _) in self.catalog.items():
            if section == "mcqs":
                letters = list("ABCD")
                self.rng.shuffle(letters)
                option_orders[qid] = letters
        retry_orders = {}
        for tid, target in self.bank["learning_targets"].items():
            ids = [q["id"] for q in target["retries"]]
            self.rng.shuffle(ids)
            retry_orders[tid] = ids
        self.state = {
            "revision": revision, "phase": "setup", "stage": "originals",
            "players": [], "duration": None, "original_order": order, "index": 0,
            "option_orders": option_orders, "retry_orders": retry_orders,
            "question_id": None, "answers": {}, "history": [], "targets": {},
            "retry_player_index": 0, "retry_target_id": None, "timer": None,
            "review_index": None,
        }

    def _persist(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        try:
            with temporary.open("w", encoding="utf-8") as output:
                json.dump(self.state, output, ensure_ascii=False, indent=2, allow_nan=False)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def _remaining(self):
        timer = self.state["timer"]
        if not timer:
            return 0
        return max(0, timer["remaining"] if timer["paused"] else timer["deadline"] - self.clock())

    def _participants(self):
        if self.state["stage"] == "retries":
            return [self.state["players"][self.state["retry_player_index"]]]
        return self.state["players"]

    def _begin(self, qid, stage):
        self.state.update(phase="question", stage=stage, question_id=qid, review_index=None)
        self.state["answers"] = {p["id"]: {"answer": None, "correct": None, "timed_out": False}
                                 for p in self._participants()}
        duration = self.state["duration"]
        self.state["timer"] = {"remaining": duration, "paused": False, "deadline": self.clock() + duration}

    def _require(self, phase):
        if self.state["phase"] != phase:
            raise ValueError(f"This action requires phase {phase}")

    def _start(self, data):
        self._require("setup")
        mode, names, duration = data.get("mode"), data.get("names"), data.get("duration")
        if not isinstance(mode, str) or mode not in {"solo", "group"}:
            raise ValueError("Choose solo or group")
        if not isinstance(names, list) or not names or any(not isinstance(n, str) or not n.strip() for n in names):
            raise ValueError("Enter a nonempty name for every player")
        names = [n.strip() for n in names]
        if any(len(n) > 80 for n in names) or len({n.casefold() for n in names}) != len(names):
            raise ValueError("Names must be distinct and at most 80 characters")
        if (mode == "solo" and len(names) != 1) or (mode == "group" and len(names) < 2):
            raise ValueError("Solo needs one player; group needs at least two")
        if type(duration) is not int or not 1 <= duration <= 86400:
            raise ValueError("Question duration must be an integer from 1 to 86400 seconds")
        self.state["mode"] = mode
        self.state["duration"] = duration
        self.state["players"] = [{"id": f"p{i + 1}", "name": n, "score": 0} for i, n in enumerate(names)]
        self.state["targets"] = {p["id"]: {} for p in self.state["players"]}
        self._begin(self.state["original_order"][0], "originals")

    def _answer(self, data):
        self._require("question")
        if self.state["review_index"] is not None:
            raise ValueError("Return to the current question before entering an answer")
        pid, answer = data.get("player_id"), data.get("answer")
        if not isinstance(pid, str) or pid not in self.state["answers"]:
            raise ValueError("Player is not answering this question")
        section, _ = self.catalog[self.state["question_id"]]
        if answer is not None:
            if section == "mcqs" and (not isinstance(answer, str) or answer not in self.state["option_orders"][self.state["question_id"]]):
                raise ValueError("Choose one of the displayed MCQ options")
            if section == "true_false" and (not isinstance(answer, str) or answer not in {"True", "False"}):
                raise ValueError("Choose True or False")
            if section == "essays":
                if not isinstance(answer, str) or len(answer) > 20000:
                    raise ValueError("Essay response must be text of at most 20000 characters")
                answer = answer.strip() or None
        self.state["answers"][pid]["answer"] = answer

    def _pause(self, paused):
        self._require("question")
        timer = self.state["timer"]
        if timer["paused"] == paused:
            raise ValueError("Timer is already in that state")
        if paused:
            remaining = self._remaining()
            if remaining <= 0:
                raise ValueError("An expired timer cannot be paused")
            timer.update(remaining=remaining, paused=True, deadline=None)
        else:
            self.state["review_index"] = None
            timer.update(paused=False, deadline=self.clock() + timer["remaining"])

    def _review(self, data):
        self._require("question")
        if not self.state["timer"]["paused"]:
            raise ValueError("Pause the timer before browsing completed questions")
        index = data.get("index")
        if index is not None and (type(index) is not int or not 0 <= index < len(self.state["history"])):
            raise ValueError("Choose a completed question to review")
        self.state["review_index"] = index

    def _lock(self):
        self._require("question")
        if self.state["review_index"] is not None:
            raise ValueError("Return to the current question before locking answers")
        if self._remaining() > 0 and any(a["answer"] is None for a in self.state["answers"].values()):
            raise ValueError("Wait for every answer or for the timer to expire before locking")
        section, question = self.catalog[self.state["question_id"]]
        for response in self.state["answers"].values():
            response["timed_out"] = response["answer"] is None
            if response["timed_out"]:
                response["correct"] = False
            elif section != "essays":
                response["correct"] = response["answer"] == question["correct"]
        self.state["timer"] = None
        if section == "essays" and any(a["correct"] is None for a in self.state["answers"].values()):
            self.state["phase"] = "essay_marking"
        else:
            self._finish_question()

    def _mark(self, data):
        self._require("essay_marking")
        pid, correct = data.get("player_id"), data.get("correct")
        if not isinstance(pid, str) or pid not in self.state["answers"] or type(correct) is not bool:
            raise ValueError("Choose correct or incorrect for an active player")
        response = self.state["answers"][pid]
        if response["correct"] is not None:
            raise ValueError("This response is already marked")
        response["correct"] = correct
        if all(a["correct"] is not None for a in self.state["answers"].values()):
            self._finish_question()

    def _finish_question(self):
        _, question = self.catalog[self.state["question_id"]]
        tid = question["target_id"]
        for player in self._participants():
            response = self.state["answers"][player["id"]]
            targets = self.state["targets"][player["id"]]
            if self.state["stage"] == "originals":
                if response["correct"]:
                    player["score"] += 1
                elif tid not in targets:
                    targets[tid] = {"status": "pending", "attempts": 0}
            else:
                progress = targets[tid]
                progress["attempts"] += 1
                if response["correct"]:
                    progress["status"] = "cleared"
                elif progress["attempts"] == 3:
                    progress["status"] = "unresolved"
        record = {"question_id": question["id"], "stage": self.state["stage"],
                  "answers": copy.deepcopy(self.state["answers"])}
        if self.state["stage"] == "retries":
            player = self._participants()[0]
            record["retry"] = {"player_id": player["id"], "label": self.bank["learning_targets"][tid]["label"],
                               "attempt": self.state["targets"][player["id"]][tid]["attempts"]}
        self.state["history"].append(record)
        self.state["phase"] = "feedback"

    def _next_retry(self):
        players = self.state["players"]
        while self.state["retry_player_index"] < len(players):
            pid = players[self.state["retry_player_index"]]["id"]
            for tid, progress in self.state["targets"][pid].items():
                if progress["status"] == "pending":
                    self.state["retry_target_id"] = tid
                    qid = self.state["retry_orders"][tid][progress["attempts"]]
                    self._begin(qid, "retries")
                    return
            self.state["retry_player_index"] += 1
        self.state.update(phase="complete", question_id=None, answers={}, timer=None)

    def _next(self):
        self._require("feedback")
        if self.state["stage"] == "retries":
            self._next_retry()
        else:
            self.state["index"] += 1
            if self.state["index"] == len(self.state["original_order"]):
                has_misses = any(self.state["targets"].values())
                self.state.update(phase="original_results" if has_misses else "complete",
                                  question_id=None, answers={}, timer=None)
            else:
                self._begin(self.state["original_order"][self.state["index"]], "originals")

    def action(self, request):
        with self.mutex:
            if not isinstance(request, dict):
                raise ValueError("Action must be an object")
            if type(request.get("revision")) is not int or request["revision"] != self.state["revision"]:
                raise ConflictError("The game changed. Refresh your view before trying again.")
            data = request.get("payload", {})
            if not isinstance(data, dict):
                raise ValueError("Action payload must be an object")
            action = request.get("action")
            if not isinstance(action, str):
                raise ValueError("Game action must be text")
            before = copy.deepcopy(self.state)
            try:
                if action == "start":
                    self._start(data)
                elif action == "answer":
                    self._answer(data)
                elif action in {"pause", "resume"}:
                    self._pause(action == "pause")
                elif action == "review":
                    self._review(data)
                elif action == "lock":
                    self._lock()
                elif action == "mark_essay":
                    self._mark(data)
                elif action == "next":
                    self._next()
                elif action == "start_retries":
                    self._require("original_results")
                    self._next_retry()
                elif action == "restart":
                    if data.get("confirmed") is not True:
                        raise ValueError("Confirm before restarting the game")
                    self._reset(self.state["revision"])
                else:
                    raise ValueError("Unknown game action")
                self.state["revision"] += 1
                self._persist()
            except Exception:
                self.state = before
                raise
            return self.view()

    def _question_view(self, qid, reveal):
        section, q = self.catalog[qid]
        shown = {"id": q["id"], "type": section,
                 "text": q.get("statement") if section == "true_false" else q["question"]}
        if section == "mcqs":
            shown["options"] = [{"id": canonical, "label": "ABCD"[i],
                                  "text": q["options"]["ABCD".index(canonical)]}
                                 for i, canonical in enumerate(self.state["option_orders"][qid])]
        if reveal:
            shown.update(explanation=q["explanation"],
                         sources=list(dict.fromkeys(source_label(src, source_mode=self.bank["source_mode"])
                                                    for src in q["sources"])))
            if section == "essays":
                shown["model_answer"] = q["model_answer"]
            else:
                shown["correct"] = q["correct"]
            if section == "mcqs":
                shown["option_explanations"] = q["option_explanations"]
            if section == "true_false" and q["correct"] == "False":
                shown["correction"] = q["correction"]
        return copy.deepcopy(shown)

    def view(self):
        with self.mutex:
            s = self.state
            view = {key: copy.deepcopy(s[key]) for key in
                    ("revision", "phase", "stage", "players", "duration", "answers")}
            view.update(title=self.bank["title"], total=len(s["original_order"]),
                        active_question_id=s["question_id"],
                        number=min(s["index"] + 1, len(s["original_order"])),
                        timer={"remaining": self._remaining(), "paused": s["timer"]["paused"]} if s["timer"] else None)
            view["targets"] = {pid: [{"id": tid, "label": self.bank["learning_targets"][tid]["label"], **progress}
                                      for tid, progress in targets.items()]
                               for pid, targets in s["targets"].items()}
            if s["phase"] in {"original_results", "complete"}:
                best = max(p["score"] for p in s["players"])
                view["winners"] = [p["id"] for p in s["players"] if p["score"] == best]
            if s["question_id"]:
                view["question"] = self._question_view(s["question_id"], s["phase"] != "question")
            if s["stage"] == "retries" and s["phase"] != "complete":
                player = s["players"][s["retry_player_index"]]
                tid = s["retry_target_id"]
                progress = s["targets"][player["id"]][tid]
                view["retry"] = {"player_id": player["id"], "label": self.bank["learning_targets"][tid]["label"],
                                 "attempt": progress["attempts"] + (1 if s["phase"] in {"question", "essay_marking"} else 0)}
            view["review"] = {"index": s["review_index"], "count": len(s["history"])}
            if s["review_index"] is not None:
                record = s["history"][s["review_index"]]
                view["question"] = self._question_view(record["question_id"], True)
                view["answers"] = copy.deepcopy(record["answers"])
                view["stage"] = record["stage"]
                if record["stage"] == "originals":
                    view["number"] = s["original_order"].index(record["question_id"]) + 1
                    view.pop("retry", None)
                else:
                    view["retry"] = copy.deepcopy(record["retry"])
            return view
