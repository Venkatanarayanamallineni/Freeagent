import json, os, re
import io, colorsys, requests
from PIL import Image
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from crawler import crawl
from ask import ask
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

def site_id_from(url):
    return urlparse(url).netloc.replace(".", "_")

def load_site(site_id):
    for folder in ["data", "demo_data"]:
        path = f"{folder}/{site_id}.json"
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    raise HTTPException(404, "Site not set up yet")

class SetupReq(BaseModel):
    url: str

class ChatReq(BaseModel):
    site_id: str
    question: str
    history: list = []

@app.post("/setup")
def setup(req: SetupReq):
    data = crawl(req.url)
    if not data["pages"]:
        raise HTTPException(400, "Couldn't read this site. It may block automated readers.")
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


BRAND_CACHE = {}

def logo_colors(url):
    if not url:
        return None
    if url in BRAND_CACHE:
        return BRAND_CACHE[url]
    out = None
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "FreeAgentBot"})
        img = Image.open(io.BytesIO(r.content)).convert("RGBA").resize((48, 48))
        px = [p for p in img.getdata() if p[3] > 40]
        if px:
            bright = sum(0.299*p[0] + 0.587*p[1] + 0.114*p[2] for p in px) / len(px)
            counts = {}
            for p in px:
                k = (p[0]//32, p[1]//32, p[2]//32)
                counts[k] = counts.get(k, 0) + 1
            best, score = (31, 35, 40), -1
            for k, c in counts.items():
                rgb = tuple(v*32 + 16 for v in k)
                h, l, s = colorsys.rgb_to_hls(*[v/255 for v in rgb])
                sc = c * (s + 0.05) * (1 if 0.15 < l < 0.85 else 0.2)
                if sc > score:
                    best, score = rgb, sc
            h, l, s = colorsys.rgb_to_hls(*[v/255 for v in best])
            rgb = colorsys.hls_to_rgb(h, min(l, 0.42), s)  # dark enough for white text
            out = {"brand": "#%02x%02x%02x" % tuple(int(v*255) for v in rgb),
                   "light_logo": bright > 200}
    except Exception as e:
        print("logo color fail", e)
    BRAND_CACHE[url] = out
    return out


@app.get("/site/{site_id}")
def site_info(site_id: str):
    data = load_site(site_id)
    name = data.get("name") or (data["pages"][0]["title"] if data["pages"] else "")
    name = re.split(r"\s[|\-–]\s", name)[0][:40].strip()
    if not name or name.lower() in ("home", "welcome", "index", "homepage"):
        name = urlparse(data["site"]).netloc.replace("www.", "")
    colors = logo_colors(data["logo"]) or {}
    return {"site": data["site"], "logo": data["logo"], "name": name,
            "brand": colors.get("brand", "#1f2328"),
            "light_logo": colors.get("light_logo", False)}

@app.get("/")
def home():
    return RedirectResponse("/static/setup.html")

app.mount("/static", StaticFiles(directory="static"), name="static")