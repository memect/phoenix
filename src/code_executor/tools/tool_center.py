"""
工具中心模块

提供工具注册、管理和创建功能。
"""

from typing import Dict, Any, List, Optional, Type
import inspect

from contextvars import ContextVar


# ===== 1. 工具描述器 =====
class ToolDescriptor:
    """工具描述器 - 负责生成工具描述，无需实例化"""
    
    def __init__(self, tool_class: Type, methods: List[str] = None, description: str = None):
        self.tool_class = tool_class
        self.methods = methods or self._auto_detect_methods()
        self.description = description or f"{tool_class.__name__} 工具"
    
    def _auto_detect_methods(self) -> List[str]:
        """自动检测可用方法"""
        return [method for method in dir(self.tool_class) 
                if not method.startswith('_') and 
                callable(getattr(self.tool_class, method))]
    
    def generate_llm_guide(self) -> str:
        """生成LLM使用指南 - 无需实例化"""
        guide_parts = [f"## {self.tool_class.__name__}"]
        cls_doc = inspect.getdoc(self.tool_class) 
        guide_parts.append(cls_doc or self.description)
        guide_parts.append("\n### 可用方法:")
        
        for method_name in self.methods:
            if hasattr(self.tool_class, method_name):
                method = getattr(self.tool_class, method_name)
                method_guide = self._generate_method_guide(method_name, method)
                guide_parts.append(method_guide)
        
        return "\n".join(guide_parts)

    def _format_type_annotation(self, annotation) -> str:
        """格式化类型注释，将 <class 'int'> 转换为 int"""
        if annotation == inspect.Parameter.empty:
            return ""
        
        # 获取类型的字符串表示
        type_str = str(annotation)
        
        # 处理基本类型的 <class 'xxx'> 格式
        if type_str.startswith("<class '") and type_str.endswith("'>"): 
            # 提取类名，如 <class 'int'> -> int
            class_name = type_str[8:-2]  # 去掉 "<class '" 和 "'>"
            return class_name
        
        # 对于其他类型（如 typing.Annotated 等），保持原样
        return type_str
    
    def _generate_method_guide(self, method_name: str, method) -> str:
        """生成单个方法的指南"""
        try:
            sig = inspect.signature(method)
            doc = inspect.getdoc(method) or f"{method_name} 方法"
            
            # 生成参数描述
            params = []
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                param_desc = f"{param_name}"
                if param.annotation != inspect.Parameter.empty:
                    formatted_type = self._format_type_annotation(param.annotation)
                    param_desc += f": {formatted_type}"
                if param.default != inspect.Parameter.empty:
                    param_desc += f" = {param.default}"
                params.append(param_desc)
            
            params_str = ", ".join(params)
            return f"- **{method_name}({params_str})**\n  {doc}"
        except Exception:
            return f"- **{method_name}**: 方法描述"


# ===== 2. 工具注册中心 =====
class ToolRegistry:
    """工具注册中心 - 使用装饰器注册工具"""
    _descriptors: Dict[str, ToolDescriptor] = {}
    
    @classmethod
    def register(cls, 
                 name: str = None, 
                 methods: List[str] = None, 
                 description: str = None):
        """装饰器：注册工具类"""
        def decorator(tool_class):
            tool_name = name or tool_class.__name__.lower()
            
            # 创建工具描述器
            descriptor = ToolDescriptor(
                tool_class=tool_class,
                methods=methods,
                description=description
            )
            
            cls._descriptors[tool_name] = descriptor
            return tool_class
        return decorator
    
    @classmethod
    def get_tool_guide(cls, tool_name: str) -> Optional[str]:
        """获取工具指南 - 无需实例化"""
        descriptor = cls._descriptors.get(tool_name)
        if not descriptor:
            raise ValueError(f"Tool '{tool_name}' not registered")
        return descriptor.generate_llm_guide() if descriptor else None
    
    @classmethod
    def get_all_tools_guide(cls) -> str:
        """获取所有工具的指南"""
        guides = []
        for tool_name, descriptor in cls._descriptors.items():
            guides.append(f"# {tool_name}")
            guides.append(descriptor.generate_llm_guide())
            guides.append("---")
        return "\n".join(guides)
    
    @classmethod
    def create_instance(cls, tool_name: str, args: list = None, kwargs: dict = None):
        """创建工具实例"""
        descriptor = cls._descriptors.get(tool_name)
        if not descriptor:
            raise ValueError(f"Tool '{tool_name}' not registered")
        args = args or []
        kwargs = kwargs or {}
        return descriptor.tool_class(*args, **kwargs)
    
    @classmethod
    def list_tools(cls) -> List[str]:
        return list(cls._descriptors.keys())
    
    @classmethod
    def get_descriptor(cls, tool_name: str) -> Optional[ToolDescriptor]:
        descriptor = cls._descriptors.get(tool_name)
        if not descriptor:
            raise ValueError(f"Tool '{tool_name}' not registered")
        return descriptor


