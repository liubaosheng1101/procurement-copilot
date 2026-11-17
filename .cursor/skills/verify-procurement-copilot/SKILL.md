---
name: verify-procurement-copilot
description: "Drive the procurement decision copilot (采购决策助手), a static Chinese calculator page, in headless Chrome and capture proof. Use when checking quote comparison, price analysis, supplier scoring, inventory replenishment, or landed cost, or before claiming this page works."
---

# Verify procurement copilot

The app is one static page, `index.html`, plus `抖音码.png`. It has no build, no server of its own, no account, and no saved data. A user opens it and runs one of five calculators in the browser. This skill starts a run-stamped local server, proves the page that answered is this checkout, drives the real buttons, and keeps the proof.

GitHub Pages publishes the same files at `https://liubaosheng1101.github.io/procurement-copilot/`. That host does not send this run's identity headers. Do not drive it for a proof of the checkout you have open. The README's "open `index.html`" path is the human path. Verification uses the stamped server below so two runs can sit on different ports and Doctor can reject a stranger.

There is no package script, unit test, or typecheck in this repo. Do not invent `npm test`. A missing test script is the baseline, not a failure.

## Launch

From the repo root, on a machine that has Node and a real Chrome/Chromium ELF binary:

```bash
npm install --prefix .cursor/skills/verify-procurement-copilot
python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py launch
```

Launch refuses to start when `index.html` or `抖音码.png` differ from `HEAD`. It picks a free `127.0.0.1` port unless `VERIFY_PORT` is set, creates a new `VERIFY_RUN_ID` unless one is already set, and serves the repo root with `scripts/serve.py`:

```bash
python3 .cursor/skills/verify-procurement-copilot/scripts/serve.py \
  --root <repo> --port <port> --run-id <VERIFY_RUN_ID> --commit <HEAD> \
  --access-log <evidence>/access.log
```

Every response carries `X-Verify-App: procurement-copilot`, `X-Verify-Run`, and `X-Verify-Commit`. `Cache-Control` is `no-store`.

Ready does not mean the port accepted a socket. Ready means all of these are true, and launch exits 0 only then:

- `GET /` is 200, the body is the empty shell (`<main id="app"></main>`), and the run headers match this launch.
- Headless Chrome dump-dom shows `#tabs` with `data-tab="quote"` through `data-tab="landed"` and `#app` containing `data-act="run">开始计算` plus the empty-result hint `点「载入示例」`.
- stdout contains `VERIFY_RUN_ID=...`, `VERIFY_URL=...`, `VERIFY_COMMIT=...`, and `READY tabs=5 button=开始计算`.

Export the printed id before any later command:

```bash
export VERIFY_RUN_ID=<the printed id>
```

Chrome for dump-dom and for driving is `VERIFY_CHROME` when set, otherwise the first ELF binary among `/opt/google/chrome/chrome`, `/usr/bin/chromium`, `/usr/bin/chromium-browser`, and `/usr/bin/google-chrome-stable`. Do not point this at `/usr/local/bin/google-chrome`. That wrapper pins one shared profile and one debugging port, so a second run would attach to someone else's browser.

Nothing is seeded. The page opens on 报价比价 with three blank offer rows. Reloading discards inputs. There is no database and no login.

If launch fails after the server process exists, launch runs cleanup for that id before exiting. A failed launch still leaves its evidence directory.

## Doctor

```bash
python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py doctor
```

Doctor is read-only. It exits 0 only when this live instance is the one worth driving:

- `VERIFY_RUN_ID` selects `/tmp/procurement-copilot-verify/<id>/state.json`.
- The recorded server pid is alive, its cmdline contains `serve.py` and this run id, and it holds the listen socket on `127.0.0.1:<port>`.
- `GET /` and `GET /抖音码.png` are 200 with this run's headers. The HTML bytes match the working tree and `HEAD`.
- `HEAD` is still the commit stamped at launch.
- A fresh dump-dom shows the five tabs and the 开始计算 button inside `#app`.

Stdout on success is one line: `DOCTOR_OK url=... commit=... pid=... run=...`. Anything off exits 1 and lists the problems in stderr and in `doctor.txt`. Do not click through Doctor.

