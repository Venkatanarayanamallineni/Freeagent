"""
say2 accuracy test.

Asks say2 every question in a CSV file and scores the answers, so we can say
"we asked N questions, X were right, 0 made-up prices or links" with proof.

Run:
    python eval.py demo_data/thecafeames_com.json evals/thecafeames.csv

CSV columns (open and edit it in Excel or VS Code):
    question  what a customer would type
    type      answer   = the site has the answer
              missing  = the site does NOT say (say2 should admit it, not guess)
              notsold  = something the business clearly doesn't sell (cars at a cafe)
    must      words the answer must contain. Separate with ;  Alternatives with |
              example:  4.50 ; latte          or          8 am|8:00|8am
    avoid     words the answer must NOT contain (same format, optional)
    note      anything for you, ignored by the script

Writes eval_results.csv (every answer) and eval_report.md (summary for the README).
"""
import csv, json, os, re, sys, time
from ask import ask

PRICE_IN = float(os.getenv("PRICE_IN_PER_M") or 0)
PRICE_OUT = float(os.getenv("PRICE_OUT_PER_M") or 0)
ADMITS = re.compile(r"not sure|don't have|do not have|don't see|isn't listed|not listed|no details?|"
                    r"call us|give us a call|reach us|email us|contact us", re.I)
MONEY = re.compile(r"\$\s?(\d{1,4}(?:,\d{3})*(?:\.\d{1,2})?)")
URL = re.compile(r"https?://[^\s)\]>\"']+")


def read_csv(path):
    for enc in ("utf-8-sig", "cp1252"):  # Excel on Windows sometimes saves cp1252
        try:
            with open(path, encoding=enc, newline="") as f:
                return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]
        except UnicodeDecodeError:
            continue
    sys.exit(f"Could not read {path}. Save it as CSV UTF-8.")


def groups(cell):
    """'4.50 ; latte|coffee' -> [['4.50'], ['latte', 'coffee']]"""
    return [[w.strip().lower() for w in part.split("|") if w.strip()] for part in cell.split(";") if part.strip()]


def norm(s):
    for dash in "\u2010\u2011\u2012\u2013\u2014\u2212":   # all the kinds of dash a model may print
        s = s.replace(dash, "-")
    return " ".join(s.lower().replace("’", "'").replace("\u00a0", " ").split())


def known_text(data):
    """Everything say2 is allowed to know: site text plus the owner's own answers and rules."""
    bits = [p["text"] for p in data["pages"]]
    bits += [c["a"] for c in data.get("corrections") or []] + list(data.get("rules") or [])
    return norm(" ".join(bits))


def known_urls(data):
    urls = {p["url"] for p in data["pages"]} | {a["url"] for a in data.get("actions") or []} | {data["site"]}
    return {u.rstrip("/").lower() for u in urls}


def money_variants(n):
    n = n.replace(",", "")
    out = {n}
    if "." in n:
        whole, cents = n.split(".")
        out |= {f"{whole}.{cents.ljust(2, '0')}", whole if cents.strip("0") == "" else f"{whole}.{cents.rstrip('0')}"}
    else:
        out |= {f"{n}.00", f"{n}.0"}
    return out


def made_up(answer, text, urls):
    """Prices and links in the answer that appear nowhere in what say2 was given."""
    bad = []
    for n in MONEY.findall(answer):
        if not any(re.search(r"(?<![\d.])" + re.escape(v) + r"(?![\d])", text) for v in money_variants(n)):
            bad.append("$" + n)
    for u in URL.findall(answer):
        u = u.rstrip(".,;:").rstrip("/").lower()
        if u not in urls and u not in text:
            bad.append(u)
    return bad


