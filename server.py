import colorsys, hashlib, hmac, io, ipaddress, json, os, re, secrets, socket, threading, time, uuid
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

from ask import ask, business_name, detect_style
from crawler import crawl

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# ---------- limits (protect Nebius credits) ----------
CHAT_PER_MIN = 15          # per visitor
SETUP_PER_HOUR = 10        # per visitor
SETTINGS_PER_HOUR = 40     # per visitor
OFFICE_PER_HOUR = 200      # per visitor
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
TONE_OK = ("professional", "friendly", "playful")


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


def tagline(data, name):
    title = data["pages"][0]["title"] if data["pages"] else ""
    skip = {name.lower(), "home", "welcome", "index", "homepage"}
    for part in re.split(r"\s[|\-–]\s", title)[1:]:
        part = part.strip()
        if 3 < len(part) <= 45 and part.lower() not in skip:
            return part
    desc = (data.get("description") or "").strip()
    first = re.split(r"(?<=[.!?])\s", desc)[0] if desc else ""
    if 3 < len(first) <= 60:
        return first
    return "Happy to help"


BRAND_CACHE = {}
STYLE_CACHE = {}


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
    logo: Optional[str] = None    # owner's own logo link
    brand: Optional[str] = None   # owner's color like #1a2b3c
    tone: Optional[str] = "friendly"
    effects: bool = True
    emoji: Optional[str] = None   # owner's own signature
    token: Optional[str] = None   # owner's edit token, to re-read a site they already set up


class SettingsReq(BaseModel):
    token: str
    theme: Optional[str] = None   # chat look: auto / light / dark
    logo: Optional[str] = None
    brand: Optional[str] = None
    tone: Optional[str] = None
    effects: Optional[bool] = None
    emoji: Optional[str] = None


class ChatReq(BaseModel):
    site_id: str
    question: str
    history: list = []


# ---------- routes ----------
JOBS = {}
JOB_ID_OK = re.compile(r"[a-f0-9]{32}")


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def owns(data, token):
    h = data.get("edit_hash")
    return bool(h and token and hmac.compare_digest(h, token_hash(token)))


def read_own_site(sid):
    """Only sites set up through this server (data/), never the read-only demo_data/."""
    path = f"data/{sid}.json"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_site(sid, data):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{sid}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def check_style_fields(logo, brand, emoji, tone):
    if logo and not logo.strip().startswith(("http://", "https://")):
        raise HTTPException(400, "Logo must be an image link (http or https).")
    if brand and not HEX_OK.fullmatch(brand.strip()):
        raise HTTPException(400, "Color must look like #1a2b3c.")
    if emoji and len(emoji.strip()) > 4:
        raise HTTPException(400, "Signature should be one symbol.")
    if tone and tone not in TONE_OK:
        raise HTTPException(400, "Unknown voice.")


def run_setup(job_id, req, url, sid, token):
    job = JOBS[job_id]

    def progress(event, info):
        if event == "page" or event == "pdf":
            job["pages"] = info["count"]
        if event == "pdf" and len(job["pdfs"]) < 3:
            job["pdfs"].append(info["name"])
        if event == "logo":
            job["logo"] = True
        if event == "action":
            job["actions"] += 1
        if event == "blocked":
            job["blocked"] += 1

    try:
        job["stage"] = "reading"
        data = crawl(url, progress)
        if not data["pages"]:
            job.update(status="error", error="We couldn't read this site. It may block automated readers.")
            return
        if req.logo:
            data["logo"] = req.logo.strip()
        if req.brand:
            data["brand"] = req.brand.strip()
        data["tone"] = req.tone if req.tone in TONE_OK else "friendly"
        data["effects"] = req.effects
        job["stage"] = "voice"
        style = detect_style(data)
        data["type"] = style["type"]
        data["effect"] = {"motion": style["motion"], "emoji": (req.emoji or "").strip() or style["emoji"]}
        data["edit_hash"] = token_hash(token)
        data["updated"] = int(time.time())
        save_site(sid, data)
        job.update(status="done", stage="done",
                   result={"site_id": sid, "pages": len(data["pages"]), "logo": data["logo"], "edit_token": token})
    except Exception as e:
        print("setup error", e)
        job.update(status="error", error="Something went wrong while reading the site. Please try again.")


