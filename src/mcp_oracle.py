"""Thin async bridge to Oracle's SQLcl MCP server (`sql -mcp`). Reused across projects."""
from __future__ import annotations

import contextlib
import os
from typing import Any, AsyncIterator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MCP_CLIENT_ID = "in-db-embeddings-rag/0.1"
MCP_MODEL_ID = os.getenv("OPENAI_MODEL", "gpt-4o")


def _text_of(result: Any) -> str:
    parts = [t for item in (getattr(result, "content", []) or [])
             if (t := getattr(item, "text", None)) is not None]
    return "\n".join(parts).strip() or "(no output)"


class OracleMCP:
    def __init__(self, command: str, connection_name: str):
        self._command, self._connection_name = command, connection_name
        self._session: ClientSession | None = None
        self._schemas: dict[str, dict] = {}
        self._stack = contextlib.AsyncExitStack()

    async def __aenter__(self) -> "OracleMCP":
        params = StdioServerParameters(command=self._command, args=["-mcp"], env=dict(os.environ))
        try:
            read, write = await self._stack.enter_async_context(stdio_client(params))
            self._session = await self._stack.enter_async_context(ClientSession(read, write))
            await self._session.initialize()
            for tool in (await self._session.list_tools()).tools:
                self._schemas[tool.name] = tool.inputSchema or {}
            await self._connect()
        except BaseException:
            await self._stack.aclose()
            raise
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._stack.aclose()

    def _arg_name(self, tool: str, *hints: str) -> str:
        props = self._schemas.get(tool, {}).get("properties", {})
        if not props:
            return hints[0]
        for hint in hints:
            for prop in props:
                if hint in prop.lower():
                    return prop
        return next(iter(props))

    async def _call(self, tool: str, args: dict[str, Any]) -> str:
        assert self._session is not None
        props = self._schemas.get(tool, {}).get("properties", {})
        payload = dict(args)
        if "mcp_client" in props:
            payload.setdefault("mcp_client", MCP_CLIENT_ID)
        if "model" in props:
            payload.setdefault("model", MCP_MODEL_ID)
        return _text_of(await self._session.call_tool(tool, payload))

    async def _connect(self) -> None:
        name_arg = self._arg_name("connect", "conn", "name")
        try:
            await self._call("connect", {name_arg: self._connection_name})
        except Exception:
            pass
        probe = await self.run_sql("SELECT user FROM dual")
        if any(m in probe for m in ("ORA-", "not established")) or "ERROR" in probe.upper():
            raise RuntimeError(f"SQLcl MCP failed to connect to '{self._connection_name}':\n{probe}")

    async def run_sql(self, sql: str) -> str:
        return await self._call("run-sql", {self._arg_name("run-sql", "sql", "query", "statement"): sql})

    async def run_sqlcl(self, command: str) -> str:
        return await self._call("run-sqlcl", {self._arg_name("run-sqlcl", "sqlcl", "command"): command})

    @property
    def tool_names(self) -> list[str]:
        return list(self._schemas)


@contextlib.asynccontextmanager
async def open_oracle_mcp(command: str, connection_name: str) -> AsyncIterator[OracleMCP]:
    async with OracleMCP(command, connection_name) as mcp:
        yield mcp
