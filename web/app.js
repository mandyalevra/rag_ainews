// app.js — converted from app.jsx (htm, no Babel)
const { useState, useEffect, useMemo, useRef } = React;
const html = htm.bind(React.createElement);

const DIGESTS = window.ARCHIVE;
const TODAY = DIGESTS[0];

// Wrap exact occurrences of q in <mark> — used when word appears literally
function highlight(text, q) {
  if (!q || !text) return text;
  const esc = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = text.split(new RegExp("(" + esc + ")", "gi"));
  if (parts.length === 1) return text;
  return parts.map((p, i) =>
    p.toLowerCase() === q
      ? html`<mark key=${i} className="hl-match">${p}</mark>`
      : p
  );
}

// Debounced semantic search — calls /api/search, returns story results with scores
function useSearch(query) {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const q = query.trim();
    if (!q) { setResults(null); setLoading(false); setError(null); return; }
    setLoading(true);
    setError(null);
    const timer = setTimeout(async () => {
      try {
        const res = await fetch("/api/search?q=" + encodeURIComponent(q) + "&n=15");
        if (!res.ok) throw new Error("search failed");
        const data = await res.json();
        setResults(data.results);
      } catch (e) {
        setError("search unavailable — is the server running?");
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 350);
    return () => clearTimeout(timer);
  }, [query.trim()]);

  return { results, loading, error };
}

// ─── ACCENT TOKENS ─────────────────────────────────────────────────────────
const ACCENTS = {
  pink:  { bg: "#FFD6E7", deep: "#E8369A", ink: "#5A0F36", soft: "#FFEEF5", glyph: "✿" },
  lilac: { bg: "#E4D9FF", deep: "#7C4DFF", ink: "#2F1A6E", soft: "#F2EDFF", glyph: "✦" },
  lime:  { bg: "#DEFF8C", deep: "#6B9E00", ink: "#2A3A00", soft: "#F2FFD6", glyph: "❋" },
};

// ─── DOODLES ───────────────────────────────────────────────────────────────
const Sparkle = ({ size = 18, color = "currentColor", style }) => html`
  <svg width=${size} height=${size} viewBox="0 0 24 24" style=${style} aria-hidden="true">
    <path d="M12 0 L13.5 9 L22 11 L13.5 13 L12 22 L10.5 13 L2 11 L10.5 9 Z" fill=${color} />
  </svg>
`;

const Squiggle = ({ width = 80, color = "currentColor", style }) => html`
  <svg width=${width} height="14" viewBox="0 0 80 14" style=${style} aria-hidden="true" fill="none">
    <path d="M2 7 Q 10 0, 18 7 T 34 7 T 50 7 T 66 7 T 78 7" stroke=${color} strokeWidth="2.5" strokeLinecap="round" />
  </svg>
`;

const Blob = ({ color, style }) => html`
  <svg viewBox="0 0 200 200" style=${style} aria-hidden="true">
    <path fill=${color} d="M44.6,-58.7C56.2,-49.1,62.5,-33.8,65.6,-18.3C68.7,-2.8,68.7,12.9,62.4,25.7C56.1,38.5,43.4,48.4,29.5,55.2C15.5,62,0.3,65.7,-15.9,63.7C-32.1,61.7,-49.3,54,-59.2,40.6C-69.1,27.2,-71.7,8.1,-68.2,-9.2C-64.7,-26.5,-55.1,-42,-41.7,-51.7C-28.3,-61.4,-11.1,-65.3,3.6,-69.6C18.4,-74,33,-68.3,44.6,-58.7Z" transform="translate(100 100)" />
  </svg>
`;

