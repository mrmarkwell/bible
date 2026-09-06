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

### [VETTED] TV Screensaver Verse Slide Generator (`bible slide` / `bible render`)
- **Summary**: Generate high-resolution 16:9 landscape slides (4K UHD default) with white scripture text on true OLED black background for Google Photos TV screensaver slideshows.
- **Rationale**: Provides ambient, contemplative scripture display on home televisions. High dynamic contrast, zero burn-in on OLED displays, and beautiful dynamic typography regardless of passage length.
- **Constraints & Alignment**:
  - Offline-first? Yes (local rendering engine).
  - Zero third-party dependencies? Yes (uses Python stdlib + system ImageMagick / pure SVG, zero pip packages per ADR-003).
  - Copyright compliant? Yes (public domain WEB/KJV by default, user-supplied texts/APIs optional).
- **Design Specifications**:
  - Landscape 16:9 aspect ratio (default 3840x2160 4K UHD, configurable to 1080p or custom).
  - Pure `#000000` black background for OLED energy efficiency and infinite contrast.
  - 15% TV safe area margin to prevent bezel clipping and overscan loss.
  - Dynamic scaling algorithm with font size clamping: auto-computes optimal font size, line wrapping, and line height to center both short verses (e.g. "Jesus wept") and lengthy pericopes without overflow.
  - Optical vertical centering (~45% baseline rather than strict geometric 50%) for natural viewing.
  - Distinct hierarchical citation styling (muted off-white/gray, em-dash or small caps).
  - Multi-slide pagination support for lengthy passages exceeding safe viewing density.
  - Dual rendering backend: ImageMagick (`magick`/`convert`) for raster PNG/JPEG + pure Python SVG vector generator.
- **Proposed Roadmap Phase**: Phase 5 (Tasks 5.1–5.5 in [ROADMAP.md](file:///usr/local/google/home/markwell/personal_dev/bible/ROADMAP.md)).
- **Status**: [VETTED] and scheduled.

### [IDEA] Audio Bible Alignment / Narration Timestamps
- **Summary**: Associate public-domain audio recordings (e.g. LibriVox WEB/KJV audio) with verse timestamps for synchronous playback and reading.
- **Rationale**: Enhances accessibility and devotional utility.
- **Status**: Raw idea awaiting evaluation.

### [IDEA] Interlinear & Original Language Lexicon (Hebrew / Greek)
- **Summary**: Store Strong's concordance numbers and lemma definitions alongside public-domain translations for deep word study.
- **Rationale**: Enables rich semantic drill-down into original language roots without external internet queries.
- **Status**: Raw idea awaiting evaluation.

