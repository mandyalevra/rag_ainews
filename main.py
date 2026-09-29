import os
import subprocess
from datetime import date
from pathlib import Path
import json
import re

import anthropic
import numpy as np
import resend
from dotenv import load_dotenv
from fastembed import TextEmbedding
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
You are an AI news curator for the platform "by mandy, daily". Given raw search results, produce a structured JSON digest.

Return ONLY valid JSON — no markdown fences, no commentary, no explanation.

Schema:
{
  "date": "April 27, 2026",
  "iso": "2026-04-27",
  "issue": 1,
  "weekday": "Monday",
  "readMin": 4,
  "tldr": [
    {"catId": "tools", "text": "One sentence on the standout tools or product story today."},
    {"catId": "money", "text": "One sentence on the standout funding or startup story today."},
    {"catId": "world", "text": "One sentence on the standout policy, regulation, or industry story today."}
  ],
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
- tldr: array of exactly 3 objects in order tools → money → world; each "text" is one tight sentence, no markdown
- readMin: integer between 3 and 5
- source: domain only, no scheme or www (e.g. "github.blog" not "https://github.blog")
- Drop any story whose URL does not link to a specific article. The URL path must contain a unique slug or identifier (e.g. "/blog/cursor-2-0" or "/p/openai-raises"). Drop if the path is empty, just "/", a top-level section ("/news", "/articles", "/blog" with no slug), or a root changelog/listing page with no specific post path
- Return only the JSON object, nothing else
- If a story's URL or title matches something in the "### Trending (most-covered today)" section, strongly prefer it: put it first in its category and treat it as a strong headline candidate

Headline rules (most important — read carefully):
- 2–4 words, all lowercase, captures the day's single biggest story
- Vary the STRUCTURE day to day — rotate between these forms and never repeat a form used recently:
    noun phrase:    "court drama",  "the llama escape",  "a quiet coup"
    verb phrase:    "apple opens up",  "models go free",  "sam moves fast"
    fragment/twist: "billion reasons",  "nobody saw that",  "it's complicated"
    alliterative:   "models, money, mayhem",  "funding frenzy"
    punny/playful:  "token economics",  "prompt and circumstance"
- Avoid generic filler words: "big", "news", "update", "new", "today"
- Never repeat the same person, company, or topic two days in a row — if recent headlines focused on Musk or OpenAI, pick a different angle entirely
- Prioritise the money or tools story if the world story dominated the last two headlines
- The headline should feel like a magazine cover line — specific, a little witty, impossible to ignore\
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


def fetch_trending(perp: Perplexity) -> list[dict]:
    resp = perp.search.create(
        query="most covered AI news story today 2026 multiple outlets mainstream",
        max_results=5,
        max_tokens_per_page=512,
        search_recency_filter="day",
    )
    return [
        {"title": r.title, "url": r.url, "snippet": r.snippet}
        for r in resp.results
    ]


def build_raw_context(all_results: dict[str, list[dict]], trending: list[dict] | None = None) -> str:
    sections = []
    for cat_name, results in all_results.items():
        items = "\n".join(
            f"- [{r['title']}]({r['url']})\n  {r['snippet']}" for r in results
        )
        sections.append(f"### {cat_name}\n{items}")
    if trending:
        items = "\n".join(
            f"- [{r['title']}]({r['url']})\n  {r['snippet']}" for r in trending
        )
        sections.append(f"### Trending (most-covered today)\n{items}")
    return "\n\n".join(sections)


def next_issue_number() -> int:
    existing = list(Path("digests").glob("*.json")) if Path("digests").exists() else []
    return len(existing) + 1


def recent_headlines(n: int = 5) -> list[str]:
    files = sorted(Path("digests").glob("*.json"), reverse=True)[:n] if Path("digests").exists() else []
    out = []
    for f in files:
        try:
            out.append(json.loads(f.read_text()).get("headline", ""))
        except Exception:
            pass
    return [h for h in out if h]


def generate_digest(claude: anthropic.Anthropic, raw: str, today_date: date) -> dict:
    issue = next_issue_number()
    weekday = today_date.strftime("%A")
    date_str = today_date.strftime("%B %d, %Y")
    iso = today_date.isoformat()

    past = recent_headlines()
    past_note = (
        f"\nRecent headlines to avoid repeating in structure or style: {past}\n"
        if past else ""
    )

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
                    f"Today is {date_str} ({weekday}), ISO: {iso}, issue number: {issue}.{past_note}\n\n"
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


def evaluate_digest(claude: anthropic.Anthropic, digest: dict, raw: str) -> dict:
    """Non-blocking quality check on a freshly generated digest.

    Runs cheap structural checks first, then asks a second Claude call to
    verify every claim in the digest is actually backed by the raw search
    results it was generated from. Returns {"passed": bool, "issues": [str]}.
    """
    issues: list[str] = []

    if not digest.get("headline"):
        issues.append("Missing headline")
    if not digest.get("tldr"):
        issues.append("Missing TL;DR")

    seen_titles: set[str] = set()
    for cat in digest.get("categories", []):
        if not cat.get("stories"):
            issues.append(f"Category '{cat.get('name')}' has no stories")
        for story in cat.get("stories", []):
            title = (story.get("title") or "").strip().lower()
            if title and title in seen_titles:
                issues.append(f"Duplicate story title: {story.get('title')}")
            seen_titles.add(title)
            if not (story.get("url") or "").startswith("http"):
                issues.append(f"Bad/missing URL for story: {story.get('title')}")

    # Guard against a fetch/generation hiccup silently reusing yesterday's
    # content instead of failing loudly. Compares against the most recent
    # digest already on disk (today's hasn't been written yet at this point).
    prev_files = sorted(Path("digests").glob("*.json"), reverse=True)
    if prev_files:
        try:
            prev = json.loads(prev_files[0].read_text())
            prev_headline = (prev.get("headline") or "").strip().lower()
            cur_headline = (digest.get("headline") or "").strip().lower()
            if cur_headline and cur_headline == prev_headline:
                issues.append(f"Headline identical to previous digest ({prev_files[0].name}): '{digest.get('headline')}'")

            prev_titles = {s.get("title", "").strip().lower() for c in prev.get("categories", []) for s in c.get("stories", [])}
            cur_titles = {s.get("title", "").strip().lower() for c in digest.get("categories", []) for s in c.get("stories", [])}
            overlap = len(cur_titles & prev_titles) / len(cur_titles) if cur_titles else 0
            if overlap > 0.4:
                issues.append(f"{overlap:.0%} of today's story titles match {prev_files[0].name} — possible stale/replicated content")
        except Exception:
            pass

    judge_prompt = (
        "You are fact-checking an AI-generated news digest against the raw search "
        "results it was built from. Flag any claim in the digest's headline, TL;DR, "
        "or story summaries that is NOT supported by the raw source material below "
        "— fabricated details, wrong numbers, or exaggerated framing.\n\n"
        f"RAW SOURCE MATERIAL:\n{raw[:12000]}\n\n"
        f"DIGEST TO CHECK:\n{json.dumps(digest, indent=2)}\n\n"
        'Respond with JSON only, no other text: {"grounded": true/false, "unsupported_claims": ["..."]}'
    )
    try:
        response = claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": judge_prompt}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        result = json.loads(text)
        if not result.get("grounded", True):
            issues.extend(f"Unsupported claim: {c}" for c in result.get("unsupported_claims", []))
    except Exception as e:
        issues.append(f"Eval judge call failed: {e}")

    return {"passed": len(issues) == 0, "issues": issues}


def markdown_from_digest(digest: dict) -> str:
    cat_labels = {
        "tools": "🔧 AI Tool & Product News",
        "money": "💰 AI Startup & Investment News",
        "world": "🌐 General AI News",
    }
    lines = [
        f"# AI Daily Digest — {digest['date']}",
        "",
        f"**TL;DR:** {' · '.join(b['text'] for b in digest['tldr']) if isinstance(digest['tldr'], list) else digest['tldr']}",
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

    sent, failed = 0, 0
    for email in subscribers:
        params: resend.Emails.SendParams = {
            "from": from_email,
            "to": [email],
            "subject": f"by mandy, daily — {digest['date']}",
            "html": html,
        }
        try:
            resend.Emails.send(params)
            sent += 1
        except Exception as e:
            print(f"  [email] Failed to send to {email}: {e}")
            failed += 1
    print(f"  [email] Sent to {sent} subscriber(s). {failed} failed.")


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

    # Cache-bust the data.js script tag in index.html with today's date
    # so every browser always loads the fresh file without needing a hard refresh
    index_path = Path("web/index.html")
    html = index_path.read_text()
    today_str = date.today().isoformat()
    html = re.sub(
        r'<script src="data\.js(?:\?v=[^"]*)?"></script>',
        f'<script src="data.js?v={today_str}"></script>',
        html,
    )
    index_path.write_text(html)


def build_audio_script(digest: dict) -> str:
    lines = [
        f"Good morning. This is by mandy, daily — your AI briefing for {digest.get('weekday')}, {digest.get('date')}.",
        f"Today: {digest.get('headline')}.",
        "",
        "Here's your quick take.",
    ]
    if isinstance(digest.get("tldr"), list):
        for item in digest["tldr"]:
            lines.append(item["text"])
    lines.append("")
    for cat in digest.get("categories", []):
        lines.append(f"{cat['name']}.")
        for story in cat.get("stories", []):
            lines.append(f"{story['title']}. {story['summary']}")
        lines.append("")
    lines.append("That's your AI briefing for today. See you tomorrow.")
    return "\n".join(lines)


def generate_audio(digest: dict) -> None:
    import urllib.request
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        print("  [audio] ELEVENLABS_API_KEY not set — skipping.")
        return
    script = build_audio_script(digest)
    voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel
    data = json.dumps({
        "text": script,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=data,
        headers={"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
    )
    try:
        audio_dir = Path("web/audio")
        audio_dir.mkdir(exist_ok=True)
        with urllib.request.urlopen(req) as resp:
            audio_path = audio_dir / f"{digest['iso']}.mp3"
            audio_path.write_bytes(resp.read())
        print(f"  [audio] Saved → {audio_path}")
    except Exception as e:
        print(f"  [audio] Failed: {e}")
        send_failure_alert(str(e), context="audio generation")


def build_embeddings_index() -> None:
    json_files = sorted(Path("digests").glob("*.json"))
    if not json_files:
        return

    print("Building embeddings index...")

    # Load existing embeddings to avoid re-embedding unchanged stories
    existing_path = Path("web/embeddings.json")
    existing: dict[str, dict] = {}
    if existing_path.exists():
        try:
            for s in json.loads(existing_path.read_text()):
                key = f"{s['digestIso']}:{s['url']}"
                existing[key] = s
        except Exception:
            pass

    all_stories = []
    new_stories = []
    for f in json_files:
        try:
            digest = json.loads(f.read_text())
        except Exception:
            continue
        for cat in digest.get("categories", []):
            for s in cat.get("stories", []):
                story = {
                    "digestIso": digest["iso"],
                    "digestDate": digest["date"],
                    "catId": cat["id"],
                    "catName": cat["name"],
                    "catEmoji": cat["emoji"],
                    "catAccent": cat["accent"],
                    **s,
                }
                key = f"{digest['iso']}:{s.get('url', '')}"
                if key in existing:
                    story["embedding"] = existing[key]["embedding"]
                else:
                    new_stories.append((len(all_stories), story))
                all_stories.append(story)

    if new_stories:
        model = TextEmbedding("BAAI/bge-small-en-v1.5")
        texts = [f"{s['title']}. {s['summary']}" for _, s in new_stories]
        embeddings = list(model.embed(texts))
        for (idx, story), vec in zip(new_stories, embeddings):
            story["embedding"] = vec.tolist()
            all_stories[idx] = story
        print(f"  → Embedded {len(new_stories)} new stories")
    else:
        print("  → No new stories to embed")

    existing_path.write_text(json.dumps(all_stories))
    print(f"  → {len(all_stories)} total stories in web/embeddings.json")


def main(force: bool = False) -> None:
    today = date.today()
    out_dir = Path("digests")
    out_dir.mkdir(exist_ok=True)
    json_path = out_dir / f"{today.isoformat()}.json"
    md_path   = out_dir / f"{today.isoformat()}.md"

    # Guard: skip everything if today's digest already exists
    if json_path.exists() and not force:
        print(f"Digest for {today.strftime('%B %d, %Y')} already exists — nothing to do.")
        print("Run with --force to regenerate and resend.")
        return

    perp = Perplexity()
    claude = anthropic.Anthropic()

    print(f"Fetching AI news for {today.strftime('%B %d, %Y')}...\n")

    all_results: dict[str, list[dict]] = {}
    for cat in CATEGORIES:
        print(f"  [{cat['name']}] searching...")
        all_results[cat["name"]] = fetch_category(perp, cat)
        print(f"    → {len(all_results[cat['name']])} results")

    print("  [Trending] finding most-covered stories...")
    try:
        trending = fetch_trending(perp)
        print(f"    → {len(trending)} trending results")
    except Exception as e:
        print(f"    → trending fetch failed ({e}), skipping")
        trending = None

    print("\nSynthesizing digest with Claude...\n")
    raw = build_raw_context(all_results, trending)
    digest = generate_digest(claude, raw, today)

    print("Running content eval...")
    eval_result = evaluate_digest(claude, digest, raw)
    if eval_result["passed"]:
        print("  [eval] Passed — no issues found.")
    else:
        print(f"  [eval] Flagged {len(eval_result['issues'])} issue(s):")
        for issue in eval_result["issues"]:
            print(f"    - {issue}")
        # Monitor mode: alert, but still publish — see main.py notes on graduating to gating.
        send_failure_alert(
            "\n".join(eval_result["issues"]),
            context="content eval (non-blocking, digest still published)",
        )

    json_path.write_text(json.dumps(digest, indent=2))
    md_path.write_text(markdown_from_digest(digest))

    build_web_data()

    print("Sending digest email to subscribers...")
    send_digest_email(digest)

    print("Generating audio digest...")
    generate_audio(digest)

    build_embeddings_index()

    divider = "─" * 60
    print(divider)
    print(markdown_from_digest(digest))
    print(divider)
    print(f"\nSaved → {json_path}")
    print(f"Saved → {md_path}")
    print(f"Web data → web/data.js ({len(digest.get('categories', []))} categories)")

    # Push updated web files to GitHub so Railway auto-deploys with fresh data
    print("\nPushing to GitHub...")
    try:
        subprocess.run(["git", "add", "web/data.js", "web/embeddings.json", "web/index.html"], check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if result.returncode != 0:
            subprocess.run(["git", "commit", "-m", f"digest: {today.isoformat()}"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("  → Pushed to GitHub")
    except subprocess.CalledProcessError as e:
        print(f"  → Git push failed (non-fatal): {e}")
        send_failure_alert(str(e), context="git push")


def send_failure_alert(error: str, context: str = "the daily digest") -> None:
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        return
    try:
        import resend
        resend.api_key = api_key
        resend.Emails.send({
            "from": os.environ.get("RESEND_FROM_EMAIL", "digest@mandyalevra.com"),
            "to": ["mandy.alevra@gmail.com"],
            "subject": f"⚠️ by mandy, daily — {context} failed {date.today().isoformat()}",
            "html": f"<p>{context} failed to run on {date.today().isoformat()}.</p><pre>{error}</pre><p>Check the VPS logs: <code>tail -50 ~/rag_ainews/digest.log</code></p>",
        })
        print("  → Failure alert sent to mandy.alevra@gmail.com")
    except Exception as e:
        print(f"  → Could not send failure alert: {e}")


if __name__ == "__main__":
    import sys
    import traceback
    try:
        main(force="--force" in sys.argv)
    except Exception:
        err = traceback.format_exc()
        print(f"FATAL ERROR:\n{err}")
        load_dotenv(override=True)
        send_failure_alert(err)
