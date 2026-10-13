import io, json, os, re, sys
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

MAX_PAGES = 50
MAX_ACTIONS = 8
HEADERS = {"User-Agent": "FreeAgentBot"}

# words on a link that mean "book / reserve / order"
ACTION_TEXT = re.compile(r"\b(book( now| online| an? appointment| a table)?|reserve( now| a table)?|reservations?|"
                         r"appointments?|schedule( now| online)?|order( online| now| ahead| pickup| delivery)?)\b")
# booking / ordering services businesses link out to
ACTION_HOSTS = ("opentable", "resy.com", "toasttab", "calendly", "vagaro", "booksy", "fresha", "squareup",
                "square.site", "doordash", "ubereats", "grubhub", "mindbody", "setmore", "acuityscheduling",
                "exploretock", "sevenrooms", "chownow", "slicelife")
SKIP_HOSTS = ("facebook.", "instagram.", "twitter.", "x.com", "tiktok.", "youtube.", "linkedin.", "pinterest.")


def pdf_text(content):
    try:
        reader = PdfReader(io.BytesIO(content))
        return " ".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:
        print("pdf fail", e)
        return ""


def find_logo(soup, base):
    # 1. an <img> that says "logo" in its src, class, alt or id
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src or src.startswith("data:"):
            continue
        hint = " ".join([src, " ".join(img.get("class", [])), img.get("alt", ""), img.get("id", "")]).lower()
        if "logo" in hint:
            return urljoin(base, src)
    # 2. app icon, then normal site icon
    for wanted in ("apple-touch-icon", "icon"):
        for link in soup.find_all("link", href=True):
            rels = " ".join(link.get("rel", [])).lower()
            if wanted in rels and not link["href"].startswith("data:"):
                return urljoin(base, link["href"])
    # 3. last resort: social share image (often a food photo)
    og = soup.find("meta", property="og:image")
    if og and og.get("content") and not og["content"].startswith("data:"):
        return urljoin(base, og["content"])
    return None


def action_kind(text, url):
    both = f"{text} {url}".lower()
    if re.search(r"order|doordash|ubereats|grubhub|toasttab|chownow|slicelife", both):
        return "order"
    if re.search(r"reserv|opentable|resy|tock|sevenrooms|table", both):
        return "reserve"
    return "book"


def maybe_action(a, link, actions):
    """Remember links like 'Book now', 'Reserve a table', 'Order online'."""
    if len(actions) >= MAX_ACTIONS or link in actions:
        return
    p = urlparse(link)
    if p.scheme not in ("http", "https") or any(h in p.netloc for h in SKIP_HOSTS):
        return
    text = " ".join(a.get_text(" ", strip=True).split())
    host_hit = any(h in p.netloc for h in ACTION_HOSTS)
    text_hit = len(text) <= 40 and ACTION_TEXT.search(text.lower())
    if host_hit or text_hit:
        actions[link] = {"url": link, "text": text[:40], "kind": action_kind(text, link)}
        return actions[link]


def crawl(start_url, progress=None):
    """progress(event, info) is called as we go, so the setup page can show real steps."""
    say = progress or (lambda event, info: None)
    domain = urlparse(start_url).netloc.replace("www.", "")
    to_visit, seen, pages = [start_url], set(), []
    logo = None
    site_name = None
    description = None
    actions = {}

    while to_visit and len(pages) < MAX_PAGES:
        url = to_visit.pop(0).split("#")[0]
        if url in seen:
            continue
        seen.add(url)
        try:
            r = requests.get(url, timeout=15, headers=HEADERS)
        except Exception as e:
            print("skip", url, e)
            continue
        ctype = r.headers.get("Content-Type", "")

        if "pdf" in ctype or url.lower().endswith(".pdf"):
            text = " ".join(pdf_text(r.content).split())
            if text:
                pages.append({"url": url, "title": "PDF: " + url.split("/")[-1], "text": text})
                print("got pdf", url)
                say("pdf", {"count": len(pages), "name": url.split("/")[-1][:40]})
            continue

        if "text/html" not in ctype:
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        page_title = soup.title.string if soup.title and soup.title.string else ""
        if r.status_code in (403, 429, 503) or "Just a moment" in page_title:
            print("blocked", url)
            say("blocked", {"url": url})
            continue

        if logo is None:
            logo = find_logo(soup, r.url)
            if logo:
                say("logo", {"url": logo})

        if site_name is None:
            meta = soup.find("meta", property="og:site_name") or soup.find("meta", attrs={"name": "application-name"})
            if meta and meta.get("content"):
                site_name = meta["content"].strip()

        if description is None:
            m = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
            description = m["content"].strip() if m and m.get("content") else ""

        for a in soup.find_all("a", href=True):
            link = urljoin(r.url, a["href"]).split("#")[0]
            found = maybe_action(a, link, actions)
            if found:
                say("action", {"kind": found["kind"]})
            if link in seen:
                continue
            if link.lower().endswith(".pdf"):
                to_visit.insert(0, link)  # PDFs first, often menus/price lists
            elif urlparse(link).netloc.replace("www.", "") == domain:
                to_visit.append(link)

        for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
            tag.decompose()
        title = page_title.strip() or url
        text = " ".join(soup.get_text(" ").split())
        pages.append({"url": url, "title": title, "text": text})
        print("got", url)
        say("page", {"count": len(pages)})

    return {"site": start_url, "name": site_name, "description": description, "logo": logo,
            "actions": list(actions.values()), "pages": pages}


if __name__ == "__main__":
    url = sys.argv[1]
    data = crawl(url)
    os.makedirs("data", exist_ok=True)
    name = urlparse(url).netloc.replace(".", "_")
    with open(f"data/{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {len(data['pages'])} pages to data/{name}.json, logo: {data['logo']}, name: {data['name']}")
    for act in data["actions"]:
        print("action:", act["kind"], act["text"], act["url"])