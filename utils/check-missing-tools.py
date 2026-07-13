#!/usr/bin/env python3
# /// script
# dependencies = ["pyyaml"]
# ///
"""
Check which MCP tools are missing from config/tools.yaml.
Prints tool name and description for each missing tool.
Does not modify tools.yaml.

Usage:
    uv run utils/check-missing-tools.py           # output to stdout
    uv run utils/check-missing-tools.py -o out.txt  # output to file
"""

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".auto-permission-request" / "config"


def get_mcp_servers() -> dict[str, str]:
    """Parse `claude mcp list` output into {server_name: command}."""
    result = subprocess.run(
        ["claude", "mcp", "list"],
        capture_output=True,
        text=True,
    )
    servers = {}
    for line in result.stdout.splitlines():
        # Format: "server-name: command - ✔ Connected"
        m = re.match(r"^([^:]+(?::[^:]+)*?):\s+(.+?)\s+-\s+[✔✘]", line)
        if m:
            name = m.group(1).strip()
            command = m.group(2).strip()
            servers[name] = command
    return servers


def server_name_to_prefix(server_name: str) -> str:
    """Convert MCP server name to Claude Code tool_name prefix.
    e.g. 'plugin:chrome-devtools-mcp:chrome-devtools' -> 'mcp__plugin_chrome-devtools-mcp_chrome-devtools__'
    """
    return "mcp__" + server_name.replace(":", "_") + "__"


def resolve_npx_command(command: str) -> str:
    """Try to resolve an npx command to a direct `node <path>` invocation.
    Falls back to the original command on any failure.
    """
    # Extract package name from e.g. "npx chrome-devtools-mcp@latest"
    m = re.match(r"npx\s+([a-zA-Z0-9@/_.-]+)", command)
    if not m:
        return command
    package_spec = m.group(1)
    package_name = re.sub(r"@[^/]+$", "", package_spec)  # strip @version

    # Ask npm to resolve the package's main entry point
    resolve_cmd = (
        f"npm exec --package={package_spec} -c "
        f"'node -e \"console.log(require.resolve(\\'{package_name}\\'))\"'"
    )
    try:
        result = subprocess.run(
            resolve_cmd,
            capture_output=True,
            text=True,
            timeout=30,
            shell=True,
        )
        path = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
        if path and Path(path).exists():
            return f"node {path}"
    except Exception:
        pass
    return command


def get_tools_from_server(command: str) -> list[dict]:
    """Send tools/list to an MCP server via stdio and return the tools list."""
    if command.startswith("npx"):
        resolved = resolve_npx_command(command)
        if resolved != command:
            print(f"  (resolved to: {resolved})", file=sys.stderr)
        command = resolved

    request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    try:
        proc = subprocess.Popen(
            shlex.split(command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
            text=True,
        )
        stdout, _ = proc.communicate(input=request + "\n", timeout=15)
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("id") == 1 and "result" in data:
                return data["result"].get("tools", [])
        return []
    except Exception as e:
        print(f"  [error querying server] {e}", file=sys.stderr)
        return []


def get_known_tool_names() -> set[str]:
    """Read all tool names already defined in config YAML files."""
    import yaml

    known = set()
    for yaml_file in sorted(CONFIG_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            known.update(entry["name"] for entry in data.get("tools", []) if "name" in entry)
        except Exception as e:
            print(f"Warning: could not read {yaml_file.name}: {e}", file=sys.stderr)
    return known


def main() -> None:
    parser = argparse.ArgumentParser(description="Check missing MCP tools in tools.yaml")
    parser.add_argument("-o", "--output", help="Write output to file instead of stdout")
    args = parser.parse_args()

    out = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout

    try:
        print("Fetching MCP servers...", file=sys.stderr)
        servers = get_mcp_servers()
        if not servers:
            print("No MCP servers found.", file=sys.stderr)
            return

        known = get_known_tool_names()
        missing = []

        for server_name, command in servers.items():
            prefix = server_name_to_prefix(server_name)
            print(f"Querying {server_name}...", file=sys.stderr)
            tools = get_tools_from_server(command)
            for tool in tools:
                tool_name = prefix + tool["name"]
                if tool_name not in known:
                    missing.append({
                        "tool_name": tool_name,
                        "description": tool.get("description", ""),
                    })

        if not missing:
            print("All MCP tools are covered in ~/.auto-permission-request/config/.", file=sys.stderr)
            return

        print(f"{len(missing)} tool(s) missing from ~/.auto-permission-request/config/:\n", file=out)
        for t in missing:
            print(f"  {t['tool_name']}", file=out)
            if t["description"]:
                print(f"    {t['description']}", file=out)
            print(file=out)

        if args.output:
            print(f"Output written to {args.output}", file=sys.stderr)
    finally:
        if args.output and out is not sys.stdout:
            out.close()


if __name__ == "__main__":
    main()
