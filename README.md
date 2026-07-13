# Permission Agent

[English](README_en.md)

一个 Claude Code 插件，自动审批安全的 **Permission Request**，将可能有风险的操作上报给用户确认，并记录所有请求日志。

## 环境

- [Claude Code](https://claude.ai/code) v2.0.45 或更高版本
- [uv](https://docs.astral.sh/uv/) — Python 包管理工具
- macOS（通知功能依赖 `osascript`）

## 介绍

Claude Code 在执行某些操作（如运行 shell 命令、读写文件、调用 MCP 工具）前会弹出 Permission Request 对话框。这个插件在对话框弹出后拦截请求，使用 LLM 自动判断风险：

- **安全操作**（读文件、本地命令、查询 API 等）→ 自动批准，无需手动确认
- **有风险的操作**（删除系统文件、外部系统写操作等）→ 上报给用户，手动确认并发送系统通知

所有请求及判断结果记录到 `~/.auto-permission-request/log/` 目录。

## 安装

### 通过 Marketplace 安装

```bash
claude plugin marketplace add {{marketplace-url}}
claude plugin install {{marketplace}}@permission-agent
```

## 配置

### 用户配置文件

编辑 `~/.auto-permission-request/config/config.json`：

```json
{
  "redactTerms": ["your-username", "sensitive-term"]
}
```

- **`redactTerms`**：发送给 LLM 进行风险判断前，会将这些词替换为 `[REDACTED]`，防止敏感信息泄露给模型。原始数据仍完整记录到日志文件。

文件不存在时插件正常运行，`redactTerms` 默认为空列表。

### LLM 模型

插件通过以下环境变量选择模型（在 `~/.claude/settings.json` 的 `env` 中配置）：

| 环境变量 | 说明 |
|---|---|
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | 优先使用，默认为 `claude-haiku-latest` |
| `ANTHROPIC_BASE_URL` | 自定义 API 代理地址 |
| `ANTHROPIC_AUTH_TOKEN` | API 认证 token |

### 工具描述文件

`config/` 目录下的 YAML 文件描述了各工具的风险特征，供 LLM 参考判断：

| 文件 | 内容 |
|---|---|
| `tools-built-in.yaml` | Claude Code 内置工具（Bash、Read、Write 等） |
| `mcp-chrome-devtools.yaml` | Chrome DevTools MCP 工具 |
| `mcp-excalidraw.yaml` | Excalidraw MCP 工具 |

新增 MCP server 后，运行以下命令检查缺失的工具描述：

```bash
uv run utils/check-missing-tools.py
```

然后在对应的 `~/.auto-permission-request/config/mcp-*.yaml` 文件中补充描述。

### 修改判断逻辑

编辑 `config/prompt.txt` 可以调整 LLM 的判断原则。

## 日志

所有 permission request 记录在 `~/.auto-permission-request/log/` 目录，每次请求对应一个 JSONL 文件（以纳秒时间戳命名），包含两行：

1. 原始 permission request（未脱敏）
2. 插件的判断结果

## 项目结构

```
permission-agent/
├── .claude-plugin/
│   └── plugin.json          # 插件 manifest
├── config/
│   └── prompt.txt           # LLM 判断 prompt（版本控制）
├── hooks/
│   └── hooks.json           # PermissionRequest hook 注册
├── src/
│   └── agent.py             # 主脚本
└── utils/
    └── check-missing-tools.py  # 检查缺失工具描述

~/.auto-permission-request/
├── config/
│   ├── config.json          # 用户配置（redactTerms）
│   ├── tools-built-in.yaml  # 内置工具描述
│   └── mcp-*.yaml           # MCP 工具描述
└── log/                     # 请求日志（JSONL）
```
