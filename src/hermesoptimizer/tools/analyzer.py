"""Analyze sessions for tool usage patterns and missed opportunities."""
from __future__ import annotations

import json
import re
from pathlib import Path

from hermesoptimizer.tools.models import ToolUsage, ToolMiss


# Patterns that indicate the AI is doing something manually instead of using a tool
MANUAL_WORKAROUND_PATTERNS: dict[str, str] = {
    r"(?i)I will (create|write|generate) a script": "script_manual",
    r"(?i)I will (create|make|generate) (an? )?image": "image_gen_manual",
    r"(?i)I will (run|execute) (this|the) (command|cmd|shell)": "shell_manual",
    r"(?i)(let me|I\'ll) (write|create) (some )?code": "code_manual",
    r"(?i)I will (build|compile) (this|the) (program|app|application)": "build_manual",
    r"(?i)(let me|I\'ll) (use|write) (a )?regex": "regex_manual",
    r"(?i)I will (parse|extract) (this|the) (data|json|xml|csv)": "parse_manual",
    r"(?i)(let me|I\'ll) (search|look up|find) (this|that|it)": "search_manual",
}

# Map manual workaround types to suggested tools
MANUAL_TO_TOOL: dict[str, str] = {
    "script_manual": "execute_code",
    "image_gen_manual": "image_generate",
    "shell_manual": "terminal",
    "code_manual": "execute_code",
    "build_manual": "execute_code",
    "regex_manual": "execute_code",
    "parse_manual": "execute_code",
    "search_manual": "web_search",
}

# Known tool names that should be used instead of manual workarounds
KNOWN_TOOLS = {
    "image_generate", "image_gen", "generate_image", "create_image",
    "web_search", "search", "search_web",
    "execute_code", "run_code", "code_execute",
    "terminal", "shell", "run_command",
    "browser_navigate", "browser_click", "browser_type",
    "file_read", "file_write", "file_search",
    "send_message", "email_send",
    "cronjob", "schedule",
    "delegate_task",
    "text_to_speech", "tts",
    "vision_analyze", "image_analyze",
}


def extract_tool_calls(messages: list[dict]) -> dict[str, dict]:
    """Extract tool calls from session messages."""
    tools: dict[str, dict] = {}
    for msg in messages:
        if msg.get("role") == "assistant":
            tool_calls = msg.get("tool_calls", [])
            for tc in tool_calls:
                name = tc.get("function", {}).get("name", tc.get("name", "unknown"))
                if name not in tools:
                    tools[name] = {"count": 0, "success": 0, "failure": 0}
                tools[name]["count"] += 1
                # Assume success unless we see an error follow-up
                tools[name]["success"] += 1
        elif msg.get("role") == "tool":
            # Mark last tool call as failed if error
            if "error" in str(msg.get("content", "")).lower():
                # Find the most recent tool
                if tools:
                    last_tool = list(tools.keys())[-1]
                    tools[last_tool]["success"] -= 1
                    tools[last_tool]["failure"] += 1
    return tools


def detect_manual_workarounds(messages: list[dict]) -> list[ToolMiss]:
    """Detect when AI should have used a tool but did manual work instead."""
    misses: list[ToolMiss] = []
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        if not isinstance(content, str):
            continue

        for pattern, miss_type in MANUAL_WORKAROUND_PATTERNS.items():
            if re.search(pattern, content):
                suggested = MANUAL_TO_TOOL.get(miss_type, "unknown")
                misses.append(
                    ToolMiss(
                        session_id="",
                        miss_type=miss_type,
                        description=f"AI said: '{content[:80]}...' but should have used {suggested}",
                        suggested_tool=suggested,
                        severity="HIGH",
                    )
                )
                break  # One miss per message is enough
    return misses


def detect_tool_avoidance(session_data: dict) -> list[ToolMiss]:
    """Detect when a session has zero tool calls but should have used tools."""
    misses: list[ToolMiss] = []
    messages = session_data.get("messages", [])
    tool_calls = sum(
        len(msg.get("tool_calls", []))
        for msg in messages
        if msg.get("role") == "assistant"
    )

    # Count total assistant messages that look like they should use tools
    assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
    if len(assistant_msgs) > 3 and tool_calls == 0:
        misses.append(
            ToolMiss(
                session_id="",
                miss_type="tool_avoidance",
                description=f"Session has {len(assistant_msgs)} assistant turns but zero tool calls",
                suggested_tool="multiple",
                severity="MEDIUM",
            )
        )

    return misses


