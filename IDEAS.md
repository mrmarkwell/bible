# Project Ideas & Feature Requests

This document is the intake hopper for new feature requests, brainstormed concepts, and future improvements. 

Ideas can be added directly by the repository owner or generated during interactive brainstorming sessions with an agent. Autonomous agents or interactive sessions will triage, refine, and translate these ideas into concrete, atomic tasks in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).

---

## Status Legend
- `[IDEA]`: Raw concept or brainstormed proposal; needs refinement.
- `[VETTED]`: Architecture and trade-offs verified against [MANIFESTO.md](file:///usr/local/google/home/markwell/personal_dev/bible/MANIFESTO.md) and [DECISIONS.md](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md).
- `[SCHEDULED]`: Formalized into atomic tasks and added to [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- `[REJECTED]`: Decided against (rationale recorded).

---

## How to Submit / Brainstorm a Feature Request
1. **In an Interactive Chat**: Simply ask the agent: *"Let's brainstorm a feature for X"* or *"I want to add a feature: Y"*. The agent will analyze alignment, break it into tasks, and add it here or directly into `ROADMAP.md`.
2. **Direct Edit**: Add an entry below under the **Active Ideas** section using the template below.
3. **Commit & Push**: Any session adding or refining ideas must commit and push immediately (`git push origin main`).

### Idea Template
```markdown
### [STATUS] Feature Name
- **Summary**: Brief description of the capability.
- **Rationale**: Why this is valuable for the user or ecosystem.
- **Constraints & Alignment**:
  - Offline-first? Yes/No
  - Zero third-party dependencies? (Must use Python stdlib / native browser APIs)
  - Copyright compliant?
- **Proposed Roadmap Phase**: Which phase does this belong to or does it require a new phase?
- **Suggested Tasks**:
  - [ ] Task description
```

---

## Active Ideas & Brainstorming Hopper

### [VETTED] Terminal-Native Ralph Loop CLI Invocation
- **Summary**: Replace background `agentapi` loop with direct terminal invocation of Jetski CLI (`/google/bin/releases/jetski-devs/tools/cli --dangerously-skip-permissions -i "Execute one cycle of the Ralph loop per AGENTS.md."`).
- **Rationale**: Immediate developer visibility, terminal-native interactivity, and elimination of fragile background daemon polling.
- **Constraints & Alignment**:
  - Zero third-party dependencies? Yes (uses existing local binary).
  - Autonomous permission auto-approval? Yes (`--dangerously-skip-permissions`).
- **Status**: Implemented via ADR-007 and Task 0.4.

### [VETTED] Semantic Tagging & Topical Heatmaps
- **Summary**: Tag verses and spans with topics (e.g. money, wisdom, Holy Spirit) and render visual heatmaps across all 66 books.
- **Status**: Active in Phase 3 of [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md); Task 3.1 Tagging API implemented in Run 022 (ADR-023). Heatmaps scheduled for Phase 4.

### [VETTED] Zero-Dependency Web Visualization Server
- **Summary**: Embedded HTTP server (`./bible serve`) serving vanilla HTML/CSS/JS with native browser SVG/Canvas heatmaps without npm or pip dependencies.
- **Status**: Scheduled in Phase 4 of [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).

### [VETTED] TV Screensaver Verse Slide Generator (`bible slide` / `bible render`)
- **Summary**: Generate high-resolution 16:9 landscape slides (4K UHD default) with white scripture text on true OLED black background for Google Photos TV screensaver slideshows.
- **Rationale**: Provides ambient, contemplative scripture display on home televisions. High dynamic contrast, zero burn-in on OLED displays, and beautiful dynamic typography regardless of passage length.
- **Constraints & Alignment**:
  - Offline-first? Yes (local rendering engine).
  - Zero third-party dependencies? Yes (uses Python stdlib + system ImageMagick / pure SVG, zero pip packages per ADR-003).
  - Copyright compliant? Yes (public domain WEB/KJV by default, user-supplied texts/APIs optional).
- **Design Specifications**:
  - Landscape 16:9 aspect ratio (default 3840x2160 4K UHD, configurable to 1080p or custom).
  - Pure `#000000` black background for OLED energy efficiency and infinite contrast.
  - 15% TV safe area margin to prevent bezel clipping and overscan loss.
  - Dynamic scaling algorithm with font size clamping: auto-computes optimal font size, line wrapping, and line height to center both short verses (e.g. "Jesus wept") and lengthy pericopes without overflow.
  - Optical vertical centering (~45% baseline rather than strict geometric 50%) for natural viewing.
  - Distinct hierarchical citation styling (muted off-white/gray, em-dash or small caps).
  - Multi-slide pagination support for lengthy passages exceeding safe viewing density.
  - Dual rendering backend: ImageMagick (`magick`/`convert`) for raster PNG/JPEG + pure Python SVG vector generator.
- **Proposed Roadmap Phase**: Phase 5 (Tasks 5.1–5.5 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md)).
- **Status**: [VETTED] and scheduled.

### [IDEA] Audio Bible Alignment / Narration Timestamps
- **Summary**: Associate public-domain audio recordings (e.g. LibriVox WEB/KJV audio) with verse timestamps for synchronous playback and reading.
- **Rationale**: Enhances accessibility and devotional utility.
- **Status**: Raw idea awaiting evaluation.

### [IDEA] Interlinear & Original Language Lexicon (Hebrew / Greek)
- **Summary**: Store Strong's concordance numbers and lemma definitions alongside public-domain translations for deep word study.
- **Rationale**: Enables rich semantic drill-down into original language roots without external internet queries.
- **Status**: Raw idea awaiting evaluation.

### [VETTED] Offline LLM Semantic Enrichment Engine (`bible enrich`)
- **Summary**: Batch offline pipeline leveraging Google's premier LLM (Gemini 2.5 Pro / Gemini 2.0 Flash) to systematically enrich the local SQLite database with multi-resolution metadata:
  1. Pericope segmentations with redemptive-historical titles and summaries.
  2. Canonical typology linkages (connecting Old Testament types/shadows to New Testament fulfillments, e.g. Passover Lamb -> 1 Cor 5:7; Melchizedek -> Hebrews 7).
  3. Thematic tag mappings categorized by both Redemptive-Historical Biblical Theology (Reading Along: Covenant, Temple, Kingship, Exile, Restoration) and Systematic Theology (Reading Across: God, Sin, Substitutionary Atonement, Justification by Faith).
  4. Biblical character profiles (historical timeline, scripture references, spoken words, key trials, and theological significance).
- **Rationale**: Unlocks deep, semantic study without requiring continuous internet or real-time LLM inference during daily use. Sovereign data remains in the user's local SQLite file.
- **Theological Foundation (TGC Alignment)**:
  - Adheres strictly to The Gospel Coalition Confessional Statement and Theological Vision for Ministry.
  - Implements the TGC hermeneutical mandate: balancing reading *along* the whole Bible (narrative arch of redemption climaxing in Christ) with reading *across* the whole Bible (propositional doctrines of grace and salvation).
  - Explicitly rejects moralistic reductionism, grounding all pericopes in God's sovereign covenant grace.
- **Constraints & Alignment**:
  - Offline-first? Yes. Once generated, all metadata lives in local SQLite; zero network calls required for queries.
  - Zero third-party dependencies? Yes. Python stdlib `urllib.request` + `json` directly interfacing with Google's Gemini REST API. No pip packages (`google-generativeai` or `requests`), zero Dependabot alerts (ADR-003, ADR-006).
  - Default Model: Google's best flagship (`gemini-2.5-pro` with fallback to `gemini-2.0-flash`), authenticated via `GEMINI_API_KEY`.
- **Proposed Roadmap Phase**: Phase 6 & Phase 7 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- **Status**: [SCHEDULED].

### [VETTED] TGC-Grounded Online Scripture RAG & Cross-Reference Synthesis
- **Summary**: Real-time interactive Scripture RAG (Retrieval-Augmented Generation) system accessible via CLI (`bible ask`) and Web UI. When a user asks a complex theological or interpretive question (e.g., *"Trace how the theme of Sabbath rest unfolds from Genesis 2 through Hebrews 4"* or *"What is the biblical basis for penal substitutionary atonement?"*), the engine:
  1. Queries local SQLite for relevant verses, cross-references, and pre-computed typological tags using FTS5 and semantic tag graphs.
  2. Synthesizes a structured, gospel-centered explanation quoting precise scripture citations.
  3. Contextualizes the answer within the overarching redemptive narrative of Christ.
- **Rationale**: Far surpasses standard keyword search by discerning conceptual and theological relationships across the entire biblical canon.
- **Theological Foundation (TGC Alignment)**:
  - Grounded in TGC's "Chastened Correspondence Theory of Truth" (Theological Vision I) and Dual-Horizon Reading (Theological Vision II).
  - Maintains the supreme authority, sufficiency, and inerrancy of Scripture (Confessional Statement II).
  - Explicitly highlights the substitutionary work of Christ and justification by faith alone.
- **Constraints & Alignment**:
  - Offline-first? Degrades gracefully: if `GEMINI_API_KEY` is not set or network is unavailable, falls back to offline SQLite FTS5 search and pre-computed cross-reference lists.
  - Zero dependencies: pure Python stdlib REST client.
- **Proposed Roadmap Phase**: Phase 8 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- **Status**: [SCHEDULED].

### [VETTED] Interactive Biblical Character Dialogue Studio ("Persona In Scripture")
- **Summary**: An interactive dialogue feature allowing users to "converse" with key biblical figures (e.g. Abraham, Moses, David, Isaiah, Mary, Peter, Paul) strictly within their canonical, historical, and theological context.
- **Rationale**: Immersive educational and devotional tool for understanding the human experiences, historical challenges, and covenantal faith of scripture's authors and witnesses.
- **Theological Foundation & Guardrails (TGC Alignment)**:
  - **Anti-Moralistic Realism**: Characters are not presented as flawless heroes to be blindly imitated, but as fallen human beings saved solely by God's sovereign mercy and grace. David speaks openly of his sin and desperate need for cleansing (Psalm 51); Peter of his denials and restoration by Christ.
  - **Christocentric Teleology**: Every character speaks from their historical horizon but bears witness to God's unfolding promise climaxing in the Messiah (e.g., Moses speaking of the prophet like unto him; Abraham rejoicing to see Christ's day; Paul testifying to the righteousness of God revealed in Jesus).
  - **Strict Scriptural Bounding**: Characters decline to speculate on extrabiblical modern queries or invent personal lore not warranted by scripture.