# 简化的装饰器别名
tool = ToolRegistry.register


# ===== 3. 工具代理 =====
class ToolProxy:
    """工具代理 - 控制方法可见性"""
    def __init__(self, tool_instance: Any, allowed_methods: List[str]):
        self._tool = tool_instance
        self._allowed_methods = set(allowed_methods)
    
    def __getattr__(self, name: str):
        if name in self._allowed_methods:
            return getattr(self._tool, name)
        raise AttributeError(f"Method '{name}' is not available")
    
    def __call__(self, *args, **kwargs):
        if '__call__' in self._allowed_methods:
            return self._tool(*args, **kwargs)
        raise AttributeError("Method '__call__' is not available")
    
    def __dir__(self):
        return list(self._allowed_methods)


# ===== 4. BaseTool =====
class BaseTool:
    """工具包装器 - 简化版，描述能力已分离"""
    def __init__(self, tool: Any, methods: List[str], tool_name: str):
        self.tool = tool
        self.methods = methods
        self.tool_name = tool_name
        self._proxy = ToolProxy(tool, methods)
    
    def get_tool(self) -> Any:
        """返回代理对象，隐藏不允许的方法"""
        return self._proxy
    
    def llm_guide(self) -> str:
        """从注册中心获取指南"""
        return ToolRegistry.get_tool_guide(self.tool_name) or "工具描述不可用"


# ===== 5. ToolHub =====
class ToolHub:
    """工具中心 - 管理多个工具"""
    def __init__(self, tools: Dict[str, BaseTool]):
        self.__tools = tools
    
    def get_tool(self, tool_name: str):
        """获取工具实例"""
        tool = self.__tools.get(tool_name)
        if tool:
            return tool.get_tool()
        return None
    
    def list_tools(self) -> List[str]:
        return list(self.__tools.keys())
    
    def get_tool_guide(self) -> str:
        """获取所有工具的使用指南"""
        tool_list = self.list_tools()
        guide_header = f"""
你可使用 ToolHub实例 的 get_tool 方法来获取工具。
比如： toolhub.get_tool('<tool_name>') 可以获取对应的工具实例。
目前，你可以使用以下工具：{tool_list}
        """
        
        tool_descs = []
        for tool_name, tool in self.__tools.items():
            tool_desc = f'<code-tool-description name={tool_name}>\n{tool.llm_guide()}\n</code-tool-description>'
            tool_descs.append(tool_desc)
        
        return f'{guide_header}\n{("\n".join(tool_descs))}'


