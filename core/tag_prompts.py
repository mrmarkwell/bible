"""Scripture Tagging Prompt Generator & LLM Response Parser.

Zero-dependency implementation (Python 3 standard library only per ADR-003):
- Prompt engineering for classifying biblical passages into predefined and dynamic semantic taxonomies.
- Strict alignment with The Gospel Coalition (TGC) Foundation Documents (ADR-006, THEOLOGY.md):
  * Dual-horizon hermeneutics: Reading along redemptive history + across systematic doctrine.
  * Christ-centered teleology: Every passage prepares for, reveals, or flows from Jesus Christ.
  * Gospel uniqueness: Focus on God's covenant grace, union with Christ, and Spirit-empowered obedience.
- Standardized JSON output contracts with schema validation, normalization, and confidence clamping.
- Resilient response extraction handling markdown code blocks, raw JSON, and error recovery.
- Single-passage, multi-passage, and batch JSONL prompt generators.
"""

from dataclasses import dataclass, field
import json
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from core.reference import Reference, parse_reference
from core.tags import CANONICAL_TAXONOMY, TagCategory


# ==============================================================================
# TGC Theological Hermeneutical System Prompt
# ==============================================================================

TGC_HERMENEUTICAL_SYSTEM_PROMPT = """You are an expert biblical theologian and Christian scholar grounded in The Gospel Coalition (TGC) Foundation Documents (Confessional Statement and Theological Vision for Ministry, detailed in THEOLOGY.md).

Your mission is to analyze biblical scripture passages and assign precise, richly descriptive semantic tags categorized by biblical theology, systematic theology, and redemptive history.

Follow these foundational theological and hermeneutical guardrails:
1. DUAL-HORIZON HERMENEUTICS:
   - Read "ALONG" the biblical storyline: Trace where this passage fits in the unfolding historical narrative of redemption (Creation -> Fall -> Covenant -> Exodus -> Temple -> Kingship -> Exile -> Restoration -> Climax in Jesus Christ -> Church -> New Creation).
   - Read "ACROSS" the biblical canon: Connect the passage to systematic doctrines of grace (Trinity, Christology, Pneumatology, Sovereign Grace, Penal Substitutionary Atonement, Justification by Faith Alone, Sanctification, Glorification).

2. CHRIST-CENTERED TELEOLOGY:
   - Old Testament passages foreshadow, prophesy, or typologically prepare for the person, office (Prophet, Priest, King), and sacrifice of Jesus Christ.
   - New Testament passages declare, explain, or pastorally apply the finished work of Christ and His kingdom.

3. GOSPEL UNIQUENESS & GRACE-DRIVEN APPLICATION:
   - Recognize that the biblical gospel is distinct from both legalistic moralism ("I obey, therefore I am accepted") and antinomian relativism ("I am free to live as I please").
   - Highlight God's sovereign covenant mercy and the believer's union with Christ, while affirming genuine fruit, faith, and obedience wrought by the Holy Spirit.

4. TAGGING PRECISION & METRICS:
   - Assign 2 to 6 of the most central and relevant tags for each passage.
   - For each tag, provide a confidence score (0.0 to 1.0) and a concise theological rationale explaining how the text justifies this tag.
   - Designate exactly one primary/central tag as "starred": true (the defining motif of the passage).
   - Output must strictly conform to the required JSON schema with no conversational filler.
"""


# ==============================================================================
# Data Transfer Objects (DTOs)
# ==============================================================================


@dataclass(frozen=True)
class GeneratedTag:
    """A semantic tag generated or parsed from an LLM response."""

    name: str
    category: str = TagCategory.THEMATIC
    confidence: float = 1.0
    starred: bool = False
    notes: Optional[str] = None
    sub_span: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize tag to dictionary."""
        return {
            "name": self.name,
            "category": self.category,
            "confidence": round(self.confidence, 3),
            "starred": self.starred,
            "notes": self.notes,
            "sub_span": self.sub_span,
        }


@dataclass
class TaggingResult:
    """Parsed result containing the target passage and associated generated tags."""

    reference: str
    tags: List[GeneratedTag] = field(default_factory=list)
    raw_response: Optional[str] = None
    model: Optional[str] = None
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """True if tags were parsed without error."""
        return self.error is None and len(self.tags) > 0

    @property
    def starred_tag(self) -> Optional[GeneratedTag]:
        """Return the primary/starred tag if present."""
        for t in self.tags:
            if t.starred:
                return t
        return self.tags[0] if self.tags else None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize tagging result to dictionary."""
        return {
            "reference": self.reference,
            "tags": [t.to_dict() for t in self.tags],
            "model": self.model,
            "error": self.error,
        }


# ==============================================================================
# Taxonomy Context & Prompt Formatting
# ==============================================================================