// ─── HEADER ────────────────────────────────────────────────────────────────
const Header = ({ onHome, onArchive, route, currentDigest }) => html`
  <header className="hdr">
    <button className="logo" onClick=${onHome}>
      <span className="logo-mark">
        <${Sparkle} size=${22} color="var(--ink)" />
      </span>
      <span className="logo-text">
        <span className="logo-name">by mandy, daily</span>
        <span className="logo-sub">an AI digest, written like a friend</span>
      </span>
    </button>
    <nav className="nav">
      <button className=${`nav-link ${route.view === "home" ? "active" : ""}`} onClick=${onHome}>today</button>
      <button className=${`nav-link ${route.view === "archive" ? "active" : ""}`} onClick=${onArchive}>
        archive
        <span className="nav-link-count">${DIGESTS.length}</span>
      </button>
      <span className="nav-spacer" />
      <span className="nav-date">${currentDigest.date}</span>
      ${currentDigest.iso === TODAY.iso && html`<${React.Fragment}><span className="nav-dot">●</span><span className="nav-status">live</span></${React.Fragment}>`}
    </nav>
  </header>
`;

// ─── HERO / TLDR ───────────────────────────────────────────────────────────
const TldrBullets = ({ digest }) => {
  // Support both new array format and old string format
  if (!Array.isArray(digest.tldr)) {
    return html`<p className="tldr-text">${digest.tldr}</p>`;
  }
  const catMap = Object.fromEntries(digest.categories.map(c => [c.id, c]));
  return html`
    <ul className="tldr-list">
      ${digest.tldr.map((item, i) => {
        const cat = catMap[item.catId] || {};
        const a = ACCENTS[cat.accent] || ACCENTS.pink;
        return html`
          <li key=${i} className="tldr-item">
            <span className="tldr-bullet" style=${{ background: a.deep }} />
            <span className="tldr-cat-emoji">${cat.emoji}</span>
            <span className="tldr-item-text">${item.text}</span>
          </li>
        `;
      })}
    </ul>
  `;
};

const Hero = ({ digest, isHistorical, onArchive }) => {
  const [y, m, d] = digest.iso.split("-");
  const shortDate = `${m}.${d}.${y.slice(2)}`;
  return html`
  <section className="hero">
    <div className="hero-meta">
      <span className="kbd">issue ${digest.issue}</span>
      <span className="hero-meta-dot">·</span>
      <span className="hero-date-full">${digest.weekday}, ${digest.date}</span>
      <span className="hero-date-short">${shortDate}</span>
      <span className="hero-meta-dot">·</span>
      <span><span className="hero-read-full">${digest.readMin} min read</span><span className="hero-read-short">${digest.readMin} min</span></span>
      ${isHistorical && html`
        <${React.Fragment}>
          <span className="hero-meta-dot">·</span>
          <span className="hero-archive-pill">from the archive</span>
        </${React.Fragment}>
      `}
      <span className="hero-meta-dot">·</span>
      <${AudioPlayer} iso=${digest.iso} />
    </div>
    <h1 className="hero-title">
      Today, <em className="hl-pink">${digest.headline}</em>.
    </h1>
    <div className="tldr">
      <div className="tldr-label">
        <span>TL;DR</span>
        <${Sparkle} size=${14} color="#1A1613" />
      </div>
      <${TldrBullets} digest=${digest} />
    </div>
    <div className="hero-decor">
      <${Squiggle} width=${120} color="var(--accent-pink-deep)" style=${{ position: "absolute", top: 18, right: -8, transform: "rotate(-12deg)" }} />
      <${Sparkle} size=${28} color="var(--accent-lime-deep)" style=${{ position: "absolute", top: -20, left: -36, transform: "rotate(15deg)" }} />
      <${Sparkle} size=${20} color="var(--accent-lilac-deep)" style=${{ position: "absolute", bottom: 30, right: -40 }} />
    </div>
  </section>
`;
};

