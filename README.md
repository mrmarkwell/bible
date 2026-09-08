# Bible Engine

> **Offline-First Sovereign Scripture Platform, Semantic Knowledge Graph & Sacred-Modern Visual Reader**  
> *Zero External Dependencies • Zero npm Packages • Zero pip Requirements • Dependabot-Immune*

---

## Overview

**Bible Engine** is an offline-first, locally hosted platform for scripture reading, full-text search, multi-resolution semantic tagging, typological cross-referencing, and visual biblical analytics.

Designed for longevity, speed, and sovereign personal study, Bible Engine operates under an uncompromising architectural mandate: **Zero External Dependencies** ([ADR-003](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md#adr-003-zero-dependency-architecture-for-zero-maintenance--dependabot-immunity)). The entire engine—database management, FTS5 full-text indexing, terminal typography, HTTP web server, REST API, and interactive user interfaces—is built exclusively with the **Python 3 standard library** and **vanilla HTML/CSS/JS**.

- **Instant Cold-Start**: Compiles and bootstraps 31,103 verses, 829 favorites, 26 canonical taxonomies, 43 cross-reference edges, and git hooks in `<0.5s` via `./bible init`.
- **Direct Citation Ergonomics**: Simply type `./bible "John 3:16"` or `./bible "Rom 8:28-30"`—no verbose flags required.
- **Fast Full-Text Search**: SQLite FTS5 full-text search across 31,100+ verses with colored ANSI keyword highlighting in `<5ms`.
- **Parallel Multi-Translation Comparison**: Side-by-side terminal comparison across translations (`./bible compare "John 1:1" WEB,KJV`).
- **Semantic Tagging & Taxonomies**: Multi-resolution passage tagging (individual verses or arbitrary spans) grounded in the confessional framework of The Gospel Coalition (TGC).
- **Typological Cross-Reference Graph**: Foundational OT shadow to NT fulfillment cross-reference network with multi-hop pathfinding.
- **Sovereign Interactive REPL Shell**: Persistent study terminal with readline history, live search, tab autocompletion, and hot theme switching (`./bible shell`).
- **Sacred-Modern Web UI**: Built-in HTTP web server (`./bible serve`) serving a split-pane reader with Obsidian Dark Mode (`#0D0E11`), Scriptorium Charcoal, and Monastery Parchment themes.
- **Self-Healing Repository Doctor**: Machine-enforced AST audits, documentation synchronization, and automated repair (`./bible doctor --fix`).

---

## 30-Second Quickstart

### 1. Bootstrap the Sovereign Environment
Clone the repository and initialize the offline database:

```bash
# Initialize SQLite database, compile WEB translation, seed tags/crossrefs, and install git hooks
./bible init

# Verify 100% system health, zero dependencies, and test suite
./bible doctor
```

### 2. Read Scripture from the Terminal
```bash
# Direct reference lookup (auto-routed)
./bible "John 3:16"

# Editorial reader layout with decorative borders and left indentation
./bible "Romans 8:28-30" --flow --margin=4 --box

# Compare translations side-by-side
./bible compare "Genesis 1:1" WEB,KJV
```

### 3. Search Scripture Instantly
```bash
# Full-text search with automatic term highlighting
./bible search "light of the world"

# Boolean operators and testament filtering
./bible search "faith AND works" --testament=NT
```

### 4. Explore Semantic Tags & Cross-References
```bash
# Show passages tagged under theological themes
./bible tag show "justification"

# Display typological cross-references
./bible crossref for "Genesis 3:15"
```

### 5. Launch Interactive REPL Shell
```bash
./bible shell
# Or simply: ./bible -i
```

### 6. Start Sacred-Modern Web Reader & REST API
```bash
./bible serve --open
# Opens http://127.0.0.1:8080 in your default browser
```

---

## CLI Command Reference

| Subcommand | Aliases | Description | Example |
|---|---|---|---|
| `get` | *(default)* | Lookup scripture passage by reference | `./bible get "John 3:16"` or `./bible "John 3:16"` |
| `compare` | | Compare passage across multiple translations | `./bible compare "John 1:1" WEB,KJV` |
| `search` | `find` | Full-text FTS5 search with keyword highlighting | `./bible search "light of the world"` |
| `translations`| `versions` | List installed translations and verse totals | `./bible translations` |
| `tag` | `tags` | Semantic tagging, passage annotations & stats | `./bible tag show "sovereignty"` |
| `crossref` | `xref`, `refs` | Typological links & cross-reference paths | `./bible crossref for "Gen 3:15"` |
| `init` | `setup`, `bootstrap` | Compile offline database and install hooks | `./bible init [--force]` |
| `db` | `database` | Storage metrics, pragmas, optimize & vacuum | `./bible db stats` / `./bible db optimize` |
| `doctor` | | Run system health & zero-dependency diagnostics | `./bible doctor [--fast] [--fix]` |
| `summary` | | Generate executive summary across recent runs | `./bible summary [--window=10]` |
| `shell` | `interactive`, `repl` | Launch interactive study console | `./bible shell` |
| `serve` | `server`, `http`, `web` | Launch local HTTP server and Sacred-Modern Web UI | `./bible serve [--port=8080] [--open]` |

---

## Interactive REPL Shell Guide (`./bible shell`)

Launch a persistent, high-velocity Scripture study session with readline history and tab autocompletion:

```text
bible [WEB]> John 3:16
=== John 3:16 (WEB) ===
  [16] For God so loved the world, that he gave his one and only Son, that
       whoever believes in him should not perish, but have eternal life.

bible [WEB]> /search "grace and truth"
=== Scripture Search: "grace and truth" (WEB) ===
Found 3 matching verses:
  1. John 1:14 (WEB) ...
  2. John 1:17 (WEB) ...

bible [WEB]> /theme sacred
✓ Theme set to 'sacred' (Illuminated Gold & Obsidian).

bible [WEB]> /flow on
✓ Reader mode: Continuous paragraph flow.

bible [WEB]> /db stats
=================================================================
 Bible Engine Database Storage Diagnostics
=================================================================
 File Location:        data/bible.db
 File Size:            26.4 MB (27,717,632 bytes)
 SQLite Version:       3.53.4
 Total Verses:         31,103 (WEB)
 Total Tags:           26 taxonomies | 829 annotations (50 starred)
 Cross-References:     43 canonical typological links
=================================================================
```

### Slash Commands in REPL

- **Passage Reading**: `<citation>` (e.g. `John 1:1`, `Rom 8:1-11`), `/get <citation>`
- **Search & Compare**: `/search <query>`, `/compare <ref> [versions]`
- **Semantic Tagging**: `/tag add <ref> <tag>`, `/tag list`, `/tag show <tag>`, `/tag density`, `/tag co-occurrence`, `/tag relevance <tags>`
- **Cross-References**: `/crossref for <ref>`, `/crossref link <src> <tgt>`, `/crossref path <src> <tgt>`, `/crossref stats`
- **Session Controls**: `/version <id>`, `/versions`, `/theme [sacred|amber|cyan|plain]`, `/margin <n>`, `/flow [on|off]`, `/box [on|off]`
- **Database & Lifecycle**: `/db stats`, `/db optimize`, `/db vacuum`, `/init`
- **Web & Diagnostics**: `/serve [start|stop]`, `/doctor`, `/summary`, `/clear`, `exit`

---

## Sacred-Modern Web UI & REST API (`./bible serve`)

Bible Engine includes a zero-dependency, multi-threaded HTTP server (`web/server.py`) serving static visual assets (`web/static/`) and a JSON REST API.

### Visual Reader Features
- **Tri-Theme Sacred-Modern Design Tokens**:
  - **Obsidian Dark Mode** (`[data-theme="obsidian"]`, default): Abyssal background `#0D0E11`, surface `#14171F`, card surfaces `#1B202B` / `#222836`.
  - **Scriptorium Warm Charcoal** (`[data-theme="scriptorium"]`): Warm charcoal `#12100E` with sepia undertones `#1A1714` / `#24201B`.
  - **Monastery Light Parchment** (`[data-theme="monastery"]`): Manuscript parchment `#F7F4EB`, `#EFE9DC`, antique ink `#211D19`.
  - **Illuminated Gold Accents**: Canonical Byzantine primary gold `#D4AF37`, leaf halo `#F5E08F`, burnished gold `#997E24`.
- **Editorial Serif Typography**: Standardized Cardo / Charter / Georgia serif stack with dynamic browser-persisted font scaling (`A-` / `A+`).
- **Reading Modes**: Toggle between Verse List Mode (hanging indents, verse numbers) and Paragraph Flow Mode (prose flow, inline superscripts).
- **Split-Pane Layout**: Collapsible sidebar with Old/New Testament book grid, chapter breadcrumbs, dynamic passage search, and one-click citation copy.

### REST API Endpoints

| Endpoint | Method | Description | Example |
|---|---|---|---|
| `/api/health` | `GET` | Health check, server uptime, database stats | `/api/health` |
| `/api/books` | `GET` | List 66 canonical books with chapter counts | `/api/books?testament=NT` |
| `/api/passage` | `GET` | Retrieve passage verses by reference | `/api/passage?ref=John+3:16-17` |
| `/api/verses` | `GET` | Retrieve verses by book, chapter, and range | `/api/verses?book=John&chapter=3` |
| `/api/search` | `GET` | Full-text search with pagination & snippet | `/api/search?q=light&limit=10` |
| `/api/translations`| `GET` | List available translations and counts | `/api/translations` |
| `/api/tags` | `GET` | List semantic tags or search tag taxonomy | `/api/tags?category=theological` |
| `/api/tags/density`| `GET` | Topic density distribution across books | `/api/tags/density?tag=grace` |
| `/api/tags/co-occurrence`| `GET` | Tag co-occurrence similarity matrix | `/api/tags/co-occurrence` |
| `/api/tags/relevance`| `GET` | Multi-tag relevance scoring and ranking | `/api/tags/relevance?tags=faith,grace` |
| `/api/crossref`| `GET` | Query typological and thematic cross-references | `/api/crossref?ref=Gen+3:15` |
| `/api/stats` | `GET` | Overall database storage and row counts | `/api/stats` |

---

## Architectural Principles & Invariants

Bible Engine is designed to outlive ephemeral framework lifecycles and operate perpetually without maintenance:

1. **Zero External Dependencies ([ADR-003](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md#adr-003-zero-dependency-architecture-for-zero-maintenance--dependabot-immunity))**:
   - Python 3 standard library only (`sqlite3`, `http.server`, `urllib`, `argparse`, `json`, `cmd`, `unittest`).
   - Vanilla HTML5, CSS3 variables, and native browser JavaScript.
   - Zero npm packages, zero pip dependencies, zero CDN dependencies.
   - **Machine-Audited**: Verified continuously via AST inspection (`./bible doctor` fails if any third-party import is introduced).
2. **Offline-First & Sovereign**:
   - Full 66-book World English Bible (31,103 verses) cached locally in `data/raw/web/` and compiled into SQLite.
   - All searches, tags, and cross-references run locally with zero network calls required.
3. **Automated Machine Safeguards ([ADR-022](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md#adr-022-multi-tiered-automated-git-hook-safeguards-fast-pre-commit-linting--machine-enforced-invariant-architecture))**:
   - Git pre-commit hook runs fast AST audits, doc-sync validation, and shell integrity in `<0.2s`.
   - Git pre-push hook executes complete hermetic test discovery and database validation before remote sync.
4. **Hermetic & Fast Test Suite**:
   - 350+ unit and integration tests executing in `<5.5s` offline (`python3 -m unittest discover tests`).
5. **Sovereign Local Secret Management & Zero-Leak Safeguards ([ADR-075](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md#adr-075-sovereign-local-secret-management-zero-leak-git-safeguards-and-development-vs-serving-credential-demarcation))**:
   - Local `.env` and `config/*` secret files are enforced with POSIX `0600` permissions (owner read/write only).
   - `.gitignore` rigorously isolates all credentials (`.env`, `config/`, `*.key`, `*api_key*`) preventing accidental upload to GitHub.
   - Pre-commit and doctor audits guarantee no credentials or secret files are ever tracked in version control.

---

## API Credentials & Local Configuration

Bible Engine operates completely offline with the public-domain World English Bible (`WEB`). External credentials unlock enhanced translations and serving capabilities:

| Credential | Scope & Purpose | Where to Find / Configure |
|---|---|---|
| `ESV_API_KEY` | **Application Development & Scripture Ingestion**<br>Used for live modern English Standard Version text retrieval, translation comparison, semantic tagging context, and pericope embedding generation. | Stored locally in `.env` (`ESV_API_KEY=...`) or `config/esv_api_key.txt` (POSIX 0600, excluded from git). Managed via `./bible keys set --esv <key>`. Free key from [api.esv.org](https://api.esv.org/). |
| `GEMINI_API_KEY` | **Runtime App Serving ONLY**<br>Needed strictly for end-user dynamic Scripture RAG answer synthesis and biblical character dialogue in `./bible serve` or `./bible chat`.<br>*(Not needed for application development like semantic tagging; development agents use local skills).* | Configured interactively during `./bible init` or `./bible keys wizard`, or via `.env`. Free key from [Google AI Studio](https://aistudio.google.com/). |

```bash
# View current credential configuration and probe status:
./bible keys status
./bible keys probe

# Configure keys interactively:
./bible keys wizard
# Or directly:
./bible keys set --esv <YOUR_KEY>
```

---

## Autonomous Development: The Ralph Loop

This repository is continuously maintained and evolved via the **Ralph Loop** (`./ralph.sh`), an autonomous agent operating lifecycle defined in [AGENTS.md](file:///usr/local/google/home/markwell/personal_dev/bible/AGENTS.md):

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

## License & Dedication

- **World English Bible (WEB)**: Dedicated to the Public Domain by Rainbow Missions, Inc.
- **Bible Engine Platform**: Dedicated to sovereign, distraction-free Scripture study and redemptive-historical theological exploration.
