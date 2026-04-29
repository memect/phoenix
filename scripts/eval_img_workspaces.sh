#!/usr/bin/env bash
# 批量并行执行 extract-dev train 评估
#
# 用法:
#   bash scripts/eval_img_workspaces.sh

set -euo pipefail

WORKSPACE_BASE="local/workspaces/img"
LOG_DIR="/tmp/eval_logs"
mkdir -p "$LOG_DIR"

WORKSPACES=(
  img_core_production
  img_revenue_by_industry
  img_revenue_by_product
  img_revenue_by_region
  img_balance_sheet_efficiency
  img_profitability_expenses
  img_cashflow_capex
  img_rd_hr_efficiency
  img_investment_valuation
)

PIDS=()
for name in "${WORKSPACES[@]}"; do
  ws="$WORKSPACE_BASE/$name"
  log="$LOG_DIR/${name}.log"

  if [[ ! -f "$ws/program.py" ]]; then
    echo "[跳过] $name: 无 program.py"
    continue
  fi

  echo "[启动] $name -> $log"
  uv run extract-dev --workspace "$ws" train --show-details > "$log" 2>&1 &
  PIDS+=("$!:$name")
done

# 等待所有完成，收集结果
echo ""
echo "等待所有评估完成..."
echo ""

FAIL=0
for entry in "${PIDS[@]}"; do
  pid="${entry%%:*}"
  name="${entry##*:}"
  if wait "$pid"; then
    status="✓"
  else
    status="✗"
    FAIL=$((FAIL + 1))
  fi
  # 提取准确率行
  acc=$(grep -E "Overall Accuracy|整体准确率|overall_accuracy" "$LOG_DIR/${name}.log" 2>/dev/null | tail -1 || echo "N/A")
  printf "%-35s %s  %s\n" "$name" "$status" "$acc"
done

echo ""
echo "详细日志: $LOG_DIR/"
[[ $FAIL -gt 0 ]] && echo "有 $FAIL 个评估失败" || echo "全部完成"
