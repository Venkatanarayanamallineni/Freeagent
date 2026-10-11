import difflib, json, os, re, sys
from urllib.parse import urlparse
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("NEBIUS_API_KEY"),
                base_url=os.getenv("NEBIUS_BASE_URL"))
MODEL = os.getenv("MODEL_ID")
MAX_TOTAL_CHARS = 250000

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
- If they ask for something we clearly don't sell (cars at a cafe, laptops at a clothing store): ONE short, light, playful line that makes clear we don't sell it, then point to something real we DO offer. The joke must not state any fake fact, and may only mention items we really offer. No source.
  Example: "No laptops here, unless you count our pancakes as a flat, round device. Want to see our breakfast menu?"
- If it's info we might have but isn't below (parking, allergies, stock): say you don't have that detail handy and share our phone or email from below if available. No source.

{tone}
Style: plain text. Be brief: 1-3 short lines for simple questions, max 5 lines ever. For lists, start each line with "- ". Give only what was asked.
Put exactly ONE source at the very end, like: Source: <url> using the most specific page. Never put URLs anywhere else.

OUR INFORMATION:
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


def build_context(data):
    pages = sorted(data["pages"], key=lambda p: -p["text"].count("$"))
    parts, total = [], 0
    for p in pages:
        chunk = f"URL: {p['url']}\nTITLE: {p['title']}\nTEXT: {p['text'][:15000]}"
        if total + len(chunk) > MAX_TOTAL_CHARS:
            continue
        parts.append(chunk)
        total += len(chunk)
    acts = data.get("actions") or []
    if acts:
        lines = "\n".join(f"- {a['kind']}: {a['text'] or a['kind']} -> {a['url']}" for a in acts)
        parts.insert(0, "OUR ACTION LINKS (booking, reservations, ordering):\n" + lines)
    return "\n\n---\n\n".join(parts)


def ask(data, history, question):
    system = SYSTEM.format(name=business_name(data),
                           tone=TONES.get(data.get("tone"), TONES["friendly"]),
                           context=build_context(data))
    messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": question}]
    r = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.2)
    answer = r.choices[0].message.content or ""
    return re.sub(r"<think>.*?</think>", "", answer, flags=re.S).strip()


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
        r = client.chat.completions.create(model=MODEL, temperature=0,
                                           messages=[{"role": "user", "content": prompt}])
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
        a = ask(data, history, q)
        print("Bot:", a)
        history += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]