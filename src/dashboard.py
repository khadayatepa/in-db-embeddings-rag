"""Streamlit dashboard for the private RAG demo (reads Oracle via SQLcl MCP).
Run:  streamlit run src/dashboard.py"""
from __future__ import annotations

import asyncio
import concurrent.futures
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st

import config
import dashboard_data as dd
from mcp_oracle import open_oracle_mcp


def _load_all_sync() -> list[dict]:
    async def _go() -> list[dict]:
        async with open_oracle_mcp(config.SQLCL_COMMAND, config.ORACLE_MCP_CONNECTION) as mcp:
            return [d for r in await dd.list_runs(mcp) if (d := await dd.get_run(mcp, r["run_id"]))]
    with concurrent.futures.ThreadPoolExecutor(1) as ex:
        return ex.submit(lambda: asyncio.run(_go())).result()


@st.cache_data(show_spinner="Loading answers from Oracle 26ai via SQLcl MCP…")
def load_all(nonce: int) -> list[dict]:
    return _load_all_sync()


def main() -> None:
    st.set_page_config(page_title="Private RAG · Oracle 26ai", page_icon="🔒", layout="wide")
    st.title("🔒 Private RAG on Oracle 26ai")
    st.caption("Embeddings & retrieval inside the database (in-DB ONNX model) · via the SQLcl MCP server")

    with st.sidebar:
        st.header("Controls")
        nonce = st.session_state.setdefault("nonce", 0)
        if st.button("🔄 Refresh from database"):
            st.session_state["nonce"] = nonce + 1
            st.cache_data.clear()
            st.rerun()

    runs = load_all(st.session_state["nonce"])
    if not runs:
        st.warning("No answers yet. Run `python src/ask.py` first.")
        return

    with st.sidebar:
        opts = {f"#{r['run_id']} · {r['mode']} · {r.get('created_at','')}": r for r in runs}
        run = opts[st.selectbox("Answer", list(opts.keys()))]

    badge = "#9a3412" if run.get("mode") == "IN_DB" else "#6b7280"
    label = "IN-DATABASE EMBEDDINGS" if run.get("mode") == "IN_DB" else "FALLBACK (OpenAI)"
    st.markdown(f"**Mode:** <span style='background:{badge};color:#fff;padding:2px 12px;border-radius:14px;'>{label}</span>",
                unsafe_allow_html=True)
    st.markdown(f"### {run['question']}")
    st.subheader("Answer")
    st.markdown(run.get("answer") or "—")
    with st.expander("Retrieved context (AI Vector Search)"):
        st.code(run.get("sources") or "—")


if __name__ == "__main__":
    main()
else:
    main()
