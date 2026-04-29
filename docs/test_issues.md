# 测试问题记录

## 重构后待修复的测试失败 (22个)

记录时间: 2026-01-08

### 1. test_extractor_tool.py (9个失败)

**问题**: 测试使用 JSON Schema 字典作为参数，但 `ExtractTool.__call__` 实现期望 Pydantic BaseModel 类

**失败的测试**:
- test_basic_extraction
- test_complex_schema
- test_list_extraction
- test_nested_object_extraction
- test_missing_fields
- test_empty_content
- test_llm_invocation
- test_schema_converter_integration
- test_return_format

**修复方向**: 
- 方案A: 修改测试，使用 Pydantic BaseModel 而非 JSON Schema 字典
- 方案B: 修改 ExtractTool 支持两种输入格式

### 2. test_ner_tool.py (9个失败)

**问题**: Mock 返回的 `response.json()` 已经是字典，但代码中又调用了 `json.loads()`，导致 TypeError

**错误信息**: `TypeError: the JSON object must be str, bytes or bytearray, not dict`

**失败的测试**:
- test_call_success
- test_call_empty_content
- test_call_chinese_text
- test_call_financial_entities
- test_request_ner_private_method
- test_special_characters
- test_various_inputs (3个参数化测试)

**修复方向**:
- 方案A: 修改 Mock 返回格式，使 `response.json()['Result']` 返回 JSON 字符串而非字典
- 方案B: 修改 `ner_tool.py` 中的 `__request_ner` 方法，检测返回类型

### 3. test_tool_run.py (1个失败)

**问题**: `test_tool_calling_functionality` 失败，可能与 ExtractTool 问题相关

**修复方向**: 待分析具体原因

### 4. test_tools.py (2个失败)

**问题**: 工具描述符生成相关测试失败

**失败的测试**:
- test_generate_llm_guide
- test_complex_tool_descriptor_generation

**修复方向**: 待分析具体原因

### 5. test_url_loader.py (1个失败)

**问题**: `test_load_from_real_api` 需要外部 API 连接

**修复方向**: 
- 方案A: 添加 `@pytest.mark.skip` 或 `@pytest.mark.integration` 标记
- 方案B: 使用 Mock 替代真实 API 调用

---

## 通过的核心测试 (145个)

所有核心属性测试和功能测试均通过，重构后的模块功能正常。
