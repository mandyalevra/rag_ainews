import os
from datetime import date
from pathlib import Path
import json
import re

import anthropic
import resend
from dotenv import load_dotenv
from perplexity import Perplexity

from email_template import build_email_html

load_dotenv(override=True)

CATEGORIES = [
    {
        "name": "AI Tool & Product News",
        "id": "tools",
        "query": "new AI model product tool feature release launch announced today 2026",
        "domains": [
            "anthropic.com", "openai.com", "deepmind.google", "blog.google",
            "mistral.ai", "meta.ai", "huggingface.co", "cohere.com",
            "x.ai", "perplexity.ai", "cursor.sh", "github.blog",
            "stability.ai", "replicate.com",
        ],
    },
    {
        "name": "AI Startup & Investment News",
        "id": "money",
        "query": "AI startup funding investment series seed round raised valuation 2026",
        "domains": [
            "techcrunch.com", "venturebeat.com", "axios.com", "bloomberg.com",
            "reuters.com", "sifted.eu", "therundown.ai", "tradevc.xyz",
            "pitchbook.com", "forbes.com", "theinformation.com",
        ],
    },
    {
        "name": "General AI News",
        "id": "world",
        "query": (
            "artificial intelligence news policy regulation lawsuit government"
            " leadership industry today 2026"
        ),
        "domains": None,
    },
]

SCHEMA_PROMPT = """\
You are an AI news curator for the platform "daily.exe". Given raw search results, produce a structured JSON digest.

Return ONLY valid JSON — no markdown fences, no commentary, no explanation.

Schema:
{
  "date": "April 27, 2026",
  "iso": "2026-04-27",
  "issue": 1,
  "weekday": "Monday",
  "readMin": 4,
  "tldr": "1–2 sentence summary of the day's most important AI story.",
  "headline": "court drama",
  "categories": [
    {
      "id": "tools",
      "emoji": "🔧",
      "name": "Tools & Products",
      "tagline": "What shipped today",
      "blurb": "1-sentence description of this category.",
      "accent": "pink",
      "stories": [
        {
          "title": "Short punchy story title",
          "summary": "2–3 sentences. Plain text, no markdown.",
          "source": "github.blog",
          "url": "https://github.blog/...",
          "tags": ["pricing", "devtools"]
        }
      ]
    }
  ]
}

Fixed values per category (do not vary):
- tools:  id="tools",  emoji="🔧", name="Tools & Products",    tagline="What shipped today",  accent="pink"
- money:  id="money",  emoji="💰", name="Startups & Money",    tagline="Who got paid",        accent="lilac"
- world:  id="world",  emoji="🌐", name="The Bigger Picture",  tagline="Policy, drama, court", accent="lime"

Rules:
- Exactly 3 categories in order: tools, money, world
- 3–5 stories per category; drop duplicates and low-signal results
- headline: 2–3 words, lowercase, evocative (e.g. "court drama", "apple opens up")
- readMin: integer between 3 and 5
- source: domain only, no scheme or www (e.g. "github.blog" not "https://github.blog")
- Return only the JSON object, nothing else\
"""


def fetch_category(perp: Perplexity, category: dict) -> list[dict]:
    kwargs: dict = {
        "query": category["query"],
        "max_results": 8,
        "max_tokens_per_page": 1024,
        "search_recency_filter": "day",
    }
    if category["domains"]:
        kwargs["search_domain_filter"] = category["domains"]

    resp = perp.search.create(**kwargs)
    return [
        {"title": r.title, "url": r.url, "snippet": r.snippet, "date": r.date}
        for r in resp.results
    ]


def build_raw_context(all_results: dict[str, list[dict]]) -> str:
    sections = []
    for cat_name, results in all_results.items():
        items = "\n".join(
            f"- [{r['title']}]({r['url']})\n  {r['snippet']}" for r in results
        )
        sections.append(f"### {cat_name}\n{items}")
    return "\n\n".join(sections)


def next_issue_number() -> int:
    existing = list(Path("digests").glob("*.json")) if Path("digests").exists() else []
    return len(existing) + 1


