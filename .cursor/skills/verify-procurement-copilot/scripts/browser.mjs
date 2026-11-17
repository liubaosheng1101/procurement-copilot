#!/usr/bin/env node
/**
 * Persistent Chrome session for one verification run.
 * Connects over CDP so each CLI call drives the same page.
 * Not product code.
 */
import fs from "fs";
import net from "net";
import path from "path";
import { spawn } from "child_process";
import { chromium } from "playwright-core";

const runId = process.env.VERIFY_RUN_ID;
if (!runId || !/^[A-Za-z0-9._-]+$/.test(runId)) {
  console.error("VERIFY_RUN_ID is missing or invalid");
  process.exit(1);
}

const statePath = `/tmp/procurement-copilot-verify/${runId}/state.json`;

function readState() {
  return JSON.parse(fs.readFileSync(statePath, "utf8"));
}

function writeState(state) {
  const tmp = `${statePath}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(state, null, 2) + "\n");
  fs.renameSync(tmp, statePath);
}

function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    if (token.startsWith("--")) {
      const key = token.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith("--")) out[key] = true;
      else {
        out[key] = next;
        i += 1;
      }
    } else out._.push(token);
  }
  return out;
}

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForCdp(port) {
  const deadline = Date.now() + 10000;
  let last = "not up";
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (res.ok) return;
      last = `status ${res.status}`;
    } catch (err) {
      last = err.message;
    }
    await sleep(100);
  }
  throw new Error(`CDP port ${port} did not open: ${last}`);
}

function pidAlive(pid) {
  if (!pid) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function connect(state) {
  if (!state.cdp_port) throw new Error("browser is not started");
  const browser = await chromium.connectOverCDP(`http://127.0.0.1:${state.cdp_port}`);
  const context = browser.contexts()[0];
  if (!context) throw new Error("CDP browser has no context");
  const page = context.pages()[0];
  if (!page) throw new Error("CDP browser has no page");
  page.setDefaultTimeout(8000);
  return { browser, page };
}

async function withPage(state, fn) {
  const { browser, page } = await connect(state);
  const pageErrors = [];
  const onError = (err) => pageErrors.push(String(err));
  page.on("pageerror", onError);
  try {
    await fn(page);
    if (pageErrors.length) throw new Error(`pageerror: ${pageErrors.join(" | ")}`);
  } finally {
    page.off("pageerror", onError);
  }
}

function locator(page, selector, nth) {
  let loc = page.locator(selector);
  if (nth !== undefined) loc = loc.nth(Number(nth));
  return loc;
}

async function requireSingleOrNth(page, selector, nth, action) {
  const count = await page.locator(selector).count();
  if (count === 0) throw new Error(`${action}: no match for ${selector}`);
  if (nth === undefined && count !== 1) {
    throw new Error(`${action}: ${selector} matched ${count} elements; pass --nth`);
  }
}

async function cmdStart(state) {
  if (pidAlive(state.browser_pid)) {
    throw new Error(`browser pid ${state.browser_pid} is already running for this run`);
  }
  const port = await freePort();
  const profile = path.join(state.tmp_dir, "drive-profile");
  fs.rmSync(profile, { recursive: true, force: true });
  fs.mkdirSync(profile, { recursive: true });
  const logPath = path.join(state.tmp_dir, "chrome-drive.log");
  const logFd = fs.openSync(logPath, "a");
  const child = spawn(
    state.chrome,
    [
      "--headless=new",
      "--disable-gpu",
      "--no-sandbox",
      "--disable-dev-shm-usage",
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-extensions",
      "--disable-sync",
      `--user-data-dir=${profile}`,
      `--remote-debugging-port=${port}`,
      "--window-size=1280,900",
      "--lang=zh-CN",
      "about:blank",
    ],
    { detached: true, stdio: ["ignore", logFd, logFd] }
  );
  child.unref();
  state.browser_pid = child.pid;
  state.cdp_port = port;
  writeState(state);
  try {
    await waitForCdp(port);
    await withPage(state, async (page) => {
      await page.goto(state.url, { waitUntil: "domcontentloaded" });
      await page.waitForSelector('button[data-act="run"]');
      await page.waitForSelector('button[data-tab="landed"]');
      await page.waitForFunction(() => {
        const img = document.querySelector("img.qr");
        return img && img.complete && img.naturalWidth > 0;
      });
    });
  } catch (err) {
    throw new Error(`browser start failed: ${err.message}`);
  }
  console.log(`OK browser pid=${child.pid} cdp=${port}`);
}

function cmdlineOf(pid) {
  try {
    return fs.readFileSync(`/proc/${pid}/cmdline`, "utf8");
  } catch {
    return "";
  }
}

