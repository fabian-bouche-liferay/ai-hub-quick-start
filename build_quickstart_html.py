#!/usr/bin/env python3
"""
Build a standalone, Liferay-flavored HTML version of an AI Hub quick start's
README.md (visual language matching learn.liferay.com's own design tokens):
a fixed left sidebar acting as the table of contents, and a small "Copy"
icon button in the top-right corner of every prompt block (fenced code
block or blockquote) so it can be copied to the clipboard in one click.

Shared across every "AI Hub - Quickstart N - ..." folder in this directory
— run it from inside the quick start's own folder:

    cd "AI Hub - Quickstart 2 - RAG"
    python ../build_quickstart_html.py --output "AI Hub RAG Quickstart.html"

    cd "AI Hub - Quickstart 1 - HTTP Requests"
    python ../build_quickstart_html.py --output "HTTP Requests in AI Hub.html"

Defaults to reading README.md in the current directory; --output defaults
to the same name with a .html extension if not given.

Requires: markdown, beautifulsoup4
    pip install markdown beautifulsoup4
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

try:
    import markdown
    from bs4 import BeautifulSoup, Tag
except ImportError as exc:  # pragma: no cover - environment guard
    sys.exit(
        f"Missing dependency: {exc}\n"
        "Install with: pip install markdown beautifulsoup4"
    )

# Substrings (already lowercase) used to classify a lead-in bold label such
# as "**Prerequisite.**" or "**What this tests.**" into a callout style.
# Checked in this order — first match wins.
WARN_MARKERS = ("watch-point", "watch out", "do not")
TEST_MARKERS = ("what this tests", "expected answer", "how to test")
INFO_MARKERS = ("prerequisite", "scope note", "forward-link", "note")


# --------------------------------------------------------------------------
# Markdown -> HTML
# --------------------------------------------------------------------------

# Matches a top-level (column-0) ordered/unordered list item marker, e.g.
# "1. Foo", "1) Foo", "- Foo", "* Foo", "+ Foo".
_TOP_LEVEL_LIST_ITEM_RE = re.compile(r"^(?:\d+[.)]|[-*+])\s+\S")
_FENCE_RE = re.compile(r"^\s*```")


def hoist_fenced_blockquotes(md_text: str) -> str:
    """A blockquote whose content includes one or more fenced code blocks
    (a documentation aside mixing prose with short copy-paste examples) is
    valid CommonMark/GFM and renders as a single quoted unit on GitHub.

    Python-Markdown's fenced-code preprocessor, however, only recognizes
    a fence (```) anchored at the very start of a line. A fence written
    inside a blockquote — every line prefixed with "> " — never matches
    it, so it falls through to ordinary paragraph/inline parsing instead:
    the opening "```lang" line, the code lines and the closing "```" get
    merged into one broken inline <code> span with the literal language
    tag and embedded newlines, rendered as misaligned boxes.

    Find each contiguous run of "> "-prefixed lines that contains a
    fence, strip the prefix from every line in that run, and render the
    dedented Markdown with its own Markdown instance (which does
    understand fences at column 0). The result is spliced back in as a
    single, already-rendered `<blockquote class="aside">` — a raw HTML
    block, which the outer Markdown pass leaves untouched — reproducing
    GitHub's own single-quote rendering instead of Python-Markdown's
    fragmented one. Ordinary text-only blockquotes elsewhere in the
    document (a quoted test question, a one-line callout) contain no
    fence and are left alone, so normal blockquote handling still
    applies to them.
    """
    lines = md_text.split("\n")
    out: list[str] = []
    i, n = 0, len(lines)

    while i < n:
        line = lines[i]
        if not line.startswith(">"):
            out.append(line)
            i += 1
            continue

        j = i
        block_lines: list[str] = []
        while j < n and lines[j].startswith(">"):
            block_lines.append(lines[j])
            j += 1
        i = j

        if "```" not in "\n".join(block_lines):
            out.extend(block_lines)
            continue

        dedented = "\n".join(re.sub(r"^>\s?", "", l) for l in block_lines)
        # Include "toc" so any heading inside the aside still gets the same
        # kind of `id` the outer document's headings get (needed for the
        # sidebar TOC and heading anchors to find it).
        inner_md = markdown.Markdown(
            extensions=["fenced_code", "sane_lists", "toc"],
            extension_configs={"toc": {"permalink": False}},
            output_format="html5",
        )
        inner_html = inner_md.convert(dedented)
        out.append(f'<blockquote class="aside">\n{inner_html}\n</blockquote>')

    return "\n".join(out)


def ensure_blank_line_before_lists(md_text: str) -> str:
    """A quick start's own convention occasionally places a lead-in line
    immediately followed by a numbered/bulleted list, with no blank line
    between them. Python-Markdown (unlike full CommonMark) does not treat
    that as a new list interrupting the paragraph — it folds every list
    line into the preceding text as a literal, unrendered "1. ..." string
    instead of a real <ol>/<li>. The same gap appears again wherever a
    list item's own indented continuation is immediately followed by the
    next top-level item with no blank line.

    Insert the blank line Markdown actually requires before every top-level
    list item that doesn't already have one, skipping fenced code blocks
    (where "1. ..." is meant to render as literal text) and skipping the
    transition between two consecutive top-level items (already valid,
    adding a blank there would just be visual noise).
    """
    lines = md_text.split("\n")
    out: list[str] = []
    in_fence = False

    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue

        if not in_fence and _TOP_LEVEL_LIST_ITEM_RE.match(line):
            prev = out[-1] if out else ""
            if prev.strip() and not _TOP_LEVEL_LIST_ITEM_RE.match(prev):
                out.append("")

        out.append(line)

    return "\n".join(out)


def convert_markdown(md_text: str) -> tuple[BeautifulSoup, str]:
    md_text = hoist_fenced_blockquotes(md_text)
    md_text = ensure_blank_line_before_lists(md_text)
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "sane_lists", "toc"],
        extension_configs={
            "toc": {"permalink": False, "toc_depth": "2-4"},
        },
        output_format="html5",
    )
    body_html = md.convert(md_text)
    soup = BeautifulSoup(body_html, "html.parser")

    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else "AI Hub Quickstart"

    return soup, title


