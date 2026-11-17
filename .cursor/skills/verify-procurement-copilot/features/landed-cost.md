# 进口到岸成本

进口到岸成本 builds a customs value from the trade term, then adds duty and the non-creditable part of VAT to produce a landed total and a unit cost. The built-in example is an FOB shipment whose VAT stays out of cost.

## Sub-features

- `landed-open` opens 进口 landed cost 测算 from the 进口到岸成本 tab.
- `landed-blank-error` shows 计算未通过 when the rate and quantity fields are empty.
- `landed-example` loads the FOB sample: rate `7.12`, quantity `10000`, duty `8`, VAT `13`.
- `landed-total` shows landed total `408,626元` and unit cost `40.86元`.
- `landed-vat` shows VAT `52,731元` with the note that deductible VAT is not in the cost.

## How to get to it (user POV)

- Choose the 进口到岸成本 tab.

## Driving it with verify.py

Preconditions:

- Doctor printed `DOCTOR_OK` for this `VERIFY_RUN_ID`.
- `verify.py browser start` has already opened this run's URL.
- The executable copy of this journey is `bash .cursor/skills/verify-procurement-copilot/scripts/drive-landed.sh`.

- **Open the tab.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser goto` and `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-tab="landed"]'`. The heading contains 进口 landed cost 测算.
- **Blank calculate.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-act="run"]'`. `.err` contains `缺少必填字段: fx_rate`.
- **Load the example.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-act="example"]'`. 贸易术语 is `FOB`, 汇率 is `7.12`, 数量 is `10000`, 关税率 shows `8`, and 增值税率 shows `13`.
- **Calculate.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-act="run"]'`. 到岸总成本 is `408,626元`, 单位到岸成本 is `40.86元`, 完税价格 is `375,580元`, 关税 is `30,046元`, 增值税 is `52,731元`, and 综合税负率 is `8.00%`.
- **VAT note.** The page contains `可抵扣：不进成本，单列垫付资金` and `贸易术语 FOB`.
- **Page requests.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser assert-same-origin --name landed/requests.json`.
- **Proof.** The script writes `landed/01-blank-error.png`, `landed/02-example-filled.png`, and `landed/03-result.png`.

## Gotchas

- The blank form's first missing required number is `fx_rate`. The trade-term select still has a value because the browser selects EXW when nothing is marked selected.
- Duty and VAT inputs show `8` and `13`, not `0.08` and `0.13`.
- Deductible VAT is visible as its own KPI and is excluded from the landed total. The note is `可抵扣：不进成本，单列垫付资金`.
- The page always adds a scenario warning that duty and VAT are not a customs ruling. That warning is not 计算未通过.
- 综合税负率 renders as `8.00%` inside the KPI value.
