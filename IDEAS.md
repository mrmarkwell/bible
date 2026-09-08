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

### [VETTED] Sovereign Test Suite Latency Decoupling, Semantic Audit Cache Ledger & Straggler Telemetry Engine (Rank A+)
- **Summary**: Implement persistent path-keyed audit cache ledgers (`.semantic_audit_cache.json`) for instant database integrity verification, optimize cold-start bootstrap checks (<0.01s), add straggler telemetry and latency leaderboards to `tools/test_runner.py` (`--slowest`, `--warn-latency`), wire into CLI (`./bible test`) and REPL (`/test`), and prune static analysis warnings across core modules.
- **Rationale**: Eliminates uncached whole-database disk scans on 168MB databases, slashing `test_bootstrap` runtime by 18x (5.4s -> 0.28s) and `test_doctor` by 3x (7.9s -> 2.7s), reducing overall `tools/doctor.py` pre-push latency from 11.7s to 9.4s, and providing developers and autonomous agents with proactive latency bottleneck observability.
- **Constraints & Alignment**:
  - Offline-first? Yes (pure local filesystem and SQLite version counters).
  - Zero third-party dependencies? Yes (Python standard library only per ADR-003).
  - High performance? Yes (audit validation in <0.01s).
- **Proposed Roadmap Phase**: Phase 0 (Task 0.27 / ADR-081).
- **Status**: Implemented via ADR-081 and Task 0.27.

### [VETTED] Sovereign Interactive REPL Persona Studio, Module-Test Symmetry Sentry, and Static Hygiene Pruning (Rank A+)
- **Summary**: Implement interactive biblical character dialogue capabilities (`/chat`, `/persona`, `/characters`) directly into the sovereign interactive study REPL console (`cli/shell.py`), create a dedicated hermetic unit test suite for `tools/ci.py` (`tests/test_ci.py`), add an automated Module-Test Symmetry diagnostic to `tools/doctor.py`, fix dotted import resolution in `tools/linter.py`, and modernize the GitHub Actions CI matrix to include Python 3.13.
- **Rationale**: Achieves complete capability parity between CLI and interactive REPL, ensuring scholars and readers can converse with all 19 canonical personas in the interactive shell. Eliminates the repository's single untested production tool (`tools/ci.py`), enforces test symmetry so no orphaned tools can slip in, eliminates linter false positives, and ensures Python 3.13 CI coverage.
- **Constraints & Alignment**:
  - Offline-first? Yes (instant canonical offline profile card fallback in unkeyed environments).
  - Zero third-party dependencies? Yes (Python standard library only per ADR-003).
  - High performance? Yes (symmetry check <0.15s, REPL character dialogues instant).
- **Proposed Roadmap Phase**: Phase 0 (Task 0.23 / ADR-069).
- **Status**: Implemented via ADR-069 and Task 0.23.

### [VETTED] Omnichannel CI Status Engine, Dedicated Semantic Compiler Test Symmetry, and Static Analysis Hygiene (Rank A+)
- **Summary**: Integrate sovereign GitHub Actions monitoring directly into the CLI (`./bible ci`) and interactive study REPL (`/ci`), add a dedicated hermetic unit test suite for `tools/build_semantic_db.py` (`tests/test_build_semantic_db.py`) achieving 90.4% coverage and establishing pure 1-to-1 module-test symmetry, and prune unused imports across test and ingestion modules.
- **Rationale**: Elevates developer and autonomous runner ergonomics by enabling instant CI workflow inspection without leaving the terminal, eliminates the sole untested compiler module blind spot, and maintains pristine zero-lint cleanliness.
- **Constraints & Alignment**:
  - Offline-first? Yes (gracefully reports offline or token state; mock tests hermetic).
  - Zero third-party dependencies? Yes (Python standard library `urllib.request`, `json`, `subprocess` per ADR-003).
  - High performance? Yes (instant API response, 18 compiler unit tests run in <0.04s).
- **Proposed Roadmap Phase**: Phase 0 (Task 0.24 / ADR-070).
- **Status**: Implemented via ADR-070 and Task 0.24.

### [VETTED] Real-Time Server-Sent Events (SSE) Streaming for Web Studio (`/api/chat/stream` & `/api/rag/stream`) (Rank A+)
- **Summary**: Expose HTTP Server-Sent Events (`text/event-stream`) endpoints in `web/server.py` (`/api/chat/stream` and `/api/rag/stream`) connecting directly to `BiblicalPersonaSession.say_stream()` and `GeminiClient.generate_stream()` to deliver real-time token streaming to the browser.
- **Rationale**: While unary REST endpoints (`/api/chat/persona` and `/api/rag`) return complete JSON responses after full LLM generation completes, complex theological questions can take 2–5 seconds to fully synthesize. Real-time token streaming provides an instant, responsive "typewriter" experience in the upcoming Web UI (Task 8.6), reducing perceived latency to under 200ms.
- **Constraints & Alignment**:
  - Offline-first? Yes (emits immediate fallback event with full profile card when offline).
  - Zero third-party dependencies? Yes (Python standard library `http.server` chunked transfer and SSE formatting per ADR-003).
  - High performance? Yes (token streaming as generated by Google Gemini API).
- **Proposed Roadmap Phase**: Phase 8 (Task 8.6 enablement).
- **Suggested Tasks**:
  - [ ] Implement SSE response writer in `web/server.py` streaming chunks with `data: {"token": "..."}\n\n`.
  - [ ] Connect `/api/chat/stream` to `BiblicalPersonaSession.say_stream()`.
  - [ ] Connect `/api/rag/stream` to streaming RAG answer pipeline.
  - [ ] Add hermetic unit tests verifying SSE stream chunking and offline fallback events.

### [VETTED] Persistent Multi-Turn Character Dialogue Transcripts & Markdown Export (Rank A+)
- **Summary**: Enhance the Biblical Character Dialogue Studio (`core/persona.py` / `./bible chat`) to support persistent session saving (`--save-session`, `/save`), resuming prior conversations (`--resume <id>`), and exporting dialogues to beautifully formatted Markdown or JSON transcripts (`--export-transcript`).
- **Rationale**: Currently, interactive terminal REPL conversations exist in ephemeral memory and evaporate when exiting the session. Allowing users and scholars to persist and export their theological dialogues with biblical characters (e.g., discussions with Paul on Romans 8 or Moses on Deuteronomy 18) turns conversations into permanent study notes and devotional study aids.
- **Constraints & Alignment**:
  - Offline-first? Yes (saves to local JSON files in `data/sessions/`).
  - Zero third-party dependencies? Yes (Python standard library `json` and file I/O per ADR-003).
  - High performance? Yes (<1ms file operations).
- **Proposed Roadmap Phase**: Phase 8 (Online Scripture RAG & Biblical Character Dialogue Studio).
- **Suggested Tasks**:
  - [ ] Implement `DialogueTranscript` serializer and session persistence engine in `core/persona.py`.
  - [ ] Add CLI flags `--save`, `--resume`, and `--export` to `./bible chat` and `/save` command in REPL.
  - [ ] Add hermetic unit tests verifying session serialization, persistence, and markdown export.

### [VETTED] Hierarchical Agent Log Action Parser & Bugfix Archetype Telemetry (Rank A+)
- **Summary**: Modernize the retrospective reporting and trajectory engine (`tools/executive_summary.py` / `./bible summary`) to perform hierarchical bullet extraction synthesizing bold headings with nested sub-bullets into comprehensive action highlights, recognize dedicated bug triage sprints (`bugfix` archetype), resolve task and phase names cleanly, and eliminate redundant phase prefixes.
- **Rationale**: Elevates the executive summary briefing from displaying hollow headings (`**Heading**:`) to fully informative summaries of implemented work and metrics across all past iterations, providing accurate trajectory visibility for both humans and autonomous agents.
- **Constraints & Alignment**:
  - Offline-first? Yes (pure local text and log parsing).
  - Zero third-party dependencies? Yes (Python standard library only per ADR-003).
  - High performance? Yes (parses all 60+ runs in <0.01s).
