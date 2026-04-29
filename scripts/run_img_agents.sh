#!/usr/bin/env bash
# 幂等启动 img workspace 的 agentscope-agent
#
# 用法:
#   bash scripts/run_img_agents.sh              # 启动所有
#   bash scripts/run_img_agents.sh status       # 查看状态
#   bash scripts/run_img_agents.sh stop         # 停止所有
#   bash scripts/run_img_agents.sh <name>       # 启动单个（如 img_core_production）

set -euo pipefail

WORKSPACE_BASE="local/workspaces/img"
LOG_DIR="/tmp/agent_logs"
PID_DIR="/tmp/agent_pids"
STUDIO_URL="http://127.0.0.1:3000"

mkdir -p "$LOG_DIR" "$PID_DIR"

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

# 检查进程是否存活
is_running() {
  local name="$1"
  local pid_file="$PID_DIR/${name}.pid"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    # pid 文件存在但进程已死，清理
    rm -f "$pid_file"
  fi
  return 1
}

# 启动单个 agent
start_one() {
  local name="$1"
  local ws="$WORKSPACE_BASE/$name"
  local log="$LOG_DIR/${name}.log"
  local pid_file="$PID_DIR/${name}.pid"

  if is_running "$name"; then
    local pid
    pid=$(cat "$pid_file")
    echo "[跳过] $name 已在运行 (PID $pid)"
    return 0
  fi

  if [[ ! -f "$ws/user_message.md" ]]; then
    echo "[错误] $name: 缺少 user_message.md"
    return 1
  fi

  echo "[启动] $name -> $log"
  nohup uv run agentscope-agent run \
    --unlabeled \
    --workspace "$ws" \
    --studio-url "$STUDIO_URL" \
    --reset \
    --user-message-file "$ws/user_message.md" \
    > "$log" 2>&1 &

  local pid=$!
  echo "$pid" > "$pid_file"
  echo "        PID=$pid"
}

# 停止单个 agent
stop_one() {
  local name="$1"
  local pid_file="$PID_DIR/${name}.pid"

  if ! is_running "$name"; then
    echo "[停止] $name 未在运行"
    return 0
  fi

  local pid
  pid=$(cat "$pid_file")
  echo "[停止] $name (PID $pid)"
  kill "$pid" 2>/dev/null || true
  rm -f "$pid_file"
}

# 显示所有状态
show_status() {
  printf "%-35s %-8s %-8s %s\n" "WORKSPACE" "STATUS" "PID" "LOG"
  printf "%-35s %-8s %-8s %s\n" "---------" "------" "---" "---"
  for name in "${WORKSPACES[@]}"; do
    local pid_file="$PID_DIR/${name}.pid"
    local log="$LOG_DIR/${name}.log"
    if is_running "$name"; then
      local pid
      pid=$(cat "$pid_file")
      printf "%-35s %-8s %-8s %s\n" "$name" "运行中" "$pid" "$log"
    else
      printf "%-35s %-8s %-8s %s\n" "$name" "已停止" "-" "$log"
    fi
  done
}

# 主逻辑
case "${1:-start}" in
  status)
    show_status
    ;;
  stop)
    for name in "${WORKSPACES[@]}"; do
      stop_one "$name"
    done
    ;;
  start)
    for name in "${WORKSPACES[@]}"; do
      start_one "$name"
    done
    echo ""
    echo "日志目录: $LOG_DIR"
    echo "查看状态: bash $0 status"
    ;;
  *)
    # 单个 workspace 名称
    found=false
    for name in "${WORKSPACES[@]}"; do
      if [[ "$name" == "$1" ]]; then
        start_one "$name"
        found=true
        break
      fi
    done
    if ! $found; then
      echo "未知参数: $1"
      echo "用法: $0 [start|status|stop|<workspace_name>]"
      exit 1
    fi
    ;;
esac
