#!/usr/bin/env bash
# Inventory replenishment journey. Requires VERIFY_RUN_ID and a started browser.
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
V=(python3 "$ROOT/.cursor/skills/verify-procurement-copilot/scripts/verify.py")
if [[ -z "${VERIFY_RUN_ID:-}" ]]; then
  echo "VERIFY_RUN_ID is not set. Run launch and export it first." >&2
  exit 1
fi

"${V[@]}" browser goto
"${V[@]}" browser click --selector 'button[data-tab="inventory"]'
"${V[@]}" browser assert-text --selector 'button.tab.on' --equals '库存补货'
"${V[@]}" browser assert-text --selector '#app h2' --contains '安全库存与补货点'
"${V[@]}" browser assert-text --selector '#app .empty' --contains '点「载入示例」'
"${V[@]}" browser click --selector 'button[data-act="run"]'
"${V[@]}" browser assert-text --selector '#app .err' --contains '缺少必填字段: on_hand'
"${V[@]}" browser screenshot --name inventory/01-blank-error.png

"${V[@]}" browser click --selector 'button[data-act="example"]'
"${V[@]}" browser assert-value --selector '[data-path="inventory.s.on_hand"]' --equals '8200'
"${V[@]}" browser assert-value --selector '[data-path="inventory.s.item"]' --equals '工业连接器 X20（示例物料）'
"${V[@]}" browser assert-value --selector '[data-path="inventory.s.warehouse"]' --equals '一号仓'
"${V[@]}" browser screenshot --name inventory/02-example-filled.png
"${V[@]}" browser click --selector 'button[data-act="run"]'
"${V[@]}" browser assert-kpi --label '建议下单量' --value '0'
"${V[@]}" browser assert-kpi --label '再订货点 ROP' --value '6,310'
"${V[@]}" browser assert-kpi --label '安全库存' --value '1,690'
"${V[@]}" browser assert-kpi --label '当前库存头寸' --value '9,500'
"${V[@]}" browser assert-kpi --label '可用库存' --value '7,000'
"${V[@]}" browser assert-kpi --label '可供天数' --value '28.8天'
"${V[@]}" browser assert-absent --text '库存头寸低于再订货点'
"${V[@]}" browser assert-absent --text '计算未通过'
"${V[@]}" browser screenshot --name inventory/03-result.png
"${V[@]}" browser assert-same-origin --name inventory/requests.json