## Drive

Drive the page that Doctor just accepted. Stable handles from `index.html` are attributes, not coordinates:

- Tabs: `button[data-tab="quote|price|score|inventory|landed"]`. The visible names are 报价比价, 价格分析, 供应商评分, 库存补货, 进口到岸成本. The active tab is `button.tab.on`.
- Actions: `button[data-act="run|example|clear|copy|download|add-row|del-row"]`. Visible names: 开始计算, 载入示例, 清空, 复制结果 JSON, 下载结果 JSON, + 添加报价 / + 添加订单行, 删除.
- Score-only actions: `button[data-sact="add-gate|del-gate|add-weight|del-weight|add-cand|del-cand"]`.
- Quote, price, inventory, and landed fields: `[data-path="<mode>.s.<field>"]`, row fields `input[data-path^="<mode>.r."][data-path$=".<field>"]` (row ids change every render; never hardcode `r1`), baseline `[data-path="quote.b.supplier"]` and `[data-path="quote.b.net_unit"]`.
- Score fields use `[data-spath="..."]` because that form is not the scalar/row schema. The supplier box is `[data-spath="candidates.0.supplier"]`. Its label is not wired with `for`.
- Results: `#app h2` (计算未通过 or 计算结果), `#app .err`, `#app .empty`, `#app .kpi`, `#app table`. KPI text lives in `.kpi .k` and `.kpi .v`. The unit is inside `.v` with no space, for example `10.83元`.
- Page identity: `h1` is `采购决策助手 · 网页版`.

Start one browser for this run, then run a feature script. The handover proof is quote:

```bash
python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser start
bash .cursor/skills/verify-procurement-copilot/scripts/drive-quote.sh
python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser stop
```

`browser start` opens the ELF Chrome with its own `--user-data-dir` under `/tmp/procurement-copilot-verify/<id>/drive-profile`, a private debugging port, and the run URL. Later `browser` commands reconnect to that same page. Each command is literal:

- `browser goto` reloads the run URL and waits until 报价比价 is active and the QR image has decoded.
- `browser click --selector '<css>' [--nth N]`
- `browser assert-text --selector '<css>' --equals '<text>'` or `--contains '<text>'`
- `browser assert-value --selector '<css>' --equals '<value>' [--nth N]`
- `browser assert-count --selector '<css>' --equals N`
- `browser assert-kpi --label '<label>' --value '<visible value>'`
- `browser assert-absent --text '<text>'` checks the visible body, not the script source.
- `browser assert-order --selector '<css>' --sequence 'a|b|c' [--nth N]`
- `browser screenshot --name quote/04-result.png`
- `browser download --selector 'button[data-act="download"]' --name quote/result.json --filename-regex '^采购决策_quote_[0-9]{8}\.json$' --expect-mode quote --expect-metric annual_tco_cny --expect-rank1 '深科电子（示例）'`
- `browser assert-same-origin --name quote/requests.json` writes the page's performance entries and fails if any http(s) entry leaves this origin.

The other calculators use the same browser and the same command shapes:

```bash
bash .cursor/skills/verify-procurement-copilot/scripts/drive-price.sh
bash .cursor/skills/verify-procurement-copilot/scripts/drive-score.sh
bash .cursor/skills/verify-procurement-copilot/scripts/drive-inventory.sh
bash .cursor/skills/verify-procurement-copilot/scripts/drive-landed.sh
```

Run `browser goto` is already the first line of each script. Do not point these scripts at a server you did not launch. Feature files under `features/` are the map of what each script asserts.

供应商评分 needs two example passes. 载入示例 on the default form (one gate row) shows three gate labels but leaves every answer after the first as 待核实, so 沪连精密（示例） scores `0.8500` and nobody is eliminated. Click 清空, click + 添加门槛 twice, then 载入示例 again: 苏恒连接器（示例） is 不通过, the leader scores `0.7000`, and the page says 门槛未通过，淘汰. `drive-score.sh` asserts both screens. Do not change the `0.8500` assertion into `0.7000` to skip the gate-row precondition.