- **Proposed Roadmap Phase**: Phase 0 (Task 0.22 / ADR-065).
- **Status**: Implemented via ADR-065 and Task 0.22.

### [VETTED] Adaptive Test Scheduling (LPT Heuristic) & Test Suite Latency Halving (Rank A+)
- **Summary**: Implement sovereign Longest Processing Time (LPT) parallel test execution scheduling with atomic historical timing cache (`.test_timing_cache.json`) in `tools/test_runner.py`. Eliminate worker thread idle starvation and straggler tail latency, alongside isolating full-tree AST and linter audits in composite tests.
- **Rationale**: Keeps total test execution latency strictly below 2.5s (slashing previous 4.8s runtime by 48.5%) and accelerates system health audits to 4.0s, safeguarding the <5.0s SLA as Phase 8 test suites expand.
- **Constraints & Alignment**:
  - Offline-first? Yes (local JSON timing cache).
  - Zero third-party dependencies? Yes (Python standard library only per ADR-003).
  - Test hermeticity & reliability? Yes (deterministic LPT scheduling with fallback to file size).
- **Proposed Roadmap Phase**: Phase 0 (Task 0.21 / ADR-064).
- **Status**: Implemented via ADR-064.

### [VETTED] Autonomous GitHub Issue Triage & Bug Resolution Engine (Rank A+)
- **Summary**: Real-time triage and resolution of open GitHub issues/bug reports during autonomous Ralph loop execution cycles. The agent prioritizes open issues at boot, reproducing and fixing the bug with regression tests, closing as irrelevant/duplicate/unplanned with reasons, or commenting on diagnostic progress.
- **Rationale**: Bridges external feedback and bug reports directly into the autonomous Ralph loop. Allows the system to maintain itself and respond to users and bug reports without human maintainer intervention.
- **Constraints & Alignment**:
  - Offline-first? Yes (falls back gracefully if network is offline or unauthenticated).
  - Zero third-party dependencies? Yes (Python standard library `urllib.request` and `json` only, zero pip packages per ADR-003).
  - Autonomous permission auto-approval? Yes (`--dangerously-skip-permissions`).
- **Proposed Roadmap Phase**: Phase 0 (Task 0.20 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md) / ADR-059).
- **Status**: Implemented via ADR-059 and Task 0.20.

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
- **Status**: Tasks 5.1, 5.2, and 5.3 implemented (ADR-034, ADR-037, ADR-038). Multi-slide pagination (Task 5.4) and batch export (Task 5.5) active in Phase 5.

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
  - **Biblical Humility & Canonical Realism**: Characters are not presented as flawless heroes to be blindly imitated, but as fallen human beings saved solely by God's sovereign mercy and grace, walking in genuine, Spirit-wrought faith. David speaks openly of his sin and desperate need for cleansing (Psalm 51); Peter of his denials and restoration by Christ.
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
- **Summary**: Implement a zero-dependency batch LLM tagging generator (`tools/tag_generator.py`) and prompt engine (`core/tag_prompts.py`) grounded in The Gospel Coalition (TGC) Foundation Documents (ADR-006, THEOLOGY.md). Supports dual-horizon hermeneutics, Christ-centered teleology, and gospel uniqueness (grace-driven application). Features:
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

### [VETTED] Smart Batch Slide Exporter and Album Compilation Generator (`bible slide-batch`) (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Implement a high-performance batch slide generation engine (`./bible slide-batch` / `SlideRenderEngine.render_batch()`) capable of exporting entire reading lists, favorite collections, thematic tags, pericopes, or custom biblical canons into structured slide albums ready for Google Photos / Apple Photos TV screensaver syncing. Features:
  1. **Album Organization & Naming Patterns**: Configurable folder structures and zero-padded filenames (e.g., `exports/slides/romans/{page_index:03d}_{citation_slug}.svg` or `.png`).
  2. **Index / Manifest Generation**: Automatic creation of an `index.html` visual gallery, `manifest.json`, and text-based slide index for quick previewing and verification.
  3. **Parallel Multiprocessing Rendering**: Leverage Python `concurrent.futures.ProcessPoolExecutor` to render hundreds of 4K slides concurrently in seconds without external dependencies.
  4. **Dynamic Metadata Embedding**: Inject Dublin Core / SVG metadata into rendered slides with canonical citations, translation version, theme, and generation timestamps.
- **Rationale**: While single-passage and multi-slide pagination are now fully operational, users displaying scripture on home televisions need collections of dozens or hundreds of curated slides (e.g. all Psalms of Ascent, Romans 8, or Top 50 Favorite Verses) exported cleanly in one command.
- **Constraints & Alignment**:
  - Offline-first? Yes (100% local rendering).
  - Zero third-party dependencies? Yes (Python 3 standard library only per ADR-003).
- **Proposed Roadmap Phase**: Phase 5 (Task 5.5 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md)).
- **Status**: Scheduled (Task 5.5 in Phase 5).

### [DONE] Sovereign Zero-Dependency Static Analysis, Code Hygiene & Linter Engine (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Build a zero-dependency static analysis, code quality, and formatting linter (`tools/linter.py`), CLI subcommand (`./bible lint`, aliases: `linter`, `check-style`), and REPL command (`/lint`) that audits 100% of Python source files in <0.08s:
  1. **AST Code Smells**: Detects duplicate dictionary keys (`E101`, fixing the latent collision `'jud'` in `core/reference.py`), mutable default argument values (`E102`), bare `except:` clauses (`E103`), unused imports (`W201`), wildcard imports (`W202`), and unreachable code (`W203`).
  2. **Line Hygiene & Formatting**: Detects trailing whitespace (`S301`), missing final newlines (`S302`), excessive blank lines (`S303`), and tab characters (`S304`).
  3. **Self-Healing Auto-Repair (`--fix`)**: Automatically strips trailing whitespace, normalizes terminating newlines to UNIX `\n`, and defragments excessive blank lines.
  4. **Pre-Commit & Doctor Integration**: Added Check 5 (`Code Quality`) to `tools/doctor.py` (running in fast mode and full diagnostics) and automated git pre-commit hooks.
- **Rationale**: Elevates developer and autonomous agent ergonomics by providing instant static analysis parity with modern industrial toolchains without adding a single external pip package, strictly preserving ADR-003 zero-maintenance and zero-dependency guarantees.
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (Python 3 standard library `ast`, `py_compile`, `dataclasses`, `pathlib` per ADR-003).
- **Proposed Roadmap Phase**: Phase 0 (Task 0.13 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md)).
- **Status**: [DONE] (Implemented in `tools/linter.py`, `core/reference.py`, `tools/doctor.py`, `cli/main.py`, `cli/shell.py`, tested in `tests/test_linter.py`, verified with 492 tests passing, and recorded in ADR-040).

### [VETTED] ESV API as Primary Translation with Compliant 500-Verse Ephemeral LRU Caching & Offline Metadata Decoupling (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Integrate the English Standard Version (ESV) as the primary system-wide default translation (`DEFAULT_TRANSLATION = "ESV"`) across the CLI (`./bible get`, `./bible search`, `./bible slide`), Web UI reader, and Phase 6 LLM prompt pipelines, while adhering 100% to Crossway's official Terms of Service:
  1. **Zero-Dependency ESV API Client (`core/esv.py`)**: Built on Python standard library `urllib.request` and `json` per ADR-003, reading `ESV_API_KEY` from environment/config.
  2. **Crossway-Compliant 500-Verse Ephemeral LRU Cache**: Enforces Crossway's strict rule (*"You may not locally store more than 500 verses... You can cache up to 500 verses"*) via an ephemeral SQLite cache with LRU eviction, avoiding full-text hoarding while eliminating duplicate network roundtrips for repeated views or slides.
  3. **Decoupled Whole-Bible Offline Metadata**: All 66 Protestant books, 1,189 chapters, 31,103 canonical integer verse coordinates (`BBCCCVVV`), thematic density heatmaps, the Canonical Redemptive Ribbon, typological arc networks, and pericope outlines remain 100% offline and instantaneous in local SQLite (<5ms query time). Raw verse words are fetched on-demand only upon drill-down.
  4. **Resilient Offline Cascade**: Automatically and gracefully cascades to the bundled public-domain World English Bible (`WEB`) when offline or when no API key is present.
  5. **ESV-Driven LLM Semantic Tagging**: Phase 6 & 7 Gemini pipelines query ESV passage text for prompt context (within the 60 req/min quota), feeding modern formal-equivalence English to LLMs for superior theological precision, then storing synthesized metadata linked by canonical IDs.