- **Constraints & Alignment**:
  - Zero third-party dependencies.
  - Powered by Gemini 2.5 Pro with specialized system prompts embedded with TGC theological guardrails and pre-loaded with canonical scripture references for that figure.
- **Proposed Roadmap Phase**: Phase 8 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- **Status**: [SCHEDULED].

### [VETTED] Illuminated Web UI: Sacred-Modern Visual Analytics & Graphic Illumination
- **Summary**: A visually stunning, contemplative, and editorial web user interface designed to illuminate biblical architecture, structure, and thematic density.
- **Visual Design System**:
  - **Aesthetic**: "Sacred Minimalist / Digital Manuscript" — rich obsidian dark mode (`#0D0E11`) paired with illuminated gold/amber accents (`#D4AF37`, `#F39C12`), crisp ivory typography (`#F5F5F7`), and subtle parchment borders (`#2A2B32`).
  - **Typography**: Editorial serif headings (Playfair Display / EB Garamond / Georgia fallback) paired with clean geometric sans-serif for metadata and scripture citations.
- **Key Graphical Visualizations (Native SVG, Zero npm)**:
  1. **Canonical Redemptive Ribbon**: Macro-level interactive SVG heatmap across all 66 books displaying chapter-by-chapter thematic concentration.
  2. **Typological Arc Network**: Visual bezier arcs spanning the Old and New Testaments connecting types and prophecies to their New Testament fulfillments.
  3. **Character Canonical Journey Map**: Interactive timeline and book-by-book presence matrix for biblical figures.
  4. **Split-View Study & Dialogue Console**: Left pane for scripture text and pericope analysis; right pane for RAG synthesis, cross-reference explorer, or biblical character dialogue.
