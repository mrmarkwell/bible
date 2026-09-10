# Bible Engine

> **Sovereign Offline-First Scripture Platform, Whole-Bible Semantic Knowledge Graph, Dense Vector Similarity Engine & Sacred-Modern Visual Reader**  
> *Zero External Dependencies • Zero npm Packages • Zero pip Requirements • Dependabot-Immune*

---

## 🌟 Overview

**Bible Engine** is an offline-first, locally hosted platform for scripture reading, parallel multi-translation comparison, full-text search, dense vector similarity, whole-bible semantic exegesis, typological graph navigation, 4K visual presentation slide generation, and grounded AI theological synthesis.

Designed for longevity, speed, and sovereign personal study, Bible Engine operates under an uncompromising architectural mandate: **Zero External Dependencies** ([ADR-003](DECISIONS.md#adr-003-zero-dependency-architecture-for-zero-maintenance--dependabot-immunity)). The entire engine—database management, FTS5 full-text search, 768-dimensional vector cosine similarity, 2D dimensionality reduction, terminal typography, 4K slide layout, HTTP web server, REST API, and interactive UI visualizers—is built exclusively with the **Python 3 standard library** and **vanilla HTML/CSS/JS**.

### ⚡ Key Capabilities at a Glance
- **Scripture Canon & Translations**: 62,205 verses stored offline in SQLite (`data/bible.db`) across both World English Bible (**WEB**) and King James Version (**KJV**), with live modern English Standard Version (**ESV**) API retrieval, 500-verse in-memory LRU caching, and transparent offline fallback.
- **Instant Cold-Start Bootstrapping**: Initializes the SQLite database, compiles 62,000+ verses, builds FTS5 indexes, seeds 1,333 pericopes, 343,000+ cross-reference edges, and configures git hooks in `<0.5s` via `./bible init`.
- **Dense Vector Database & Semantic Similarity**: 1,333 normalized 768-dimensional pericope vector embeddings with signed `int8` quantization (<25MB in SQLite), 31,103 verse micro-anchors for parent-document retrieval, pure standard library cosine similarity (<15ms across whole Bible), and FastMap/PCA 2D projection ([ADR-051](DECISIONS.md#adr-051-zero-dependency-vector-similarity-engine-int8-quantization--sqlite-blob-storage), [ADR-114](DECISIONS.md#adr-114-whole-bible-verse-micro-anchor-embedding-synchronization--parent-document-retrieval-architecture)).
- **Tri-Modal Hybrid Scripture RAG**: Combines dense vector similarity, SQLite FTS5 BM25 lexical matching, and typological arc graph traversal fused via weighted Reciprocal Rank Fusion (RRF), with 4D theological facet pre-filtering (Testament, Genre, Storyline Epoch, Theological Locus) and TGC confessional guardrails ([ADR-102](DECISIONS.md#adr-102-tri-modal-hybrid-scripture-rag-reciprocal-rank-fusion-rrf--theological-facet-filtering-architecture)).
- **Canonical Biblical Character Persona Studio**: Conversational dialogue engine modeling 19 canonical biblical figures (Paul, Moses, David, Peter, John, Isaiah, Mary, etc.) using biblical citations, historical vocabulary, and Christ-centered orientation with real-time SSE streaming ([ADR-063](DECISIONS.md#adr-063-canonical-biblical-character-dialogue-engine-tgc-theological-guardrails-and-persona-studio)).
- **4K / 1080p Visual Verse Slide Generator**: Renders presentation-grade typography for TV displays and Google Photos screensavers with dynamic font-size clamping, balanced word wrapping, optical vertical centering (~45%), TV safe margins, OLED pitch-black theme (`#000000`), multi-slide pagination, and batch export ([ADR-038](DECISIONS.md#adr-038-visual-verse-slide-generator-for-tv-screensavers-and-sacred-presentation), [ADR-044](DECISIONS.md#adr-044-batch-slide-generator-export-engine-for-google-photos-tv-screensaver-albums)).
- **Sacred-Modern Web UI & Visualizations**: Obsidian Dark Mode (`#0D0E11`) and illuminated gold (`#D4AF37`) split-screen reader, Redemptive Ribbon 66-book heatmap, interactive 2D semantic scatter map atlas, pure SVG typological arc graph, and character dialogue studio.
- **Sovereign Developer & Operational Tooling**: High-performance parallel test runner (1,062 tests in <10s), AST-based static linter, performance benchmark suite, zero-dependency code coverage, CI/CD sentry, and 9-point system health doctor.

---

## 🚀 30-Second Quickstart

### 1. Initialize the Environment
```bash
# Bootstrap the SQLite database, seed tables, and install git hooks
./bible init

# Verify 100% system health, zero dependencies, and test suite
./bible doctor
```

### 2. Read Scripture from the Terminal
```bash
# Direct reference lookup (auto-routed without flags)
./bible "John 3:16"
./bible "Romans 8:28-39"

# Editorial reader layout with decorative borders and paragraph flow
./bible "Philippians 2:5-11" --flow --margin=4 --box

# Compare translations side-by-side (ESV, KJV, WEB)
./bible compare "Genesis 1:1" --versions=ESV,KJV,WEB
```

### 3. Fast Full-Text & Vector Similarity Search
```bash
# Full-text FTS5 BM25 search with keyword highlighting
./bible search "light of the world"
./bible search "faith AND works" --testament=NT

# Vector-based conceptual semantic similarity search
./bible similar "John 3:16" --limit=5
./bible similar "armor of God against spiritual warfare"

# View the whole Bible as a 2D ASCII/ANSI semantic scatter map
./bible map
```

### 4. Grounded Theological Inquiry (Scripture RAG)
```bash
# Inquire across Scripture with Tri-Modal Hybrid RAG & Reciprocal Rank Fusion
./bible ask "How does Jesus fulfill the Day of Atonement?"

# Filter retrieval by theological epoch, genre, or testament
./bible ask "Trace the temple from Eden to the New Jerusalem" --epoch=exodus
```

### 5. Dialogue with Canonical Biblical Characters
```bash
# Interactive conversation with biblical figures grounded in canonical texts
./bible chat paul
./bible chat moses
./bible chat david
```

### 6. Generate 4K Visual Verse Slides for TV Screensavers
```bash
# Generate a single 4K presentation slide (OLED black background)
./bible slide "Philippians 4:6-7" --resolution=4k --theme=oled-black --out=slide.png

# Batch export all starred favorites into a folder for TV displays
./bible slide-batch --favorites --starred-only --resolution=4k --theme=oled-black --out=slides/
```

### 7. Launch Interactive REPL Studio or Web UI
```bash
# Launch persistent interactive terminal REPL
./bible shell

# Start local HTTP server and Sacred-Modern Web UI
./bible serve --open
# Opens http://localhost:8080 in your default browser
```

---

## 💻 CLI Subcommand Reference

Bible Engine provides an illuminated Sacred-Modern platform status dashboard when invoked with no arguments (`./bible`). Specific capabilities are accessed via subcommands:

| Subcommand | Aliases | Description | Example |
|---|---|---|---|
| `status` | *(default)* | Illuminated Sacred-Modern platform health & metrics dashboard | `./bible status` or `./bible` |
| `get` | | Read scripture passage by citation with styling | `./bible get "Rom 8:28-39"` or `./bible "Rom 8"` |
| `compare` | | Parallel side-by-side multi-translation comparison | `./bible compare "John 1:1" --versions=ESV,KJV,WEB` |
| `search` | `find` | SQLite FTS5 BM25 keyword search with ANSI highlighting | `./bible search "grace and truth"` |
| `similar` | `vector` | Dense vector cosine similarity search (passages or queries) | `./bible similar "John 3:16"` |
| `map` | `scatter` | Interactive terminal 2D semantic scatter map atlas | `./bible map` |
| `ask` | `rag` | Grounded Scripture RAG synthesis with hybrid search | `./bible ask "How does Christ fulfill the law?"` |
| `chat` | `persona` | Interactive canonical dialogue with 19 biblical characters | `./bible chat paul` |
| `characters` | | List all available biblical personas and profiles | `./bible characters` |
| `slide` | `render` | Generate 4K/1080p presentation slides for TV screens | `./bible slide "Phil 4:6-7" --resolution=4k` |
| `slide-batch` | | Batch export entire reading plans/favorites to slides | `./bible slide-batch --favorites --starred-only` |
| `tag` | `tags` | Multi-resolution semantic exegesis, tags & co-occurrence | `./bible tag show "justification"` |
| `crossref` | `xref` | Query 343,000+ TSK cross-references and typological paths | `./bible crossref for "Gen 3:15"` |
| `corpora` | | Inspect 7 canonical corpora and whole-Bible pericopes | `./bible corpora` |
| `translations`| `versions` | List installed translations and verse totals | `./bible translations` |
| `keys` | | Manage and probe API credentials (ESV, Gemini) | `./bible keys status` / `./bible keys wizard` |
| `init` | `setup` | Compile SQLite database, seed tables, and install hooks | `./bible init [--force]` |
| `db` | `database` | Storage metrics, table inspections, vacuum, and optimization | `./bible db stats` / `./bible db optimize` |
| `shell` | `interactive` | Launch sovereign interactive REPL study console | `./bible shell` |
| `serve` | `web` | Start multi-threaded HTTP server and Sacred-Modern Web UI | `./bible serve [--port=8080] [--open]` |
| `test` | | Run parallel hermetic test runner (1,062 tests in <10s) | `./bible test [--fast] [--watch]` |
| `lint` | | Run sovereign AST-based static linter | `./bible lint` |
| `bench` | | Run performance latency profiler and regression gate | `./bible bench` |
| `coverage` | | Zero-dependency code coverage profiler | `./bible coverage` |
| `doctor` | | Run 9-point system health & zero-dependency diagnostics | `./bible doctor [--fast] [--fix]` |
| `ci` | | Inspect GitHub Actions CI/CD status and run details | `./bible ci check` / `./bible ci status` |
| `issues` | | Triage, search, and manage GitHub issues autonomously | `./bible issues list` |
| `summary` | | Generate multi-iteration executive trajectory summary | `./bible summary [--window=10]` |

---

## 🖥️ Interactive REPL Studio (`./bible shell`)

The persistent terminal REPL shell provides a fluid study environment with readline history, command tab autocompletion, and live rendering:

```text
╔═════════════════════════════════════════════════════════════════════════════╗
║      Bible Engine — Sovereign Scripture & Semantic Knowledge Platform      ║
║          Offline-First • Zero Dependencies • Run #106 • 114 ADRs           ║
╚═════════════════════════════════════════════════════════════════════════════╝

bible [ESV]> John 3:16
=== John 3:16 (ESV) ===
  [16] For God so loved the world, that he gave his only Son, that whoever
       believes in him should not perish but have eternal life.

bible [ESV]> /similar "Romans 8:28"
=== Top Semantic Vector Matches for Romans 8:28 ===
  1. Ephesians 1:11 (94.2% similarity) — "predestined according to the purpose of him..."
  2. Genesis 50:20  (91.8% similarity) — "you meant evil against me, but God meant it for good..."
  3. 2 Tim 1:9      (89.5% similarity) — "called us with a holy calling... according to his purpose..."

bible [ESV]> /ask "Explain justification by faith alone"
=== Grounded Scripture RAG Exegesis ===
Retrieved 4 foundational pericopes (Romans 3:21-26, Galatians 2:15-21, Genesis 15:1-6, Philippians 3:8-9)...
[Answer synthesized with TGC Confessional Guardrails and biblical citation links]

bible [ESV]> /chat paul
=== Canonical Persona Dialogue: Apostle Paul (First Century AD) ===
Paul> Grace to you and peace from God our Father and the Lord Jesus Christ. What burdens your spirit concerning the gospel of our Lord?
```

### Common REPL Slash Commands
- **Reading & Search**: `<citation>` (e.g. `Rom 8:1-11`), `/get <ref>`, `/compare <ref>`, `/search <query>`, `/similar <ref-or-query>`
- **Theological AI**: `/ask <question> [--testament=NT] [--epoch=exodus]`, `/chat <persona>`, `/characters`, `/persona <name>`
- **Visuals & Slides**: `/slide <ref> [--4k] [--oled]`, `/map` (terminal 2D scatter map)
- **Knowledge Graph**: `/tag show <tag>`, `/tag density`, `/crossref for <ref>`, `/typology [ref]`
- **System & Tooling**: `/status`, `/doctor`, `/test`, `/lint`, `/bench`, `/coverage`, `/summary`, `/theme [sacred|amber|cyan|plain]`

---

## 🎨 Sacred-Modern Web UI & Visualizations (`./bible serve`)

Launch the built-in HTTP server (`./bible serve --port=8080`) to access the responsive web application:

### 1. Visual Reader & Editorial Typography
- **Tri-Theme Token System**:
  - **Obsidian Dark Mode** (`#0D0E11` background, `#14171F` surface, `#D4AF37` gold accents)
  - **Scriptorium Warm Charcoal** (`#12100E` background with warm sepia undertones)
  - **Monastery Light Parchment** (`#F7F4EB` background with antique manuscript ink)
- **Editorial Typography**: Standardized Cardo / Charter / Georgia serif stack with browser-persisted dynamic font scaling (`A-` / `A+`).
- **Dual Reading Modes**: Toggle between Verse List Mode (hanging indents, verse numbers) and Paragraph Flow Mode (prose flow, inline superscripts).

### 2. Interactive Visualizers & AI Panels
- **2D Semantic Scatter Map Atlas**: Interactive canvas visualization where all 1,333 pericopes appear as clickable dots spatially clustered by 768-dimensional conceptual proximity using FastMap/PCA.
- **Redemptive Ribbon 66-Book Heatmap**: Interactive canonical heatmap visualizing theological tag frequency across all 66 books.
- **Typological Arc Network**: Native browser SVG graph connecting Old Testament shadows (e.g., Bronze Serpent, Passover Lamb) directly to Christological fulfillments.
- **Split-Screen RAG Exegesis**: Split-pane view providing dynamic grounded study notes, cross-reference expansion, and reciprocal rank fusion search scores.
- **Biblical Character Dialogue Studio**: Conversational interface with biblical saints featuring real-time Server-Sent Events (SSE) token streaming.

---

## 🖼️ Visual Verse Slide Generator for TV Screensavers

Bible Engine includes a dynamic rendering engine (`core/render.py`) producing ultra-high-resolution visual slides optimized for 4K and 1080p television screensavers and presentations:

```bash
# Generate a single 4K slide with OLED pitch-black background
./bible slide "Philippians 4:6-7"   --resolution=4k   --theme=oled-black   --font="Georgia"   --citation-style=below   --out=phil4.png

# Batch export an entire folder of slides from curated favorites
./bible slide-batch   --favorites   --starred-only   --resolution=4k   --theme=oled-black   --out=tv_slides/
```

- **OLED Protection**: Pure `#000000` background ensures zero burn-in on modern OLED TVs.
- **Dynamic Typography**: Auto-computes optical font size clamping, balanced word wrapping, line-height geometry, and vertical optical centering (~45%) within TV safe margins (15%).
- **Multi-Slide Pagination**: Passages exceeding readability thresholds automatically paginate into numbered slide sequences (e.g., `1/3`, `2/3`, `3/3`).

---

## 📡 REST API Reference

The built-in HTTP server exposes a comprehensive JSON REST API:

| Endpoint | Method | Description | Example |
|---|---|---|---|
| `/api/status` | `GET` | Platform status, metrics, and health overview | `/api/status` |
| `/api/health` | `GET` | System health check and uptime telemetry | `/api/health` |
| `/api/books` | `GET` | List 66 canonical books with chapter counts | `/api/books?testament=NT` |
| `/api/passage` | `GET` | Retrieve passage verses by reference | `/api/passage?ref=John+3:16-17` |
| `/api/verses` | `GET` | Retrieve verses by book, chapter, and range | `/api/verses?book=Romans&chapter=8` |
| `/api/search` | `GET` | FTS5 full-text search with pagination & snippets | `/api/search?q=grace&limit=10` |
| `/api/similar` | `GET` | Vector cosine similarity for citations or text | `/api/similar?ref=John+3:16` |
| `/api/embeddings/map` | `GET` | 2D projection coordinates for all pericopes | `/api/embeddings/map` |
| `/api/rag` | `POST` | Execute Tri-Modal Hybrid Scripture RAG query | `/api/rag` (JSON payload) |
| `/api/chat/persona` | `POST` | Dialogue with biblical persona (supports SSE) | `/api/chat/persona` |
| `/api/characters` | `GET` | Catalog of 19 canonical biblical characters | `/api/characters` |
| `/api/slide` | `GET` | Render dynamic SVG/PNG slide on-the-fly | `/api/slide?ref=Phil+4:6-7&res=4k` |
| `/api/tags` | `GET` | List semantic tags and taxonomy categories | `/api/tags` |
| `/api/crossref` | `GET` | Query typological and thematic cross-references | `/api/crossref?ref=Gen+3:15` |
| `/api/stats` | `GET` | Overall database storage and row counts | `/api/stats` |

---

## 🔒 Security, Credentials & Offline Posture

Bible Engine functions completely offline with zero external network connectivity using its bundled public-domain translations (WEB and KJV). External API credentials unlock enhanced translations and AI synthesis:

| Credential | Purpose | Scope & Storage |
|---|---|---|
| `ESV_API_KEY` | Modern English Standard Version text retrieval & context building | Stored locally in `.env` (`ESV_API_KEY=...`) or `config/esv_api_key.txt` (POSIX `0600`). Free key from [api.esv.org](https://api.esv.org/). |
| `GEMINI_API_KEY` | Runtime dynamic Scripture RAG synthesis and Character Persona Chat | Configured interactively during `./bible init` or `./bible keys wizard`, or via `.env`. Free key from [Google AI Studio](https://aistudio.google.com/). |

```bash
# View credential status and probe API connectivity:
./bible keys status
./bible keys probe

# Configure keys interactively:
./bible keys wizard
```

- **Zero Secret Leaks ([ADR-075](DECISIONS.md#adr-075-sovereign-local-secret-management-zero-leak-git-safeguards-and-development-vs-serving-credential-demarcation))**: `.gitignore` strictly isolates all credential files. Machine-enforced pre-commit hooks and doctor sentries prevent secret leakage.
- **Copyright Compliance ([ADR-041](DECISIONS.md#adr-041-public-open-source-repository-governance-permissive-mit-license-and-crossway-legal-attribution-guidelines))**: ESV text is retrieved ephemerally with in-memory caching and attribution per Crossway guidelines; copyrighted texts are never committed to git.

---

## 🛠️ Developer Architecture & Invariants

Bible Engine is designed to run for decades without maintenance:

1. **Zero External Dependencies ([ADR-003](DECISIONS.md#adr-003-zero-dependency-architecture-for-zero-maintenance--dependabot-immunity))**:
   - Python 3 standard library only (`sqlite3`, `http.server`, `urllib`, `argparse`, `json`, `math`, `struct`, `unittest`).
   - Vanilla HTML5, modern CSS3 variables, native browser JavaScript (ES6+). Zero npm packages, zero pip dependencies.
   - Verified continuously via AST inspection (`./bible doctor` fails if any third-party import is introduced).
2. **Deterministic Hermetic Testing**:
   - Parallel test runner (`tools/test_runner.py` / `./bible test`) with Longest Processing Time (LPT) scheduling runs **1,062 tests in <10 seconds** offline.
3. **Automated Machine Safeguards ([ADR-022](DECISIONS.md#adr-022-multi-tiered-automated-git-hook-safeguards-fast-pre-commit-linting--machine-enforced-invariant-architecture))**:
   - Pre-commit hook runs fast AST audits, doc-sync validation, and shell integrity checks in `<0.2s`.
   - Pre-push hook executes complete hermetic test discovery and database validation before remote sync.

---

## 🤖 Autonomous Development: The Ralph Loop

This repository is continuously maintained and evolved via the **Ralph Loop** (`./ralph.sh`), an autonomous agent operating harness defined in [AGENTS.md](AGENTS.md):

```bash
# Run continuous autonomous iterations:
./ralph.sh --loop

# Run fixed number of iterations (e.g. 5):
./ralph.sh --loop 5

# Run single headless cycle with real-time streaming telemetry:
./ralph.sh -p

# On-demand Senior Product Manager Meta-Improvement Sprint:
./ralph.sh --cleanup -p

# On-demand Executive Summary & Trajectory Briefing Double Milestone:
./ralph.sh --summary -p
```

### Cadence Protocol
- **Every 5th Iteration (`run % 5 == 0`)**: Dedicated **Senior Product Manager Meta-Improvement & System Health Sprint**. Agents step out of domain coding to answer:
  1. *"What is the weakest aspect of this project structure?"*
  2. *"What is preventing this from being more incredible?"*
  and immediately execute a Rank A+ meta-improvement.
- **Every 10th Iteration (`run % 10 == 0`)**: **Executive Briefing Double Milestone**. Synthesizes multi-iteration retrospectives, trajectory projections, and letter-graded improvement ideas.

---

## 📄 License & Dedication

- **World English Bible (WEB)**: Dedicated to the Public Domain by Rainbow Missions, Inc.
- **King James Version (KJV)**: Public Domain in the United States and worldwide outside the Crown rights in the UK.
- **English Standard Version (ESV)**: Scripture quotations marked "ESV" are from the ESV® Bible (The Holy Bible, English Standard Version®), copyright © 2001 by Crossway, a publishing ministry of Good News Publishers. Used by permission. All rights reserved.
- **Bible Engine Software Platform**: Released under the permissive [MIT License](LICENSE).
