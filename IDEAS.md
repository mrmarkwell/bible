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
- **Status**: Scheduled in Phases 3 and 4 of [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).

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
- **Status**: [SCHEDULED].

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

### [SCHEDULED] Git Pre-Commit / Pre-Push Hook Automation (`bible doctor --install-hook`) (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Provide automated git hook installation (`./bible doctor --install-hook` or `tools/install_hooks.sh`) that writes a zero-dependency pre-commit/pre-push script to `.git/hooks/pre-push`. The hook runs `python3 tools/doctor.py`, preventing any git push from completing if AST dependency violations, documentation desynchronization, or failing tests are detected.
- **Rationale**: Eliminates human and agent oversight by physically preventing any non-compliant code or broken state from being pushed to `origin/main`.
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (uses standard git hooks and Python standard library).
- **Proposed Roadmap Phase**: Phase 0, Developer Ergonomics & Harness Tooling (Task 0.7).
- **Status**: [SCHEDULED].


