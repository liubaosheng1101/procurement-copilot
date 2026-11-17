#!/usr/bin/env bash
# Price-analysis journey. Requires VERIFY_RUN_ID and a started browser.
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
V=(python3 "$ROOT/.cursor/skills/verify-procurement-copilot/scripts/verify.py")
if [[ -z "${VERIFY_RUN_ID:-}" ]]; then
  echo "VERIFY_RUN_ID is not set. Run launch and export it first." >&2
  exit 1
fi

"${V[@]}" browser goto
"${V[@]}" browser click --selector 'button[data-tab="price"]'
"${V[@]}" browser assert-text --selector 'button.tab.on' --equals '价格分析'
"${V[@]}" browser assert-text --selector '#app h2' --contains '采购价格趋势'
"${V[@]}" browser assert-text --selector '#app .empty' --contains '点「载入示例」'
"${V[@]}" browser click --selector 'button[data-act="run"]'
"${V[@]}" browser assert-text --selector '#app .err' --contains '缺少必填字段: orders[0].qty'
"${V[@]}" browser screenshot --name price/01-blank-error.png

"${V[@]}" browser click --selector 'button[data-act="example"]'
"${V[@]}" browser assert-value --selector '[data-path="price.s.baseline_price"]' --equals '11.68'
"${V[@]}" browser assert-value --selector 'input[data-path^="price.r."][data-path$=".supplier"]' --nth 0 --equals '沪连精密（示例）'
"${V[@]}" browser assert-count --selector '#app .rowcard' --equals 8
"${V[@]}" browser screenshot --name price/02-example-filled.png
"${V[@]}" browser click --selector 'button[data-act="run"]'
"${V[@]}" browser assert-kpi --label '加权均价' --value '11.14元'
"${V[@]}" browser assert-kpi --label '总采购量' --value '97,000'
"${V[@]}" browser assert-kpi --label '总金额' --value '1,080,900元'
"${V[@]}" browser assert-kpi --label '首→末期间变化' --value '-7.16%'
"${V[@]}" browser assert-kpi --label 'PPV 采购价差' --value '-52,060元'
"${V[@]}" browser assert-text --selector '#app' --contains '60.14%'
"${V[@]}" browser assert-order --selector '#app table' --nth 1 --sequence '深科电子（示例）|沪连精密（示例）|苏恒连接器（示例）'
"${V[@]}" browser assert-absent --text '计算未通过'
"${V[@]}" browser screenshot --name price/03-result.png
"${V[@]}" browser assert-same-origin --name price/requests.json