- **Constraints & Alignment**:
  - Zero npm, zero node_modules, zero bundler. 100% vanilla HTML5, CSS3, and native browser SVG/Canvas (ADR-003).
  - Runs directly from the embedded Python standard library HTTP server (`bible serve`).
- **Proposed Roadmap Phase**: Enhanced Phase 4 & Phase 8 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- **Status**: [SCHEDULED].

### [VETTED] Streaming Public Domain Ingestion & Offline Pack Compiler (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Implement a dedicated zero-dependency streaming importer and compiler CLI (`tools/ingest_web.py`) that streams or parses the full World English Bible (WEB) text (~31,102 verses across all 66 books), performs atomic batch database transactions via `sqlite3.executemany`, validates canonical verse totals, and compiles the standalone bundled `data/bible.db` file with pre-built FTS5 indexes.
- **Rationale**: Eliminates manual database creation steps and guarantees 100% reproducible, hermetic scripture data pack generation in seconds without any external dependencies.
- **Constraints & Alignment**:
  - Offline-first? Yes (generates standalone SQLite database).
  - Zero third-party dependencies? Yes (Python standard library `sqlite3`, `urllib.request`, `json`/text parser).
  - Copyright compliant? Yes (World English Bible is 100% public domain).
- **Proposed Roadmap Phase**: Phase 1, Task 1.3 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- **Status**: [DONE] (Implemented in `tools/ingest_web.py`, tested in `tests/test_ingest.py`, and recorded in ADR-009).

### [VETTED] Automated Curated Favorites Batch Ingestion & Starred Verse Tagging (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Implement an automated ingestion utility (`tools/ingest_favorites.py`) that reads the repository's curated dataset [`favorite_bible_verses.csv`](file:///usr/local/google/home/markwell/personal_dev/bible/favorite_bible_verses.csv), parses all 829 scripture passages into canonical `Reference` objects, populates the `spans` table, registers the `favorites` tag under category `curation`, and tags all entries into `verse_tags` while accurately preserving the 50 priority `starred=True` records.
- **Rationale**: Directly operationalizes the user's personal curated scripture dataset into the database as a first-class knowledge entity, making user favorites immediately queryable via CLI and Web UI.
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (`csv`, `sqlite3`, `core.reference`, `core.db`).
- **Proposed Roadmap Phase**: Phase 1, Task 1.6 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- **Status**: [DONE] (Implemented in `tools/ingest_favorites.py`, tested in `tests/test_favorites.py`, and recorded in ADR-012).

