import json, os, re, sys
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("NEBIUS_API_KEY"),
                base_url=os.getenv("NEBIUS_BASE_URL"))
MODEL = os.getenv("MODEL_ID")
MAX_CHARS_PER_PAGE = 3000

def build_context(data):
    parts = []
    for p in data["pages"]:
        parts.append(f"URL: {p['url']}\nTITLE: {p['title']}\nTEXT: {p['text'][:MAX_CHARS_PER_PAGE]}")
    return "\n\n---\n\n".join(parts)

SYSTEM = """You are the helpful assistant for this business website.
Answer ONLY using the website content below.
If the answer is not in the content, say: "I couldn't find that on this site."
Keep answers short. Use plain text, no markdown. End with the source URL you used, like: Source: <url>

WEBSITE CONTENT:
{context}"""

def ask(data, history, question):
    messages = [{"role": "system", "content": SYSTEM.format(context=build_context(data))}]
    messages += history + [{"role": "user", "content": question}]
    r = client.chat.completions.create(model=MODEL, messages=messages)
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