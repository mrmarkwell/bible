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
