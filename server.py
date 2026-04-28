import json
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


@app.get("/api/search")
async def semantic_search(q: str, n: int = 15):
    emb_path = Path("web/embeddings.json")
    if not emb_path.exists():
        return {"results": [], "query": q, "error": "embeddings index not built yet"}

    stories = json.loads(emb_path.read_text())
    model = get_model()

    query_vec = np.array(list(model.embed([q]))[0])
    query_norm = np.linalg.norm(query_vec)
    q_lower = q.lower()

    results = []
    for s in stories:
        vec = np.array(s["embedding"])
        score = float(np.dot(query_vec, vec) / (query_norm * np.linalg.norm(vec)))

        # Boost exact matches so they always surface above pure semantic results
        title_lower = s.get("title", "").lower()
        summary_lower = s.get("summary", "").lower()
        if q_lower in title_lower:
            score += 0.25
        elif q_lower in summary_lower:
            score += 0.12

        if score > 0.35:
            out = {k: v for k, v in s.items() if k != "embedding"}
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
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=True)
