# Architectural Decision Records (ADRs)

This document is an append-only log of significant design and architectural decisions made by developers and autonomous agents. When faced with ambiguity or multiple viable design paths, agents evaluate options, make a decision, and record it here.

---

## ADR-001: Autonomous Agent Development Protocol ("Ralph Loop")
- **Date**: 2026-09-06
- **Status**: Accepted
- **Context**: The repository is intended to be developed end-to-end by autonomous LLM agents without interactive human supervision at every step. Without an orchestrator, agents risk losing context, diverging from high-level goals, or halting indefinitely on minor ambiguities.
- **Decision**:
  1. Adopt the Ralph Loop lifecycle: Boot → Select from Backlog → Implement & Test → Log Progress → Self-Terminate.
  2. Treat documentation (`MANIFESTO.md`, `ROADMAP.md`, `DECISIONS.md`, `AGENT_LOG.md`) as state machines.
  3. Agents make decisions under ambiguity without stopping to prompt the user, recording the decision in this document.
  4. True blockers (missing secrets/keys or hardware barriers) are recorded in `BLOCKED.md` for human review.
- **Consequences**:
  - Agents remain unblocked and autonomous.
  - Clear traceability of why certain technical paths were taken.
  - Human owner can inspect decisions retrospectively.

---

## ADR-002: Repository Modular Directory Restructuring & Legacy Preservation
- **Date**: 2026-09-06
- **Status**: Accepted
- **Context**: The repository previously had flat root files (`fetch.lua`, `bible.typ`, `.gitignore`, `README.md`) prototyping ESV API fetching and ImageMagick/Typst image generation. To support a multi-component system (CLI, database, web UI, tagging), a structured modular layout is needed.
- **Decision**:
  - Move prototype scripts to `legacy/` preserving git history and functioning code.
  - Establish a modular directory skeleton:
    - `core/`: Core scripture reference parser, database schema, and storage engines.
    - `cli/`: Command-line interface definitions and commands.
    - `web/`: Local web visualization UI and dashboard.
    - `data/`: Local database storage, public domain texts, and schema migrations.
    - `legacy/`: Preserved initial Lua and Typst prototypes.
- **Consequences**:
  - Keeps root clean and organized.
  - Clear domain boundaries for upcoming implementation tasks.

---

## ADR-003: Zero-Dependency Architecture for Zero Maintenance & Dependabot Immunity
- **Date**: 2026-09-06
- **Status**: Accepted
- **Context**: The human owner will never manually write or maintain code in this repository. All code is agent-written. A primary operational constraint is **near-zero maintenance**: the project must never spam the owner with GitHub Dependabot security alerts or break due to upstream package churn. Modern web toolchains (npm/Node, React, Vite, D3) and complex crate/pip dependency trees require constant security bumping and version maintenance.
- **Decision**:
  1. **Zero External Dependencies**: Build the entire platform using **Python 3 Standard Library only** (Python 3.10+):
     - CLI: built-in `argparse`
     - Database: built-in `sqlite3` (with FTS5 full-text search)
     - Web Server: built-in `http.server` with JSON REST endpoints
     - Data models: built-in `dataclasses`, `json`, `typing`
     - Tests: built-in `unittest`
     - Obfuscation/Encryption: built-in `hashlib` & pure-standard-library keystream cipher
  2. **Zero npm / Node.js**: The Web UI dashboard will be written entirely in **Vanilla HTML5, CSS3, and JavaScript** with native browser SVG for heatmaps and graphs. No `package.json`, no `node_modules`, no bundler, no build step.
  3. **Zero Security Alerts**: With zero external third-party packages, GitHub Dependabot will never trigger vulnerability notifications.
  4. **High Agent Ergonomics**: LLMs possess near-flawless knowledge of the Python standard library and standard browser APIs, eliminating build toolchain failures, compiler lifetime issues, and transitive dependency breakage.
- **Consequences**:
  - The codebase can sit untouched for a decade and still run identically on any machine with Python 3.
  - No npm or pip security vulnerability notices ever.
  - Completely self-contained, lightning-fast test suite (`python3 -m unittest discover`).

---

## ADR-004: Mandatory Immediate Remote Push
- **Date**: 2026-09-06
- **Status**: Accepted
- **Context**: Because development occurs via autonomous ephemeral agents and loop runners, commits remaining only on the local machine create risks of desynchronization, lost state, and invisible progress on GitHub.
- **Decision**:
  - Every agent must immediately push every commit to `origin/main` (`git push origin main`).
  - No commit is considered complete until it is successfully pushed to the remote repository.
  - Any blocker recorded in `BLOCKED.md` must also be committed and pushed immediately.
- **Consequences**:
  - GitHub remote is always in perfect synchronization with local development.
  - Remote CI / observers / GitHub activity feeds reflect real-time progress.

---

## ADR-005: TV Screensaver Verse Slide Architecture & Dual-Backend Rendering Engine
- **Date**: 2026-09-06
- **Status**: Accepted
- **Context**: The user requested a feature to generate beautiful landscape image slides from the CLI featuring white scripture text on a black background, designed specifically for Google Photos slideshows on home TV screensavers. The implementation must accommodate passages of varying lengths (from two words to multi-verse pericopes) with balanced typography and safe margins, while strictly honoring ADR-003 (Zero external pip/npm dependencies).
- **Decision**:
  1. **Primary Raster Backend (ImageMagick CLI)**: Utilize the host system's existing ImageMagick installation (`magick` or `convert`) via Python's standard library `subprocess`. ImageMagick provides hardware-accelerated text rasterization, Pango rich text formatting, fontconfig integration, and high-quality anti-aliasing without requiring Python pip dependencies (`Pillow`, `cairosvg`, etc.).
  2. **Zero-Binary Vector Backend (Pure Python SVG)**: Provide a built-in pure Python standard library SVG generator for vector output and environments lacking ImageMagick.
  3. **TV Display & Screensaver Optimizations**:
     - **Default Resolution**: 16:9 4K UHD (3840x2160) for maximum clarity on modern 4K/8K displays, with selectable 1080p (1920x1080) and custom dimensions.
     - **OLED Pure Black**: Background defaults to `#000000` to completely power off OLED pixels, yielding infinite contrast and eliminating burn-in.
     - **TV Safe Area Margins**: Enforce a 15% inner bounding box so text never clips on bezel edges or TV overscan.
     - **Dynamic Typography Scaling**: Implement an auto-fit scaling algorithm that bounds font sizes with upper/lower limits (preventing short verses from appearing comically gigantic and long passages from shrinking below readable thresholds from a 10-foot couch distance).
     - **Optical Vertical Centering**: Offset text slightly above mechanical dead-center (~45% baseline) for natural human aesthetic perception.
     - **Hierarchical Citation**: Render reference citations in smaller, muted typography (e.g., `#AAAAAA`) separated from the scripture body.
     - **Multi-Slide Splitting**: Long passages exceeding single-slide legibility thresholds can be split across consecutive slide frames (`1/N`).
     - **Format Support**: Default to PNG (lossless, highly compressible on black backgrounds) with optional JPEG (`--quality=95`) for legacy TV media player compatibility.
- **Consequences**:
- Full compliance with ADR-003: zero pip requirements, zero Dependabot alerts.
  - Generates TV-ready 4K images natively.
  - Directly fulfills user's home TV screensaver workflow via Google Photos.

---

## ADR-006: Google Gemini LLM Architecture & TGC Theological Hermeneutic Framework
- **Date**: 2026-09-06
- **Status**: Accepted
- **Context**: The user requested integrating Large Language Models (LLMs) to unlock deep semantic understanding of Scripture. Specifically:
  1. **Offline Metadata Enrichment**: Pre-generating rich biblical metadata (thematic taxonomies, pericopes, typology, cross-references, character profiles) into the local SQLite database so the application functions sovereignly offline.
  2. **Online Interactive Intelligence**: Enabling real-time Scripture RAG (Retrieval-Augmented Generation) for cross-referencing and interactive dialogue with biblical figures.
  3. **Theological Alignment**: All theological and hermeneutical principles must adhere to The Gospel Coalition (TGC) Foundation Documents (Confessional Statement & Theological Vision for Ministry).
  4. **Vendor & Tooling Standard**: Default model must be Google's current premier model (e.g. `gemini-2.5-pro` / `gemini-2.0-flash`).
  5. **Architecture Mandate**: Must strictly preserve ADR-003 (Zero External Dependencies, no pip/npm packages, zero Dependabot alerts).
- **Decision**:
  1. **Zero-Dependency Google Gemini REST Client (`core/llm.py`)**:
     - Implement a lean, robust API client using Python's standard library `urllib.request`, `json`, and `os`.
     - Target the Google Gemini REST endpoint (`https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`).
     - Default model identifier: `gemini-2.5-pro` (configurable via `--model` flag or `GEMINI_MODEL` env var, with fallback to `gemini-2.0-flash`).
     - Authentication: reads `GEMINI_API_KEY` from environment.
     - Zero third-party packages (`google-generativeai`, `requests`, `aiohttp` are prohibited).
  2. **Two-Tier Offline vs. Online Architecture**:
     - **Tier 1 (Offline Sovereign Database)**: A batch generator CLI (`bible enrich`) uses Gemini to synthesize and populate SQLite tables (`pericopes`, `typology_edges`, `theological_themes`, `character_profiles`). Once ingested, 100% of these enriched features run locally and offline without internet or API keys.
     - **Tier 2 (Online Dynamic RAG & Character Dialogue)**: When `GEMINI_API_KEY` is present, the Web UI and CLI unlock dynamic conversational synthesis and interactive character dialogue, grounded against local SQLite scripture verses. If the API key is missing or offline, the system degrades gracefully with clear status messaging.
  3. **TGC Foundation Hermeneutical System Prompt Protocol**:
     - System prompts and semantic tag taxonomies are explicitly guided by TGC's Foundation Documents:
       - **Dual-Horizon Hermeneutics**: Balance reading *along* the whole Bible (redemptive-historical trajectory: Creation, Fall, Redemption, Restoration climaxing in Christ) and reading *across* the whole Bible (systematic theological categories: God, sin, substitutionary atonement, justification by grace through faith).
       - **Christ-Centered & Anti-Moralistic**: Biblical figures and narratives are never framed in isolated moralism ("Dare to be a Daniel"); rather, they are presented as fallible instruments in God's redemptive history pointing to the true and better Prophet, Priest, and King, Jesus Christ.
       - **Scriptural Infallibility & Reverence**: Responses maintain deep reverence, accuracy to the text, and reject theological relativism or flippant anachronism.
  4. **Biblical Character Dialogue ("Persona In Scripture") Safety & Constraints**:
     - Characters speak strictly from the biblical record of their historical period, context, and canonical testimony.
     - They express humble faith in Yahweh / Christ, candidly acknowledge their sins and failures recorded in Scripture, and decline speculative or extra-biblical doctrine.
- **Consequences**:
  - Full compliance with ADR-003: No pip dependencies, zero Dependabot alerts.
  - First-class support for Google's best LLM models.
  - Faithful, intellectually rigorous theological alignment with The Gospel Coalition.
  - Offline-first sovereignty with optional online AI power.

---

## ADR-007: Terminal-Native Ralph Loop Runner via Jetski CLI (`--dangerously-skip-permissions`)
- **Date**: 2026-09-06
- **Status**: Accepted
- **Context**: The initial `ralph.sh` runner attempted to orchestrate autonomous cycles using a background `agentapi new-conversation` subshell while polling git commits. In practice, this background daemon model was brittle, opaque, failed on interactive tool permission prompts, and did not suit the developer's desired interactive terminal workflow. The developer requested invoking Jetski directly in the terminal via `/google/bin/releases/jetski-devs/tools/cli --dangerously-skip-permissions` with an explicit initial prompt to execute one Ralph loop iteration.
- **Decision**:
  1. **Direct Terminal Execution**: Retire the background `agentapi` loop runner in `ralph.sh`.
  2. **Jetski CLI as Canonical Terminal Runner**:
     - Developers can invoke the Ralph loop directly in their terminal using:
       `/google/bin/releases/jetski-devs/tools/cli --dangerously-skip-permissions -i "Execute one cycle of the Ralph loop per AGENTS.md."`
     - Or invoke the convenient local wrapper `./ralph.sh` which defaults to this exact command.
  3. **Auto-Approve Tool Permissions**: `--dangerously-skip-permissions` is mandatory for autonomous execution to ensure file edits, command execution, and test suites run unblocked without hanging on human modal confirmations.
  4. **Interactive, Print, and Continuous Loop Flexibility**:
      - Default mode uses `-i` (`--prompt-interactive`), launching the interactive terminal TUI with the prompt pre-loaded, giving the user live progress visibility and interactive access upon completion.
      - Non-interactive headless/print mode is supported via `-p` / `--print`.
      - **Continuous Loop Mode** is supported via `--loop` / `-l [N]`. It executes iterative headless cycles sequentially, incorporating crucial automated guardrails:
        - **Blocker Guard**: Immediately halts if `BLOCKED.md` is detected to prevent runaway token burning.
        - **Roadmap Guard**: Automatically stops when all tasks in `ROADMAP.md` are marked complete.
        - **Timeout Extension**: Automatically sets `--print-timeout 30m` so heavy operations (e.g. multi-step testing or bulk DB ingestion) do not abort prematurely on Jetski's default 5-minute timeout.
        - **Cooldown & Interruption**: Enforces a clean pause between cycles and traps `SIGINT` (Ctrl+C).