// ─── AUDIO PLAYER ──────────────────────────────────────────────────────────
const AudioPlayer = ({ iso }) => {
  const [state, setState] = useState("idle"); // idle | loading | playing | paused | unavailable
  const audioRef = useRef(null);

  const toggle = async () => {
    if (state === "unavailable") return;
    if (!audioRef.current) {
      audioRef.current = new Audio(`/audio/${iso}.mp3`);
      audioRef.current.onended = () => setState("idle");
      audioRef.current.onerror = () => setState("unavailable");
    }
    const a = audioRef.current;
    if (state === "playing") {
      a.pause();
      setState("paused");
    } else {
      setState("loading");
      try {
        await a.play();
        setState("playing");
      } catch {
        setState("unavailable");
      }
    }
  };

  useEffect(() => () => audioRef.current?.pause(), [iso]);

  if (state === "unavailable") return null;

  const label = state === "playing" ? "pause" : state === "loading" ? "…" : "listen";
  const icon = state === "playing"
    ? html`<path d="M6 5 H8 V15 H6 Z M11 5 H13 V15 H11 Z" fill="currentColor" />`
    : html`<path d="M6 4 L18 11 L6 18 Z" fill="currentColor" />`;

  return html`
    <button className="audio-btn" onClick=${toggle} title="Listen to today's digest">
      <svg width="16" height="16" viewBox="0 0 20 20">${icon}</svg>
      <span>${label}</span>
    </button>
  `;
};

// ─── CATEGORY CARDS ────────────────────────────────────────────────────────
const CategoryCard = ({ cat, index, onOpen }) => {
  const accent = ACCENTS[cat.accent];
  const [hovered, setHovered] = useState(false);
  const rotations = ["-2.5deg", "1.5deg", "-1deg"];
  return html`
    <button
      className="cat-card"
      onClick=${() => onOpen(cat.id)}
      onMouseEnter=${() => setHovered(true)}
      onMouseLeave=${() => setHovered(false)}
      style=${{
        background: accent.bg,
        color: accent.ink,
        "--cat-deep": accent.deep,
        "--cat-soft": accent.soft,
        transform: `rotate(${hovered ? "0deg" : rotations[index]})`,
      }}
    >
      <div className="cat-card-top">
        <span className="cat-num">0${index + 1}</span>
        <span className="cat-arrow" aria-hidden="true">
          <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
            <circle cx="18" cy="18" r="17" stroke=${accent.deep} strokeWidth="1.5" fill="none" />
            <path d="M13 18 H23 M19 14 L23 18 L19 22" stroke=${accent.deep} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      </div>
      <div className="cat-emoji" aria-hidden="true">${cat.emoji}</div>
      <div className="cat-meta">
        <span className="cat-tagline">${cat.tagline}</span>
        <span className="cat-count">${cat.stories.length} stories</span>
      </div>
      <h3 className="cat-name">${cat.name}</h3>
      <p className="cat-blurb">${cat.blurb}</p>
      <div className="cat-tags">
        ${cat.stories.slice(0, 3).map((s, i) => html`
          <span key=${i} className="cat-tag">${s.tags[0]}</span>
        `)}
      </div>
      <div className="cat-glyph" aria-hidden="true" style=${{ color: accent.deep }}>${accent.glyph}</div>
    </button>
  `;
};

const CategoryGrid = ({ digest, onOpen }) => html`
  <section className="cat-grid-wrap">
    <div className="cat-grid-head">
      <h2 className="section-title">
        Pick your <em className="hl-lilac">flavor</em> of news
        <${Sparkle} size=${22} color="var(--accent-pink-deep)" style=${{ display: "inline", verticalAlign: "middle", marginLeft: 6 }} />
      </h2>
      <p className="section-sub">three categories, hand-picked headlines, zero hype.</p>
    </div>
    <div className="cat-grid">
      ${digest.categories.map((c, i) => html`
        <${CategoryCard} key=${c.id} cat=${c} index=${i} onOpen=${onOpen} />
      `)}
    </div>
  </section>
`;

