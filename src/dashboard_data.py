"""Read RAG runs back out of Oracle through the SQLcl MCP server (as JSON)."""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from mcp_oracle import OracleMCP

RUNS_SQL = """
SELECT JSON_ARRAYAGG(
         JSON_OBJECT('run_id' VALUE run_id, 'question' VALUE question, 'mode' VALUE embed_mode,
                     'created_at' VALUE TO_CHAR(created_at,'YYYY-MM-DD HH24:MI') RETURNING CLOB)
         ORDER BY created_at DESC RETURNING CLOB) AS data
FROM rag_runs
""".strip()


def _detail_sql(run_id: int) -> str:
    return f"""
SELECT JSON_OBJECT('run_id' VALUE run_id, 'question' VALUE question, 'mode' VALUE embed_mode,
                   'created_at' VALUE TO_CHAR(created_at,'YYYY-MM-DD HH24:MI'),
                   'answer' VALUE answer, 'sources' VALUE sources RETURNING CLOB) AS data
FROM rag_runs WHERE run_id = {int(run_id)}
""".strip()


def _extract(out: str) -> Any:
    for row in list(csv.reader(io.StringIO(out)))[1:]:
        for cell in row:
            cell = cell.strip()
            if cell and cell[0] in "[{":
                return json.loads(cell)
    return None


async def list_runs(mcp: OracleMCP) -> list[dict]:
    return _extract(await mcp.run_sql(RUNS_SQL)) or []


async def get_run(mcp: OracleMCP, run_id: int) -> dict | None:
    return _extract(await mcp.run_sql(_detail_sql(run_id)))
