"use strict";

let state = null;
let csrf = "";
let busy = false;
let timerReceived = 0;
let displayedKey = "";
let connectionLost = false;
const drafts = new Map();
const app = document.getElementById("app");
const errorBox = document.getElementById("error");
const typeNames = {mcqs: "Multiple choice", true_false: "True or false", essays: "Essay"};

// Theme is a browser preference, independent of answers and the game session.
const themeToggle = document.getElementById("theme-toggle");
function setTheme(theme) {
  const dark = theme === "dark";
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  themeToggle.setAttribute("aria-pressed", String(dark));
  themeToggle.textContent = dark ? "Light mode" : "Dark mode";
}
let savedTheme = "light";
try { savedTheme = localStorage.getItem("exam-night-theme") || "light"; } catch (_) { /* Storage may be disabled. */ }
setTheme(savedTheme);
themeToggle.addEventListener("click", () => {
  const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  setTheme(theme);
  try { localStorage.setItem("exam-night-theme", theme); } catch (_) { /* The toggle still works without storage. */ }
});

// User/source text is inserted as text nodes, never as HTML.
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function button(text, action, className = "button") {
  const node = el("button", className, text);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
}
function countdownClock() {
  const wrapper = el("div", "clock-timer");
  wrapper.setAttribute("role", "timer");
  wrapper.setAttribute("aria-label", "Question countdown");
  const namespace = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(namespace, "svg");
  svg.setAttribute("viewBox", "0 0 80 80");
  svg.setAttribute("class", "clock-face");
  svg.setAttribute("aria-hidden", "true");
  function shape(tag, attributes) {
    const node = document.createElementNS(namespace, tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    svg.append(node); return node;
  }
  shape("circle", {cx: 40, cy: 40, r: 32, class: "clock-track"});
  shape("circle", {cx: 40, cy: 40, r: 32, class: "clock-progress", id: "clock-progress", transform: "rotate(-90 40 40)", "stroke-dasharray": 2 * Math.PI * 32});
  for (let i = 0; i < 12; i++) {
    const angle = i * Math.PI / 6;
    shape("line", {x1: 40 + Math.sin(angle) * 23, y1: 40 - Math.cos(angle) * 23,
                   x2: 40 + Math.sin(angle) * 26, y2: 40 - Math.cos(angle) * 26, class: "clock-tick"});
  }
  shape("line", {x1: 40, y1: 40, x2: 40, y2: 22, class: "clock-hand", id: "clock-hand"});
  shape("circle", {cx: 40, cy: 40, r: 3, class: "clock-center"});
  const text = el("div", "clock-text");
  const count = el("div", "timer"); count.id = "timer";
  const status = el("div", "timer-caption", "Time remaining"); status.id = "timer-status";
  text.append(count, status); wrapper.append(svg, text); return wrapper;
}
function clockText(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  const pad = value => String(value).padStart(2, "0");
  return `${hours ? `${pad(hours)}:` : ""}${pad(minutes)}:${pad(rest)}`;
}
function showError(message) {
  errorBox.textContent = message || "";
  errorBox.hidden = !message;
}
function accept(next, force = false) {
  if (state && (state.active_question_id !== next.active_question_id || next.phase !== "question")) drafts.clear();
  state = next;
  if (next.csrf_token) csrf = next.csrf_token;
  timerReceived = performance.now();
  document.title = `${next.title} · Exam Night`;
  document.getElementById("restart").hidden = next.phase === "setup";
  const key = `${next.revision}:${next.phase}`;
  if (force || key !== displayedKey) {
    displayedKey = key;
    render();
  }
  tick();
}
async function refresh(force = false) {
  const response = await fetch("/api/state", {cache: "no-store"});
  if (!response.ok) throw new Error("Could not reconnect to the game. Refresh the page.");
  const next = await response.json();
  if (state && next.revision < state.revision && next.csrf_token === csrf) return;
  accept(next, force);
}
async function act(action, payload = {}) {
  if (busy) return false;
  busy = true;
  showError("");
  try {
    const response = await fetch("/api/action", {
      method: "POST", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrf},
      body: JSON.stringify({action, revision: state.revision, payload})
    });
    const result = await response.json();
    if (!response.ok) {
      if (result.state) accept(result.state, true);
      if (response.status === 403) await refresh(true);
      throw new Error(result.error || "Could not save that action.");
    }
    accept(result, true);
    return true;
  } catch (error) {
    showError(error.message || "Connection lost. Keep the local server running and refresh the page.");
    return false;
  } finally {
    busy = false;
  }
}
function render() {
  app.dataset.phase = state.phase;
  app.dataset.revision = String(state.revision);
  app.replaceChildren();
  if (state.phase === "setup") renderSetup();
  else if (["original_results", "complete"].includes(state.phase)) renderResults();
  else renderQuestion();
}
function renderSetup() {
  const hero = el("section", "hero");
  hero.append(el("div", "eyebrow", "A little competition. A lot of learning."), el("h1", "", state.title),
              el("p", "", "Play solo or bring your friends. Every correct answer earns a point. Every mistake is a chance to learn."));
  const grid = el("div", "setup-grid");
  const form = el("form", "panel setup-panel");
  const mode = el("select"); mode.id = "mode";
  for (const [value, text] of [["solo", "Solo · just me"], ["group", "Group · play with friends"]]) {
    const option = el("option", "", text); option.value = value; mode.append(option);
  }
  const names = el("textarea"); names.id = "names"; names.required = true;
  names.placeholder = "Your name"; names.setAttribute("aria-describedby", "names-hint");
  const duration = el("input"); duration.id = "duration"; duration.type = "number";
  duration.min = "1"; duration.max = "86400"; duration.step = "1"; duration.required = true; duration.value = "60";
  function label(text, id) { const node = el("label", "", text); node.htmlFor = id; return node; }
  const hint = el("p", "hint", "Solo: enter one name. Group: enter one name per line."); hint.id = "names-hint";
  form.append(el("h2", "", "Set up your game"), label("How are you playing?", "mode"), mode,
              label("Player names", "names"), names, hint,
              label("Seconds per question", "duration"), duration,
              el("p", "hint", "The same time applies to every question and retry. You can pause the timer."));
  const actions = el("div", "actions");
  const start = el("button", "button primary", `Start ${state.total}-question game →`); start.type = "submit";
  actions.append(start); form.append(actions);
  mode.addEventListener("change", () => { names.placeholder = mode.value === "solo" ? "Your name" : "Alex\nSam\nJordan"; });
  form.addEventListener("submit", event => {
    event.preventDefault();
    const roster = names.value.split(/\r?\n/).map(n => n.trim()).filter(Boolean);
    act("start", {mode: mode.value, names: roster, duration: Number(duration.value)});
  });
  const guide = el("aside", "panel guide");
  guide.append(el("span", "badge", "HOW IT WORKS"), el("h2", "", "Host the room."));
  const list = el("ol");
  for (const text of ["Share this browser screen with your friends. The host records the answers everyone gives.",
                      "Lock everyone’s answers before revealing results. Essays are marked by the host.",
                      "Highest original score wins. Then revisit missed concepts with new questions."]) list.append(el("li", "", text));
  guide.append(list, el("p", "hint", "Friends answer aloud or in shared chat. They don’t need to open this app."));
  grid.append(form, guide); app.append(hero, grid);
}
function renderQuestion() {
  const q = state.question;
  const reviewing = state.review?.index !== null && state.review?.index !== undefined;
  const top = el("div", "section-top");
  const heading = el("div");
  heading.append(el("div", "eyebrow", `${reviewing ? "Review · " : ""}${state.stage === "retries" ? "Practice · points are settled" : `Question ${state.number} / ${state.total}`}`),
                 el("h1", "", state.stage === "retries" ? `${playerName(state.retry.player_id)} · retry ${state.retry.attempt} of 3` : state.title));
  top.append(heading);
  if (state.timer) {
    const timers = el("div", "timer-box");
    timers.append(countdownClock(), button(state.timer.paused ? (reviewing ? "Resume current question" : "Resume timer") : "Pause timer", () => act(state.timer.paused ? "resume" : "pause"), "button quiet"));
    top.append(timers);
  }
  app.append(top);
  if (state.timer?.paused) renderReviewNavigation();
  if (state.stage === "originals") {
    const progress = el("progress", "progress"); progress.max = state.total; progress.value = state.number;
    progress.setAttribute("aria-label", "Original exam progress"); app.append(progress);
  } else app.append(el("p", "hint", `Learning target: ${state.retry.label}`));
  const panel = el("section", "panel question-panel");
  panel.append(el("span", "badge", typeNames[q.type]), el("h2", "", q.text));
  if (q.options) {
    const options = el("div", "options");
    for (const option of q.options) {
      const row = el("div", "option");
      row.append(el("span", "option-letter", option.label), el("span", "", option.text)); options.append(row);
    }
    panel.append(options);
  }
  app.append(panel);
  const players = el("div", "players");
  for (const [pid, answer] of Object.entries(state.answers)) players.append(playerCard(pid, answer, q));
  app.append(players);
  if (reviewing) {
    app.append(el("p", "hint", "Reviewing a completed question. Return to the current question to continue answering."));
    renderFeedback(q);
  } else if (state.phase === "question") {
    const note = el("p", "deadline-note"); note.id = "deadline-note"; note.hidden = true;
    note.textContent = "Time is up. Finish recording answers, then lock. Anyone without an answer will be marked timed out.";
    app.append(note);
    const actions = el("div", "actions");
    const lock = button("Lock everyone’s answers", () => act("lock"), "button primary"); lock.id = "lock";
    actions.append(lock); app.append(actions, el("p", "hint", "Save each response before locking. Results stay hidden until everyone is answered or timed out."));
  } else {
    renderFeedback(q);
    if (state.phase === "feedback") {
      const actions = el("div", "actions");
      const last = state.stage === "originals" && state.number === state.total;
      actions.append(button(last ? "See original results →" : "Continue →", () => act("next"), "button primary")); app.append(actions);
    }
  }
}
function renderReviewNavigation() {
  const {index, count} = state.review;
  const navigation = el("nav", "review-navigation");
  navigation.setAttribute("aria-label", "Paused question navigation");
  const controls = el("div", "review-controls");
  const previous = button("← Previous question", () => act("review", {index: index === null ? count - 1 : index - 1}), "button quiet");
  previous.disabled = count === 0 || index === 0;
  const next = button("Next question →", () => act("review", {index: index + 1 < count ? index + 1 : null}), "button quiet");
  next.disabled = index === null;
  controls.append(previous, next);
  if (index !== null) controls.append(button("Return to current question", () => act("review", {index: null}), "button primary"));
  navigation.append(controls, el("p", "hint", index === null
    ? (count ? "Timer paused. Browse your completed questions." : "Timer paused. No earlier questions yet.")
    : `Completed question ${index + 1} of ${count} · current question remains paused`));
  app.append(navigation);
}
function playerName(pid) { return state.players.find(p => p.id === pid).name; }
function responseText(answer, q) {
  if (answer === null) return "No answer";
  if (q.options) { const option = q.options.find(o => o.id === answer); return `${option.label}) ${option.text}`; }
  return answer;
}
function playerCard(pid, answer, q) {
  const player = state.players.find(p => p.id === pid);
  const card = el("section", "player-card"); card.dataset.player = pid;
  const header = el("div", "player-header");
  header.append(el("h3", "", player.name), el("span", "score", `${player.score} pts`)); card.append(header);
  if (state.phase === "question" && state.review?.index === null) {
    const form = el("form");
    const label = el("label", "", "Their answer"); label.htmlFor = `answer-${pid}`;
    let input;
    if (q.type === "essays") {
      input = el("textarea"); input.maxLength = 20000; input.value = answer.answer || "";
      input.placeholder = "Type or paste their response";
    } else {
      input = el("select");
      const empty = el("option", "", "Choose an answer…"); empty.value = ""; input.append(empty);
      const choices = q.options || [{id: "True", text: "True"}, {id: "False", text: "False"}];
      for (const choice of choices) { const option = el("option", "", choice.label ? `${choice.label}) ${choice.text}` : choice.text); option.value = choice.id; input.append(option); }
      input.value = answer.answer || "";
    }
    input.id = `answer-${pid}`;
    const draftKey = `${q.id}:${pid}`;
    if (drafts.has(draftKey)) input.value = drafts.get(draftKey);
    const save = el("button", "button", answer.answer === null ? "Save answer" : "Update answer"); save.type = "submit";
    const actions = el("div", "actions"); actions.append(save);
    const status = el("p", "status", answer.answer === null ? "Waiting for an answer" : "Answer saved · editable until lock");
    if (drafts.has(draftKey)) status.textContent = "Unsaved change · save before locking";
    input.addEventListener("input", () => {
      drafts.set(draftKey, input.value);
      status.textContent = "Unsaved change · save before locking";
      tick();
    });
    form.append(label, input, actions, status);
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (busy) return;
      const value = input.value;
      drafts.delete(draftKey);
      if (!(await act("answer", {player_id: pid, answer: value || null}))) {
        drafts.set(draftKey, value);
        render(); tick();
      }
    });
    card.append(form);
  } else {
    card.append(el("p", "response", responseText(answer.answer, q)));
    let status = answer.timed_out ? "Timed out" : answer.correct === null ? "Waiting for host marking" : answer.correct ? "Correct" : "Incorrect";
    card.append(el("p", `status ${answer.correct === true ? "correct" : answer.correct === false ? "wrong" : ""}`, status));
    if (state.phase === "essay_marking" && answer.correct === null) {
      const actions = el("div", "actions");
      actions.append(button("Correct", () => act("mark_essay", {player_id: pid, correct: true}), "button primary"),
                     button("Incorrect", () => act("mark_essay", {player_id: pid, correct: false}))); card.append(actions);
    }
  }
  return card;
}
function renderFeedback(q) {
  const panel = el("section", "panel feedback");
  panel.append(el("h2", "", state.phase === "essay_marking" ? "Host: mark against this model answer" : "The answer, explained"));
  if (q.type === "essays") {
    const points = el("ul", "model-points"); for (const point of q.model_answer) points.append(el("li", "", point)); panel.append(points);
  } else panel.append(el("p", "correct-answer", `Correct answer: ${responseText(q.correct, q)}`));
  if (q.correction) panel.append(el("p", "explanation", `Correction: ${q.correction}`));
  panel.append(el("p", "explanation", q.explanation));
  if (q.options) for (const option of q.options) {
    const row = el("div", "rationale"); row.append(el("strong", "", `${option.label}) ${option.text}${option.id === q.correct ? " · correct" : " · incorrect"}`),
                                                  el("div", "", q.option_explanations[option.id])); panel.append(row);
  }
  const sources = el("details"); sources.append(el("summary", "", "Source references"), el("div", "sources", q.sources.join("\n\n")));
  panel.append(sources); app.append(panel);
}
function renderResults() {
  const complete = state.phase === "complete";
  app.append(el("div", "eyebrow", complete ? "Game complete" : "Original exam complete"));
  const banner = el("section", "winner-banner");
  const winners = state.players.filter(p => state.winners.includes(p.id));
  banner.append(el("span", "badge", state.players.length === 1 ? "YOUR RESULT" : winners.length > 1 ? "SHARED WINNERS" : "WINNER"),
                el("h2", "", winners.map(p => p.name).join(" & ")),
                el("p", "", `${winners[0].score} / ${state.total} points · original answers decide the score`));
  app.append(banner);
  const board = el("section", "leaderboard");
  const sorted = [...state.players].sort((a,b) => b.score - a.score);
  for (const player of sorted) {
    const row = el("div", "leader-row");
    const rank = sorted.findIndex(p => p.score === player.score) + 1;
    row.append(el("span", "rank", String(rank)), el("span", "leader-name", player.name), el("span", "leader-score", `${player.score} pts`)); board.append(row);
  }
  app.append(board, el("h2", "", complete ? "What you learned" : "Next: turn mistakes into understanding"));
  const cards = el("div", "players");
  for (const player of state.players) {
    const card = el("section", "player-card"); card.append(el("h3", "", player.name));
    const targets = state.targets[player.id];
    if (!targets.length) card.append(el("p", "empty-note", "No missed learning targets. Nice work."));
    else {
      const list = el("ul", "target-list");
      for (const target of targets) {
        const row = el("li"); row.append(el("span", "target-label", target.label));
        const label = target.status === "cleared" ? "Cleared" : target.status === "unresolved" ? "Needs more study" : "Ready to revisit";
        row.append(el("span", "target-status", `${label} · ${target.attempts} / 3 retries used`)); list.append(row);
      }
      card.append(list);
    }
    cards.append(card);
  }
  app.append(cards);
  if (!complete) {
    app.append(el("p", "hint", "One player at a time. One correct retry clears a target; three failed retries end it. Your score stays the same."));
    const actions = el("div", "actions"); actions.append(button("Start targeted practice →", () => act("start_retries"), "button primary")); app.append(actions);
  }
}
function tick() {
  if (!state || !state.timer) return;
  const elapsed = state.timer.paused ? 0 : (performance.now() - timerReceived) / 1000;
  const remaining = Math.max(0, state.timer.remaining - elapsed);
  const count = document.getElementById("timer");
  if (count) {
    const seconds = Math.ceil(remaining);
    count.textContent = clockText(seconds);
    count.setAttribute("aria-label", `${seconds} seconds remaining${state.timer.paused ? ", paused" : ""}`);
    count.classList.toggle("expired", remaining === 0);
  }
  const caption = document.getElementById("timer-status");
  if (caption) caption.textContent = state.timer.paused ? "Paused" : remaining === 0 ? "Time is up" : "Time remaining";
  const progress = document.getElementById("clock-progress");
  if (progress) progress.setAttribute("stroke-dashoffset", 2 * Math.PI * 32 * (1 - remaining / state.duration));
  const hand = document.getElementById("clock-hand");
  if (hand) hand.setAttribute("transform", `rotate(${360 * (1 - remaining / state.duration)} 40 40)`);
  const note = document.getElementById("deadline-note"); if (note) note.hidden = remaining > 0;
  const lock = document.getElementById("lock");
  if (lock) lock.disabled = drafts.size > 0 || (remaining > 0 && Object.values(state.answers).some(a => a.answer === null));
}
document.getElementById("restart").addEventListener("click", () => document.getElementById("restart-dialog").showModal());
document.getElementById("cancel-restart").addEventListener("click", () => document.getElementById("restart-dialog").close());
document.getElementById("confirm-restart").addEventListener("click", async () => {
  if (await act("restart", {confirmed: true})) document.getElementById("restart-dialog").close();
});
setInterval(tick, 200);
setInterval(async () => {
  // Do not replace an in-progress host draft. Saved game updates are revisioned.
  if (busy) return;
  try {
    await refresh();
    if (connectionLost) showError("");
    connectionLost = false;
  } catch (error) {
    connectionLost = true;
    showError("Connection lost. Keep the local server running; progress returns when it reconnects.");
  }
}, 2000);
refresh().catch(error => showError(error.message));
