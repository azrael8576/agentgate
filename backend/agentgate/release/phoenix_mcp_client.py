import json
import os
import select
import subprocess
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


class PhoenixMCPError(RuntimeError):
    """Raised when Phoenix MCP evidence cannot be queried."""


@dataclass(frozen=True)
class PhoenixMCPConfig:
    base_url: str
    api_key: str
    project_identifier: str
    command: tuple[str, ...] = ("npx", "-y", "@arizeai/phoenix-mcp@latest")


class PhoenixMCPClient:
    def __init__(self, config: PhoenixMCPConfig, timeout_seconds: float = 30.0) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds
        self._next_id = 1
        self._process: subprocess.Popen[str] | None = None

    def __enter__(self) -> "PhoenixMCPClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def start(self) -> None:
        if self._process is not None:
            return
        command = [
            *self.config.command,
            "--baseUrl",
            self.config.base_url,
            "--apiKey",
            self.config.api_key,
        ]
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agentgate", "version": "0.1.0"},
            },
        )
        self._notify("notifications/initialized", {})

    def close(self) -> None:
        if self._process is None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()
        self._process = None

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self._request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )
        return _decode_tool_result(result)

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        process = self._require_process()
        assert process.stdin is not None
        process.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": method, "params": params}) + "\n"
        )
        process.stdin.flush()

    def _request(self, method: str, params: dict[str, Any]) -> Any:
        process = self._require_process()
        assert process.stdin is not None
        assert process.stdout is not None
        request_id = self._next_id
        self._next_id += 1
        process.stdin.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params,
                }
            )
            + "\n"
        )
        process.stdin.flush()

        while True:
            ready, _, _ = select.select([process.stdout], [], [], self.timeout_seconds)
            if not ready:
                raise PhoenixMCPError(
                    f"Phoenix MCP {method} timed out after {self.timeout_seconds:.0f}s."
                )
            line = process.stdout.readline()
            if line == "":
                stderr = ""
                if process.stderr is not None:
                    stderr = process.stderr.read()
                raise PhoenixMCPError(f"Phoenix MCP server exited before response. stderr={stderr}")
            payload = json.loads(line)
            if payload.get("id") != request_id:
                continue
            if "error" in payload:
                raise PhoenixMCPError(f"Phoenix MCP {method} failed: {payload['error']}")
            return payload.get("result")

    def _require_process(self) -> subprocess.Popen[str]:
        if self._process is None:
            raise PhoenixMCPError("Phoenix MCP client is not started.")
        return self._process


def load_phoenix_mcp_config(
    project_identifier: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> PhoenixMCPConfig:
    resolved_base_url = base_url or os.getenv("PHOENIX_HOST") or os.getenv("PHOENIX_BASE_URL")
    collector_endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
    if resolved_base_url is None and collector_endpoint:
        resolved_base_url = _base_url_from_collector_endpoint(collector_endpoint)

    resolved_api_key = api_key or os.getenv("PHOENIX_API_KEY")
    resolved_project = (
        project_identifier or os.getenv("PHOENIX_PROJECT") or os.getenv("PHOENIX_PROJECT_NAME")
    )
    missing = [
        name
        for name, value in (
            (
                "PHOENIX_HOST or PHOENIX_BASE_URL or PHOENIX_COLLECTOR_ENDPOINT",
                resolved_base_url,
            ),
            ("PHOENIX_API_KEY", resolved_api_key),
            ("PHOENIX_PROJECT or PHOENIX_PROJECT_NAME", resolved_project),
        )
        if not value
    ]
    if missing:
        raise PhoenixMCPError("Missing Phoenix MCP configuration: " + ", ".join(missing))

    return PhoenixMCPConfig(
        base_url=str(resolved_base_url).rstrip("/"),
        api_key=str(resolved_api_key),
        project_identifier=str(resolved_project),
    )


def _base_url_from_collector_endpoint(endpoint: str) -> str:
    normalized = endpoint.rstrip("/")
    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.netloc:
        return normalized

    path = parsed.path
    for suffix in ("/v1/traces", "/v1/traces/"):
        if path.endswith(suffix.rstrip("/")):
            path = path[: -len(suffix.rstrip("/"))]
            break

    if not path:
        return f"{parsed.scheme}://{parsed.netloc}"
    return f"{parsed.scheme}://{parsed.netloc}{path}".rstrip("/")


def _decode_tool_result(result: Any) -> Any:
    if not isinstance(result, dict) or "content" not in result:
        return result
    if result.get("isError") is True:
        message = _tool_result_text(result)
        raise PhoenixMCPError(message or "Phoenix MCP tool call failed.")
    content = result.get("content")
    if not isinstance(content, list):
        return result
    decoded_blocks: list[Any] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if not isinstance(text, str):
            decoded_blocks.append(block)
            continue
        try:
            decoded_blocks.append(json.loads(text))
        except json.JSONDecodeError:
            if _looks_like_http_error_text(text):
                raise PhoenixMCPError(text) from None
            decoded_blocks.append(text)

    if len(decoded_blocks) == 1:
        decoded = decoded_blocks[0]
        if isinstance(decoded, str) and _looks_like_http_error_text(decoded):
            raise PhoenixMCPError(decoded)
        return decoded
    return decoded_blocks


def _tool_result_text(result: dict[str, Any]) -> str:
    content = result.get("content")
    if not isinstance(content, list):
        return ""
    texts = [
        block.get("text")
        for block in content
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    ]
    return "\n".join(texts)


def _looks_like_http_error_text(text: str) -> bool:
    lowered = text.lower()
    return (
        " unauthorized" in lowered
        or lowered.endswith("unauthorized")
        or " forbidden" in lowered
        or " invalid token" in lowered
        or ": 401" in lowered
        or ": 403" in lowered
    )