# --------------------------------------------------------------------------
# Post-processing
# --------------------------------------------------------------------------

def build_toc_tree(soup: BeautifulSoup) -> list[dict]:
    headings = soup.select("h2[id], h3[id], h4[id]")
    root: list[dict] = []
    stack: list[tuple[int, list[dict]]] = []

    for h in headings:
        level = int(h.name[1])
        node = {
            "id": h["id"],
            "text": h.get_text(" ", strip=True),
            "level": level,
            "children": [],
        }
        while stack and stack[-1][0] >= level:
            stack.pop()
        (stack[-1][1] if stack else root).append(node)
        stack.append((level, node["children"]))

    return root


def render_toc(nodes: list[dict]) -> str:
    if not nodes:
        return ""
    items = []
    for node in nodes:
        children_html = render_toc(node["children"])
        items.append(
            f'<li class="toc-level-{node["level"]}">'
            f'<a href="#{node["id"]}">{html.escape(node["text"])}</a>'
            f"{children_html}</li>"
        )
    return "<ul>" + "".join(items) + "</ul>"


def add_heading_anchors(soup: BeautifulSoup) -> None:
    for level in ("h2", "h3", "h4"):
        for heading in soup.find_all(level):
            heading_id = heading.get("id")
            if not heading_id:
                continue
            anchor = soup.new_tag(
                "a",
                href=f"#{heading_id}",
                **{"class": "heading-anchor", "aria-hidden": "true", "tabindex": "-1"},
            )
            anchor.string = "#"
            heading.append(anchor)


def wrap_tables(soup: BeautifulSoup) -> None:
    for table in soup.find_all("table"):
        wrapper = soup.new_tag("div", **{"class": "table-wrap"})
        table.wrap(wrapper)


COPY_ICON_SVG = (
    '<svg class="icon-copy" viewBox="0 0 24 24" width="16" height="16" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="9" y="9" width="13" height="13" rx="2"></rect>'
    '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>'
    "</svg>"
)
CHECK_ICON_SVG = (
    '<svg class="icon-check" viewBox="0 0 24 24" width="16" height="16" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="20 6 9 17 4 12"></polyline>'
    "</svg>"
)


