# 🧬 keyan · 科研女娲

> 经济学实证论文 Skill 生成工作台 —— 输入学者姓名 + 论文 PDF，自动蒸馏科研范式，生成可运行的 AI 科研助理。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📖 这是什么？

**keyan（科研女娲）** 是一个面向经济学研究的 AI Skill 生成系统。它的核心能力是：

> 给定一位经济学家（或研究主题）的一批论文 PDF，自动提炼其研究范式，并生成一个专属的 `XXX-research-assistant` Skill。

生成后的 Skill 可以直接在支持 Copilot 的 AI 编辑器中使用，辅助你进行：

- 📄 论文阅读与结构化拆解
- 🔍 选题诊断与研究方向定位
- 📊 数据、变量与模型设计
- 🧪 识别策略评估（DID / FE / IV / 事件研究 等）
- 🛡️ 稳健性、机制与异质性检验设计
- ✍️ 论文写作（Introduction、文献综述、结果解释）
- 🎤 组会汇报与答辩 Q&A 准备
- 👀 审稿人视角的批判性修改

---

## 🚀 快速开始（部署）

### 前置条件

| 项目 | 要求 |
|---|---|
| AI 编辑器 | VS Code + GitHub Copilot（或支持 Copilot Skill 的编辑器） |
| Python | 3.9+（仅 PDF 解析脚本需要） |
| MinerU API Token | [免费申请](https://mineru.net/apiManage)（PDF 精准解析用） |

### 安装方式

两种方式任选其一：

**方式一：跟 Agent 说一句话**

对 Copilot / Claude / Opencode 说：

> 帮我把 https://github.com/ShenzhenLime/keyan 整个仓库克隆下来，作为一个完整文件夹放到 skills 目录中。不要只复制 SKILL.md，要把整个 keyan/ 文件夹（含 scripts/、skills/、README.md、requirements.txt 等所有内容）都放进去。

**方式 B：手动克隆到 skills 目录**

```bash
# 进入 skills 目录（以 OpenCode 为例）
cd C:\Users\27522\.config\opencode\skills

# 如果使用 VS Code + Copilot，则进入项目根目录的 .github/copilot/ 或 .copilot/
# cd 你的项目/.github/copilot

git clone https://github.com/ShenzhenLime/keyan.git
cd keyan
pip install -r requirements.txt
```

安装完成后目录结构：

```text
skills/
└── keyan/                    ← 整个仓库作为一个文件夹
    ├── SKILL.md              ← 主 Skill（科研女娲工作台）
    ├── README.md
    ├── requirements.txt
    ├── scripts/
    │   └── 文件批量解析.py
    └── skills/
        └── liguangzhong-research-assistant/
            ├── SKILL.md
            └── references/
```

> ⚠️ 是 `skills/keyan/SKILL.md`，不是 `skills/SKILL.md`。整个仓库作为一个完整的 Skill 文件夹放进去。

配置好 MinerU Token（见下方 ⚙️ 配置章节），重启编辑器即可使用。

---

## 🔄 工作流程

本 Skill 包含 **6 个阶段**，从原始 PDF 到可运行的科研助理 Skill：

```mermaid
flowchart TD
    A[📥 用户提供 PDF + 学者名] --> B[Phase 0: 入口分流 & 需求澄清]
    B --> B2[Phase 0.6: MinerU PDF 解析]
    B2 --> C[Phase 1: 论文筛选<br/>顶刊优先 + 近年为主]
    C --> D[Phase 2: 单篇论文结构化拆解<br/>问题 / 数据 / 变量 / 模型 / 识别]
    D --> E[Phase 3: 多篇论文共性提炼<br/>研究设计 / 写作范式 / 诚实边界]
    E --> F[Phase 4: 生成 XXX-research-assistant Skill]
    F --> G[Phase 5: 交付与持续更新]

    style A fill:#e1f5fe
    style G fill:#c8e6c9
```

### 各阶段说明

| 阶段 | 做什么 | 产物 |
|---|---|---|
| **Phase 0** | 澄清需求（学者/主题/用途）+ PDF 预处理 | 结构化 Markdown 论文 |
| **Phase 1** | 论文筛选（顶刊优先、时间覆盖、主题均衡） | `paper-selection.md` |
| **Phase 2** | 单篇论文 13 维度拆解（X/Y/M、数据、模型、识别、写作DNA） | `paper-XXX.md` × N 篇 |
| **Phase 3** | 跨论文共性提炼（稳定范式 / 倾向性模式） | `01-研究设计.md` `02-写作范式.md` `03-诚实边界.md` |
| **Phase 4** | 组装生成可运行的 `XXX-research-assistant/SKILL.md` | 最终 Skill 文件 |
| **Phase 5** | 交付说明 + 增量更新机制 | 持续维护 |

> 📌 **PDF 解析**使用 [MinerU](https://mineru.net/) 精准解析 API，可将论文 PDF 转为结构化 Markdown（含公式、表格、图表）。

---

## 📂 目录结构

安装后的目录结构（以 OpenCode 为例）：

```text
skills/
└── keyan/                       ← 🧬 整个仓库作为一个 Skill 文件夹
    ├── SKILL.md                 ← 主 Skill（科研女娲工作台）
    ├── README.md                ← 📖 本文件
    ├── requirements.txt         ← Python 依赖
    ├── scripts/
    │   └── 文件批量解析.py       ← 🔧 MinerU PDF 批量解析脚本
    └── skills/
        └── liguangzhong-research-assistant/
            ├── SKILL.md         ← 📦 示例：李广众科研助理 Skill
            └── references/      ← 📋 中间产物（语料、拆解、综合）
```

---

## 📦 Python 外部包

PDF 解析脚本 `scripts/文件批量解析.py` 依赖以下外部包：

| 包名 | 用途 |
|---|---|
| `requests` | HTTP 请求（MinerU API 调用、文件上传/下载） |

### 安装方式

```bash
pip install -r requirements.txt
```

或直接安装：

```bash
pip install requests
```

---

## ⚙️ PDF 解析脚本配置

`scripts/文件批量解析.py` 的关键配置项：

| 配置项 | 说明 | 默认值 |
|---|---|---|
| `TOKEN` | MinerU API Token（从环境变量 `M_TOKEN` 读取） | 必填 |
| `PDF_DIR` | PDF 文件夹绝对路径 | 需用户指定 |
| `OUT_DIR` | 解析结果输出目录 | 需用户指定 |
| `MODEL_VERSION` | 解析模型（`vlm` / `pipeline` / `MinerU-HTML`） | `vlm` |
| `BATCH_MAX` | 单次批量上限 | 50 |
| `POLL_TIMEOUT` | 轮询超时（秒） | 1800 |

> ⚠️ 使用前请先到 [MinerU API 管理](https://mineru.net/apiManage) 申请 Token，并设为环境变量 `M_TOKEN`。

---

## 🎯 已生成的 Skill 示例

| Skill 名称 | 学者 | 论文数 | 覆盖领域 |
|---|---|---|---|
| `liguangzhong-research-assistant` | 李广众 | 15 篇（精选自 ~60 篇） | 汇率与国际金融、公司金融与治理、政府治理与税收、法与金融、资本市场 |

触发词示例：「李广众」「李广众论文」「按李广众的方式看这个选题」「用李广众 skill 帮我改论文」

---

## 🤝 贡献与扩展

欢迎基于本项目蒸馏更多学者的科研助理 Skill：

1. Fork 本仓库
2. 准备目标学者的论文 PDF
3. 运行 `scripts/文件批量解析.py` 解析 PDF
4. 对 Copilot 说「基于这些论文生成 XXX 的科研助理 Skill」
5. 提交 PR 将生成的 `skills/XXX-research-assistant/` 分享给社区

---

## 📜 License

MIT License

---

## 🙏 致谢

- [MinerU](https://mineru.net/) — PDF 精准解析
- [GitHub Copilot](https://github.com/features/copilot) — AI Skill 运行环境
