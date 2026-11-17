#!/usr/bin/env bash
# Supplier-score journey. Requires VERIFY_RUN_ID and a started browser.
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
V=(python3 "$ROOT/.cursor/skills/verify-procurement-copilot/scripts/verify.py")
if [[ -z "${VERIFY_RUN_ID:-}" ]]; then
  echo "VERIFY_RUN_ID is not set. Run launch and export it first." >&2
  exit 1
fi

"${V[@]}" browser goto
"${V[@]}" browser click --selector 'button[data-tab="score"]'
"${V[@]}" browser assert-text --selector 'button.tab.on' --equals '供应商评分'
"${V[@]}" browser assert-text --selector '#app h2' --contains '门槛校验 + 加权评分'
"${V[@]}" browser assert-value --selector '[data-spath="candidates.0.supplier"]' --equals '供应商 A'
"${V[@]}" browser assert-count --selector 'input[data-spath^="gates."][data-spath$=".label"]' --equals 1
"${V[@]}" browser click --selector 'button[data-act="run"]'
"${V[@]}" browser assert-absent --text '计算未通过'
"${V[@]}" browser assert-kpi --label '评分第一' --value '供应商 A'
"${V[@]}" browser assert-kpi --label '加权总分' --value '—'
"${V[@]}" browser assert-text --selector '#app' --contains '待补证后复评（门槛待核实）'
"${V[@]}" browser screenshot --name score/01-default-result.png

"${V[@]}" browser click --selector 'button[data-act="example"]'
"${V[@]}" browser assert-count --selector 'input[data-spath^="gates."][data-spath$=".label"]' --equals 3
"${V[@]}" browser assert-value --selector '[data-spath="candidates.0.supplier"]' --equals '沪连精密（示例）'
"${V[@]}" browser assert-value --selector '[data-spath="candidates.2.supplier"]' --equals '苏恒连接器（示例）'
"${V[@]}" browser assert-value --selector '[data-spath="weights.0.weight"]' --equals '30'
"${V[@]}" browser assert-value --selector '[data-spath="candidates.0.gates.0"]' --equals 'pass'
"${V[@]}" browser assert-value --selector '[data-spath="candidates.2.gates.1"]' --equals 'pending'
"${V[@]}" browser assert-value --selector '[data-spath="candidates.3.gates.2"]' --equals 'pending'
"${V[@]}" browser screenshot --name score/02-example-default-gates.png
"${V[@]}" browser click --selector 'button[data-act="run"]'
"${V[@]}" browser assert-kpi --label '评分第一' --value '沪连精密（示例）'
"${V[@]}" browser assert-kpi --label '加权总分' --value '0.8500'
"${V[@]}" browser assert-kpi --label '权重合计' --value '100.00%'
"${V[@]}" browser assert-text --selector '#app' --contains '待补证后复评（门槛待核实）'
"${V[@]}" browser assert-absent --text '门槛未通过，淘汰'
"${V[@]}" browser assert-order --selector '#app table' --nth 0 --sequence '沪连精密（示例）|甬新电气（示例·待补证）|苏恒连接器（示例）|深科电子（示例）'
"${V[@]}" browser screenshot --name score/03-truncated-result.png

"${V[@]}" browser click --selector 'button[data-act="clear"]'
"${V[@]}" browser assert-count --selector 'input[data-spath^="gates."][data-spath$=".label"]' --equals 1
"${V[@]}" browser click --selector 'button[data-sact="add-gate"]'
"${V[@]}" browser click --selector 'button[data-sact="add-gate"]'
"${V[@]}" browser assert-count --selector 'input[data-spath^="gates."][data-spath$=".label"]' --equals 3
"${V[@]}" browser click --selector 'button[data-act="example"]'
"${V[@]}" browser assert-value --selector '[data-spath="candidates.2.gates.1"]' --equals 'fail'
"${V[@]}" browser assert-value --selector '[data-spath="candidates.3.gates.2"]' --equals 'pending'
"${V[@]}" browser screenshot --name score/04-example-three-gates.png
"${V[@]}" browser click --selector 'button[data-act="run"]'
"${V[@]}" browser assert-kpi --label '评分第一' --value '沪连精密（示例）'
"${V[@]}" browser assert-kpi --label '加权总分' --value '0.7000'
"${V[@]}" browser assert-kpi --label '权重合计' --value '100.00%'
"${V[@]}" browser assert-text --selector '#app' --contains '门槛未通过，淘汰'
"${V[@]}" browser assert-text --selector '#app' --contains '待补证后复评（门槛待核实）'
"${V[@]}" browser assert-order --selector '#app table' --nth 0 --sequence '沪连精密（示例）|甬新电气（示例·待补证）|深科电子（示例）|苏恒连接器（示例）'
"${V[@]}" browser assert-absent --text '计算未通过'
"${V[@]}" browser screenshot --name score/05-aligned-result.png
"${V[@]}" browser assert-same-origin --name score/requests.json
