# Private RAG on Oracle 26ai — embeddings *inside* the database

A retrieval-augmented Q&A where the **documents and the query are embedded inside
Oracle 26ai** using an in-database ONNX model (`VECTOR_EMBEDDING`). Your text never
leaves the database to be embedded — ideal for private or regulated data. The agent
reaches the DB only through the **SQLcl MCP Server**.

```
 question ─> (embed query INSIDE Oracle) ─> AI Vector Search over documents ─> top-k context
                                                                                   │
                                                                                   ▼
                                                              LLM composes the answer from in-DB context
```

## Runs today, goes zero-external when you load the model
This project **auto-detects** the in-DB embedding model:
- **Model loaded** → documents *and* the query are embedded with `VECTOR_EMBEDDING` — **no text leaves Oracle**.
- **No model yet** → it falls back to client-side OpenAI embeddings so the demo still runs.

The embedding column is `VECTOR(*, FLOAT32)`, so it works in either mode (e.g. 384-dim
in-DB vs 1536-dim fallback) with no schema change.

## Make it fully in-database (one-time)
Load Oracle's prebuilt ONNX model, then re-seed — see **`sql/load_model.sql`** for the
exact `DBMS_VECTOR.LOAD_ONNX_MODEL` / `LOAD_ONNX_MODEL_CLOUD` calls. After it loads:
```
python src/seed.py     # now embeds inside Oracle
python src/ask.py       # query embedded inside Oracle too
```
`ask.py`/`seed.py` print which mode they used (`IN-DATABASE` vs `FALLBACK`).

## Setup
```powershell
pip install -r requirements.txt
copy .env.example .env          # set OPENAI_API_KEY (fallback) + ORACLE_MCP_CONNECTION
python src/seed.py              # build + embed the knowledge base
python src/ask.py               # ask QUESTION and get a grounded answer
streamlit run src/dashboard.py  # view answers
```

## Files
| File | Purpose |
| --- | --- |
| `src/embeddings.py` | Detects the in-DB model; builds the `VECTOR_EMBEDDING` expression. |
| `src/seed.py` | Loads a self-referential Oracle 26ai knowledge base; embeds in-DB or via fallback. |
| `src/ask.py` | Retrieves via AI Vector Search (query embedded in-DB when possible) + answers. |
| `sql/load_model.sql` | One-time ONNX model load to enable zero-external mode. |
| `src/dashboard.py` | Streamlit view of answers (shows the embedding mode). |

> Note on "zero external": embeddings + retrieval are fully in-database. The final
> answer wording is produced by your chosen LLM from the in-DB context — swap in an
> in-database generation path (e.g. Select AI) to keep generation in Oracle too.

> ⚠️ A learning demo.
