#!/usr/bin/env bash
# Quote comparison journey. Requires VERIFY_RUN_ID and a started browser.
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
V=(python3 "$ROOT/.cursor/skills/verify-procurement-copilot/scripts/verify.py")
if [[ -z "${VERIFY_RUN_ID:-}" ]]; then
  echo "VERIFY_RUN_ID is not set. Run launch and export it first." >&2
  exit 1
fi

"${V[@]}" browser goto
"${V[@]}" browser click --selector 'button[data-tab="quote"]'
"${V[@]}" browser assert-text --selector h1 --equals '采购决策助手 · 网页版'
"${V[@]}" browser assert-text --selector 'button.tab.on' --equals '报价比价'
"${V[@]}" browser assert-text --selector '#app h2' --contains '多份报价横向比价'
"${V[@]}" browser assert-text --selector '#app .empty' --contains '点「载入示例」'
"${V[@]}" browser screenshot --name quote/01-initial.png

"${V[@]}" browser click --selector 'button[data-act="run"]'
"${V[@]}" browser assert-text --selector '#app h2' --contains '计算未通过'
"${V[@]}" browser assert-text --selector '#app .err' --contains '缺少必填字段: offers[0].supplier'
"${V[@]}" browser screenshot --name quote/02-blank-error.png

"${V[@]}" browser click --selector 'button[data-act="example"]'
"${V[@]}" browser assert-value --selector '[data-path="quote.s.annual_demand"]' --equals '120000'
"${V[@]}" browser assert-value --selector '[data-path="quote.s.capital_cost_annual"]' --equals '6'
"${V[@]}" browser assert-value --selector 'input[data-path^="quote.r."][data-path$=".supplier"]' --nth 0 --equals '沪连精密（示例）'
"${V[@]}" browser assert-value --selector 'input[data-path^="quote.r."][data-path$=".supplier"]' --nth 1 --equals '深科电子（示例）'
"${V[@]}" browser assert-value --selector 'input[data-path^="quote.r."][data-path$=".supplier"]' --nth 2 --equals '苏恒连接器（示例·小规模3%）'
"${V[@]}" browser assert-value --selector '[data-path="quote.b.supplier"]' --equals '现供应商（近6月加权净价）'
"${V[@]}" browser assert-value --selector '[data-path="quote.b.net_unit"]' --equals '11.68'
"${V[@]}" browser assert-absent --text '计算未通过'
"${V[@]}" browser assert-text --selector '#app .empty' --contains '点「载入示例」'
"${V[@]}" browser screenshot --name quote/03-example-filled.png

"${V[@]}" browser click --selector 'button[data-act="run"]'
"${V[@]}" browser assert-kpi --label '综合最优' --value '深科电子（示例）'
"${V[@]}" browser assert-kpi --label '到厂单位成本' --value '10.83元'
"${V[@]}" browser assert-kpi --label '年度总成本 TCO' --value '1,302,200元'
"${V[@]}" browser assert-kpi --label '相对基线年节降' --value '102,396元'
"${V[@]}" browser assert-text --selector '#app' --contains '年度总成本 TCO（从低到高）'
"${V[@]}" browser assert-text --selector '#app' --contains '现供应商（近6月加权净价）'
"${V[@]}" browser assert-order --selector '#app table' --sequence '深科电子（示例）|沪连精密（示例）|苏恒连接器（示例·小规模3%）'
"${V[@]}" browser assert-absent --text '计算未通过'
"${V[@]}" browser screenshot --name quote/04-result.png

"${V[@]}" browser download \
  --selector 'button[data-act="download"]' \
  --name quote/result.json \
  --filename-regex '^采购决策_quote_[0-9]{8}\.json$' \
  --expect-mode quote \
  --expect-metric annual_tco_cny \
  --expect-rank1 '深科电子（示例）'
"${V[@]}" browser assert-same-origin --name quote/requests.json
