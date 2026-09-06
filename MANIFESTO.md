# The Bible Engine Manifesto

> "The grass withers, the flower fades, but the word of our God will stand forever." — Isaiah 40:8

## 1. Vision & Purpose

The **Bible Engine** is an offline-first, locally hosted platform designed to explore, analyze, and visualize biblical text and semantic relationships. It combines:
1. A blazing-fast **Command-Line Interface (CLI)** for instant scripture reference, search, and reading.
2. A structured **Knowledge Database** storing biblical texts, multi-resolution semantic tags, cross-references, and commentary metadata.
3. An interactive **Web UI** offering visual macro-level insights (e.g., topic heatmaps across the 66 canonical books) with micro-level drill-down capabilities.
4. An **Autonomous Agent Workflow** engineered for continuous, decentralized software evolution by AI agents without human micro-management.

---

## 2. Core Pillars

### I. Offline-First & Sovereign Data
The platform must function 100% offline once set up. It requires no continuous internet access, no remote database dependencies, and no phone-home telemetry. All texts, indexes, and semantic metadata live locally on the user's filesystem in open, standard formats (SQLite).

### II. Public Domain First & Copyright Safety
Publishing biblical text in a public GitHub repository requires strict legal diligence:
- **Public Domain Texts (First-Class Citizens)**: Translations such as the **World English Bible (WEB)**, King James Version (KJV), or American Standard Version (ASV) are freely redistributable and can be included directly in public repositories without legal hindrance.
- **Copyrighted Translations (ESV, NIV, NASB, etc.)**: Plaintext copyrighted translations must never appear unencrypted or unlicensed in a public git repository. The system provides:
  - Secure local encryption / encrypted data packs requiring a user-supplied key or offline unlock mechanism.
  - On-demand API/local ingestion scripts where users supply their own authorized credentials or locally licensed text files.

### III. Multi-Resolution Semantic Knowledge Graph
Biblical text is dense and non-linear. The database models scripture across multiple granularities:
- **Atoms**: Canonical verses referenced by standard scheme (`Book Chapter:Verse`, e.g., `JHN 3:16`).
- **Spans**: Multi-verse passages, pericope units, chapters, and thematic arcs.
- **Semantic Tags**: Thematic tags (e.g., `money`, `covenant`, `wisdom`, `atonement`, `Holy Spirit`, `command`, `lament`) with confidence scores, origins (human vs. model), and hierarchical categorizations.
- **Relational Edges**: Cross-references, direct citations, thematic connections, and typology links.

### IV. Visual & Cognitive Comprehension
Text search is not enough. The Web UI transforms biblical knowledge into visual insight:
- **Macro-Scale Heatmaps**: View thematic density across the entire biblical canon (Pentateuch, Historical, Wisdom, Major/Minor Prophets, Gospels, Epistles, Apocalypse).
- **Interactive Exploration**: Click into heatmap cells, scripture clusters, and edge networks to immediately view the corresponding verses and context.

### V. Autonomous Agent Evolution (The Ralph Loop)
This codebase is developed and maintained primarily by autonomous LLM agents running in bounded execution loops ("Ralph loops"):
- Every agent is ephemeral, stateless, and self-contained.
- Documentation, state tracking, and decision logging are treated as first-class architectural components.
- Progress is incremental, tested, committed frequently, and cleanly handed off.
