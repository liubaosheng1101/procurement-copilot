# Procurement copilot verification map

This directory is the maintained source for the five calculators in 采购决策助手. Read this index, then drive the matching feature file. The page has no other interactive calculators. The footer disclaimer and the 采购老刘 card are static.

## Baseline preconditions

- Launch with `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py launch` from the repo root.
- Export the printed `VERIFY_RUN_ID`. The server is `http://127.0.0.1:<port>/` from that launch, not GitHub Pages and not `file://`.
- `verify.py doctor` must print `DOCTOR_OK` for that id before any click.
- `verify.py browser start` once per run. Feature scripts assume that browser is up.
- Install `playwright-core` with `npm install --prefix .cursor/skills/verify-procurement-copilot` before `browser start`.
- `index.html` and `抖音码.png` must match `HEAD`. Launch already enforces this.
- The page stores nothing. A reload is a clean form. Do not expect localStorage, cookies, or seeded rows.

## Driving conventions

- Start every feature script from whatever page is open. Each script begins with `browser goto`, which reloads this run's URL.
- Prefer `data-tab`, `data-act`, `data-path`, and `data-spath` over text-only selectors. Visible Chinese strings are the assertions, not the only selectors.
- Treat every command as literal, including the fullwidth punctuation in `点「载入示例」` and `年度总成本 TCO（从低到高）`.
- Run browser actions through `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser ...`.
- KPI values include the unit with no space (`10.83元`). Comparison strips whitespace inside `.kpi .v`.
- The em dash in an empty KPI is U+2014 (`—`), the character `fmt` returns for null.
- Write screenshots and JSON under `evidence/<VERIFY_RUN_ID>/`. Cleanup must leave them there.

## Proof and skip reporting

- Capture the click and the next screen. A final KPI without the earlier error or filled inputs is an incomplete quote proof.
- UI proof is the screenshot plus the assertions in the feature script.
- The quote proof also saves the file produced by 下载结果 JSON and checks `mode`, `ranking_metric`, and the rank-1 supplier.
- `assert-same-origin` writes the page's own request URLs. A foreign origin fails the feature.
- Record the feature id in the artifact path (`quote/`, `price/`, `score/`, `inventory/`, `landed/`).
- If a selector is missing, stop and report the command and the unmet precondition. Do not drive a different calculator and call this one verified.

## Feature entry contract

Each feature file has an H1, one paragraph, then exactly these H2 sections: `Sub-features`, `How to get to it (user POV)`, `Driving it with verify.py`, `Gotchas`.

## Features

- [报价比价](./quote-comparison.md) compares offers on a normalized landed unit cost and annual TCO. This is the handover proof.
- [价格分析](./price-analysis.md) rolls purchase lines into weighted price, PPV, and supplier share.
- [供应商评分](./supplier-score.md) rejects suppliers who miss a gate, then ranks the rest.
- [库存补货](./inventory-replenishment.md) computes safety stock, reorder point, and a constrained order quantity.
- [进口到岸成本](./landed-cost.md) turns a trade term into duty, VAT, and landed cost.
