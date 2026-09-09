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

---

## Hermeneutic Invariant: Pericope-First Exegesis

Biblical chapter and verse divisions are artificial post-biblical additions (versification was introduced in 1551 by Robert Estienne). The authorial, literary unit of thought is the **pericope** (typically 5–30 verses: e.g. Romans 8:1–11, Genesis 22:1–19).

**Strict Rule**: **Never perform exegesis or assign semantic tags to a single verse in total isolation.**
- An agent reading only Romans 8:28 ("all things work together for good") or John 11:35 ("Jesus wept") in isolation falls prey to moralistic flattening, shallow aphorisms, and proof-texting.
- All tagging must be performed **pericope-first**:
  1. Analyze the pericope as an organic literary and theological whole (central proposition, discourse connectives, redemptive-historical summary).
  2. Derive verse-level tags, theological loci, speech acts, and propositional triples as structural sub-elements within that pericope's discourse argument.

---

## Hermetic Context Sandwich: 3-Tier Stratified Context Architecture

To prevent **context rot** (accumulating thousands of tokens over long sessions) while preventing **out-of-context myopia** (isolated single verses), every pericope exegesis unit must be evaluated with a hermetic, stratified 3-tier context sandwich (~1,500–2,500 tokens total):

```
+-----------------------------------------------------------------------+
| TIER 1: MACRO CONTEXT (Book Horizon ~200 tokens)                      |
| Author, date, historical setting, overarching theological argument,   |
| and Christological trajectory (from core/semantic_prompts.py)         |
+-----------------------------------------------------------------------+
| TIER 2: MESO CONTEXT (Discourse Surroundings ~150 tokens)             |
| Preceding pericope heading + central proposition                      |
| Following pericope heading + central proposition                      |
+-----------------------------------------------------------------------+
| TIER 3: MICRO FOCUS (Active Pericope ~500–1,500 tokens)               |
| Full ESV/WEB scripture text of the active pericope with verse numbers |
+-----------------------------------------------------------------------+
| CONTROLLED VOCABULARY & THEOLOGICAL CRITIC RULES (~800 tokens)        |
| TGC hermeneutical constraints + JSON schema + taxonomy rules          |
+-----------------------------------------------------------------------+
```

1. **Tier 1 (Macro - Book Horizon)**: Injects the pre-compiled [`BookHorizon`](file:///usr/local/google/home/markwell/personal_dev/bible/core/semantic_prompts.py#L88-L120) for the book (e.g. Paul's argument of justification by faith in Romans).
2. **Tier 2 (Meso - Discourse Flow)**: Injects the central propositions of the preceding and following pericopes so the agent understands the trajectory of the author's argument.
3. **Tier 3 (Micro - Active Passage)**: Injects the exact verse text of the pericope with verse markers.

**Stateless Worker Isolation**: After the pericope JSON is generated, validated via `ExegeticalCritic`, and written to SQLite, the context memory is discarded. No exegesis tokens leak from one pericope into the next.

---

## Bounded Sprint Cadence for Autonomous Ralph Loop Iterations

To prevent timeouts, context degradation, or ambiguous task completion during autonomous execution cycles:

1. **Sprint Budget**:
   - A single Ralph loop iteration must claim a **bounded sprint**: exactly **one canonical book** (e.g. Galatians, Philippians), or a fixed budget of **15–25 pericopes** for massive books (e.g. Genesis, Psalms, Isaiah).
2. **Ledger-Driven State Machine**:
   - State is tracked in SQLite via [`SemanticCheckpointLedger`](file:///usr/local/google/home/markwell/personal_dev/bible/core/semantic_compiler.py#L80-L150) (`status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED')`).
   - Run compilation command:
     `python3 tools/build_semantic_db.py --book <BookName> --strict-critic`
3. **Deterministic Acceptance Criteria**:
   - 100% of the units assigned to the sprint must reach `status = COMPLETED` in SQLite.
   - Zero audit violations from [`ExegeticalCritic`](file:///usr/local/google/home/markwell/personal_dev/bible/core/semantic_audit.py#L8-L23).
   - Zero test regressions (`python3 tools/test_runner.py`).
4. **Handoff & Exit**:
   - Mark the book's subtask `[x]` in `ROADMAP.md`.
   - Record progress metrics in `AGENT_LOG.md`.
   - Commit with message `feat(semantic): tag <BookName> (<N> pericopes, <V> verses)`.
   - Push immediately (`git push origin main`) and terminate.

---

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