def wrap_copyable_blocks(soup: BeautifulSoup) -> None:
    """Every fenced code block, and every short text-only blockquote, in
    this document is a ready-to-paste prompt, sample value or command.
    Wrap each in a frame with a small copy button pinned to its top-right
    corner — a dark "code" frame for <pre>, matching learn.liferay.com's
    own `pre[class*="language-"]` treatment, and a light "quote" frame for
    a plain blockquote, matching its lightweight left-rule quote style. A
    blockquote used as a documentation aside instead (prose mixed with
    nested fenced-code examples, marked "aside" by
    hoist_fenced_blockquotes) is not a single pastable unit, so it keeps
    its plain quoted styling and only its nested code blocks get copy
    buttons.
    """
    for block in soup.find_all(["pre", "blockquote"]):
        if block.name == "blockquote" and "aside" in (block.get("class") or []):
            continue
        kind = "code" if block.name == "pre" else "quote"
        wrapper = soup.new_tag("div", **{"class": f"copy-frame copy-frame-{kind}"})
        block.wrap(wrapper)
        button = soup.new_tag(
            "button",
            type="button",
            **{"class": "copy-btn", "aria-label": "Copy to clipboard"},
        )
        button.append(BeautifulSoup(COPY_ICON_SVG, "html.parser"))
        button.append(BeautifulSoup(CHECK_ICON_SVG, "html.parser"))
        wrapper.insert(0, button)


def classify_label_paragraph(paragraph: Tag) -> str | None:
    """Return an admonition class — using learn.liferay.com's own "adm-*"
    naming (adm-warning, adm-note, adm-important) — for a paragraph that
    opens with a bold label such as '**What this tests**' or '**Expected
    answer**', or with a ⚠️ warning marker."""
    text = paragraph.get_text(" ", strip=True)
    prefix = text[:8]
    if "⚠" in prefix:
        return "adm-warning"

    if not paragraph.contents:
        return None
    first = paragraph.contents[0]
    if not isinstance(first, Tag) or first.name != "strong":
        return None

    raw_label = first.get_text(" ", strip=True)
    label = raw_label.lower()

    if "⚠" in raw_label or any(marker in label for marker in WARN_MARKERS):
        return "adm-warning"
    if any(marker in label for marker in TEST_MARKERS):
        return "adm-note"
    if label.startswith("note") or any(marker in label for marker in INFO_MARKERS):
        return "adm-important"
    return None


def apply_callouts(soup: BeautifulSoup) -> None:
    for paragraph in soup.find_all("p"):
        css_class = classify_label_paragraph(paragraph)
        if css_class:
            existing = paragraph.get("class", [])
            paragraph["class"] = existing + ["adm-block", css_class]


# --------------------------------------------------------------------------
# Page assembly
# --------------------------------------------------------------------------

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Code+Pro:wght@400;600&family=Source+Sans+3:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
{css}
</style>
</head>
<body>
<header class="topbar">
  <button class="menu-toggle" type="button" aria-label="Toggle table of contents">&#9776;</button>
  <div class="logo"><span class="dot"></span>Liferay Learn</div>
  <div class="doc-title">{title}</div>
  <div class="spacer"></div>
</header>
<div class="layout">
  <nav class="sidebar" aria-label="Table of contents">
    <input class="toc-filter" type="search" placeholder="Filter this guide&hellip;" aria-label="Filter table of contents">
    <div class="toc">{toc}</div>
  </nav>
  <div class="content-wrap">
    <main class="doc-content">
{content}
    </main>
  </div>
