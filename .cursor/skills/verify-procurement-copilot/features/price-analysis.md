# 价格分析

价格分析 rolls order lines into a weighted average price, period-on-period change, PPV against a baseline, and each supplier's share of spend.

## Sub-features

- `price-open` opens 采购价格趋势 from the 价格分析 tab.
- `price-blank-error` shows 计算未通过 when the blank order rows are calculated.
- `price-example` loads eight sample order lines and baseline `11.68`.
- `price-wap` shows the weighted price, total quantity, total spend, and the first-to-last change.
- `price-share` shows 深科电子（示例） as the largest share.

## How to get to it (user POV)

- Choose the 价格分析 tab.

## Driving it with verify.py

Preconditions:

- Doctor printed `DOCTOR_OK` for this `VERIFY_RUN_ID`.
- `verify.py browser start` has already opened this run's URL.
- The executable copy of this journey is `bash .cursor/skills/verify-procurement-copilot/scripts/drive-price.sh`.

- **Open the tab.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser goto` and `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-tab="price"]'`. The active tab reads 价格分析 and the heading contains 采购价格趋势.
- **Blank calculate.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-act="run"]'`. `.err` contains `缺少必填字段: orders[0].qty`.
- **Load the example.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-act="example"]'`. Baseline is `11.68`, the first supplier box is `沪连精密（示例）`, and there are 8 `.rowcard` rows.
- **Calculate.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-act="run"]'`. 加权均价 is `11.14元`, 总采购量 is `97,000`, 总金额 is `1,080,900元`, 首→末期间变化 is `-7.16%`, and PPV 采购价差 is `-52,060元`.
- **Supplier share.** The second `#app table` lists 深科电子（示例）, then 沪连精密（示例）, then 苏恒连接器（示例）. The page contains `60.14%`.
- **Page requests.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser assert-same-origin --name price/requests.json`.
- **Proof.** The script writes `price/01-blank-error.png`, `price/02-example-filled.png`, and `price/03-result.png`.

## Gotchas

- A fresh 价格分析 form fails on quantity, not on the missing period. The message is `缺少必填字段: orders[0].qty`.
- The example has eight lines, not the four blank rows the empty form starts with.
- PPV for this example is negative (`-52,060元`). That is the visible result.
- Share is on the second table. Pass `--nth 1` to `assert-order`. The first table is periods.
- Percent fields on the rows show `13` for a 0.13 tax rate.
