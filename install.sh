#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="$HOME/.auto-permission-request/config"

echo "Installing auto-permission-request..."

# ---------------------------------------------------------------------------
# 1. Install the plugin via Claude Code marketplace
# ---------------------------------------------------------------------------
claude plugin marketplace add Yuxin61/cc-marketplace
claude plugin install auto-permission-request@yuxin-s

# ---------------------------------------------------------------------------
# 2. Create config directory
# ---------------------------------------------------------------------------
mkdir -p "$CONFIG_DIR"

# ---------------------------------------------------------------------------
# 3. Write config.json (skip if exists)
# ---------------------------------------------------------------------------
CONFIG_JSON="$CONFIG_DIR/config.json"
if [ ! -f "$CONFIG_JSON" ]; then
    cat > "$CONFIG_JSON" << 'EOF'
{
  "redactTerms": []
}
EOF
    echo "Created $CONFIG_JSON"
else
    echo "Skipped $CONFIG_JSON (already exists)"
fi

# ---------------------------------------------------------------------------
# 4. Write tools-built-in.yaml (skip if exists)
# ---------------------------------------------------------------------------
TOOLS_YAML="$CONFIG_DIR/tools-built-in.yaml"
if [ ! -f "$TOOLS_YAML" ]; then
    cat > "$TOOLS_YAML" << 'EOF'
# Built-in Claude Code tool descriptions.
# Rules are matched top-to-bottom; first match wins within this file.
# Bash has multiple entries — more specific regex rules must come before the catch-all exact rule.

