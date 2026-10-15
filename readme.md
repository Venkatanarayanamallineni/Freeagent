# say2

<img src="static/brand/say2_wordmark.svg" alt="say2" width="220">

*Said "setu", the Sanskrit word for bridge: the bridge between a small business and every customer.*

**Your website, now taking questions.**

say2 gives any small business website a front desk. Paste your link, and it reads every page and every PDF on your site: menus, price lists, schedules, the fine print. Then it adds a small chat bubble to your site that answers customers in your voice, any time of day, with a link to where each answer came from.

**[Try it live →](https://say2.onrender.com)** &nbsp;·&nbsp; Demo video: _add link_

---

## Every era gave small business one tool

- **1879, the cash register.** Owners stopped losing money.
- **1974, the barcode scanner.** Owners stopped losing time.
- **Today, the front desk.** Owners stop losing the customer who asked a question at 11 pm and never got an answer.

Big chains have call centers. The corner café has nobody. say2 is that front desk.

## How to use it

1. **Paste your website link** on the say2 page and click **Hire my assistant**. No account needed.
2. **Watch it read your site.** A receipt prints what it finds: pages, PDF menus, your logo, booking links. Most sites take about a minute.
3. **Add it to your site.** You get one line of code, with step-by-step help for Wix, Squarespace, WordPress, Shopify and Webflow. Not technical? Use **Send to developer** and forward the ready-made message.
4. **Make it yours.** Under **Preview & style**, pick its voice (Polished, Warm or Witty), color, light or dark look, and logo.
5. **Teach it.** Open **Back office** any time to fix answers and fill in gaps.

## What your customers get

- **Real answers from your site:** prices, hours, menus, services, contact details.
- **A source with every answer,** so they can check it themselves.
- **Honesty:** if your site doesn't say, it tells them so and shares your phone or email. It doesn't guess.
- **Book or order in one tap:** if your site links to booking or ordering (OpenTable, Toast, Calendly, Vagaro and more), a button takes them straight there.
- **Voice:** they can ask out loud and hear the answer read back.
- **Your look:** your logo, your color and a small touch that fits what you sell.
- **Chains welcome:** if prices or hours differ by location, it asks which one they mean.

## What you control: Back office

- **Fix this answer:** see a reply you don't like? Rewrite it once, and the assistant answers that way from then on.
- **Questions we couldn't answer:** anything your site doesn't cover lands in an inbox. Answer it in one line, and it's learned.
- **House rules:** plain words like "Always mention our Tuesday special" or "For allergy questions, ask them to call us."

Your answers always come before the website. Only you can open your Back office: it's tied to the browser you used for setup.

## Good to know

- **AI can still be wrong,** and websites go out of date. Every chat window reminds customers to confirm allergies and anything important with you.
- **What we store:** your site's public text, your style settings, and your Back office answers and rules. We don't save chat conversations, only the text of questions the assistant couldn't answer, so you can answer them. See the [privacy page](https://say2.onrender.com/static/privacy.html).
- **Sites it can't read yet:** sites that block automated readers, sites that build their pages entirely with JavaScript, and menus that are photos inside a PDF.
- **Fair use:** set it up only for sites you own or have permission to use.

## How it works

```
Your link ─► read every page and PDF ─► rank (pages with prices first) ─► NVIDIA Nemotron ─► sourced answer
```

There's no vector database and no training step. A small business site fits inside NVIDIA Nemotron's long memory, so every answer is written with the whole site in view. Your Back office answers and house rules go in first, and questions it can't answer go to your inbox.

---

## For the judges

**NVIDIA x Nebius Global AI Hackathon · Track: Best Apps and Agents**

**How NVIDIA and Nebius are used**
- **Model:** NVIDIA **Nemotron 3 Super (120B)**, an open model, served through **Nebius Token Factory** with its OpenAI-compatible API.
- **Every customer answer** is written by Nemotron, reading up to about 250,000 characters of the site per answer.
- **At setup,** Nemotron also works out what kind of business it is and picks the chat bubble's signature icon and motion.
- **Visible on our own pages:** each answer shows the model, time and tokens used, for example `NVIDIA Nemotron on Nebius · 2.7s · 28,145 tokens · $0.0038` (measured on a large university site).
- **Why Super:** we started with Nemotron 3 Nano (30B) and switched after testing, because Super followed the "never invent facts" and "name the exact item" rules much more reliably.

**Built during the hackathon:** everything here was built during the submission period, starting October 7, 2026.

**Feedback on NVIDIA and Nebius tools:** _fill in before submitting: what worked well, what was confusing, what you'd want next._

## Roadmap

- **Auto re-read** on a schedule, so prices and hours stay current.
- **Domain verification,** so only real owners can set up a site.
- **Insights:** the questions customers ask most, and what your site is missing.
- **Lead capture** for callbacks.
- **Native Shopify and Wix apps,** so owners never touch code.
- **Free self-hosted mode:** run the same Nemotron model on your own machine with Ollama, no API key.

---

## Run it yourself (for developers)

<details>
<summary>Setup, configuration and deployment</summary>

### Requirements
- Python 3.10 or newer
- A Nebius Token Factory API key

### Install

```bash
git clone https://github.com/Venkatanarayanamallineni/Say2.git
cd Say2
python -m venv venv

# Windows
venv\Scripts\activate
# Mac / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Configure
Copy `.env.example` to `.env` and fill it in. In Token Factory, open the Nemotron model, click **View code**, choose **Python**, and copy the `base_url` and `model` values.

| Setting | What it is |
|---|---|
| `NEBIUS_API_KEY` | Your Token Factory key |
| `NEBIUS_BASE_URL` | The `base_url` from Token Factory |
| `MODEL_ID` | The Nemotron model name from Token Factory |
| `PRICE_IN_PER_M`, `PRICE_OUT_PER_M` | Optional: model prices per 1M tokens, to show cost per answer |
| `REPO_URL` | Optional: GitHub link shown on the landing page |

### Run

```bash
uvicorn server:app --reload
```

Open http://127.0.0.1:8000.

Command-line tools (optional):

```bash
python crawler.py https://example.com     # read a site into data/
python ask.py data/example_com.json       # chat with it in the terminal
python eval.py data/example_com.json evals/questions.csv   # accuracy test, writes eval_report.md
```

### Deploy on Render
1. New **Web Service** from this repo.
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
4. Add the settings from `.env` as environment variables.

Render's free tier sleeps after 15 minutes without visitors, and its disk resets on restart. Sites saved in `demo_data/` always survive. To keep it awake, point a free uptime pinger at `/health`.

### Project files

| File | Job |
|---|---|
| `crawler.py` | Reads the site: pages, PDFs, logo, name, booking and order links |
| `ask.py` | Builds the prompt and calls Nemotron on Nebius |
| `eval.py` | Accuracy test: asks a list of questions and scores the answers |
| `server.py` | The web server: setup, chat, Back office, settings, rate limits |
| `static/setup.html` | Landing page, setup receipt and install card |
| `static/widget.js` | The chat bubble businesses add to their site |
| `static/preview.html` | Preview page |
| `static/office.html` | Back office |
| `static/privacy.html` | Privacy and terms |
| `demo_data/` | Saved demo sites |

### Safety
- Rate limits per visitor, plus a daily cap across all visitors, to protect API credits.
- Only the owner's private key can restyle a site, re-read it or open its Back office.
- The crawler refuses private and internal network addresses.
- The API key stays on the server and is never sent to the browser.

</details>

## License

[GNU AGPL-3.0](LICENSE)