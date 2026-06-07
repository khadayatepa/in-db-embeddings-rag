"""Persist RAG answers to Oracle (via MCP). Table prefix `rag_`."""
from __future__ import annotations

from mcp_oracle import OracleMCP


def _create_if_absent(ddl: str) -> str:
    body = ddl.replace("'", "''")
    return ("BEGIN EXECUTE IMMEDIATE '" + body + "'; "
            "EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF; END;")


DDL = [
    _create_if_absent(
        "CREATE TABLE rag_runs (run_id NUMBER PRIMARY KEY, question VARCHAR2(2000), "
        "embed_mode VARCHAR2(20), created_at TIMESTAMP DEFAULT SYSTIMESTAMP, answer CLOB, sources CLOB)"),
    "CREATE OR REPLACE VIEW v_rag_feed AS SELECT run_id, question, embed_mode, created_at, answer, sources FROM rag_runs",
]


def _q(text: str) -> str:
    t = (text or "").replace("'", "''")
    t = t.replace("&", "'||CHR(38)||'")
    t = t.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "'||CHR(10)||'")
    return "'" + t + "'"


def _clob(text: str, size: int = 1500) -> str:
    raw = text or ""
    chunks = [raw[i:i + size] for i in range(0, len(raw), size)] or [""]
    return "||".join("TO_CLOB(" + _q(c) + ")" for c in chunks)


async def _exec(mcp: OracleMCP, sql: str, what: str) -> None:
    out = await mcp.run_sql(sql)
    if "ORA-" in out or "Error" in out or "cancelled" in out:
        ora = next((ln for ln in out.splitlines() if "ORA-" in ln), out[:300])
        raise RuntimeError(f"persist {what} FAILED: {ora}")


async def ensure_tables(mcp: OracleMCP) -> None:
    for stmt in DDL:
        await mcp.run_sql(stmt)


async def save_run(mcp: OracleMCP, *, run_id: int, question: str, mode: str, answer: str, sources: str) -> None:
    await _exec(mcp,
        "INSERT INTO rag_runs (run_id, question, embed_mode, answer, sources) VALUES "
        f"({run_id}, {_q(question)}, {_q(mode)}, {_clob(answer)}, {_clob(sources)})", "insert run")
    await _exec(mcp, "COMMIT", "commit")