- **Rationale**: Eliminates copyright infringement and DMCA risks associated with committing proprietary text blobs to public git repositories, fulfills user desire for ESV as primary translation, preserves instant whole-Bible visualizations offline, and dramatically improves LLM semantic reasoning accuracy.
- **Constraints & Alignment**:
  - Offline-first? Hybrid (whole-Bible metadata is 100% offline; raw ESV text is fetched on-demand with 500-verse LRU cache and offline WEB fallback).
  - Zero third-party dependencies? Yes (Python 3 standard library `urllib.request`, `json`, `sqlite3` per ADR-003).
  - Copyright compliant? 100% compliant with Crossway ESV API guidelines.
- **Proposed Roadmap Phase**: Phase 2 (Task 2.5 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md)) & Phase 6 (Task 6.1).
- **Status**: [VETTED] / Scheduled (Task 2.5 in Phase 2; ADR-041).

### [DONE] Public Open-Source Repository Governance & Permissive MIT Licensing (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Establish public open-source repository governance and adopt the standard, universally recognized permissive **MIT License** (`LICENSE`) for the Bible Engine codebase:
  1. Grants unrestricted rights to use, copy, modify, merge, publish, distribute, sublicense, and sell the software.
  2. Explicitly protects the authors with standard liability disclaimers.
  3. Formulates clear boundary between the open-source code and third-party copyrighted texts/APIs (such as Crossway's ESV API).
  4. Updates repository documentation (`MANIFESTO.md`, `README.md`) to reflect open-source status.
- **Rationale**: Enables the repository to be fully public, shared with church tech communities, showcased in professional portfolios, and contributed to by open-source collaborators without legal ambiguities.
- **Constraints & Alignment**:
  - Open-source standard? Yes (OSI-approved MIT License).
  - Copyright safety? Fully compliant with Crossway's requirement that ESV text is not released under Creative Commons, since code is MIT and text is fetched via API.
- **Proposed Roadmap Phase**: Phase 0 (Task 0.14 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md)).
- **Status**: [DONE] (Implemented in `LICENSE`, `MANIFESTO.md`, `ROADMAP.md`, and ADR-041).

### [VETTED] One-Shot ESV Semantic Understanding Database Compilation Pipeline (Rank A+)
- **Rank**: `A+` (Unambiguously a good idea for improvement)
- **Summary**: Implement a comprehensive, resumable, multi-pass batch analysis and compilation pipeline (`tools/build_semantic_db.py`) that systematically analyzes the complete text of the English Standard Version (ESV) to produce a sovereign, permanent semantic understanding database in local SQLite:
  1. **Layered Semantic Extraction**: Extracts 6 core semantic dimensions across all 66 canonical books:
     - *Discourse & Structural Hierarchy*: Pericopes (~2,800 units), literary genre, chiasm/parallelism, central exegetical propositions, and verse-level propositional rhetoric (ground, inference, purpose, contrast).
     - *Dual-Horizon Theological Semantics*: Redemptive-historical storyline epochs (Creation to New Creation), canonical thematic ribbons (Temple, Covenant, Seed, Priesthood), and systematic theological loci (Justification, Atonement, Sovereign Grace) grounded in The Gospel Coalition (TGC) Foundation Documents.
     - *Intertextual Graph*: Typological arcs connecting OT shadows to NT fulfillments with explicit theological correspondence, plus direct citations and allusions.
     - *Entity & Agency Network*: Canonical character profiles, agent-action-patient semantic triples, and contextual divine titles.
     - *Speech Acts & Devotional Tone*: Illocutionary force (imperative, promise, warning, indicative, lament, doxology) and emotional affect.
     - *Vector Geometry*: Quantized dense vector embeddings for all 31,102 verses and pericopes for zero-shot conceptual search.
  2. **Multi-Pass Quality Assurance & Verification**: Employs top-down book horizon context, low-temperature structured JSON prompting, an automated exegetical critic audit (checking canonical coordinate validity, theological coherence with THEOLOGY.md, and entity normalization), and a resumable SQLite ledger.
  3. **Offline Sovereignty & Legal Compliance**: Analyzes ESV text via one-time execution, storing derivative metadata, coordinates, and relational edges in SQLite without distributing raw copyrighted text files in the git repository (ADR-041).
- **Rationale**: The Bible is a static, closed canon that does not change. Performing an elite, high-compute semantic extraction once and saving the verified results into an immutable local SQLite database equips the Bible Engine with permanent, microsecond-latency theological intelligence offline without recurring API dependencies.
- **Constraints & Alignment**:
  - Offline-first? Yes (compiled SQLite database operates 100% offline).
  - Zero third-party dependencies? Yes (Python 3 standard library only per ADR-003).
  - Copyright compliant? Yes (derives metadata, tags, discourse graphs, and embeddings without redistributing raw text; complies with ADR-041).
- **Proposed Roadmap Phase**: Phase 7 (Tasks 7.1–7.6 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md); ADR-042).
- **Status**: [SCHEDULED] (Phase 7).

#### Detailed Technical Specifications & Implementation Instructions for Agents:

##### 1. Database Schema Specifications (`core/db.py`)
Add the following tables and indices to `core/db.py`:
- `pericopes`: `(id, book_id, start_canonical_id, end_canonical_id, human_ref, title, genre, literary_structure, central_proposition, redemptive_summary, created_at)`
- `discourse_relations`: `(id, source_canonical_id, target_canonical_id, relation_type, connective_word, explanation)` where `relation_type IN ('ground', 'inference', 'purpose', 'concession', 'contrast', 'condition')`
- `verse_theology`: `(id, start_canonical_id, end_canonical_id, theological_locus, primary_doctrine, storyline_epoch, thematic_ribbon, confidence, warrant_notes, created_at)`
- `typological_arcs`: `(id, type_start_id, type_end_id, type_label, antitype_start_id, antitype_end_id, antitype_label, theological_correspondence, warrant_level, created_at)` where `warrant_level IN ('explicit_nt_citation', 'canonical_thematic_pattern')`
- `semantic_propositions`: `(id, canonical_verse_id, speech_act, agent, action, patient, affect_tone, notes)` where `speech_act IN ('indicative', 'imperative', 'promise', 'warning', 'doxology', 'lament', 'prayer')`
- `verse_embeddings` & `pericope_embeddings`: `(id/canonical_id, model, dimensions, quantization, vector_blob BLOB)`

##### 2. Zero-Dependency Vector Engine (`core/vector.py`)
- Standard library `struct` packing (`int8` signed bytes: `b = struct.pack(f"{len(vec)}b", *quantized)`).
- Normalization: Scale float embeddings to unit norm, multiply by 127.0, and round to integer.
- Cosine similarity: Computed via integer dot-product: `sim = sum(a[i] * b[i]) / (127.0 * 127.0)`.
- Performance: Evaluates 31,102 verses in <15ms using pure standard library list comprehensions.

