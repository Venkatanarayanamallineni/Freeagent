import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("NEBIUS_API_KEY"),
                base_url=os.getenv("NEBIUS_BASE_URL"))

r = client.chat.completions.create(
    model=os.getenv("MODEL_ID"),
    messages=[{"role": "user", "content": "Say hi in 5 words."}],
)
print(r.choices[0].message.content)