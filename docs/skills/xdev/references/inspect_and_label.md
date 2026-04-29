# 查看数据、schema 与标注

## 查看文档集合

列出文档：

```bash
xdev list
```

查看单篇文档：

```bash
xdev doc <doc_id>
```

如果输出提示文档过长，只展示前 1000 字，应改用 `pdf-ai-explorer` 查看完整内容。

## schema

`xdev` 依赖 `.xdev/schema.json`。

当前只支持两种顶层类型：

- `object`
- `list_of_objects`

字段约束：

- key 必须稳定
- value 类型一般为 `str` / `int` / `float` / `bool` / `list`
- 只支持扁平一层结构，不要设计嵌套对象

## 标注指导

查看通用标注说明：

```bash
xdev label-guide
```

查看某个文档的标注模板：

```bash
xdev label-guide <doc_id>
```

标注文件位置：

```text
.xdev/labels/<doc_id>.json
```

## 标注状态

检查整体状态：

```bash
xdev label-status
```

输出详细问题文档：

```bash
xdev label-status --detail
```

它会区分：

- 已标注
- 未标注
- schema 不匹配

## 推荐操作顺序

1. `xdev list`
2. 采样若干篇 `xdev doc <doc_id>`
3. 设计或修正 `.xdev/schema.json`
4. `xdev label-guide`
5. 补齐 `.xdev/labels/`
6. `xdev label-status --detail`

## 经验规则

- 标注必须基于文档原文，不要臆测
- schema key 一旦开始标注，尽量不要频繁改名
- 导入新 PDF 后，要重新检查 `label-status`
- `business_guide.md` 是辅助文档，不替代 schema 和 labels