# ===== 6. ToolHubFactory =====
class ToolHubFactory:
    """工具工厂 - 创建ToolHub实例"""
    def __init__(self, registry: ToolRegistry = None):
        self.registry = registry or ToolRegistry
    
    def get_available_tools_guide(self) -> str:
        """获取所有可用工具的指南 - 无需实例化任何工具"""
        return self.registry.get_all_tools_guide()
    
    def create_tool_hub(self, tool_names: List[str], tool_config: Dict[str, Dict[str, Any]]) -> ToolHub:
        """创建ToolHub - 每次都是新实例"""
        # 验证tool_config格式
        self._validate_tool_config(tool_names, tool_config)
        
        tools = {}
        
        for tool_name in tool_names:
            if tool_name not in self.registry.list_tools():
                raise ValueError(f"Tool '{tool_name}' not registered")
            
            # 创建工具实例 - 每次都是新的
            tool_instance = self.registry.create_instance(
                tool_name,
                args=tool_config[tool_name].get('args', []),
                kwargs=tool_config[tool_name].get('kwargs', {})
            )
            
            # 获取描述器信息
            descriptor = self.registry.get_descriptor(tool_name)
            
            # 包装为BaseTool
            tools[tool_name] = BaseTool(
                tool=tool_instance,
                methods=descriptor.methods,
                tool_name=tool_name
            )
        
        return ToolHub(tools)
    
    def _validate_tool_config(self, tool_names: List[str], tool_config: Dict[str, Dict[str, Any]]) -> None:
        """验证tool_config格式"""
        # 检查tool_config是否为字典
        if not isinstance(tool_config, dict):
            raise TypeError(f"tool_config must be a dictionary, got {type(tool_config).__name__}")
        
        # 检查是否包含所有required的tool_names
        for tool_name in tool_names:
            if tool_name not in tool_config:
                raise ValueError(f"Missing configuration for tool '{tool_name}' in tool_config")
            
            # 检查每个工具配置的格式
            config = tool_config[tool_name]
            if not isinstance(config, dict):
                raise TypeError(f"Configuration for tool '{tool_name}' must be a dictionary, got {type(config).__name__}")
            
            # 检查args字段格式
            if 'args' in config:
                args = config['args']
                if not isinstance(args, list):
                    raise TypeError(f"'args' field for tool '{tool_name}' must be a list, got {type(args).__name__}")
            
            # 检查kwargs字段格式
            if 'kwargs' in config:
                kwargs = config['kwargs']
                if not isinstance(kwargs, dict):
                    raise TypeError(f"'kwargs' field for tool '{tool_name}' must be a dictionary, got {type(kwargs).__name__}")
            
            # 检查是否有未知字段
            allowed_fields = {'args', 'kwargs'}
            unknown_fields = set(config.keys()) - allowed_fields
            if unknown_fields:
                raise ValueError(f"Unknown fields in configuration for tool '{tool_name}': {', '.join(unknown_fields)}. Allowed fields: {', '.join(allowed_fields)}")


# ===== 7. 便捷工厂函数 =====
def create_tool_hub(tool_names: List[str], tool_config: Dict[str, Dict[str, Any]]) -> ToolHub:
    """便捷的工厂函数 - 每次返回新的ToolHub实例"""
    factory = ToolHubFactory()
    return factory.create_tool_hub(tool_names, tool_config)


class Policy:
    """全局策略"""
    def __init__(self, tool_names: List[str], tool_config: Dict[str, Dict[str, Any]]):
        self.__tool_names = tool_names
        self.__tool_config = tool_config

    @property
    def tool_names(self) -> List[str]:
        """获取工具名称"""
        return self.__tool_names

    @tool_names.setter
    def tool_names(self, tool_names: List[str]):
        """设置工具名称"""
        self.__tool_names = tool_names

    @property
    def tool_config(self) -> Dict[str, Dict[str, Any]]:
        """获取工具配置"""
        return self.__tool_config

    @tool_config.setter
    def tool_config(self, tool_config: Dict[str, Dict[str, Any]]):
        """设置工具配置"""
        self.__tool_config = tool_config

    def clear(self):
        """清空策略"""
        self.__tool_names = []
        self.__tool_config = {}


# ===== 8. 上下文策略管理 =====

# 使用ContextVar替代全局变量
_policy_context: ContextVar[Optional[Policy]] = ContextVar('policy_context', default=None)


