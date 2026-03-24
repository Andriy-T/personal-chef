"""Manual test script for web_search and fetch_page tools.

Results are saved to test_results/ for review.
"""
import sys
import io
import re
import os
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from tools import web_search, fetch_page

QUERIES = [
    "receta tortilla española",
    "gazpacho andaluz receta",
    "pasta carbonara receta",
]

OUT_DIR = Path("test_results")


def save(filename: str, content: str):
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / filename
    path.write_text(content, encoding="utf-8")
    print(f"  Saved → {path}")
    return path


def slug(text: str) -> str:
    return re.sub(r"[^\w]+", "_", text).strip("_").lower()


def run_web_search_tests() -> dict[str, str]:
    """Run web_search for every query, save each result, return {query: result}."""
    print("\n" + "=" * 60)
    print("web_search")
    print("=" * 60)

    all_results = {}
    for query in QUERIES:
        print(f"\nQuery: {query!r}")
        result = web_search.invoke({"query": query})
        all_results[query] = result

        content = f"Query: {query}\n{'='*60}\n\n{result}"
        save(f"search_{slug(query)}.txt", content)

        preview = result[:300].replace("\n", " ")
        print(f"  Preview: {preview}...")

    return all_results


def extract_urls(text: str) -> list[str]:
    return [u.rstrip(".,)\"'") for u in re.findall(r"https?://[^\s\"']+", text)]


def run_fetch_page_tests(search_results: dict[str, str]):
    """For each query pick the first URL from its search result and fetch it."""
    print("\n" + "=" * 60)
    print("fetch_page")
    print("=" * 60)

    for query, result in search_results.items():
        urls = extract_urls(result)
        if not urls:
            print(f"\n[{query}] No URL found — skipping.")
            save(f"fetch_{slug(query)}.txt", f"Query: {query}\n\nNo URL found in search results.")
            continue

        url = urls[0]
        print(f"\nQuery:  {query!r}")
        print(f"URL:    {url}")
        page = fetch_page.invoke({"url": url})

        content = f"Query: {query}\nURL: {url}\n{'='*60}\n\n{page}"
        save(f"fetch_{slug(query)}.txt", content)

        preview = page[:300].replace("\n", " ")
        print(f"Preview: {preview}...")


def write_summary(search_results: dict[str, str]):
    lines = [
        f"Test run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "web_search results",
        "-" * 40,
    ]
    for query, result in search_results.items():
        urls = extract_urls(result)
        lines.append(f"  {query!r}: {len(urls)} URL(s) found")
        for u in urls:
            lines.append(f"    - {u}")

    lines += ["", "fetch_page results", "-" * 40]
    for query in search_results:
        path = OUT_DIR / f"fetch_{slug(query)}.txt"
        if path.exists():
            text = path.read_text(encoding="utf-8")
            chars = len(text)
            lines.append(f"  {query!r}: {chars} chars fetched")

    save("summary.txt", "\n".join(lines))


if __name__ == "__main__":
    search_results = run_web_search_tests()
    run_fetch_page_tests(search_results)
    write_summary(search_results)
    print(f"\nDone. Results in ./{OUT_DIR}/")
