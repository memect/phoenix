# Enrich 后处理——结构化知识提取

## 背景

fact-extract 的 segmented 后端产出 manifest（每条 fact = 一句话摘要 + source_ids）。enrich 是去重之后的后处理步骤，对每条 fact 提取四类结构化知识。

## 四类知识

| 类别 | 说明 | 示例 |
|------|------|------|
| entities | 实体：人名、地名、机构、日期等 | `{"name": "孙悟空", "type": "人名"}` |
| attributes | 属性：实体的特征或性质 | `{"entity": "孙悟空", "attr": "出生方式", "value": "仙石所生"}` |
| relations | 关系：两个实体之间的关联 | `{"subject": "孙悟空", "predicate": "占据", "object": "水帘洞"}` |
| events | 事件：动作 + 施事/受事/时间/地点 | `{"action": "诞生", "agent": "孙悟空", "patient": null, "location": "花果山", "time": null}` |

entity type 由 LLM 自由输出，不做预定义枚举。

## 数据流

```
manifest.json + sources/*.txt
  │
  ▼ 逐条 fact: 拼接 summary + source 原文
  │
  ▼ 32 并发调用 LLM
  │   每条完成后立即写入 enriched/<id>.json
  │
  ▼ 全部完成后汇总
  │
  ▼ manifest.enriched.json
```

## 断点续跑

- `enriched/` 目录存放每条 fact 的独立 JSON 文件
- 重启时扫描目录，已有的自动跳过
- 中断后再次执行同一命令即可续跑

## 使用方式

```bash
uv run fact-extract enrich \
  --manifest <manifest.json 路径> \
  --model <model> --api-base <url> --api-key <key>
```

输入：`manifest.json` + 同级 `sources/` 目录
输出：同级 `manifest.enriched.json` + `enriched/` 中间文件目录

## 输出格式

每条 fact 在原有字段基础上新增四个数组字段：

```json
{
  "id": "fact_0001",
  "summary": "...",
  "source_ids": ["e001"],
  "entities": [...],
  "attributes": [...],
  "relations": [...],
  "events": [...]
}
```
