---
name: semantic-tagging
description: >-
  Apply biblical, theological, and christological semantic tags to Scripture passages and pericopes
  using direct agent cognition and local taxonomic schemas, without wasteful external API calls.
  Grounded in The Gospel Coalition (TGC) Foundation Documents and redemptive-historical hermeneutics.
---

# Semantic Tagging & Theological Annotation Skill

Use this skill when classifying, tagging, or annotating Scripture passages with theological themes, covenantal epochs, and typological arcs during application development.

## Core Mandate: Direct Agent Cognition vs External API Calls

- **Agent Identity**: The agent developing this platform is Gemini. Calling an external Gemini API via `GEMINI_API_KEY` during development is redundant, slow, and wasteful.
- **Credential Demarcation**:
  - `GEMINI_API_KEY`: Required **ONLY** for serving the app to end users (e.g. dynamic live RAG answer synthesis and biblical persona dialogue in `./bible serve` or `./bible chat`). Prompted interactively during `./bible init` or `./bible keys wizard`. It is **NOT** required for application development.
  - `ESV_API_KEY`: Stored locally in `.env` (`ESV_API_KEY=...`) and `config/esv_api_key.txt` (POSIX 0600, excluded from git). Used by agents to fetch clean modern English Standard Version text for context, passage extraction, or embedding reference.
- **Local Execution**: Autonomous agents generate semantic tags directly in-session using the local taxonomic definitions and prompt structures in [core/tag_prompts.py](file:///usr/local/google/home/markwell/personal_dev/bible/core/tag_prompts.py) and [core/semantic_prompts.py](file:///usr/local/google/home/markwell/personal_dev/bible/core/semantic_prompts.py).

## Theological Foundation: Dual-Horizon & Christ-Centered Hermeneutics

All tagging must adhere to [THEOLOGY.md](file:///usr/local/google/home/markwell/personal_dev/bible/THEOLOGY.md) (The Gospel Coalition Foundation Documents):

1. **Dual-Horizon Hermeneutic**:
   - *Near Horizon*: Read the text along its redemptive-historical trajectory in its immediate historical-grammatical context.
   - *Far Horizon*: Read the text across the canonical horizon, discerning how it prepares for, typifies, or flows from Jesus Christ.

2. **Christological Teleology**:
   - The entire canon bears witness to Christ (Luke 24:27, 44-47; John 5:39).
   - OT passages should identify typological shadows, covenant promises, and messianic trajectories without flattening historical reality into simplistic allegories.

3. **Gospel Uniqueness (Third Way)**:
   - Distinguish the gospel from both **legalism** (salvation by moral performance) and **antinomianism** (relativism / license without holiness).
   - Grace is the root of Christian obedience; faith produces holiness through the Holy Spirit.

## Canonical Taxonomies & Controlled Vocabularies

When tagging passages, draw primary categories from the canonical taxonomies defined in `core/tag_prompts.py`:

- **Theological / Systematic**: `trinity`, `sovereignty`, `creation`, `fall`, `sin`, `atonement`, `justification`, `sanctification`, `grace`, `resurrection`, `eschatology`.
- **Covenantal / Redemptive Epoch**: `covenant-creation`, `covenant-noah`, `covenant-abraham`, `covenant-moses`, `covenant-david`, `covenant-new`.
- **Typological / Christological**: `seed-of-woman`, `passover-lamb`, `bronze-serpent`, `true-temple`, `melchizedek-priesthood`, `davidic-king`, `suffering-servant`.
- **Practical & Ethical**: `discipleship`, `prayer`, `faith`, `humility`, `justice`, `mercy`, `worship`, `stewardship`.

## Tagging Procedure for Agents

1. **Retrieve Passage Text**:
   - Use the bundled offline WEB text in `data/bible.db`:
     `./bible "<ref>"`
   - Or use the developer `ESV_API_KEY` (automatically resolved from `.env` or `config/esv_api_key.txt`):
     `./bible "<ref>" --version=ESV`

2. **Formulate Tag Classification**:
   Format the classification payload following the canonical JSON schema:
   ```json
   {
     "reference": "John 1:1-14",
     "tags": ["incarnation", "trinity", "creation", "christology", "covenant-new"],
     "primary_category": "theological",
     "summary": "The eternal Word who was with God and was God becomes flesh, dwelling among us full of grace and truth.",
     "christological_connection": "Jesus Christ is the eternal Logos and true light, the climax of God's self-revelation.",
     "confidence": 0.98
   }
   ```

3. **Apply & Verify in Database**:
   - Preview with dry run:
     `python3 tools/tag_generator.py apply --dry-run <payload.json>`
   - Commit tags to database:
     `./bible tag add "John 1:1-14" "incarnation" --category=theological`
   - Inspect applied annotations:
     `./bible tag show "incarnation"`

4. **Verify Zero Regressions**:
   - Ensure all unit tests pass:
     `python3 -m unittest discover tests`