@app.post("/setup")
def setup(req: SetupReq, request: Request):
    url = req.url.strip()
    if not is_public_url(url):
        raise HTTPException(400, "Please enter a public website link (http or https).")
    check_style_fields(req.logo, req.brand, req.emoji, req.tone)
    sid = site_id_from(url)

    # someone already set this site up: only its owner can re-read it
    existing = read_own_site(sid)
    if existing and existing.get("edit_hash") and not owns(existing, req.token):
        return {"existing": True, "site_id": sid, "pages": len(existing["pages"]), "logo": existing.get("logo")}

    rate_limit(request, "setup", SETUP_PER_HOUR, 3600)
    now = time.time()
    for jid in [j for j, v in JOBS.items() if now - v["t"] > 1800]:
        JOBS.pop(jid, None)
    token = req.token if existing and owns(existing, req.token) else secrets.token_urlsafe(24)
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"t": now, "status": "running", "stage": "opening", "pages": 0, "pdfs": [],
                    "logo": False, "actions": 0, "blocked": 0, "result": None, "error": None}
    threading.Thread(target=run_setup, args=(job_id, req, url, sid, token), daemon=True).start()
    return {"job": job_id}


@app.get("/setup/{job_id}")
def setup_status(job_id: str):
    if not JOB_ID_OK.fullmatch(job_id) or job_id not in JOBS:
        raise HTTPException(404, "Setup not found. Please start again.")
    return {k: v for k, v in JOBS[job_id].items() if k != "t"}


@app.post("/settings/{site_id}")
def settings(site_id: str, req: SettingsReq, request: Request):
    rate_limit(request, "settings", SETTINGS_PER_HOUR, 3600)
    if not SITE_ID_OK.fullmatch(site_id):
        raise HTTPException(400, "Bad site id")
    data = read_own_site(site_id)
    if not data or not owns(data, req.token):
        raise HTTPException(403, "Only the person who set up this assistant can change it.")
    check_style_fields(req.logo, req.brand, req.emoji, req.tone)
    if req.logo is not None:
        data["logo"] = req.logo.strip() or data.get("logo")
    if req.brand is not None:
        if req.brand.strip():
            data["brand"] = req.brand.strip()
        else:
            data.pop("brand", None)  # empty = match the logo again
    if req.tone:
        data["tone"] = req.tone
    if req.effects is not None:
        data["effects"] = req.effects
    if req.theme in ("auto", "light", "dark"):
        data["theme"] = req.theme
    if req.emoji:
        data.setdefault("effect", {"motion": "twinkle"})["emoji"] = req.emoji.strip()
    save_site(site_id, data)
    return {"ok": True}


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
    t0 = time.time()
    try:
        res = ask(data, history, q)
    except Exception as e:
        print("model error", e)
        raise HTTPException(502, "The assistant is busy right now. Please try again.")
    ms = int((time.time() - t0) * 1000)
    if res["unanswered"]:
        log_unanswered(req.site_id, q)
    return {"answer": res["answer"], "meta": answer_meta(ms, res["tokens"])}


def model_label():
    m = (os.getenv("MODEL_ID") or "").lower()
    return "NVIDIA Nemotron" if "nemotron" in m else (os.getenv("MODEL_ID") or "model").split("/")[-1]


def answer_meta(ms, tokens):
    meta = {"model": model_label(), "host": "Nebius", "ms": ms, "tokens": tokens["in"] + tokens["out"]}
    try:  # optional: copy real prices (US$ per 1M tokens) from Nebius's pricing page into .env
        pin, pout = float(os.getenv("PRICE_IN_PER_M", "")), float(os.getenv("PRICE_OUT_PER_M", ""))
        meta["cost"] = round((tokens["in"] * pin + tokens["out"] * pout) / 1_000_000, 6)
    except ValueError:
        pass
    return meta


def new_id():
    return uuid.uuid4().hex[:10]