- **Consequences**:
   - Direct, transparent terminal feedback during loop execution.
   - Reliable execution without background process desynchronization.
   - Seamless developer ergonomics: run single turns interactively or chain cycles hands-free until complete.

---

## ADR-008: Canonical Integer ID Encoding & SQLite FTS5 Trigger Architecture
- **Date**: 2026-09-06
- **Status**: Accepted
- **Context**: In Task 1.2, the Bible Engine requires a relational database schema in SQLite (`core/db.py`) supporting 66 canonical books, multi-translation verse storage, arbitrary multi-verse passage spans, multi-resolution semantic tags, cross-references, and lightning-fast full-text search. Relational systems often struggle with scripture range queries (e.g. querying whether a tag on Romans 8:1-11 applies to Romans 8:5, or retrieving all verses in a cross-chapter span like Genesis 1:1 - 2:3) if based on text strings or separate book/chapter/verse columns. Furthermore, SQLite full-text search (FTS5) requires synchronization with the underlying verses table.
- **Decision**:
  1. **Canonical Integer ID Encoding (`BBCCCVVV`)**:
     - Encode every canonical verse as an integer:
       `canonical_verse_id = book_number * 1,000,000 + chapter * 1,000 + verse`
     - Valid for all 66 books (OT: 1-39, NT: 40-66), all chapters (max Psalm 150 < 1,000), and all verses (max Psalm 119:176 < 1,000).
     - Single verses, intra-chapter spans, cross-chapter spans, whole chapters, and multi-chapter ranges map to exact `[start_canonical_id, end_canonical_id]` intervals.
     - Fast, indexed B-Tree range scans: `WHERE canonical_verse_id BETWEEN :start AND :end` retrieves all verses in canonical order.
     - Overlapping range check for multi-resolution tagging and cross-references:
       `WHERE start_canonical_id <= :query_end AND end_canonical_id >= :query_start` enables immediate matching across verses, pericopes, and chapters.
  2. **SQLite FTS5 Automatic Trigger Synchronization**:
     - Build full-text search using SQLite's native FTS5 virtual table with `porter unicode61` tokenization.
     - Attach `AFTER INSERT`, `AFTER UPDATE`, and `AFTER DELETE` triggers on the `verses` table to maintain the `verses_fts` virtual table in real time without application-level double writes or out-of-sync risks.
  3. **Robust Query Sanitization**:
     - Provide `sanitize_fts_query` to parse user queries, supporting exact quoted phrases and Boolean operators (`AND`, `OR`, `NOT`) while stripping problematic punctuation that could cause SQLite syntax errors.
  4. **Strict Zero-Dependency Compliance**:
     - Built entirely on Python 3 standard library `sqlite3` and `dataclasses`.
- **Consequences**:
  - Passage retrieval and full-text search are instantaneous and hermetic.
  - Multi-resolution semantic tagging works uniformly across verses, pericopes, and books.
  - Fully compliant with ADR-003 (zero external dependencies, zero Dependabot alerts).

---

## ADR-009: World English Bible (WEB) Ingestion & Offline Pack Compilation Pipeline
- **Date**: 2026-09-06
- **Status**: Accepted
- **Context**: Task 1.3 requires ingesting a full public domain Bible translation (World English Bible - WEB) into a bundled SQLite database (`data/bible.db`) for offline access. The translation must cover all 66 Protestant canonical books (~31,102 verses) with complete fidelity to chapter and verse structures, zero external dependencies, and reproducible local compilation.
- **Decision**:
  1. **Canonical Public Domain Translation**: Select the World English Bible (WEB) as the foundational offline scripture translation. It is 100% dedicated to the public domain by Rainbow Missions, Inc., modern English, and legally redistributable without licensing encumbrances.
  2. **Two-Tier Raw Cache & SQLite Compilation (`tools/ingest_web.py`)**:
     - Raw JSON files for all 66 canonical books are downloaded and cached in `data/raw/web/{book}.json` (9.9MB total).
     - Because raw JSON files are committed to the repository, subsequent builds and test runs operate 100% offline without network calls.
     - A dedicated compilation pipeline aggregates paragraph text and poetic line fragments into complete canonical verses, assigns canonical integer IDs (`BBCCCVVV`), and batch-inserts all 31,103 verses using `sqlite3.executemany` within an atomic transaction.
  3. **Automated Search Indexing & Compaction**:
     - SQLite FTS5 triggers automatically synchronize full-text search tokens for all 31,103 verses during insertion.
     - Post-insertion runs `PRAGMA optimize` to generate optimal query planner statistics and `VACUUM` to defragment the SQLite database file into a production-ready package.
  4. **Strict Zero-Dependency Compliance**:
     - Implemented entirely with Python 3 standard library (`urllib.request`, `json`, `sqlite3`, `pathlib`, `collections`).
- **Consequences**:
  - Offline-first sovereignty guaranteed: full Bible text is available instantly without internet or external APIs.
  - Lightning-fast hermetic compilation: ~31,103 verses compiled in under 5 seconds.
  - Full compliance with ADR-003 (Zero Dependencies, Zero Dependabot alerts).

---

## ADR-010: Zero-Dependency ChaCha20-HMAC Authenticated Keystream Cryptosystem
- **Date**: 2026-09-06
- **Status**: Accepted
- **Context**: In Task 1.4 and Manifesto Pillar II (Public Domain First & Copyright Safety), copyrighted Bible translations (e.g., ESV, NIV, NASB) and sensitive user notes/data packs must never appear unencrypted in public repositories. Furthermore, per ADR-003 (Zero External Dependencies), the system cannot link against OpenSSL C extensions or rely on pip cryptography libraries (`cryptography`, `pycryptodome`), which are major sources of Dependabot alerts and build portability issues.
- **Decision**:
  1. **Pure Python RFC 7539 ChaCha20 Stream Cipher (`core/crypto.py`)**:
     - Implement the RFC 7539 ChaCha20 specification directly in standard Python using 32-bit unsigned word operations via `struct` and bitwise rotations.
     - Verified rigorously against official RFC 7539 Section 2.3.2 block vector and Section 2.4.2 multi-block encryption vector.
  2. **Encrypt-then-MAC Authentication (HMAC-SHA256)**:
     - Combine ChaCha20 keystream encryption with HMAC-SHA256 over the entire encrypted payload and header using Python's standard library `hmac` and `hashlib`.
     - Key separation via HKDF-style context strings (`BIBLE_ENC_KEY_V1` and `BIBLE_MAC_KEY_V1`) from the master key.
     - Constant-time verification using `hmac.compare_digest` to prevent timing side-channel attacks.
  3. **PBKDF2-HMAC-SHA256 Key Derivation**:
     - Passwords/passphrases are converted to 256-bit symmetric keys using Python's standard library `hashlib.pbkdf2_hmac` with configurable iterations (default 100,000) and cryptographically random 16-byte salts.
  4. **Self-Describing Sovereign Binary Pack Wire Format (`.bpack`)**:
     - Wire format: `[MAGIC_HEADER: 14 bytes ('BIBLE_PACK_V1\x00')]` + `[iterations: 4 bytes BE]` + `[salt: 16 bytes]` + `[nonce: 12 bytes]` + `[hmac_tag: 32 bytes]` + `[ciphertext: N bytes]`.
  5. **Strict Zero-Dependency Compliance**:
     - 100% Python 3 standard library (`struct`, `hmac`, `hashlib`, `secrets`, `os`).
- **Consequences**:
  - Copyrighted translations and personal data packs can be safely distributed or stored locally in encrypted form.
  - Zero external C/pip dependencies: 100% immune to Dependabot alerts and cross-platform installation issues.
  - Verified 100% against RFC 7539 standard test vectors.




---

## ADR-011: Unified Core Integration & Hermetic Test Architecture
- **Date**: 2026-09-06
- **Status**: Accepted
- **Context**: Phase 1 established four core modules: `core/reference.py`, `core/db.py`, `tools/ingest_web.py`, and `core/crypto.py`. Each module has isolated unit tests, but Task 1.5 requires a unified integration test suite in `tests/test_core.py` verifying cross-cutting workflows, package-level exports (`__all__`), and end-to-end data pipelines without external test fixtures, network access, or third-party libraries.
- **Decision**:
  1. **Top-Level Package Interface Contract (`core/__init__.py`)**:
     - The `core` module explicitly exposes its complete public API via `__all__`, covering reference objects (`Book`, `Reference`, `parse_reference`, `ALL_BOOKS`), database models (`Database`, `VerseRecord`, `TagRecord`, `CrossReferenceRecord`, `SearchResult`), and cryptographic routines (`ChaCha20`, `encrypt_string`, `decrypt_string`, `encrypt_text_pack`, `decrypt_text_pack`).
     - `tests/test_core.py` tests both public export introspection and functional contracts.
  2. **Multi-Stage End-to-End Pipeline Testing**:
     - `tests/test_core.py` establishes multi-stage integration tests demonstrating complete data lifecycles:
       - Parsing OT prophecy references ("Micah 5:2", "Isaiah 53:5") and NT fulfillments ("Matthew 2:6", "1 Peter 2:24").
       - In-memory database persistence with automatic Protestant 66-book catalog seeding.
       - Bidirectional cross-reference graph links with typed relationships (`prophecy_fulfillment`, `typology`).
       - Semantic tagging and first-class starred favorites curation.
       - SQLite FTS5 synchronized search matching across passages.
       - Encrypting database verse text via PBKDF2 + ChaCha20-HMAC into authenticated ciphertext and sovereign `.bpack` files, followed by tamper detection and decrypting.
  3. **Hermeticity & Performance**:
     - 100% Python standard library `unittest`.
     - In-memory SQLite (`:memory:`) and `tempfile.TemporaryDirectory` guaranteeing complete isolation and zero side effects.
     - Entire 94-test suite executes in under 5 seconds.
- **Consequences**:
  - Full confidence in cross-module interoperability before building Phase 2 CLI.
  - 100% Zero-Dependency compliance (ADR-003).

---

## ADR-012: Curated Favorites Ingestion & Curation Architecture
- **Date**: 2026-09-06
- **Status**: Accepted
- **Context**: In Task 1.6, the user's personal curated dataset [`favorite_bible_verses.csv`](file:///usr/local/google/home/markwell/personal_dev/bible/favorite_bible_verses.csv) contains 829 scripture passage entries spanning the Protestant canon, with 50 marked as high-priority starred passages (`starred=TRUE`). These records include single verses, intra-chapter verse spans, and entire chapters. The database schema in `core/db.py` must ingest and represent these favorites as first-class entities while enabling fast retrieval for CLI display, web dashboards, and Phase 5 TV screensaver batch export (`bible slide-batch --favorites`).
- **Decision**:
  1. **First-Class Semantic Tag Modeling**:
     - Model favorites under the semantic tagging architecture in `tags` and `verse_tags` using tag name `favorites` and category `curation`.
     - Store the boolean priority flag in the indexed `starred` column (`0` or `1`) on `verse_tags`.
     - Canonical integer IDs (`BBCCCVVV`) are assigned to `start_canonical_id` and `end_canonical_id`, supporting fast interval overlap checks against any scripture reference (`start_canonical_id <= :query_end AND end_canonical_id >= :query_start`).
  2. **Zero-Dependency Batch Ingestion Pipeline (`tools/ingest_favorites.py`)**:
     - Built using Python 3 standard library `csv`, `sqlite3`, `pathlib`, and `argparse` per ADR-003.
     - Automatically cleans and parses each CSV row into a canonical `Reference` object via `core/reference.py`.
     - Incorporates safe dataset typo correction (e.g. correcting `Mark 1:223-26` to `Mark 1:23-26`) with explicit audit notes in the record.
     - Supports idempotent re-runs with automatic tag clearing (`clear_tag`) and batch insertion (`tag_references_batch`) within an atomic transaction.
  3. **High-Level Curation API in Database (`core/db.py`)**:
     - `tag_references_batch(items, tag_name='favorites', ...)`: high-performance batch insertion using `sqlite3.executemany`.
     - `clear_tag(tag_name)`: atomic deletion of all association rows for a given tag.
     - `tag_as_favorite(reference, starred, notes)`: convenience single-reference favorite tagging.
     - `get_favorites(starred_only=False)`: retrieval of all favorite passages or filtered by priority starred status in canonical scripture order.
  4. **Strict Zero-Dependency Compliance**:
     - 100% Python standard library, zero pip/npm requirements.
- **Consequences**:
  - All 829 curated favorites (including 50 starred) are persistent, queryable, and indexed in `data/bible.db`.
  - Seamless integration with future CLI (`bible get --favorites`) and screensaver generator (`bible slide-batch --favorites`).
  - Hermetically tested in `tests/test_favorites.py`.

---

