# Project Roadmap & Backlog

This document is the single source of truth for current project status, active tasks, and future backlog. Autonomous agents must consult this document during boot and update it upon completing work.

---

## Current Status Overview
- **Active Phase**: Phase 0 — Repository Architecture & Autonomous Harness
- **Overall Progress**: Architectural foundation complete, ready for Phase 1
- **Architecture Mandate**: **Zero External Dependencies** (Python standard library only + Vanilla HTML/CSS/JS). No npm, no pip dependencies, zero Dependabot alerts.

---

## Phase Breakdown

### Phase 0: Repository Architecture & Autonomous Harness
- [x] **Task 0.1**: Draft `MANIFESTO.md`, `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and `AGENT_LOG.md`.
- [x] **Task 0.2**: Restructure repository layout (establish `cli/`, `core/`, `web/`, `data/`, `legacy/`).
- [x] **Task 0.3**: Establish Zero-Dependency Architecture (ADR-003) for zero maintenance and Dependabot immunity.

### Phase 1: Core Data Models & Offline Scripture Storage (Zero Dependencies)
- [ ] **Task 1.1**: Define standard canonical scripture reference model (`Book` [1-66], `Chapter`, `Verse`, `Span/Range`, OSIS identifiers) in `core/reference.py`.
- [ ] **Task 1.2**: Implement SQLite database schema & connection manager in `core/db.py` (`verses`, `translations`, `books`, `spans`, `tags`, `verse_tags`, `cross_references`, and FTS5 search).
- [ ] **Task 1.3**: Ingest full Public Domain Bible translation (World English Bible - WEB) into bundled SQLite database for offline access.
- [ ] **Task 1.4**: Implement zero-dependency keystream encryption/obfuscation module in `core/crypto.py` for copyrighted translations.
- [ ] **Task 1.5**: Hermetic unit tests using `unittest` in `tests/test_core.py`.

### Phase 2: Command Line Interface (CLI)
- [ ] **Task 2.1**: Implement CLI entry point `bible.py` (executable `./bible`) with verse lookup command (`./bible get "John 3:16"`, `./bible get "Romans 8:28-30"`).
- [ ] **Task 2.2**: Support multi-translation flag (`--version=WEB`, `--version=ESV`) with fallbacks.
- [ ] **Task 2.3**: Implement full-text search CLI command (`./bible search "light of the world"`).
- [ ] **Task 2.4**: Formatted terminal output (clean margins, optional verse numbers, colored ANSI styling using standard library).

### Phase 3: Semantic Tagging & Knowledge Database Engine
- [ ] **Task 3.1**: Create Tagging API allowing tags on individual verses or arbitrary verse spans (e.g., `Romans 8:1-11` -> `Holy Spirit`, `Sanctification`).
- [ ] **Task 3.2**: Implement verse-to-verse cross-referencing and relationship edges (thematic, prophecy-fulfillment, quotation).
- [ ] **Task 3.3**: Create batch LLM tagging tool/prompt generator to classify and tag scripture into predefined and dynamic semantic taxonomies.
- [ ] **Task 3.4**: Aggregation queries: topic density per book, tag co-occurrence matrix, verse relevance scoring.

### Phase 4: Web UI & Visualizations (Vanilla Web, No npm)
- [ ] **Task 4.1**: Build built-in HTTP server (`./bible serve [--port=8080]`) serving REST API and embedded static web assets via Python's `http.server`.
- [ ] **Task 4.2**: Implement pure SVG/Canvas Thematic Heatmap visualization across all 66 books of the Bible for any chosen tag/topic.
- [ ] **Task 4.3**: Implement drill-down verse viewer: clicking a heatmap cell / book chapter displays scripture passages and active tags.
- [ ] **Task 4.4**: Implement pure SVG Cross-Reference / Topic Graph visualization.

### Phase 5: Image & Typst Integration
- [ ] **Task 5.1**: Integrate Typst verse card generation from CLI (`./bible render "Philippians 4:13" --output=verse.png`).
- [ ] **Task 5.2**: Add template customization options for Typst rendering (fonts, colors, aspect ratios).
