import difflib, json, os, re, sys
from urllib.parse import urlparse
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("NEBIUS_API_KEY"),
                base_url=os.getenv("NEBIUS_BASE_URL"))
MODEL = os.getenv("MODEL_ID")
MAX_TOTAL_CHARS = 250000   # "full": the whole site, up to this much
SMART_CHARS = 40000        # "smart": only the pages that match the question, up to this much
THINKING = os.getenv("THINKING", "on").lower() != "off"   # reasoning costs a few tokens but keeps answers truthful (eval: 38/40 on vs 35/40 off)
_no_think_ok = True
STOP = set("a an the and or of to in on for with at by from is are was were be do does did can could would should i you we our your my me it this that what which who when where how much many any some there have has get".split())

# Owner picks one at setup. Changes how much humor the bot uses.
TONES = {
    "professional": "TONE (overrides humor rules above): polite and professional. No jokes. If we don't sell something, say so politely and point to what we offer.",
    "friendly": "TONE: warm and friendly. Light humor only when it fits.",
    "playful": "TONE: playful and fun. A witty line is welcome when it fits, but facts stay exact.",
}

SYSTEM = """You work at {name} and you're chatting with a customer on our website.
Talk like a friendly team member: use "we", "our", "us". Never say "the website", "this site", "the page" or "the content", and never mention that you are reading anything.

TRUTH RULES (most important):
- Use ONLY our information below. Never invent items, prices, hours, reviews, or any fact.
- Only call something "popular", "best seller" or "top" if our information says so.
- If unsure, say you're not sure. Never guess.

How to answer:
- Specific question (price, hours, contact): answer directly, name the exact item.
- Broad question ("what do you have", "dinner", "books"): list up to 4 main categories with price range only, no examples. Then ask which one they want to know more about.
- Suggestion or a meal: suggest a small combo that fits us (e.g. starter + main + drink, 2-3 similar books, one outfit item), with prices.
- Budget words (cheap, under $X): give our cheapest matching options and the price range.
- Vague question: short helpful answer, then ONE short follow-up question.
- They want to book, reserve, schedule or order: one short line, then on its own line write "Action: <url>" using the best match from OUR ACTION LINKS. If there is no fitting link, share our phone number instead. Never invent a link.

When something is missing:
- If they ask for something that has nothing to do with our kind of business (cars at a cafe, laptops at a clothing store, haircuts at a bookstore): ONE short, light, playful line that makes clear we don't sell it, then point to something real we DO offer. The joke must not state any fake fact, and may only mention items we really offer. No source.
  Example: "No laptops here, unless you count our pancakes as a flat, round device. Want to see our breakfast menu?"
- If it's something a business like ours could plausibly have or offer (an amenity, service, policy, item, event, payment method, parking, games, music, allergies, stock) but it isn't below: NEVER say we don't have it. Say you don't have that detail handy and share our phone or email from below if available. No source. Then add the tag [[NO_ANSWER]] at the very end.
- Not sure which of the two it is? Treat it as missing info, never as something we don't have.
- Only use [[NO_ANSWER]] when the detail is missing. Never use it for normal answers or for things we clearly don't sell.

{tone}
Style: plain text. Answer first, in 1-2 short sentences. Stop once the question is answered: no filler, no small talk, no extra suggestions unless they asked for ideas. Max 5 lines ever. For lists, start each line with "- ". Use commas, not dashes.
Put exactly ONE source at the very end, like: Source: <url> using the most specific page. Never put URLs anywhere else.

{owner}OUR INFORMATION:
{context}"""


JUNK_NAMES = {"", "null", "undefined", "none", "home", "welcome", "index", "homepage"}


def _letters(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def business_name(data):
    # candidates: the site's own name tag, then each part of the homepage title
    domain = urlparse(data["site"]).netloc.replace("www.", "")
    stem = _letters(domain.split(".")[0])
    title = data["pages"][0]["title"] if data["pages"] else ""
    cands = [str(data.get("name") or "")] + re.split(r"\s[|\-–]\s", title)
    cands = [c.strip()[:40] for c in cands]
    cands = [c for c in cands if c.lower() not in JUNK_NAMES and not c.startswith("http")]
    if not cands:
        return domain
    # pick the one that looks most like the domain (cafebeaudelaire.com -> "Cafe Beaudelaire")
    score = lambda c: difflib.SequenceMatcher(None, _letters(c), stem).ratio()
    best = max(cands, key=score)
    return best if score(best) >= 0.5 else cands[0]


def words(t):
    return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) > 2 and w not in STOP}


def pick_pages(data, question, history):
    """Smart mode: the homepage plus the pages that share the most words with the question."""
    q = words(question + " " + " ".join(h["content"] for h in (history or [])[-2:] if h.get("role") == "user"))
    def score(p):
        head = words(p["title"] + " " + p["url"].replace("/", " ").replace("-", " "))
        body = words(p["text"][:20000])
        return 3 * len(q & head) + len(q & body)
    pages = data["pages"]
    ranked = sorted(pages[1:], key=lambda p: (-score(p), -p["text"].count("$")))
    return pages[:1] + ranked