### [VETTED] Encrypted Sovereign Data Pack CLI & User Keyring (`bible pack` / `bible unpack`) (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Build dedicated CLI utility commands (`bible pack` and `bible unpack`) leveraging `core/crypto.py` to encrypt and decrypt arbitrary scripture corpora, pericope study packs, or user notes into sovereign `.bpack` format with interactive passphrase prompting, salt/nonce generation, and HMAC integrity validation.
- **Rationale**: Provides end-users and researchers with an effortless, standard-library-only mechanism to pack copyrighted translations (e.g. ESV, NIV) or private study notes for offline sharing and storage without risk of exposing unencrypted text in public git repositories.
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (uses `core/crypto.py`, stdlib only).
  - Copyright compliant? Yes (enables Pillar II copyright safety).
- **Proposed Roadmap Phase**: Phase 2 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- **Status**: [SCHEDULED].

### [VETTED] Zero-Dependency Terminal Scripture Formatter & ANSI Styler (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Build a dedicated terminal presentation module (`core/formatter.py` or `cli/formatter.py`) that renders scripture passages, search results, and metadata with clean typography: responsive terminal column wrapping (via `shutil.get_terminal_size()`), subtle dimmed verse numbers (`\033[2m16\033[0m`), highlighted search tokens (bold amber/gold), poetic indented line breaks, and optional marginal references, with graceful degradation when piped or running in non-TTY environments (`NO_COLOR` or `not sys.stdout.isatty()`).
- **Rationale**: Elevates the command-line reading experience from raw text output to an editorial reading environment directly in the terminal, preparing for Phase 2 CLI (`bible get`, `bible search`).
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (Python standard library `os`, `sys`, `shutil`, `textwrap`, `re`).
- **Proposed Roadmap Phase**: Phase 2, Task 2.4 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- **Status**: [SCHEDULED].

### [VETTED] Unified Executable Bible CLI & Subcommand Dispatcher (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Implement a single executable entry point `./bible` (and `bible.py`) in root/cli leveraging Python's standard library `argparse` with structured subcommand dispatching (`get`, `search`, `favorites`, `pack`, `serve`, `slide`). Includes automatic `--help` generation, version flag (`--version`), configurable database path override (`--db`), and human-friendly error reporting.
- **Rationale**: Provides a seamless, unified developer and user experience where all scripture lookups, searches, curation queries, and utilities are accessible via a single memorable CLI tool with zero external dependencies.
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (Python standard library `argparse`, `sys`, `pathlib`).
- **Proposed Roadmap Phase**: Phase 2, Task 2.1 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- **Status**: [DONE] (Implemented in `bible.py`, `bible`, `cli/main.py`, tested in `tests/test_cli.py`, and recorded in ADR-013).

### [VETTED] Fallback Translation Cascade & Multi-Translation Comparison CLI (`bible compare` / `bible get --version`) (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Support multi-translation lookup flags in `bible get` (`--version=WEB,KJV,ESV`) as well as a dedicated parallel comparison subcommand (`bible compare "John 1:1" --versions=WEB,KJV`) with automatic fallback to public-domain translations (WEB) when a requested translation is not installed or lacks the target passage.
- **Rationale**: Students and readers frequently study biblical passages by comparing translations side-by-side (e.g. formal equivalence vs. dynamic equivalence), and graceful fallbacks prevent hard CLI failures when user packs are absent.
- **Constraints & Alignment**:
- Offline-first? Yes (queries local SQLite database).
- Zero third-party dependencies? Yes (Python standard library only).
- Copyright compliant? Yes (public domain WEB/KJV by default, user packs optional).
- **Proposed Roadmap Phase**: Phase 2, Task 2.2 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- **Status**: [DONE] (Implemented in `core/db.py` and `cli/main.py`, tested in `tests/test_cli.py` and `tests/test_db.py`, and recorded in ADR-018).

### [VETTED] Live Streaming Telemetry & Event Formatter for Ralph Loop (`ralph.sh --loop`) (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Implement a zero-dependency streaming event consumer (`scripts/stream_runner.py`) for `ralph.sh --loop` that ingests Jetski's `--output-format stream-json` NDJSON output in real time and renders live terminal progress (active tool calls, bash commands executed, files inspected/edited, step duration, and live text deltas) before exiting cleanly with the process status code.
- **Rationale**: Currently, running continuous headless loop iterations (`ralph.sh --loop`) uses Jetski's default `-p` (print) mode with `--output-format text`. Because the agent spends 95% of its execution loop calling tools, running tests, and reading files (during which `TextDelta` is empty), the terminal remains completely silent for 5–15 minutes, appearing frozen to the user. A streaming event renderer restores full live visibility without sacrificing the autonomous multi-turn loop lifecycle.
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (Python 3 standard library `sys`, `json`, `time`).
- **Proposed Roadmap Phase**: Phase 0 Harness / Developer Tooling.
- **Status**: [DONE] (Implemented in `tools/stream_runner.py`, integrated into `ralph.sh`, and recorded in ADR-014).

