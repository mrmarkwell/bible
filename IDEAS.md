# Project Ideas & Feature Requests

This document is the intake hopper for new feature requests, brainstormed concepts, and future improvements. 

Ideas can be added directly by the repository owner or generated during interactive brainstorming sessions with an agent. Autonomous agents or interactive sessions will triage, refine, and translate these ideas into concrete, atomic tasks in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).

---

## Status Legend
- `[IDEA]`: Raw concept or brainstormed proposal; needs refinement.
- `[VETTED]`: Architecture and trade-offs verified against [MANIFESTO.md](file:///usr/local/google/home/markwell/personal_dev/bible/MANIFESTO.md) and [DECISIONS.md](file:///usr/local/google/home/markwell/personal_dev/bible/DECISIONS.md).
- `[SCHEDULED]`: Formalized into atomic tasks and added to [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).
- `[REJECTED]`: Decided against (rationale recorded).

---

## How to Submit / Brainstorm a Feature Request
1. **In an Interactive Chat**: Simply ask the agent: *"Let's brainstorm a feature for X"* or *"I want to add a feature: Y"*. The agent will analyze alignment, break it into tasks, and add it here or directly into `ROADMAP.md`.
2. **Direct Edit**: Add an entry below under the **Active Ideas** section using the template below.
3. **Commit & Push**: Any session adding or refining ideas must commit and push immediately (`git push origin main`).

### Idea Template
```markdown
### [STATUS] Feature Name
- **Summary**: Brief description of the capability.
- **Rationale**: Why this is valuable for the user or ecosystem.
- **Constraints & Alignment**:
  - Offline-first? Yes/No
  - Zero third-party dependencies? (Must use Python stdlib / native browser APIs)
  - Copyright compliant?
- **Proposed Roadmap Phase**: Which phase does this belong to or does it require a new phase?
- **Suggested Tasks**:
  - [ ] Task description
```

---

## Active Ideas & Brainstorming Hopper

### [VETTED] Semantic Tagging & Topical Heatmaps
- **Summary**: Tag verses and spans with topics (e.g. money, wisdom, Holy Spirit) and render visual heatmaps across all 66 books.
- **Status**: Scheduled in Phases 3 and 4 of [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).

### [VETTED] Zero-Dependency Web Visualization Server
- **Summary**: Embedded HTTP server (`./bible serve`) serving vanilla HTML/CSS/JS with native browser SVG/Canvas heatmaps without npm or pip dependencies.
- **Status**: Scheduled in Phase 4 of [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md).

### [IDEA] Audio Bible Alignment / Narration Timestamps
- **Summary**: Associate public-domain audio recordings (e.g. LibriVox WEB/KJV audio) with verse timestamps for synchronous playback and reading.
- **Rationale**: Enhances accessibility and devotional utility.
- **Status**: Raw idea awaiting evaluation.

### [IDEA] Interlinear & Original Language Lexicon (Hebrew / Greek)
- **Summary**: Store Strong's concordance numbers and lemma definitions alongside public-domain translations for deep word study.
- **Rationale**: Enables rich semantic drill-down into original language roots without external internet queries.
- **Status**: Raw idea awaiting evaluation.
