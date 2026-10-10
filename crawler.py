import io, json, os, sys
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

MAX_PAGES = 50
HEADERS = {"User-Agent": "FreeAgentBot"}


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
            if wanted in rels:
                return urljoin(base, link["href"])
    # 3. last resort: social share image (often a food photo)
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return urljoin(base, og["content"])
    return None


def crawl(start_url):
    domain = urlparse(start_url).netloc.replace("www.", "")
    to_visit, seen, pages = [start_url], set(), []
    logo = None
    site_name = None

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
            continue

        if "text/html" not in ctype:
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        page_title = soup.title.string if soup.title and soup.title.string else ""
        if r.status_code in (403, 429, 503) or "Just a moment" in page_title:
            print("blocked", url)
            continue

        if logo is None:
            logo = find_logo(soup, r.url)

        if site_name is None:
            meta = soup.find("meta", property="og:site_name") or soup.find("meta", attrs={"name": "application-name"})
            if meta and meta.get("content"):
                site_name = meta["content"].strip()

        for a in soup.find_all("a", href=True):
            link = urljoin(r.url, a["href"]).split("#")[0]
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

    return {"site": start_url, "name": site_name, "logo": logo, "pages": pages}


if __name__ == "__main__":
    url = sys.argv[1]
    data = crawl(url)
    os.makedirs("data", exist_ok=True)
    name = urlparse(url).netloc.replace(".", "_")
    with open(f"data/{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {len(data['pages'])} pages to data/{name}.json, logo: {data['logo']}, name: {data['name']}")