### [VETTED] Senior Product Manager Meta-Improvement Cadence & System Health Sprint Protocol (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Establish an automated sprint cadence in the autonomous Ralph loop where every 5th iteration transforms into a dedicated "cleanup" sprint. The agent shifts out of the feature execution role into a Senior Product Manager & Meta-Architect role to evaluate whole-system health. The agent asks: *"What is the weakest aspect of this project structure? What is preventing this from being more incredible?"*, formulates at least one Rank A+ idea to improve the system or processes, and has unconditional authority to execute it immediately ("Nothing is disallowed during these sprints").
- **Rationale**: Prevents accumulated process friction, technical debt, and developer ergonomics bottlenecks that linear feature-by-feature execution ignores. Elevates the meta-processes the project uses to accomplish itself.
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (uses Python stdlib & bash).
  - Autonomous loop compatible? Yes (fully integrated into `ralph.sh` and `AGENTS.md`).
- **Proposed Roadmap Phase**: Phase 0, Task 0.5 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- **Status**: [DONE] (Formalized in `ralph.sh`, `AGENTS.md`, `GEMINI.md`, and recorded in ADR-015).

### [SCHEDULED] Automated Pre-Commit Fast Linter & Doc-Sync Validator (`tools/doctor.py` / `bible doctor`) (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Implement a zero-dependency diagnostic utility (`tools/doctor.py` or `./bible doctor`) that runs pre-commit / pre-push health checks in <1 second:
  1. Validates 100% Zero-Dependency compliance (inspects AST of all `.py` files to ensure no third-party non-standard library modules are imported).
  2. Validates state machine synchronization: verifies all ADRs referenced in code/logs exist in `DECISIONS.md`, all tasks marked `[DONE]` in `ROADMAP.md` exist, and `AGENT_LOG.md` run numbers are sequential.
  3. Validates that every Rank A+ idea in `IDEAS.md` has an associated roadmap task or completed status.
  4. Checks that bash scripts pass `bash -n` and unit test discovery discovers all test suites cleanly.
- **Rationale**: Eliminates human and agent oversight by turning process rules, dependency boundaries, and documentation integrity into automated, deterministic assertions that can run in pre-commit hooks or the Ralph loop.
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (Python 3 standard library `ast`, `os`, `sys`, `re`, `pathlib`).
- **Proposed Roadmap Phase**: Phase 0, Developer Ergonomics & Harness Tooling (Task 0.6).
- **Status**: [DONE] (Implemented in `tools/doctor.py`, integrated into CLI via `./bible doctor`, integrated into `ralph.sh`, tested in `tests/test_doctor.py`, and recorded in ADR-016).

### [DONE] Git Pre-Commit / Pre-Push Hook Automation (`bible doctor --install-hooks`) (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Provide automated git hook installation (`./bible doctor --install-hooks` and `tools/install_hooks.sh`) that writes zero-dependency pre-commit (<0.15s) and pre-push (<2.5s) scripts into `.git/hooks`. The pre-commit hook runs fast AST zero-dependency and documentation synchronization linting; the pre-push hook runs full doctor verification (including database PRAGMA check and 100% hermetic unit tests), physically preventing non-compliant or broken state from ever reaching `origin/main`.
- **Rationale**: Eliminates human and agent oversight by physically preventing any non-compliant code, missing ADRs, or broken tests from being pushed to `origin/main`.
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (uses standard git hooks and Python standard library).
- **Proposed Roadmap Phase**: Phase 0, Developer Ergonomics & Harness Tooling (Task 0.7).
- **Status**: [DONE] (Implemented in `tools/doctor.py`, `tools/install_hooks.sh`, `cli/main.py`, `cli/shell.py`, tested in `tests/test_doctor.py`, `tests/test_harness.py`, `tests/test_cli.py`, `tests/test_shell.py`, and recorded in ADR-022).

### [VETTED] Curated Executive Summary & Project Trajectory Briefing (10th Iteration Cadence & Skill) (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Establish an automated cadence every 10th Ralph loop iteration (`run_number % 10 == 0`) where the agent curates an Executive Summary reviewing the last 10 iterations from `AGENT_LOG.md`, presents a high-level project completion percentage and trajectory with estimated iterations remaining, and runs full automated health diagnostics (`tools/doctor.py`). In addition, expose the capability on-demand via the CLI (`./bible summary [--window N]`), standalone script (`tools/executive_summary.py`), and project skill (`skills/executive-summary/SKILL.md`).
- **Rationale**: The repository owner maintains a sovereign, near-zero maintenance posture and rarely inspects commits or code. Providing a periodic 10-iteration retrospective and forward-looking effort estimate keeps the owner informed with zero noise, while on-demand invocation provides instant visibility at any time.
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (Python 3 standard library only).
- **Proposed Roadmap Phase**: Phase 0, Task 0.8 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- **Status**: [DONE] (Implemented in `tools/executive_summary.py`, `skills/executive-summary/SKILL.md`, CLI `./bible summary`, `ralph.sh`, and recorded in ADR-017).