async function cmdStop(state) {
  if (!pidAlive(state.browser_pid)) {
    state.browser_pid = null;
    state.cdp_port = null;
    writeState(state);
    console.log("OK browser already stopped");
    return;
  }
  const pid = state.browser_pid;
  const owned = cmdlineOf(pid);
  if (!owned.includes(state.run_id) || !owned.includes("drive-profile")) {
    throw new Error(`refusing to stop pid ${pid}; cmdline is not this run's drive browser`);
  }
  try {
    process.kill(-pid, "SIGTERM");
  } catch {
    try {
      process.kill(pid, "SIGTERM");
    } catch {
      /* already gone */
    }
  }
  const deadline = Date.now() + 3000;
  while (Date.now() < deadline && pidAlive(pid)) await sleep(100);
  if (pidAlive(pid)) {
    try {
      process.kill(-pid, "SIGKILL");
    } catch {
      try {
        process.kill(pid, "SIGKILL");
      } catch {
        /* already gone */
      }
    }
  }
  state.browser_pid = null;
  state.cdp_port = null;
  writeState(state);
  console.log(`OK browser stopped pid=${pid}`);
}

async function cmdGoto(state) {
  await withPage(state, async (page) => {
    await page.goto(state.url, { waitUntil: "domcontentloaded" });
    await page.waitForSelector('button[data-act="run"]');
    await page.waitForSelector('button.tab.on');
    await page.waitForFunction(() => {
      const img = document.querySelector("img.qr");
      return img && img.complete && img.naturalWidth > 0;
    });
    const on = (await page.locator("button.tab.on").innerText()).trim();
    if (on !== "报价比价") throw new Error(`fresh page tab is ${on}`);
  });
  console.log(`OK goto ${state.url}`);
}

async function cmdClick(state, args) {
  if (!args.selector) throw new Error("click requires --selector");
  await withPage(state, async (page) => {
    await requireSingleOrNth(page, args.selector, args.nth, "click");
    await locator(page, args.selector, args.nth).click();
  });
  console.log(`OK click ${args.selector}`);
}

async function cmdAssertText(state, args) {
  if (!args.selector) throw new Error("assert-text requires --selector");
  const equals = args.equals;
  const contains = args.contains;
  if (equals === undefined && contains === undefined) {
    throw new Error("assert-text requires --equals or --contains");
  }
  await withPage(state, async (page) => {
    const count = await page.locator(args.selector).count();
    if (count === 0) throw new Error(`assert-text: no match for ${args.selector}`);
    const texts = await page.locator(args.selector).allInnerTexts();
    const norm = texts.map((text) => text.replace(/\s+/g, " ").trim());
    if (equals !== undefined) {
      const want = String(equals).replace(/\s+/g, " ").trim();
      if (!norm.some((text) => text === want)) {
        throw new Error(`assert-text equals failed for ${args.selector}. want ${want}. have ${JSON.stringify(norm)}`);
      }
    }
    if (contains !== undefined) {
      const want = String(contains);
      if (!norm.some((text) => text.includes(want))) {
        throw new Error(`assert-text contains failed for ${args.selector}. want ${want}. have ${JSON.stringify(norm)}`);
      }
    }
  });
  console.log(`OK assert-text ${args.selector}`);
}

async function cmdAssertValue(state, args) {
  if (!args.selector || args.equals === undefined) throw new Error("assert-value requires --selector and --equals");
  await withPage(state, async (page) => {
    await requireSingleOrNth(page, args.selector, args.nth, "assert-value");
    const got = await locator(page, args.selector, args.nth).inputValue();
    if (got !== String(args.equals)) {
      throw new Error(`assert-value ${args.selector} got ${JSON.stringify(got)} want ${JSON.stringify(args.equals)}`);
    }
  });
  console.log(`OK assert-value ${args.selector}=${args.equals}`);
}

async function cmdAssertCount(state, args) {
  if (!args.selector || args.equals === undefined) throw new Error("assert-count requires --selector and --equals");
  await withPage(state, async (page) => {
    const count = await page.locator(args.selector).count();
    if (count !== Number(args.equals)) {
      throw new Error(`assert-count ${args.selector} got ${count} want ${args.equals}`);
    }
  });
  console.log(`OK assert-count ${args.selector}=${args.equals}`);
}

async function cmdAssertKpi(state, args) {
  if (!args.label || args.value === undefined) throw new Error("assert-kpi requires --label and --value");
  await withPage(state, async (page) => {
    const kpis = await page.$$eval(".kpi", (els) =>
      els.map((el) => ({
        k: (el.querySelector(".k")?.innerText || "").replace(/\s+/g, ""),
        v: (el.querySelector(".v")?.innerText || "").replace(/\s+/g, ""),
      }))
    );
    const wantK = String(args.label).replace(/\s+/g, "");
    const wantV = String(args.value).replace(/\s+/g, "");
    const hit = kpis.find((kpi) => kpi.k === wantK);
    if (!hit) throw new Error(`KPI ${args.label} not found. Have ${JSON.stringify(kpis)}`);
    if (hit.v !== wantV) throw new Error(`KPI ${args.label}: got ${hit.v} want ${wantV}. All ${JSON.stringify(kpis)}`);
  });
  console.log(`OK kpi ${args.label}=${args.value}`);
}

