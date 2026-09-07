# Project Roadmap & Backlog

This document is the single source of truth for current project status, active tasks, and future backlog. Autonomous agents must consult this document during boot and update it upon completing work.

---

## Current Status Overview
- **Active Phase**: Phase 5 — Visual Verse Slide Generator for TV Screensavers & Presentation
- **Overall Progress**: Phase 0, Phase 1, Phase 2, Phase 3, and Phase 4 complete (100%); Phase 5 in progress (Tasks 5.1, 5.2, 5.3, 5.4 complete)
- **Architecture Mandate**: **Zero External Dependencies** (Python standard library only + Vanilla HTML/CSS/JS). No npm, no pip dependencies, zero Dependabot alerts.

---

## Phase Breakdown

### Phase 0: Repository Architecture & Autonomous Harness
- [x] **Task 0.1**: Draft `MANIFESTO.md`, `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and `AGENT_LOG.md`.
- [x] **Task 0.2**: Restructure repository layout (establish `cli/`, `core/`, `web/`, `data/`, `legacy/`).
- [x] **Task 0.3**: Establish Zero-Dependency Architecture (ADR-003) for zero maintenance and Dependabot immunity.
- [x] **Task 0.4**: Update Ralph Loop runner harness (`ralph.sh`) to invoke Jetski CLI directly in terminal with `--dangerously-skip-permissions` (ADR-007).
- [x] **Task 0.5**: Establish Senior Product Manager Meta-Improvement & System Health Sprint cadence (every 5th iteration) in `ralph.sh`, `AGENTS.md`, and `DECISIONS.md` (ADR-015).
- [x] **Task 0.6**: Implement automated pre-commit fast linter & doc-sync validator (`tools/doctor.py` / `bible doctor`) to verify zero-dependency AST and state machine integrity. *(Run 015)*
- [x] **Task 0.7**: Implement Git pre-commit / pre-push hook automation (`tools/install_hooks.sh` and `bible doctor --install-hooks`) to enforce machine-level validation before pushing to remote. *(Run 021 / ADR-022)*
- [x] **Task 0.8**: Establish Executive Summary & Project Trajectory Briefing cadence (every 10th iteration), on-demand CLI command (`./bible summary`), standalone tool (`tools/executive_summary.py`), and project skill (`skills/executive-summary/SKILL.md`) (ADR-017). *(Run 016)*
- [x] **Task 0.9**: Implement interactive shell context management (`__enter__`/`__exit__`), clean test warning elimination, and autonomous runner `--help` self-documentation (ADR-026). *(Run 025)*
- [x] **Task 0.10**: Implement Sovereign Cold-Start Bootstrapping, Unified Database Compilation & Lifecycle Engine (`bible init` / `bible db`), Self-Healing Doctor Diagnostics (`--fix`), and Comprehensive Repository Documentation (ADR-030). *(Run 029 / Senior PM Cleanup Sprint)*
- [x] **Task 0.11**: Implement Omnichannel Visual Slide Integration across CLI, REPL Shell, and REST API (`./bible slide`, `/slide`, `/api/slide`, ADR-035). *(Run 034 / Senior PM Meta-Sprint)*
- [x] **Task 0.12**: Implement High-Performance Parallel Hermetic Test Runner (`tools/test_runner.py`), CLI integration (`./bible test`), REPL shell integration (`/test`), strict ResourceWarning leak auditing, and doctor acceleration (ADR-036). *(Run 035 / Senior PM Cleanup Sprint)*
- [x] **Task 0.13**: Implement Sovereign Zero-Dependency Static Analysis, Code Hygiene & Linter Engine (`tools/linter.py`), CLI subcommand (`./bible lint`), REPL shell integration (`/lint`), pre-commit hook integration, and doctor diagnostics (ADR-040). *(Run 039 / Senior PM Cleanup Sprint)*
- [x] **Task 0.14**: Configure Public Open-Source Repository Governance, Permissive MIT License (`LICENSE`), and Crossway Legal Attribution Guidelines (ADR-041).
- [x] **Task 0.15**: Implement Sovereign Zero-Dependency Code Coverage Engine (`tools/coverage.py`), CLI subcommand (`./bible coverage`), REPL integration (`/coverage`), and Resilient Autonomous Telemetry Architecture (`tools/executive_summary.py`) (ADR-043). *(Run 040 / Senior PM Double Milestone)*

### Phase 1: Core Data Models & Offline Scripture Storage (Zero Dependencies)
- [x] **Task 1.1**: Define standard canonical scripture reference model (`Book` [1-66], `Chapter`, `Verse`, `Span/Range`, OSIS identifiers) in `core/reference.py`.
- [x] **Task 1.2**: Implement SQLite database schema & connection manager in `core/db.py` (`verses`, `translations`, `books`, `spans`, `tags`, `verse_tags`, `cross_references`, and FTS5 search).
- [x] **Task 1.3**: Ingest full Public Domain Bible translation (World English Bible - WEB) into bundled SQLite database for offline access.
- [x] **Task 1.4**: Implement zero-dependency keystream encryption/obfuscation module in `core/crypto.py` for copyrighted translations.
- [x] **Task 1.5**: Hermetic unit tests using `unittest` in `tests/test_core.py`.
- [x] **Task 1.6**: Ingest user's curated favorites (`favorite_bible_verses.csv`, 829 passages, 50 starred) into database as a first-class `favorites` tag with `starred` boolean attribute.


### Phase 2: Command Line Interface (CLI)
- [x] **Task 2.1**: Implement CLI entry point `bible.py` (executable `./bible`) with verse lookup command (`./bible get "John 3:16"`, `./bible get "Romans 8:28-30"`). *(Run 012)*
- [x] **Task 2.2**: Support multi-translation flag (`--version=WEB`, `--version=ESV`) with fallbacks, parallel comparison subcommand (`bible compare`), and translations inspector (`bible translations`). *(Run 017)*
- [x] **Task 2.3**: Implement full-text search CLI command (`./bible search "light of the world"`). *(Run 018)*
- [x] **Task 2.4**: Formatted terminal output (clean margins, text wrapping, optional verse numbers, paragraph breaks, colored ANSI styling using standard library). *(Run 019)*
- [ ] **Task 2.5**: Implement Zero-Dependency ESV API Client (`core/esv.py`), Compliant 500-Verse Ephemeral LRU Cache, and Set ESV as Default Translation with Graceful Offline Fallback (ADR-041).

### Phase 3: Semantic Tagging & Knowledge Database Engine
- [x] **Task 3.1**: Create Tagging API allowing tags on individual verses or arbitrary verse spans (e.g., `Romans 8:1-11` -> `Holy Spirit`, `Sanctification`). *(Run 022 / ADR-023)*
- [x] **Task 3.2**: Implement verse-to-verse cross-referencing and relationship edges (thematic, prophecy-fulfillment, quotation). *(Run 023 / ADR-024)*
- [x] **Task 3.3**: Create batch LLM tagging tool/prompt generator to classify and tag scripture into predefined and dynamic semantic taxonomies (`tools/tag_generator.py` / `core/tag_prompts.py`). *(Run 024 / ADR-025)*
- [x] **Task 3.4**: Aggregation queries: topic density per book, tag co-occurrence matrix, verse relevance scoring. *(Run 026 / ADR-027)*

### Phase 4: Web UI & Visualizations (Vanilla Web, No npm)
- [x] **Task 4.1**: Build built-in HTTP server (`./bible serve [--port=8080]`) serving REST API and embedded static web assets via Python's `http.server`. *(Run 027 / ADR-028)*
- [x] **Task 4.2**: Implement Sacred-Modern design system (obsidian dark mode `#0D0E11`, illuminated gold accents `#D4AF37`, editorial typography, responsive split-pane layout). *(Run 028 / ADR-029)*
- [x] **Task 4.3**: Implement Canonical Redemptive Ribbon: dual-modal terminal ASCII/Unicode visualizer and Sacred-Modern Web UI Thematic Heatmap across all 66 books of the Bible for any chosen tag/topic. *(Run 030 / ADR-031)*
- [x] **Task 4.4**: Implement drill-down verse viewer: clicking a heatmap cell / book chapter displays scripture passages, pericopes, and active tags. *(Run 031 / ADR-032)*
- [x] **Task 4.5**: Implement pure SVG Typological Arc Network & Cross-Reference Graph connecting Old Testament shadows to New Testament fulfillments. *(Run 032 / ADR-033)*