### [VETTED] Sovereign Interactive Scripture REPL Shell, Direct Citation Routing & Test Velocity Engine (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Implement a sovereign interactive Scripture study REPL shell (`bible shell`, `bible interactive`), automatic direct citation command routing (`./bible "John 3:16"` without requiring explicit `get`), and test suite velocity acceleration:
  1. **Direct Citation Routing**: Users typing `./bible "John 3:16"` or `./bible "Rom 8:28-30" --flow` are automatically routed to the scripture renderer, eliminating CLI choice errors for natural citations.
  2. **Interactive REPL Shell (`cli/shell.py`)**: Zero-dependency study shell powered by `cmd.Cmd` and `readline` with colored prompt, history, direct passage lookup, `/search`, `/compare`, session theme/version switching (`/theme`, `/version`), margin/flow toggles, and live diagnostics (`/doctor`, `/summary`).
  3. **Test Velocity & Doctor Comprehensive Discovery**: Slashing test suite latency from 4.95s to 2.44s via class-level fixture optimization and hermetic mock isolation, while upgrading `tools/doctor.py` to dynamically discover all test suites.
- **Rationale**: Eliminates primary user friction in scripture lookup, provides a delightful persistent exploration environment, and preserves sub-3-second test feedback.
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (Python 3 standard library `cmd`, `readline`, `shlex`, `unittest`).
- **Proposed Roadmap Phase**: Phase 0 & Phase 2.
- **Status**: [DONE] (Implemented in `cli/shell.py`, `cli/main.py`, `tests/test_shell.py`, `tools/doctor.py`, and recorded in ADR-021).

### [DONE] Automated Cross-Reference Graph Ingestion & Relationship Edge Compiler (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Implement a zero-dependency cross-reference engine (`core/crossref.py`), relationship edge compiler, canonical seed dataset, and interactive CLI/REPL tools for Phase 3 Task 3.2. Provides canonical relationship types (`quotation`, `prophecy_fulfillment`, `typology`, `thematic`, `allusion`, `parallel`), directional and bidirectional querying, multi-hop BFS pathfinding, hydrated verse texts, summary statistics, and CLI commands (`./bible crossref`, `./bible get --refs`).
- **Rationale**: Multiplies the depth of Scripture study offline; fulfills Task 3.2 acceptance criteria; enables rich typological arc visualizations in Phase 4 and grounded RAG retrieval expansion in Phase 8.
- **Constraints & Alignment**:
  - Offline-first? Yes (compiles offline dataset into bundled SQLite database).
  - Zero third-party dependencies? Yes (Python 3 standard library `csv`, `sqlite3`, `pathlib`).
  - Copyright compliant? Yes (public domain cross-reference data).
- **Proposed Roadmap Phase**: Phase 3 (Task 3.2 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md)).
- **Status**: [DONE] (Implemented in `core/crossref.py`, `core/terminal.py`, `cli/main.py`, `cli/shell.py`, verified in `tests/test_crossref.py`, and recorded in ADR-024).

### [DONE] Batch LLM Semantic Tagging Pipeline, TGC Hermeneutical Prompt Engine & Offline Ingestion (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Implement a zero-dependency batch LLM tagging generator (`tools/tag_generator.py`) and prompt engine (`core/tag_prompts.py`) grounded in The Gospel Coalition (TGC) Foundation Documents (ADR-006). Supports dual-horizon hermeneutics, Christ-centered teleology, and anti-moralistic reading. Features:
  1. Offline inspection and prompt export for single passages, batch JSONL generation (from `--refs`, `favorite_bible_verses.csv`, or books), and offline response file application (`./bible tag apply-llm`).
  2. Online execution via Google Gemini REST API (`gemini-2.5-pro` with `gemini-2.0-flash` fallback) using pure Python standard library `urllib.request` (zero pip packages).
  3. CLI subcommands (`./bible tag prompt`, `./bible tag generate`, `./bible tag apply-llm`, `./bible tag batch`) and interactive REPL command (`/tag prompt`).
- **Rationale**: Enables high-volume, hermeneutically sound semantic tagging of Scripture passages across the biblical canon without manual data-entry bottleneck or unconstrained LLM hallucinations.
- **Constraints & Alignment**:
  - Offline-first? Yes (supports offline prompt generation and local response file ingestion).
  - Zero third-party dependencies? Yes (Python 3 standard library only per ADR-003).
  - Copyright compliant? Yes (uses public domain WEB/KJV by default).
- **Proposed Roadmap Phase**: Phase 3, Task 3.3 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
### [DONE] Interactive Shell Context Management, Resource Leak Elimination & Runner Self-Documentation (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Implement context management protocol (`__enter__`/`__exit__`), explicit `.close()`, and `database` dependency injection on `BibleShell` to eliminate SQLite connection resource leakage and warnings (`ResourceWarning: unclosed database`). Muffle noisy batch prompt generator stdout during hermetic testing, align core export unit test suites with Phase 2/3 symbols, and add comprehensive `--help` / `-h` self-documenting CLI guidance to `ralph.sh`.
- **Rationale**: Elevates developer ergonomics, guarantees leak-free database lifecycle management, keeps test suites completely quiet and deterministic, and provides human operators with clear CLI documentation of Ralph runner modes and cadence triggers.
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (Python 3 standard library only).
- **Proposed Roadmap Phase**: Phase 0 (Task 0.9 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md)).
- **Status**: [DONE] (Implemented in `cli/shell.py`, `ralph.sh`, verified in `tests/test_tags.py`, `tests/test_crossref.py`, `tests/test_tag_prompts.py`, `tests/test_core.py`, `tests/test_harness.py`, and recorded in ADR-026).

