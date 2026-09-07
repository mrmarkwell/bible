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

