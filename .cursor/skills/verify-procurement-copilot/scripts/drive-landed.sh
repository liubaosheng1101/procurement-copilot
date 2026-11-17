#!/usr/bin/env bash
# Landed-cost journey. Requires VERIFY_RUN_ID and a started browser.
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
V=(python3 "$ROOT/.cursor/skills/verify-procurement-copilot/scripts/verify.py")
if [[ -z "${VERIFY_RUN_ID:-}" ]]; then
  echo "VERIFY_RUN_ID is not set. Run launch and export it first." >&2
  exit 1
fi

"${V[@]}" browser goto
"${V[@]}" browser click --selector 'button[data-tab="landed"]'
"${V[@]}" browser assert-text --selector 'button.tab.on' --equals '进口到岸成本'
"${V[@]}" browser assert-text --selector '#app h2' --contains '进口 landed cost 测算'
"${V[@]}" browser assert-text --selector '#app .empty' --contains '点「载入示例」'
"${V[@]}" browser click --selector 'button[data-act="run"]'
"${V[@]}" browser assert-text --selector '#app .err' --contains '缺少必填字段: fx_rate'
"${V[@]}" browser screenshot --name landed/01-blank-error.png

"${V[@]}" browser click --selector 'button[data-act="example"]'
"${V[@]}" browser assert-value --selector '[data-path="landed.s.trade_term"]' --equals 'FOB'
"${V[@]}" browser assert-value --selector '[data-path="landed.s.fx_rate"]' --equals '7.12'
"${V[@]}" browser assert-value --selector '[data-path="landed.s.quantity"]' --equals '10000'
"${V[@]}" browser assert-value --selector '[data-path="landed.s.duty_rate"]' --equals '8'
"${V[@]}" browser assert-value --selector '[data-path="landed.s.vat_rate"]' --equals '13'
"${V[@]}" browser screenshot --name landed/02-example-filled.png
"${V[@]}" browser click --selector 'button[data-act="run"]'
"${V[@]}" browser assert-kpi --label '到岸总成本' --value '408,626元'
"${V[@]}" browser assert-kpi --label '单位到岸成本' --value '40.86元'
"${V[@]}" browser assert-kpi --label '完税价格' --value '375,580元'
"${V[@]}" browser assert-kpi --label '关税' --value '30,046元'
"${V[@]}" browser assert-kpi --label '增值税' --value '52,731元'
"${V[@]}" browser assert-kpi --label '综合税负率' --value '8.00%'
"${V[@]}" browser assert-text --selector '#app' --contains '可抵扣：不进成本，单列垫付资金'
"${V[@]}" browser assert-text --selector '#app' --contains '贸易术语 FOB'
"${V[@]}" browser assert-absent --text '计算未通过'
"${V[@]}" browser screenshot --name landed/03-result.png
"${V[@]}" browser assert-same-origin --name landed/requests.json