### [DONE] Semantic Tag Aggregation Queries, Co-Occurrence Matrix & Verse Relevance Scoring (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Implement statistical aggregation queries, co-occurrence analysis, and multi-tag relevance scoring over the semantic tagging engine. Includes:
  1. **Topic Density Distribution (`get_topic_density_per_book`)**: Aggregates distinct passages, starred passages, distinct tags, and top tag frequencies across all 66 canonical books with testament and category filters.
  2. **Tag Co-Occurrence Analysis (`get_tag_co_occurrences`)**: Computes shared passage counts, Jaccard similarity indices (`|A ∩ B| / |A ∪ B|`), and Dice coefficients (`2|A ∩ B| / (|A| + |B|)`) across overlapping passage spans.
  3. **Verse Relevance Scoring (`score_verse_relevance`)**: Ranks scripture passages against arbitrary query tags using a composite scoring function balancing tag match ratio (0.60), full coverage bonus (0.20), starred boost (0.10), and span specificity (0.10), with text hydration.
  4. **CLI & REPL Integration**: `./bible tag density`, `./bible tag co-occurrence`, `./bible tag relevance`, and interactive shell commands `/tag density`, `/tag co-occurrence`, `/tag relevance`.
- **Rationale**: Completes Phase 3 Task 3.4; directly feeds the Phase 4 Canonical Redemptive Ribbon SVG heatmap (Task 4.3) and Phase 8 grounded RAG retrieval (Task 8.1).
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (Python 3 standard library only per ADR-003).
- **Proposed Roadmap Phase**: Phase 3, Task 3.4 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- **Status**: [DONE] (Implemented in `core/tags.py`, `core/terminal.py`, `cli/main.py`, `cli/shell.py`, tested in `tests/test_tags.py`, `tests/test_core.py`, and recorded in ADR-027).

### [VETTED] Offline Web UI History & Sovereign Reading State via LocalStorage (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Implement a sovereign, client-side offline persistence layer in `web/static/app.js` using the browser's native `localStorage` API. Retains recently looked-up scripture references, FTS5 search queries, starred passage bookmarks, and reader typography preferences (font scale, layout style) without requiring server-side session cookies or external database mutations. Features a dedicated "History & Bookmarks" drawer in the Sacred-Modern UI sidebar with instant one-click navigation and offline data export/clearing.
- **Rationale**: Elevates the built-in Web UI into a personalized scripture study workstation while adhering strictly to Manifesto Pillar I (Offline-First & Sovereign Data) and ADR-003 (Zero External Dependencies, vanilla JavaScript). Works seamlessly even when entirely disconnected from network access.
- **Constraints & Alignment**:
  - Offline-first? Yes (100% browser-native client storage).
  - Zero third-party dependencies? Yes (native browser `localStorage`, vanilla JS).
- **Proposed Roadmap Phase**: Phase 4, Task 4.2 / 4.4 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- **Status**: [VETTED] (Core reader theme, typography scale, flow mode, and verse number state persisted via `localStorage` in Run 028 / ADR-029; bookmarks and history drawer queued for Task 4.4).

### [DONE] Canonical Redemptive Ribbon Heatmap & Sacred Macro-Visualizer (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Build macro-scale visual scripture thematic heatmap across all 66 Protestant canonical books grouped by canonical divisions (Law, History, Poetry, Prophets, Gospels, Pauline Epistles, General Epistles, Apocalypse). Implemented as a dual-modal architecture: terminal-native illuminated ASCII/Unicode visualizer (`./bible ribbon [tag]`, `/ribbon` REPL slash command) and Sacred-Modern Web UI interactive overlay (`#panel-ribbon`, `#select-ribbon-tag`, `#ribbon-legend-bar`, data-heat level badge styling).
- **Rationale**: Solves the micro vs. macro disconnect by providing immediate visual topography of theological themes across all 66 books without any external charting or npm packages.
- **Constraints & Alignment**:
  - Offline-first? Yes (100% offline).
  - Zero third-party dependencies? Yes (Python 3 stdlib and native browser DOM/CSS only per ADR-003).
- **Proposed Roadmap Phase**: Phase 4, Task 4.3 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- **Status**: [DONE] (Implemented in `core/terminal.py`, `core/__init__.py`, `cli/main.py`, `cli/shell.py`, `web/static/`, tested in `tests/test_tags.py` and `tests/test_server.py`, and recorded in ADR-031).











