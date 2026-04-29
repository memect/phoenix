# AgentScope 工具函数规范

本文档记录 AgentScope 框架中工具函数的编写规范，避免常见错误。

## 返回值要求

**重要**: AgentScope 的工具函数**必须返回 `ToolResponse` 对象**，不能直接返回字符串或其他类型。

### 错误示例

```python
# ❌ 错误！不能直接返回 str
async def my_tool(arg: str) -> str:
    result = do_something(arg)
    return result
```

### 正确示例

```python
from agentscope.tool import ToolResponse
from agentscope.message import TextBlock

# ✓ 正确！返回 ToolResponse
async def my_tool(arg: str) -> ToolResponse:
    result = do_something(arg)
    return ToolResponse(
        content=[TextBlock(type="text", text=result)]
    )
```

## 常见错误

### TypeError: The tool function must return a ToolResponse object

```
TypeError: The tool function must return a ToolResponse object, or an AsyncGenerator/Generator of ToolResponse objects, but got <class 'str'>.
```

**原因**: 工具函数返回了 `str` 而不是 `ToolResponse`。

**解决方案**: 将返回值包装为 `ToolResponse`：

```python
# 修改前
return answer

# 修改后
return ToolResponse(content=[TextBlock(type="text", text=answer)])
```

## ToolResponse 结构

```python
from agentscope.tool import ToolResponse
from agentscope.message import TextBlock

# 文本响应
ToolResponse(
    content=[TextBlock(type="text", text="响应内容")]
)

# 多部分响应
ToolResponse(
    content=[
        TextBlock(type="text", text="第一部分"),
        TextBlock(type="text", text="第二部分"),
    ]
)
```

## 参考

- AgentScope 官方文档: https://doc.agentscope.io/
- 项目中的工具实现: `src/agentscope_agent/tools/`
