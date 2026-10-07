import io, json, os, sys
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

MAX_PAGES = 30

def pdf_text(content):
    try:
        reader = PdfReader(io.BytesIO(content))
        return " ".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:
        print("pdf fail", e)
        return ""

def crawl(start_url):
    domain = urlparse(start_url).netloc
    to_visit, seen, pages = [start_url], set(), []
    logo = None

    while to_visit and len(pages) < MAX_PAGES:
        url = to_visit.pop(0).split("#")[0]
        if url in seen:
            continue
        seen.add(url)
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "FreeAgentBot"})
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

        if logo is None:
            icon = soup.find("meta", property="og:image") or soup.find("link", rel="icon")
            if icon:
                logo = urljoin(url, icon.get("content") or icon.get("href"))

        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"]).split("#")[0]
            if link in seen:
                continue
            if link.lower().endswith(".pdf"):
                to_visit.insert(0, link)  # PDFs first, often menus/price lists
            elif urlparse(link).netloc == domain:
                to_visit.append(link)

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        title = soup.title.string.strip() if soup.title and soup.title.string else url
        text = " ".join(soup.get_text(" ").split())
        pages.append({"url": url, "title": title, "text": text})
        print("got", url)

    return {"site": start_url, "logo": logo, "pages": pages}

if __name__ == "__main__":
    url = sys.argv[1]
    data = crawl(url)
    os.makedirs("data", exist_ok=True)
    name = urlparse(url).netloc.replace(".", "_")
    with open(f"data/{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {len(data['pages'])} pages to data/{name}.json")