def log_unanswered(sid, q):
    """Keep questions the assistant couldn't answer, so the owner can fill the gap."""
    data = read_own_site(sid)
    if not data:
        return
    inbox = data.setdefault("inbox", [])
    if any(i["q"].strip().lower() == q.strip().lower() for i in inbox):
        return
    inbox.append({"id": new_id(), "q": q[:300], "t": int(time.time())})
    data["inbox"] = inbox[-100:]
    save_site(sid, data)


class OfficeReq(BaseModel):
    token: str
    action: str
    q: Optional[str] = None
    a: Optional[str] = None
    id: Optional[str] = None
    rules: Optional[list] = None


def office_state(data):
    return {"name": business_name(data),
            "inbox": data.get("inbox") or [],
            "corrections": data.get("corrections") or [],
            "rules": data.get("rules") or []}


def clean(text, limit):
    text = " ".join(str(text or "").split())
    if not text:
        raise HTTPException(400, "Please write something first.")
    return text[:limit]


@app.post("/office/{site_id}")
def office(site_id: str, req: OfficeReq, request: Request):
    """Back Office: the owner's own answers, unanswered questions and house rules."""
    rate_limit(request, "office", OFFICE_PER_HOUR, 3600)
    if not SITE_ID_OK.fullmatch(site_id):
        raise HTTPException(400, "Bad site id")
    data = read_own_site(site_id)
    if not data or not owns(data, req.token):
        raise HTTPException(403, "Only the person who set up this assistant can open its Back Office.")
    fixes = data.setdefault("corrections", [])
    inbox = data.setdefault("inbox", [])

    if req.action == "load":
        return office_state(data)
    if req.action in ("add_correction", "answer"):
        if req.action == "answer":
            item = next((i for i in inbox if i["id"] == req.id), None)
            if not item:
                raise HTTPException(404, "That question is gone. Refresh and try again.")
            q = item["q"]
            data["inbox"] = [i for i in inbox if i["id"] != req.id]
        else:
            q = clean(req.q, 300)
            data["inbox"] = [i for i in inbox if i["q"].strip().lower() != q.strip().lower()]  # answered now
        a = clean(req.a, 800)
        fixes = [c for c in fixes if c["q"].strip().lower() != q.strip().lower()]
        fixes.append({"id": new_id(), "q": q, "a": a, "t": int(time.time())})
        data["corrections"] = fixes[-50:]
    elif req.action == "delete_correction":
        data["corrections"] = [c for c in fixes if c["id"] != req.id]
    elif req.action == "dismiss":
        data["inbox"] = [i for i in inbox if i["id"] != req.id]
    elif req.action == "set_rules":
        rules = [" ".join(str(r).split())[:200] for r in (req.rules or []) if str(r).strip()]
        data["rules"] = rules[:15]
    else:
        raise HTTPException(400, "Unknown action.")
    save_site(site_id, data)
    return office_state(data)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/config")
def config():
    """Public settings for our own pages. Set REPO_URL in .env / Render to show the GitHub link."""
    return {"repo": os.getenv("REPO_URL", "").strip()}


@app.get("/site/{site_id}")
def site_info(site_id: str):
    data = load_site(site_id)
    name = business_name(data)

    effect = data.get("effect")
    btype = data.get("type")
    if not effect or not btype:  # older sites set up before effects existed
        if site_id not in STYLE_CACHE:
            STYLE_CACHE[site_id] = detect_style(data)
        st = STYLE_CACHE[site_id]
        effect = effect or {"motion": st["motion"], "emoji": st["emoji"]}
        btype = btype or st["type"]
    if data.get("effects") is False:
        effect = {}

    colors = logo_colors(data["logo"]) or {}
    return {"site": data["site"], "logo": data["logo"], "name": name,
            "tagline": tagline(data, name),
            "effect": effect,
            "theme": data.get("theme", "auto"),
            "type": btype,
            "actions": [{"url": a["url"], "kind": a["kind"]} for a in (data.get("actions") or [])][:8],
            "brand": data.get("brand") or colors.get("brand", "#1f2328"),
            "light_logo": colors.get("light_logo", False)}


@app.get("/")
def home():
    return RedirectResponse("/static/setup.html")


app.mount("/static", StaticFiles(directory="static"), name="static")