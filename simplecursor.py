from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI

DEFAULT_MODEL = "gpt-4.1-mini"
MAX_FILE_CHARS = 4096
MAX_SEARCH_MATCHES = 200
BASE_DIR = Path.cwd().resolve()
CLIENT: OpenAI | None = None

SYSTEM_PROMPT = (
    "You are Cursor, a coding agent. Accomplish the user's task using the provided tools, "
    "one step at a time. First gather context by listing directories, searching, and reading "
    "files before editing. Do not invent file contents. Propose only one destructive action "
    "(write_file or run_command) at a time. When the task is complete, stop calling tools and "
    "summarize what you changed."
)


def _resolve_in_cwd(path: str) -> Path:
    resolved = (BASE_DIR / path).resolve()
    if resolved != BASE_DIR and BASE_DIR not in resolved.parents:
        raise ValueError(f"path escapes working directory: {path}")
    return resolved


def _truncate(text: str, limit: int = MAX_FILE_CHARS) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n\n...[truncated to {limit} chars]"


def read_file(path: str) -> str:
    try:
        target = _resolve_in_cwd(path)
        if not target.exists() or not target.is_file():
            return f"ERROR: file not found: {path}"
        return _truncate(target.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001 - tools return errors as strings
        return f"ERROR: {exc}"


def list_dir(path: str) -> str:
    try:
        target = _resolve_in_cwd(path)
        if not target.exists() or not target.is_dir():
            return f"ERROR: directory not found: {path}"
        entries: list[str] = []
        for entry in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            suffix = "/" if entry.is_dir() else ""
            entries.append(f"{entry.name}{suffix}")
        return "\n".join(entries) or "(empty directory)"
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


def search(query: str, path: str = ".") -> str:
    if not query:
        return "ERROR: query cannot be empty"
    try:
        target = _resolve_in_cwd(path)
        if not target.exists():
            return f"ERROR: path not found: {path}"
        files = [target] if target.is_file() else [p for p in target.rglob("*") if p.is_file()]
        matches: list[str] = []
        lowered = query.lower()
        for file_path in files:
            try:
                lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for idx, line in enumerate(lines, start=1):
                if lowered in line.lower():
                    rel = file_path.relative_to(BASE_DIR)
                    matches.append(f"{rel}:{idx}: {line}")
                    if len(matches) >= MAX_SEARCH_MATCHES:
                        return "\n".join(matches) + "\n...[search results truncated]"
        return "\n".join(matches) if matches else "(no matches)"
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


def write_file(path: str, content: str) -> str:
    try:
        target = _resolve_in_cwd(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"wrote file: {target.relative_to(BASE_DIR)}"
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


def run_command(command: str) -> str:
    try:
        # shell=True is intentionally used for simplicity and broad CLI compatibility; it has
        # command-injection risk and should be hardened in production tools.
        completed = subprocess.run(  # noqa: S602
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=BASE_DIR,
            timeout=60,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        output = output.strip() or "(no output)"
        return _truncate(f"exit_code={completed.returncode}\n{output}", limit=MAX_FILE_CHARS)
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the working directory",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List entries in a directory",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search for text in files under a path",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write full content to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command in the current working directory",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
]

DISPATCH: dict[str, Callable[..., str]] = {
    "read_file": read_file,
    "list_dir": list_dir,
    "search": search,
    "write_file": write_file,
    "run_command": run_command,
}
DESTRUCTIVE: set[str] = {"write_file", "run_command"}


def _preview_write(path: str, content: str) -> str:
    preview = _truncate(content, limit=300)
    return f"write_file target={path}\npreview:\n{preview}"


def _request_approval(name: str, args: dict[str, Any]) -> bool:
    if name == "write_file":
        print(_preview_write(str(args.get("path", "")), str(args.get("content", ""))))
    elif name == "run_command":
        print(f"run_command command={args.get('command', '')}")
    answer = input("approve? [y/N] ").strip().lower()
    return answer == "y"


def execute_tool(name: str, args: dict[str, Any], auto_approve: bool) -> str:
    if name not in DISPATCH:
        return f"ERROR: unknown tool: {name}"
    if name in DESTRUCTIVE and not auto_approve:
        if not _request_approval(name, args):
            return "user denied this action"
    try:
        return DISPATCH[name](**args)
    except TypeError as exc:
        return f"ERROR: bad arguments for {name}: {exc}"
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


def _assistant_message_payload(message: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in message.tool_calls
        ]
    return payload


def agent_loop(task: str, *, max_steps: int, verbose: bool, auto_approve: bool) -> None:
    if CLIENT is None:
        raise RuntimeError("OpenAI client is not initialized")

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    if verbose:
        print("System prompt:")
        print(SYSTEM_PROMPT)
        print("-" * 60)

    for step in range(1, max_steps + 1):
        print(f"Step {step}")
        if verbose:
            print(f"messages={len(messages)}")

        response = CLIENT.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        message = response.choices[0].message
        messages.append(_assistant_message_payload(message))

        tool_calls = message.tool_calls or []
        if not tool_calls:
            final_text = (message.content or "").strip() or "(no summary)"
            print("Final summary:")
            print(final_text)
            return

        for call in tool_calls:
            raw_args = call.function.arguments or "{}"
            print(f"Tool call: {call.function.name} args={raw_args}")
            try:
                parsed_args = json.loads(raw_args)
                if not isinstance(parsed_args, dict):
                    parsed_args = {}
            except json.JSONDecodeError:
                parsed_args = {}

            result = execute_tool(call.function.name, parsed_args, auto_approve)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.function.name,
                    "content": result,
                }
            )

    print(f"Stopped after reaching max steps ({max_steps}).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SimpleCursor: minimal agentic coding assistant",
        usage='python simplecursor.py "<task in plain English>" [--verbose] [--auto-approve] [--max-steps N]',
    )
    parser.add_argument("task", help="Task in plain English")
    parser.add_argument("--verbose", action="store_true", help="Print system prompt and message count")
    parser.add_argument("--auto-approve", action="store_true", help="Skip approval prompts")
    parser.add_argument("--max-steps", type=int, default=15, help="Maximum agent loop iterations")
    args = parser.parse_args()

    if args.max_steps < 1:
        parser.error("--max-steps must be >= 1")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "OPENAI_API_KEY is not set. Set it first, e.g. '\n"
            "  bash: export OPENAI_API_KEY=...\n"
            "  powershell: $env:OPENAI_API_KEY=...\n'"
        )

    global CLIENT
    CLIENT = OpenAI(api_key=api_key)
    agent_loop(args.task, max_steps=args.max_steps, verbose=args.verbose, auto_approve=args.auto_approve)


if __name__ == "__main__":
    main()
