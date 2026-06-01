---
name: pdf-parse
description: |
  PDF 论文批量解析工具。调用 MinerU 精准解析 API，将学术论文 PDF 批量转换为结构化 Markdown（含 full.md 和图片目录）。适用于需要将 PDF 论文转为可读文本的场景。
  触发词：「解析PDF」「PDF转markdown」「批量解析论文」「论文PDF转文本」「MinerU解析」「parse pdf」。
---

# pdf-parse · PDF 论文批量解析

## 1. 功能定位

将学术论文 PDF 批量转换为结构化 Markdown，输出包含：
- `full.md` — 论文全文的结构化 Markdown
- `images/` — 论文中的图表

**数据流：**

```text
PDF_DIR（用户提供）
    │
    ▼  pdf_to_md.py
    │   MinerU API v4 batch
    │
    ▼
OUT_DIR（脚本自动创建）
    ├── paper-001/
    │   ├── full.md
    │   └── images/
    ├── paper-002/
    │   ├── full.md
    │   └── images/
    └── ...
```

## 2. 前置条件：Token 配置

脚本通过环境变量 `M_TOKEN` 读取 MinerU API Token。

**必须在运行前确认用户已完成以下操作：**

1. 前往 [MinerU API 管理](https://mineru.net/apiManage) 申请 Token；
2. Windows：搜索"环境变量" → "编辑系统环境变量" → "环境变量" → 在"用户变量"中新建 `M_TOKEN`，值为你的 Token → 确定；
3. 重启 VSCode 使环境变量生效。

> 如果不想设环境变量，也可直接编辑脚本，将 `TOKEN = os.getenv('M_TOKEN')` 替换为 `TOKEN = "你的token字符串"`（不推荐，有泄露风险）。

**推荐提醒模板：**

```markdown
⚠️ 在运行 PDF 解析之前，请先确认 MinerU Token 已配置。

操作步骤：
1. 在 https://mineru.net/apiManage 申请 API Token；
2. Windows：搜索"环境变量" → "编辑系统环境变量" → "环境变量" → 新建用户变量 `M_TOKEN` = 你的 Token；
3. 重启 VSCode，确认无误后告诉我，我会帮你运行解析脚本。
```

## 3. 使用方式

### 3.1 通过对话触发

用户提供 PDF 文件夹路径后，助手调用脚本完成解析。

必须确认的信息：
- PDF 文件夹的**绝对路径**（不接受相对路径）
- 输出目录（默认为 `data/<对象>/paper/`）

### 3.2 手动运行

```powershell
python pdf_to_md.py --pdf-dir <PDF文件夹绝对路径> --out-dir <输出目录>
```

### 3.3 脚本配置项

| 配置项 | 位置 | 默认行为 | 用户可修改 |
|---|---|---|---|
| `TOKEN` | 脚本顶部 `本地必须配置区域` | 从环境变量 `M_TOKEN` 读取 | 可直接写死字符串 |
| `PDF_DIR` | 脚本顶部 `本地必须配置区域` | 用户提供的 PDF 文件夹绝对路径 | ✅ 是 |
| `OUT_DIR` | 脚本顶部 `本地必须配置区域` | 脚本自动创建，默认为 `data/<对象>/paper/` | ✅ 用户可指定其他路径 |
| `MODEL_VERSION` | `可选配置区域` | `"vlm"`（推荐） | 可选 `pipeline` / `vlm` / `MinerU-HTML` |
| `BATCH_MAX` | `可选配置区域` | `50`（API 限制） | 通常不需要改 |
| `POLL_TIMEOUT` | `可选配置区域` | `1800` 秒（30 分钟） | 文件多可适当调大 |

## 4. 执行流程

### Step 1：检查 PDF 文件

确认 `PDF_DIR` 下存在 `.pdf` 文件。脚本会自动扫描：

```python
pdf_files = sorted(set(PDF_DIR.glob("*.pdf")) | set(PDF_DIR.glob("*.PDF")))
```

### Step 2：运行解析脚本

在确认 Token 已配置后，在终端运行：

```powershell
python pdf_to_md.py
```

或由助手代为执行。

### Step 3：等待解析完成

脚本会经历四个阶段：
1. **获取上传链接** — 向 MinerU 申请批量上传 URL；
2. **上传文件** — 将本地 PDF PUT 到预签名 URL；
3. **轮询解析状态** — 每 5 秒查询一次，直到全部完成或超时；
4. **下载并解压结果** — 每个 PDF 对应一个子文件夹，内含 `full.md` 和 `images/`。

解析完成后，脚本会打印汇总：

```text
🎉 全部完成！成功: X, 失败/跳过: Y
结果保存在: C:\...\data\<对象>\paper\
```

### Step 4：验证输出

确认每个 PDF 对应的输出文件夹中存在 `full.md`。如果部分文件解析失败（状态 `failed`），脚本会跳过并报告原因，需人工检查原 PDF 是否损坏或格式不兼容。

## 5. 完成检查

- [ ] `M_TOKEN` 已设置且有效；
- [ ] `PDF_DIR` 已指向正确的 PDF 文件夹；
- [ ] 脚本已成功运行并完成所有文件解析；
- [ ] `OUT_DIR` 中每个 PDF 对应一个包含 `full.md` 的子文件夹；
- [ ] 失败的 PDF 已记录，并判断是否影响语料覆盖度；
- [ ] `OUT_DIR` 路径已记录，后续流程可直接引用。

## 6. 输出用途

解析完成后，`OUT_DIR` 中的 `full.md` 文件可被其他 skill 或工作流直接读取和分析，例如：
- 作为 `keyan` 科研工作台的语料输入
- 作为论文阅读和拆解的结构化文本源
- 作为文献综述和选题分析的基础材料