### Phase 5: Visual Verse Slide Generator for TV Screensavers & Presentation
- [x] **Task 5.1**: Implement Rendering Engine abstraction (`core/render.py`) supporting system ImageMagick (`magick`/`convert`) for raster output and pure Python SVG generator (vector). *(Run 033 / ADR-034)*
- [x] **Task 5.2**: Build dynamic typography & layout engine: auto-computes optimal font size clamping, balanced word wrapping, line height, and optical vertical centering (~45%) within TV safe margins. *(Run 036 / ADR-037)*
- [x] **Task 5.3**: Implement CLI slide generation command (`bible slide` / `bible render`) with rich options: *(Run 037 / ADR-038)*
  - Resolution: `--resolution=4k` (3840x2160 default), `--resolution=1080p` (1920x1080), or custom `WxH`.
  - Color themes: `--theme=oled-black` (pure `#000000` default), `--theme=charcoal` (`#121212`), `--theme=inverted` (black on white).
  - Typography: `--font=<family>` (defaults to serif e.g., Georgia / Liberation Serif), `--font-size=<auto|pt>`, `--line-spacing`.
  - Layout & Margins: `--safe-area=<pct>` (default 15%), `--align=<center|left|right>`.
  - Citation: `--citation-style=<below|smallcaps|none>`, `--citation-color=<hex>`.
  - Format: `--format=png` (default lossless), `--format=jpg` (with `--quality=95`).
