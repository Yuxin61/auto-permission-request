# /// script
# dependencies = ["anthropic", "pyyaml"]
# ///

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


USER_DIR = Path.home() / ".auto-permission-request"
CONFIG_DIR = USER_DIR / "config"
LOG_DIR = USER_DIR / "log"


def load_config() -> list[str]:
    config_path = CONFIG_DIR / "config.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        terms = data.get("redactTerms", [])
        return [t for t in terms if isinstance(t, str) and t]
    except Exception:
        return []


def anonymize(text: str, redact_terms: list[str]) -> str:
    for term in redact_terms:
        text = text.replace(term, "[REDACTED]")
    return text


def load_tool_description(request: dict) -> str:
    import yaml

    tools = []
    for yaml_file in sorted(CONFIG_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            tools.extend(data.get("tools", []))
        except Exception:
            pass

    tool_name = request.get("tool_name", "")
    tool_input = request.get("tool_input", {})

    for entry in tools:
        if entry.get("name") != tool_name:
            continue
        match = entry.get("match", {})
        if match.get("type") == "exact":
            return entry.get("description", "").strip()
        elif match.get("type") == "regex":
            field = match.get("field", "command")
            pattern = match.get("pattern", "")
            value = tool_input.get(field, "") if isinstance(tool_input, dict) else ""
            if re.search(pattern, value):
                return entry.get("description", "").strip()

    return ""


def load_prompt(plugin_root: str, request: dict, anonymized_json: str) -> str:
    prompt_path = Path(plugin_root) / "config" / "prompt.txt"
    template = prompt_path.read_text(encoding="utf-8")
    tool_description = load_tool_description(request)
    if tool_description:
        tool_section = f"## Tool context\n\n{tool_description}\n\n"
    else:
        tool_section = ""
    return template.replace("{tool_context}", tool_section).replace("{request_json}", anonymized_json)


_DECISION_TOOL = {
    "name": "submit_decision",
    "description": "Submit the permission decision.",
    "input_schema": {
        "type": "object",
        "properties": {
            "decision": {
                "type": "string",
                "enum": ["allow", "ask"],
                "description": "Whether to auto-approve or escalate to the user.",
            },
            "reason": {
                "type": "string",
                "description": "One sentence explanation.",
            },
        },
        "required": ["decision", "reason"],
    },
}


def call_haiku(prompt: str) -> dict:
    import anthropic

    client = anthropic.Anthropic(
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
        auth_token=os.environ.get("ANTHROPIC_AUTH_TOKEN"),
    )
    model = os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-latest")
    message = client.messages.create(
        model=model,
        max_tokens=256,
        tools=[_DECISION_TOOL],
        tool_choice={"type": "tool", "name": "submit_decision"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in message.content:
        if block.type == "tool_use" and block.name == "submit_decision":
            return block.input
    raise ValueError(f"model did not call submit_decision: {message.content}")


def make_output(decision: str, reason: str) -> dict:
    if decision == "allow":
        msg = f"[Permission Agent] ✓ Auto-approved: {reason}"
    else:
        msg = f"[Permission Agent] ⚠ Escalated to user: {reason}"
    return {
        "systemMessage": msg,
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {
                "behavior": decision,
            },
        },
    }


def write_log(request: dict, output: dict, prompt: str | None = None) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts_ns = time.time_ns()
        log_file = LOG_DIR / f"{ts_ns}.jsonl"
        with log_file.open("w", encoding="utf-8") as f:
            f.write(json.dumps(request, ensure_ascii=False) + "\n")
            f.write(json.dumps(output, ensure_ascii=False) + "\n")
        if prompt is not None:
            prompt_file = LOG_DIR / f"{ts_ns}.txt"
            prompt_file.write_text(prompt, encoding="utf-8")
    except Exception as e:
        print(f"[permission-agent] log write error: {e}", file=sys.stderr)


def notify(title: str, message: str) -> None:
    try:
        safe_title = title.replace('"', "'")
        safe_message = message[:100].replace('"', "'")
        script = f'display notification "{safe_message}" with title "{safe_title}" sound name "Glass"'
        subprocess.run(["osascript", "-e", script], check=False)
    except Exception:
        pass


def main() -> None:
    plugin_root = str(Path(__file__).parent.parent)

    raw_input = sys.stdin.read()

    # Parse request — if stdin is garbage, fall back to ask
    try:
        request = json.loads(raw_input)
    except Exception:
        request = {"_raw": raw_input}

    redact_terms = load_config()
    anonymized = anonymize(json.dumps(request, ensure_ascii=False), redact_terms)

    decision = "ask"
    reason = "agent error, escalated to user"
    prompt = None

    try:
        prompt = load_prompt(plugin_root, request, anonymized)
        result = call_haiku(prompt)
        raw_decision = result.get("decision", "ask")
        decision = "allow" if raw_decision == "allow" else "ask"
        reason = str(result.get("reason", "no reason provided"))
    except Exception as e:
        print(f"[permission-agent] assessment error: {e}", file=sys.stderr)
        decision = "ask"
        reason = f"agent error: {type(e).__name__}"

    output = make_output(decision, reason)
    write_log(request, output, prompt)
    if decision == "ask":
        tool = request.get("tool_name", "unknown tool")
        notify(f"Permission needed: {tool}", reason)
    print(json.dumps(output))


if __name__ == "__main__":
    main()