// ─── STORY CARDS ───────────────────────────────────────────────────────────
const StoryCard = ({ story, accent, index }) => {
  const [open, setOpen] = useState(true);
  const a = ACCENTS[accent];
  return html`
    <article className=${`story ${open ? "open" : ""}`} style=${{ "--cat-deep": a.deep, "--cat-bg": a.bg, "--cat-soft": a.soft }}>
      <button className="story-head" onClick=${() => setOpen(!open)}>
        <div className="story-num"><span>${String(index + 1).padStart(2, "0")}</span></div>
        <div className="story-head-main">
          <h3 className="story-title">${story.title}</h3>
          <div className="story-meta">
            <span className="story-source">${story.source}</span>
            <span className="story-dot">·</span>
            ${story.tags.map((t, i) => html`<span key=${i} className="story-tag">#${t}</span>`)}
          </div>
        </div>
        <span className="story-toggle" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M5 8 L10 13 L15 8" stroke=${a.deep} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      </button>
      <div className="story-body">
        <p>${story.summary}</p>
        <a href=${story.url} target="_blank" rel="noreferrer" className="story-link">
          read the source
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style=${{ marginLeft: 6 }}>
            <path d="M3 11 L11 3 M5 3 H11 V9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </a>
      </div>
    </article>
  `;
};

// ─── DIGEST DETAIL VIEW ────────────────────────────────────────────────────
const DigestView = ({ digest, catId, onBackHome, onPickCat }) => {
  const cat = digest.categories.find(c => c.id === catId);
  const a = ACCENTS[cat.accent];
  const idx = digest.categories.findIndex(c => c.id === catId);
  const next = digest.categories[(idx + 1) % digest.categories.length];

  useEffect(() => { window.scrollTo({ top: 0, behavior: "instant" }); }, [catId, digest.iso]);

  return html`
    <div className="digest" style=${{ "--cat-bg": a.bg, "--cat-deep": a.deep, "--cat-soft": a.soft, "--cat-ink": a.ink }}>
      <div className="digest-banner">
        <button onClick=${onBackHome} className="back-btn">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M10 3 L5 8 L10 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span>all categories</span>
        </button>
        <div className="digest-banner-meta">
          <span className="kbd">${digest.date}</span>
        </div>
      </div>

      <header className="digest-hero">
        <div className="digest-hero-emoji" aria-hidden="true">${cat.emoji}</div>
        <div className="digest-hero-text">
          <div className="digest-hero-eyebrow">
            <span>category /</span> <span style=${{ color: a.deep }}>${cat.tagline.toLowerCase()}</span>
          </div>
          <h1 className="digest-hero-title">${cat.name}</h1>
          <p className="digest-hero-blurb">${cat.blurb}</p>
        </div>
        <div className="digest-hero-decor">
          <${Blob} color=${a.bg} style=${{ position: "absolute", width: 280, height: 280, top: -80, right: -80, opacity: 0.55 }} />
          <${Sparkle} size=${32} color=${a.deep} style=${{ position: "absolute", top: 30, right: 60, transform: "rotate(20deg)" }} />
          <${Sparkle} size=${20} color=${a.deep} style=${{ position: "absolute", top: 130, right: 18, transform: "rotate(-15deg)" }} />
        </div>
      </header>

      <section className="stories">
        ${cat.stories.map((s, i) => html`<${StoryCard} key=${i} story=${s} accent=${cat.accent} index=${i} />`)}
      </section>

      <section className="next-cat">
        <span className="next-label">up next, same day</span>
        <button className="next-card" onClick=${() => onPickCat(next.id)} style=${{ background: ACCENTS[next.accent].bg, color: ACCENTS[next.accent].ink }}>
          <div>
            <div className="next-tagline">${next.tagline}</div>
            <div className="next-name">${next.name} <span style=${{ color: ACCENTS[next.accent].deep }}>→</span></div>
          </div>
          <span className="next-emoji">${next.emoji}</span>
        </button>
      </section>
    </div>
  `;
};

// ─── STORY SEARCH RESULT ───────────────────────────────────────────────────
const SCORE_LABEL = (score) => {
  if (score >= 0.65) return { label: "strong match", accent: "lime" };
  if (score >= 0.48) return { label: "related",      accent: "lilac" };
  return                    { label: "broad match",  accent: "pink" };
};

const StorySearchResult = ({ item, query, index, onOpenCat }) => {
  const a = ACCENTS[item.catAccent];
  const { label: scoreLabel, accent: scoreAccent } = SCORE_LABEL(item.score);
  const scoreA = ACCENTS[scoreAccent];
  return html`
    <button
      className="arch-card story-result"
      onClick=${() => onOpenCat(item.digestIso, item.catId)}
      style=${{ animationDelay: `${index * 40}ms` }}
    >
      <div className="arch-card-left story-result-cat">
        <div className="story-result-emoji">${item.catEmoji}</div>
        <div className="story-result-cat-name" style=${{ color: a.deep }}>${item.catName}</div>
      </div>
      <div className="arch-card-mid">
        <div className="arch-meta">
          <span>${item.digestDate}</span>
          <span className="arch-meta-dot">·</span>
          <span>${item.source}</span>
          ${item.tags.slice(0, 2).map((t, i) => html`
            <${React.Fragment} key=${i}>
              <span className="arch-meta-dot">·</span>
              <span>#${t}</span>
            </${React.Fragment}>
          `)}
          <span className="arch-meta-dot">·</span>
          <span className="story-score-pill" style=${{ background: scoreA.bg, color: scoreA.ink, borderColor: scoreA.deep }}>
            ${scoreLabel}
          </span>
        </div>
        <h3 className="arch-headline story-result-title">${highlight(item.title, query)}</h3>
        <p className="arch-tldr">${highlight(item.summary, query)}</p>
        <a href=${item.url} target="_blank" rel="noreferrer"
           className="story-result-link"
           onClick=${e => e.stopPropagation()}>
          read source →
        </a>
      </div>
      <div className="arch-card-arrow" aria-hidden="true">
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
          <circle cx="16" cy="16" r="15" stroke="var(--ink)" strokeWidth="1.5" fill="none" />
          <path d="M11 16 H21 M17 12 L21 16 L17 20" stroke="var(--ink)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </button>
  `;
};

// ─── ARCHIVE VIEW ──────────────────────────────────────────────────────────
const ArchiveCard = ({ digest, onOpen, isToday, index }) => {
  const accents = digest.categories.map(c => ACCENTS[c.accent]);
  return html`
    <button className="arch-card" onClick=${() => onOpen(digest.iso)} style=${{ animationDelay: `${index * 40}ms` }}>
      <div className="arch-card-left">
        <div className="arch-date">
          <span className="arch-day">${digest.date.split(" ")[1].replace(",", "")}</span>
          <span className="arch-month">${digest.date.split(" ")[0].slice(0, 3).toLowerCase()}</span>
        </div>
        <div className="arch-issue">issue ${digest.issue}</div>
      </div>
      <div className="arch-card-mid">
        <div className="arch-meta">
          <span>${digest.weekday}</span>
          <span className="arch-meta-dot">·</span>
          <span>${digest.readMin} min</span>
          ${isToday && html`<span className="arch-today-pill">today</span>`}
        </div>
        <h3 className="arch-headline">"${digest.headline}"</h3>
        <p className="arch-tldr">${Array.isArray(digest.tldr) ? digest.tldr.map(b => b.text).join(" · ") : digest.tldr}</p>
        <div className="arch-cats">
          ${digest.categories.map((c, i) => html`
            <span key=${i} className="arch-cat-chip" style=${{ background: accents[i].bg, color: accents[i].ink, borderColor: accents[i].deep }}>
              <span>${c.emoji}</span>
              <span>${c.stories.length}</span>
            </span>
          `)}
        </div>
      </div>
      <div className="arch-card-arrow" aria-hidden="true">
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
          <circle cx="16" cy="16" r="15" stroke="var(--ink)" strokeWidth="1.5" fill="none" />
          <path d="M11 16 H21 M17 12 L21 16 L17 20" stroke="var(--ink)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </button>
  `;
};

const ArchiveView = ({ onOpen, onOpenCat }) => {
  const [query, setQuery] = useState("");
  const { results: storyResults, loading, error } = useSearch(query);
  const isSearching = query.trim().length > 0;

  return html`
    <div className="archive">
      <header className="arch-hero">
        <div className="arch-hero-text">
          <div className="arch-hero-eyebrow">
            <${Sparkle} size=${14} color="var(--accent-lime-deep)" />
            <span>the archive</span>
          </div>
          <h1 className="arch-hero-title">
            Every <em className="hl-lime">brief,</em> in one place.
          </h1>
          <p className="arch-hero-sub">
            ${DIGESTS.length} issues · ${DIGESTS.reduce((n, d) => n + d.categories.reduce((m, c) => m + c.stories.length, 0), 0)} articles. Click any to read.
          </p>
        </div>
        <div className="arch-search">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.6" />
            <path d="M11 11 L14 14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            placeholder="search articles, sources, tags…"
            value=${query}
            onInput=${e => setQuery(e.target.value)}
          />
          ${query && html`
            <button className="arch-search-clear" onClick=${() => setQuery("")}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M3 3 L9 9 M9 3 L3 9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              </svg>
            </button>
          `}
        </div>
      </header>

      ${isSearching ? html`
        <${React.Fragment}>
          ${loading
            ? html`<div className="arch-loading"><span className="arch-loading-dot" /><span className="arch-loading-dot" /><span className="arch-loading-dot" /></div>`
            : error
            ? html`<p className="arch-results-label" style=${{ color: "var(--accent-pink-deep)" }}>${error}</p>`
            : html`
              <${React.Fragment}>
                <p className="arch-results-label">
                  ${(storyResults || []).length} article${(storyResults || []).length !== 1 ? "s" : ""} related to "${query}"
                </p>
                <div className="arch-list">
                  ${!storyResults || storyResults.length === 0
                    ? html`
                      <div className="arch-empty">
                        <div className="arch-empty-mark">∅</div>
                        <p>nothing related to "${query}" found. try a broader term?</p>
                      </div>
                    `
                    : storyResults.map((s, i) => html`
                      <${StorySearchResult} key=${s.digestIso + s.url} item=${s} query=${query.trim().toLowerCase()} index=${i} onOpenCat=${onOpenCat} />
                    `)
                  }
                </div>
              </${React.Fragment}>
            `
          }
        </${React.Fragment}>
      ` : html`
        <div className="arch-list">
          ${DIGESTS.map((d, i) => html`
            <${ArchiveCard} key=${d.iso} digest=${d} onOpen=${onOpen} isToday=${i === 0} index=${i} />
          `)}
        </div>
      `}
    </div>
  `;
};

// ─── SUBSCRIBE / FOOTER ────────────────────────────────────────────────────
const Subscribe = () => {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState("idle");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email) return;
    setStatus("loading");
    try {
      const res = await fetch("/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      setStatus(data.status === "already_subscribed" ? "duplicate" : "done");
    } catch {
      setStatus("error");
    }
  };

  return html`
    <section className="subscribe">
      <div className="subscribe-inner">
        <div className="subscribe-text">
          <h2 className="subscribe-title">
            wake up to <em className="hl-pink">smart</em>, not <em>scrolly</em>.
          </h2>
          <p className="subscribe-sub">one email · weekday mornings · the only AI digest you'll actually finish.</p>
        </div>
        <form className="subscribe-form" onSubmit=${handleSubmit}>
          ${status === "idle" || status === "loading" ? html`
            <${React.Fragment}>
              <input type="email" required placeholder="your@email" value=${email}
                     onInput=${e => setEmail(e.target.value)} disabled=${status === "loading"} />
              <button type="submit" disabled=${status === "loading"}>
                ${status === "loading" ? "…" : html`<${React.Fragment}>subscribe<${Sparkle} size=${14} color="currentColor" style=${{ marginLeft: 8, verticalAlign: "middle" }} /></${React.Fragment}>`}
              </button>
            </${React.Fragment}>
          ` : status === "done" ? html`
            <div className="subscribe-done">
              <${Sparkle} size=${18} color="var(--accent-pink-deep)" /> you're in. see you tomorrow morning.
            </div>
          ` : status === "duplicate" ? html`
            <div className="subscribe-done">
              <${Sparkle} size=${18} color="var(--accent-lime-deep)" /> already subscribed — see you tomorrow!
            </div>
          ` : html`
            <div className="subscribe-done">something went wrong. try again?</div>
          `}
        </form>
      </div>
    </section>
  `;
};

const Footer = () => html`
  <footer className="ftr">
    <div className="ftr-row">
      <span>by mandy, daily — built with curiosity</span>
      <span>made for technical founders & investors</span>
      <span>2026 · all caffeinated rights reserved</span>
    </div>
  </footer>
`;

// ─── HOME ──────────────────────────────────────────────────────────────────
const Home = ({ digest, isHistorical, onOpen, onArchive }) => html`
  <${React.Fragment}>
    <${Hero} digest=${digest} isHistorical=${isHistorical} onArchive=${onArchive} />
    <${CategoryGrid} digest=${digest} onOpen=${onOpen} />
    <${Subscribe} />
    <${Footer} />
  </${React.Fragment}>
`;

// ─── APP ───────────────────────────────────────────────────────────────────
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "palette": "candy",
  "displayFont": "instrument",
  "showSparkles": true
}/*EDITMODE-END*/;

const PALETTES = {
  candy:    { bg: "#FBF7F4", ink: "#1A1613", pink: { bg: "#FFD6E7", deep: "#E8369A", ink: "#5A0F36", soft: "#FFEEF5" }, lilac: { bg: "#E4D9FF", deep: "#7C4DFF", ink: "#2F1A6E", soft: "#F2EDFF" }, lime: { bg: "#DEFF8C", deep: "#6B9E00", ink: "#2A3A00", soft: "#F2FFD6" } },
  cyber:    { bg: "#0E0B14", ink: "#F4ECFF", pink: { bg: "#FF5FB1", deep: "#FF8FD0", ink: "#FFE4F2", soft: "#3A1126" }, lilac: { bg: "#9B7BFF", deep: "#C7B6FF", ink: "#EDE5FF", soft: "#1F1638" }, lime: { bg: "#C8FF3D", deep: "#E2FF7A", ink: "#1A2200", soft: "#1F2A05" } },
  pastel:   { bg: "#FFF9F2", ink: "#2A1F2E", pink: { bg: "#FFE0EC", deep: "#D9568D", ink: "#5A0F36", soft: "#FFF1F6" }, lilac: { bg: "#E8E0FF", deep: "#8B6BD9", ink: "#2F1A6E", soft: "#F4F0FF" }, lime: { bg: "#E8F4C0", deep: "#88A93E", ink: "#2A3A00", soft: "#F4FAE0" } },
  espresso: { bg: "#F5EDE2", ink: "#2A1A0E", pink: { bg: "#F4B8C4", deep: "#C9416A", ink: "#4F0F22", soft: "#FBE4EA" }, lilac: { bg: "#D4C4E4", deep: "#7553A8", ink: "#2A1648", soft: "#EDE4F4" }, lime: { bg: "#D4DC8C", deep: "#6B7A1A", ink: "#1F2800", soft: "#EAF0C8" } },
};

const FONTS = {
  instrument: { display: '"Instrument Serif", Georgia, serif', body: '"Geist", "Inter", system-ui, sans-serif', mono: '"JetBrains Mono", ui-monospace, monospace' },
  newsreader: { display: '"Newsreader", Georgia, serif', body: '"DM Sans", system-ui, sans-serif', mono: '"JetBrains Mono", ui-monospace, monospace' },
  serif4:     { display: '"Source Serif 4", Georgia, serif', body: '"Geist", system-ui, sans-serif', mono: '"JetBrains Mono", ui-monospace, monospace' },
};

function App() {
  const [route, setRoute] = useState({ view: "home", iso: TODAY.iso, catId: null });
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);

  const palette = PALETTES[tweaks.palette] || PALETTES.candy;
  const fonts = FONTS[tweaks.displayFont] || FONTS.instrument;

  const currentDigest = useMemo(
    () => DIGESTS.find(d => d.iso === route.iso) || TODAY,
    [route.iso]
  );
  const isHistorical = currentDigest.iso !== TODAY.iso;

  useEffect(() => {
    Object.assign(ACCENTS.pink,  palette.pink,  { glyph: "✿" });
    Object.assign(ACCENTS.lilac, palette.lilac, { glyph: "✦" });
    Object.assign(ACCENTS.lime,  palette.lime,  { glyph: "❋" });
  }, [tweaks.palette]);

  const cssVars = {
    "--bg": palette.bg, "--ink": palette.ink,
    "--accent-pink-bg": palette.pink.bg, "--accent-pink-deep": palette.pink.deep,
    "--accent-pink-ink": palette.pink.ink, "--accent-pink-soft": palette.pink.soft,
    "--accent-lilac-bg": palette.lilac.bg, "--accent-lilac-deep": palette.lilac.deep,
    "--accent-lilac-ink": palette.lilac.ink, "--accent-lilac-soft": palette.lilac.soft,
    "--accent-lime-bg": palette.lime.bg, "--accent-lime-deep": palette.lime.deep,
    "--accent-lime-ink": palette.lime.ink, "--accent-lime-soft": palette.lime.soft,
    "--font-display": fonts.display, "--font-body": fonts.body, "--font-mono": fonts.mono,
  };

  const goHome        = () => setRoute({ view: "home",    iso: TODAY.iso,  catId: null });
  const goArchive     = () => setRoute({ view: "archive", iso: route.iso,  catId: null });
  const openDigestDay = (iso)         => setRoute({ view: "home",    iso,            catId: null });
  const openDigestCat = (iso, catId)  => setRoute({ view: "digest",  iso,            catId });
  const openCategory  = (catId)       => setRoute({ view: "digest",  iso: route.iso, catId });
  const backToDayHome = ()            => setRoute({ view: "home",    iso: route.iso, catId: null });
  const pickCat       = (catId)       => setRoute({ view: "digest",  iso: route.iso, catId });

  const screenLabel =
    route.view === "archive" ? "Archive"
    : route.view === "digest" ? `${currentDigest.iso} – ${route.catId}`
    : `${currentDigest.iso} – home`;

  return html`
    <div className="app" style=${cssVars} data-sparkles=${tweaks.showSparkles ? "on" : "off"} data-screen-label=${screenLabel}>
      <${Header} onHome=${goHome} onArchive=${goArchive} route=${route} currentDigest=${currentDigest} />
      <main className="main">
        ${route.view === "archive" && html`<${ArchiveView} onOpen=${openDigestDay} onOpenCat=${openDigestCat} />`}
        ${route.view === "home"    && html`<${Home} digest=${currentDigest} isHistorical=${isHistorical} onOpen=${openCategory} onArchive=${goArchive} />`}
        ${route.view === "digest"  && html`<${DigestView} digest=${currentDigest} catId=${route.catId} onBackHome=${backToDayHome} onPickCat=${pickCat} />`}
      </main>

      <${TweaksPanel} title="Tweaks">
        <${TweakSection} title="Palette" subtitle="pick your vibe">
          <${TweakRadio}
            value=${tweaks.palette}
            onChange=${(v) => setTweak("palette", v)}
            options=${[
              { value: "candy",    label: "Candy" },
              { value: "cyber",    label: "Cyber" },
              { value: "pastel",   label: "Pastel" },
              { value: "espresso", label: "Espresso" },
            ]}
          />
        </${TweakSection}>
        <${TweakSection} title="Display font">
          <${TweakRadio}
            value=${tweaks.displayFont}
            onChange=${(v) => setTweak("displayFont", v)}
            options=${[
              { value: "instrument", label: "Instrument" },
              { value: "newsreader", label: "Newsreader" },
              { value: "serif4",     label: "Serif 4" },
            ]}
          />
        </${TweakSection}>
        <${TweakSection} title="Sparkles">
          <${TweakToggle} value=${tweaks.showSparkles} onChange=${(v) => setTweak("showSparkles", v)} label="Show sparkles & doodles" />
        </${TweakSection}>
      </${TweaksPanel}>
    </div>
  `;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${App} />`);
