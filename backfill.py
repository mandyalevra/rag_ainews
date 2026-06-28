import json
import time
import re
from datetime import date, timedelta
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from perplexity import Perplexity

from main import CATEGORIES, SCHEMA_PROMPT, build_web_data, build_embeddings_index, next_issue_number, recent_headlines

load_dotenv(override=True)

START_DATE = date(2026, 5, 19)
END_DATE   = date(2026, 6, 27)


def fetch_category_for_date(perp: Perplexity, category: dict, target: date) -> list[dict]:
    date_str = target.strftime("%B %d, %Y")
    query = f"{category['query']} {date_str}"
    kwargs: dict = {
        "query": query,
        "max_results": 8,
        "max_tokens_per_page": 1024,
        "search_recency_filter": "month",
    }
    if category["domains"]:
        kwargs["search_domain_filter"] = category["domains"]
    resp = perp.search.create(**kwargs)
    return [
        {"title": r.title, "url": r.url, "snippet": r.snippet, "date": r.date}
        for r in resp.results
    ]


def build_raw_context(all_results: dict) -> str:
    sections = []
    for cat_name, results in all_results.items():
        items = "\n".join(
            f"- [{r['title']}]({r['url']})\n  {r['snippet']}" for r in results
        )
        sections.append(f"### {cat_name}\n{items}")
    return "\n\n".join(sections)


def generate_digest_for_date(claude: anthropic.Anthropic, raw: str, target: date) -> dict:
    out_dir = Path("digests")
    existing = list(out_dir.glob("*.json")) if out_dir.exists() else []
    issue = len(existing) + 1
    weekday = target.strftime("%A")
    date_str = target.strftime("%B %d, %Y")
    iso = target.isoformat()

    past = recent_headlines()
    past_note = (
        f"\nRecent headlines to avoid repeating in structure or style: {past}\n"
        if past else ""
    )

    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=[{"type": "text", "text": SCHEMA_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{
            "role": "user",
            "content": (
                f"Today is {date_str} ({weekday}), ISO: {iso}, issue number: {issue}.{past_note}\n\n"
                f"Raw search results:\n\n{raw}\n\n"
                f"Return the digest JSON."
            ),
        }],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def main():
    out_dir = Path("digests")
    out_dir.mkdir(exist_ok=True)

    perp = Perplexity()
    claude = anthropic.Anthropic()

    current = START_DATE
    while current <= END_DATE:
        json_path = out_dir / f"{current.isoformat()}.json"
        if json_path.exists():
            print(f"[{current}] already exists — skipping")
            current += timedelta(days=1)
            continue

        print(f"\n[{current}] Fetching news...")
        all_results = {}
        for cat in CATEGORIES:
            print(f"  [{cat['name']}] searching...")
            try:
                all_results[cat["name"]] = fetch_category_for_date(perp, cat, current)
                print(f"    → {len(all_results[cat['name']])} results")
            except Exception as e:
                print(f"    → Error: {e}")
                all_results[cat["name"]] = []

        raw = build_raw_context(all_results)

        print(f"  Synthesizing with Claude...")
        try:
            digest = generate_digest_for_date(claude, raw, current)
            json_path.write_text(json.dumps(digest, indent=2))
            print(f"  Saved → {json_path}")
        except Exception as e:
            print(f"  Failed to generate digest: {e}")
            current += timedelta(days=1)
            continue

        # Pause to avoid rate limits
        time.sleep(5)
        current += timedelta(days=1)

    print("\nBuilding web data and embeddings...")
    build_web_data()
    build_embeddings_index()
    print("Done.")


if __name__ == "__main__":
    main()