def score(row, res, text, urls):
    a = norm(res["answer"])
    kind = (row.get("type") or "answer").lower()
    fake = made_up(res["answer"], text, urls)
    missing_words = [" / ".join(g) for g in groups(row.get("must", "")) if not any(w in a for w in g)]
    avoided = [w for g in groups(row.get("avoid", "")) for w in g if w in a]
    problems = []
    if fake:
        problems.append("not on site: " + ", ".join(fake))
    if avoided:
        problems.append("said: " + ", ".join(avoided))
    if kind == "missing":
        if not (res["unanswered"] or ADMITS.search(a)):
            problems.append("should admit it doesn't know")
    else:
        if missing_words:
            problems.append("missing: " + ", ".join(missing_words))
        if res["unanswered"]:
            problems.append("said it didn't know")
    return kind, not problems, problems, fake


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    rows = [r for r in read_csv(sys.argv[2]) if r.get("question")]
    if not rows:
        sys.exit("No questions found. The first row must be: question,type,must,avoid,note")
    text, urls = known_text(data), known_urls(data)

    results = []
    print(f"Asking {len(rows)} questions...\n")
    for i, row in enumerate(rows, 1):
        start = time.time()
        res = None
        for attempt in (1, 2):  # one retry if the API hiccups
            try:
                res = ask(data, [], row["question"])
                break
            except Exception as e:
                if attempt == 2:
                    res = {"answer": f"ERROR: {e}", "unanswered": False, "tokens": {"in": 0, "out": 0}}
                time.sleep(3)
        secs = time.time() - start
        kind, ok, problems, fake = score(row, res, text, urls)
        if res["answer"].startswith("ERROR:"):
            ok, problems = False, ["API error"]
        cost = res["tokens"]["in"] / 1e6 * PRICE_IN + res["tokens"]["out"] / 1e6 * PRICE_OUT
        results.append({"question": row["question"], "type": kind, "pass": ok, "problems": "; ".join(problems),
                        "fake": len(fake), "inbox": res["unanswered"], "seconds": round(secs, 2),
                        "tokens_in": res["tokens"]["in"], "tokens_out": res["tokens"]["out"],
                        "cost": round(cost, 5), "answer": res["answer"]})
        mark = "PASS" if ok else "FAIL"
        print(f"{i:>3}. {mark}  [{kind}] {row['question']}")
        if not ok:
            print(f"       {'; '.join(problems)}")
            print(f"       answer: {res['answer'][:160].replace(chr(10), ' ')}")

    with open("eval_results.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

    n = len(results)
    def part(kind):
        rs = [r for r in results if r["type"] == kind]
        return sum(r["pass"] for r in rs), len(rs)
    passed = sum(r["pass"] for r in results)
    fakes = sum(r["fake"] for r in results)
    ok_runs = [r for r in results if r["tokens_in"]]
    avg = lambda k: sum(r[k] for r in ok_runs) / max(1, len(ok_runs))
    a_ok, a_n = part("answer")
    m_ok, m_n = part("missing")
    s_ok, s_n = part("notsold")

    lines = [
        f"# say2 accuracy test",
        "",
        f"**Site:** {data['site']}  ",
        f"**Model:** {os.getenv('MODEL_ID')} on Nebius Token Factory  ",
        f"**Date:** {time.strftime('%Y-%m-%d')}",
        "",
        f"| Check | Result |",
        f"|---|---|",
        f"| Overall | **{passed} / {n}** ({passed / n:.0%}) |",
    ]
    if a_n: lines.append(f"| Correct answers (site has the answer) | {a_ok} / {a_n} |")
    if m_n: lines.append(f"| Admits it doesn't know (site doesn't say) | {m_ok} / {m_n} |")
    if s_n: lines.append(f"| Handles things the business doesn't sell | {s_ok} / {s_n} |")
    lines += [
        f"| Made-up prices or links found | **{fakes}** |",
        f"| Average time per answer | {avg('seconds'):.1f} s |",
        f"| Average tokens per answer | {avg('tokens_in') + avg('tokens_out'):,.0f} |",
    ]
    if PRICE_IN or PRICE_OUT:
        lines.append(f"| Average cost per answer | ${avg('cost'):.4f} |")
    lines += ["", "Made-up check: every $ amount and link in every answer is matched against the site's own text. "
              "Anything not found there counts as made up.", ""]
    fails = [r for r in results if not r["pass"]]
    if fails:
        lines += ["## Misses", ""] + [f"- **{r['question']}**: {r['problems']}" for r in fails]

    with open("eval_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("\n" + "\n".join(l for l in lines if l.startswith("|")))
    print("\nSaved eval_results.csv and eval_report.md")


if __name__ == "__main__":
    main()