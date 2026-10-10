/* Development-only browser verification. Gameplay itself requires only Python. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {spawn} = require("node:child_process");
const {chromium} = require("playwright");

async function main() {
  const root = path.resolve(__dirname, "..");
  const work = path.join(root, "work");
  fs.mkdirSync(work, {recursive: true});
  const directory = fs.mkdtempSync(path.join(work, "browser-"));
  const bank = JSON.parse(fs.readFileSync(path.join(__dirname, "files/sample_game.json"), "utf8"));
  const exam = path.join(directory, "exam.json");
  fs.writeFileSync(exam, JSON.stringify(bank));
  const originals = new Map(["mcqs", "true_false", "essays"].flatMap(s => bank[s].map(q => [q.id, q])));
  const questions = new Map([...originals, ...Object.values(bank.learning_targets).flatMap(t => t.retries.map(q => [q.id, q]))]);
  const server = spawn(process.env.EXAM_TEST_PYTHON || "python", [path.join(root, "scripts/serve_exam_game.py"), exam], {cwd: root, windowsHide: true});
  let errors = "";
  server.stderr.on("data", chunk => { errors += chunk; });
  let browser;
  try {
    const url = await new Promise((resolve, reject) => {
      let output = "";
      const timeout = setTimeout(() => reject(new Error(`Server did not start: ${errors}`)), 15000);
      server.stdout.on("data", chunk => {
        output += chunk;
        const match = output.match(/Open (http:\/\/127\.0\.0\.1:\d+)/);
        if (match) { clearTimeout(timeout); resolve(match[1]); }
      });
      server.once("exit", code => { clearTimeout(timeout); reject(new Error(`Server exited ${code}: ${errors}`)); });
    });
    browser = await chromium.launch({headless: true, ...(process.env.EXAM_TEST_BROWSER ? {executablePath: process.env.EXAM_TEST_BROWSER} : {})});
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const jsErrors = [];
    const externalRequests = [];
    page.on("pageerror", error => jsErrors.push(error.message));
    page.on("request", request => { if (!request.url().startsWith(url)) externalRequests.push(request.url()); });
    page.on("dialog", dialog => { jsErrors.push(`Unexpected dialog: ${dialog.message()}`); dialog.dismiss(); });
    await page.goto(url);
    const current = () => page.evaluate(async () => (await fetch("/api/state")).json());
    async function phase(name) {
      await page.waitForFunction(async value => (await (await fetch("/api/state")).json()).phase === value, name);
      await page.waitForFunction(value => window.document.getElementById("app").dataset.phase === value, name);
    }
    async function clickAction(name) {
      const previous = await current();
      await page.getByRole("button", {name, exact: true}).click();
      await page.waitForFunction(async revision => (await (await fetch("/api/state")).json()).revision > revision, previous.revision);
      await page.waitForFunction(revision => Number(document.getElementById("app").dataset.revision) > revision, previous.revision);
    }
    async function save(pid, value) {
      const view = await current();
      const input = page.locator(`#answer-${pid}`);
      if (view.question.type === "essays") await input.fill(value);
      else await input.selectOption(value);
      const revision = view.revision;
      await page.locator(`[data-player="${pid}"]`).getByRole("button", {name: /Save answer|Update answer/}).click();
      await page.waitForFunction(async rev => (await (await fetch("/api/state")).json()).revision > rev, revision);
      await page.waitForFunction(rev => Number(document.getElementById("app").dataset.revision) > rev, revision);
    }
    async function solve(correctness) {
      const view = await current();
      const q = questions.get(view.question.id);
      for (const pid of Object.keys(view.answers)) {
        const right = correctness[pid];
        const value = view.question.type === "essays" ? "Four equal straight sides" : right ? q.correct : view.question.type === "mcqs" ? [..."ABCD"].find(c => c !== q.correct) : q.correct === "True" ? "False" : "True";
        await save(pid, value);
      }
      await clickAction("Lock everyone’s answers");
      if (view.question.type === "essays") {
        for (const pid of Object.keys(view.answers)) {
          const revision = (await current()).revision;
          await page.locator(`[data-player="${pid}"]`).getByRole("button", {name: correctness[pid] ? "Correct" : "Incorrect", exact: true}).click();
          await page.waitForFunction(async rev => (await (await fetch("/api/state")).json()).revision > rev, revision);
          await page.waitForFunction(rev => Number(document.getElementById("app").dataset.revision) > rev, revision);
        }
      }
      await phase("feedback");
    }
    async function restart() {
      await page.getByRole("button", {name: "Restart game", exact: true}).click();
      await page.getByRole("dialog").getByRole("button", {name: "Restart game", exact: true}).click();
      await phase("setup");
    }
    async function theme(dark) {
      await page.locator("#theme-toggle").click();
      assert.equal(await page.locator("html").getAttribute("data-theme"), dark ? "dark" : "light");
      assert.equal(await page.locator("#theme-toggle").getAttribute("aria-pressed"), String(dark));
      assert.equal(await page.locator("#theme-toggle").textContent(), dark ? "Light mode" : "Dark mode");
      // Allow the short button background transition to settle before screenshots.
      await page.waitForTimeout(200);
    }
    await phase("setup");
    assert.equal(await page.locator("html").getAttribute("data-theme"), "light");
    const setupRevision = (await current()).revision;
    await page.locator("#names").fill("Theme draft");
    await theme(true);
    assert.equal(await page.locator("#names").inputValue(), "Theme draft");
    assert.equal((await current()).revision, setupRevision);
    await page.reload();
    await phase("setup");
    assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
    await theme(false);
    await page.locator("#mode").selectOption("group");
    await page.locator("#names").fill("Alice\nBob");
    await page.locator("#duration").fill("60");
    await clickAction("Start 3-question game →");
    assert.match(await page.locator("#timer").textContent(), /^\d{2}:\d{2}$/);
    assert.equal(await page.locator(".clock-face").count(), 1);
    await page.screenshot({path: path.join(work, "game-preview.png"), fullPage: true});
    await clickAction("Pause timer");
    let view = await current();
    assert.equal(view.timer.paused, true);
    assert.equal(view.question.correct, undefined);
    // Saving Alice must preserve Bob's unsaved draft across re-render and polling.
    await page.locator("#answer-p1").selectOption("B");
    await page.locator("#answer-p2").selectOption("A");
    const beforeTheme = await current();
    await theme(true);
    assert.equal(await page.locator("#answer-p1").inputValue(), "B");
    assert.equal(await page.locator("#answer-p2").inputValue(), "A");
    assert.deepEqual(await current(), beforeTheme);
    await page.screenshot({path: path.join(work, "game-dark.png"), fullPage: true});
    await theme(false);
    await save("p1", "B");
    assert.equal(await page.locator("#answer-p2").inputValue(), "A");
    assert.equal(await page.locator("#lock").isDisabled(), true);
    await save("p2", "A");
    await clickAction("Resume timer");
    const runningTheme = await current();
    await theme(true);
    await theme(false);
    const afterRunningTheme = await current();
    assert.equal(afterRunningTheme.revision, runningTheme.revision);
    assert.deepEqual(afterRunningTheme.answers, runningTheme.answers);
    assert.deepEqual(afterRunningTheme.players, runningTheme.players);
    assert.equal(afterRunningTheme.timer.paused, false);
    assert.ok(afterRunningTheme.timer.remaining <= runningTheme.timer.remaining);
    const beforeRefresh = await current();
    await page.reload();
    await page.locator("#answer-p1").waitFor();
    assert.equal((await current()).revision, beforeRefresh.revision);
    assert.equal(await page.locator("#answer-p1").inputValue(), "B");
    await clickAction("Lock everyone’s answers");
    await phase("feedback");
    assert.equal((await current()).players[0].score, 1);
    await page.screenshot({path: path.join(work, "game-feedback.png"), fullPage: true});
    await clickAction("Continue →");
    // Paused review must retain the active draft, remaining time, and scoring.
    assert.equal(await page.getByRole("button", {name: "← Previous question", exact: true}).count(), 0);
    await clickAction("Pause timer");
    const paused = await current();
    await page.locator("#answer-p1").selectOption("True");
    await clickAction("← Previous question");
    view = await current();
    assert.equal(view.review.index, 0);
    assert.equal(view.question.type, "mcqs");
    assert.equal(await page.locator("#answer-p1").count(), 0);
    assert.deepEqual(view.players, paused.players);
    assert.equal(view.timer.remaining, paused.timer.remaining);
    const frozenClock = await page.locator("#timer").textContent();
    const beforeReviewTheme = await current();
    await theme(true);
    assert.deepEqual(await current(), beforeReviewTheme);
    await theme(false);
    await page.waitForTimeout(2200);
    assert.equal(await page.locator("#timer").textContent(), frozenClock);
    await page.screenshot({path: path.join(work, "game-paused-review.png"), fullPage: true});
    await clickAction("Next question →");
    assert.equal(await page.locator("#answer-p1").inputValue(), "True");
    assert.equal((await current()).review.index, null);
    await clickAction("← Previous question");
    await page.reload();
    await page.getByRole("button", {name: "Return to current question", exact: true}).waitFor();
    assert.equal((await current()).review.index, 0);
    await clickAction("Return to current question");
    await clickAction("Resume timer");
    assert.equal((await current()).question.correct, undefined);
    await solve({p1: true, p2: true});
    await clickAction("Continue →");
    await clickAction("Pause timer");
    await clickAction("← Previous question");
    assert.equal((await current()).review.index, 1);
    await clickAction("← Previous question");
    assert.equal((await current()).review.index, 0);
    await clickAction("Next question →");
    assert.equal((await current()).review.index, 1);
    await clickAction("Resume current question");
    await solve({p1: true, p2: true});
    await clickAction("See original results →");
    await phase("original_results");
    assert.deepEqual((await current()).winners, ["p1"]);
    await clickAction("Start targeted practice →");
    assert.deepEqual(Object.keys((await current()).answers), ["p2"]);
    await solve({p2: true});
    await clickAction("Continue →");
    await phase("complete");
    view = await current();
    assert.deepEqual(view.players.map(p => p.score), [3, 2]);
    assert.equal(view.targets.p2[0].status, "cleared");
    await page.screenshot({path: path.join(work, "game-results.png"), fullPage: true});
    // A second run verifies solo timeouts and exhausting exactly three retries.
    await restart();
    await page.locator("#names").fill("Solo");
    await page.locator("#duration").fill("1");
    await clickAction("Start 3-question game →");
    await page.waitForFunction(() => !document.getElementById("lock").disabled);
    assert.equal((await current()).question.correct, undefined);
    await clickAction("Lock everyone’s answers");
    assert.equal((await current()).answers.p1.timed_out, true);
    await clickAction("Continue →");
    await solve({p1: true});
    await clickAction("Continue →");
    await solve({p1: true});
    await clickAction("See original results →");
    await clickAction("Start targeted practice →");
    for (let i = 0; i < 3; i++) {
      await solve({p1: false});
      await clickAction("Continue →");
    }
    await phase("complete");
    view = await current();
    assert.equal(view.targets.p1[0].status, "unresolved");
    assert.equal(view.targets.p1[0].attempts, 3);
    assert.equal(view.players[0].score, 2);
    // All-correct group result must declare shared winners, not a speed winner.
    await restart();
    await page.locator("#mode").selectOption("group");
    await page.locator("#names").fill("Alice\nBob");
    await page.locator("#duration").fill("60");
    await clickAction("Start 3-question game →");
    for (let i = 0; i < 3; i++) {
      await solve({p1: true, p2: true});
      await clickAction(i === 2 ? "See original results →" : "Continue →");
    }
    await phase("complete");
    assert.deepEqual((await current()).winners, ["p1", "p2"]);
    // Responsive view must remain usable without horizontal overflow.
    await page.setViewportSize({width: 390, height: 844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    await restart();
    await page.locator("#names").fill("Clock check");
    await page.locator("#duration").fill("3661");
    await clickAction("Start 3-question game →");
    assert.match(await page.locator("#timer").textContent(), /^\d{2}:\d{2}:\d{2}$/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    await clickAction("Pause timer");
    assert.equal(await page.getByRole("button", {name: "← Previous question", exact: true}).isDisabled(), true);
    await page.screenshot({path: path.join(work, "game-mobile-clock.png"), fullPage: true});
    await theme(true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    await page.screenshot({path: path.join(work, "game-mobile-dark.png"), fullPage: true});
    await restart();
    assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
    await page.reload();
    await phase("setup");
    assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
    await theme(false);
    // Browsers that block storage must still be able to switch themes and play.
    const noStorage = await browser.newContext();
    await noStorage.addInitScript(() => {
      Object.defineProperty(window, "localStorage", {get() { throw new Error("Storage disabled"); }});
    });
    const blockedPage = await noStorage.newPage();
    blockedPage.on("pageerror", error => jsErrors.push(error.message));
    await blockedPage.goto(url);
    await blockedPage.locator("#names").waitFor();
    assert.equal(await blockedPage.locator("html").getAttribute("data-theme"), "light");
    await blockedPage.locator("#theme-toggle").click();
    assert.equal(await blockedPage.locator("html").getAttribute("data-theme"), "dark");
    await blockedPage.reload();
    await blockedPage.locator("#names").waitFor();
    assert.equal(await blockedPage.locator("html").getAttribute("data-theme"), "light");
    await noStorage.close();
    assert.deepEqual(jsErrors, []);
    assert.deepEqual(externalRequests, []);
    console.log("Browser smoke passed: themes, clock, paused navigation, group/solo, drafts, refresh, essays, timeouts, retries, ties, mobile.");
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