def get_tgc_hermeneutical_system_prompt() -> str:
    """Return the canonical TGC-aligned hermeneutical system prompt."""
    return TGC_HERMENEUTICAL_SYSTEM_PROMPT.strip()


def format_taxonomy_for_prompt(
    categories: Optional[Sequence[str]] = None,
    custom_tags: Optional[Sequence[Union[str, Tuple[str, str, str]]]] = None,
    include_descriptions: bool = True,
) -> str:
    """Build a structured text representation of the taxonomy for LLM prompts.

    Args:
        categories: Optional list of categories to filter (`theological`, `historical`, etc.).
        custom_tags: Optional custom candidate tags (strings or `(name, category, description)` tuples).
        include_descriptions: Whether to append theological descriptions to tag names.

    Returns:
        Formatted markdown string describing available taxonomy tags.
    """
    lines: List[str] = []
    allowed_cats = {c.strip().lower() for c in categories} if categories else None

    # Format Canonical Predefined Taxonomies
    section_titles = {
        "redemptive_historical": "Redemptive-Historical Storyline Motifs (Reading Along)",
        "systematic_theology": "Systematic & Covenant Theology (Reading Across)",
        "practical_christian_living": "Christian Faith & Lived Obedience",
    }

    for group_key, tag_list in CANONICAL_TAXONOMY.items():
        title = section_titles.get(group_key, group_key.replace("_", " ").title())
        group_lines: List[str] = []

        for name, cat, desc in tag_list:
            if allowed_cats and cat.lower() not in allowed_cats:
                continue
            if include_descriptions and desc:
                group_lines.append(f"- **{name}** (`{cat}`): {desc}")
            else:
                group_lines.append(f"- **{name}** (`{cat}`)")

        if group_lines:
            lines.append(f"### {title}")
            lines.extend(group_lines)
            lines.append("")

    # Format Custom / Dynamic Candidate Tags
    if custom_tags:
        lines.append("### Custom & User-Defined Taxonomy Tags")
        for item in custom_tags:
            if isinstance(item, tuple) and len(item) == 3:
                c_name, c_cat, c_desc = item
                lines.append(f"- **{c_name}** (`{c_cat}`): {c_desc}")
            elif isinstance(item, tuple) and len(item) == 2:
                c_name, c_cat = item
                lines.append(f"- **{c_name}** (`{c_cat}`)")
            else:
                c_name = str(item)
                lines.append(f"- **{c_name}** (`thematic`)")
        lines.append("")

    return "\n".join(lines).strip()


# ==============================================================================
# Prompt Generation Functions
# ==============================================================================


def generate_tagging_prompt(
    reference: Union[Reference, str],
    passage_text: str,
    categories: Optional[Sequence[str]] = None,
    custom_tags: Optional[Sequence[Union[str, Tuple[str, str, str]]]] = None,
    allow_new_tags: bool = True,
    max_tags: int = 6,
    translation_id: str = "WEB",
) -> str:
    """Generate a hermeneutically rigorous prompt to classify a biblical passage into semantic tags.

    Args:
        reference: Citation string or canonical Reference object (e.g. "Romans 8:1-11").
        passage_text: The scripture text of the passage.
        categories: Optional list of tag categories to restrict or emphasize.
        custom_tags: Optional user-supplied candidate tags.
        allow_new_tags: If True, LLM may propose novel tags if no existing tag fits.
        max_tags: Maximum number of tags to produce (default 6).
        translation_id: Bible translation code (e.g. 'WEB', 'ESV').

    Returns:
        Structured prompt string ready for Gemini or other LLMs.
    """
    ref_obj = parse_reference(reference) if isinstance(reference, str) else reference
    human_ref = ref_obj.format()
    clean_text = passage_text.strip()

    taxonomy_block = format_taxonomy_for_prompt(
        categories=categories,
        custom_tags=custom_tags,
        include_descriptions=True,
    )

    new_tag_directive = (
        "You may also propose novel, high-value tags if the passage distinctly warrants them, "
        "provided you assign an appropriate category and theological rationale."
        if allow_new_tags
        else "You MUST select tags exclusively from the predefined taxonomies listed above. Do not invent new tags."
    )

    valid_categories_str = ", ".join(f"`{c}`" for c in TagCategory.ALL)

    prompt = f"""Analyze the following biblical passage and classify it with semantic tags according to redemptive-historical and systematic theological significance.

## Scripture Passage
- **Citation**: {human_ref}
- **Translation**: {translation_id}
- **Text**:
\"\"\"{clean_text}\"\"\"

## Available Taxonomy
{taxonomy_block}

## Instructions & Directives
1. Select between 2 and {max_tags} tags that best capture the theological, redemptive-historical, and thematic heart of this passage.
2. {new_tag_directive}
3. Category must be one of: {valid_categories_str}.
4. Tag names must be formatted in strict lowercase snake_case (e.g. "holy_spirit", "sovereign_grace", "justification", "prayer").
5. Designate exactly one primary tag as `"starred": true` (the core theological motif of this passage). All other tags must have `"starred": false`.
6. Provide a confidence score (between 0.0 and 1.0) indicating how explicitly and prominently the theme is expressed in the text.
7. Provide concise `"notes"` (1-2 sentences) detailing the theological rationale and citing specific phrases from the passage.
8. If a tag specifically applies to a sub-range within the passage (e.g. verses 1-2 within a multi-verse span), provide the citation in `"sub_span"`; otherwise, set `"sub_span": null`.

## Required Output Format
Respond ONLY with valid JSON conforming strictly to this JSON schema:
```json
{{
  "reference": "{human_ref}",
  "tags": [
    {{
      "name": "tag_name_in_snake_case",
      "category": "theological",
      "confidence": 0.95,
      "starred": true,
      "notes": "Theological rationale referencing specific words or redemptive significance.",
      "sub_span": null
    }}
  ]
}}
```
Do not include any conversational text, preamble, or markdown outside the JSON block.
"""
    return prompt.strip()


