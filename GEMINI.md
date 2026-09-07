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
5. **Human Executive Briefing & Mandatory Post-Briefing Promotion**: Conclude with a clear status report on blockers (`BLOCKED.md`), active trajectory, and key improvement ideas with mandatory letter grades. **CRITICAL POST-BRIEFING STEP**: If ANY idea is evaluated as rank **A+**, you MUST NOT stop; you MUST immediately call tools to append it to [IDEAS.md](file:///usr/local/google/home/markwell/personal_dev/bible/IDEAS.md), commit, and push (`git push origin main`) before finishing.

---

### Mode 2: Autonomous Ralph Loop Mode (Zero Human Intervention)
**Trigger**: The agent is invoked by `./ralph.sh`, directly via `/google/bin/releases/jetski-devs/tools/cli --dangerously-skip-permissions -i "Execute one cycle of the Ralph loop per AGENTS.md."`, or when the prompt explicitly requests autonomous loop execution (`"ralph"`, `"next task"`, `"run loop"`).


In this mode:
1. **Self-Directed Boot**: Read [MANIFESTO.md](file:///usr/local/google/home/markwell/personal_dev/bible/MANIFESTO.md), [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md), [DECISIONS.md](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md), and [AGENT_LOG.md](file:///usr/local/google/home/markwell/personal_dev/bible/AGENT_LOG.md).
2. **Check Blockers**: If [BLOCKED.md](file:///usr/local/google/home/markwell/personal_dev/bible/BLOCKED.md) exists and is unresolved, halt immediately. If resolved, clear it and proceed.
3. **Cadence Check (Every 5th Iteration = Senior PM Cleanup Sprint)**:
   - **If Run Number is a multiple of 5, loop iteration % 5 == 0, or invoked via `--cleanup`**:
     - Assume the persona of a **Senior Product Manager & Meta-Architect**.
     - Do **NOT** advance domain roadmap feature tasks.
     - Audit the health of the whole system, answering the two core diagnostic questions:
       1. *"What is the weakest aspect of this project structure?"*
       2. *"What is preventing this from being more incredible?"*
     - Conceive at least ONE Rank A+ idea to improve or clean up the system/processes.
     - **Execute it completely**: Nothing is disallowed during these sprints. Write code/tools, run tests (100% pass), record ADR in [DECISIONS.md](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md), promote in [IDEAS.md](file:///usr/local/google/home/markwell/personal_dev/bible/IDEAS.md), and log in [AGENT_LOG.md](file:///usr/local/google/home/markwell/personal_dev/bible/AGENT_LOG.md).
   - **If Standard Cycle**:
     - Claim the highest-priority `[TODO]` item from [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md) and mark it `[IN PROGRESS]`.
     - Implement feature & hermetic unit tests (`tests/test_*.py`).
4. **Implement & Test**: Work strictly within [ADR-003](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md#adr-003-zero-dependency-architecture-for-zero-maintenance--dependabot-immunity) (Python 3 stdlib only, zero pip/npm packages). Verify 100% test pass (`python3 -m unittest discover tests`).
5. **No Questions Asked**: Resolve ambiguities autonomously, recording decisions in [DECISIONS.md](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md).
6. **Handoff & Push**: Mark completed items in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md), append to [AGENT_LOG.md](file:///usr/local/google/home/markwell/personal_dev/bible/AGENT_LOG.md), commit with conventional message, and **immediately run `git push origin main`**.
7. **Emit Executive Briefing**: Conclude with a user-facing summary reporting blocker status (`BLOCKED.md`), accomplishments, current trajectory, letter-graded improvement ideas, and hygiene.
8. **MANDATORY POST-BRIEFING A+ PROMOTION STEP**: Review the ideas in Section 4 of the emitted briefing. If ANY idea is self-evaluated as rank **A+**, you MUST NOT stop; you MUST immediately call tools to append the formalized feature request to [IDEAS.md](file:///usr/local/google/home/markwell/personal_dev/bible/IDEAS.md), commit (`git commit -m "docs: promote Rank A+ idea <name> to IDEAS.md"`), and immediately run `git push origin main`. Never terminate without executing this step.
9. **Self-Termination**: Cleanly exit only after Step 8 completes.