tools:

  # ---------------------------------------------------------------------------
  # Bash — webbridge (kimi-webbridge local browser automation daemon)
  # Matched when the command calls the local daemon at 127.0.0.1:10086
  # ---------------------------------------------------------------------------
  - name: "Bash"
    match:
      type: regex
      field: command
      pattern: "127\\.0\\.0\\.1:10086"
    description: |
      This command uses the kimi-webbridge browser automation daemon running locally
      at 127.0.0.1:10086. It controls the user's real browser via a local HTTP API.

      Available actions and their risk profile:
      - navigate: opens a URL in the browser — read-like, always safe
      - find_tab: locates an existing tab — read-only, always safe
      - snapshot: reads the accessibility tree of the current page — read-only, always safe
      - click: simulates a click on an element — SAFE for navigation/expand/tab-switch;
        ESCALATE if clicking a button that clearly submits, saves, publishes, deletes,
        or confirms an irreversible action on an external system (e.g. "Save", "Submit",
        "Delete", "Publish", "Confirm", "Send")
      - fill: types into an input field — safe by itself; only risky if immediately
        followed by a submit action in the same command
      - evaluate: runs JavaScript in the page — safe for reading DOM state; escalate
        if it clearly mutates external server state
      - screenshot / save_as_pdf: saves to local disk — always safe
      - network: reads network traffic — read-only, always safe
      - upload: uploads a file — safe; the actual risk is in what the receiving page does
      - list_tabs / close_tab / close_session: tab management — always safe
      - sleep: just waits — always safe

      Key principle: this daemon only controls the local browser. The question is
      whether the browser action itself causes an irreversible change on an external
      system. Reading, navigating, and observing are always safe.

  # ---------------------------------------------------------------------------
  # Bash — kimi-webbridge CLI (status/start/stop)
  # ---------------------------------------------------------------------------
  - name: "Bash"
    match:
      type: regex
      field: command
      pattern: "kimi-webbridge"
    description: |
      This command runs the kimi-webbridge CLI to manage the local browser automation
      daemon (status check, start, stop). It only affects a local process.
      Always safe.

  # ---------------------------------------------------------------------------
  # Bash — general shell commands (catch-all)
  # ---------------------------------------------------------------------------
  - name: "Bash"
    match:
      type: exact
    description: |
      This is a general shell command. Reason through what it actually does:

      1. Does it read or write? Reading files, listing directories, parsing output,
         running local tools are generally safe.
      2. If it writes or deletes: is the target a critical local system file
         (e.g. /etc/sudoers, ~/.ssh/id_rsa, system configs)? If yes, escalate.
         Temp files (/tmp), project files, and build artifacts are safe.
      3. If it makes a network request (curl, wget, etc.): is the destination
         localhost/127.0.0.1? Always safe. Is it an external host? Safe unless
         the destination is unexpected or untrusted - i.e., a host unrelated to the
         current project or task context. The presence of credentials (tokens, cookies,
         API keys) in the request is normal and should not by itself trigger escalation.
      4. Does it delete irreplaceable data (user documents, source code, system files)?
         Escalate. Deleting /tmp files or generated files is safe.

  # ---------------------------------------------------------------------------
  # Read
  # ---------------------------------------------------------------------------
  - name: "Read"
    match:
      type: exact
    description: |
      Reads a file from the local filesystem. This is always a read-only operation.
      Safe regardless of what the file contains (credentials, configs, keys, etc.)
      — reading does not expose data to anyone; it just displays content locally.
      Always allow.

  # ---------------------------------------------------------------------------
  # Edit
  # ---------------------------------------------------------------------------
  - name: "Edit"
    match:
      type: exact
    description: |
      Edits a file by replacing a string in it. Risk depends on the target file:
      - Project files, config files in the user's own directories: safe
      - /tmp files: safe
      - System integrity files (/etc/sudoers, /etc/shadow, /etc/hosts, SSH keys,
        boot config): escalate — modifications can break or compromise the system

  # ---------------------------------------------------------------------------
  # Write
  # ---------------------------------------------------------------------------
  - name: "Write"
    match:
      type: exact
    description: |
      Creates or overwrites a file. Risk depends on WHERE, not on WHAT the file contains.
      - User's project directories, /tmp, home directory files: safe regardless of content
      - System integrity files (/etc/sudoers, /etc/shadow, SSH keys, boot config): escalate
      Never escalate based on file content alone (URLs, tokens, credentials, infrastructure
      data written to a local file stay local and are not exposed to anyone).

  # ---------------------------------------------------------------------------
  # WebFetch
  # ---------------------------------------------------------------------------
  - name: "WebFetch"
    match:
      type: exact
    description: |
      Fetches content from a URL over HTTP/HTTPS. This is a read operation.
      Always safe — it retrieves data, does not modify any external state.

  # ---------------------------------------------------------------------------
  # WebSearch
  # ---------------------------------------------------------------------------
  - name: "WebSearch"
    match:
      type: exact
    description: |
      Performs a web search. Read-only operation.
      Always safe.

  # ---------------------------------------------------------------------------
  # Agent
  # ---------------------------------------------------------------------------
  - name: "Agent"
    match:
      type: exact
    description: |
      Spawns a subagent to handle a subtask. The subagent will itself trigger
      permission requests for any risky actions it takes. Spawning is safe;
      assess the subagent's individual tool calls when they come in.
      Always allow the spawn itself.

  # ---------------------------------------------------------------------------
  # Workflow
  # ---------------------------------------------------------------------------
  - name: "Workflow"
    match:
      type: exact
    description: |
      Runs a workflow script that orchestrates multiple subagents. Similar to Agent —
      the workflow itself is an orchestration layer; individual tool calls within it
      will trigger their own permission requests.
      Always allow the workflow launch itself.

  # ---------------------------------------------------------------------------
  # LSP
  # ---------------------------------------------------------------------------
  - name: "LSP"
    match:
      type: exact
    description: |
      Language Server Protocol operation (go to definition, find references, hover, etc.).
      Read-only code intelligence query against the local codebase.
      Always safe.

  # ---------------------------------------------------------------------------
  # NotebookEdit
  # ---------------------------------------------------------------------------
  - name: "NotebookEdit"
    match:
      type: exact
    description: |
      Edits a Jupyter notebook cell. Local file modification.
      Safe for user's own project notebooks. Same risk profile as Edit.
EOF
    echo "Created $TOOLS_YAML"
else
    echo "Skipped $TOOLS_YAML (already exists)"
fi

echo "Done."
