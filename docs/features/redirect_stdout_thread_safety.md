# redirect_stdout 线程安全问题

## 问题描述

`extract-dev train/test` 命令在并发执行时，进度打印和后续输出会丢失。

## 问题位置

`code_executor/executor.py` 中的 `_execute_from_path_with_output` 函数：

```python
def _execute_from_path_with_output(program_path, input_data):
    stdout_buffer = StringIO()
    stderr_buffer = StringIO()
    
    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        # 执行代码...
```

这个函数通过 `asyncio.to_thread` 在子线程中执行。

## 根本原因

`contextlib.redirect_stdout` 不是线程安全的，因为它操作的是全局的 `sys.stdout`。

**竞争条件示例**：

```
时间线:
T1: 线程A 进入 with → 保存 old=原始stdout, sys.stdout=bufferA
T2: 线程B 进入 with → 保存 old=bufferA(!), sys.stdout=bufferB
T3: 线程A 退出 with → sys.stdout=原始stdout
T4: 线程B 退出 with → sys.stdout=bufferA(!)  ← 问题！
```

最终 `sys.stdout` 指向了某个 StringIO buffer 而不是终端。

**导致的问题**：
1. 主线程的 `print()` 被重定向到子线程的 buffer，输出丢失
2. `asyncio.run()` 返回后 `sys.stdout` 仍指向 buffer，后续输出也丢失

## 当前临时修复

位置：`extract_dev/cli.py`

1. **进度回调使用 `sys.__stdout__`**：绕过 `sys.stdout` 重定向

```python
def _print(msg: str):
    """使用 sys.__stdout__ 打印，绕过 redirect_stdout"""
    sys.__stdout__.write(msg + '\n')
    sys.__stdout__.flush()
```

2. **`asyncio.run()` 后恢复 stdout**：

```python
evaluation_result = asyncio.run(engine.evaluate_program(...))
# 恢复 stdout（防止 redirect_stdout 竞争条件导致的问题）
sys.stdout = sys.__stdout__
```

## 正式修复方案

### 方案1: ThreadLocal（推荐）

自定义 `ThreadLocalStdout`，每个线程写入独立的 buffer：

```python
import threading
import sys

_thread_local = threading.local()

class ThreadLocalStdout:
    def __init__(self, original):
        self._original = original
    
    def write(self, text):
        buf = getattr(_thread_local, 'buffer', None)
        if buf is not None:
            buf.write(text)
        else:
            self._original.write(text)
    
    def flush(self):
        buf = getattr(_thread_local, 'buffer', None)
        if buf is not None:
            buf.flush()
        self._original.flush()
    
    # 需要实现其他 stdout 属性：encoding, fileno, isatty 等

# 程序启动时安装
sys.stdout = ThreadLocalStdout(sys.__stdout__)
sys.stderr = ThreadLocalStdout(sys.__stderr__)

# 在线程中使用
def run_in_thread():
    _thread_local.buffer = StringIO()
    try:
        # 代码执行...
        print("这会写入线程本地 buffer")
    finally:
        output = _thread_local.buffer.getvalue()
        _thread_local.buffer = None
    return output
```

**优点**：轻量、真正的线程安全
**缺点**：需要全局安装，有一定侵入性

### 方案2: 多进程

用 `subprocess` 执行代码，每个进程有独立的 stdout/stderr：

```python
async def execute_in_subprocess(program_path, input_data):
    # 序列化 input_data
    # 启动子进程执行
    # 返回 (result, stdout, stderr)
```

**优点**：完全隔离，无竞争条件
**缺点**：
- 进程创建开销大
- 需要序列化 input_data（包含复杂对象如 docjson、pdf_bytes）
- 子进程需要重新导入所有依赖（tools 等）

### 推荐

**方案1 (ThreadLocal)** 更实际，因为：
- 当前代码执行依赖很多导入（tools、Document 等）
- input_data 包含复杂对象，序列化成本高

## TODO

- [ ] 实现 ThreadLocalStdout 方案，彻底解决 redirect_stdout 线程安全问题
