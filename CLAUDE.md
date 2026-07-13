# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

A Claude Code **plugin** (`auto-permission-request`) that intercepts every `PermissionRequest` hook event before the dialog appears, asks a Haiku LLM to assess risk, and either auto-approves safe operations or escalates risky ones to the user with a macOS notification. All requests are logged to `~/.permission-requests/`.

## Running the Agent

The agent (`src/agent.py`) is invoked by the Claude Code hook system, not run directly. To test it manually, pipe a JSON permission request to it:

```bash
echo '{"tool_name":"Read","tool_input":{"file_path":"/tmp/test.txt"}}' | uv run src/agent.py
```

## Checking for Missing Tool Descriptions

After adding a new MCP server, check which tools lack descriptions:

```bash
uv run utils/check-missing-tools.py
# or write to a file:
uv run utils/check-missing-tools.py -o missing.txt
```

This queries live MCP servers via `claude mcp list` and compares against all `config/*.yaml` files.

## Architecture

### Hook Flow

1. Claude Code fires `PermissionRequest` → `hooks/hooks.json` routes it to `src/agent.py` via `uv run`
2. `agent.py` reads the request JSON from stdin
3. Terms in `config/config.json` (`redactTerms`) are substituted with `[REDACTED]` before sending to the LLM
4. `config/*.yaml` files are scanned for a matching tool entry; first match wins (top-to-bottom within each file, files processed in sorted order)
5. The matched description (or nothing) is injected into `config/prompt.txt` as `{tool_context}`; the redacted JSON goes into `{request_json}`
6. Haiku is called; the response must be `{"decision": "allow"|"ask", "reason": "..."}`
7. Result + original unredacted request are written as a two-line JSONL to `~/.auto-permission-request/log/<ns-timestamp>.jsonl`; if `decision == "ask"`, a macOS notification fires
8. The output JSON is printed to stdout for Claude Code to consume

### Tool Description Matching (`config/*.yaml`)

Each YAML file has a top-level `tools` array. Each entry has:
- `name`: exact tool name (e.g. `"Bash"`, `"mcp__plugin_chrome-devtools-mcp_chrome-devtools__click"`)
- `match.type`: `"exact"` (matches any call to that tool) or `"regex"` (also requires `field` + `pattern` to match a field in `tool_input`)
- `description`: free-text context injected into the LLM prompt

For `Bash` in particular, more-specific `regex` rules must come **before** the catch-all `exact` rule.

### Configuration

| File | Purpose |
|---|---|
| `~/.auto-permission-request/config/config.json` | `redactTerms` list — terms replaced with `[REDACTED]` before LLM call |
| `~/.auto-permission-request/config/tools-built-in.yaml` | Risk descriptions for Claude Code built-in tools |
| `~/.auto-permission-request/config/mcp-*.yaml` | Risk descriptions for MCP server tools |
| `<plugin-root>/config/prompt.txt` | LLM system prompt with `{tool_context}` and `{request_json}` placeholders (version-controlled) |
| `hooks/hooks.json` | Registers the `PermissionRequest` hook |
| `.claude-plugin/plugin.json` | Plugin manifest (name, version, author) |

`config/config.json` and all `*.yaml` files live in `~/.auto-permission-request/config/` (outside the repo). Only `config/prompt.txt` is tracked in git.

### LLM Model Selection

Configured via environment variables in `~/.claude/settings.json` (`env` section):
- `ANTHROPIC_DEFAULT_HAIKU_MODEL` — model to use (default: `claude-haiku-latest`)
- `ANTHROPIC_BASE_URL` — optional API proxy
- `ANTHROPIC_AUTH_TOKEN` — optional custom auth token

### Dependencies

`src/agent.py` uses inline PEP 723 script metadata (`# /// script`) — `uv run` installs `anthropic` and `pyyaml` automatically into an isolated environment. No `pyproject.toml` or manual venv needed.