##### 3. Multi-Pass Batch Compilation Pipeline (`tools/build_semantic_db.py`)
- **Stage 1 (Book Horizons)**: Compute macro-outlines for each book (historical context, central theological message, authorial intent) cached in a staging dictionary.
- **Stage 2 (Pericope Processing)**: Iterate through all ~2,800 pericopes. For each pericope, construct prompt with: (a) Book Horizon, (b) Immediate preceding/following context, (c) Target ESV pericope text.
- **Stage 3 (Global Typology & Citations)**: Link OT types with NT fulfillments; map explicit NT citations of the OT.
- **Stage 4 (Vectorization)**: Compute dense embeddings using `text-embedding-004` and write quantized blobs to `verse_embeddings` and `pericope_embeddings`.
- **Stage 5 (Audit & Critic Gate)**: Run `core/semantic_audit.py` to verify:
  - 100% of generated verse coordinates match canonical ranges in `core/reference.py`.
  - Zero moralistic reductionism violations (asserts TGC Christ-centered framework).
  - Entity deduplication across persona names.
- **Stage 6 (Checkpoint Ledger)**: Maintain a table `compilation_ledger (pericope_id, status, error, updated_at)` enabling graceful pause, retry on transient HTTP errors, and immediate resumption.

##### 4. Verification & Testing Protocol
- Hermetic mock unit tests in `tests/test_semantic_db.py` verifying schema migrations, DTO serialization, vector search accuracy, and audit constraints on representative test passages (Genesis 1-3, Isaiah 53, Romans 8, Revelation 21-22).
- Zero third-party dependencies maintained (100% Python 3 standard library per ADR-003).

---

### [VETTED] Sovereign Zero-Dependency Code Coverage & Test Gap Detection Engine
- **Summary**: Build a pure Python 3 standard library code coverage engine (`tools/coverage.py`) that uses bytecode inspection (`code.co_lines()`) to discover executable statements across production files and traces test execution across parallel worker processes. Generates high-contrast ANSI terminal progress bars, calculates missing line intervals (e.g. `44, 46, 115-116`), enforces quality thresholds (`--fail-under`), and exports standalone Sacred-Modern HTML reports without any third-party pip packages.
- **Rationale**: Strict zero-dependency architecture (ADR-003) prevents using pip-installed coverage tools like `pytest-cov` or `coverage.py`. Without automated coverage metrics, developers and autonomous agents operate blind regarding which code paths are actually verified versus completely untested. A native standard library coverage tool provides instant visibility and enforces test coverage gates in CI and developer workflows.
- **Constraints & Alignment**:
  - Offline-first? Yes (operates 100% offline).
  - Zero third-party dependencies? Yes (Python 3 standard library `trace`, `compile`, and `ProcessPoolExecutor` only).
  - High performance? Yes (parallel multi-process tracing audits all test suites in ~12 seconds).
- **Proposed Roadmap Phase**: Phase 0 (Task 0.15; ADR-043).
- **Status**: [VETTED] (Implemented via Run 040 / ADR-043).

---

