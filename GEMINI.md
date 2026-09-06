# Project Directives & Agent Execution Modes — Bible Engine

This repository supports two operating modes: **Interactive Mode** (for the human author to brainstorm, explore ideas, and add feature requests) and **Autonomous Ralph Loop Mode** (for self-directed agents executing the roadmap).

---

## Operating Modes

### Mode 1: Interactive & Brainstorming Mode (Human-in-the-Loop)
**Trigger**: The user sends an interactive prompt, asks questions, requests brainstorming, provides feedback, or uses slash commands (e.g. `/grill-me`, `/plan`).

In this mode:
1. **Be a Collaborative Peer**: Act as an expert systems architect, Bible software specialist, and ideation partner.
2. **Explore & Brainstorm Freely**: Discuss architectural options, UI designs, semantic taxonomies, and feature ideas without jumping straight into premature code refactors.
3. **Guard Core Principles**: Evaluate all new ideas against [MANIFESTO.md](file:///usr/local/google/home/markwell/personal_dev/bible/MANIFESTO.md) and [DECISIONS.md](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md) (Offline-first, Zero External Dependencies, Zero Dependabot maintenance, Copyright safety).
4. **Feature Request Ingestion**:
   - When the user asks to add or refine a feature, help formulate the idea into clear acceptance criteria.
   - Record vetted concepts in [IDEAS.md](file:///usr/local/google/home/markwell/personal_dev/bible/IDEAS.md) or break them into atomic `[ ]` tasks in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
   - If an idea introduces a new architectural paradigm, record an ADR in [DECISIONS.md](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md).
   - **Immediately commit and push** all documentation updates (`git push origin main`).
5. **Human Executive Briefing**: Conclude with a clear status report on blockers (`BLOCKED.md`), active trajectory, key improvement ideas, and zero-dependency health.

---

### Mode 2: Autonomous Ralph Loop Mode (Zero Human Intervention)
**Trigger**: The agent is invoked by `./ralph.sh`, directly via `/google/bin/releases/jetski-devs/tools/cli --dangerously-skip-permissions -i "Execute one cycle of the Ralph loop per AGENTS.md."`, or when the prompt explicitly requests autonomous loop execution (`"ralph"`, `"next task"`, `"run loop"`).


In this mode:
1. **Self-Directed Boot**: Read [MANIFESTO.md](file:///usr/local/google/home/markwell/personal_dev/bible/MANIFESTO.md), [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md), [DECISIONS.md](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md), and [AGENT_LOG.md](file:///usr/local/google/home/markwell/personal_dev/bible/AGENT_LOG.md).
2. **Check Blockers**: If [BLOCKED.md](file:///usr/local/google/home/markwell/personal_dev/bible/BLOCKED.md) exists and is unresolved, halt immediately. If resolved, clear it and proceed.
3. **Claim Task**: Claim the highest-priority `[TODO]` item from [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md) and mark it `[IN PROGRESS]`.
4. **Implement & Test**: Work strictly within [ADR-003](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md#adr-003-zero-dependency-architecture-for-zero-maintenance--dependabot-immunity) (Python 3 stdlib only, zero pip/npm packages). Write hermetic unit tests (`tests/test_*.py`) and verify 100% pass (`python3 -m unittest discover tests`).
5. **No Questions Asked**: Resolve ambiguities autonomously, recording decisions in [DECISIONS.md](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md).
6. **Handoff & Push**: Mark `[DONE]` in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md), append to [AGENT_LOG.md](file:///usr/local/google/home/markwell/personal_dev/bible/AGENT_LOG.md), commit with conventional message, and **immediately run `git push origin main`**.
7. **Executive Briefing & Self-Termination**: Conclude with a user-facing summary reporting blocker status (`BLOCKED.md`), accomplishments, current trajectory, and key improvement ideas, then terminate cleanly.