def generate_digest(claude: anthropic.Anthropic, raw: str, today_date: date) -> dict:
    issue = next_issue_number()
    weekday = today_date.strftime("%A")
    date_str = today_date.strftime("%B %d, %Y")
    iso = today_date.isoformat()

    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": SCHEMA_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Today is {date_str} ({weekday}), ISO: {iso}, issue number: {issue}.\n\n"
                    f"Raw search results:\n\n{raw}\n\n"
                    f"Return the digest JSON."
                ),
            }
        ],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def markdown_from_digest(digest: dict) -> str:
    cat_labels = {
        "tools": "🔧 AI Tool & Product News",
        "money": "💰 AI Startup & Investment News",
        "world": "🌐 General AI News",
    }
    lines = [
        f"# AI Daily Digest — {digest['date']}",
        "",
        f"**TL;DR:** {digest['tldr']}",
        "",
    ]
    for cat in digest["categories"]:
        lines.append(f"## {cat_labels.get(cat['id'], cat['name'])}")
        for story in cat["stories"]:
            lines.append(
                f"- **{story['title']}.** {story['summary']}"
                f" [{story['source']}]({story['url']})"
            )
        lines.append("")
    return "\n".join(lines)


def load_subscribers() -> list[str]:
    f = Path("subscribers.json")
    return json.loads(f.read_text()) if f.exists() else []


def send_digest_email(digest: dict) -> None:
    api_key = os.environ.get("RESEND_API_KEY", "")
    from_email = os.environ.get("RESEND_FROM_EMAIL", "")
    if not api_key or not from_email:
        print("  [email] RESEND_API_KEY or RESEND_FROM_EMAIL not set — skipping.")
        return

    subscribers = load_subscribers()
    if not subscribers:
        print("  [email] No subscribers yet — skipping.")
        return

    resend.api_key = api_key
    html = build_email_html(digest)

    params: resend.Emails.SendParams = {
        "from": from_email,
        "to": subscribers,
        "subject": f"daily.exe — {digest['date']}",
        "html": html,
    }
    resend.Emails.send(params)
    print(f"  [email] Sent to {len(subscribers)} subscriber(s).")


def build_web_data() -> None:
    json_files = sorted(Path("digests").glob("*.json"), reverse=True)
    digests = []
    for f in json_files:
        try:
            digests.append(json.loads(f.read_text()))
        except Exception:
            pass
    js = (
        "// Auto-generated by main.py — do not edit manually\n"
        "window.ARCHIVE = " + json.dumps(digests, indent=2) + ";\n"
    )
    Path("web/data.js").write_text(js)


def main() -> None:
    perp = Perplexity()
    claude = anthropic.Anthropic()
    today = date.today()

    print(f"Fetching AI news for {today.strftime('%B %d, %Y')}...\n")

    all_results: dict[str, list[dict]] = {}
    for cat in CATEGORIES:
        print(f"  [{cat['name']}] searching...")
        all_results[cat["name"]] = fetch_category(perp, cat)
        print(f"    → {len(all_results[cat['name']])} results")

    print("\nSynthesizing digest with Claude...\n")
    raw = build_raw_context(all_results)
    digest = generate_digest(claude, raw, today)

    out_dir = Path("digests")
    out_dir.mkdir(exist_ok=True)

    json_path = out_dir / f"{today.isoformat()}.json"
    json_path.write_text(json.dumps(digest, indent=2))

    md_path = out_dir / f"{today.isoformat()}.md"
    md_path.write_text(markdown_from_digest(digest))

    build_web_data()

    print("Sending digest email to subscribers...")
    send_digest_email(digest)

    divider = "─" * 60
    print(divider)
    print(markdown_from_digest(digest))
    print(divider)
    print(f"\nSaved → {json_path}")
    print(f"Saved → {md_path}")
    print(f"Web data → web/data.js ({len(digests := json.loads(json_path.read_text()).get('categories', []))} categories)")


if __name__ == "__main__":
    main()
