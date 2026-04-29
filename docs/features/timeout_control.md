# 超时控制功能

AgentScope Agent 的运行时间控制和超时提醒机制。

## 功能概述

超时控制功能包含两个部分：

1. **超时提醒** - 在运行时间接近限制时，通过 system 消息提醒 agent
2. **强制中断** - 超过时间限制后，调用 agent 的 `interrupt()` 方法强制停止

## 配置参数

### CLI 参数

```bash
agentscope-agent run \
  --run-timeout 3600 \           # 运行总时长限制（秒）
  --no-timeout-reminder          # 禁用超时提醒（可选）
```

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ASA_RUN_TIMEOUT` | 运行总时长限制（秒） | None（不限制） |
| `ASA_TIMEOUT_REMINDER_ENABLED` | 是否启用超时提醒 | true |
| `ASA_TIMEOUT_REMINDER_START` | 从剩余多少秒开始提醒 | 1800（30分钟） |
| `ASA_TIMEOUT_REMINDER_INTERVAL` | 普通提醒间隔 | 300（5分钟） |
| `ASA_TIMEOUT_COUNTDOWN_THRESHOLD` | 进入倒数模式的阈值 | 300（5分钟） |
| `ASA_TIMEOUT_TEARDOWN` | 超时后的缓冲时间 | 60（1分钟） |

## 工作流程

```
0                                      run_timeout              run_timeout + teardown
|------------------------------------------|--------------------------|
                                           |                          |
                        开始提醒 ←─────────┘                          |
                        （剩余 30 分钟）                               |
                                                                      |
                        倒数模式 ←─────────── 剩余 5 分钟              |
                        （每轮提醒）                                   |
                                                                      |
                        最后一轮提醒 ←────── 剩余 < 60 秒              |
                                                                      |
                                           循环检测超时 ───────────────┤
                                           （进入 teardown）           |
                                                                      |
                                                    强制中断 agents ←─┘
```

## 提醒消息

### 普通提醒（剩余 5-30 分钟）
每隔 5 分钟提醒一次：
```
⏰ 剩余时间: 25 分钟
```

### 倒数模式（剩余 ≤ 5 分钟）
每轮都提醒：
```
⏰ 倒计时: 剩余 3 分 20 秒，请尽快收尾。
```

### 最后一轮（剩余 < 60 秒）
```
⏰ 这是最后一轮，请交付你的工作。
```

## 强制中断机制

当 `run_timeout + teardown` 时间到达后：

1. 按顺序调用 `interrupt()` 方法：
   - 先中断 ExtractDevAgent
   - 再中断 Supervisor
2. 循环检测到超时后退出
3. 自动提交工作区

## 代码使用

### 基本用法

```python
from agentscope_agent.workflow import run_extract_dev_agent

run_extract_dev_agent(
    model="openai/gpt-4",
    api_base="https://api.openai.com/v1",
    api_key="...",
    run_timeout=3600,  # 1 小时
)
```

### 自定义提醒配置

```python
run_extract_dev_agent(
    model="openai/gpt-4",
    api_base="https://api.openai.com/v1",
    api_key="...",
    run_timeout=3600,
    timeout_reminder_enabled=True,
    timeout_reminder_start=1200,     # 剩余 20 分钟开始提醒
    timeout_reminder_interval=180,   # 每 3 分钟提醒一次
    timeout_countdown_threshold=300, # 剩余 5 分钟进入倒数模式
    timeout_teardown=120,            # 超时后 2 分钟强制中断
)
```

### 禁用提醒

```python
run_extract_dev_agent(
    model="openai/gpt-4",
    api_base="https://api.openai.com/v1",
    api_key="...",
    run_timeout=3600,
    timeout_reminder_enabled=False,  # 禁用提醒，只保留强制中断
)
```

## 内部实现

### 核心类

#### TimeoutReminderConfig
超时提醒配置数据类。

```python
@dataclass
class TimeoutReminderConfig:
    enabled: bool = True
    reminder_start: float = 1800.0
    reminder_interval: float = 300.0
    countdown_threshold: float = 300.0
    teardown: float = 60.0
```

#### TimeoutReminder
超时提醒管理器，负责跟踪时间和生成提醒消息。

```python
class TimeoutReminder:
    def get_remaining_time(self) -> float
    def is_expired(self) -> bool
    def is_last_round(self) -> bool
    def should_remind_now(self) -> bool
    def get_reminder_message(self) -> str | None
```

### 全局访问

使用 contextvars 实现协程安全的全局访问：

```python
from agentscope_agent.timeout import set_timeout_reminder, get_timeout_reminder

# 设置
reminder = TimeoutReminder(run_timeout=3600)
set_timeout_reminder(reminder)

# 获取
reminder = get_timeout_reminder()
if reminder and reminder.should_remind_now():
    msg = reminder.get_reminder_message()
```

### Hook 机制

通过 AgentScope 的 `pre_reply` hook 自动注入提醒消息：

```python
from agentscope_agent.hooks import register_timeout_reminder_hook

# 给 agent 注册 hook
register_timeout_reminder_hook(agent)
```

Hook 会在 agent 处理消息前检查是否需要提醒，如果需要则往 memory 中添加 system 消息。

### 监控协程

`timeout_monitor` 协程在后台运行，到时间后中断 agents：

```python
from agentscope_agent.timeout import timeout_monitor

# 启动监控
monitor_task = asyncio.create_task(
    timeout_monitor([agent, supervisor.agent], timeout_reminder)
)

# 清理
monitor_task.cancel()
```

## 退出原因

运行结束后会打印退出原因：

- `任务完成` - 正常完成目标
- `运行超时（X秒）` - 循环开始时检测到超时
- `强制中断（超时 + teardown）` - 被 timeout_monitor 中断
- `达到最大迭代次数（X）` - 迭代次数限制
- `用户中断` - Ctrl+C
- `用户退出` - 输入 exit（单 agent 模式）

## 相关文件

- `src/agentscope_agent/timeout.py` - TimeoutReminder 类和 timeout_monitor
- `src/agentscope_agent/hooks/timeout_reminder.py` - pre_reply hook
- `src/agentscope_agent/config.py` - 配置定义
- `src/agentscope_agent/workflow.py` - 集成逻辑
- `tests/agentscope_agent/test_timeout_reminder.py` - 单元测试
