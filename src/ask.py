"""
Private RAG: retrieve from the knowledge base and answer a question.

Retrieval is done with AI Vector Search. When the in-DB ONNX model is loaded, the
QUERY is embedded inside Oracle too (VECTOR_EMBEDDING) — so no document or query text
ever leaves the database. The final wording is composed by your LLM from the
in-database context. Run:  python src/ask.py
"""
from __future__ import annotations

import asyncio
import sys
import textwrap

from openai import AsyncOpenAI

import config
import persist
from embeddings import indb_model_available, indb_embed_expr, sql_str, vector_literal
from mcp_oracle import open_oracle_mcp, OracleMCP

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass


def _wrap(t: str) -> str:
    return "\n".join(textwrap.fill(p, 92, initial_indent="   ", subsequent_indent="   ") if p.strip() else "" for p in t.splitlines())


async def retrieve(mcp: OracleMCP, client: AsyncOpenAI, question: str, indb: bool, k: int = 3) -> str:
    if indb:
        qexpr = indb_embed_expr(sql_str(question))   # embed the query INSIDE Oracle
    else:
        vec = (await client.embeddings.create(model=config.EMBED_MODEL, input=question)).data[0].embedding
        qexpr = f"TO_VECTOR('{vector_literal(vec)}')"
    sql = (
        "SELECT title, "
        f"ROUND(VECTOR_DISTANCE(embedding, {qexpr}, COSINE), 4) AS distance, content "
        "FROM documents "
        f"ORDER BY VECTOR_DISTANCE(embedding, {qexpr}, COSINE) "
        f"FETCH APPROX FIRST {k} ROWS ONLY"
    )
    return await mcp.run_sql(sql)


async def main() -> None:
    q = config.QUESTION
    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY or None)
    print(f"\n=== Private RAG on Oracle 26ai ===\nQ: {q}\n")

    async with open_oracle_mcp(config.SQLCL_COMMAND, config.ORACLE_MCP_CONNECTION) as mcp:
        indb = await indb_model_available(mcp)
        mode = "IN-DATABASE (query embedded inside Oracle)" if indb else "FALLBACK (OpenAI client-side embedding)"
        print(f"Embedding mode: {mode}\n")

        context = await retrieve(mcp, client, q, indb)
        print("Retrieved context (top matches):\n" + _wrap(context[:700]) + "\n")

        resp = await client.chat.completions.create(
            model=config.OPENAI_MODEL, temperature=0.2,
            messages=[
                {"role": "system", "content": "Answer the user's question using ONLY the provided context "
                 "from the knowledge base. Be concise and cite the document title(s) you used. If the "
                 "context doesn't cover it, say so."},
                {"role": "user", "content": f"Question: {q}\n\nContext:\n{context}"},
            ],
        )
        answer = resp.choices[0].message.content or ""
        print("Answer:\n" + _wrap(answer) + "\n")

        await persist.ensure_tables(mcp)
        import time
        await persist.save_run(mcp, run_id=int(time.time()), question=q,
                               mode=("IN_DB" if indb else "FALLBACK"),
                               answer=answer, sources=context)
        print("💾 Saved to rag_runs (view: v_rag_feed).")


if __name__ == "__main__":
    asyncio.run(main())
