# Autonomous Project Directive — Bible Engine

> [!IMPORTANT]
> **ZERO HUMAN INTERVENTION MANDATE**:
> You are operating in a fully autonomous agentic development loop (the **Ralph Loop**).
> You do NOT need and must NOT wait for human prompts, instructions, approvals, or greetings to begin work.
> Even if the user prompt is blank, a greeting ("hi"), or unspecific, **immediately and unconditionally begin Step 1 of the Ralph Loop**.

---

## Autonomous Execution Rules

1. **Self-Directed Boot**:
   * Consult [AGENTS.md](file:///usr/local/google/home/markwell/personal_dev/bible/AGENTS.md).
   * Check [BLOCKED.md](file:///usr/local/google/home/markwell/personal_dev/bible/BLOCKED.md):
     * If present with an unresolved blocker, self-terminate immediately.
     * If present with a human resolution, clear/delete `BLOCKED.md` and proceed.
   * Review [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md), [DECISIONS.md](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md), and [AGENT_LOG.md](file:///usr/local/google/home/markwell/personal_dev/bible/AGENT_LOG.md).

2. **Claim & Execute**:
   * Select the highest-priority `[TODO]` task from [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md) whose prerequisites are met.
   * Mark it `[IN PROGRESS]` with your timestamp.
   * Follow [ADR-003](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md#adr-003-zero-dependency-architecture-for-zero-maintenance--dependabot-immunity): **Python 3 Standard Library only** (no pip packages, no npm packages).
   * Write hermetic unit tests (`tests/test_*.py`) and verify 100% pass (`python3 -m unittest discover tests`).

3. **No Interactive Clarification**:
   * Do NOT pause to ask the human user questions.
   * Resolve any design ambiguity independently, align with [MANIFESTO.md](file:///usr/local/google/home/markwell/personal_dev/bible/MANIFESTO.md), and append the decision to [DECISIONS.md](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md).

4. **Handoff & Clean Exit**:
   * Mark the task `[DONE]` in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
   * Append a summary to [AGENT_LOG.md](file:///usr/local/google/home/markwell/personal_dev/bible/AGENT_LOG.md).
   * Commit all work with conventional git commit message.
   * Verify git working tree is clean.
   * Self-terminate immediately.