</div>
<button class="back-to-top" type="button" aria-label="Back to top">&#8593;</button>
<script>
{js}
</script>
</body>
</html>
"""

CSS = """
:root {
  /* Design tokens pulled from learn.liferay.com's own stylesheet
     (https://liferaylearnglobalcss-exte5a2learn-extprd.lfr.cloud/global.css)
     — the CSS custom-property fallback values there, e.g.
     var(--color-brand-primary, #0b5fff), are learn.liferay.com's real
     palette, not an approximation of it. */
  --lf-brand: #0b5fff;
  --lf-brand-hover: #0053f0;
  --lf-brand-active: #004ad7;

  --lf-neutral-0: #ffffff;
  --lf-neutral-1: #f7f7f8;
  --lf-neutral-2: #e2e2e4;
  --lf-neutral-4: #b1b2b9;
  --lf-neutral-6: #82828c;
  --lf-neutral-8: #54555f;
  --lf-neutral-9: #33343d;
  --lf-neutral-10: #282934;

  --lf-active-bg: #e6edfb;
  --lf-hover-bg: #edf3fe;

  --lf-warning-bg: #f7eae0;   --lf-warning-text: #944000;
  --lf-success-bg: #e9f5e8;   --lf-success-text: #3b892f;
  --lf-info-bg: #e6ebf5;      --lf-info-text: #25488a;

  --lf-font-sans: 'Source Sans 3', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
  --lf-font-mono: 'Source Code Pro', Consolas, Menlo, "Liberation Mono", monospace;
  --lf-radius: 0.5rem;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font-family: var(--lf-font-sans);
  color: var(--lf-neutral-8);
  background: var(--lf-neutral-0);
  line-height: 1.6;
}

/* Top bar */
.topbar {
  position: fixed; top: 0; left: 0; right: 0; height: 60px;
  background: var(--lf-neutral-0); color: var(--lf-neutral-10);
  display: flex; align-items: center; gap: .75rem; padding: 0 1rem;
  z-index: 50; border-bottom: 1px solid var(--lf-neutral-2);
}
.topbar .logo { font-weight: 700; font-size: 1.05rem; display: flex; align-items: center; gap: .45rem; letter-spacing: .01em; color: var(--lf-neutral-10); }
.topbar .logo .dot { width: .55rem; height: .55rem; border-radius: 50%; background: var(--lf-brand); }
.topbar .doc-title {
  color: var(--lf-neutral-6); font-size: .85rem; border-left: 1px solid var(--lf-neutral-2);
  padding-left: .75rem; margin-left: .1rem; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; max-width: 55vw;
}
.topbar .spacer { flex: 1; }
.menu-toggle {
  display: none; background: transparent; border: 1px solid var(--lf-neutral-2);
  color: var(--lf-neutral-10); border-radius: 6px; padding: .3rem .55rem; font-size: 1rem; cursor: pointer;
}

/* Layout */
.layout { display: flex; padding-top: 60px; min-height: 100vh; }
.sidebar {
  position: fixed; top: 60px; bottom: 0; left: 0; width: 300px;
  overflow-y: auto; background: var(--lf-neutral-1); border-right: 1px solid var(--lf-neutral-2);
  padding: 1rem .85rem 2.5rem; z-index: 40;
}
.toc-filter {
  width: 100%; padding: .5rem .65rem; border: 1px solid var(--lf-neutral-2);
  border-radius: 6px; font-size: .85rem; margin-bottom: .85rem; background: var(--lf-neutral-0);
  font-family: inherit; color: var(--lf-neutral-10);
}
.toc ul { list-style: none; margin: 0; padding-left: 1rem; }
.toc > div > ul, .toc > ul { padding-left: 0; }
.toc a {
  display: block; padding: .32rem .55rem .32rem .65rem; color: var(--lf-neutral-8);
  text-decoration: none; font-size: .86rem; line-height: 1.35; border-left: 2px solid transparent;
}
.toc li.toc-level-2 > a { font-weight: 700; color: var(--lf-neutral-10); font-size: .9rem; margin-top: .4rem; }
.toc li.toc-level-3 > a { font-weight: 500; }
.toc li.toc-level-4 > a { font-size: .8rem; color: var(--lf-neutral-6); }
.toc a:hover { color: var(--lf-neutral-10); background: var(--lf-hover-bg); }
.toc a.active { background: var(--lf-active-bg); border-left-color: var(--lf-brand); color: var(--lf-brand-active); font-weight: 700; }

.content-wrap { margin-left: 300px; flex: 1; display: flex; justify-content: center; padding: 2.5rem 2rem 7rem; }
.doc-content { max-width: 840px; width: 100%; }

