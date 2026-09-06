# Project Roadmap & Backlog

This document is the single source of truth for current project status, active tasks, and future backlog. Autonomous agents must consult this document during boot and update it upon completing work.

---

## Current Status Overview
- **Active Phase**: Phase 0 — Repository Architecture & Autonomous Harness
- **Overall Progress**: Foundation setup in progress

---

## Phase Breakdown

### Phase 0: Repository Architecture & Autonomous Harness
- [x] **Task 0.1**: Draft `MANIFESTO.md`, `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and `AGENT_LOG.md`.
- [x] **Task 0.2**: Restructure repository layout (establish `cli/`, `core/`, `web/`, `data/`, `legacy/`).
- [ ] **Task 0.3**: Confirm core technology stack and copyright handling strategy with repository owner.

### Phase 1: Core Data Models & Offline Scripture Storage
- [ ] **Task 1.1**: Define standard canonical scripture reference model (Book [1-66], Chapter, Verse, Span/Range, OSIS identifiers).
- [ ] **Task 1.2**: Design and implement SQLite database schema (`verses`, `translations`, `books`, `spans`, `tags`, `verse_tags`, `cross_references`).
- [ ] **Task 1.3**: Ingest full Public Domain Bible translation (World English Bible - WEB / KJV) into SQLite database for offline access.
- [ ] **Task 1.4**: Implement encryption / obfuscation module for copyrighted translations (AES-256-GCM / ChaCha20) with CLI import mechanism.
- [ ] **Task 1.5**: Comprehensive unit tests for scripture reference parsing, database query performance, and offline text retrieval.

### Phase 2: Command Line Interface (CLI)
- [ ] **Task 2.1**: Implement CLI entry point with verse lookup command (`bible get "John 3:16"`, `bible get "Romans 8:28-30"`).
- [ ] **Task 2.2**: Support multi-translation flag (`--version=WEB`, `--version=ESV`) with fallbacks.
- [ ] **Task 2.3**: Implement full-text search CLI command (`bible search "light of the world"`).
- [ ] **Task 2.4**: Add formatted terminal output (syntax highlighting, clean margins, optional verse numbers).

### Phase 3: Semantic Tagging & Knowledge Database Engine
- [ ] **Task 3.1**: Create Tagging API allowing tags on individual verses or arbitrary verse spans (e.g., `Romans 8:1-11` -> `Holy Spirit`, `Sanctification`).
- [ ] **Task 3.2**: Implement verse-to-verse cross-referencing and relationship edges (thematic, prophecy-fulfillment, quotation).
- [ ] **Task 3.3**: Create an offline/online batch LLM tagging tool/script to classify and tag chapters and verses into predefined and dynamic semantic taxonomies.
- [ ] **Task 3.4**: Aggregation queries: topic density per book, tag co-occurrence matrix, verse relevance scoring.

### Phase 4: Web UI & Visualizations
- [ ] **Task 4.1**: Build local lightweight web server / API endpoint (`bible serve` command).
- [ ] **Task 4.2**: Implement Thematic Heatmap visualization across all 66 books of the Bible for any chosen tag/topic.
- [ ] **Task 4.3**: Implement drill-down verse viewer: clicking a heatmap cell / book chapter displays scripture passages and active tags.
- [ ] **Task 4.4**: Implement Cross-Reference / Topic Graph visualization.

### Phase 5: Image & Typst Integration
- [ ] **Task 5.1**: Integrate and modernize Typst verse card generation from CLI (`bible render "Philippians 4:13" --format=png`).
- [ ] **Task 5.2**: Add template customization options for Typst rendering (fonts, colors, aspect ratios).
