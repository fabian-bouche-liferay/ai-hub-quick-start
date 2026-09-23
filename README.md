# AI Hub Quick Start series

A series of hands-on quick starts showing how to build with **Liferay AI
Hub** and how it integrates with **Liferay DXP**. Each quick start is a
self-contained folder: a written tutorial (`README.md`) plus a matching
screenshot-illustrated, standalone HTML version you can read offline or
share.

## The quick starts

1. **[AI Hub - Quickstart 1 - HTTP Requests](AI%20Hub%20-%20Quickstart%201%20-%20HTTP%20Requests/README.md)**
   — calling Liferay Headless APIs from an AI Hub agent's HTTP Request
   node: input/output variables, OAuth2 scopes, and how to bring
   third-party data in through an `objectEntryManager` client extension
   proxy.
2. **[AI Hub - Quickstart 2 - RAG](AI%20Hub%20-%20Quickstart%202%20-%20RAG/README.md)**
   — building a RAG chatbot: Search Workers, Search Blueprints, the native
   Supervisor, and an Answer Builder grounded in a real CMS knowledge base.
3. **[AI Hub - Quickstart 3 - Kaleo Workflow](AI%20Hub%20-%20Quickstart%203%20-%20Kaleo%20Workflow/README.md)**
   — triggering an AI Hub agent synchronously from a DXP Kaleo workflow,
   exchanging data through `workflowContext`, and the security/identity
   implications of doing so.

Each folder's `README.md` ends with a "Recommendations" section and an
"Other business use cases for this pattern" section listing further ideas
that reuse the same mechanism.

## Repository layout

```
ai-hub-quick-start/
├── build_quickstart_html.py          # shared HTML generator (see below)
├── AI Hub - Quickstart 1 - HTTP Requests/
│   ├── README.md
│   ├── HTTP Requests in AI Hub.html  # generated, do not edit by hand
│   └── images/
├── AI Hub - Quickstart 2 - RAG/
│   ├── README.md
│   ├── AI Hub RAG Quickstart.html    # generated, do not edit by hand
│   └── images/
└── AI Hub - Quickstart 3 - Kaleo Workflow/
    ├── README.md
    ├── AI Hub Kaleo Workflow Quickstart.html  # generated, do not edit by hand
    └── images/
```

The source of truth for every quick start is its `README.md`. The `.html`
file next to it is a build artifact — always regenerate it after editing
the Markdown, never hand-edit it.

## `build_quickstart_html.py`

A single script, shared by all three quick starts, that converts a quick
start's `README.md` into a standalone HTML page styled after
[learn.liferay.com](https://learn.liferay.com)'s own visual language
(same color tokens, fonts, and admonition style as a real Liferay Learn
course page such as
[course-environment-setup-22](https://learn.liferay.com/course/course-environment-setup-22)).

It adds two things a plain Markdown-to-HTML render doesn't have:

- **A fixed left sidebar table of contents**, built from the document's
  own headings, so the generated page is navigable like a course page
  rather than a single long scroll.
- **A "Copy" icon button** in the top-right corner of every fenced code
  block and every blockquote (used for callouts and multi-line prompts),
  so a reader can copy a command or a prompt in one click without
  selecting text by hand.

It also fixes a real limitation of the `markdown` library: a fenced code
block written *inside* a blockquote (`> ` followed by a line starting with
` ``` `) isn't picked up by the library's fence preprocessor, which only
matches fences starting at column 0. The script's `hoist_fenced_blockquotes()`
step finds these, dedents and renders them separately, then splices the
result back in — so nested code blocks inside asides/callouts render
correctly instead of as broken, duplicated boxes.

### Usage

Run it from inside the quick start folder whose `README.md` you want to
build, not from the repo root:

```bash
cd "AI Hub - Quickstart 2 - RAG"
python ../build_quickstart_html.py --output "AI Hub RAG Quickstart.html"

cd "AI Hub - Quickstart 1 - HTTP Requests"
python ../build_quickstart_html.py --output "HTTP Requests in AI Hub.html"

cd "AI Hub - Quickstart 3 - Kaleo Workflow"
python ../build_quickstart_html.py --output "AI Hub Kaleo Workflow Quickstart.html"
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--input` | `README.md` in the current directory | Source Markdown file |
| `--output` | `--input` with a `.html` extension | Destination HTML file |

Requires `markdown` and `beautifulsoup4`:

```bash
pip install markdown beautifulsoup4
```

### When to re-run it

Any time a quick start's `README.md` changes — new section, edited text,
new screenshot — re-run the script for that folder and commit the
regenerated `.html` alongside the Markdown change, so the two never drift
apart.