/* Headings — learn.liferay.com's article headings are plain, undecorated:
   no colored rule under h1, just weight and the neutral-10 ink. */
.doc-content h1 { font-size: 2rem; line-height: 1.25; margin: 0 0 1rem; color: var(--lf-neutral-10); font-weight: 700; }
.doc-content h1 + p { font-size: 1.1rem; color: var(--lf-neutral-6); margin-top: 0; }
.doc-content h2 {
  font-size: 1.5rem; margin: 2.75rem 0 1rem; padding-top: .75rem;
  border-top: 1px solid var(--lf-neutral-2); color: var(--lf-neutral-10); font-weight: 700; scroll-margin-top: 78px;
}
.doc-content h2:first-of-type { border-top: 0; margin-top: 1.75rem; }
.doc-content h3 { font-size: 1.2rem; margin: 2rem 0 .75rem; color: var(--lf-neutral-10); font-weight: 600; scroll-margin-top: 78px; }
.doc-content h4 { font-size: 1rem; margin: 1.5rem 0 .6rem; color: var(--lf-neutral-10); font-weight: 600; scroll-margin-top: 78px; }
.heading-anchor { margin-left: .45rem; opacity: 0; text-decoration: none; color: var(--lf-brand); font-weight: 400; font-size: .8em; }
h2:hover .heading-anchor, h3:hover .heading-anchor, h4:hover .heading-anchor { opacity: 1; }

/* Body text — learn.liferay.com renders article paragraphs in neutral-8,
   reserving neutral-10 for headings and emphasis. */
.doc-content p { margin: .85rem 0; color: var(--lf-neutral-8); }
.doc-content strong { color: var(--lf-neutral-10); font-weight: 600; }
.doc-content ul, .doc-content ol { padding-left: 1.4rem; }
.doc-content li { margin: .3rem 0; color: var(--lf-neutral-8); }
.doc-content hr { border: 0; border-top: 1px solid var(--lf-neutral-2); margin: 2.75rem 0; }
.doc-content a { color: var(--lf-brand); }
.doc-content a:hover { color: var(--lf-brand-active); text-decoration: underline; }
.doc-content code {
  font-family: var(--lf-font-mono); background: var(--lf-neutral-2); color: var(--lf-neutral-10);
  padding: .125rem .4rem; border-radius: 4px; font-size: .88em;
}
em { color: inherit; }
.doc-content img {
  max-width: 100%; height: auto; display: block; margin: 1.1rem 0;
  border: 1px solid var(--lf-neutral-2); border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,.08);
}

/* Admonitions — learn.liferay.com's own "adm-*" callout vocabulary
   (adm-warning / adm-note / adm-important), same background/text pairs. */
.doc-content p.adm-block { padding: .75rem 1rem; border-radius: var(--lf-radius); margin: 1.1rem 0; }
.doc-content p.adm-warning { background: var(--lf-warning-bg); color: var(--lf-warning-text); }
.doc-content p.adm-note { background: var(--lf-success-bg); color: var(--lf-success-text); }
.doc-content p.adm-important { background: var(--lf-info-bg); color: var(--lf-info-text); }
.doc-content p.adm-block strong:first-child { color: inherit; }

/* Blockquotes — learn.liferay.com's lightweight quoted style: a thin blue
   rule and no filled background, used both for a short quoted prompt and
   for a documentation aside that mixes prose with nested code examples. */
.doc-content blockquote {
  border-left: 2px solid var(--lf-brand); color: var(--lf-neutral-8);
  font-size: 1.125rem; font-weight: 300; line-height: 1.5;
  margin: 1.5rem 0; padding-left: 1.5rem;
}
.doc-content blockquote p { margin: .6rem 0; }
.doc-content blockquote code { background: var(--lf-neutral-2); }
.doc-content blockquote.aside { font-size: 1rem; font-weight: 400; }
.doc-content blockquote.aside h3 { font-size: 1.1rem; margin-top: 0; }
.doc-content blockquote.aside .copy-frame-code { margin: 1rem 0; }

