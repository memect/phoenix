# 导入与同步数据

## 先选一种数据来源

首次准备 `.xdev` 时，优先使用下面四种方式之一：

```bash
xdev import-data --set-id <set_id>
xdev import-data --pdfs /path/to/pdfs
xdev import-data --from-data-dir /path/to/other/.xdev
xdev import-data --source /path/to/source.json
```

规则：

- 这些模式互斥，一次只选一个
- 远程标准集使用 `--set-id`
- 本地 PDF 目录使用 `--pdfs`
- 已有 `.xdev` 复制使用 `--from-data-dir`
- 已经有统一来源描述文件时使用 `--source`

## 远程标准集常用参数

```bash
xdev import-data \
  --set-id <set_id> \
  --std-ids doc1,doc2 \
  --base-url http://host:port
```

可选参数：

- `--std-ids`
- `--std-ids-file`
- `--sync`
- `--skip-exist`
- `--base-url`

## 增量维护

新增一个 PDF 或一个目录：

```bash
xdev import-data --add-pdf /path/to/new.pdf
xdev import-data --add-pdf /path/to/new_pdf_dir
```

如果允许覆盖已有文档：

```bash
xdev import-data --add-pdf /path/to/new.pdf --force
```

同步长期维护的 PDF 目录：

```bash
xdev sync-pdfs /path/to/pdfs
```

`sync-pdfs` 会报告：

- 新增
- 删除
- 修改
- 不变

适用建议：

- 一次性初始化数据：优先 `import-data --set-id/--pdfs/--from-data-dir/--source`
- 只补少量新增文件：优先 `import-data --add-pdf`
- 持续对齐一个外部 PDF 目录：优先 `sync-pdfs`

## 重新解析

如果已有 PDF 需要重新生成 DocJSON：

```bash
xdev import-data --reparse
xdev import-data --reparse --doc-ids doc1,doc2
```

## 注意事项

- 不要在同一个 workspace 里无意识混用不同来源
- 如果数据来源已经实质变化，宁可新建 workspace，也不要让旧 labels 默默失效
- 数据导入完成后，下一步通常是 `xdev list`、`xdev doc`、`xdev label-status`
