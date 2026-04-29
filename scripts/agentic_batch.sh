#!/usr/bin/env bash
# agentic-extract 批量运行脚本
#
# 用法:
#   ./scripts/agentic_batch.sh <batch-dir> <command> [args...]
#
# 命令:
#   start           启动所有任务
#   status          查看所有任务状态
#   logs <名称>     实时查看日志 (tail -f)
#   stop <名称>     停止指定任务
#   stop-all        停止所有任务
#   restart <名称>  重启指定任务
#   restart-failed  重启所有失败的任务
#
# batch-dir 目录下需要有 tasks.conf 配置文件，格式见示例。
#
# 示例:
#   ./scripts/agentic_batch.sh local/workspaces/北交所-深交所-上交所 start
#   ./scripts/agentic_batch.sh local/workspaces/北交所-深交所-上交所 status
#   ./scripts/agentic_batch.sh local/workspaces/北交所-深交所-上交所 logs 金融类利润

set -euo pipefail

# ── 颜色 ──────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── 参数检查 ──────────────────────────────────────
if [[ $# -lt 2 ]]; then
    echo "用法: $0 <batch-dir> <command> [args...]"
    echo ""
    echo "命令: start | status | logs <名称> | stop <名称> | stop-all | restart <名称> | restart-failed"
    exit 1
fi

BATCH_DIR="$1"
COMMAND="$2"
shift 2
ARGS=("$@")

CONF="$BATCH_DIR/tasks.json"
LOG_DIR="$BATCH_DIR/logs"
PID_DIR="$BATCH_DIR/.pids"

if [[ ! -f "$CONF" ]]; then
    echo "错误: 找不到配置文件 $CONF"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "错误: 需要安装 jq 来解析 JSON 配置"
    exit 1
fi

mkdir -p "$LOG_DIR" "$PID_DIR"

# ── 解析配置 ──────────────────────────────────────
TASK_NAMES=()
TASK_SET_IDS=()
TASK_MAX_ITERATIONS=()
TASK_LIMITS=()
TASK_TARGET_ACCURACIES=()
TASK_MESSAGES=()
TASK_RESETS=()
TASK_SUPERVISORS=()
TASK_PRESERVE_THINKINGS=()

# 读取默认值
DEFAULT_MAX_ITERATIONS=$(jq -r '.defaults.max_iterations // 50' "$CONF")
DEFAULT_LIMIT=$(jq -r '.defaults.limit // ""' "$CONF")
DEFAULT_TARGET_ACCURACY=$(jq -r '.defaults.target_accuracy // ""' "$CONF")
DEFAULT_RESET=$(jq -r '.defaults.reset // false' "$CONF")
DEFAULT_SUPERVISOR=$(jq -r '.defaults.supervisor // ""' "$CONF")
DEFAULT_PRESERVE_THINKING=$(jq -r '.defaults.preserve_thinking // false' "$CONF")

# 读取任务列表
TASK_COUNT=$(jq '.tasks | length' "$CONF")

for ((i=0; i<TASK_COUNT; i++)); do
    name=$(jq -r ".tasks[$i].name" "$CONF")
    set_id=$(jq -r ".tasks[$i].set_id // empty" "$CONF")
    max_iter=$(jq -r ".tasks[$i].max_iterations // \"$DEFAULT_MAX_ITERATIONS\"" "$CONF")
    limit=$(jq -r ".tasks[$i].limit // \"$DEFAULT_LIMIT\"" "$CONF")
    target_acc=$(jq -r ".tasks[$i].target_accuracy // \"$DEFAULT_TARGET_ACCURACY\"" "$CONF")
    message=$(jq -r ".tasks[$i].message // \"\"" "$CONF")
    reset=$(jq -r ".tasks[$i].reset // \"$DEFAULT_RESET\"" "$CONF")
    supervisor=$(jq -r ".tasks[$i].supervisor // \"$DEFAULT_SUPERVISOR\"" "$CONF")
    preserve_thinking=$(jq -r ".tasks[$i].preserve_thinking // \"$DEFAULT_PRESERVE_THINKING\"" "$CONF")

    TASK_NAMES+=("$name")
    TASK_SET_IDS+=("$set_id")
    TASK_MAX_ITERATIONS+=("$max_iter")
    TASK_LIMITS+=("$limit")
    TASK_TARGET_ACCURACIES+=("$target_acc")
    TASK_MESSAGES+=("$message")
    TASK_RESETS+=("$reset")
    TASK_SUPERVISORS+=("$supervisor")
    TASK_PRESERVE_THINKINGS+=("$preserve_thinking")
done

if [[ $TASK_COUNT -eq 0 ]]; then
    echo "错误: 配置文件中没有任务"
    exit 1
fi

# ── 工具函数 ──────────────────────────────────────

# 根据部分名称查找任务索引（模糊匹配）
find_task() {
    local query="$1"
    local matches=()

    for i in "${!TASK_NAMES[@]}"; do
        if [[ "${TASK_NAMES[$i]}" == "$query" ]]; then
            echo "$i"
            return 0
        fi
    done

    for i in "${!TASK_NAMES[@]}"; do
        if [[ "${TASK_NAMES[$i]}" == *"$query"* ]]; then
            matches+=("$i")
        fi
    done

    if [[ ${#matches[@]} -eq 1 ]]; then
        echo "${matches[0]}"
        return 0
    elif [[ ${#matches[@]} -gt 1 ]]; then
        echo "错误: '$query' 匹配到多个任务:" >&2
        for i in "${matches[@]}"; do
            echo "  - ${TASK_NAMES[$i]}" >&2
        done
        return 1
    else
        echo "错误: 找不到匹配 '$query' 的任务" >&2
        return 1
    fi
}

# 获取任务状态: RUNNING / DONE / FAILED / STOPPED
get_status() {
    local name="$1"
    local pid_file="$PID_DIR/$name.pid"
    local exit_file="$PID_DIR/$name.exit"
    local workspace="$BATCH_DIR/$name"
    local current_json="$workspace/.agent_state/current.json"
    local legacy_current_json="$workspace/logs/current.json"

    if [[ -f "$pid_file" ]]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "RUNNING|$pid"
            return
        fi
    fi

    if [[ ! -f "$current_json" && -f "$legacy_current_json" ]]; then
        current_json="$legacy_current_json"
    fi

    # 检查 runtime 状态文件中的实际状态
    if [[ -f "$current_json" ]]; then
        local status_line
        status_line=$(grep -o '"status":[^,}]*' "$current_json" 2>/dev/null | cut -d'"' -f4)
        if [[ "$status_line" == "completed" ]]; then
            echo "DONE|0"
            return
        elif [[ "$status_line" == failed* ]]; then
            echo "FAILED|internal"
            return
        fi
    fi

    if [[ -f "$exit_file" ]]; then
        local code
        code=$(cat "$exit_file")
        if [[ "$code" == "0" ]]; then
            echo "DONE|$code"
        else
            echo "FAILED|$code"
        fi
        return
    fi

    echo "STOPPED|"
}

# 启动单个任务
start_task() {
    local idx="$1"
    local name="${TASK_NAMES[$idx]}"
    local set_id="${TASK_SET_IDS[$idx]}"
    local max_iter="${TASK_MAX_ITERATIONS[$idx]}"
    local limit="${TASK_LIMITS[$idx]}"
    local target_acc="${TASK_TARGET_ACCURACIES[$idx]}"
    local message="${TASK_MESSAGES[$idx]}"
    local reset="${TASK_RESETS[$idx]}"
    local supervisor="${TASK_SUPERVISORS[$idx]}"
    local preserve_thinking="${TASK_PRESERVE_THINKINGS[$idx]}"
    local workspace="$BATCH_DIR/$name"
    local log_file="$LOG_DIR/$name.log"
    local pid_file="$PID_DIR/$name.pid"
    local exit_file="$PID_DIR/$name.exit"

    # 检查是否已在运行
    if [[ -f "$pid_file" ]]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "  ${YELLOW}跳过${NC} $name (已在运行, PID $pid)"
            return
        fi
    fi

    rm -f "$exit_file"

    # 构建命令参数
    local cmd_args=(
        uv run agentic-extract run
        --workspace "$workspace"
        --max-iterations "$max_iter"
    )
    if [[ -n "$set_id" ]]; then
        cmd_args+=(--set-id "$set_id")
    fi
    if [[ -n "$limit" ]]; then
        cmd_args+=(--limit "$limit")
    fi
    if [[ -n "$target_acc" ]]; then
        cmd_args+=(--target-accuracy "$target_acc")
    fi
    if [[ -n "$message" ]]; then
        cmd_args+=(--message "$message")
    fi
    if [[ "$reset" == "true" ]]; then
        cmd_args+=(--reset)
    fi
    if [[ -n "$supervisor" ]]; then
        cmd_args+=(--supervisor "$supervisor")
    fi
    if [[ "$preserve_thinking" == "true" ]]; then
        cmd_args+=(--preserve-thinking)
    fi

    # 后台启动，完成后记录退出码
    # 清除 ANTHROPIC_* 环境变量，避免与配置文件中的 api_key 冲突
    (
        unset ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL ANTHROPIC_API_KEY
        "${cmd_args[@]}" >> "$log_file" 2>&1
        echo $? > "$exit_file"
    ) &

    local pid=$!
    echo "$pid" > "$pid_file"
    echo -e "  ${GREEN}启动${NC} $name (PID $pid)"
}

# ── 命令实现 ──────────────────────────────────────

cmd_start() {
    echo -e "${BOLD}启动 $TASK_COUNT 个任务${NC}"
    echo ""
    for i in "${!TASK_NAMES[@]}"; do
        start_task "$i"
    done
    echo ""
    echo -e "日志目录: ${CYAN}$LOG_DIR${NC}"
    echo "查看状态: $0 $BATCH_DIR status"
}

cmd_status() {
    local running=0 done=0 failed=0 stopped=0

    printf "${BOLD}%-36s  %-10s  %s${NC}\n" "任务" "状态" "信息"
    printf "%-36s  %-10s  %s\n" "----" "----" "----"

    for i in "${!TASK_NAMES[@]}"; do
        local name="${TASK_NAMES[$i]}"
        local status_info
        status_info=$(get_status "$name")
        local status="${status_info%%|*}"
        local detail="${status_info##*|}"

        case "$status" in
            RUNNING)
                printf "%-36s  ${GREEN}%-10s${NC}  PID %s\n" "$name" "RUNNING" "$detail"
                ((running++)) || true
                ;;
            DONE)
                printf "%-36s  ${CYAN}%-10s${NC}  exit %s\n" "$name" "DONE" "$detail"
                ((done++)) || true
                ;;
            FAILED)
                printf "%-36s  ${RED}%-10s${NC}  exit %s\n" "$name" "FAILED" "$detail"
                ((failed++)) || true
                ;;
            STOPPED)
                printf "%-36s  ${YELLOW}%-10s${NC}\n" "$name" "STOPPED"
                ((stopped++)) || true
                ;;
        esac
    done

    echo ""
    echo -e "合计: ${GREEN}运行中 $running${NC}  ${CYAN}完成 $done${NC}  ${RED}失败 $failed${NC}  ${YELLOW}未启动 $stopped${NC}"
}

cmd_logs() {
    if [[ ${#ARGS[@]} -eq 0 ]]; then
        echo "用法: $0 $BATCH_DIR logs <任务名称>"
        exit 1
    fi

    local idx
    idx=$(find_task "${ARGS[0]}") || exit 1
    local name="${TASK_NAMES[$idx]}"
    local log_file="$LOG_DIR/$name.log"

    if [[ ! -f "$log_file" ]]; then
        echo "日志文件不存在: $log_file"
        exit 1
    fi

    echo -e "${BOLD}实时日志: $name${NC}"
    echo -e "文件: ${CYAN}$log_file${NC}"
    echo "按 Ctrl+C 退出"
    echo "---"
    tail -f "$log_file"
}

cmd_stop() {
    if [[ ${#ARGS[@]} -eq 0 ]]; then
        echo "用法: $0 $BATCH_DIR stop <任务名称>"
        exit 1
    fi

    local idx
    idx=$(find_task "${ARGS[0]}") || exit 1
    local name="${TASK_NAMES[$idx]}"
    local pid_file="$PID_DIR/$name.pid"

    if [[ ! -f "$pid_file" ]]; then
        echo "$name: 没有 PID 文件"
        return
    fi

    local pid
    pid=$(cat "$pid_file")

    if kill -0 "$pid" 2>/dev/null; then
        # 先杀子进程，再杀主进程
        pkill -P "$pid" 2>/dev/null || true
        kill "$pid" 2>/dev/null || true
        echo -e "${YELLOW}已停止${NC} $name (PID $pid)"
    else
        echo "$name: 进程已不在运行"
    fi

    rm -f "$pid_file"
}

cmd_stop_all() {
    echo -e "${BOLD}停止所有任务${NC}"
    for i in "${!TASK_NAMES[@]}"; do
        local name="${TASK_NAMES[$i]}"
        local pid_file="$PID_DIR/$name.pid"

        if [[ -f "$pid_file" ]]; then
            local pid
            pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                pkill -P "$pid" 2>/dev/null || true
                kill "$pid" 2>/dev/null || true
                echo -e "  ${YELLOW}已停止${NC} $name (PID $pid)"
            fi
            rm -f "$pid_file"
        fi
    done
}

cmd_restart() {
    if [[ ${#ARGS[@]} -eq 0 ]]; then
        echo "用法: $0 $BATCH_DIR restart <任务名称>"
        exit 1
    fi

    local idx
    idx=$(find_task "${ARGS[0]}") || exit 1
    local name="${TASK_NAMES[$idx]}"

    local status_info
    status_info=$(get_status "$name")
    local status="${status_info%%|*}"

    if [[ "$status" == "RUNNING" ]]; then
        echo "错误: $name 正在运行中，请先 stop"
        exit 1
    fi

    local log_file="$LOG_DIR/$name.log"
    echo "" >> "$log_file" 2>/dev/null || true
    echo "=== RESTART at $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$log_file"

    echo -e "${BOLD}重启任务: $name${NC}"
    start_task "$idx"
}

cmd_restart_failed() {
    echo -e "${BOLD}重启所有失败的任务${NC}"
    local count=0

    for i in "${!TASK_NAMES[@]}"; do
        local name="${TASK_NAMES[$i]}"
        local status_info
        status_info=$(get_status "$name")
        local status="${status_info%%|*}"

        if [[ "$status" == "FAILED" ]]; then
            local log_file="$LOG_DIR/$name.log"
            echo "" >> "$log_file" 2>/dev/null || true
            echo "=== RESTART at $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$log_file"

            start_task "$i"
            ((count++)) || true
        fi
    done

    if [[ $count -eq 0 ]]; then
        echo "没有失败的任务"
    else
        echo ""
        echo "已重启 $count 个任务"
    fi
}

# ── 命令分发 ──────────────────────────────────────

case "$COMMAND" in
    start)          cmd_start ;;
    status)         cmd_status ;;
    logs)           cmd_logs ;;
    stop)           cmd_stop ;;
    stop-all)       cmd_stop_all ;;
    restart)        cmd_restart ;;
    restart-failed) cmd_restart_failed ;;
    *)
        echo "未知命令: $COMMAND"
        echo "可用命令: start | status | logs | stop | stop-all | restart | restart-failed"
        exit 1
        ;;
esac
