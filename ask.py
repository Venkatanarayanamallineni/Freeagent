import json, os, re, sys
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("NEBIUS_API_KEY"),
                base_url=os.getenv("NEBIUS_BASE_URL"))
MODEL = os.getenv("MODEL_ID")


MAX_TOTAL_CHARS = 250000

def build_context(data):
    pages = sorted(data["pages"], key=lambda p: -p["text"].count("$"))
    parts, total = [], 0
    for p in pages:
        chunk = f"URL: {p['url']}\nTITLE: {p['title']}\nTEXT: {p['text'][:15000]}"
        if total + len(chunk) > MAX_TOTAL_CHARS:
            continue
        parts.append(chunk)
        total += len(chunk)
    return "\n\n---\n\n".join(parts)



SYSTEM = """You are a friendly, smart employee of this business, honest sales, chatting with a customer on its website.

TRUTH RULES (most important):
- Use ONLY the website content below. Never invent items, prices, hours, reviews, or any fact.
- Only call something "popular", "best seller" or "top" if the website says so.
- If unsure, say you're not sure. Never guess.

How to answer:
- Specific question (price, hours, contact): answer directly, name the exact item.
- Broad question ("what do you have", "dinner", "books"): list up to 4 main categories with price range only, no examples. Then ask which one they want to know more about.
- Suggestion or a meal: suggest a small combo that fits the business (e.g. starter + main + drink, 2-3 similar books, one outfit item), with prices.
- Budget words (cheap, under $X): give the cheapest matching options and the price range.
- Vague question: short helpful answer, then ONE short follow-up question.

When something is missing:
- If they ask for something this business clearly doesn't sell (cars at a cafe, laptops at a clothing store): reply with ONE short, light, playful line that makes clear they don't sell it, then point to a real related thing they DO offer. The joke must not state any fake fact. No source.
  Example: "No laptops here, unless you count our pancakes as a flat, round device. Want to see the breakfast menu?"
- If it's info that may exist but isn't on the site (parking, allergies, stock): say it's not on the site and give the contact info from the site if available. No source.

Style: plain text. Be brief: 1-3 short lines for simple questions, max 5 lines ever. For lists, start each line with "- ". Give only what was asked.
Put exactly ONE source at the very end, like: Source: <url> using the most specific page. Never put URLs anywhere else.


WEBSITE CONTENT:
{context}"""

def ask(data, history, question):
    messages = [{"role": "system", "content": SYSTEM.format(context=build_context(data))}]
    messages += history + [{"role": "user", "content": question}]
    r = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.2)
    answer = r.choices[0].message.content or ""
    return re.sub(r"<think>.*?</think>", "", answer, flags=re.S).strip()

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