def generate_batch_tagging_prompts(
    passages: Sequence[Tuple[Union[Reference, str], str]],
    categories: Optional[Sequence[str]] = None,
    custom_tags: Optional[Sequence[Union[str, Tuple[str, str, str]]]] = None,
    allow_new_tags: bool = True,
    max_tags: int = 6,
    translation_id: str = "WEB",
) -> List[Dict[str, Any]]:
    """Generate structured batch prompt payloads for multiple passages (suitable for JSONL export).

    Args:
        passages: Sequence of `(reference, text)` pairs.
        categories: Optional category filter.
        custom_tags: Optional custom candidate tags.
        allow_new_tags: Whether to permit novel tags.
        max_tags: Maximum tags per passage.
        translation_id: Translation identifier.

    Returns:
        List of dictionaries with `id`, `reference`, `prompt`, and `system_prompt`.
    """
    sys_prompt = get_tgc_hermeneutical_system_prompt()
    batch_items: List[Dict[str, Any]] = []

    for idx, (ref, text) in enumerate(passages, start=1):
        ref_obj = parse_reference(ref) if isinstance(ref, str) else ref
        user_prompt = generate_tagging_prompt(
            reference=ref_obj,
            passage_text=text,
            categories=categories,
            custom_tags=custom_tags,
            allow_new_tags=allow_new_tags,
            max_tags=max_tags,
            translation_id=translation_id,
        )
        batch_items.append(
            {
                "id": f"tag_request_{idx:04d}",
                "reference": ref_obj.format(),
                "system_prompt": sys_prompt,
                "prompt": user_prompt,
            }
        )

    return batch_items


# ==============================================================================
# Response Parsing & Normalization
# ==============================================================================


def extract_json_payload(raw_text: str) -> str:
    """Extract raw JSON text from an LLM response string.

    Handles markdown code blocks (```json ... ``` or ``` ... ```), leading/trailing
    chatter, and raw JSON strings.
    """
    text = raw_text.strip()

    # Match ```json ... ``` or ``` ... ``` code blocks
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if code_block_match:
        return code_block_match.group(1).strip()

    # Match the outermost JSON object { ... } or array [ ... ]
    start_brace = text.find("{")
    start_bracket = text.find("[")

    if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
        end_brace = text.rfind("}")
        if end_brace != -1 and end_brace > start_brace:
            return text[start_brace : end_brace + 1].strip()
    elif start_bracket != -1:
        end_bracket = text.rfind("]")
        if end_bracket != -1 and end_bracket > start_bracket:
            return text[start_bracket : end_bracket + 1].strip()

    return text


def normalize_tag_name(name: str) -> str:
    """Clean and normalize a tag name string to strict canonical lowercase snake_case."""
    from core.tags import normalize_tag_name as _norm
    return _norm(name)


def normalize_category(category: str) -> str:
    """Normalize and validate a tag category string."""
    cat_norm = category.strip().lower()
    if TagCategory.is_valid(cat_norm):
        return cat_norm
    # Heuristic mapping for common LLM variations
    if "theolog" in cat_norm or "doctrin" in cat_norm:
        return TagCategory.THEOLOGICAL
    if "hist" in cat_norm or "narrative" in cat_norm or "story" in cat_norm:
        return TagCategory.HISTORICAL
    if "prophe" in cat_norm or "eschat" in cat_norm:
        return TagCategory.PROPHECY
    if "typo" in cat_norm or "shadow" in cat_norm or "figure" in cat_norm:
        return TagCategory.TYPOLOGY
    if "liturg" in cat_norm or "worship" in cat_norm or "psalm" in cat_norm:
        return TagCategory.LITURGICAL
    if "curat" in cat_norm or "fav" in cat_norm:
        return TagCategory.CURATION
    return TagCategory.THEMATIC


