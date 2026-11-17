# 库存补货

库存补货 computes usable stock, safety stock, a reorder point, and an order quantity rounded up to MOQ and the order multiple. The built-in example does not need a new order.

## Sub-features

- `inventory-open` opens 安全库存与补货点 from the 库存补货 tab.
- `inventory-blank-error` shows 计算未通过 when the required stock fields are empty.
- `inventory-example` loads the X20 snapshot for 一号仓.
- `inventory-rop` shows safety stock `1,690`, ROP `6,310`, and on-hand position `9,500`.
- `inventory-no-order` shows a suggested order of `0` because the position is above the reorder point.

## How to get to it (user POV)

- Choose the 库存补货 tab.

## Driving it with verify.py

Preconditions:

- Doctor printed `DOCTOR_OK` for this `VERIFY_RUN_ID`.
- `verify.py browser start` has already opened this run's URL.
- The executable copy of this journey is `bash .cursor/skills/verify-procurement-copilot/scripts/drive-inventory.sh`.

- **Open the tab.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser goto` and `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-tab="inventory"]'`. The heading contains 安全库存与补货点.
- **Blank calculate.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-act="run"]'`. `.err` contains `缺少必填字段: on_hand`.
- **Load the example.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-act="example"]'`. 账面库存 is `8200`, 物料 is `工业连接器 X20（示例物料）`, and 仓库 is `一号仓`.
- **Calculate.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser click --selector 'button[data-act="run"]'`. 建议下单量 is `0`, 再订货点 ROP is `6,310`, 安全库存 is `1,690`, 当前库存头寸 is `9,500`, 可用库存 is `7,000`, and 可供天数 is `28.8天`.
- **No replenishment warning.** The visible text does not contain `库存头寸低于再订货点`.
- **Page requests.** Run `python3 .cursor/skills/verify-procurement-copilot/scripts/verify.py browser assert-same-origin --name inventory/requests.json`.
- **Proof.** The script writes `inventory/01-blank-error.png`, `inventory/02-example-filled.png`, and `inventory/03-result.png`.

## Gotchas

- A suggested order of `0` is the correct example result. Position `9,500` is above ROP `6,310`, so the page must not show `库存头寸低于再订货点`.
- The blank form fails on `on_hand` even though several other fields default to 0.
- 可供天数 renders as `28.8天` inside the KPI value.
- There is no row list on this calculator. Fields are `[data-path="inventory.s.<field>"]`.
