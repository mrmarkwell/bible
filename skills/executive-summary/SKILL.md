---
name: executive-summary
description: >-
  Generate and present a curated executive summary reviewing work done across recent Ralph loop
  iterations (default: last 10), high-level project trajectory, remaining roadmap effort, and
  system health. Use when asked for an executive summary, milestone review, project trajectory,
  or status briefing.
---

# Executive Summary & Trajectory Briefing

Use this skill whenever the user asks for an **executive summary**, a review of recent Ralph loop iterations, an assessment of project trajectory/completion, or an overall project health check.

## Automatic Cadence & On-Demand Usage

- **Automatic 10th Iteration Double Milestone**: Every 10th Ralph loop iteration (`run_number % 10 == 0`, e.g. Run #010, #020, #030...) performs the **Senior Product Manager role** (since 10 is divisible by 5) by answering the core diagnostic questions and executing a Rank A+ meta-improvement. At the end of the cycle, the agent delivers the curated **Human Executive Briefing post-summary**.
- **On-Demand Usage**: Can be executed at any time on-demand via the CLI or python tool:
  - Command: `./bible summary` or `python3 tools/executive_summary.py`
  - Custom window (e.g. last 5 or 20 runs): `./bible summary --window 20`

## Procedure

1. **Execute Diagnostic & Summary Generator**:
   Run the zero-dependency executive summary generator:
   ```bash
   python3 tools/executive_summary.py [--window 10]
   ```
   Or via the CLI:
   ```bash
   ./bible summary
   ```

2. **Inspect the Generated Report**:
   The report evaluates:
   - **Executive Overview & Trajectory**: Overall roadmap completion percentage, active phase, remaining tasks, observed velocity, and estimated iterations remaining.
   - **Phase Breakdown**: Completed vs total tasks per phase across all 8 phases.
   - **Review of Work in Last N Iterations**: Chronological summary of goals, phase, and key technical highlights for each run.
   - **Overall Project Health**: Automated diagnostics covering Zero-Dependency compliance (AST audit), documentation state machine sync, shell integrity, database integrity, and test pass rate.
   - **Immediate Next Milestones**: The next atomic roadmap task and upcoming cadence milestones.

3. **Present to User**:
   Provide the formatted markdown output directly to the user in the conversation or log entry.