async function cmdAssertAbsent(state, args) {
  if (!args.text) throw new Error("assert-absent requires --text");
  await withPage(state, async (page) => {
    const text = await page.locator("body").innerText();
    if (text.includes(String(args.text))) {
      throw new Error(`assert-absent found ${args.text}`);
    }
  });
  console.log(`OK absent ${args.text}`);
}

async function cmdAssertOrder(state, args) {
  if (!args.selector || !args.sequence) throw new Error("assert-order requires --selector and --sequence");
  const parts = String(args.sequence).split("|");
  await withPage(state, async (page) => {
    await requireSingleOrNth(page, args.selector, args.nth, "assert-order");
    const text = await locator(page, args.selector, args.nth).innerText();
    let cursor = 0;
    for (const part of parts) {
      const at = text.indexOf(part, cursor);
      if (at < 0) throw new Error(`assert-order missing ${part} after index ${cursor}. text=${text.slice(0, 500)}`);
      cursor = at + part.length;
    }
  });
  console.log(`OK order ${args.sequence}`);
}

async function cmdScreenshot(state, args) {
  if (!args.name) throw new Error("screenshot requires --name");
  const dest = path.join(state.evidence_dir, args.name);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  await withPage(state, async (page) => {
    await page.screenshot({ path: dest, fullPage: true });
  });
  console.log(`OK screenshot ${args.name}`);
}

async function cmdDownload(state, args) {
  if (!args.selector || !args.name) throw new Error("download requires --selector and --name");
  const dest = path.join(state.evidence_dir, args.name);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  let suggested = "";
  await withPage(state, async (page) => {
    await requireSingleOrNth(page, args.selector, args.nth, "download");
    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 8000 }),
      locator(page, args.selector, args.nth).click(),
    ]);
    suggested = download.suggestedFilename();
    await download.saveAs(dest);
  });
  if (args["filename-regex"] && !new RegExp(args["filename-regex"]).test(suggested)) {
    throw new Error(`filename ${suggested} does not match ${args["filename-regex"]}`);
  }
  const data = JSON.parse(fs.readFileSync(dest, "utf8"));
  if (args["expect-mode"] && data.mode !== args["expect-mode"]) {
    throw new Error(`download mode ${data.mode} != ${args["expect-mode"]}`);
  }
  if (args["expect-metric"] && data.ranking_metric !== args["expect-metric"]) {
    throw new Error(`download ranking_metric ${data.ranking_metric} != ${args["expect-metric"]}`);
  }
  if (args["expect-rank1"]) {
    const best = (data.offers || []).find((offer) => offer.rank === 1);
    if (!best || best.supplier !== args["expect-rank1"]) {
      throw new Error(`download rank1 ${best && best.supplier} != ${args["expect-rank1"]}`);
    }
  }
  console.log(`OK download ${suggested} -> ${args.name}`);
}

async function cmdSameOrigin(state, args) {
  const names = await (async () => {
    let found;
    await withPage(state, async (page) => {
      found = await page.evaluate(() => performance.getEntries().map((entry) => entry.name));
    });
    return found;
  })();
  const origin = new URL(readState().url).origin;
  const httpNames = names.filter((name) => /^https?:/i.test(name));
  const foreign = httpNames.filter((name) => new URL(name).origin !== origin);
  const dest = path.join(state.evidence_dir, args.name || "requests.json");
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.writeFileSync(dest, JSON.stringify({ origin, entries: httpNames, foreign }, null, 2) + "\n");
  if (!httpNames.length) throw new Error("no performance entries");
  if (foreign.length) throw new Error(`cross-origin page entries: ${foreign.join(", ")}`);
  console.log(`OK same-origin entries=${httpNames.length}`);
}

const commands = {
  start: cmdStart,
  stop: cmdStop,
  goto: cmdGoto,
  click: cmdClick,
  "assert-text": cmdAssertText,
  "assert-value": cmdAssertValue,
  "assert-count": cmdAssertCount,
  "assert-kpi": cmdAssertKpi,
  "assert-absent": cmdAssertAbsent,
  "assert-order": cmdAssertOrder,
  screenshot: cmdScreenshot,
  download: cmdDownload,
  "assert-same-origin": cmdSameOrigin,
};

const argv = parseArgs(process.argv.slice(2));
const command = argv._[0];
if (!command || !commands[command]) {
  console.error(`unknown browser command ${command || ""}. Known: ${Object.keys(commands).join(", ")}`);
  process.exit(1);
}

try {
  const state = readState();
  await commands[command](state, argv);
  process.exit(0);
} catch (err) {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
}
