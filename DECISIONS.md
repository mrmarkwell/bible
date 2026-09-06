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