def detect_repeated_tool_failures(messages: list[dict]) -> list[ToolMiss]:
    """Detect when the same tool fails repeatedly."""
    misses: list[ToolMiss] = []
    tool_errors: dict[str, int] = {}

    for msg in messages:
        if msg.get("role") == "tool":
            content = str(msg.get("content", ""))
            if "error" in content.lower():
                # Try to identify which tool failed
                tool_name = msg.get("name", "unknown")
                tool_errors[tool_name] = tool_errors.get(tool_name, 0) + 1

    for tool_name, count in tool_errors.items():
        if count >= 3:
            misses.append(
                ToolMiss(
                    session_id="",
                    miss_type="repeated_tool_failure",
                    description=f"Tool '{tool_name}' failed {count} times in session",
                    suggested_tool="fallback_or_alternative",
                    severity="HIGH",
                )
            )

    return misses


class ToolAnalyzer:
    """Analyze tool usage across sessions."""

    def __init__(self, session_paths: list[Path]) -> None:
        self.session_paths = session_paths
        self.usages: list[ToolUsage] = []
        self.misses: list[ToolMiss] = []

    def analyze(self) -> None:
        """Parse all sessions and aggregate tool data."""
        for path in self.session_paths:
            self._parse_session(path)

    def _parse_session(self, path: Path) -> None:
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return

        session_id = data.get("session_id", path.stem)
        provider = data.get("provider", "unknown")
        model = data.get("model", "unknown")
        lane = data.get("lane", "default")
        messages = data.get("messages", [])

        # Extract tool calls
        tools = extract_tool_calls(messages)
        for name, stats in tools.items():
            self.usages.append(
                ToolUsage(
                    session_id=session_id,
                    provider=provider,
                    model=model,
                    lane=lane,
                    tool_name=name,
                    call_count=stats["count"],
                    success_count=stats["success"],
                    failure_count=stats["failure"],
                )
            )

        # Detect misses
        manual_misses = detect_manual_workarounds(messages)
        for m in manual_misses:
            m.session_id = session_id
        self.misses.extend(manual_misses)

        avoidance_misses = detect_tool_avoidance(data)
        for m in avoidance_misses:
            m.session_id = session_id
        self.misses.extend(avoidance_misses)

        failure_misses = detect_repeated_tool_failures(messages)
        for m in failure_misses:
            m.session_id = session_id
        self.misses.extend(failure_misses)

    def by_tool(self) -> dict[str, dict]:
        """Aggregate tool usage by tool name."""
        result: dict[str, dict] = {}
        for u in self.usages:
            if u.tool_name not in result:
                result[u.tool_name] = {"calls": 0, "success": 0, "failure": 0, "sessions": set()}
            result[u.tool_name]["calls"] += u.call_count
            result[u.tool_name]["success"] += u.success_count
            result[u.tool_name]["failure"] += u.failure_count
            result[u.tool_name]["sessions"].add(u.session_id)
        for k, v in result.items():
            v["sessions"] = len(v["sessions"])
        return result

    def by_provider(self) -> dict[str, dict]:
        """Aggregate tool usage by provider."""
        result: dict[str, dict] = {}
        for u in self.usages:
            if u.provider not in result:
                result[u.provider] = {"calls": 0, "tools": set(), "sessions": set()}
            result[u.provider]["calls"] += u.call_count
            result[u.provider]["tools"].add(u.tool_name)
            result[u.provider]["sessions"].add(u.session_id)
        for k, v in result.items():
            v["tools"] = len(v["tools"])
            v["sessions"] = len(v["sessions"])
        return result

    def by_model(self) -> dict[str, dict]:
        """Aggregate tool usage by model."""
        result: dict[str, dict] = {}
        for u in self.usages:
            if u.model not in result:
                result[u.model] = {"calls": 0, "tools": set(), "sessions": set()}
            result[u.model]["calls"] += u.call_count
            result[u.model]["tools"].add(u.tool_name)
            result[u.model]["sessions"].add(u.session_id)
        for k, v in result.items():
            v["tools"] = len(v["tools"])
            v["sessions"] = len(v["sessions"])
        return result

    def by_lane(self) -> dict[str, dict]:
        """Aggregate tool usage by lane."""
        result: dict[str, dict] = {}
        for u in self.usages:
            if u.lane not in result:
                result[u.lane] = {"calls": 0, "tools": set(), "sessions": set()}
            result[u.lane]["calls"] += u.call_count
            result[u.lane]["tools"].add(u.tool_name)
            result[u.lane]["sessions"].add(u.session_id)
        for k, v in result.items():
            v["tools"] = len(v["tools"])
            v["sessions"] = len(v["sessions"])
        return result

    def miss_rate(self) -> float:
        """Calculate tool miss rate (misses per session)."""
        sessions = len(set(u.session_id for u in self.usages)) or len(self.session_paths)
        if sessions == 0:
            return 0.0
        return len(self.misses) / sessions

    def misses_by_type(self) -> dict[str, int]:
        """Count misses by type."""
        result: dict[str, int] = {}
        for m in self.misses:
            result[m.miss_type] = result.get(m.miss_type, 0) + 1
        return result