## ADR-013: Subcommand CLI Architecture & Terminal Scripture Formatter Entry Point
- **Date**: 2026-09-06
- **Status**: Accepted
- **Context**: In Phase 2 Task 2.1, the Bible Engine requires a command-line interface entry point (`bible.py` and executable `./bible`) to provide immediate scripture lookup (`./bible get "John 3:16"`). The CLI must support flexible argument structures (quoted citations, unquoted arguments like `bible get Romans 8:28-30`, cross-chapter spans, whole books), configurable database path overrides (`--db`), translation selection (`--version=WEB`), output customization (`--no-numbers`, `--no-header`), and clean, human-friendly error reporting, while strictly complying with ADR-003 (Zero External Dependencies, Python standard library only).
- **Decision**:
  1. **Dual Entry Point Architecture (`cli/main.py` + `bible.py` + `./bible`)**:
     - Implement core CLI dispatching, argument parsing, and command handlers in `cli/main.py`.
     - Provide top-level root executable `bible.py` and executable symlink `./bible` (`chmod +x`) configured with `#!/usr/bin/env python3`.
     - Automatically configure `sys.path` to ensure absolute package imports (`core.db`, `core.reference`) function identically regardless of the user's invocation working directory.
  2. **Standard Library Subcommand Dispatcher (`argparse`)**:
     - Built using standard library `argparse` with structured subcommands (`get`, with planned extensions `search`, `favorites`, `pack`, `serve`, `slide`).
     - Global flags: `--db` for overriding SQLite file path, `--version` / `-v` for tool versioning, and auto-generated `--help`.
     - Subcommand `get` captures citation tokens via `nargs="+"`, seamlessly supporting both quoted (`"John 3:16"`) and unquoted (`John 3 16` / `Romans 8:28-30`) CLI arguments.
  3. **Readable Terminal Output Formatting**:
     - Implemented `format_verse_lines` providing clean passage headers (e.g. `=== Romans 8:28-30 (WEB) ===`), bracketed verse numbers (`[28] ...`), and flags to suppress numbers or headers for shell scripting or piping (`--no-numbers`, `--no-header`).
  4. **Hermetic Testing & Zero-Dependency Compliance**:
     - 100% Python 3 standard library (`argparse`, `sys`, `pathlib`, `unittest`).
     - Hermetically tested in `tests/test_cli.py` using in-memory/temporary SQLite databases and `unittest.mock.patch` over `sys.stdout` and `sys.stderr`.
- **Consequences**:
  - Developers and users can immediately query scripture from the terminal via `./bible get "John 3:16"`.
  - Seamless scriptability with zero external pip/npm packages (ADR-003).
  - Clean foundation for Task 2.2 (`--version` cascades) and Task 2.3 (`search`).

---

## ADR-014: Real-Time Live Streaming Telemetry for Autonomous Ralph Loop Harness
- **Date**: 2026-09-06
- **Status**: Accepted
- **Context**: When running continuous autonomous iterations with `./ralph.sh --loop`, the harness executes Jetski CLI in headless print mode (`-p`). In default print mode (`--output-format text`), Jetski only streams `TextDelta` tokens and suppresses all tool execution events (running bash commands, running unit tests, inspecting/editing files). Because an autonomous cycle spends >90% of its execution time running tools before emitting its final Executive Briefing, the terminal output remained silent for 5–15 minutes, appearing hung or frozen to the human observer. Running interactive mode (`-i`) inside a loop was not viable because interactive mode stays open waiting for user input and does not exit on turn completion.
- **Decision**:
  1. **Utilize Jetski NDJSON Streaming Mode (`--output-format stream-json`)**:
     - Switch `ralph.sh` (`--loop` and `--print`) to invoke Jetski with `--output-format stream-json`.
     - In this mode, Jetski emits strongly typed NDJSON events (`init`, `step_update`, `result`) in real time for every tool invocation, argument payload, execution status, and streaming text token.
  2. **Zero-Dependency Streaming Event Formatter (`tools/stream_runner.py`)**:
     - Implement a standalone Python utility using the Python 3 standard library (`sys`, `json`, `datetime`, `os`) per ADR-003.
     - Formats active tool calls with concise parameter summaries (e.g. `⚙ [TOOL] run_command : python3 -m unittest discover tests`).
     - Emits tool completion timings (`✔ [DONE] run_command (1.25s)`).
     - Flushes streaming model text deltas live to `sys.stdout`.
     - Emits final session summary cards with token counts and duration.
     - Preserves clean process exit codes (exit 0 on success, exit 1 on error) so `ralph.sh` can monitor loop health and stop on failures.
  3. **Robust Bash Pipeline Integration in `ralph.sh`**:
     - Pipe Jetski CLI into `python3 "$REPO_DIR/tools/stream_runner.py"`.
     - Inspect `PIPESTATUS` to correctly capture both Jetski's and the formatter's exit status while honoring `pipefail`.
- **Consequences**:
  - The human observer can watch Jetski work in real time during continuous `--loop` execution (watching every tool call, test execution, and streamed thought).
  - The process continues to terminate cleanly at the end of each turn, allowing the `while` loop to advance autonomously without manual intervention.
  - Fully tested in `tests/test_stream_runner.py` with 100% test pass rate and zero external dependencies.

---