class PolicyContext:
    """策略上下文管理器"""
    
    def __init__(self, policy: Policy):
        self.policy = policy
        self.token = None
    
    def __enter__(self) -> 'PolicyContext':
        """进入上下文，设置新策略"""
        self.token = _policy_context.set(self.policy)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文，恢复原策略"""
        if self.token is not None:
            _policy_context.reset(self.token)
    
    def get_current_policy(self) -> Policy:
        """获取当前上下文中的策略"""
        return self.policy


def get_global_policy() -> Policy:
    """获取当前上下文中的全局策略
    
    如果当前 Context 中没有设置策略，会尝试从环境变量重新加载配置。
    这解决了 ContextVar 在不同异步上下文（如 FastAPI 请求）中值隔离的问题。
    """
    policy = _policy_context.get()
    if policy is None:
        return Policy(tool_names=[], tool_config={})
    return policy


def set_global_policy(policy: Policy):
    """设置全局策略"""
    _policy_context.set(policy)


def create_default_tool_hub() -> ToolHub:
    """创建默认的ToolHub"""
    policy = get_global_policy()
    return create_tool_hub(policy.tool_names, policy.tool_config)


def has_default_tool() -> bool:
    """检查是否存在默认工具"""
    policy = get_global_policy()
    return len(policy.tool_names) > 0


def create_default_llm_guide() -> str:
    """创建默认的LLM指南"""
    policy = get_global_policy()
    
    # 构建指南内容
    guide_parts = []
    
    # 1. 导入和基本用法指南
    guide_parts.append("""
<tool-import-guide>
# 工具导入和使用指南

## 推荐入口
```python
from code_executor.document.models.document import Document
from code_executor.tools import ToolHub
```

## 基本用法
```python
def extract(document: Document, tool_hub: ToolHub):
    # xdev 会自动读取配置并注入 tool_hub
    tool = tool_hub.get_tool('tool_name')

    # 使用工具
    result = tool.method_name(param1, param2)
```

## 注意事项
- xdev 负责基于当前配置创建工具中心
- 只能访问策略中配置的工具
</tool-import-guide>
""")
    
    # 2. 可用工具列表
    if policy.tool_names:
        tool_list = "\n".join([f"- **{name}**: {ToolRegistry.get_descriptor(name).description if ToolRegistry.get_descriptor(name) else '工具描述'}" for name in policy.tool_names])
        guide_parts.append(f"""
<available-tools>
# 可用工具列表

当前策略配置的可用工具：

{tool_list}
</available-tools>
""")
    else:
        guide_parts.append("""
<available-tools>
# 可用工具列表

当前策略未配置任何工具。
</available-tools>
""")
    
    # 3. 工具详细说明
    guide_parts.append("""
<tool-details>
# 工具详细说明
""")
    
    for tool_name in policy.tool_names:
        descriptor = ToolRegistry.get_descriptor(tool_name)
        if descriptor:
            # 生成工具的详细指南
            tool_guide = descriptor.generate_llm_guide()
            
            # 添加使用示例
            example_code = f"""
### 使用示例
```python
# 获取 {tool_name} 工具
{tool_name}_tool = tool_hub.get_tool('{tool_name}')

# 使用工具方法（请根据具体方法调整参数）
"""
            
            # 为每个方法添加示例
            for method_name in descriptor.methods:
                if hasattr(descriptor.tool_class, method_name):
                    method = getattr(descriptor.tool_class, method_name)
                    try:
                        sig = inspect.signature(method)
                        params = []
                        for param_name, param in sig.parameters.items():
                            if param_name == 'self':
                                continue
                            if param.default != inspect.Parameter.empty:
                                params.append(f"{param_name}={repr(param.default)}")
                            else:
                                params.append(f"{param_name}=...")
                        
                        params_str = ", ".join(params)
                        example_code += f"# result = {tool_name}_tool.{method_name}({params_str})\n"
                    except Exception:
                        example_code += f"# result = {tool_name}_tool.{method_name}(...)\n"
            
            example_code += "```\n"
            
            guide_parts.append(f"""
<tool-detail name={tool_name}>
## {tool_name} 工具

{tool_guide}

{example_code}
</tool-detail>
""")
    
    guide_parts.append("""
</tool-details>""")
    
    return "\n".join(guide_parts)