def build_context(data, question="", history=None):
    total_site = sum(len(p["text"]) for p in data["pages"])
    smart = data.get("depth") == "smart" and total_site > SMART_CHARS
    limit = SMART_CHARS if smart else MAX_TOTAL_CHARS
    pages = pick_pages(data, question, history) if smart else sorted(data["pages"], key=lambda p: -p["text"].count("$"))
    parts, total, seen = [], 0, set()
    for p in pages:
        key = p["text"][:3000]
        if key in seen:          # same page reached by two links ("/" and "/index"): send it once
            continue
        seen.add(key)
        chunk = f"URL: {p['url']}\nTITLE: {p['title']}\nTEXT: {p['text'][:15000]}"
        if total + len(chunk) > limit:
            continue
        parts.append(chunk)
        total += len(chunk)
    acts = data.get("actions") or []
    if acts:
        lines = "\n".join(f"- {a['kind']}: {a['text'] or a['kind']} -> {a['url']}" for a in acts)
        parts.insert(0, "OUR ACTION LINKS (booking, reservations, ordering):\n" + lines)
    return "\n\n---\n\n".join(parts)


def owner_block(data):
    """The owner's own answers and house rules from Back Office. These outrank the website."""
    parts = []
    fixes = data.get("corrections") or []
    if fixes:
        lines = "\n".join(f"Q: {c['q']}\nA: {c['a']}" for c in fixes[-50:])
        parts.append("OUR OWN ANSWERS (written by the owner; most trusted. Use them for the same or similar questions, "
                     "and follow them if they disagree with the website):\n" + lines)
    rules = data.get("rules") or []
    if rules:
        parts.append("HOUSE RULES FROM THE OWNER (always follow, but never invent facts):\n" + "\n".join(f"- {r}" for r in rules[:15]))
    return "\n\n".join(parts) + "\n\n" if parts else ""


def complete(messages, **kw):
    """Chat call with Nemotron's reasoning switched off (fewer output tokens, faster).
    If the server doesn't accept that switch, fall back to a normal call and stop trying."""
    global _no_think_ok
    if not THINKING and _no_think_ok:
        try:
            return client.chat.completions.create(model=MODEL, messages=messages,
                                                  extra_body={"chat_template_kwargs": {"enable_thinking": False}}, **kw)
        except Exception as e:
            print("reasoning switch not accepted, using normal calls:", e)
            _no_think_ok = False
    return client.chat.completions.create(model=MODEL, messages=messages, **kw)


def ask(data, history, question):
    """Returns {"answer", "unanswered", "tokens"}."""
    system = SYSTEM.format(name=business_name(data),
                           tone=TONES.get(data.get("tone"), TONES["friendly"]),
                           owner=owner_block(data),
                           context=build_context(data, question, history))
    messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": question}]
    r = complete(messages, temperature=0.2, max_tokens=1500 if THINKING else 350)  # room for reasoning; still caps runaway output
    answer = re.sub(r"<think>.*?</think>", "", r.choices[0].message.content or "", flags=re.S).strip()
    # plain hyphens and spaces, so phone numbers and prices copy cleanly
    answer = answer.replace("\u2011", "-").replace("\u2010", "-").replace("\u00a0", " ").replace("\u202f", " ")
    unanswered = "[[NO_ANSWER]]" in answer
    answer = answer.replace("[[NO_ANSWER]]", "").strip()
    usage = getattr(r, "usage", None)
    tokens = {"in": getattr(usage, "prompt_tokens", 0) or 0, "out": getattr(usage, "completion_tokens", 0) or 0}
    return {"answer": answer, "unanswered": unanswered, "tokens": tokens}


TYPES = ["food", "drinks", "beauty", "fashion", "books", "education", "other"]
MOTIONS = ["steam", "rise", "fall", "twinkle"]


def detect_style(data):
    """Ask Nemotron once: what kind of business, which emoji, which motion for the bubble effect."""
    sample = " ".join(p["text"][:1500] for p in data["pages"][:3])
    prompt = ('Look at this business and reply with JSON only, like {"type":"food","emoji":"🍕","motion":"steam"}.\n'
              "type: one of " + ", ".join(TYPES) + ".\n"
              "emoji: ONE emoji showing what they mainly sell (pizza 🍕, coffee ☕, bakery 🥐, ice cream 🍦, "
              "books 📚, flowers 🌸, nails 💅, clothing 👗).\n"
              "motion: steam (hot food or coffee), rise (drinks, bubbles), fall (flowers, leaves, pages), "
              "twinkle (beauty, jewelry, fashion, anything else).\n\n" + sample)
    try:
        r = complete([{"role": "user", "content": prompt}], temperature=0, max_tokens=200)
        out = re.sub(r"<think>.*?</think>", "", r.choices[0].message.content or "", flags=re.S)
        j = json.loads(re.search(r"\{.*?\}", out, re.S).group(0))
        return {"type": j.get("type") if j.get("type") in TYPES else "other",
                "emoji": str(j.get("emoji", "")).strip()[:4] or "✦",
                "motion": j.get("motion") if j.get("motion") in MOTIONS else "twinkle"}
    except Exception as e:
        print("style detect fail", e)
        return {"type": "other", "emoji": "✦", "motion": "twinkle"}


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    history = []
    print("Ask about the site (type 'quit' to stop)")
    while True:
        q = input("\nYou: ")
        if q.lower() == "quit":
            break
        a = ask(data, history, q)["answer"]
        print("Bot:", a)
        history += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]