- [x] **Task 5.4**: Add multi-slide pagination: automatically split long passages exceeding maximum readability thresholds into numbered slide sequences (e.g. `1/3`, `2/3`, `3/3`). *(Run 038 / ADR-039)*
- [ ] **Task 5.5**: Add batch export command (`bible slide-batch`) to generate a folder of 4K slides from a tag, book, reading plan, or user favorites (`--favorites`, `--starred-only` from `favorite_bible_verses.csv`), ready for Google Photos TV screensaver albums.

### Phase 6: Google Gemini LLM Client & Theological Guardrail Engine (Zero-Dependencies)
- [ ] **Task 6.1**: Implement pure Python stdlib Google Gemini API client in `core/llm.py` (`urllib.request`, JSON serialization, retry/backoff, streaming/response parsing, defaulting to `gemini-2.5-pro` with `gemini-2.0-flash` fallback, zero pip dependencies per ADR-003 and ADR-006). Passage context builder defaults to ESV via ESV API client (`core/esv.py`) per ADR-041.
- [ ] **Task 6.2**: Implement TGC Hermeneutical Framework & System Prompt Generator in `core/theology.py` (codifying The Gospel Coalition Confessional Statement and Theological Vision for Ministry: dual-horizon hermeneutics, Christ-centered typology, non-moralistic interpretation, justification by faith alone).
- [ ] **Task 6.3**: Write hermetic unit tests with mock HTTP responses for `core/llm.py` and theological prompts in `tests/test_llm.py`.

### Phase 7: Offline Theological Enrichment & Whole-Bible Semantic Database Compiler (ADR-042)
- [ ] **Task 7.1**: Extend SQLite database schema and records in `core/db.py` to support 6-layer semantic architecture: `pericopes` (genre, literary_structure, central_proposition, redemptive_summary), `discourse_relations` (ground, inference, purpose, contrast, condition), `verse_theology` (storyline_epoch, thematic_ribbon, theological_locus, primary_doctrine), `typological_arcs` (type, antitype, theological_correspondence, warrant), `semantic_propositions` (speech_act, agent, action, patient, tone), and `verse_embeddings` / `pericope_embeddings` (BLOB storage).
- [ ] **Task 7.2**: Implement Zero-Dependency Vector Similarity Engine (`core/vector.py`) for packed byte embeddings, int8 quantization, and ultra-fast pure Python cosine similarity (<15ms across 31,102 vectors without numpy or external vector DBs).
- [ ] **Task 7.3**: Implement Stratified Exegetical Prompt Architecture & TGC Hermeneutical System in `core/semantic_prompts.py` (macro-book context injection, pericope propositions, discourse rhetoric, along/across theological loci, and agent triples).
- [ ] **Task 7.4**: Implement Automated Exegetical Critic & Quality Audit Suite (`core/semantic_audit.py`) validating canonical coordinate boundaries (`BBCCCVVV`), anti-moralistic compliance, character entity deduplication, and 100% whole-Bible verse coverage.
- [ ] **Task 7.5**: Implement Resumable Batch Semantic Compilation Engine (`tools/build_semantic_db.py` / `./bible build-semantic`) featuring a SQLite checkpoint ledger, rate limiting, book-by-book resume, and progress telemetry.
- [ ] **Task 7.6**: Execute one-shot compilation over the ESV corpus to generate and compile the complete, permanent semantic database pack into `data/bible.db`, verifying 100% offline queryability, FTS5 sync, and vector search.


### Phase 8: Online Scripture RAG & Biblical Character Dialogue Studio
- [ ] **Task 8.1**: Implement Scripture RAG retrieval engine in `core/rag.py` (combines FTS5 keyword search, semantic tag intersection, and cross-reference expansion to build grounded, hermeneutically focused context windows).
- [ ] **Task 8.2**: Implement CLI RAG inquiry command (`./bible ask "Trace the theme of the temple from the Garden of Eden to the New Jerusalem"`, `./bible ask "How does Jesus fulfill the Day of Atonement?"`).
- [ ] **Task 8.3**: Implement Biblical Character Dialogue Engine in `core/persona.py` (dynamically loads character scripture citations and historical background, enforces TGC anti-moralistic and Christ-centered humility guardrails, and strictly forbids extrabiblical inventions).
- [ ] **Task 8.4**: Implement CLI character dialogue command (`./bible chat paul`, `./bible chat moses`, `./bible chat david`, `./bible chat peter`).
- [ ] **Task 8.5**: Expose REST endpoints in web server (`/api/rag`, `/api/chat/persona`, `/api/characters`) with graceful offline status handling when `GEMINI_API_KEY` is not present.
- [ ] **Task 8.6**: Build interactive Web UI panels: Split-Screen Scripture Reader with dynamic RAG study notes and Interactive Biblical Character Dialogue Studio.



