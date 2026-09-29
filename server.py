import asyncio
import json
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv(override=True)

_embed_model = None
_embed_lock = threading.Lock()


def get_model():
    global _embed_model
    if _embed_model is None:
        with _embed_lock:
            if _embed_model is None:
                from fastembed import TextEmbedding
                _embed_model = TextEmbedding("BAAI/bge-small-en-v1.5")
    return _embed_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm the model in background so first search is fast
    threading.Thread(target=get_model, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)

SUBSCRIBERS_FILE = Path("subscribers.json")


def load_subscribers() -> list[str]:
    if SUBSCRIBERS_FILE.exists():
        return json.loads(SUBSCRIBERS_FILE.read_text())
    return []


def save_subscribers(subs: list[str]) -> None:
    SUBSCRIBERS_FILE.write_text(json.dumps(subs, indent=2))


class SubscribeRequest(BaseModel):
    email: str


@app.post("/subscribe")
async def subscribe(req: SubscribeRequest):
    email = req.email.lower().strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email")
    subs = load_subscribers()
    if email in subs:
        return {"status": "already_subscribed"}
    subs.append(email)
    save_subscribers(subs)
    return {"status": "subscribed"}


@app.get("/subscribers")
async def get_subscribers():
    return {"subscribers": load_subscribers(), "count": len(load_subscribers())}


@app.post("/api/admin/rebuild-embeddings")
async def rebuild_embeddings_endpoint(secret: str = ""):
    """One-off maintenance hook: rebuilds the embeddings index using this
    process's already-loaded model, instead of spawning a separate process
    that would load a second copy and risk OOM on a memory-constrained box."""
    expected = os.environ.get("ADMIN_SECRET", "")
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="forbidden")
    from main import build_embeddings_index
    model = get_model()
    await asyncio.get_event_loop().run_in_executor(None, build_embeddings_index, model)
    return {"status": "done"}


_index_lock = threading.Lock()
_index_cache = {"mtime": None, "meta": None, "matrix": None, "norms": None}


def get_index():
    """Load + cache the embeddings index in memory, rebuilding only when
    web/embeddings.json changes on disk (once/day, via the digest pipeline).
    Avoids re-reading and re-parsing an ~18MB JSON file on every keystroke."""
    emb_path = Path("web/embeddings.json")
    if not emb_path.exists():
        return None

    mtime = emb_path.stat().st_mtime
    if _index_cache["mtime"] == mtime:
        return _index_cache

    with _index_lock:
        if _index_cache["mtime"] == mtime:
            return _index_cache
        stories = json.loads(emb_path.read_text())
        matrix = np.array([s["embedding"] for s in stories], dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1)
        meta = [{k: v for k, v in s.items() if k != "embedding"} for s in stories]
        _index_cache.update(mtime=mtime, meta=meta, matrix=matrix, norms=norms)
        return _index_cache


@app.get("/api/search")
async def semantic_search(q: str, n: int = 15):
    index = get_index()
    if index is None:
        return {"results": [], "query": q, "error": "embeddings index not built yet"}

    meta, matrix, norms = index["meta"], index["matrix"], index["norms"]
    model = get_model()

    query_vec = np.array(list(model.embed([q]))[0], dtype=np.float32)
    query_norm = np.linalg.norm(query_vec)
    q_lower = q.lower()

    # Vectorized cosine similarity against every story in one matrix op,
    # instead of a per-story Python loop.
    scores = (matrix @ query_vec) / (norms * query_norm)

    results = []
    for s, score in zip(meta, scores):
        score = float(score)
        # Boost exact matches so they always surface above pure semantic results
        title_lower = s.get("title", "").lower()
        summary_lower = s.get("summary", "").lower()
        if q_lower in title_lower:
            score += 0.25
        elif q_lower in summary_lower:
            score += 0.12

        if score > 0.35:
            out = dict(s)
            out["score"] = round(min(score, 1.0), 4)
            results.append(out)

    results.sort(key=lambda x: x["score"], reverse=True)
    return {"results": results[:n], "query": q}


@app.get("/data.js")
async def serve_data_js():
    path = Path("web/data.js")
    if not path.exists():
        raise HTTPException(status_code=404)
    content = path.read_text()
    return Response(
        content=content,
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


# Serve web/ as static files — must be mounted last
app.mount("/", StaticFiles(directory="web", html=True), name="web")


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    reload = os.environ.get("RAILWAY_ENVIRONMENT") is None  # no reload in production
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=reload)