## ADR-015: Senior Product Manager Meta-Improvement Cadence & System Health Sprint Protocol (Every 5th Iteration)
- **Date**: 2026-09-06
- **Status**: Accepted
- **Context**: In autonomous, multi-turn software development loops (such as the Ralph Loop), agents naturally optimize locally for the immediate roadmap ticket assigned to them. Over multiple consecutive feature iterations, this creates systemic blind spots: process friction, harness fragility, telemetry opacity, architectural drift, documentation lag, and slow test fixtures remain unaddressed because no individual ticket owns them. The user requested formalizing a recurring sprint cadence: every 5th iteration must transform into a dedicated "cleanup" sprint where the agent acts as a Senior Product Manager, diagnosing whole-system health and executing meta-improvements to how the project accomplishes itself.
- **Decision**:
  1. **Every-5th-Iteration Cadence**:
     - Automatically designate every 5th iteration (Run #005, #010, #015, #020..., `run_number % 5 == 0`, loop iteration % 5 == 0, or on-demand via `./ralph.sh --cleanup` / `-c`) as a **Senior Product Manager Meta-Improvement & System Health Sprint**.
  2. **Role & Cognitive Shift**:
     - The agent transitions from a domain task executor to a Senior Product Manager and Meta-Architect.
     - The agent is **strictly prohibited** from advancing standard domain roadmap tasks during this sprint.
     - Focus shifts entirely to *meta-improvements* — improving the processes, tooling, test velocity, documentation integrity, and architecture that the project uses to accomplish itself.
  3. **Mandatory Core Diagnostic Questions**:
     - The sprint must directly evaluate and answer:
       1. *"What is the weakest aspect of this project structure?"*
       2. *"What is preventing this from being more incredible?"*
  4. **Unconditional Execution Mandate ("Nothing is Disallowed")**:
     - The sprint must formulate at least **one Rank A+ idea** targeting meta-system enhancement or cleanup.
     - If the idea is of Rank A+ quality, the agent has full ownership to **execute it immediately** during the sprint. Nothing is disallowed (refactoring structures, optimizing harnesses, overhauling test fixtures, introducing zero-dependency developer tools).
  5. **Verification & Audit Artifacts**:
     - All changes must be verified hermetically with a 100% test pass rate.
     - Architectural decisions recorded in `DECISIONS.md`.
     - Rank A+ feature request logged in `IDEAS.md`.
     - Logged under a dedicated header in `AGENT_LOG.md` (`[Run XXX — Senior PM Cleanup Sprint]`).
     - Immediately committed and pushed to `origin/main` per ADR-004.
  6. **CLI & Harness Integration**:
     - `ralph.sh` automatically detects run counts from `AGENT_LOG.md` via `get_next_run_number()`.
     - In `--loop` mode, every 5th cycle prints a prominent Senior PM banner and injects `CLEANUP_PROMPT`.
     - Provides `./ralph.sh --cleanup` / `-c` for running meta-sprints on demand.
- **Consequences**:
  - Eliminates the buildup of technical and process debt.
  - Ensures continuous, compounding evolution of developer tooling, test speed, and autonomous harness reliability.
  - Balances raw feature throughput with regular architectural reflection and system elevation.

---

## ADR-016: Automated Repository Doctor & Health Verification Engine (`tools/doctor.py` / `bible doctor`)
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: In autonomous multi-agent development cycles, agents enforce architectural constraints (ADR-003 Zero-Dependency, state machine document synchronization, test hermeticity, database integrity) through discipline and instruction reading. However, human and LLM oversight can experience occasional regression or subtle drift: an agent might inadvertently import an external module, leave orphaned ADR references, create non-contiguous run logs, or push code with slow or failing tests. To guarantee long-term sovereign maintenance, a fast (<1.5s), automated, zero-dependency diagnostic verification engine was needed that can be executed on-demand via the CLI (`./bible doctor`), programmatically by pre-commit hooks, or automatically between Ralph loop iterations.
- **Decision**:
  1. **Zero-Dependency Diagnostic Engine (`tools/doctor.py`)**:
     - Implement a standalone diagnostic tool using Python 3 standard library only (`ast`, `re`, `subprocess`, `unittest`, `dataclasses`, `time`, `pathlib`).
     - Five core diagnostic pillars:
       1. *Zero External Dependencies (AST Audit)*: Parses the Abstract Syntax Tree of all `.py` files across the repository to verify that only Python 3 standard library modules and internal first-party packages are imported. Catches any pip packages before they enter the repository.
       2. *Documentation State Machine Synchronization*: Validates that all ADRs referenced in `AGENT_LOG.md` exist in `DECISIONS.md`, that `AGENT_LOG.md` run numbers are strictly contiguous, and that all Rank A+ ideas in `IDEAS.md` are accounted for in `ROADMAP.md` or `DECISIONS.md`.
       3. *Shell Script Integrity*: Validates bash script syntax (`bash -n ralph.sh`) and executable permissions.
       4. *SQLite Scripture Database Integrity*: Runs SQLite `PRAGMA quick_check` against `data/bible.db`, asserts WEB translation verse counts (~31,103 verses), and executes a live FTS5 query to ensure search index integrity.
       5. *Hermetic In-Process Test Suite*: Runs the entire hermetic unit test suite in-process via `unittest.TestLoader` to guarantee 100% test pass rate in <1.0 second without subprocess recursion.
  2. **First-Class CLI Subcommand (`./bible doctor`)**:
     - Integrate the doctor command directly into `cli/main.py` under `./bible doctor`.
     - Renders styled ANSI status badges (`[PASS]` / `[FAIL]`) when run in interactive terminals and clean text in non-TTY environments.
  3. **Continuous Ralph Loop Health Validation**:
     - Integrate automatic doctor invocation into `ralph.sh` following every successful loop cycle, immediately flagging any state degradation before the next turn boots.
  4. **Test Suite Hermetic Speed Optimization**:
     - Refactored `tools/ingest_web.py` to accept an optional `books` parameter, enabling test suites to verify full schema creation, parsing, translation registration, and FTS5 search using representative books (Genesis, John, Romans, Revelation) in ~0.35s rather than loading all 66 books (~4.8s).
     - Reduced full test suite execution duration from ~5.5s down to <2.9s.
- **Consequences**:
  - Zero third-party dependencies are deterministically enforced by AST analysis at the machine level.
  - Project state machine integrity (ADRs, run logs, roadmap items) cannot silently drift out of synchronization.
  - Test feedback velocity improved by ~50%, accelerating both human development and autonomous agent iterations.
  - 100% compliance with ADR-003 and Manifesto principles.

---

## ADR-017: Autonomous Executive Summary Cadence (Every 10th Iteration) & Trajectory Diagnostic Engine
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: In sovereign, zero-maintenance autonomous software development, the human author rarely inspects code diffs, raw logs, or individual commits. While the Senior Product Manager Cleanup Sprint (every 5th iteration, ADR-015) audits meta-processes and tooling, there was no structured, macro-level synthesis reviewing accomplishments across a 10-iteration window, calculating true velocity, forecasting remaining effort in iterations to complete the roadmap, and providing a unified health overview. The user requested: (1) an automatic executive summary every 10th Ralph iteration reviewing the last 10 iterations, and (2) an on-demand capability (such as a project skill or CLI command) to produce this summary at any time.
- **Decision**:
  1. **Zero-Dependency Executive Summary Generator (`tools/executive_summary.py`)**:
     - Built using Python 3 standard library only (`re`, `dataclasses`, `datetime`, `math`, `pathlib`).
     - Parses `AGENT_LOG.md` into structured run records (phase, task, key actions, verifications).
     - Parses `ROADMAP.md` across all 8 phases to calculate completed, in-progress, and pending tasks.
     - Computes empirical velocity (tasks per iteration) and calculates estimated remaining iterations to roadmap completion.
     - Automatically runs the full diagnostic suite (`tools/doctor.py`) to verify zero external dependencies, state synchronization, bash integrity, database health, and test pass rate.
  2. **First-Class CLI Subcommand (`./bible summary`)**:
     - Integrated into `cli/main.py` under `./bible summary [--window N] [--no-doctor]`.
     - Supports reviewing an arbitrary window of past iterations (default: 10).
  3. **Dedicated Project Skill (`skills/executive-summary/SKILL.md`)**:
     - Formally defined as an agent skill with instructions and execution workflows.
  4. **Autonomous Ralph Loop Cadence Integration (`ralph.sh`)**:
     - Updated `ralph.sh`: every 10th iteration (`run_number % 10 == 0`, e.g. Run #010, #020, #030...), injects `SUMMARY_PROMPT`, instructing the agent to first execute the **Senior Product Manager role** (answering the two diagnostic questions and executing a Rank A+ meta-improvement, since 10 is divisible by 5), and then conclude by delivering the curated **Human Executive Briefing post-summary**.
     - Added `--summary` / `-s` CLI flags to `ralph.sh` for triggering the executive summary on demand in terminal or headless mode.
  5. **Harmonized Cadence Hierarchy**:
     - Iterations divisible by 10 (`10, 20, 30...`) trigger the **Senior PM Meta-Sprint & 10th-Iteration Executive Briefing** double milestone.
     - Iterations divisible by 5 but not 10 (`5, 15, 25...`) trigger the **Senior PM Cleanup Sprint**.
     - All other iterations execute standard domain roadmap tasks.
- **Consequences**:
  - The 10th iteration cleanly preserves the 5-iteration cadence invariant (always performing Senior PM meta-engineering when divisible by 5) while appending the macro 10-run executive synthesis at the end.
  - The repository owner receives clear, high-level, low-noise milestone reviews every 10 iterations without needing to inspect commits.
  - Project completion trajectory and iteration estimates are empirically computed from live roadmap and log state.
  - The capability can be triggered on demand via CLI, python script, or skill.
  - Zero external dependencies are preserved (Python 3 stdlib only).

---

## ADR-018: Multi-Translation CLI Cascade, Fallback Resolution & Parallel Comparison Engine
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: Bible readers, scholars, and devotions regularly compare passages across multiple translations (e.g. formal equivalence like KJV/ESV vs. dynamic equivalence like WEB/NIV). Furthermore, while the public domain World English Bible (WEB) is bundled locally by default, user-provided copyrighted packs (e.g. ESV, NIV) may or may not be installed. A rigid single-translation CLI (`bible get --version=ESV`) would crash or exit with errors when a requested translation is absent, degrading user experience. Task 2.2 on the roadmap mandates multi-translation flag support with graceful fallbacks.
- **Decision**:
  1. **Translation Fallback Resolution Engine (`core/db.py`)**:
     - Added `get_available_translation_ids()` to query distinct translation IDs with populated verses.
     - Added `get_verses_with_fallback(reference, translation_id="WEB", fallback_id="WEB") -> Tuple[List[VerseRecord], str, bool]`: queries the requested translation; if unavailable or containing zero verses for the passage, seamlessly cascades to the configured fallback translation (default: `WEB`) and flags `is_fallback=True`.
     - Added `compare_verses(reference, translation_ids, fallback_id="WEB")` returning a structured dictionary of translation results.
  2. **Multi-Translation Lookup in `bible get` (`cli/main.py`)**:
     - Extended `--version` / `-t` to accept comma-separated strings (e.g. `--version=WEB,KJV`), repeated flags (`-t WEB -t KJV`), and list structures via `parse_translation_ids()`.
     - Added `--fallback` (default: `WEB`) and `--no-fallback` / `--strict` flags for controlling fallback behavior.
     - When fallback is utilized, outputs an informative notice to `sys.stderr` (`Notice: Translation 'ESV' not available; falling back to 'WEB'.`) and clearly labels the passage header `=== Reference (WEB [fallback for ESV]) ===`.
     - Sequentially outputs all requested translation blocks.
  3. **Parallel Multi-Translation Comparison Subcommand (`bible compare`)**:
     - Added dedicated subcommand `bible compare <reference> [--versions=WEB,KJV] [--mode=aligned|stacked]`:
       - `aligned` mode (default): interleaved verse-by-verse comparison grouping matching verses together across translations for side-by-side linguistic analysis.
       - `stacked` mode: renders complete consecutive passage blocks per translation.
       - Full fallback integration: missing translations fall back to `WEB` with notice and visual indicator `[WEB*]`.
  4. **Translation Catalog Inspection (`bible translations` / `bible versions`)**:
     - Added first-class subcommand to list registered translations, language codes, copyright/encryption status, and total verse counts.
- **Consequences**:
  - Scripture study across multiple translations is natively supported in the CLI with zero external dependencies.
  - Absence of optional translation packs never results in hard failure unless `--strict` / `--no-fallback` is explicitly commanded.
  - Aligned verse comparison provides an exceptional terminal reading and exegesis experience.
  - 100% compliant with ADR-003 zero-dependency architecture.

---

## ADR-019: SQLite FTS5 Full-Text Search CLI Command & Structured Presentation Engine
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: In Phase 1, an SQLite FTS5 virtual table (`verses_fts`) with automatic synchronization triggers was established in `core/db.py`. However, user-facing discovery required a robust, high-performance CLI command (`bible search` and alias `bible find`) with rich filtering (book, testament, translation fallback), exact phrase matching (`--exact`), ranking vs. canonical sorting (`--sort=relevance|canonical`), pagination, snippet highlighting, match count summaries, and scriptable JSON export.
- **Decision**:
  1. **Enhanced Full-Text Search Core (`core/db.py`)**:
     - Upgraded `search_text` to accept `testament` (`OT`/`NT`), `exact` (enforcing contiguous phrase matches), and `sort_by` (`relevance` via FTS5 BM25 `f.rank ASC` vs `canonical` via indexed `v.canonical_verse_id ASC`).
     - Added `count_search_matches(...)` executing fast index-backed `COUNT(*)` over the filtered FTS5 virtual table.
     - Added `to_dict()` on `SearchResult` for clean dictionary serialization.
     - Updated `get_book` in `core/reference.py` to accept existing `Book` instances idempotently.
  2. **Scripture Search CLI Interface (`cli/main.py`)**:
     - Added `bible search` (and alias `bible find`) taking one or more query words, quoted phrases, or Boolean expressions (`AND`, `OR`, `NOT`).
     - Filter flags: `--book` / `-b`, `--testament`, `--version` / `-t` with automatic fallback cascade to `WEB` (with stderr notification), and `--strict` enforcement.
     - Presentation options: `--exact` / `-e`, `--sort=relevance|canonical`, `--snippets` (contextual FTS5 snippets with `<b>` delimiters), `--limit` / `-n`, `--offset` for pagination.
     - UNIX pipeline & automation integration: `--count` outputs integer match count only; `--json` emits structured JSON array.
  3. **Terminal Presentation & Token Highlighting**:
     - `highlight_search_tokens`: highlights query words or exact phrases in terminal output using ANSI bold yellow codes (`\033[1;33m`), safely degrading to plain text when `color=False`, piped, or under `NO_COLOR`.
     - `format_search_snippet`: converts SQLite FTS5 `<b>` tags to ANSI yellow highlights or clean bracketed tags (`[...]`) in plain text mode.
     - Clear headers and pagination footers indicating total matches, current page range, and remaining count.
- **Consequences**:
  - Delivers fast, sovereign scripture search directly from the terminal without cloud or internet dependencies.
  - Supports both theological research (finding specific phrases across testament boundaries) and pipeline scripting (via `--count` and `--json`).
  - Hermetic tests in `tests/test_db.py` and `tests/test_cli.py` verify 100% test coverage and zero third-party dependencies (stdlib only per ADR-003).

---

## ADR-020: Terminal Scripture Typography, Layout Margins & ANSI Styling Engine
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: Reading scripture in terminal emulators requires thoughtful typography. Raw unformatted text wrapping across 160+ column terminal screens impairs eye tracking and readability. Users require clean typographic line lengths (optimal ~80–88 columns), hanging verse indentations, custom left margins, continuous paragraph flow ("reader mode"), illuminated ANSI color palettes (sacred gold, amber, cyan), decorative unicode box citation headers, and strict compliance with `NO_COLOR` standards.
- **Decision**:
  1. **Core Terminal Typography Engine (`core/terminal.py`)**:
     - Built zero-dependency terminal formatting module supporting:
       - `format_scripture_passage`: flexible verse layout supporting line-by-line verse lists with hanging indentation or continuous paragraph flow (`--flow`).
       - `format_aligned_comparison_styled`: aligned multi-translation side-by-side comparison with column margins and line wrapping.
       - `format_citation_header`: plain banner (`=== John 3:16 (WEB) ===`) or boxed header (`┌───┐ ... └───┘`).
       - `get_terminal_width`: clamps wide terminal windows to optimal reading measure (default 80–88 characters) with dynamic fallback.
       - `wrap_prefixed_text`: wraps text after fixed-width prefixes without collapsing multiple space alignment columns.
       - `strip_ansi` and `visual_len`: calculates true printed display character widths disregarding zero-width ANSI escape sequences.
       - ANSI color palette (`sacred` gold, `amber`, `cyan`, `plain`) with automatic `NO_COLOR`, `TERM=dumb`, and non-TTY suppression via `should_use_color()`.
  2. **CLI Integration (`cli/main.py`)**:
     - Upgraded `bible get` and `bible compare` with flags:
       - `--width` / `-w <N>`: target line wrap width for reading.
       - `--margin` / `-m <N>`: left margin indentation width in spaces.
       - `--flow`: renders verses continuously in a paragraph reader format instead of verse-per-line.
       - `--color` / `--no-color`: force enable or disable ANSI color styling.
       - `--theme=<sacred|amber|cyan|plain>`: selects illuminated color scheme.
       - `--box`: draws unicode double/single border around citation banners.
     - Fully backward-compatible with default pipe / plain-text scripting.
  3. **Hermetic Test Suite (`tests/test_terminal.py` and `tests/test_cli.py`)**:
     - Added 15 new hermetic tests covering visual length calculations, ANSI stripping, boxed headers, color themes, paragraph flow wrapping, margins, and CLI subcommands.
- **Consequences**:
  - Delivers a contemplative, sacred reading experience directly in the terminal with zero external dependencies.
  - Maintains strict standard library compliance (ADR-003) and 100% test coverage.
  - Automatically respects user environments (`NO_COLOR`, redirection pipes, CI logs).

---

## ADR-021: Sovereign Interactive Scripture REPL Shell, Direct Reference CLI Routing & Test Velocity Optimization
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: During the Run 020 Senior Product Manager Meta-Audit, two primary system friction points and growth opportunities were identified:
  1. *CLI Friction & Lack of Direct Citation Routing*: Users running `./bible "John 3:16"` encountered an `argparse` choice error because citations required the explicit `get` subcommand. Scripture lookup is the primary human interaction; canonical citations should resolve directly and transparently.
  2. *Lack of an Interactive Study Environment*: Every query required re-invoking the process from bash. A sovereign, persistent interactive REPL shell (`bible shell`) enables fluid, continuous Scripture exploration, search, and translation comparison without process startup overhead.
  3. *Test Suite Velocity & Diagnostic Drift*: The test suite was approaching 5.0 seconds due to redundant disk database creation across 33 CLI tests and recursive test discovery in `test_doctor.py`. Additionally, `tools/doctor.py` had a hardcoded test list that missed several newly created test suites.
- **Decision**:
  1. **Direct Scripture Reference Routing (`cli/main.py`)**:
     - Implemented `preprocess_cli_argv(argv)`: automatically inspects positional arguments prior to `argparse` parsing. If the first positional argument is not a registered subcommand or option flag, and safely parses as a valid canonical scripture citation (`parse_reference`), the CLI transparently prepends `get`.
     - Flags such as `--flow`, `--margin`, `--box`, `--theme`, and `--version` are seamlessly forwarded to the passage renderer.
  2. **Interactive Scripture Study REPL Shell (`cli/shell.py`)**:
     - Built `BibleShell` subclassing Python standard library `cmd.Cmd` with `readline` support (history navigation and tab completion).
     - Provides instant direct citation evaluation (e.g. typing `John 3:16` or `Romans 8:28-30` immediately displays formatted scripture).
     - Provides slash and subcommand helpers: `/search <query>`, `/compare <ref> [versions]`, `/version <id>`, `/versions`, `/theme <name>`, `/margin <n>`, `/flow [on|off]`, `/box [on|off]`, `/doctor`, `/summary`, `/clear`, `/help`, and `exit`.
     - Supported via `./bible shell` (aliases: `interactive`, `repl`, `console`) and top-level `-i` / `--interactive` flag.
  3. **Test Velocity & Doctor Comprehensive Coverage Optimization**:
     - Optimized `tests/test_cli.py`: converted per-test disk database creation in `setUp` to a shared class-level fixture (`setUpClass`), slashing CLI test execution time from 1.92s to 0.15s (>12x speedup).
     - Hermetically isolated `tests/test_doctor.py` using sample temp directories and mocked checks, eliminating recursive multi-run test overhead and reducing execution from 2.09s to 0.05s.
     - Upgraded `tools/doctor.py` `check_unit_tests` to dynamically discover all `test_*.py` files in `tests/` (excluding only `test_doctor.py` to prevent self-recursion), expanding live doctor coverage from 133 to 212 tests.
     - Overall repository test suite runtime dropped from 4.95s to 2.44s across 220 hermetic tests (a >50% acceleration).
  4. **Autonomous Harness Cadence Fix (`ralph.sh`)**:
     - Fixed `is_summary_run` variable expansion and integrated double-milestone prompt dispatch into continuous `--loop` mode.
- **Consequences**:
  - Delivers an intuitive, sovereign interactive Scripture study environment with zero external dependencies.
  - Slashes test latency in half while expanding automated health check coverage to 100% of test suites.
  - Guarantees seamless CLI ergonomics for direct citation queries.

---

## ADR-022: Multi-Tiered Automated Git Hook Safeguards, Fast Pre-Commit Linting & Machine-Enforced Invariant Architecture
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: The Bible Engine project enforces strict architectural invariants: 100% Zero External Dependencies (ADR-003), immediate remote pushes (ADR-004), documentation state machine synchronization (ADR-016), shell script integrity, and 100% passing hermetic tests. However, these invariants previously relied on manual developer vigilance or post-hoc validation by `ralph.sh` and `./bible doctor`. There was no mechanical, machine-level prevention at the git level: a developer or agent could commit an unapproved pip package (`import requests`), introduce a doc-sync gap in `AGENT_LOG.md`, or break a test, and `git push origin main` would proceed unchecked. Furthermore, running full doctor diagnostics on every commit (~2.0s) would add unwanted latency to atomic commit velocity.
- **Decision**:
  1. **Multi-Tiered Git Hook Defense Architecture**:
     - **Pre-Commit Hook (`.git/hooks/pre-commit`)**: Executes `python3 tools/doctor.py --fast`. Completes in <0.15 seconds (~0.11s). Validates:
       1. Zero External Dependencies AST audit across all Python files.
       2. Documentation state machine synchronization (ADRs, sequential runs, Rank A+ ideas).
       3. Shell script integrity (`ralph.sh`, `tools/install_hooks.sh`).
       4. Git hook safeguards status.
       If any violation occurs, the commit is instantly aborted with colored diagnostics, preventing invalid code from ever entering git history without delaying developers.
     - **Pre-Push Hook (`.git/hooks/pre-push`)**: Executes `python3 tools/doctor.py` (full mode). Completes in ~2.0 seconds. Validates:
       1. All four fast pre-commit checks.
       2. SQLite scripture database integrity (`PRAGMA quick_check`, 31,103+ verses, FTS5 index operational).
       3. Full hermetic unit test suite (100% pass across all test suites).
       Guarantees that broken code, failing tests, or corrupt databases can never be pushed to `origin/main`.
  2. **Automated Hook Lifecycle Management**:
     - Added `--install-hooks` / `--install-hook` and `--uninstall-hooks` to `tools/doctor.py` and CLI `./bible doctor`.
     - Added standalone executable shell script `tools/install_hooks.sh` for standard Unix developer onboarding.
     - Added `check_git_hooks` in `tools/doctor.py` as a 6th core diagnostic check, continuously verifying that git hook safeguards are active and executable.
  3. **Doctor Quiet Execution & Custom Stream Redirection**:
     - Enhanced `run_all_checks` in `tools/doctor.py` with `fast: bool = False`, `quiet: bool = False`, and `stream: Optional[TextIO] = None`.
     - Suppresses verbose ASCII banner output during hermetic test discovery runs (`python3 -m unittest discover tests`), maintaining clean, silent test feedback.
  4. **Interactive REPL Shell Integration (`cli/shell.py`)**:
     - Upgraded `/doctor` slash command in `BibleShell` to support `/doctor fast`, `/doctor hooks`, `/doctor install-hooks`, and `/doctor uninstall-hooks` with tab autocompletion.
- **Consequences**:
  - Invariants for zero dependencies, documentation synchronization, and test pass rates are physically enforced by git at the machine level before commits and pushes can occur.
  - Pre-commit latency remains under 0.15s, ensuring atomic commit workflows (ADR-004) are never bottlenecked.
  - Phase 0 Task 0.7 is fully satisfied and verified.
  - 100% zero external dependencies (Python 3 stdlib and POSIX bash only).

---

## ADR-023: Multi-Resolution Semantic Tagging Engine, Canonical Taxonomies & Hydrated Passage API
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: In Phase 3 (Task 3.1), the Bible Engine requires a first-class Semantic Tagging API allowing users and automated agents to annotate individual verses (e.g. `John 3:16`), arbitrary multi-verse passage spans (e.g. `Romans 8:1-11`), whole chapters (e.g. `Psalm 23`), or cross-chapter pericopes (e.g. `Genesis 1:1 - 2:3`). Relational systems frequently struggle with scripture range queries and tag resolution across hierarchical boundaries (e.g., whether a tag placed on Romans 8:1-11 applies when a user queries Romans 8:1 or Romans 8:5). Furthermore, users need to query passages associated with a topic and immediately read the hydrated scripture text, inspect tag metrics, remove or update tags idempotently, and interact via CLI commands (`./bible tag`) and the interactive REPL (`/tag`).
- **Decision**:
  1. **Multi-Resolution Tagging Engine & Domain Service (`core/tags.py`)**:
     - Implemented `TaggingService` encapsulating tag definition, passage annotation, taxonomy management, and querying.
     - Standardized canonical tag categories (`TagCategory`): `thematic`, `theological`, `historical`, `liturgical`, `curation`, `prophecy`, `typology`.
     - Codified canonical TGC-aligned taxonomy presets (`CANONICAL_TAXONOMY`): 25 pre-defined theological and redemptive-historical motifs (Creation, Fall, Covenant, Temple, Kingship, Exile, Restoration, Justification, Sanctification, Sovereign Grace, etc.).
     - Introduced `TagSummary` DTO for aggregated metrics (passage counts, starred counts, distinct books covered) and `TaggedPassage` DTO with hydrated `VerseRecord` sequences, joined passage text, and structured serialization (`to_dict()`).
  2. **Database Layer Enhancements (`core/db.py`)**:
     - **Span Auto-Registration & Linking**: When tagging multi-verse passages, `Database.tag_reference` automatically resolves or inserts the passage into the `spans` table, recording `span_id` in `verse_tags`.
     - **Idempotency**: Re-tagging an existing passage/tag combination updates metadata (`confidence`, `source`, `starred`, `notes`, `span_id`) rather than creating redundant association rows.
     - **Hierarchical Range Resolution**: `get_tags_for_reference` evaluates canonical ID ranges (`start_canonical_id <= query_end AND end_canonical_id >= query_start`), enabling queries on single verses (e.g. Rom 8:1) to seamlessly discover tags placed on parent spans (Rom 8:1-11) or whole chapters (Rom 8). Added `exact_only` parameter to restrict queries strictly to identical citation boundaries.
     - **Lifecycle Management**: Added `untag_reference` (scoped deletion of a specific tag association from a reference), `delete_tag` (cascading deletion of a tag and all its associations), and `get_tag_stats` (aggregated statistics across tags).
  3. **Terminal Typography & Badge Formatting (`core/terminal.py`)**:
     - Added `format_tags_badge`: renders subtle inline tag badges (e.g. `🏷  [Holy Spirit] [Sanctification]`) with ANSI styling or plain text fallback.
     - Added `format_tag_table`: renders aligned, terminal-width-aware tables for tag listings.
     - Added `format_tagged_passages`: renders scripture passages associated with a tag with formatted headers, reader paragraph flow, verse numbers, and notes.
  4. **CLI & Interactive REPL Integration (`cli/main.py` & `cli/shell.py`)**:
     - Added `./bible tag` (aliases: `./bible tags`) with 8 subcommands:
       - `add <ref> <tags...>`: attach tags with optional `--category`, `--notes`, `--starred`, `--confidence`.
       - `list`: list tags with optional `--category`, `--sort`, and `--json`.
       - `show <tag>`: display passages associated with a tag with hydrated scripture text, `--version`, `--starred-only`, `--limit`, and `--json`.
       - `for <ref>`: display tags applying to a verse or span with optional `--exact` and `--json`.
       - `remove <ref> <tag>`: remove tag association from a specific passage.
       - `delete <tag>`: delete tag definition entirely.
       - `stats [tag]`: show aggregated usage metrics.
       - `seed`: seed canonical TGC theological and redemptive taxonomies.
     - Enhanced `./bible get`: added `--tags` flag to display active tags beneath passage lookups.
     - Enhanced `BibleShell`: added `/tag` (and `/tags`) slash command supporting all tag operations, plus rich tab auto-completion (`complete_tag`) for subcommands and existing tag names.
  5. **Hermetic Test Suite (`tests/test_tags.py`)**:
     - Built 26 hermetic tests covering definition lifecycle, validation, multi-resolution span linking, idempotency, untagging, overlapping vs exact queries, hydrated verse rendering, terminal styling, CLI subcommands, and REPL interactions.
- **Consequences**:
  - Delivers a comprehensive, sovereign semantic tagging system with zero external dependencies (Python 3 stdlib only per ADR-003).
  - Satisfies all requirements for Phase 3 Task 3.1.
  - Multi-resolution hierarchical querying bridges individual verses to broader redemptive-historical and systematic themes.
  - 100% test coverage and full integration across CLI and interactive REPL.

---

## ADR-024: Scripture Cross-Referencing, Typological Arc Graph & Canonical Relationship Engine
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: In Phase 3 (Task 3.2), the Bible Engine requires a relational scripture knowledge graph connecting passages across the biblical canon. Scripture is not merely an isolated set of verses; it is an organic, intertextual web of direct citations, Messianic prophecies and fulfillments, typological shadows and realities, literary allusions, and parallel historical accounts. Users and downstream tools (such as Phase 4 visual SVG typological arcs and Phase 8 Gemini RAG retrieval) need to query passage connections, navigate multi-hop thematic paths across testaments, inspect hydrated scripture texts on both ends of an edge, filter by relationship types, and manage connections via the CLI (`./bible crossref` / `./bible get --refs`) and interactive REPL (`/crossref`).
- **Decision**:
  1. **Canonical Relationship Taxonomy (`core/crossref.py`)**:
     - Codified standardized relationship edge types in `RelationshipType`:
       - `quotation`: Direct canonical quotation (e.g., NT citing OT).
       - `prophecy_fulfillment`: Messianic/eschatological prediction and historical fulfillment in Christ.
       - `typology`: Old Testament shadow/pattern realized in New Testament substance.
       - `thematic`: Shared theological or redemptive-historical motif.
       - `allusion`: Verbal, structural, or conceptual literary echo.
       - `parallel`: Synoptic Gospel parallel or historical cross-account.
     - Provided human-readable labels and decorative icons (📜, ⚡, 🏛, 🔗, ✨, ⚖) for terminal and UI presentation.
  2. **Domain Service & Graph Operations (`CrossReferenceService`)**:
     - `link_passages`: Link two scripture references with relationship type, confidence weight (0.0 to 1.0), and theological notes.
     - `link_passages_batch`: Atomic batch insertion of relational edges inside a transaction.
     - `unlink_passages` & `delete_edge_by_id`: Scoped removal of relationship edges.
     - `get_cross_references`: Fetch raw relational records with directional or bidirectional filtering and minimum weight thresholds.
     - `get_hydrated_cross_references`: Hydrate cross-reference records with full verse texts from any installed translation, computing contextual direction (`outgoing`, `incoming`, `loop`) relative to the queried citation.
     - `find_path`: Breadth-first search (BFS) traversing the relational graph to discover multi-hop paths connecting distant passages up to a specified maximum depth.
     - `get_summary_statistics`: Aggregates graph metrics, distribution by relationship type, distinct passages, and cross-testament trajectories (e.g. `OT->NT`).
  3. **Curated Canonical Seed Dataset (`CANONICAL_CROSS_REFERENCES`)**:
     - Hand-curated 43 foundational canonical edges grounded in The Gospel Coalition (TGC) foundation documents:
       - Protoevangelium (Genesis 3:15 -> Galatians 4:4-5, Romans 16:20, Revelation 12).
       - Abrahamic Covenant & Faith (Genesis 12:1-3, 15:6 -> Galatians 3, Romans 4).
       - The Akedah & Isaac (Genesis 22 -> John 3:16, John 1:29, Hebrews 11).
       - Melchizedek (Genesis 14, Psalm 110:4 -> Hebrews 7).
       - Passover & Bronze Serpent (Exodus 12 -> 1 Cor 5:7, John 19:36; Numbers 21 -> John 3:14-15).
       - Prophet like Moses (Deuteronomy 18 -> Acts 3:22, John 1:45).
       - Davidic Covenant (2 Samuel 7 -> Luke 1:32, Hebrews 1:5).
       - Royal & Suffering Psalms (Psalms 2, 16, 22, 110, 118 -> Gospels & Acts).
       - The Suffering Servant (Isaiah 53 -> 1 Peter 2, Matthew 8, Acts 8, Romans 4, Luke 22).
       - Virgin Birth, New Covenant, Spirit Outpouring, and Pierced Messiah (Isaiah 7:14, Micah 5:2, Jeremiah 31:31-34, Joel 2:28-32, Zechariah 12:10).
     - Built idempotent seeding method (`seed_canonical_cross_references`) ensuring zero duplicate rows upon repeated executions.
  4. **Terminal Formatting & Typography (`core/terminal.py`)**:
     - Implemented `format_cross_references`: Renders rich hydrated cards with icons, directional arrows, relationship labels, weights, flowing verse prose, and theological notes.
     - Implemented `format_cross_reference_table`: Displays responsive tabular edge lists.
  5. **CLI & Interactive REPL Integration (`cli/main.py` & `cli/shell.py`)**:
     - Created `./bible crossref` (aliases: `xref`, `refs`) with 7 subcommands:
       - `for <ref>`: Query cross-references connected to a passage, supporting `--type`, `--version`, `--min-weight`, and `--json`.
       - `link <source> <target>`: Create edge with `--type`, `--weight`, `--notes`.
       - `unlink <source> <target>`: Delete edge(s) with optional `--type`.
       - `list`: Tabular list of stored edges with `--type`, `--limit`, `--json`.
       - `path <source> <target>`: Multi-hop graph pathfinding with `--max-depth` and `--json`.
       - `stats`: Output knowledge graph statistics and testament trajectory counts.
       - `seed`: Populate canonical seed dataset.
     - Upgraded `./bible get`: added `--refs` / `--cross-refs` flag to render connected cross-references directly beneath passage lookups.
     - Added `/crossref` (and `/xref`, `/refs`) to `BibleShell` with full argument parsing and tab auto-completion (`complete_crossref`).
  6. **Hermetic Test Suite (`tests/test_crossref.py`)**:
     - 20 unit and integration tests covering RelationshipType validation, linking/unlinking, hydration, seed dataset idempotency, BFS pathfinding, summary statistics, terminal formatting, CLI subcommands, and REPL interactions.
- **Consequences**:
  - Completes Phase 3 Task 3.2 cleanly with 100% test pass rate and Zero External Dependencies (ADR-003).
  - Establishes the foundational graph engine required for Phase 4 typological visual SVG arcs and Phase 8 RAG context generation.

---

## ADR-025: Batch LLM Semantic Tagging Pipeline, TGC Hermeneutical Prompt Engine & Offline Ingestion Tooling
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: In Phase 3 (Task 3.3), the Bible Engine requires a scalable, rigorous tooling pipeline to classify and tag biblical passages (verses, spans, chapters, pericopes) into predefined canonical and dynamic semantic taxonomies using Large Language Models (LLMs). Manual annotation across 31,103 verses is slow, while unconstrained LLM prompting risks inconsistent taxonomies, moralistic reductionism, and hallucinated schema structures. Furthermore, per Manifesto Pillars I & II, the system must remain offline-first, sovereign, and strictly zero-dependency (ADR-003: no pip or npm packages), supporting offline prompt generation and response ingestion without requiring active API keys, while providing direct online execution via Google Gemini when credentials are provided.
- **Decision**:
  1. **TGC-Aligned Hermeneutical Prompt Engine (`core/tag_prompts.py`)**:
     - System prompts codified directly from The Gospel Coalition (TGC) Foundation Documents (Confessional Statement and Theological Vision for Ministry):
       - **Dual-Horizon Hermeneutics**: Reading "along" the redemptive-historical narrative (Eden to New Jerusalem climaxing in Christ) and "across" systematic doctrine (Trinity, Justification, Sovereign Grace, Atonement).
       - **Christ-Centered Teleology**: Every text foreshadows, reveals, or applies the gospel of Jesus Christ.
       - **Anti-Moralistic Interpretation**: Reject legalistic/moralistic reductionism; ground all narrative interpretation in sovereign covenant mercy.
     - Formats available taxonomies dynamically (`format_taxonomy_for_prompt`) from `CANONICAL_TAXONOMY` and custom candidate tags.
     - Strict JSON output contract requiring: `name`, `category` (from canonical set), `confidence` (0.0 to 1.0), `starred` (identifying the central motif), concise `notes` (theological rationale), and optional `sub_span`.
  2. **Resilient JSON Payload Extraction & Validation (`core/tag_prompts.py`)**:
     - `extract_json_payload`: Tolerates markdown code blocks (```json ... ```), raw JSON strings, and trailing text deltas.
     - Normalizes tag names to canonical case or title case; maps common category variants (e.g. "doctrinal", "eschatological") to `TagCategory.ALL`.
     - Clamps confidence scores to `[0.0, 1.0]` and enforces that at least one tag is starred.
     - Robust error handling: returns structured `TaggingResult` with diagnostics rather than throwing uncaught exceptions.
  3. **Batch Generator & Pure Stdlib Gemini REST Client (`tools/tag_generator.py`)**:
     - Standalone executable CLI utility supporting four core modes:
       - `prompt`: Inspect or export the prompt for any passage with category and custom tag filters.
       - `batch`: Bulk prompt generator producing JSONL or JSON batch requests from `--refs`, `--favorites` (`favorite_bible_verses.csv`), `--book`, or `--input-file`.
       - `apply`: Offline ingestion pipeline that reads LLM response files (JSON or JSONL) or stdin (`-`), validates tags, and writes them into SQLite via `TaggingService` with `--dry-run` preview and `--min-confidence` filtering.
       - `generate`: Online direct tagging leveraging Google Gemini API (`gemini-2.5-pro` with `gemini-2.0-flash` fallback) using standard library `urllib.request` (zero pip packages).
  4. **CLI & Interactive REPL Integration (`cli/main.py` & `cli/shell.py`)**:
     - Integrated subcommands into `./bible tag`: `prompt`, `generate`, `apply-llm` (alias `apply`), and `batch`.
     - Added `/tag prompt <ref>` to `BibleShell` REPL with tab auto-completion in `complete_tag`.
  5. **Hermetic Test Suite (`tests/test_tag_prompts.py`)**:
     - Authored 24 unit and integration tests covering prompt generation, taxonomy filtering, response extraction, confidence clamping, error recovery, CLI argument dispatching, mock Gemini API requests, and REPL slash commands.
- **Consequences**:
  - Completes Phase 3 Task 3.3.
  - Provides a complete, sovereign pipeline for offline prompt generation and response ingestion, as well as optional real-time Gemini LLM tagging.
  - Strictly preserves Zero External Dependencies (ADR-003, ADR-006).
  - Test suite expanded to 300 tests passing 100% in under 3.8s.

---

## ADR-026: Resource Lifecycle Integrity, Shell Context Management, and Autonomous Runner Self-Documentation
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: During the Run 025 Senior Product Manager Meta-Improvement & System Health Sprint, a comprehensive audit across runtime execution, testing infrastructure, and developer ergonomics revealed three key friction points in how the project accomplishes itself:
  1. **SQLite Connection Resource Leakage in Tests**: When instantiating `BibleShell(db_path=...)`, an internal `Database` connection was allocated and cached on `self._db`. When unit tests instantiated `BibleShell` without an explicit teardown mechanism, Python 3.13 garbage collection emitted `ResourceWarning: unclosed database in <sqlite3.Connection object>`. Running Python with warning errors (`-W error::ResourceWarning`) halted test runs.
  2. **Test Output Noise Pollution**: In `tools/tag_generator.py`, batch generation commands (`cmd_prompt`, `cmd_batch`) printed status messages directly to `sys.stdout`. When invoked during unit tests (`tests/test_tag_prompts.py`), these diagnostic messages leaked into the test runner's standard output, violating the quiet/clean terminal mandate for hermetic tests.
  3. **Harness Self-Documentation Deficit**: The autonomous runner script `ralph.sh` supported rich operational flags (`--loop [N]`, `-p`, `--cleanup`, `--summary`, `-c`, `-s`), but lacked standard CLI help flags (`--help`, `-h`). Developers or operators querying `./ralph.sh --help` were greeted by immediate autonomous loop execution rather than formatted documentation explaining modes and cadence rules.
  4. **Core Public Symbols Divergence in Export Tests**: In `tests/test_core.py`, `TestCoreExports` tested Phase 1 exports but had not been kept in parity with subsequent Phase 2 and Phase 3 capabilities (semantic tagging, cross-references, hermeneutical prompt engineering, and typography).
- **Decision**:
  1. **Interactive Shell Context Management & Dependency Injection (`cli/shell.py`)**:
     - Upgraded `BibleShell` to implement explicit resource teardown via `close()`, ensuring any internally allocated `Database` connection is safely closed.
     - Implemented Python context management protocol (`__enter__` returning `self`, `__exit__` invoking `self.close()`).
     - Added optional `database: Optional[Database] = None` dependency injection parameter to `BibleShell.__init__`. When tests or callers supply an existing `Database` instance, `BibleShell` reuses it rather than opening duplicate file handles, and preserves ownership semantics.
     - Wrapped `launch_shell()` in a `try...finally: shell.close()` construct.
  2. **Zero Warning & Clean Output Test Hygiene (`tests/`)**:
     - Updated `tests/test_tags.py`, `tests/test_crossref.py`, and `tests/test_tag_prompts.py` to instantiate `BibleShell` within context managers or inject existing fixture databases, guaranteeing 100% cleanup without unclosed resource warnings.
     - Silenced batch prompt generation test stdout in `tests/test_tag_prompts.py` using `unittest.mock.patch("sys.stdout", io.StringIO())`.
     - Updated `tests/test_core.py` to assert comprehensive public exports across Phase 1, Phase 2, and Phase 3.
  3. **Autonomous Runner Self-Documentation (`ralph.sh`)**:
     - Implemented `show_help()` in `ralph.sh` rendering formatted ANSI usage, mode options, and cadence protocol explanations.
     - Added robust `--help` / `-h` flag interception before command dispatch.
     - Added hermetic CLI test `test_ralph_help_flags` in `tests/test_harness.py` asserting exit code 0 and usage rendering.
- **Consequences**:
  - `python3 -W error::ResourceWarning -m unittest discover tests` runs 100% clean across all 301 tests in 3.67s with zero warnings and zero terminal clutter.
  - `BibleShell` lifecycle is deterministic and safely reusable in headless scripts, REPL sessions, and test fixtures.
  - `./ralph.sh --help` and `-h` provide clear, self-documenting guidance for human and agent operators.
  - Zero external dependencies preserved (ADR-003).

---

## ADR-027: Semantic Tag Aggregation Queries, Co-Occurrence Matrix, and Verse Relevance Scoring Engine
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: Phase 3 establishes semantic tagging, knowledge graph relationships, and hermeneutical tagging pipelines. To support Phase 4 visualizations (the Canonical Redemptive Ribbon heatmap and typological exploration) and Phase 8 RAG retrieval, the platform requires statistical aggregation queries over the semantic tag corpus:
  1. **Topic Density Distribution**: Visualizing how themes and theological concepts are distributed across the 66 canonical books (OT vs. NT, passage frequency, starred proportions, top tags).
  2. **Tag Co-Occurrence Analysis**: Quantifying semantic proximity and pairing patterns between tags (e.g. how often `Sanctification` and `Grace` co-occur on the same or overlapping scripture spans), complete with mathematical association indices (Jaccard similarity and Sørensen–Dice coefficient).
  3. **Verse Relevance Scoring & Multi-Tag Ranking**: A principled ranking algorithm to score scripture passages against arbitrary sets of query tags, balancing tag coverage ratio, association confidence, user curation priority (starred boost), and passage specificity.
- **Decision**:
  1. **Data Models & Analytical Records (`core/tags.py`)**:
     - Defined `BookTopicDensity`: Captures canonical book order, total chapters, distinct passages, starred passages, distinct tags, and tag frequency breakdown.
     - Defined `TagCoOccurrence`: Captures tag pairs, shared passage counts, Jaccard similarity index, Dice coefficient, and category metadata.
     - Defined `TagCoOccurrenceMatrix`: Grid matrix and ranked pairwise metrics.
     - Defined `VerseRelevance`: Scored passage ranking with match ratio, average confidence, starred boost, specificity bonus, and hydrated verse texts.
  2. **Domain Service Aggregation Methods (`TaggingService`)**:
     - `get_topic_density_per_book(tag_name, category, testament, min_passages)`: Computes distribution across the 66 canonical books using canonical ID arithmetic (`start_canonical_id / 1000000 = book_id`), deduplicating passages by span key `(start_canonical_id, end_canonical_id)`.
     - `get_tag_co_occurrences(tags, category, min_co_occurrences)`: Evaluates overlapping passage boundaries in `verse_tags` (`vt1.start <= vt2.end AND vt1.end >= vt2.start`), computing Jaccard index `|A ∩ B| / |A ∪ B|` and Dice coefficient `2|A ∩ B| / (|A| + |B|)`.
     - `score_verse_relevance(tags, translation_id, starred_only, min_score, limit, hydrate_verses)`: Composite scoring function weighting match ratio (0.60), full match bonus (0.20), starred boost (0.10), and span specificity (0.10).
  3. **Terminal Presentation & Table Formatters (`core/terminal.py`)**:
     - `format_topic_density_table`: Aligned tabular presentation showing book name, testament, chapters, passage counts, starred counts, distinct tags, and top tag breakdowns.
     - `format_tag_co_occurrence_table`: Aligned pairwise co-occurrence table with shared counts, Jaccard, and Dice metrics.
     - `format_verse_relevance_table`: Ranked score listing with percentage match, active tag badges, and flowing verse text.
  4. **CLI & Interactive REPL Integration (`cli/main.py` & `cli/shell.py`)**:
     - Added `./bible tag density [--category] [--testament] [--min-passages] [--json]`.
     - Added `./bible tag co-occurrence [tags...] [--category] [--min-shared] [--json]` (aliases `co-occur`, `matrix`).
     - Added `./bible tag relevance <tags...> [--starred-only] [--min-score] [--limit] [--json]` (alias `rank`).
     - Added `/tag density`, `/tag co-occurrence`, and `/tag relevance` to `BibleShell` REPL with subcommands and tag name auto-completion.
  5. **Core Exports & Hermetic Unit Tests**:
     - Exported all new data models and formatters in `core/__init__.py`.
     - Authored comprehensive unit and integration tests in `tests/test_tags.py` (`TestTagAggregationAnalytics`), bringing total suite to 307 passing tests in ~4.0s with zero warnings (`-W error::ResourceWarning`).
- **Consequences**:
  - Completes Task 3.4 and completes Phase 3 (Semantic Tagging & Knowledge Database Engine) at 100% (4/4 tasks done).
  - Unblocks Phase 4: provides the exact backend aggregation data feeds required for the Canonical Redemptive Ribbon SVG heatmap (Task 4.3).
  - 100% Zero External Dependencies maintained (Python standard library only per ADR-003).

---

## ADR-028: Built-in Zero-Dependency HTTP Web Server, Multi-Threaded Request Router, and REST API Architecture
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: Phase 4 begins the visual exploration and interactive Web UI era of the Bible Engine. Per Manifesto Pillars I (Offline-First & Sovereign Data) and III/IV (Multi-Resolution Knowledge Graph & Visual Comprehension), and ADR-003 (Zero External Dependencies, stdlib only), the platform requires a built-in local HTTP web server capable of:
  1. Serving static assets (HTML/CSS/JS/SVG) securely with correct MIME types and path traversal protections.
  2. Providing a full-featured REST API exposing scripture text, multi-translation fallback queries, SQLite FTS5 search, semantic tags, co-occurrence analytics, topic density distributions, and cross-reference relationship networks.
  3. Operating hermetically and concurrently with high performance without external web frameworks (no Flask, FastAPI, Django, or Starlette; zero pip dependencies).
  4. Integrating seamlessly into both the command line (`./bible serve [--port=8080] [--host=127.0.0.1] [--open]`) and interactive REPL shell (`/serve [start|stop|status]`).
- **Decision**:
  1. **Server Architecture & Lifecycle (`web/server.py` & `web/__init__.py`)**:
     - Built `BibleWebServer` wrapping Python standard library `http.server.ThreadingHTTPServer` to handle concurrent HTTP requests smoothly without thread pool starvation.
     - Implemented dynamic subclass binding (`BoundHandler`) per server instance, guaranteeing hermetic isolation between parallel instances during testing without global class variable collisions.
     - Upgraded `Database.__init__` in `core/db.py` to support `check_same_thread: bool = True` (set to `False` by the web server to permit multi-threaded analytical reads safely under SQLite WAL mode).
  2. **Comprehensive REST API Engine (`BibleRequestHandler`)**:
     - Standardized JSON responses with UTF-8 encoding, standardized error envelopes (`{"error": "...", "status": 400|404|500}`), and CORS headers (`Access-Control-Allow-Origin: *`, `OPTIONS` preflight handling).
     - Implemented complete endpoint suite:
       - `GET /api/health`: System health, version, database path, verse count, and available translations.
       - `GET /api/books`: Canonical 66-book catalog with optional testament filtering (`testament=OT|NT`).
       - `GET /api/passage`: Multi-verse range lookup with translation fallback, active semantic tags, and cross-references.
       - `GET /api/verses`: Direct chapter navigation by book name/OSIS and chapter number.
       - `GET /api/search`: High-performance FTS5 full-text search with query highlighting snippets, testament filtering, and match ranking.
       - `GET /api/translations`: Installed translation inventory, public domain status, and license notes.
       - `GET /api/tags`: Semantic tag taxonomy listing and category/query search.
       - `GET /api/tags/density`: Canonical book distribution and passage counts per topic.
       - `GET /api/tags/co-occurrence`: Co-occurrence matrix with Jaccard and Dice association metrics.
       - `GET /api/tags/relevance`: Multi-tag scored scripture passage ranking.
       - `GET /api/crossref`: Passage cross-reference relationship retrieval with hydrated target verses.
       - `GET /api/crossref/stats`: Global cross-reference relationship metrics.
       - `GET /api/stats`: Comprehensive repository and knowledge database aggregate counts.
  3. **Secure Static Asset Dispatch & Sacred-Modern Web Scaffolding (`web/static/`)**:
     - Built safe static file dispatcher verifying that resolved target paths strictly remain within the static directory (`Path.is_relative_to`), returning HTTP 403 Forbidden on directory traversal attempts and HTTP 404 on missing files.
     - Authored initial Sacred-Modern UI foundation:
       - `index.html`: Responsive split-pane layout with sidebar controls (passage, search, topic cloud, cross-references, REST API docs) and reader stage.
       - `style.css`: Pure CSS3 styling implementing Obsidian Dark Mode (`#0D0E11`), illuminated gold accents (`#D4AF37`), and editorial serif typography.
       - `app.js`: Vanilla ES6+ client logic handling health polling, book/chapter selection, instant passage lookup, search queries, and tag navigation.
  4. **CLI & REPL Integration (`cli/main.py` & `cli/shell.py`)**:
     - Added `./bible serve [--host] [--port] [--open] [--verbose]` command (aliases: `server`, `http`, `web`).
     - Added `/serve [start|stop|status]` command to `BibleShell` REPL running the web server on a background daemon thread for simultaneous interactive CLI study and browser exploration.
  5. **Hermetic Test Suite (`tests/test_server.py`)**:
     - Created comprehensive test suite running against ephemeral server port 0, covering all static asset routes, security protections, CORS pre-flights, REST API endpoints, validation errors, and CLI/shell lifecycle. Total test count expanded from 307 to 339 tests passing 100% in ~5.2s.
- **Consequences**:
  - Completes Task 4.1 in full.
  - Establishes the foundational server and web application architecture for Phase 4 (Web UI & Visualizations).
  - Maintains 100% Zero External Dependencies compliance (stdlib only per ADR-003).

---

## ADR-029: Sacred-Modern Design System, Multi-Theme Obsidian/Scriptorium/Monastery Palette, and Editorial Typography Reader Architecture
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: In Phase 4 (Task 4.2), the Bible Engine requires a cohesive, beautiful, and distraction-free visual design system ("Sacred-Modern") to accompany the built-in HTTP server and API. Scripture reading demands rigorous typographic care: optimal column measure (65–75 characters / ~780px), hierarchical serif typography, graceful paragraph flow, customizable scaling, and high-contrast night/day modes. Per Manifesto Pillars I (Offline-First & Sovereign Data) and Zero-Dependency ADR-003, the design system must be 100% self-contained in pure CSS3 and Vanilla ES6+ without external CDNs, npm packages, web font CDNs, or CSS frameworks.
- **Decision**:
  1. **Tri-Theme Sacred-Modern Color Palette (`web/static/style.css`)**:
     - **Obsidian Dark Mode** (`[data-theme="obsidian"]`, default): Abyssal background `#0D0E11`, elevated card surfaces `#14171F` and `#1B202B`, with radial gradient header `#181C26` to `#0D0E11`.
     - **Scriptorium Warm Charcoal** (`[data-theme="scriptorium"]`): Deep warm charcoal `#12100E` with sepia undertones `#1A1714` and muted gold accents.
     - **Monastery Light Parchment** (`[data-theme="monastery"]`): Illuminated manuscript parchment `#F7F4EB`, elevated `#EFE9DC`, warm antique ink `#211D19`, and burnished gold `#B89025`.
     - **Illuminated Gold Hierarchy**: Canonical Byzantine primary gold `#D4AF37`, luminous leaf halo `#F5E08F`, burnished gold `#997E24`, and linear gold gradients (`linear-gradient(135deg, #F5E08F 0%, #D4AF37 50%, #997E24 100%)`).
     - **Semantic Category Color System**: Distinct accent borders for semantic taxonomies (`theological` Sapphire `#4A90E2`, `thematic` Tyrian Purple `#9B51E0`, `curation` Pure Gold `#F1C40F`, `prophecy` Emerald `#2ECC71`, `typology` Amber `#F39C12`, `historical` Ochre `#E67E22`, `liturgical` Crimson `#E74C3C`).
  2. **Editorial Typography & Reader Ergonomics (`web/static/style.css` & `app.js`)**:
     - Standardized serif stack: `"Cardo", "Charter", "Georgia", "Iowan Old Style", "Palatino Linotype", "Liberation Serif", serif`.
     - Dynamic font scaling controls (`A-` / `A+`, keyboard shortcuts `-` / `+`) dynamically updating `--reader-font-size` between 15px and 30px, persisted in `localStorage`.
     - Dual presentation modes:
       - **Verse List Mode** (default): Line-by-line verses with right-aligned monospace verse numbers and hanging indents.
       - **Paragraph Flow Mode** (`.flow-mode`, keyboard shortcut `f`): Continuous editorial prose with subtle inline superscript verse numerals.
     - Verse number visibility toggle (`Numbers: On` / `Numbers: Off`).
     - One-click copy passage (`btn-copy-passage`, keyboard shortcut `c`) generating clean markdown/text citations with version attribution.
  3. **Responsive Split-Pane Layout & Visual Components (`index.html` & `app.js`)**:
     - Collapsible sidebar (`#sidebar.collapsed`, keyboard shortcut `[`) for distraction-free Zen scripture study.
     - Mobile drawer mode (`@media (max-width: 900px)`): transforms sidebar into a slide-over off-canvas drawer with darkened backdrop overlay.
     - **Canonical Ribbon Grid**: Visual interactive navigator across all 66 Protestant canonical books grouped by Old Testament (39 books) and New Testament (27 books), enabling instant chapter jumping.
     - **Canonical Chapter Navigation Bar**: Quick `< Prev Chapter` and `Next Chapter >` buttons with dynamic breadcrumbs (`Testament / Book / Chapter`) that automatically navigate across book boundaries.
     - Global search preprocessor in top header (`#header-quick-input`, shortcut `/`): automatically detects whether input is a citation or full-text search query.
     - Comprehensive keyboard shortcut navigation subsystem with accessible modal dialog (`?`).
  4. **Hermetic Test Suite (`tests/test_server.py`)**:
     - Expanded tests verifying CSS theme tokens, HTML layout containers, chapter breadcrumb elements, shortcuts modal, and client capability functions. Total test count expanded to 342 tests passing 100% in 5.39s with zero warnings.
- **Consequences**:
  - Completes Phase 4 Task 4.2 in full.
  - Elevates the Bible Engine web interface to an editorial, sacred-modern reading standard.
  - Maintains 100% Zero External Dependencies compliance (pure HTML/CSS/JS, zero npm/pip packages per ADR-003).

---

## ADR-030: Sovereign Cold-Start Bootstrapping, Unified Database Compilation & Lifecycle Engine (bible init / bible db), Self-Healing Doctor Diagnostics (--fix), and Comprehensive Repository Documentation
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: In Cadence Sprint Run 029 (Senior Product Manager Meta-Improvement & System Health Sprint), a systematic audit of the project structure and developer ergonomics confronted the two core diagnostic questions:
  1. *What is the weakest aspect of this project structure?*
     - **Fragmented Cold-Start & Incomplete Data Lifecycle**: The scripture database (`data/bible.db`) is an unversioned, ignored binary artifact. A fresh clone or reset environment contains 0 verses, 0 tags, and 0 cross-references. Prior to this sprint, compiling a complete database required tribal knowledge and manual execution of 4 separate scripts/subcommands (`tools/ingest_web.py`, `tools/ingest_favorites.py`, `./bible tag seed`, and `./bible crossref seed`). When `bible.db` was missing, CLI commands displayed outdated hints pointing only to `tools/ingest_web.py`. Furthermore, `tools/doctor.py` failed on `check_database_integrity` with zero remediation capabilities.
     - **Diagnostic Blind Spots**: `tools/doctor.py` explicitly skipped `test_doctor.py` in `check_unit_tests` due to legacy recursion fears, leaving 14 unit tests excluded from standard repo diagnostics.
     - **Documentation Deficit**: `README.md` was an empty 25-line placeholder lacking quickstarts, CLI references, REPL guides, or web server instructions.
  2. *What is preventing this from being more incredible?*
     - The lack of sovereign, automated self-healing. Any developer, CI system, or autonomous Ralph loop agent encountering a clean or corrupted workspace had to piece together data ingestion manually. With a single `./bible init` or `./bible doctor --fix` command, the entire system can compile, index, and verify itself in seconds with zero human intervention.
- **Decision**:
  1. **Unified Cold-Start Bootstrapping Engine (`core/bootstrap.py`)**:
     - Implemented `bootstrap_database()`: orchestrates schema initialization, World English Bible compilation (31,103 verses from cached raw JSON), curated favorites ingestion (829 passages, 50 starred), canonical TGC taxonomies seeding (26 tags), canonical typological cross-reference links seeding (43 edges), SQLite `PRAGMA optimize`, and git hook safeguards installation.
     - Fast idempotent verification: if database is already complete and healthy, exits in `<0.4s` without redundant disk writes.
     - Implemented `get_db_stats()`: comprehensive reporting of database size, SQLite version, pragmas, page sizes, FTS5 status, verse breakdown by translation, tags, and cross-references.
  2. **First-Class CLI Subcommands (`cli/main.py`)**:
     - Added `./bible init` (aliases: `setup`, `bootstrap`): one-step idempotent compilation with `--force`, `--quick`, and `--no-hooks`.
     - Added `./bible db` (aliases: `database`): subcommands `stats` / `status`, `init`, `optimize`, and `vacuum`.
     - Updated missing database error messages to guide users directly to `./bible init` and `doctor --fix`.
     - Added `"init"`, `"setup"`, `"bootstrap"`, `"db"`, `"database"` to `preprocess_cli_argv` registered command bypass.
  3. **Self-Healing Doctor Diagnostics (`tools/doctor.py` / `bible doctor --fix`)**:
     - Added `--fix` (`-f`) flag to `tools/doctor.py` and `./bible doctor`. When enabled, automatically installs missing/inactive git hooks and automatically compiles/bootstraps missing or corrupted scripture databases.
     - Removed arbitrary `test_doctor.py` exclusion in `check_unit_tests`: all 18 test modules (356 tests) are now discovered and validated with zero exclusions.
  4. **Interactive REPL Shell Integration (`cli/shell.py`)**:
     - Added `/db` (`stats`, `status`, `optimize`, `vacuum`, `init`) and `/init` slash commands with tab autocompletion.
     - Updated `/help` command reference.
  5. **Authoritative Engineering Guide (`README.md`)**:
     - Transformed 25-line stub into an authoritative, illuminated manual: 30-second quickstarts, CLI command table, REPL slash command guide, Sacred-Modern web reader and REST API documentation, Zero-Dependency architectural invariants, and autonomous Ralph loop operations.
  6. **Hermetic Unit Test Suite**:
     - Authored `tests/test_bootstrap.py` (7 tests) verifying format size, stats, health checks, idempotent bootstrap, quick mode, and force rebuilds.
     - Expanded `tests/test_cli.py` (58 tests), `tests/test_shell.py` (16 tests), and `tests/test_doctor.py` (14 tests).
- **Consequences**:
  - Completes Phase 0 Task 0.10 in full.
  - Eliminates cold-start friction and tribal knowledge: any machine or fresh clone reaches 100% operational readiness in `<0.5s` via `./bible init`.
  - Self-healing diagnostics (`./bible doctor --fix`) provide complete autonomous repair capabilities.
  - 100% Zero External Dependencies compliance (Python 3 stdlib only per ADR-003).

---

## ADR-031: Canonical Redemptive Ribbon Heatmap Engine, Macro-Thematic Topography & Multi-Modal Sacred Visualization
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: In Cadence Sprint Run 030 (Senior Product Manager Meta-Improvement Sprint & 10th-Iteration Executive Briefing Double Milestone), a system audit confronted the two core diagnostic inquiries:
  1. *What is the weakest aspect of this project structure?*
     - **Micro vs. Macro Granularity Disconnect**: The Bible Engine possessed rich verse-by-verse lookup, multi-translation alignment, SQLite FTS5 search, and statistical topic density algorithms, but had zero holistic macro-visualization across the 66 canonical books. Users and developers had no intuitive, birds-eye view of how theological themes (e.g. Covenant, Atonement, Justification, Resurrection) distribute across canonical divisions (Law, History, Poetry, Prophets, Gospels, Epistles, Apocalypse).
  2. *What is preventing this from being more incredible?*
     - The lack of a unified multi-modal macro-visualization across both terminal CLI and Sacred-Modern Web UI. By unifying canonical book groupings with dynamic proportional intensity heatmaps, users can immediately observe biblical-theological topography in both terminal environments and browser dashboards without any third-party graphing libraries.
- **Decision**:
  1. **Canonical Book Division Schema (`core/terminal.py`)**:
     - Defined `CANONICAL_DIVISIONS`: Law (1-5), History (6-17), Poetry & Wisdom (18-22), Major Prophets (23-27), Minor Prophets (28-39), Gospels & Acts (40-44), Pauline Epistles (45-57), General Epistles (58-65), and Apocalypse (66).
     - Created `_intensity_char(pct)`: Unicode density character mapping (`·`, `░`, `▒`, `▓`, `█`) calibrated across 5 proportional intensity tiers.
     - Implemented `format_redemptive_ribbon_ascii()`: multi-line terminal ASCII visualizer grouping books by canonical division, calculating proportional density against max passages, and rendering illuminated ANSI color highlights.
  2. **First-Class CLI & REPL Integration (`cli/main.py` & `cli/shell.py`)**:
     - Added `./bible ribbon [tag]` subcommand (aliases: `./bible tag density --ribbon`, `./bible tag density -r`).
     - Added `/ribbon [tag]` and `/tag ribbon [tag]` interactive REPL slash commands with dynamic tag autocompletion (`complete_ribbon`).
     - Added `"ribbon"` to CLI `preprocess_cli_argv` registered command list.
  3. **Sacred-Modern Web UI Heatmap Overlay (`web/static/`)**:
     - Upgraded `#panel-ribbon` with interactive topic selector (`#select-ribbon-tag`), 5-tier color legend (`#ribbon-legend-bar`), and data-heat styling (`[data-heat="0"]` through `[data-heat="4"]`) in `style.css`.
     - Implemented `loadRibbonDensity()` and `populateRibbonTagSelector()` in `app.js`, dynamically querying `/api/tags/density` and mapping proportional heat badges to each book button.
  4. **Hermetic Unit Test Suite**:
     - Authored `TestRedemptiveRibbon` in `tests/test_tags.py` (4 tests) verifying plain/styled output, CLI `./bible ribbon`, `--ribbon` flag, and shell `/ribbon` commands.
     - Expanded `tests/test_server.py` verifying HTML elements, CSS legend styles, and JS client functions. Total test count expanded to 360 tests passing 100% with zero warnings.
- **Consequences**:
  - Unlocks holistic macro-thematic visualization across all 66 books in both terminal and web reader.
  - Retains 100% Zero External Dependencies compliance (Python 3 stdlib and vanilla browser DOM/CSS only per ADR-003).

---

## ADR-032: Drill-Down Scripture Viewer, Canonical Pericope Headings & Chapter Thematic Heatmaps
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: Prior to Task 4.4, the web and CLI interfaces provided macro-thematic visualization across the 66 canonical books (ADR-031 Redemptive Ribbon) and verse-level lookup, but lacked a seamless intermediate navigation layer. Clicking a book on the macro heatmap could not drill down into individual chapter cells with active thematic intensity, and scripture text was rendered as isolated verse blocks without canonical pericope section headings, passage outlines, or inline semantic tag indicators.
- **Decision**:
  1. **Canonical Pericope Model & Knowledge Base (`core/pericopes.py`, `core/db.py`)**:
     - Added `PericopeRecord` dataclass and `pericopes` SQLite table indexed by `book_id` and canonical ID ranges (`start_canonical_id`, `end_canonical_id`).
     - Curated 144 foundational canonical pericopes (`CANONICAL_PERICOPES`) spanning both Old and New Testaments with descriptive titles and redemptive-historical summaries.
     - Implemented `PericopeService` with idempotent batch seeding (`seed_canonical_pericopes`) integrated into `core/bootstrap.py`.
  2. **Chapter-Level Thematic Density (`core/tags.py`)**:
     - Defined `ChapterTopicDensity` dataclass (`book_id`, `book_name`, `osis`, `chapter`, `passage_count`, `starred_count`).
     - Implemented `TaggingService.get_topic_density_per_chapter(book, tag_name, category)` computing chapter-by-chapter thematic concentration using canonical verse ID math in `<1ms`.
  3. **REST API Expansion (`web/server.py`)**:
     - Added `GET /api/pericopes` supporting query filtering by scripture citation, book, or chapter.
     - Added `GET /api/tags/chapters` returning chapter density arrays for drill-down heatmaps.
     - Enhanced `GET /api/passage` to return overlapping `pericopes` arrays and verse-level `tags` lists.
  4. **Interactive Drill-Down UI & Inline Pericope Viewer (`web/static/`)**:
     - Added `#chapter-drilldown-box` with `#drilldown-chapter-grid` and back-to-canon toggle button in `index.html`.
     - In `app.js`, hooked book clicks in the Canonical Ribbon to open chapter drill-down, dynamically color-coding each chapter cell according to the active topic's density (`data-heat="0".."4"`).
     - Added pericope quick chips in the reader navigation bar and rendered illuminated pericope section banners with redemptive summaries and verse tag pills in the reading flow.
  5. **CLI & REPL Integration (`cli/main.py`, `cli/shell.py`, `core/terminal.py`)**:
     - Added `./bible pericopes [query]` and `./bible chapters <book> [tag]` subcommands.
     - Added `--pericopes` (`-p`) flag to `./bible get` to print pericope banners and redemptive summaries.
     - Added `/pericopes` and `/chapters` REPL commands to `BibleShell`.
     - Implemented `format_pericope_banner`, `format_pericope_table`, and `format_chapter_density_grid` in `core/terminal.py`.
  6. **Verification & Testing**:
     - Authored `tests/test_pericopes.py` (6 tests) and expanded `tests/test_tags.py`, `tests/test_server.py`. Total test suite expanded to 369 tests passing 100% in ~7.4s with zero warnings.
- **Consequences**:
  - Completes Roadmap Task 4.4 in full.
  - Seamlessly bridges the macro (66 books), intermediate (chapters & pericopes), and micro (verses & tags) dimensions of scripture study.
  - Retains 100% Zero-Dependency architecture (pure Python 3 stdlib, vanilla HTML/CSS/JS, zero pip/npm packages).

---

## ADR-033: Pure Vector SVG Typological Arc Network, Cross-Reference Graph & Curated Christological Knowledge Engine
- **Date**: 2026-09-07
- **Status**: Accepted
- **Context**: Prior to Task 4.5, the Bible Engine provided linear scripture reading, pericope outline navigation, and book/chapter thematic heatmaps (ADR-031, ADR-032). However, scripture's deep organic unity—specifically redemptive typology connecting Old Testament shadows (sacrifices, covenants, high priesthood, the rock, manna, Joseph, Boaz, Jonah) to New Testament fulfillments in Christ—was invisible to the eye. Users could not visualize how canonical books across millennia intertwine in unified redemptive history, nor export publication-grade vector graphics or interactively trace connections in the terminal or browser.
- **Decision**:
  1. **Pure SVG Arc Network Layout Engine (`core/arcs.py`)**:
     - Engineered a mathematical layout mapping the 66 canonical books onto an SVG horizontal axis with sub-chapter and verse precise positioning (`get_reference_x()`).
     - Added an intertestamental visual pause between Malachi (OT book 39) and Matthew (NT book 40).
     - Generated smooth cubic Bézier curves (`M sx,y_base C sx,y_ctrl tx,y_ctrl tx,y_base`) where arc peak height scales proportionally with canonical distance between endpoints.
     - Built Sacred-Modern color themes (`obsidian`, `scriptorium`, `monastery`, `transparent`) and categorized relationship styling: `typology` (amber `#F39C12`), `prophecy_fulfillment` (emerald `#2ECC71`), `quotation` (sapphire `#4A90E2`), `thematic` (purple `#9B51E0`), `allusion` (rose `#E056FD`), and `parallel` (slate `#747D8C`).
     - Implemented both standalone vector SVG generation (`render_svg()`) and terminal visualizer (`render_terminal_summary()`).
  2. **Canonical Typological Knowledge Base Expansion (`core/crossref.py`)**:
     - Expanded `CANONICAL_CROSS_REFERENCES` with 24 foundational Christological typologies (Adam/Christ, Noah's Ark, Abraham & Isaac, Melchizedek, Jacob's Ladder, Joseph's Betrayal & Deliverance, Burning Bush, Passover Lamb, Manna from Heaven, Water from the Rock, Bronze Serpent, Tabernacle, High Priest Aaron, Day of Atonement, Cities of Refuge, Boaz Kinsman-Redeemer, Davidic King, Jonah 3 Days/Nights, etc.).
     - Expanded total cross-reference edges from 43 to 67 edges (with 66 Old-to-New Testament fulfillment trajectories).
  3. **REST API & Standalone SVG Endpoints (`web/server.py`)**:
     - Added `send_svg()` HTTP response handler with `image/svg+xml` content type and caching headers.
     - Added `GET /api/crossref/arcs` and `GET /api/arcs` returning JSON graph data (nodes, book marks, Bézier paths).
     - Added `GET /api/crossref/arcs.svg` and `GET /api/arcs.svg` dynamically serving standalone vector SVG graphics supporting query filters (`?theme=obsidian&type=typology&book=Genesis`).
  4. **Interactive Sacred-Modern Visualizer UI (`web/static/`)**:
     - Added `Arcs` navigation tab, `#panel-arcs` sidebar with interactive relationship filters, canonical book dropdown, scope filters, and connection list.
     - Created `#arc-visualizer-stage` panoramic view with responsive SVG viewport `#arc-svg-viewport` and active connection detail inspector `#arc-active-detail-card`.
     - Added click and hover event listeners in `app.js` with instant glowing highlight effects and direct navigation to open connected scripture passages in the reader.
     - Integrated single-click standalone SVG export download (`btnStageDownloadSvg`).
  5. **CLI & REPL Shell Integration (`cli/main.py`, `cli/shell.py`)**:
     - Added `./bible arcs` subcommand (with aliases `arc`, `typology`, `typologies`) supporting `--type`, `--book`, `--testament`, `--svg <path>`, `--theme`, `--width`, `--height`, and `--json`.
     - Added `/arcs` interactive REPL command in `BibleShell` with command autocompletion and dynamic parameter parsing.
  6. **Hermetic Test Suite (`tests/test_arcs.py`)**:
     - Authored 21 dedicated unit tests validating mathematical geometry, Bézier control points, filter semantics, SVG XML validity, JSON serialization, CLI execution, REPL commands, and HTTP/SVG endpoints.
     - All 390 repository tests pass 100% in 8.3s with zero warnings.
- **Consequences**:
  - Completes Roadmap Phase 4 (Task 4.5) and concludes the Web UI & Visualizations phase.
  - Bridges redemptive-historical biblical theology with pure vector graphic rendering.
  - Retains 100% Zero-Dependency compliance per ADR-003 (Python 3 stdlib, vanilla SVG/ES6+/CSS3, zero npm/pip dependencies).
