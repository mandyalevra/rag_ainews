import json
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv(override=True)

app = FastAPI()

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


# Serve web/ as static files — must be mounted last
app.mount("/", StaticFiles(directory="web", html=True), name="web")


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=True)
