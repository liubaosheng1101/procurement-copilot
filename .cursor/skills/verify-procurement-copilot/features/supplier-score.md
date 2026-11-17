# 供应商评分

供应商评分 drops any supplier who fails a gate, then min-max normalizes the remaining metrics and weights them. What 载入示例 shows depends on how many gate rows are already on the form.

## Sub-features

- `score-open` opens 门槛校验 + 加权评分 from the 供应商评分 tab.
- `score-default` calculates the untouched default form instead of showing 计算未通过.
- `score-example-default-gates` loads the example onto the one default gate row. Extra gate answers become 待核实, 沪连精密（示例） scores `0.8500`, and nobody is eliminated.
- `score-example-three-gates` adds two gate rows first. The same example then fails 苏恒连接器（示例） and scores 沪连精密（示例） at `0.7000`.

## How to get to it (user POV)

- Choose the 供应商评分 tab.
- Choose + 添加门槛 when the example's extra gate answers need somewhere to land.

## Driving it with verify.py

Preconditions:

- Doctor printed `DOCTOR_OK` for this `VERIFY_RUN_ID`.
- `verify.py browser start` has already opened this run's URL.
- The executable copy of this journey is `bash .cursor/skills/verify-procurement-copilot/scripts/drive-score.sh`.

- **Open the tab.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser goto` and `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-tab="score"]'`. The heading contains 门槛校验 + 加权评分. `[data-spath="candidates.0.supplier"]` is `供应商 A`. There is 1 gate label.
- **Calculate the default.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-act="run"]'`. There is no 计算未通过 heading. 评分第一 is `供应商 A`, 加权总分 is `—`, and the page contains `待补证后复评（门槛待核实）`.
- **Load the example on one gate row.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-act="example"]'`. Three gate labels appear. The first supplier is `沪连精密（示例）`, the third is `苏恒连接器（示例）`, and the first weight is `30`. `[data-spath="candidates.2.gates.1"]` is `pending`, not `fail`.
- **Calculate that screen.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-act="run"]'`. 评分第一 is `沪连精密（示例）`, 加权总分 is `0.8500`, and 权重合计 is `100.00%`. The first ranking table order is 沪连精密（示例）, 甬新电气（示例·待补证）, 苏恒连接器（示例）, 深科电子（示例）. Pass `--nth 0` because a second table lists the normalized metrics. The body contains `待补证后复评（门槛待核实）` and does not contain `门槛未通过，淘汰`.
- **Make room for every gate answer.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-act="clear"]'`, then `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-sact="add-gate"]'` twice. The form has 3 empty gate rows.
- **Load the example again.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-act="example"]'`. `[data-spath="candidates.2.gates.1"]` is `fail` and `[data-spath="candidates.3.gates.2"]` is `pending`.
- **Calculate the aligned example.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-act="run"]'`. 评分第一 is `沪连精密（示例）`, 加权总分 is `0.7000`, and 权重合计 is `100.00%`. The page contains `门槛未通过，淘汰` and `待补证后复评（门槛待核实）`. The first ranking table order is 沪连精密（示例）, 甬新电气（示例·待补证）, 深科电子（示例）, 苏恒连接器（示例）. Pass `--nth 0`.
- **Page requests.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser assert-same-origin --name score/requests.json`.
- **Proof.** The script writes `score/01-default-result.png`, `score/02-example-default-gates.png`, `score/03-truncated-result.png`, `score/04-example-three-gates.png`, and `score/05-aligned-result.png`.

## Gotchas

- The fresh score form is already calculable. 开始计算 does not show 计算未通过. The default supplier name is `供应商 A`, and the empty score renders as U+2014 `—`.
- 载入示例 keeps only as many gate answers as gate rows already on screen, then shows the example's three labels. The default form has one row, so answers two and three come back as 待核实. 苏恒连接器（示例） is not eliminated on that path, and the leader's visible score is `0.8500`.
- Do not replace the `0.8500` check with `0.7000`. The `0.7000` result is the second journey, after 清空 and two clicks on + 添加门槛.
- Score inputs use `data-spath`, not `data-path`. The supplier field has no `for` label.
- Weights are typed as percents (`30`). Assert the input value `30`.
- 苏恒连接器（示例） in this module has no `·小规模3%` suffix. That suffix belongs to the quote example only.
- A missing metric is not a zero. On the aligned example, 甬新电气（示例·待补证） stays ranked with `待补证后复评（门槛待核实）`.
- Elimination is the sentence `门槛未通过，淘汰`, not a missing row. It appears only after the three-gate example.
