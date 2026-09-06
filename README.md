# Bible Engine

An offline-first, locally hosted platform for scripture retrieval, semantic tagging, and biblical knowledge visualization.

## Overview
- **Fast Scripture Retrieval**: Instant offline passage lookup via CLI.
- **Knowledge Database**: Multi-resolution tagging (individual verses & verse spans) and verse cross-referencing.
- **Visualizations**: Topic density heatmaps across the 66 books of the Bible, with interactive verse drill-down.
- **Copyright Safe**: Built around public-domain modern translations (such as World English Bible - WEB) with secure local encryption for copyrighted texts.
- **Autonomous Agent Ecosystem**: Developed continuously via Ralph loops by self-directed AI agents.

## Core Documentation
- [MANIFESTO.md](file:///usr/local/google/home/markwell/personal_dev/bible/MANIFESTO.md): Architecture pillars, vision, and domain concepts.
- [AGENTS.md](file:///usr/local/google/home/markwell/personal_dev/bible/AGENTS.md): Operating manual for autonomous agents (Ralph Loop lifecycle).
- [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md): Current status and backlog tasks across all phases.
- [DECISIONS.md](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md): Architectural Decision Records (ADRs).
- [AGENT_LOG.md](file:///usr/local/google/home/markwell/personal_dev/bible/AGENT_LOG.md): Append-only chronological agent execution logs.

## Repository Layout
- `cli/`: Command-line interface definitions and commands.
- `core/`: Scripture reference parser, database schema, and storage abstraction.
- `web/`: Local web dashboard and visualizations.
- `data/`: Local SQLite database files, migrations, and raw translation texts.
- `legacy/`: Preserved initial Lua and Typst prototypes.
