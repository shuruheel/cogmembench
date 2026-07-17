from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from ..config import ROOT
from .mindgraph_client import MindGraphHTTPMemory


COGNITIVE_TOOL_NAMES = {
    "mindgraph_capture",
    "mindgraph_reason",
    "mindgraph_commit",
    "mindgraph_plan",
    "mindgraph_retrieve",
}


class MCPStdioClient:
    """Minimal synchronous MCP client used to exercise the production server contract."""

    def __init__(self, command: list[str], env: dict[str, str]):
        self._next_id = 1
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env,
        )
        initialized = self.request(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "cogmembench", "version": "0.1.0"},
            },
        )
        self.instructions = str(initialized.get("instructions") or "")
        self.server_info = initialized.get("serverInfo") or {}
        self.notify("notifications/initialized", {})

    def _write(self, payload: dict[str, Any]) -> None:
        if self._process.stdin is None:
            raise RuntimeError("MCP stdin is unavailable")
        self._process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self._process.stdin.flush()

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        if self._process.stdout is None:
            raise RuntimeError("MCP stdout is unavailable")
        while True:
            line = self._process.stdout.readline()
            if not line:
                code = self._process.poll()
                raise RuntimeError(f"MCP server exited before response (code={code})")
            message = json.loads(line)
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError(f"MCP error: {message['error']}")
            result = message.get("result")
            return result if isinstance(result, dict) else {"value": result}

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def close(self) -> None:
        if self._process.poll() is not None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=3)


def _default_mcp_command() -> list[str]:
    configured = os.getenv("COGMEMBENCH_MCP_ENTRYPOINT")
    entrypoint = (
        Path(configured)
        if configured
        else ROOT.parent / "mindgraph-mcp" / "dist" / "index.js"
    )
    return [os.getenv("COGMEMBENCH_NODE_BINARY", "node"), str(entrypoint)]


class MindGraphMCPMemory(MindGraphHTTPMemory):
    """HTTP lifecycle/snapshot adapter with production MCP tool schemas and dispatch."""

    def __init__(self, base_url: str, **kwargs: Any):
        super().__init__(base_url, **kwargs)
        api_key = self.api_key or os.getenv("MINDGRAPH_API_KEY")
        if not api_key and base_url.startswith(("http://127.0.0.1", "http://localhost")):
            api_key = "cogmembench-local"
        if not api_key:
            raise RuntimeError("production MCP integration requires MINDGRAPH_API_KEY")
        env = {
            **os.environ,
            "MINDGRAPH_API_KEY": api_key,
            "MINDGRAPH_BASE_URL": base_url,
            "MINDGRAPH_AGENT_ID": self.agent_id,
        }
        self._mcp = MCPStdioClient(_default_mcp_command(), env)
        listed = self._mcp.request("tools/list", {})
        tools = [
            tool
            for tool in listed.get("tools", [])
            if isinstance(tool, dict) and tool.get("name") in COGNITIVE_TOOL_NAMES
        ]
        missing = COGNITIVE_TOOL_NAMES - {str(tool.get("name")) for tool in tools}
        if missing:
            self._mcp.close()
            raise RuntimeError(f"production MCP contract is missing tools: {sorted(missing)}")
        self.active_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", {"type": "object"}),
                },
            }
            for tool in tools
        ]
        canonical = json.dumps(self.active_tools, sort_keys=True, separators=(",", ":"))
        self.tool_contract_sha256 = hashlib.sha256(canonical.encode()).hexdigest()
        self.behavioral_contract = self._mcp.instructions
        self.behavioral_contract_sha256 = hashlib.sha256(
            self.behavioral_contract.encode()
        ).hexdigest()
        self.mcp_server_info = self._mcp.server_info

    def execute_tool(self, name: str, args: dict[str, Any], session_id: str) -> Any:
        result = self._mcp.request(
            "tools/call",
            {"name": name, "arguments": {**args, "agent_id": self.agent_id}},
        )
        content = result.get("content") or []
        texts = [item.get("text", "") for item in content if item.get("type") == "text"]
        parsed: list[Any] = []
        for value in texts:
            try:
                parsed.append(json.loads(value))
            except json.JSONDecodeError:
                parsed.append(value)
        observation: Any = parsed[0] if len(parsed) == 1 else parsed
        if result.get("isError"):
            raise RuntimeError(f"MCP tool error: {observation}")
        return observation

    def contract_manifest(self) -> dict[str, Any]:
        return {
            "tool_contract_sha256": self.tool_contract_sha256,
            "behavioral_contract_sha256": self.behavioral_contract_sha256,
            "server_info": self.mcp_server_info,
            "tools": [tool["function"]["name"] for tool in self.active_tools],
        }

    def close(self) -> None:
        self._mcp.close()