/* Prompt / copy frames: a dark "code" frame for fenced code (matching
   learn.liferay.com's own pre[class*="language-"] surface) and a light
   "quote" frame that leaves the blockquote's own thin-rule style intact. */
.copy-frame { position: relative; margin: 1rem 0 1.6rem; }
.copy-frame-code { border-radius: var(--lf-radius); overflow: hidden; background: var(--lf-neutral-9); }
.copy-frame-code pre {
  margin: 0; padding: 1em 3.4rem 1em 1.25rem; color: var(--lf-neutral-0);
  background: transparent; border: 0; font-family: var(--lf-font-mono);
  font-size: .9rem; line-height: 1.6; white-space: pre-wrap; word-break: break-word;
}
.copy-frame-code pre code { background: transparent; color: inherit; padding: 0; border-radius: 0; }
.copy-frame-quote blockquote { margin: 0; padding-right: 3.2rem; }

.copy-btn {
  position: absolute; top: .6rem; right: .6rem; z-index: 2;
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; padding: 0; border: 0; border-radius: 6px; background: transparent;
  cursor: pointer; transition: background .15s ease, color .15s ease;
}
.copy-btn .icon-check { display: none; }
.copy-btn.copied .icon-copy { display: none; }
.copy-btn.copied .icon-check { display: inline; }
.copy-frame-code .copy-btn { color: rgba(255,255,255,.75); }
.copy-frame-code .copy-btn:hover { background: rgba(255,255,255,.12); color: var(--lf-neutral-0); }
.copy-frame-quote .copy-btn { top: .4rem; color: var(--lf-neutral-6); }
.copy-frame-quote .copy-btn:hover { background: var(--lf-hover-bg); color: var(--lf-brand-active); }
.copy-btn.copied { color: var(--lf-success-text) !important; }

/* Tables */
.table-wrap { overflow-x: auto; margin: 1.4rem 0; border: 1px solid var(--lf-neutral-2); border-radius: var(--lf-radius); }
.doc-content table { border-collapse: collapse; width: 100%; font-size: .88rem; }
.doc-content th, .doc-content td { padding: .55rem .75rem; border-bottom: 1px solid var(--lf-neutral-2); text-align: left; vertical-align: top; color: var(--lf-neutral-8); }
.doc-content thead th { background: var(--lf-neutral-1); color: var(--lf-neutral-10); font-weight: 600; position: sticky; top: 0; }
.doc-content tbody tr:nth-child(even) { background: var(--lf-neutral-1); }

/* Back to top */
.back-to-top {
  position: fixed; right: 1.5rem; bottom: 1.5rem; width: 44px; height: 44px; border-radius: 50%;
  background: var(--lf-brand); color: #fff; border: 0; display: flex; align-items: center;
  justify-content: center; cursor: pointer; box-shadow: 0 2px 10px rgba(11,95,255,.35);
  opacity: 0; pointer-events: none; transition: opacity .2s ease, transform .2s ease, background .15s ease; z-index: 45; font-size: 1.1rem;
}
.back-to-top:hover { background: var(--lf-brand-active); transform: translateY(-2px); }
.back-to-top.visible { opacity: 1; pointer-events: auto; }

/* Responsive */
@media (max-width: 900px) {
  .menu-toggle { display: inline-flex; align-items: center; justify-content: center; }
  .sidebar { transform: translateX(-100%); transition: transform .2s ease; box-shadow: 2px 0 14px rgba(0,0,0,.12); }
  body.sidebar-open .sidebar { transform: translateX(0); }
  .content-wrap { margin-left: 0; padding: 2rem 1.15rem 5rem; }
  body.sidebar-open::after {
    content: ""; position: fixed; inset: 60px 0 0 0; background: rgba(40,41,52,.35); z-index: 39;
  }
}

