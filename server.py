import colorsys, io, ipaddress, json, os, re, socket, time
from collections import defaultdict, deque
from typing import Optional
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

from ask import ask, business_name
from crawler import crawl

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# ---------- limits (protect Nebius credits) ----------
CHAT_PER_MIN = 15          # per visitor
SETUP_PER_HOUR = 10        # per visitor
CHAT_PER_DAY_TOTAL = 1500  # all visitors combined
MAX_QUESTION_CHARS = 500

HITS = defaultdict(deque)
DAY = {"date": "", "count": 0}


def client_ip(request):
    fwd = request.headers.get("x-forwarded-for")
    return (fwd.split(",")[0] if fwd else request.client.host).strip()


def rate_limit(request, key, limit, window):
    q = HITS[(key, client_ip(request))]
    now = time.time()
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Too many requests. Please wait a minute and try again.")
    q.append(now)


def daily_cap():
    today = time.strftime("%Y-%m-%d")
    if DAY["date"] != today:
        DAY.update(date=today, count=0)
    if DAY["count"] >= CHAT_PER_DAY_TOTAL:
        raise HTTPException(503, "Chat is resting for today. Please try again tomorrow.")
    DAY["count"] += 1


# ---------- helpers ----------
SITE_ID_OK = re.compile(r"[a-z0-9_\-]{1,100}")
HEX_OK = re.compile(r"#[0-9a-fA-F]{6}")


def site_id_from(url):
    return re.sub(r"[^a-z0-9_\-]", "_", urlparse(url).netloc.lower())


def load_site(site_id):
    if not SITE_ID_OK.fullmatch(site_id):
        raise HTTPException(400, "Bad site id")
    for folder in ["data", "demo_data"]:
        path = f"{folder}/{site_id}.json"
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    raise HTTPException(404, "Site not set up yet")


def is_public_url(url):
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return False
        ip = ipaddress.ip_address(socket.gethostbyname(p.hostname))
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)
    except Exception:
        return False


BRAND_CACHE = {}


def logo_colors(url):
    if not url:
        return None
    if url in BRAND_CACHE:
        return BRAND_CACHE[url]
    out = None
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "FreeAgentBot"})
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        img.thumbnail((96, 96))
        allpx = list(img.getdata())
        px = [p for p in allpx if p[3] > 200]  # solid pixels only
        if px:
            see_through = 1 - len(px) / len(allpx)
            light_share = sum(1 for p in px if 0.299*p[0] + 0.587*p[1] + 0.114*p[2] > 200) / len(px)
            light_logo = see_through > 0.1 and light_share > 0.6  # white logo on clear background

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
            if s < 0.15:
                rgb = (31/255, 35/255, 40/255)  # grey/black logo: use near-black
            else:
                rgb = colorsys.hls_to_rgb(h, min(l, 0.32), s)  # dark enough for white text
            out = {"brand": "#%02x%02x%02x" % tuple(int(v*255) for v in rgb),
                   "light_logo": light_logo}
    except Exception as e:
        print("logo color fail", e)
    BRAND_CACHE[url] = out
    return out


# ---------- request shapes ----------
class SetupReq(BaseModel):
    url: str
    logo: Optional[str] = None   # owner's own logo link (optional)
    brand: Optional[str] = None  # owner's color like #1a2b3c (optional)


class ChatReq(BaseModel):
    site_id: str
    question: str
    history: list = []


# ---------- routes ----------
@app.post("/setup")
def setup(req: SetupReq, request: Request):
    rate_limit(request, "setup", SETUP_PER_HOUR, 3600)
    url = req.url.strip()
    if not is_public_url(url):
        raise HTTPException(400, "Please enter a public website link (http or https).")
    data = crawl(url)
    if not data["pages"]:
        raise HTTPException(400, "Couldn't read this site. It may block automated readers.")
    if req.logo:
        if not req.logo.startswith(("http://", "https://")):
            raise HTTPException(400, "Logo must be an image link (http or https).")
        data["logo"] = req.logo.strip()
    if req.brand:
        if not HEX_OK.fullmatch(req.brand.strip()):
            raise HTTPException(400, "Color must look like #1a2b3c.")
        data["brand"] = req.brand.strip()
    sid = site_id_from(url)
    os.makedirs("data", exist_ok=True)
    with open(f"data/{sid}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"site_id": sid, "pages": len(data["pages"]), "logo": data["logo"]}


@app.post("/chat")
def chat(req: ChatReq, request: Request):
    rate_limit(request, "chat", CHAT_PER_MIN, 60)
    q = req.question.strip()
    if not q:
        raise HTTPException(400, "Please type a question.")
    if len(q) > MAX_QUESTION_CHARS:
        raise HTTPException(400, "Question is too long. Please shorten it.")
    data = load_site(req.site_id)
    daily_cap()
    # only allow normal chat turns from the browser (no fake "system" messages)
    history = [{"role": h["role"], "content": h["content"][:2000]}
               for h in req.history[-6:]
               if isinstance(h, dict) and h.get("role") in ("user", "assistant")
               and isinstance(h.get("content"), str)]
    try:
        answer = ask(data, history, q)
    except Exception as e:
        print("model error", e)
        raise HTTPException(502, "The assistant is busy right now. Please try again.")
    return {"answer": answer}


@app.get("/site/{site_id}")
def site_info(site_id: str):
    data = load_site(site_id)
    name = business_name(data)
    name = data.get("name") or (data["pages"][0]["title"] if data["pages"] else "")
    name = re.split(r"\s[|\-–]\s", name)[0][:40].strip()
    if not name or name.lower() in ("home", "welcome", "index", "homepage"):
        name = urlparse(data["site"]).netloc.replace("www.", "")
    colors = logo_colors(data["logo"]) or {}
    return {"site": data["site"], "logo": data["logo"], "name": name,
            "brand": data.get("brand") or colors.get("brand", "#1f2328"),
            "light_logo": colors.get("light_logo", False)}


@app.get("/")
def home():
    return RedirectResponse("/static/setup.html")


app.mount("/static", StaticFiles(directory="static"), name="static")