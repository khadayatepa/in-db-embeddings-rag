"""
Embedding mode helpers.

The whole point of this project: when an in-database ONNX model is loaded, the
documents AND the query are embedded *inside Oracle* with VECTOR_EMBEDDING — no text
ever leaves the database. If no model is loaded yet, we fall back to client-side
OpenAI embeddings so the demo still runs (and the README shows how to flip to in-DB).
"""
from __future__ import annotations

import config
from mcp_oracle import OracleMCP


def sql_str(text: str) -> str:
    """Quote a literal for inlining into SQL (escape quotes + '&')."""
    t = (text or "").replace("'", "''")
    if "&" in t:
        t = t.replace("&", "'||CHR(38)||'")
    return "'" + t + "'"


def vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


async def indb_model_available(mcp: OracleMCP) -> bool:
    """True if the configured ONNX embedding model is loaded in the database."""
    out = await mcp.run_sql(
        "SELECT COUNT(*) FROM user_mining_models "
        f"WHERE model_name = UPPER('{config.INDB_MODEL}') AND mining_function = 'EMBEDDING'"
    )
    return any(line.strip() == "1" for line in out.splitlines())


def indb_embed_expr(text_literal_sql: str) -> str:
    """SQL expression that embeds the given (already-quoted) text inside the DB."""
    return f"VECTOR_EMBEDDING({config.INDB_MODEL} USING {text_literal_sql} AS data)"