@media print {
  .topbar, .sidebar, .copy-btn, .menu-toggle, .back-to-top { display: none !important; }
  .content-wrap { margin-left: 0; padding: 0; }
  .copy-frame-code { border: 1px solid #999; }
  .copy-frame-code pre { color: #111; }
  :root { --lf-neutral-9: #f4f4f4; }
}
"""

JS = """
(function () {
  // Copy-to-clipboard for every prompt frame.
  document.addEventListener("click", function (event) {
    var btn = event.target.closest(".copy-btn");
    if (!btn) return;
    var frame = btn.closest(".copy-frame");
    var target = frame.querySelector("pre, blockquote");
    var text = target ? target.innerText : "";

    function feedback() {
      btn.classList.add("copied");
      setTimeout(function () {
        btn.classList.remove("copied");
      }, 1500);
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(feedback).catch(function () {
        fallbackCopy(text, feedback);
      });
    } else {
      fallbackCopy(text, feedback);
    }
  });

  function fallbackCopy(text, done) {
    var textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    try { document.execCommand("copy"); } catch (err) { /* no-op */ }
    document.body.removeChild(textarea);
    done();
  }

  // Mobile sidebar toggle.
  var menuToggle = document.querySelector(".menu-toggle");
  if (menuToggle) {
    menuToggle.addEventListener("click", function () {
      document.body.classList.toggle("sidebar-open");
    });
  }
  document.querySelectorAll(".toc a").forEach(function (link) {
    link.addEventListener("click", function () {
      document.body.classList.remove("sidebar-open");
    });
  });

  // Table-of-contents filter (recursively keeps a branch visible if any
  // descendant entry matches).
  var filterInput = document.querySelector(".toc-filter");
  if (filterInput) {
    filterInput.addEventListener("input", function () {
      var query = filterInput.value.trim().toLowerCase();
      document.querySelectorAll(".toc > ul > li").forEach(function (li) {
        filterItem(li, query);
      });
    });
  }

  function filterItem(li, query) {
    var link = li.querySelector(":scope > a");
    var text = link ? link.textContent.toLowerCase() : "";
    var childList = li.querySelector(":scope > ul");
    var childMatch = false;
    if (childList) {
      childList.querySelectorAll(":scope > li").forEach(function (childLi) {
        if (filterItem(childLi, query)) childMatch = true;
      });
    }
    var selfMatch = !query || text.indexOf(query) !== -1;
    var show = selfMatch || childMatch;
    li.style.display = show ? "" : "none";
    return show;
  }

  // Scroll-spy: highlight the current section in the sidebar.
  var headings = document.querySelectorAll(".doc-content h2[id], .doc-content h3[id], .doc-content h4[id]");
  var linkMap = {};
  document.querySelectorAll(".toc a").forEach(function (a) {
    linkMap[a.getAttribute("href").slice(1)] = a;
  });

  if ("IntersectionObserver" in window && headings.length) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var link = linkMap[entry.target.id];
        if (!link || !entry.isIntersecting) return;
        document.querySelectorAll(".toc a.active").forEach(function (a) { a.classList.remove("active"); });
        link.classList.add("active");
      });
    }, { rootMargin: "0px 0px -72% 0px", threshold: 0 });
    headings.forEach(function (h) { observer.observe(h); });
  }

  // Back-to-top button.
  var backToTop = document.querySelector(".back-to-top");
  if (backToTop) {
    window.addEventListener("scroll", function () {
      backToTop.classList.toggle("visible", window.scrollY > 600);
    }, { passive: true });
    backToTop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }
})();
"""


def build_page(md_text: str) -> str:
    soup, title = convert_markdown(md_text)

    toc_tree = build_toc_tree(soup)
    toc_html = render_toc(toc_tree)

    add_heading_anchors(soup)
    wrap_tables(soup)
    apply_callouts(soup)
    wrap_copyable_blocks(soup)

    content_html = str(soup)

    return PAGE_TEMPLATE.format(
        title=html.escape(title),
        toc=toc_html,
        content=content_html,
        css=CSS,
        js=JS,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--input", type=Path, default=Path("README.md"),
        help="Source Markdown file (default: README.md in the current directory)",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Destination HTML file (default: --input with a .html extension)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"Input file not found: {args.input}")

    output = args.output if args.output is not None else args.input.with_suffix(".html")

    md_text = args.input.read_text(encoding="utf-8")
    page = build_page(md_text)

    output.write_text(page, encoding="utf-8")
    print(f"Wrote {output} ({len(page):,} bytes)")


if __name__ == "__main__":
    main()
