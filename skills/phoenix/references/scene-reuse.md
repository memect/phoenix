# Scene Reuse

Before running `agentic-extract auto` on a new document set, check whether an existing workspace already handles the same document type. If yes, copy its `program.py` and skip the agent loop entirely.

## When to Check

Check for scene reuse when:

- The user provides a new PDF directory or document set
- The user describes extraction fields (e.g. "提取合同编号、甲方、乙方")
- No workspace exists yet for the current task

## How to Check

### Step 1 — Find existing workspaces

```bash
# List all workspaces in the current project directory
ls -d */  | grep -v '^\.'
# Or check a known parent directory
ls ~/workspaces/
```

### Step 2 — Read their schemas

```bash
cat <existing-ws>/.xdev/schema.json
```

Look at the field names and descriptions. Ask yourself:

- Do the fields overlap significantly with what the user wants now?
- Is the document type the same (invoice, contract, annual report, etc.)?

### Step 3 — Judge similarity

Reuse if **both** conditions hold:

1. Document type is the same category
2. At least 60% of the requested fields exist in the existing schema (by name or meaning)

Do not reuse if the document structure is fundamentally different, even if some field names match.

### Step 4 — Act on the decision

If reusable:

```bash
cp <existing-ws>/program.py new-ws/program.py
agentic-extract auto --workspace new-ws --pdfs-dir ./new-pdfs --message '...'
# then immediately run (skip full auto iteration)
agentic-extract run \
  --workspace new-ws \
  --message '基于已有提取程序，验证并按需调整'
```

If not reusable:

```bash
agentic-extract auto \
  --workspace new-ws \
  --pdfs-dir ./new-pdfs \
  --message '...'
```

## Telling the User

Always tell the user what you found before acting:

- Found reusable scene: "发现 `ws-contracts` 已有合同提取程序，字段覆盖率 80%，直接复用并验证。"
- No match: "未找到相似场景，从头迭代。"
- Partial match: "找到相似场景但字段差异较大，建议从头迭代或以已有程序为基础修改。"