Percent fields show the human percent (`13`, `6`, `8`), while the calculator stores a fraction. Assert the value in the input. Money and quantities on the result cards are `zh-CN` formatted by the page (`1,302,200`, `-52,060`). Assert that visible string. A result JSON download is a side effect of 下载结果 JSON, not a substitute for the KPI text.

复制结果 JSON needs clipboard permission and is not part of the proof. 清空 resets the current calculator's inputs and result; the scripts reload instead, which is the same empty state because the page stores nothing.

## Evidence

Proof for a run lives in:

`.cursor/skills/verify-procurement-copilot/evidence/<VERIFY_RUN_ID>/`

That directory is created by launch and is never deleted by cleanup. It holds:

- `launch.txt`, `ready.dom.html` — the readiness dump and exit 0
- `doctor.txt`, `doctor.dom.html` — the Doctor verdict
- `commands.jsonl` — every `verify.py` command, its exit code, and the browser stdout/stderr
- `access.log`, `serve.log` — the stamped server
- `cleanup.txt` — which pids were stopped
- `quote/`, `price/`, `score/`, `inventory/`, `landed/` — screenshots, downloads, and request lists written by the feature scripts

Capture the action and the next visible state. For quote that is the blank error screen, the filled example, the KPI card, and the downloaded JSON. The JSON is checked for `mode`, `ranking_metric`, and the rank-1 supplier, and the KPI labels are checked on screen. `assert-same-origin` records the URLs the page actually requested. This app has no fetch and no analytics call in `index.html`. A cross-origin performance entry fails the drive. Chrome's own component traffic is not in that list; do not treat a netlog of the browser binary as the page.

Do not mock the calculators. The buttons call the in-page `compute` on the DOM values. There is no test-only endpoint.

## Cleanup

```bash
python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py cleanup
```

Cleanup reads this run's state and signals only those processes:

- the browser pid, and only when its cmdline contains this run id and `drive-profile`
- the server pid, and only when its cmdline contains `serve.py` and this run id

It then deletes `/tmp/procurement-copilot-verify/<VERIFY_RUN_ID>/`. It does not delete `evidence/<VERIFY_RUN_ID>/`. If the cmdline does not match, cleanup exits 2 and leaves the process alone. A second cleanup, after the state is gone, exits 0 and still writes `cleanup.txt` when the evidence directory exists.

After cleanup, `verify.py doctor` must exit non-zero because the instance is gone. When the evidence directory is still there, that failure is written to `doctor-after-cleanup.txt` and to `commands.jsonl`. The screenshots and the earlier `doctor.txt` must still be on disk.

Two runs may proceed together when they use different `VERIFY_RUN_ID`s. They do not share a port, a profile, or page memory. There is no shared account to corrupt. Do not kill Chrome or Python by process name.

## Helpers

All of these are verification scaffolding. Invoke them from the repo root.

- `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py launch|doctor|cleanup`
- `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser <command> ...`
- `bash .cursor/skills/verify-procurement-copilot/scripts/drive-quote.sh`
- `bash .cursor/skills/verify-procurement-copilot/scripts/drive-price.sh`
- `bash .cursor/skills/verify-procurement-copilot/scripts/drive-score.sh`
- `bash .cursor/skills/verify-procurement-copilot/scripts/drive-inventory.sh`
- `bash .cursor/skills/verify-procurement-copilot/scripts/drive-landed.sh`

`verify.py browser` runs `node .cursor/skills/verify-procurement-copilot/scripts/browser.mjs` with the same arguments. `browser.mjs` is the CDP client. `serve.py` is the HTTP server started by `launch`, not a command to run by hand except when you are reading the exact process Doctor checks. Exit 0 means the command's checks passed. Exit 1 means a check failed or the instance is not ready. Exit 2 means cleanup refused to signal a pid it does not own.

Install the browser client once per checkout with `npm install --prefix .cursor/skills/verify-procurement-copilot`. That pulls `playwright-core` only. The browser itself is the system Chrome found above, not a Playwright-managed download.

## Maintenance

When labels, example rows, selectors, or result text change, update the feature file and its `drive-*.sh` together, then re-run that script against a fresh launch. Use `/maintain-verification-skill` for that upkeep. Do not change an expected visible string without driving the page again.