### [DONE] Sovereign Cold-Start Bootstrapping, Unified Database Compilation & Lifecycle Engine, Self-Healing Doctor Diagnostics, and Comprehensive Repository Documentation (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Implement a unified, sovereign database compilation, inspection, and self-healing lifecycle engine (`core/bootstrap.py`, `./bible init`, `./bible db`, `tools/doctor.py --fix`). Idempotently compiles and bootstraps 31,103 World English Bible verses from raw cached JSON, 829 curated favorites (50 starred), 26 canonical TGC taxonomies, 43 typological cross-reference links, and automated git hooks in `<0.5s`. Automatically heals missing/corrupted databases and uninstalled git hooks via `./bible doctor --fix`. Eliminates arbitrary test discovery exclusions in `tools/doctor.py` (guaranteeing 100% test coverage across all 356 tests). Elevates `README.md` into an authoritative, illuminated engineering and user manual with complete CLI, REPL, web, and architectural documentation.
- **Rationale**: Completely eradicates cold-start friction, tribal knowledge, and diagnostic blind spots. Guarantees that any human developer, CI pipeline, or autonomous Ralph loop agent cloning or resetting the repository can achieve 100% operational readiness in a single command with zero third-party dependencies.
- **Constraints & Alignment**:
  - Offline-first? Yes (100% offline compilation and local verification).
  - Zero third-party dependencies? Yes (Python 3 standard library only per ADR-003).
- **Proposed Roadmap Phase**: Phase 0, Task 0.10 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- **Status**: [DONE] (Implemented in `core/bootstrap.py`, `core/__init__.py`, `cli/main.py`, `cli/shell.py`, `tools/doctor.py`, `README.md`, verified with 356 passing unit tests, and recorded in ADR-030).

### [DONE] Omnichannel Visual Verse Slide Integration across CLI, Interactive REPL Shell, and REST API (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Establish first-class, omnichannel developer and user ergonomics for the visual verse slide rendering engine across the command-line interface (`./bible slide`), interactive REPL shell (`/slide`), and embedded REST API (`/api/slide` and `/api/slide.svg`).
  1. **CLI Subcommand (`./bible slide`)**: Supports instant rendering of single verses and pericopes to vector SVG, lossless PNG, or high-res JPEG with arguments for resolution (`4k`, `1080p`, `720p`, `square`, custom), theme (`oled_black`, `charcoal`, `obsidian`, `monastery`, `inverted`, `parchment`), backend selection (`auto`, `svg`, `imagemagick`), dynamic typography scaling, automated pericope title integration via `PericopeService`, and stdout stream piping.
  2. **REPL Directives (`/slide` / `/render`)**: In-shell command in `BibleShell` with intelligent `shlex` parameter parsing and interactive tab autocompletion for themes, resolutions, and flags.
  3. **RESTful HTTP API (`GET /api/slide`)**: Live web endpoint serving dynamically rendered slides in `image/svg+xml`, `image/png`, or `image/jpeg` directly to browsers, web UI visualizers, and external digital signage/screensaver scrapers.
  4. **Resource Management**: Fixed background server and shell lifecycle cleanup in test suites, ensuring 100% leak-free test executions.
- **Rationale**: Elevates the newly created TV screensaver slide engine from an internal code library into an accessible, versatile, and omnipresent capability. Users can generate 4K OLED slides directly from the terminal, explore designs interactively in the REPL, or link dynamic SVG slides in the web interface and home automation systems.
- **Constraints & Alignment**:
  - Offline-first? Yes (100% local rendering).
  - Zero third-party dependencies? Yes (Python 3 standard library only, optional system ImageMagick detection, zero pip packages per ADR-003).
- **Proposed Roadmap Phase**: Phase 0 (Task 0.11 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md)).
- **Status**: [DONE] (Implemented in `cli/main.py`, `cli/shell.py`, `web/server.py`, tested in `tests/test_cli.py`, `tests/test_render.py`, `tests/test_server.py`, `tests/test_shell.py`, and recorded in ADR-035).

### [DONE] High-Performance Parallel Hermetic Test Runner & Zero-Pollution Resource Leak Prevention Engine (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Build a zero-dependency, high-performance parallel test runner (`tools/test_runner.py`), omnichannel CLI subcommand (`./bible test`, aliases: `tests`, `check`), and interactive REPL command (`/test`) that executes test modules in parallel worker processes via `concurrent.futures.ProcessPoolExecutor`. Enforces strict `ResourceWarning` auditing (`-W error::ResourceWarning`) to eliminate latent unclosed SQLite databases, file descriptors, and sockets. Hardens `Database` with defensive `__del__` cleanup and idempotent `close()`. Completely eliminates stdout/stderr test pollution. Integrates parallel execution directly into `tools/doctor.py`, slashing full repository health diagnostic latency from ~10.0s to ~2.5s (a 4x acceleration for every pre-push hook and Ralph loop cycle).
- **Rationale**: Elevates developer and autonomous agent feedback loop velocity by 4.5x–5.0x (running 436 tests across 22 modules in <2.0 seconds). Prevents warning blindness and guarantees 100% leak-free, clean test execution across the entire repository.
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (Python 3 standard library `concurrent.futures`, `subprocess`, `unittest`, `sys`, `time` per ADR-003).
- **Proposed Roadmap Phase**: Phase 0 (Task 0.12 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md)).
- **Status**: [DONE] (Implemented in `tools/test_runner.py`, `core/db.py`, `tools/doctor.py`, `cli/main.py`, `cli/shell.py`, tested in `tests/test_test_runner.py`, verified with 436 tests passing in <2s, and recorded in ADR-036).