def parse_tagging_response(
    response_text: str,
    default_reference: Optional[Union[Reference, str]] = None,
    model: Optional[str] = None,
) -> TaggingResult:
    """Parse, validate, and normalize an LLM response containing semantic tags.

    Args:
        response_text: Raw response string from the LLM.
        default_reference: Fallback reference if JSON does not specify one.
        model: Optional LLM model identifier.

    Returns:
        TaggingResult object containing validated GeneratedTag instances.
    """
    ref_str = ""
    if default_reference:
        ref_obj = (
            parse_reference(default_reference)
            if isinstance(default_reference, str)
            else default_reference
        )
        ref_str = ref_obj.format()

    json_str = extract_json_payload(response_text)
    if not json_str:
        return TaggingResult(
            reference=ref_str,
            raw_response=response_text,
            model=model,
            error="Empty or unextractable response content",
        )

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        return TaggingResult(
            reference=ref_str,
            raw_response=response_text,
            model=model,
            error=f"Invalid JSON format: {exc}",
        )

    # Extract reference and tag list
    parsed_ref = ref_str
    tag_items: List[Dict[str, Any]] = []

    if isinstance(data, dict):
        if "reference" in data and data["reference"]:
            try:
                parsed_ref = parse_reference(str(data["reference"])).format()
            except Exception:
                parsed_ref = str(data["reference"]).strip()
        if "tags" in data and isinstance(data["tags"], list):
            tag_items = data["tags"]
        else:
            # Maybe the dict is a single tag
            if "name" in data:
                tag_items = [data]
    elif isinstance(data, list):
        tag_items = data
    else:
        return TaggingResult(
            reference=parsed_ref,
            raw_response=response_text,
            model=model,
            error=f"Unexpected JSON root type: {type(data).__name__}",
        )

    # Validate and normalize each tag
    valid_tags: List[GeneratedTag] = []
    seen_names: Set[str] = set()
    has_starred = False

    for item in tag_items:
        if not isinstance(item, dict) or "name" not in item:
            continue

        raw_name = str(item.get("name", "")).strip()
        if not raw_name:
            continue

        name = normalize_tag_name(raw_name)
        if name.lower() in seen_names:
            continue
        seen_names.add(name.lower())

        cat = normalize_category(str(item.get("category", TagCategory.THEMATIC)))

        # Confidence clamping
        try:
            raw_conf = float(item.get("confidence", 1.0))
            confidence = max(0.0, min(1.0, raw_conf))
        except (ValueError, TypeError):
            confidence = 1.0

        # Starred handling
        starred = bool(item.get("starred", False))
        if starred:
            has_starred = True

        # Notes
        notes = item.get("notes")
        notes_str = str(notes).strip() if notes is not None else None
        if notes_str == "":
            notes_str = None

        # Sub-span validation
        sub_span = item.get("sub_span")
        sub_span_str = None
        if sub_span:
            try:
                sub_ref = parse_reference(str(sub_span))
                sub_span_str = sub_ref.format()
            except Exception:
                sub_span_str = str(sub_span).strip()

        valid_tags.append(
            GeneratedTag(
                name=name,
                category=cat,
                confidence=confidence,
                starred=starred,
                notes=notes_str,
                sub_span=sub_span_str,
            )
        )

    # Ensure at least one tag is starred if tags exist
    if valid_tags and not has_starred:
        # Star the highest-confidence tag
        highest = max(valid_tags, key=lambda t: t.confidence)
        valid_tags = [
            GeneratedTag(
                name=t.name,
                category=t.category,
                confidence=t.confidence,
                starred=(t == highest),
                notes=t.notes,
                sub_span=t.sub_span,
            )
            for t in valid_tags
        ]

    return TaggingResult(
        reference=parsed_ref,
        tags=valid_tags,
        raw_response=response_text,
        model=model,
        error=None if valid_tags else "No valid tags found in JSON payload",
    )


def format_prompt_for_gemini_api(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """Format prompt payload for the Google Gemini REST API (`generateContent`).

    Args:
        prompt: The main user prompt text.
        system_prompt: Optional system instructions (defaults to TGC hermeneutical prompt).
        temperature: Sampling temperature (low for deterministic classification).

    Returns:
        Dictionary ready for JSON serialization and HTTP POST.
    """
    sys_instruction = system_prompt or get_tgc_hermeneutical_system_prompt()
    return {
        "system_instruction": {
            "parts": [{"text": sys_instruction}]
        },
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": temperature,
        },
    }