### [VETTED] Automated Chromecast & Google TV Web Gallery Cast Receiver
- **Summary**: Extend the Sacred-Modern slide album web gallery (`index.html` generated by `bible slide-batch` and served via `bible serve`) with Google Cast SDK integration and DIAL protocol autodiscovery. Users can tap a single "Cast to TV" button in Chrome or their mobile browser to beam high-resolution scripture slideshows directly to Chromecast, Google TV, Android TV, or smart screens without needing manual USB flash drives or Google Photos albums.
- **Rationale**: While local image folders work well with Google Photos or USB media players, casting directly from the browser or local web server to a Chromecast/Google TV device provides an effortless 10-foot living room experience. It combines real-time slide switching, ambient transitions, and zero setup for modern smart home environments.
- **Constraints & Alignment**:
  - Offline-first? Yes (runs over local LAN; uses vanilla JS Cast receiver API).
  - Zero third-party dependencies? Yes (native browser Cast framework via Google's official receiver CDN or local LAN websocket fallback; zero npm packages).
  - Copyright compliant? Yes (renders user's active local passages).
- **Proposed Roadmap Phase**: Phase 5 / Phase 4 (Task 5.6).
- **Suggested Tasks**:
  - [ ] Add Cast Sender API buttons to Sacred-Modern web gallery (`index.html`).
  - [ ] Support custom slideshow cycle timers, ambient transition speeds, and theme switching via remote web controller.
  - [ ] Add CLI cast initiation subcommand (`./bible cast --plan romans_road`).
- **Status**: [VETTED] (Rank A+; Promoted in Run 041).

---

### [DONE] Sovereign High-Velocity Performance Benchmark Engine, Statistical Latency Profiler & Regression Guard
- **Summary**: Build a pure Python 3 standard library statistical micro-benchmarking engine (`tools/benchmark.py`) that profiles critical engine workloads with nanosecond precision (`time.perf_counter_ns()`), computing mean, median, min, max, standard deviation, p90, p99, operations/second, and throughput (MB/s). Features persistent baseline snapshots (`.benchmark_baseline.json`), automated regression detection (`--fail-regression N%`), color-coded ANSI terminal reporting with delta indicators, standalone Sacred-Modern HTML dashboard export (`--html`), and omnichannel integration across CLI (`./bible bench`), REPL shell (`/bench`), and system doctor (`./bible doctor --bench`).
- **Rationale**: The Bible Engine's Manifesto mandates "instantaneous offline responsiveness" and "zero-latency scripture access." While unit tests guard correctness and linters guard syntax, the system previously had zero automated infrastructure to monitor runtime latency. Algorithmic regressions in reference parsing, SQLite queries, FTS5 search, ChaCha20-HMAC keystream generation, 4K SVG slide rendering, or AST analysis could degrade performance silently. A native benchmarking engine gives developers and autonomous agents quantitative feedback and enforces regression gates in CI and developer workflows.
- **Constraints & Alignment**:
  - Offline-first? Yes (operates 100% offline, zero network calls).
  - Zero third-party dependencies? Yes (Python 3 standard library `time`, `statistics`, `math`, `json`, `argparse` only per ADR-003).
  - High performance? Yes (high-velocity quick mode runs all 14 workloads in <2.7s; full runs in ~13s).
- **Proposed Roadmap Phase**: Phase 0 (Task 0.16; ADR-047).
- **Status**: [DONE] (Rank A+; Implemented in Run 044 / Senior PM Cleanup Sprint).

---

### [DONE] Zero-Dependency GitHub Actions Continuous Integration & Multi-Python Matrix Quality Guard
- **Summary**: Implement a comprehensive, zero-dependency GitHub Actions CI/CD automation workflow (`.github/workflows/ci.yml`) coupled with a native structural CI/CD validator in `tools/doctor.py` (`check_ci_workflows`). Executes continuous integration runs across Python versions 3.10, 3.11, and 3.12 without requiring any third-party pip packages, wheels, or virtual environments. Sequentially enforces the 6 core sovereign quality gates on every push and pull request: fast zero-dependency AST audit, automated database compilation (`./bible init`), system health diagnostics (`tools/doctor.py`), parallel hermetic unit test execution (`tools/test_runner.py`), sovereign static analysis (`tools/linter.py`), performance regression prevention (`tools/benchmark.py --quick --compare-baseline --fail-regression 50`), and statement coverage gating (`tools/coverage.py --threshold 70.0`).
- **Rationale**: The repository previously relied entirely on local git hooks (`pre-commit` and `pre-push`) for quality enforcement. While local hooks protect the workstation, GitHub remote branches had zero server-side verification. Any collaborator, web-based pull request, automated dependency sync, or out-of-band commit could push regressions, syntax defects, or external pip dependencies directly to `origin/main` undetected. Native GitHub Actions CI guarantees that every single commit pushed to GitHub is automatically verified against Python 3.10, 3.11, and 3.12 across all quality dimensions in under 45 seconds with 0 pip packages.
- **Constraints & Alignment**:
  - Offline-first? Yes (the engine itself requires zero network access; runner uses standard GitHub Ubuntu environment).
  - Zero third-party dependencies? Yes (uses official GitHub Actions `checkout@v4` and `setup-python@v5`; invokes 100% Python standard library tools).
  - Multi-version compatibility? Yes (explicitly verifies Python 3.10, 3.11, and 3.12).
- **Proposed Roadmap Phase**: Phase 0 (Task 0.17; ADR-048).
- **Status**: [DONE] (Rank A+; Implemented in Run 045 / Senior PM Cleanup Sprint).

---

### [VETTED] Hybrid FTS5 & Dense Vector Reciprocal Rank Fusion (RRF) Search Engine
- **Summary**: Build a hybrid search orchestrator (`core/hybrid_search.py`) that merges keyword results from SQLite FTS5 (BM25 ranking) with semantic vector results from `core/vector.py` (cosine similarity of user queries against the offline invariant scripture vector database) using Reciprocal Rank Fusion ($RRF = \sum \frac{1}{60 + \text{rank}_i}$). Supports `--hybrid` flag on `./bible search` and `/search` in the REPL shell, with configurable alpha balancing between lexical and semantic weights.
- **Rationale**: Lexical search alone misses conceptual synonyms and thematic parallels without keyword overlap, while pure vector search can occasionally miss exact phrase matches or rare biblical names. When a user enters a natural language inquiry or topic, hybrid RRF combines the literal keyword precision of BM25 with the conceptual depth of 768-dimensional dense vectors matched against the pre-computed whole-Bible vector database, delivering the ultimate scripture discovery experience.
- **Constraints & Alignment**:
  - Offline-first? Yes (operates locally over SQLite FTS5 and pre-computed packed int8 vectors).
  - Zero third-party dependencies? Yes (pure Python standard library math and sorting).
  - High performance? Yes (merging two top-100 lists takes <0.2ms).
- **Proposed Roadmap Phase**: Phase 7 / Phase 8 (Task 7.7 / Task 8.1; ADR-076).
- **Status**: [VETTED] (Rank A+; Promoted in Run 048).

---

### [DONE] Sovereign System Health Acceleration, Deep Semantic Schema Validation & Machine-Readable Telemetry Engine
- **Summary**: Modernize and accelerate the system health diagnostic suite (`tools/doctor.py`), refactor unit test benchmark isolation in `tests/test_benchmark.py` and `tests/test_doctor.py` to restore the strict <5.0-second test velocity mandate (achieving 653 tests in 3.83s, a 38% speedup), expand database health diagnostics to verify foreign keys (`PRAGMA foreign_key_check`) and the 6-layer Phase 7 semantic tables/columns with non-destructive self-healing auto-migration (`--fix`), add structured machine-readable JSON output (`--json`) across CLI and REPL shell, and enforce `ROADMAP.md` phase and task state machine syntax validation.
- **Rationale**: The autonomous Ralph loop and continuous integration workflows require deterministic, lightning-fast test feedback (<5.0s SLA) and deep architectural invariant verification. Adding foreign key validation and Phase 7 semantic schema integrity checks prevents silent database corruption, while machine-readable JSON telemetry enables automated health reporting and CI/CD status integration.
- **Constraints & Alignment**:
  - Offline-first? Yes (runs 100% offline).
  - Zero third-party dependencies? Yes (Python standard library only).
  - High performance? Yes (full doctor diagnostics in <5.0s; fast mode in <0.8s; parallel tests in 3.83s).
- **Proposed Roadmap Phase**: Phase 0 (Task 0.18; ADR-053).
- **Status**: [DONE] (Rank A+; Implemented in Run 050 / Senior PM Cleanup Sprint).

---

### [VETTED] Streamlined Semantic Prompt CLI & Dry-Run Exegetical Subcommand (`./bible prompt`)
- **Summary**: Implement a dedicated CLI subcommand (`./bible prompt <ref> [--type pericope|typology|discourse] [--copy] [--output <file>]`) and interactive shell command (`/prompt <ref>`) that allows developers and Bible students to generate, preview, export, or clipboard-copy fully assembled, stratified exegetical prompts for any canonical passage directly from the terminal without executing live API calls.
- **Rationale**: While `core/semantic_prompts.py` provides the programmatic engine to build multi-layer prompts with macro-book horizons, users and developers currently have no direct CLI mechanism to inspect generated prompts for specific biblical passages (e.g. `Romans 8:28-39`, `Exodus 12:1-14`) or copy them into external LLM interfaces (Claude, Gemini, ChatGPT) for ad-hoc study or offline manual review. Exposing prompt generation as a fast, zero-dependency CLI tool empowers manual verification and interactive study.
- **Constraints & Alignment**:
  - Offline-first? Yes (builds prompts 100% offline from local scripture text and embedded 66-book horizons).
  - Zero third-party dependencies? Yes (Python 3 standard library only per ADR-003).
  - High velocity? Yes (generates complete prompt text in <1ms).
- **Proposed Roadmap Phase**: Phase 7 (Task 7.3.1).
- **Suggested Tasks**:
  - [ ] Add `prompt` subcommand to `cli/` argument parser with `--type`, `--raw-json`, and `--output` options.
  - [ ] Add `/prompt` command to interactive shell in `cli/shell.py`.
  - [ ] Add hermetic unit tests in `tests/test_cli.py` verifying CLI prompt output formatting.
- **Status**: [VETTED] (Rank A+; Promoted in Run 051).

---

### [VETTED] Sovereign Dual-Horizon Scripture Graph & Typological Matrix Visualizer
- **Summary**: Implement a zero-dependency interactive graph and matrix viewer (`./bible graph` and `/graph` in REPL shell) generating self-contained SVG and terminal ASCII visualizations of the newly compiled 6-layer permanent semantic database (`data/bible.db`). Visualizes redemptive-historical arcs linking Old Testament types directly to New Testament antitypical fulfillments, rhetorical discourse flow networks across pericopes, and dual-horizon theological loci distributions.
- **Rationale**: With Phase 7 now complete and 100.00% of the canon's theological and typological metadata permanently compiled into SQLite, users and developers need visual, pedagogical tools to explore how Old Testament shadows connect with Christological fulfillments across all 66 books without relying on external web browsers or npm packages.
- **Constraints & Alignment**:
  - Offline-first? Yes (queries local `data/bible.db` directly).
  - Zero third-party dependencies? Yes (pure Python standard library SVG generator and ANSI terminal layout).
  - High performance? Yes (sub-second rendering for complex multi-book subgraphs).
- **Proposed Roadmap Phase**: Phase 8 (Task 8.7).
- **Suggested Tasks**:
  - [ ] Add `core/graph_visualizer.py` supporting SVG and terminal ASCII network graph generation.
  - [ ] Expose `./bible graph [ref]` subcommand in `cli/main.py`.
  - [ ] Expose `/graph [ref]` in REPL interactive shell `cli/shell.py`.
  - [ ] Add hermetic unit tests in `tests/test_graph_visualizer.py`.
- **Status**: [VETTED] (Rank A+; Promoted in Run 054).

---

### [DONE] Deep Semantic Diagnostic Integration, Omnichannel Audit Ergonomics & Doctor Coverage Gates
- **Summary**: Seamlessly embed the Exegetical Critic and Whole-Bible Verse Coverage Auditor into the core system health suite (`tools/doctor.py`), validating that all 31,103 canonical coordinates, 1,304 pericopes, and 6 semantic layers are verified error-free on every doctor invocation. Expose first-class `/audit-semantic` (alias: `/audit`) commands in the interactive REPL shell (`cli/shell.py`) with full argument parsing and book auto-completion, achieve doctor benchmarking parity (`--bench`) across CLI and REPL, and equip `tools/audit_semantic.py` with custom stream redirection.
- **Rationale**: While Phase 7 successfully compiled 100.00% semantic coverage into SQLite, the project's health diagnostic infrastructure previously only validated standard database tables and verse counts. If semantic coordinate boundaries or pericope linkages degraded, doctor would pass blindly. Continuous semantic auditing in `doctor.py` prevents silent metadata corruption, while omnichannel REPL integration gives developers instant terminal access to audit metrics.
- **Constraints & Alignment**:
  - Offline-first? Yes (queries local SQLite database in ~0.08s).
  - Zero third-party dependencies? Yes (Python 3 standard library only per ADR-003).
  - High performance? Yes (full database semantic audit completes in <85ms).
- **Proposed Roadmap Phase**: Phase 0 (Task 0.19; ADR-058).
- **Status**: [DONE] (Rank A+; Implemented in Run 055 / Senior PM Cleanup Sprint).












---

### [VETTED] Interactive REPL `/chat` Persona Subshell & Command-Line REPL Completion (Rank A+)
- **Summary**: Expose biblical character dialogue not only through a dedicated CLI command (`./bible chat <character> [--stream] [--translation]`), but also inside the interactive `./bible shell` REPL via `/chat <character>` with live tab completion across all 19 canonical persona names and aliases.
- **Rationale**: Harmonizes with existing `/ask` REPL integration (ADR-062) and provides an immediate, frictionless playground for scholars and students to converse with biblical figures within the interactive shell.
- **Constraints & Alignment**:
  - Offline-first? Yes (clean offline fallback card when `GEMINI_API_KEY` is not present).
  - Zero third-party dependencies? Yes (Python 3 stdlib `cmd`, `readline`, `urllib.request`).
  - Strict theological guardrails? Yes (governed by `core/persona.py` and TGC Foundation Documents).
- **Proposed Roadmap Phase**: Phase 8 (Integrated into Task 8.4).
- **Suggested Tasks**:
  - [ ] Expose `chat` CLI command in `cli/main.py` with `--stream`, `--translation`, and persona listing.
  - [ ] Expose `/chat <character>` in `cli/shell.py` with multi-turn conversation loop and tab autocompletion across personas.
  - [ ] Add hermetic unit tests in `tests/test_cli.py` and `tests/test_shell.py`.
- **Status**: [VETTED] (Rank A+; Promoted in Run 059).

---

### [VETTED] Interactive API Key Setup Wizard in `./bible init` for Frictionless User Onboarding (Rank A+)
- **Summary**: Enhance `./bible init` with an interactive, user-friendly onboarding wizard that prompts the user to configure `ESV_API_KEY` (unlocking the primary ESV translation and live passage fetching) and `GEMINI_API_KEY` (unlocking online Scripture RAG and biblical persona dialogue). If keys are provided, securely write them to local configuration (`config/esv_api_key.txt`, `~/.config/bible/esv_api_key`, or `.env`), validate them with live health-check probes, and eliminate silent degradation across the system. Provide non-interactive flags (`--esv-key <key>`, `--gemini-key <key>`, `--non-interactive`) for headless environments.
- **Rationale**: Currently, when a user boots the platform without pre-existing environment variables, commands silently fall back to `WEB` or emit warnings without guiding the user through how to obtain and persist these free credentials. Making initialization interactive, welcoming, and self-guiding ensures all primary capabilities (ESV word-for-word text, AI RAG exegesis, persona conversations) are unlocked immediately upon install.
- **Constraints & Alignment**:
  - Offline-first? Yes (optional keys; if skipped, clearly informs the user of public-domain offline WEB mode without failing).
  - Zero third-party dependencies? Yes (Python 3 standard library `getpass`/`input`, `pathlib`, `urllib.request`).
  - Secure? Yes (stores keys in local user configuration with restrictive POSIX permissions `0600`).
- **Proposed Roadmap Phase**: Phase 0 (Task 0.26 / ADR-074).
- **Suggested Tasks**:
  - [x] Implement sovereign zero-dependency API key onboarding engine and connectivity probes in `tools/onboarding.py`.
  - [x] Add interactive credential prompt and instructions to `core/bootstrap.py` and `cli/main.py` during `./bible init`.
  - [x] Expose top-level `./bible keys` CLI command and `/keys` REPL command.
  - [x] Add non-interactive flag support (`--esv-key`, `--gemini-key`, `--no-probe`) for scripted setup.
  - [x] Add hermetic unit tests across `tests/test_onboarding.py`, `tests/test_bootstrap.py`, `tests/test_cli.py`, and `tests/test_shell.py`.
- **Status**: [DONE] (Rank A+; Implemented via ADR-074 and Task 0.26 in Run 070).

---

### [VETTED] Unified Translation Default Alignment & Transparent CLI Fallback Notices (Rank A+)
- **Summary**: Harmonize all CLI help messages, argument parsers, and execution routines so that the default translation is consistently documented and reported as `ESV` (matching internal routing in `DEFAULT_TRANSLATION` per ADR-041/045). When an ESV query cascades to `WEB` because no `ESV_API_KEY` is configured, always output a clean, non-intrusive one-line informational notice (e.g. `Notice: ESV requested but ESV_API_KEY not configured. Displaying WEB (World English Bible). Run './bible init' to configure ESV.`) rather than silently outputting WEB without explanation.
- **Rationale**: Resolves the confusing cognitive dissonance where `--help` states `default: WEB`, internal code routes to `ESV`, and the CLI silently produces `WEB` text without explaining that ESV was intended but cascaded due to a missing API key.
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes.
- **Proposed Roadmap Phase**: Phase 2 (Task 2.6).
- **Suggested Tasks**:
  - [ ] Update `parser_get`, `parser_compare`, and other CLI help texts in `cli/main.py` to specify `default: ESV (with offline WEB fallback)`.
  - [ ] Ensure `get_verses_with_fallback` prints a transparent, informative message when cascading from default ESV to WEB.
  - [ ] Add unit tests verifying consistent help text and fallback messaging in `tests/test_cli.py`.
- **Status**: [VETTED] (Rank A+; Feature Request added).

---

### [VETTED] Dynamic Bottom-Up Semantic Tagging & Clean-Slate Taxonomy Migration (Rank A+)
- **Summary**: Replace the rigid, pre-assumed 25-tag seed set with an organic, bottom-up dynamic taxonomy system. Reset the `tags` table to retain only the single valid user tag (`favorites`), while removing artificial pre-assumed tags. Provide support for hundreds of fine-grained, emergent semantic tags created during deep textual exegesis (e.g. `money`, `pride`, `prophecy`, `red_letters`, `heaven`, `hell`, `persecution`, `temptation`, `sovereignty`, `adoption`). Enforce strict `snake_case` naming conventions and consistent theological categorization.
- **Rationale**: Pre-assuming 25 rigid theological tags artificially boxed in the tagging system while leaving 100% of those tags with 0 associated verses. Scripture addresses hundreds of practical, ethical, historical, and doctrinal themes. Allowing the semantic analysis engine to discover and create tags dynamically as it processes scripture text reflects authentic textual exegesis and enables rich discovery for users.
- **Constraints & Alignment**:
  - Offline-first? Yes (all created tags and verse associations reside permanently in local SQLite `data/bible.db`).
  - Zero third-party dependencies? Yes (Python 3 stdlib only).
  - Format standard? Strict `snake_case` identifiers.
- **Proposed Roadmap Phase**: Phase 3 (Task 3.5).
- **Suggested Tasks**:
  - [ ] Migrate database to prune the unlinked 25 pre-assumed tags, keeping `favorites`.
  - [ ] Update `TaggingService` in `core/tags.py` to enforce `snake_case` normalization and dynamic tag registration on the fly.
  - [ ] Update tests in `tests/test_tags.py` and `tests/test_db.py`.
- **Status**: Implemented via Task 3.5 and ADR-079.

---

### [VETTED] Universal Tagging Unification: Deprecate `starred` Column in Favor of `#starred` Tag (Rank A+)
- **Summary**: Eliminate the dedicated boolean `starred` column from `verse_tags` (and associated APIs) and unify it into the primary tagging architecture by treating "starred" as simply another first-class tag (`name = 'starred'`). Run an automated migration converting all existing rows where `starred = 1` into standard `verse_tags` entries linked to the `starred` tag.
- **Rationale**: Having both a `starred` boolean attribute and a tagging system creates schema redundancy and conceptual confusion. In an elegant relational architecture, a priority star is simply a curation tag (`#starred`). Removing the dedicated column simplifies queries, eliminates special-case API flags, and allows users to search, filter, and inspect starred passages through standard tag mechanics (`./bible get --tag starred`, `./bible ribbon starred`).
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (standard SQLite migrations in `core/db.py`).
- **Proposed Roadmap Phase**: Phase 3 (Task 3.6).
- **Suggested Tasks**:
  - [ ] Write non-destructive schema migration in `core/db.py`: insert `starred` tag, map all `starred=1` entries into `verse_tags`, and remove or deprecate the legacy column.
  - [ ] Update `TaggingService` and CLI/REPL arguments to query `starred` as a standard tag.
  - [ ] Update hermetic tests across `tests/test_favorites.py`, `tests/test_tags.py`, and `tests/test_db.py`.
- **Status**: [VETTED] (Rank A+; Feature Request added).

---

### [VETTED] Visual Distinction for Single-Verse vs. Passage/Pericope Tag Spans in Web UI & CLI (Rank A+)
- **Summary**: Enhance the Web UI (Reader, Heatmaps, and Pericope drill-down) and CLI/terminal outputs to clearly distinguish between tags applied to a single discrete verse (e.g. `John 3:16`) versus tags spanning a wider pericope or multi-verse passage (e.g. `Romans 8:1-11`, `Genesis 1:1 - 2:3`). In the Web UI, use distinct visual chips (e.g. `[Verse Tag: #adoption]` with subtle border vs. `[Span Tag: #sanctification (vv. 1-11)]` with an illuminated bracket enclosing the entire rendered passage). In the CLI, display clear span boundaries beside tag badges.
- **Rationale**: Currently, when a user views a verse that inherits a tag from a parent pericope or multi-verse span, the UI displays the tag without indicating whether it was placed specifically on that single verse or spans the whole section. Clarifying tag granularity gives readers instant exegetical context.
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes (vanilla CSS/JS + standard library ANSI terminal layout).
- **Proposed Roadmap Phase**: Phase 4 (Task 4.6).
- **Suggested Tasks**:
  - [ ] Add `span_range_text` and `is_single_verse` helper indicators to `TaggedPassage` in `core/tags.py`.
  - [ ] Update terminal badge formatting in `core/terminal.py` to annotate multi-verse spans.
  - [ ] Update Web UI reader JavaScript (`web/static/app.js`) and CSS (`web/static/style.css`) to render bracketed span boundaries and distinct tag chips.
  - [ ] Add unit tests in `tests/test_terminal.py` and `tests/test_server.py`.
- **Status**: [VETTED] (Rank A+; Feature Request added).

---

### [VETTED] Client-Controlled Semantic Tagging Project Skill & ESV Exegetical Guidelines Engine (`skills/semantic-tagging`) (Rank A+)
- **Summary**: Create a dedicated project skill (`skills/semantic-tagging/SKILL.md`) equipping agents to perform client-controlled, book-by-book or range-by-range semantic tagging of the entire Bible. Key characteristics of the skill:
  1. **Strict ESV Translation Mandate**: Semantic analysis must be conducted exclusively on the ESV text (`core/esv.py`). No other translation may be used for semantic exegesis.
  2. **Comprehensive Scope**: Processes all verses and pericopes in the commanded book or passage range.
  3. **Three-Step Exegetical Workflow**:
     - *Step 1*: Inspect all existing tags currently attached to the verse(s).
     - *Step 2*: Inspect all available tags across the database taxonomy.
     - *Step 3*: Analyze the ESV text against THEOLOGY.md principles and assign relevant tags, creating new `snake_case` tags whenever a suitable one does not already exist.
  4. **Client-Directed Execution**: Repeatedly callable on demand by book (e.g., `"Use your semantic_tagging skill to tag all verses and pericopes in the book of Genesis"`).
  5. **Curated Biblical Semantic Guidelines**: Incorporate exhaustive, web-curated semantic guidelines aligned with TGC Foundation Documents (thematic motifs, redemptive epochs, Christological fulfillments, ethical teachings, practical topics like `money`, `pride`, `persecution`, `prayer`, `red_letters`, `heaven`, `hell`).
- **Rationale**: Replaces opaque, monolithic batch jobs with a transparent, client-governed, agentic skill. Allows the client to inspect, guide, and incrementally tag books of the Bible with complete oversight, ensuring high exegetical quality, zero hallucinated schemas, and rich thematic tagging across the entire canon.
- **Constraints & Alignment**:
  - Offline-first database storage? Yes (all results persisted directly to SQLite `data/bible.db`).
  - Zero third-party dependencies? Yes (Python stdlib and Jetski skill standard).
  - Strict theological guardrails? Yes (grounded in `THEOLOGY.md`).
- **Proposed Roadmap Phase**: Phase 3 (Task 3.7).
- **Suggested Tasks**:
  - [ ] Create `skills/semantic-tagging/SKILL.md` with operational workflows, step-by-step instructions, and TGC-aligned exegetical tagging guidelines.
  - [ ] Build backing helper CLI/tooling (`tools/semantic_tagger.py` or `./bible tag analyze <book|range> --skill-mode`) operating strictly on ESV text.
  - [ ] Author hermetic unit tests verifying the skill tooling and ESV passage fetching.
- **Status**: [VETTED] (Rank A+; Feature Request added).

---

### [VETTED] Bundled King James Version (KJV) Ingestion & Multi-Translation Comparison Parity (Rank A+)
- **Summary**: Ingest a complete, verified public-domain translation—the **King James Version (KJV)**—into `data/bible.db` as a second permanent offline translation alongside WEB (~31,102 verses). Provide an offline compilation pipeline (`tools/ingest_kjv.py`), raw text cache in `data/raw/kjv/`, and full FTS5 search indexing.
- **Rationale**: Currently, `data/bible.db` only has 1 translation (`WEB`), rendering `./bible compare` incapable of comparing different translations offline (it compares WEB against fallback WEB). Bundling KJV unlocks authentic offline multi-translation comparison, formal vs. dynamic equivalence study, and historical phrase search without needing external API credentials.
- **Constraints & Alignment**:
  - Offline-first? Yes (100% public domain text committed to repository).
  - Zero third-party dependencies? Yes (Python 3 stdlib pipeline).
  - Copyright compliant? Yes (KJV is 100% public domain).
- **Proposed Roadmap Phase**: Phase 1 (Task 1.7).
- **Suggested Tasks**:
  - [ ] Cache clean public domain KJV JSON in `data/raw/kjv/`.
  - [ ] Implement `tools/ingest_kjv.py` compiling KJV verses into `data/bible.db` with canonical IDs (`BBCCCVVV`).
  - [ ] Add hermetic unit tests in `tests/test_ingest.py`.
- **Status**: [VETTED] (Rank A+; Feature Request added).

---

### [VETTED] Comprehensive Scripture Cross-Reference Knowledge Graph Ingestion (TSK) (Rank A+)
- **Summary**: Ingest an authoritative, public-domain cross-reference dataset (such as the **Treasury of Scripture Knowledge - TSK**, containing ~340,000 canonical cross-references) into `cross_references` table in `data/bible.db`, expanding the graph from 67 hand-curated rows to comprehensive whole-Bible coverage.
- **Rationale**: Currently, `cross_references` contains only 67 rows, making the Web UI's Typological Arc Network and CLI `--refs` look empty for 90% of the Bible. Ingesting TSK equips every chapter with rich canonical intertextual links.
- **Constraints & Alignment**:
  - Offline-first? Yes.
  - Zero third-party dependencies? Yes.
  - Fast query latency? Yes (indexed by `start_canonical_id` and `end_canonical_id`).
- **Proposed Roadmap Phase**: Phase 3 (Task 3.8).
- **Suggested Tasks**:
  - [ ] Source clean public-domain TSK cross-reference dataset into `data/raw/cross_references/`.
  - [ ] Build zero-dependency ingestion script `tools/ingest_crossrefs.py`.
  - [ ] Add unit tests in `tests/test_crossref.py`.
- **Status**: [VETTED] (Rank A+; Feature Request added).

---

### [VETTED] Whole-Bible ESV Verse and Pericope Dense Embeddings Generation (Rank A+)
- **Summary**: Populate `verse_embeddings` and `pericope_embeddings` with dense vector embeddings (e.g. 768-dim int8 quantized byte buffers, ~24MB total) generated from the **ESV** text using a standard embedder (e.g. `text-embedding-004`). Because the sacred text of Scripture is fixed and invariant, the entire vector database for all 31,102 verses and 1,304 pericopes is compiled **offline** once into SQLite (`data/bible.db`). The pre-computed embeddings serve dual primary functions:
  1. **Corpus Similarity Exploration**: Instant passage-to-passage and pericope-to-pericope cosine similarity matching (<15ms via `core/vector.py`) to discover thematic parallels, typological connections, and cross-canonical echoes without keyword dependencies.
  2. **Vector-Based Natural Language Query Search for RAG**: At runtime, user-input natural language questions or search queries (e.g. *"How much should I tithe?"*, *"What does the Bible teach about anxiety?"*, *"Why did Jesus weep?"*) are embedded via the same standard embedder, and cosine similarity against the offline vector database retrieves the top semantic verse/pericope matches as direct answers or as grounded context for RAG theological exegesis in CLI and Web UI chat.
- **Rationale**: The `verse_embeddings` table currently has 0 rows in `data/bible.db`, and `pericope_embeddings` has only coarse synthetic vectors. Since scripture never changes, baking real ESV vector embeddings into the database offline guarantees permanent zero-maintenance retrieval with zero ongoing embedding computation for the scripture corpus itself. This unlocks genuine micro-level semantic similarity search and empowers high-precision natural language RAG retrieval.
- **Constraints & Alignment**:
  - Scripture invariance: Pre-computed offline once; never recomputed at runtime for static verses.
  - Translation mandate: Strictly generated from **ESV** text (`core/esv.py`).
  - Storage: Quantized int8 packed byte BLOBs in SQLite (<25MB total).
  - Zero external dependencies: Vector similarity math in pure Python standard library `struct` and `math` (ADR-003/051).
- **Proposed Roadmap Phase**: Phase 7 (Task 7.7; ADR-076).
- **Suggested Tasks**:
  - [ ] Add standard embedding generation method in `core/llm.py` targeting Google's REST embedding endpoint with int8 quantization.
  - [ ] Implement batch embedder in `tools/build_embeddings.py` operating offline on ESV text with checkpointing.
  - [ ] Populate `verse_embeddings` (31,102 rows) and `pericope_embeddings` (1,304 rows) in `data/bible.db`.
  - [ ] Add hermetic unit tests in `tests/test_vector.py`.
- **Status**: [VETTED] (Rank A+; Feature Request added).

---

### [VETTED] Interactive 2D Semantic Similarity Scatter Map Visualizer in Web UI (Rank A+)
- **Summary**: Implement an interactive Web UI panel (`/map` or `/explore/map`) visualizing the entire Bible or selected books as a 2D semantic similarity scatter map. Verses and pericopes appear as clickable dots arranged by conceptual proximity (using pre-projected 2D coordinates derived via t-SNE/UMAP or PCA on ESV vector embeddings). Users can zoom, pan, hover to read tooltips, and click dots to inspect the passage text, active tags, and theological themes in the split-screen reader.
- **Rationale**: Transforms abstract high-dimensional vector embeddings into an intuitive visual landscape. Allows Bible students to visually discover unexpected conceptual clusters (e.g. sacrificial imagery across Leviticus, Hebrews, and Revelation clustering together) and navigate scripture spatially.
- **Constraints & Alignment**:
  - Offline-first? Yes (2D projection coordinates pre-computed and stored in SQLite).
  - Zero npm dependencies? Yes (vanilla JavaScript + native HTML5 Canvas or SVG).
- **Proposed Roadmap Phase**: Phase 4 (Task 4.7).
- **Suggested Tasks**:
  - [ ] Add 2D coordinate columns (`map_x`, `map_y`) to `verse_embeddings` / `pericope_embeddings` schema.
  - [ ] Build projection utility in `tools/project_embeddings.py` calculating 2D coordinates.
  - [ ] Expose REST endpoint `GET /api/embeddings/map`.
  - [ ] Build interactive Canvas/SVG scatter map component in `web/static/app.js` with hover tooltips, book coloring, and click-to-read integration.
  - [ ] Add unit tests in `tests/test_server.py`.
- **Status**: [VETTED] (Rank A+; Feature Request added).

---

### [VETTED] Vector-Similarity Scripture Retrieval & Pericope Recommender UI (Rank A+)
- **Summary**: Implement a dedicated Semantic Retrieval & Similarity Explorer panel in the Web UI (`/similarity` or integrated into the Split-Screen Reader) and CLI (`./bible similar <ref-or-query>`). Supports dual-mode semantic retrieval:
  1. **Passage-to-Passage Similarity**: When inspecting any verse or pericope, displays the most semantically similar passages across the whole Bible ranked by cosine similarity score (e.g., `Romans 3:25` ➔ `Leviticus 16:15` [94% similarity], `Hebrews 9:12` [91% similarity]), with visual score badges, highlighted thematic overlaps, and instant one-click drill-down.
  2. **Natural Language User Query Search**: Allows users to enter natural language questions or topical queries (e.g., *"How much should I tithe?"*, *"Dealing with grief and loss"*, *"Armor of God against spiritual warfare"*). The query is embedded via the standard embedder and matched against the offline verse and pericope vector database, returning ranked matching passages with cosine similarity scores and pericope summaries.
- **Rationale**: Provides a powerful AI-assisted alternative and complement to traditional word-based concordances. Enables scholars and readers to discover conceptually parallel passages even when they do not share identical vocabulary, and allows users to search Scripture using conversational, natural language questions.
- **Constraints & Alignment**:
  - Offline-first? Yes for passage-to-passage search (queries local SQLite int8 vector BLOBs via `core/vector.py` in <15ms). For user-input query search, embedding is generated via standard embedder and matched locally against the offline database.
  - Zero third-party dependencies? Yes.
- **Proposed Roadmap Phase**: Phase 4 (Task 4.8; ADR-076).
- **Suggested Tasks**:
  - [ ] Add `find_similar_verses(canonical_id, limit=10)` and `find_similar_pericopes(pericope_id, limit=10)` to `core/vector.py` and `core/db.py`.
  - [ ] Add `search_verses_by_vector(embedding, limit=10)` and `search_pericopes_by_vector(embedding, limit=10)` to `core/vector.py`.
  - [ ] Expose CLI command `./bible similar <ref-or-query> [--limit 10] [--threshold 0.7]`.
  - [ ] Expose REST endpoints `GET /api/similar?ref=<citation>` and `GET /api/similar?q=<natural-language-query>`.
  - [ ] Add "Similar Passages" accordion tab and natural language query search in Web UI Split-Screen Reader (`web/static/app.js`) with similarity progress bars and click-to-load.
  - [ ] Add unit tests in `tests/test_vector.py` and `tests/test_server.py`.
- **Status**: [VETTED] (Rank A+; Feature Request added).



