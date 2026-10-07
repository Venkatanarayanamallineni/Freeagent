import json, os
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from crawler import crawl
from ask import ask
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

def site_id_from(url):
    return urlparse(url).netloc.replace(".", "_")

def load_site(site_id):
    path = f"data/{site_id}.json"
    if not os.path.exists(path):
        raise HTTPException(404, "Site not set up yet")
    with open(path, encoding="utf-8") as f:
        return json.load(f)

class SetupReq(BaseModel):
    url: str

class ChatReq(BaseModel):
    site_id: str
    question: str
    history: list = []

@app.post("/setup")
def setup(req: SetupReq):
    data = crawl(req.url)
    sid = site_id_from(req.url)
    os.makedirs("data", exist_ok=True)
    with open(f"data/{sid}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"site_id": sid, "pages": len(data["pages"]), "logo": data["logo"]}

@app.post("/chat")
def chat(req: ChatReq):
    data = load_site(req.site_id)
    answer = ask(data, req.history[-6:], req.question)
    return {"answer": answer}

@app.get("/site/{site_id}")
def site_info(site_id: str):
    data = load_site(site_id)
    return {"site": data["site"], "logo": data["logo"]}
app.mount("/static", StaticFiles(directory="static"), name="static")