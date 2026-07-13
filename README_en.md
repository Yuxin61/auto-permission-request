# Permission Agent

[中文](README.md)

A Claude Code plugin that automatically approves safe **Permission Requests**, escalates potentially risky operations to the user for confirmation, and logs all requests.

## Prerequisites

- [Claude Code](https://claude.ai/code) v2.0.45 or later
- [uv](https://docs.astral.sh/uv/) — Python package manager
- macOS (notifications rely on `osascript`)

## Introduction

Claude Code shows a permission dialog before executing certain operations (running shell commands, reading/writing files, calling MCP tools). This plugin intercepts each request before the dialog appears and uses an LLM to assess risk:

- **Safe operations** (reading files, local commands, read-only API calls, etc.) → auto-approved, no manual confirmation needed
- **Risky operations** (deleting system files, writing to external systems, etc.) → escalated to the user, dialog appears and a system notification is sent

All requests and decisions are logged to `~/.auto-permission-request/log/`.

## Installation

### Via Marketplace

```bash
claude plugin marketplace add Yuxin61/cc-marketplace
claude plugin install auto-permission-request@yuxin-s
```

## Configuration

### User Config File

Edit `~/.auto-permission-request/config/config.json`:

```json
{
  "redactTerms": ["your-username", "sensitive-term"]
}
```

- **`redactTerms`**: Before sending a request to the LLM for risk assessment, these terms are replaced with `[REDACTED]` to prevent sensitive information from being sent to the model. The original unredacted data is still written to the log files.

If the file does not exist, the plugin runs normally with an empty `redactTerms` list.

### LLM Model

The plugin selects a model using the following environment variables (configured in the `env` section of `~/.claude/settings.json`):

| Variable | Description |
|---|---|
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | Model to use, defaults to `claude-haiku-latest` |
| `ANTHROPIC_BASE_URL` | Custom API proxy URL |
| `ANTHROPIC_AUTH_TOKEN` | API authentication token |

### Tool Description Files

YAML files in `~/.auto-permission-request/config/` describe the risk profile of each tool, giving the LLM context to make better decisions:

| File | Contents |
|---|---|
| `tools-built-in.yaml` | Claude Code built-in tools (Bash, Read, Write, etc.) |
| `mcp-chrome-devtools.yaml` | Chrome DevTools MCP tools |
| `mcp-excalidraw.yaml` | Excalidraw MCP tools |

After enabling a new MCP server, run the following to check for missing tool descriptions:

```bash
uv run utils/check-missing-tools.py
```

Then add descriptions for the missing tools to the appropriate `~/.auto-permission-request/config/mcp-*.yaml` file.

### Customizing the Assessment Logic

Edit `config/prompt.txt` to adjust the LLM's risk assessment principles.

## Logs

All permission requests are logged to `~/.auto-permission-request/log/`. Each request creates one JSONL file named by nanosecond timestamp, containing two lines:

1. The original permission request (unredacted)
2. The plugin's decision output

## Project Structure

```
permission-agent/
├── .claude-plugin/
│   └── plugin.json          # Plugin manifest
├── config/
│   └── prompt.txt           # LLM assessment prompt (version-controlled)
├── hooks/
│   └── hooks.json           # PermissionRequest hook registration
├── src/
│   └── agent.py             # Main hook script
└── utils/
    └── check-missing-tools.py  # Check for missing tool descriptions

~/.auto-permission-request/
├── config/
│   ├── config.json          # User config (redactTerms)
│   ├── tools-built-in.yaml  # Built-in tool descriptions
│   └── mcp-*.yaml           # MCP tool descriptions
└── log/                     # Permission request logs (JSONL)
```
