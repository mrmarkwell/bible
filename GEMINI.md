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
2. **Check Blockers**: If [BLOCKED.md](file:///usr/local/google/home/markwell/personal_dev/bible/BLOCKED.md) exists and is unresolved, halt immediately. If resolved, clear it and proceed. **Mandatory Blocker Rule**: If a task requires external credentials that are absent, you MUST NOT silently generate hollow placeholder data; you MUST stop and record a blocker in `BLOCKED.md` requesting the necessary key!
   - **Where to find `ESV_API_KEY`**: Stored locally in `.env` (`ESV_API_KEY=...`) or `config/esv_api_key.txt` (POSIX 0600 permissions, strictly ignored by git). Automatically discovered via `core.esv.get_esv_api_key()` or `tools.onboarding.discover_esv_api_key()` for passage queries, semantic tagging context, and embeddings.
   - **`GEMINI_API_KEY` Scope**: Needed **ONLY** for serving the app (dynamic Scripture RAG and Persona Chat in `./bible serve`), gathered interactively during `./bible init`. For application development like semantic tagging, agents MUST use local skills (`skills/semantic-tagging/SKILL.md`) rather than wasteful external API calls. Missing `GEMINI_API_KEY` is never a blocker for development agents.
3. **Priority 0 Check: GitHub Actions CI/CD Health (TOP PRIORITY)**:
   - Check the health of GitHub Actions CI on `origin/main` using `python3 tools/ci.py check` (or `./bible ci check`).
   - If CI/CD is failing or broken on GitHub Actions, **HALT ALL OTHER TASKS AND FIX CI/CD FIRST**.
   - Do not pick up new roadmap tasks or triage normal GitHub issues while CI is red.
   - Investigate failure logs (`./bible ci status --details` or `gh run view --log-failed`), reproduce locally, fix root cause, verify hermetic test pass (`./bible test`), commit, and push immediately (`git push origin main`).
   - Monitor CI until it passes (`./bible ci --watch`).
4. **Priority Check: Open GitHub Issue / Bug Report Triage**:
   - Check for open GitHub issues using `python3 tools/github_issues.py check` (or `./bible issues list`).
   - If an open GitHub issue exists, **prioritize addressing it in this iteration before roadmap tasks**:
     - *Path A (Fix & Close)*: Write regression test, fix bug, verify 100% tests pass (`./bible test`), commit with `Fixes #<number>`, and close via `python3 tools/github_issues.py close <number> --comment "..."` (or let GitHub native commit parsing close on push).
     - *Path B (Close with Reason)*: Close invalid/duplicate/unplanned issue via `python3 tools/github_issues.py close <number> --reason not_planned --comment "<reason>"`.
     - *Path C (Diagnostic Comment)*: If blocked or awaiting information, post status comment via `python3 tools/github_issues.py comment <number> "<status and reason>"`.
   - Document triage and resolution in `AGENT_LOG.md`.
5. **Cadence Check (10th Iteration = Senior PM Meta-Sprint + Executive Briefing; 5th Iteration = Senior PM Cleanup Sprint)**:
   - **If Run Number is a multiple of 10, loop iteration % 10 == 0, or invoked via `--summary`**:
     - Step into the **Senior Product Manager & Meta-Architect** role (since 10 is divisible by 5): answer the two core diagnostic questions (*"What is the weakest aspect?"*, *"What is preventing this from being more incredible?"*), formulate and **execute** a Rank A+ meta-improvement with 100% passing tests and zero dependencies.
     - Next, run `python3 tools/executive_summary.py` (or `./bible summary`) to curate the accomplishments across the last 10 iterations from `AGENT_LOG.md`.
     - Deliver the curated **Human Executive Briefing post-summary** at the end of the iteration, covering project trajectory, remaining effort in iterations, overall system health, and letter-graded improvement opportunities (with mandatory immediate ingestion for any Rank A+ ideas).
   - **If Run Number is a multiple of 5 (and not 10), loop iteration % 5 == 0, or invoked via `--cleanup`**:
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
6. **Implement & Test**: Work strictly within [ADR-003](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md#adr-003-zero-dependency-architecture-for-zero-maintenance--dependabot-immunity) (Python 3 stdlib only, zero pip/npm packages). Verify 100% test pass (`python3 -m unittest discover tests`).
7. **No Questions Asked**: Resolve ambiguities autonomously, recording decisions in [DECISIONS.md](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md).
8. **Handoff & Push**: Mark completed items in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md), append to [AGENT_LOG.md](file:///usr/local/google/home/markwell/personal_dev/bible/AGENT_LOG.md), commit with conventional message, and **immediately run `git push origin main`**.
9. **Emit Executive Briefing**: Conclude with a user-facing summary reporting blocker status (`BLOCKED.md`), accomplishments, current trajectory, letter-graded improvement ideas, and hygiene.
10. **MANDATORY POST-BRIEFING A+ PROMOTION STEP**: Review the ideas in Section 4 of the emitted briefing. If ANY idea is self-evaluated as rank **A+**, you MUST NOT stop; you MUST immediately call tools to append the formalized feature request to [IDEAS.md](file:///usr/local/google/home/markwell/personal_dev/bible/IDEAS.md), commit (`git commit -m "docs: promote Rank A+ idea <name> to IDEAS.md"`), and immediately run `git push origin main`. Never terminate without executing this step.
11. **Self-Termination**: Cleanly exit only after Step 10 completes.
