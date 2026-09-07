"""Batch Visual Verse Slide Exporter & Screensaver Album Generator.

Zero-dependency implementation (Python 3 standard library only per ADR-003):
- High-performance batch export of 4K UHD and 1080p landscape scripture slides for
  Google Photos, Apple Photos, Chromecast, and smart TV screensaver displays.
- Flexible passage source resolution:
  * User favorites (--favorites, --starred-only from favorite_bible_verses.csv / DB).
  * Semantic tags (--tag <name>).
  * Canonical book pericopes or chapters (--book <name>).
  * Curated reading plans (--plan <name> from core/plans.py).
  * Explicit citation lists or text files.
- High-concurrency parallel rendering via concurrent.futures.ProcessPoolExecutor.
- Structured album packaging:
  * Zero-padded sequential filenames (e.g. 001_john_3_16.png).
  * Multi-slide pagination handling for long passages (001_romans_8_28_p1.png).
  * manifest.json: Complete structured album metadata and slide inventory.
  * index.html: Offline Sacred-Modern dark-themed visual gallery with slideshow modal.
  * index.txt: Simple plaintext index for media players and scripts.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
import datetime
import html
import json
import os
from pathlib import Path
import random
import re
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from core.db import Database, VerseRecord
from core.pericopes import PericopeService
from core.plans import ReadingPlan, get_plan
from core.reference import Book, Reference, get_book, parse_reference
from core.render import (
    PaginationConfig,
    RenderConfig,
    RenderError,
    RenderResult,
    SlideContent,
    SlideRenderEngine,
    SlideTheme,
    get_default_engine,
    get_theme,
    paginate_verses,
    parse_resolution,
)
from core.tags import TaggingService

DEFAULT_CSV_PATH = Path(__file__).resolve().parent.parent / "favorite_bible_verses.csv"


# ==============================================================================
# Data Models
# ==============================================================================


@dataclass
class BatchPassageItem:
    """Represents a resolved scripture passage ready for batch slide rendering."""

    reference: Reference
    citation: str
    verses: List[VerseRecord]
    text: str
    translation: str
    pericope_title: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    starred: bool = False
    source_info: str = ""


@dataclass
class BatchSlideItem:
    """Metadata for an individual rendered slide within an exported album."""

    index: int
    passage_index: int
    reference_str: str
    citation: str
    text_excerpt: str
    page_num: int
    total_pages: int
    filename: str
    file_path: Path
    file_size_bytes: int
    width: int
    height: int
    format: str
    backend: str
    theme_name: str
    pericope_title: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    starred: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize slide metadata for manifest.json."""
        return {
            "index": self.index,
            "passage_index": self.passage_index,
            "reference": self.reference_str,
            "citation": self.citation,
            "text_excerpt": self.text_excerpt,
            "page": self.page_num,
            "total_pages": self.total_pages,
            "filename": self.filename,
            "relative_path": self.filename,
            "file_size_bytes": self.file_size_bytes,
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "backend": self.backend,
            "theme": self.theme_name,
            "pericope_title": self.pericope_title,
            "tags": self.tags,
            "starred": self.starred,
        }


@dataclass
class BatchExportConfig:
    """Configuration options for batch slide export."""

    destination_dir: Path
    render_config: RenderConfig = field(default_factory=RenderConfig)
    pagination_config: PaginationConfig = field(default_factory=PaginationConfig)
    album_title: str = "Scripture Screensaver Album"
    album_description: str = ""
    source_type: str = "custom"
    source_query: str = ""
    max_workers: int = 4
    sequential: bool = False
    shuffle: bool = False
    seed: Optional[int] = None
    limit: Optional[int] = None
    offset: int = 0
    generate_gallery: bool = True
    generate_manifest: bool = True
    generate_index_txt: bool = True
    prefix_zero_padding: int = 3
    quiet: bool = False
    progress_callback: Optional[Callable[[int, int, str], None]] = None


@dataclass
class BatchExportResult:
    """Outcome and summary metrics of a batch slide export."""

    destination_dir: Path
    album_title: str
    total_passages: int
    total_slides: int
    total_bytes: int
    duration_seconds: float
    items: List[BatchSlideItem] = field(default_factory=list)
    manifest_path: Optional[Path] = None
    gallery_path: Optional[Path] = None
    index_txt_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result for JSON export."""
        return {
            "album_title": self.album_title,
            "destination_dir": str(self.destination_dir),
            "total_passages": self.total_passages,
            "total_slides": self.total_slides,
            "total_bytes": self.total_bytes,
            "duration_seconds": round(self.duration_seconds, 3),
            "manifest_file": str(self.manifest_path) if self.manifest_path else None,
            "gallery_file": str(self.gallery_path) if self.gallery_path else None,
            "index_txt_file": str(self.index_txt_path) if self.index_txt_path else None,
            "slides": [item.to_dict() for item in self.items],
        }


# ==============================================================================
# Multiprocessing Worker
# ==============================================================================


def _render_batch_slide_worker(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Top-level picklable worker function for parallel process execution."""
    out_path = Path(payload["output_path"])
    content_dict = payload["content"]
    cfg_dict = payload["config"]
    meta = payload["metadata"]

    raw_font_size = cfg_dict.get("font_size")
    if isinstance(raw_font_size, str):
        if raw_font_size.strip().lower() in ("auto", "none", "fit", "default", ""):
            font_size = None
        else:
            try:
                font_size = float(raw_font_size.replace("pt", "").strip())
            except ValueError:
                font_size = None
    else:
        font_size = raw_font_size

    theme = get_theme(cfg_dict.get("theme", "oled_black"))
    config = RenderConfig(
        width=cfg_dict.get("width", 3840),
        height=cfg_dict.get("height", 2160),
        theme=theme,
        safe_area_pct=cfg_dict.get("safe_area_pct", 0.15),
        font_family=cfg_dict.get("font_family"),
        font_size=font_size,
        line_spacing=cfg_dict.get("line_spacing", 1.5),
        text_align=cfg_dict.get("text_align", "center"),
        citation_style=cfg_dict.get("citation_style", "below"),
        citation_color=cfg_dict.get("citation_color"),
        accent_color=cfg_dict.get("accent_color"),
        optical_center_pct=cfg_dict.get("optical_center_pct", 0.45),
        balance_lines=cfg_dict.get("balance_lines", True),
        show_accent_rule=cfg_dict.get("show_accent_rule", True),
        show_tags=cfg_dict.get("show_tags", False),
        backend=cfg_dict.get("backend", "auto"),
        output_format=cfg_dict.get("output_format", "png"),
        jpeg_quality=cfg_dict.get("jpeg_quality", 95),
        dpi=cfg_dict.get("dpi", 300),
    )

    content = SlideContent(
        text=content_dict["text"],
        citation=content_dict.get("citation", ""),
        translation=content_dict.get("translation", "WEB"),
        pericope_title=content_dict.get("pericope_title"),
        page_indicator=content_dict.get("page_indicator"),
        tags=content_dict.get("tags", []),
    )

    engine = get_default_engine()
    try:
        res = engine.render_to_file(content, out_path, config=config)
        size = out_path.stat().st_size if out_path.exists() else len(res.data)
        return {
            "success": True,
            "output_path": str(out_path),
            "file_size": size,
            "width": res.width,
            "height": res.height,
            "format": res.format,
            "backend": res.backend,
            "metadata": meta,
        }
    except Exception as exc:
        return {
            "success": False,
            "output_path": str(out_path),
            "error": str(exc),
            "metadata": meta,
        }


# ==============================================================================
# Slide Batch Exporter Engine
# ==============================================================================


class SlideBatchExporter:
    """Engine for resolving scripture passages and generating batch screensaver albums."""

    def __init__(self, db: Optional[Database] = None) -> None:
        """Initialize exporter with optional Database connection."""
        self._db = db

    def _get_db(self) -> Database:
        """Return initialized Database connection."""
        if self._db is None:
            self._db = Database()
        return self._db

    def resolve_passages(
        self,
        favorites: bool = False,
        starred_only: bool = False,
        tag: Optional[str] = None,
        book: Optional[str] = None,
        plan: Optional[str] = None,
        references: Optional[Sequence[Union[str, Reference]]] = None,
        file_path: Optional[Union[str, Path]] = None,
        csv_path: Optional[Union[str, Path]] = None,
        translation_id: str = "WEB",
        limit: Optional[int] = None,
        offset: int = 0,
        shuffle: bool = False,
        seed: Optional[int] = None,
    ) -> List[BatchPassageItem]:
        """Resolve a collection of passages from specified criteria.

        Args:
            favorites: If True, resolve from user curated favorites.
            starred_only: If True, only include starred/prioritized passages.
            tag: Semantic tag name (e.g. 'Covenant', 'Grace').
            book: Canonical book name (e.g. 'Romans', 'James').
            plan: Curated reading plan name (e.g. 'psalms_of_ascent', 'sermon').
            references: Explicit list of reference strings or Reference objects.
            file_path: Path to text file containing one reference per line.
            csv_path: Optional override path for favorite_bible_verses.csv.
            translation_id: Bible translation ID for verse text hydration (default 'WEB').
            limit: Maximum passages to return.
            offset: Number of passages to skip.
            shuffle: Whether to randomize passage order.
            seed: Optional random seed for reproducible shuffling.

        Returns:
            List of hydrated BatchPassageItem records.
        """
        db = self._get_db()
        pericope_svc = PericopeService(db)
        tagging_svc = TaggingService(db)

        items: List[BatchPassageItem] = []

        if favorites:
            items = self._resolve_favorites(
                db,
                starred_only=starred_only,
                csv_path=csv_path or DEFAULT_CSV_PATH,
                translation_id=translation_id,
            )
        elif tag:
            items = self._resolve_tag(
                db,
                tag_name=tag,
                starred_only=starred_only,
                translation_id=translation_id,
            )
        elif book:
            items = self._resolve_book(
                db,
                pericope_svc=pericope_svc,
                book_name=book,
                translation_id=translation_id,
            )
        elif plan:
            items = self._resolve_plan(
                db,
                plan_name=plan,
                translation_id=translation_id,
            )
        elif file_path:
            items = self._resolve_file(
                db,
                file_path=Path(file_path),
                translation_id=translation_id,
            )
        elif references:
            items = self._resolve_references(
                db,
                references=references,
                translation_id=translation_id,
            )

        # Enrich pericope titles and tags if missing
        for item in items:
            if not item.pericope_title:
                overlaps = pericope_svc.get_pericopes_for_passage(item.reference)
                if overlaps:
                    item.pericope_title = overlaps[0].title
            if not item.tags:
                active_tags = tagging_svc.get_tags_for_passage(item.reference)
                item.tags = [t.tag_name for t in active_tags if t.tag_name]

        # Apply shuffle if requested
        if shuffle:
            rng = random.Random(seed)
            rng.shuffle(items)

        # Apply offset and limit
        if offset > 0:
            items = items[offset:]
        if limit is not None:
            items = items[:limit]

        return items

    def _resolve_favorites(
        self,
        db: Database,
        starred_only: bool,
        csv_path: Path,
        translation_id: str,
    ) -> List[BatchPassageItem]:
        """Resolve passages from favorites tag in DB, or fallback to CSV."""
        db_records = db.get_references_for_tag("favorites", starred_only=starred_only)
        items: List[BatchPassageItem] = []

        if db_records:
            for r in db_records:
                ref = parse_reference(r.human_ref)
                if ref is None:
                    continue
                verses, used_id, _ = db.get_verses_with_fallback(ref, translation_id=translation_id)
                if not verses:
                    continue
                text = " ".join(v.text.strip() for v in verses)
                items.append(
                    BatchPassageItem(
                        reference=ref,
                        citation=ref.format(),
                        verses=verses,
                        text=text,
                        translation=used_id,
                        starred=bool(r.starred),
                        source_info="Curated Favorites (DB)",
                    )
                )
            return items

        # Fallback to favorite_bible_verses.csv if DB tag was not seeded
        if csv_path.exists():
            import csv
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    starred_val = str(row.get("starred", "")).strip().lower() in ("true", "1", "yes")
                    if starred_only and not starred_val:
                        continue
                    try:
                        ref = Reference.from_csv_row(row)
                    except Exception:
                        continue
                    verses, used_id, _ = db.get_verses_with_fallback(ref, translation_id=translation_id)
                    if not verses:
                        continue
                    text = " ".join(v.text.strip() for v in verses)
                    items.append(
                        BatchPassageItem(
                            reference=ref,
                            citation=ref.format(),
                            verses=verses,
                            text=text,
                            translation=used_id,
                            starred=starred_val,
                            source_info="Curated Favorites (CSV)",
                        )
                    )

        return items

    def _resolve_tag(
        self,
        db: Database,
        tag_name: str,
        starred_only: bool,
        translation_id: str,
    ) -> List[BatchPassageItem]:
        """Resolve passages matching a semantic tag."""
        records = db.get_references_for_tag(tag_name, starred_only=starred_only)
        items: List[BatchPassageItem] = []
        for r in records:
            ref = parse_reference(r.human_ref)
            if ref is None:
                continue
            verses, used_id, _ = db.get_verses_with_fallback(ref, translation_id=translation_id)
            if not verses:
                continue
            text = " ".join(v.text.strip() for v in verses)
            items.append(
                BatchPassageItem(
                    reference=ref,
                    citation=ref.format(),
                    verses=verses,
                    text=text,
                    translation=used_id,
                    starred=bool(r.starred),
                    tags=[tag_name],
                    source_info=f"Tag: {tag_name}",
                )
            )
        return items

    def _resolve_book(
        self,
        db: Database,
        pericope_svc: PericopeService,
        book_name: str,
        translation_id: str,
    ) -> List[BatchPassageItem]:
        """Resolve all pericopes or chapter segments for a book."""
        b = get_book(book_name)
        if b is None:
            return []

        pericopes = pericope_svc.get_pericopes_for_book(b)
        items: List[BatchPassageItem] = []

        if pericopes:
            for p in pericopes:
                ref = parse_reference(p.human_ref)
                if ref is None:
                    continue
                verses, used_id, _ = db.get_verses_with_fallback(ref, translation_id=translation_id)
                if not verses:
                    continue
                text = " ".join(v.text.strip() for v in verses)
                items.append(
                    BatchPassageItem(
                        reference=ref,
                        citation=ref.format(),
                        verses=verses,
                        text=text,
                        translation=used_id,
                        pericope_title=p.title,
                        source_info=f"Book: {b.name}",
                    )
                )
        else:
            # Fallback to chapters if no pericopes registered
            for ch in range(1, b.total_chapters + 1):
                ref = Reference(b, ch)
                verses, used_id, _ = db.get_verses_with_fallback(ref, translation_id=translation_id)
                if not verses:
                    continue
                text = " ".join(v.text.strip() for v in verses)
                items.append(
                    BatchPassageItem(
                        reference=ref,
                        citation=ref.format(),
                        verses=verses,
                        text=text,
                        translation=used_id,
                        source_info=f"Book: {b.name}",
                    )
                )

        return items

    def _resolve_plan(
        self,
        db: Database,
        plan_name: str,
        translation_id: str,
    ) -> List[BatchPassageItem]:
        """Resolve passages defined in a curated reading plan."""
        plan_obj = get_plan(plan_name)
        if plan_obj is None:
            return []

        items: List[BatchPassageItem] = []
        for cit in plan_obj.passages:
            ref = parse_reference(cit)
            if ref is None:
                continue
            verses, used_id, _ = db.get_verses_with_fallback(ref, translation_id=translation_id)
            if not verses:
                continue
            text = " ".join(v.text.strip() for v in verses)
            items.append(
                BatchPassageItem(
                    reference=ref,
                    citation=ref.format(),
                    verses=verses,
                    text=text,
                    translation=used_id,
                    tags=list(plan_obj.tags),
                    source_info=f"Plan: {plan_obj.title}",
                )
            )
        return items

    def _resolve_file(
        self,
        db: Database,
        file_path: Path,
        translation_id: str,
    ) -> List[BatchPassageItem]:
        """Resolve passages listed line-by-line in a text file."""
        if not file_path.exists():
            return []

        items: List[BatchPassageItem] = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                ref = parse_reference(stripped)
                if ref is None:
                    continue
                verses, used_id, _ = db.get_verses_with_fallback(ref, translation_id=translation_id)
                if not verses:
                    continue
                text = " ".join(v.text.strip() for v in verses)
                items.append(
                    BatchPassageItem(
                        reference=ref,
                        citation=ref.format(),
                        verses=verses,
                        text=text,
                        translation=used_id,
                        source_info=f"File: {file_path.name}",
                    )
                )
        return items

    def _resolve_references(
        self,
        db: Database,
        references: Sequence[Union[str, Reference]],
        translation_id: str,
    ) -> List[BatchPassageItem]:
        """Resolve an explicit list of scripture references."""
        items: List[BatchPassageItem] = []
        for item in references:
            ref = parse_reference(item) if isinstance(item, str) else item
            if ref is None:
                continue
            verses, used_id, _ = db.get_verses_with_fallback(ref, translation_id=translation_id)
            if not verses:
                continue
            text = " ".join(v.text.strip() for v in verses)
            items.append(
                BatchPassageItem(
                    reference=ref,
                    citation=ref.format(),
                    verses=verses,
                    text=text,
                    translation=used_id,
                    source_info="Custom References",
                )
            )
        return items

    def export_batch(
        self,
        config: BatchExportConfig,
        passages: Optional[Sequence[BatchPassageItem]] = None,
    ) -> BatchExportResult:
        """Execute batch slide rendering and album compilation.

        Args:
            config: BatchExportConfig containing destination, themes, and execution flags.
            passages: Optional pre-resolved passage items. If None, resolved via config criteria.

        Returns:
            BatchExportResult containing all rendered slide items and manifest paths.
        """
        start_time = time.perf_counter()
        dest_dir = config.destination_dir.resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Resolve passages if not provided
        if passages is None:
            passages = self.resolve_passages(
                favorites=(config.source_type == "favorites"),
                tag=config.source_query if config.source_type == "tag" else None,
                book=config.source_query if config.source_type == "book" else None,
                plan=config.source_query if config.source_type == "plan" else None,
                limit=config.limit,
                offset=config.offset,
                shuffle=config.shuffle,
                seed=config.seed,
            )

        render_cfg = config.render_config
        pag_cfg = config.pagination_config
        theme = render_cfg.theme
        theme_name = theme.name if isinstance(theme, SlideTheme) else str(theme)
        out_ext = render_cfg.output_format.lower()
        pad = max(3, config.prefix_zero_padding)

        # Pre-paginate and prepare tasks
        tasks: List[Dict[str, Any]] = []
        slide_metadata_list: List[Dict[str, Any]] = []
        slide_counter = 1

        for p_idx, passage in enumerate(passages, start=1):
            if pag_cfg.enabled:
                slides = paginate_verses(
                    verses=passage.verses,
                    parent_ref=passage.reference,
                    config=render_cfg,
                    pagination=pag_cfg,
                    pericope_title=passage.pericope_title,
                    tags=passage.tags,
                )
            else:
                slides = [
                    SlideContent(
                        text=passage.text,
                        citation=passage.citation,
                        translation=passage.translation,
                        pericope_title=passage.pericope_title,
                        tags=passage.tags,
                    )
                ]

            total_pages = len(slides)
            safe_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", passage.citation).strip("_").lower()

            for page_num, slide_content in enumerate(slides, start=1):
                if total_pages > 1:
                    filename = f"{slide_counter:0{pad}d}_{safe_slug}_p{page_num}.{out_ext}"
                else:
                    filename = f"{slide_counter:0{pad}d}_{safe_slug}.{out_ext}"

                out_file = dest_dir / filename
                text_snip = slide_content.text.strip()
                if len(text_snip) > 120:
                    text_snip = text_snip[:117] + "..."

                meta = {
                    "index": slide_counter,
                    "passage_index": p_idx,
                    "reference_str": passage.reference.format(),
                    "citation": slide_content.citation or passage.citation,
                    "text_excerpt": text_snip,
                    "page_num": page_num,
                    "total_pages": total_pages,
                    "filename": filename,
                    "file_path": out_file,
                    "theme_name": theme_name,
                    "pericope_title": slide_content.pericope_title,
                    "tags": list(slide_content.tags or []),
                    "starred": passage.starred,
                }
                slide_metadata_list.append(meta)

                # Build worker payload
                payload = {
                    "output_path": str(out_file),
                    "content": {
                        "text": slide_content.text,
                        "citation": slide_content.citation,
                        "translation": slide_content.translation,
                        "pericope_title": slide_content.pericope_title,
                        "page_indicator": slide_content.page_indicator,
                        "tags": slide_content.tags,
                    },
                    "config": {
                        "width": render_cfg.width,
                        "height": render_cfg.height,
                        "theme": theme_name,
                        "safe_area_pct": render_cfg.safe_area_pct,
                        "font_family": render_cfg.font_family,
                        "font_size": render_cfg.font_size,
                        "line_spacing": render_cfg.line_spacing,
                        "text_align": render_cfg.text_align,
                        "citation_style": render_cfg.citation_style,
                        "citation_color": render_cfg.citation_color,
                        "accent_color": render_cfg.accent_color,
                        "optical_center_pct": render_cfg.optical_center_pct,
                        "balance_lines": render_cfg.balance_lines,
                        "show_accent_rule": render_cfg.show_accent_rule,
                        "show_tags": render_cfg.show_tags,
                        "backend": render_cfg.backend,
                        "output_format": render_cfg.output_format,
                        "jpeg_quality": render_cfg.jpeg_quality,
                        "dpi": render_cfg.dpi,
                    },
                    "metadata": meta,
                }
                tasks.append(payload)
                slide_counter += 1

        total_slides = len(tasks)
        rendered_items: List[BatchSlideItem] = []
        total_bytes = 0

        # Execute rendering: parallel multiprocessing or sequential
        if config.sequential or config.max_workers <= 1 or total_slides <= 1:
            for idx, task in enumerate(tasks, start=1):
                res_dict = _render_batch_slide_worker(task)
                meta = res_dict["metadata"]
                if res_dict.get("success", False):
                    item = BatchSlideItem(
                        index=meta["index"],
                        passage_index=meta["passage_index"],
                        reference_str=meta["reference_str"],
                        citation=meta["citation"],
                        text_excerpt=meta["text_excerpt"],
                        page_num=meta["page_num"],
                        total_pages=meta["total_pages"],
                        filename=meta["filename"],
                        file_path=Path(res_dict["output_path"]),
                        file_size_bytes=res_dict["file_size"],
                        width=res_dict["width"],
                        height=res_dict["height"],
                        format=res_dict["format"],
                        backend=res_dict["backend"],
                        theme_name=meta["theme_name"],
                        pericope_title=meta["pericope_title"],
                        tags=meta["tags"],
                        starred=meta["starred"],
                    )
                    rendered_items.append(item)
                    total_bytes += item.file_size_bytes

                if not config.quiet and not config.progress_callback:
                    _print_cli_progress(idx, total_slides, meta["citation"])
                elif config.progress_callback:
                    config.progress_callback(idx, total_slides, meta["citation"])
        else:
            workers = min(config.max_workers, total_slides, os.cpu_count() or 4)
            with ProcessPoolExecutor(max_workers=workers) as executor:
                future_to_task = {
                    executor.submit(_render_batch_slide_worker, t): t for t in tasks
                }
                completed_count = 0
                for future in as_completed(future_to_task):
                    completed_count += 1
                    res_dict = future.result()
                    meta = res_dict["metadata"]
                    if res_dict.get("success", False):
                        item = BatchSlideItem(
                            index=meta["index"],
                            passage_index=meta["passage_index"],
                            reference_str=meta["reference_str"],
                            citation=meta["citation"],
                            text_excerpt=meta["text_excerpt"],
                            page_num=meta["page_num"],
                            total_pages=meta["total_pages"],
                            filename=meta["filename"],
                            file_path=Path(res_dict["output_path"]),
                            file_size_bytes=res_dict["file_size"],
                            width=res_dict["width"],
                            height=res_dict["height"],
                            format=res_dict["format"],
                            backend=res_dict["backend"],
                            theme_name=meta["theme_name"],
                            pericope_title=meta["pericope_title"],
                            tags=meta["tags"],
                            starred=meta["starred"],
                        )
                        rendered_items.append(item)
                        total_bytes += item.file_size_bytes

                    if not config.quiet and not config.progress_callback:
                        _print_cli_progress(completed_count, total_slides, meta["citation"])
                    elif config.progress_callback:
                        config.progress_callback(completed_count, total_slides, meta["citation"])

        # Sort rendered items cleanly by original index
        rendered_items.sort(key=lambda x: x.index)
        duration = time.perf_counter() - start_time

        # Generate manifest.json
        manifest_path = None
        if config.generate_manifest:
            manifest_path = dest_dir / "manifest.json"
            manifest_data = {
                "album_title": config.album_title,
                "album_description": config.album_description,
                "source_type": config.source_type,
                "source_query": config.source_query,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "total_passages": len(passages),
                "total_slides": len(rendered_items),
                "total_bytes": total_bytes,
                "resolution": f"{render_cfg.width}x{render_cfg.height}",
                "theme": theme_name,
                "format": render_cfg.output_format,
                "duration_seconds": round(duration, 3),
                "slides": [it.to_dict() for it in rendered_items],
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2)

        # Generate index.txt
        index_txt_path = None
        if config.generate_index_txt:
            index_txt_path = dest_dir / "index.txt"
            with open(index_txt_path, "w", encoding="utf-8") as f:
                f.write(f"# {config.album_title}\n")
                f.write(f"# Exported: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Resolution: {render_cfg.width}x{render_cfg.height} | Theme: {theme_name}\n\n")
                for it in rendered_items:
                    f.write(f"{it.filename}\t{it.citation}\t({it.width}x{it.height})\n")

        # Generate index.html (Sacred-Modern visual TV gallery)
        gallery_path = None
        if config.generate_gallery:
            gallery_path = dest_dir / "index.html"
            html_content = generate_html_gallery(
                title=config.album_title,
                description=config.album_description,
                slides=rendered_items,
                render_cfg=render_cfg,
                theme_name=theme_name,
            )
            with open(gallery_path, "w", encoding="utf-8") as f:
                f.write(html_content)

        return BatchExportResult(
            destination_dir=dest_dir,
            album_title=config.album_title,
            total_passages=len(passages),
            total_slides=len(rendered_items),
            total_bytes=total_bytes,
            duration_seconds=duration,
            items=rendered_items,
            manifest_path=manifest_path,
            gallery_path=gallery_path,
            index_txt_path=index_txt_path,
        )


def _print_cli_progress(current: int, total: int, citation: str) -> None:
    """Print terminal progress bar with ANSI styling."""
    bar_width = 24
    pct = (current / total) if total > 0 else 1.0
    filled = int(round(bar_width * pct))
    bar = "█" * filled + "░" * (bar_width - filled)
    cit_disp = citation[:28]
    sys.stderr.write(
        f"\r\033[K[\033[38;2;212;175;55m{bar}\033[0m] {int(pct * 100):>3}% "
        f"({current}/{total}) \033[36m{cit_disp:<28}\033[0m"
    )
    sys.stderr.flush()
    if current >= total:
        sys.stderr.write("\n")


# ==============================================================================
# Sacred-Modern Visual TV Gallery Generator (index.html)
# ==============================================================================


def generate_html_gallery(
    title: str,
    description: str,
    slides: List[BatchSlideItem],
    render_cfg: RenderConfig,
    theme_name: str,
) -> str:
    """Generate a standalone, zero-dependency Sacred-Modern dark gallery HTML page."""
    escaped_title = html.escape(title)
    escaped_desc = html.escape(description)
    total_slides = len(slides)
    res_label = f"{render_cfg.width}x{render_cfg.height}"

    cards_html: List[str] = []
    for s in slides:
        cit_esc = html.escape(s.citation)
        peri_html = (
            f'<div class="card-pericope">{html.escape(s.pericope_title)}</div>'
            if s.pericope_title
            else ""
        )
        tags_html = "".join(
            f'<span class="tag-pill">{html.escape(t)}</span>' for t in s.tags[:3]
        )
        snip_esc = html.escape(s.text_excerpt)
        page_badge = (
            f'<span class="page-badge">{s.page_num}/{s.total_pages}</span>'
            if s.total_pages > 1
            else ""
        )
        starred_badge = '<span class="star-badge">★ Starred</span>' if s.starred else ""
        size_kb = f"{s.file_size_bytes / 1024:.1f} KB"

        cards_html.append(
            f"""
      <div class="slide-card" data-index="{s.index}" data-filename="{html.escape(s.filename)}" data-citation="{cit_esc}">
        <div class="card-media" onclick="openLightbox({s.index - 1})">
          <img src="{html.escape(s.filename)}" alt="{cit_esc}" loading="lazy" />
          <div class="media-overlay">
            <span class="overlay-zoom">⤢ View 4K</span>
          </div>
          {page_badge}
        </div>
        <div class="card-body">
          <div class="card-header">
            <span class="card-number">#{s.index:03d}</span>
            <div class="card-citation">{cit_esc}</div>
            {starred_badge}
          </div>
          {peri_html}
          <div class="card-text">"{snip_esc}"</div>
          <div class="card-footer">
            <div class="card-tags">{tags_html}</div>
            <div class="card-meta">
              <span>{size_kb}</span>
              <a href="{html.escape(s.filename)}" download class="download-btn" title="Download Slide">⬇</a>
            </div>
          </div>
        </div>
      </div>
"""
        )

    slides_json_array = json.dumps([s.to_dict() for s in slides])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{escaped_title} — Visual Verse TV Gallery</title>
  <style>
    :root {{
      --bg-base: #0D0E11;
      --bg-surface: #161922;
      --bg-card: #1C202B;
      --border-color: #272C3D;
      --border-focus: #D4AF37;
      --accent-gold: #D4AF37;
      --accent-gold-hover: #F0C43F;
      --accent-dim: #7A621E;
      --text-main: #F3F4F6;
      --text-muted: #9CA3AF;
      --text-dim: #6B7280;
      --radius: 10px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background-color: var(--bg-base);
      color: var(--text-main);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      line-height: 1.6;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    header {{
      background: linear-gradient(180deg, #161922 0%, #0D0E11 100%);
      border-bottom: 1px solid var(--border-color);
      padding: 2.5rem 2rem 1.75rem 2rem;
    }}
    .header-content {{
      max-width: 1400px;
      margin: 0 auto;
    }}
    .header-top {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: 1.5rem;
    }}
    .album-badge {{
      display: inline-block;
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--accent-gold);
      background: rgba(212, 175, 55, 0.12);
      border: 1px solid rgba(212, 175, 55, 0.3);
      padding: 0.25rem 0.75rem;
      border-radius: 999px;
      margin-bottom: 0.75rem;
    }}
    h1 {{
      font-family: Georgia, 'Liberation Serif', serif;
      font-size: 2.25rem;
      font-weight: normal;
      color: var(--text-main);
      letter-spacing: -0.02em;
      margin-bottom: 0.5rem;
    }}
    .description {{
      color: var(--text-muted);
      font-size: 1rem;
      max-width: 800px;
    }}
    .meta-badges {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      margin-top: 1.25rem;
    }}
    .meta-badge {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 6px;
      padding: 0.35rem 0.75rem;
      font-size: 0.82rem;
      color: var(--text-muted);
    }}
    .meta-badge strong {{
      color: var(--text-main);
      margin-left: 0.25rem;
    }}

    /* TV Screensaver Guide Collapsible */
    .tv-guide-wrapper {{
      margin-top: 1.5rem;
      background: rgba(212, 175, 55, 0.05);
      border: 1px solid rgba(212, 175, 55, 0.25);
      border-radius: var(--radius);
      overflow: hidden;
    }}
    .tv-guide-header {{
      padding: 0.85rem 1.25rem;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      align-items: center;
      user-select: none;
      font-weight: 600;
      color: var(--accent-gold);
    }}
    .tv-guide-body {{
      display: none;
      padding: 1.25rem;
      border-top: 1px solid rgba(212, 175, 55, 0.2);
      background: #111318;
      font-size: 0.9rem;
      color: var(--text-muted);
    }}
    .tv-guide-body.active {{ display: block; }}
    .tv-steps-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1.25rem;
      margin-top: 0.75rem;
    }}
    .tv-step-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 1rem;
    }}
    .tv-step-card h4 {{
      color: var(--accent-gold);
      font-size: 0.95rem;
      margin-bottom: 0.5rem;
    }}
    .tv-step-card ol {{
      padding-left: 1.2rem;
    }}
    .tv-step-card li {{
      margin-bottom: 0.35rem;
    }}

    /* Controls Bar */
    .controls-bar {{
      max-width: 1400px;
      margin: 1.5rem auto 0 auto;
      padding: 0 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      flex-wrap: wrap;
    }}
    .search-input {{
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 0.6rem 1rem;
      border-radius: 6px;
      font-size: 0.9rem;
      min-width: 280px;
      outline: none;
      transition: border-color 0.2s;
    }}
    .search-input:focus {{
      border-color: var(--border-focus);
    }}
    .slideshow-btn {{
      background: var(--accent-gold);
      color: #000;
      border: none;
      font-weight: 600;
      padding: 0.6rem 1.25rem;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      transition: background 0.2s;
    }}
    .slideshow-btn:hover {{
      background: var(--accent-gold-hover);
    }}

    /* Gallery Grid */
    main {{
      flex: 1;
      max-width: 1400px;
      width: 100%;
      margin: 1.5rem auto;
      padding: 0 2rem;
    }}
    .gallery-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
      gap: 1.75rem;
    }}
    .slide-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      overflow: hidden;
      display: flex;
      flex-direction: column;
      transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
    }}
    .slide-card:hover {{
      transform: translateY(-4px);
      border-color: var(--border-focus);
      box-shadow: 0 12px 30px rgba(0, 0, 0, 0.5);
    }}
    .card-media {{
      position: relative;
      aspect-ratio: 16 / 9;
      background: #000;
      overflow: hidden;
      cursor: pointer;
    }}
    .card-media img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
      transition: transform 0.3s ease;
    }}
    .slide-card:hover .card-media img {{
      transform: scale(1.02);
    }}
    .media-overlay {{
      position: absolute;
      inset: 0;
      background: rgba(0, 0, 0, 0.4);
      display: flex;
      align-items: center;
      justify-content: center;
      opacity: 0;
      transition: opacity 0.2s;
    }}
    .slide-card:hover .media-overlay {{
      opacity: 1;
    }}
    .overlay-zoom {{
      background: rgba(13, 14, 17, 0.85);
      color: var(--accent-gold);
      border: 1px solid var(--accent-gold);
      padding: 0.4rem 0.85rem;
      border-radius: 6px;
      font-size: 0.82rem;
      font-weight: 600;
    }}
    .page-badge {{
      position: absolute;
      top: 10px;
      right: 10px;
      background: rgba(0,0,0,0.75);
      border: 1px solid var(--border-color);
      color: #fff;
      font-size: 0.75rem;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
    }}
    .card-body {{
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      flex: 1;
    }}
    .card-header {{
      display: flex;
      align-items: baseline;
      gap: 0.5rem;
      margin-bottom: 0.25rem;
    }}
    .card-number {{
      font-size: 0.78rem;
      color: var(--text-dim);
      font-family: monospace;
    }}
    .card-citation {{
      font-family: Georgia, 'Liberation Serif', serif;
      font-size: 1.2rem;
      color: var(--accent-gold);
      flex: 1;
    }}
    .star-badge {{
      font-size: 0.72rem;
      color: #F59E0B;
      background: rgba(245, 158, 11, 0.12);
      border: 1px solid rgba(245, 158, 11, 0.3);
      padding: 0.1rem 0.4rem;
      border-radius: 4px;
    }}
    .card-pericope {{
      font-size: 0.85rem;
      color: var(--text-muted);
      font-style: italic;
      margin-bottom: 0.6rem;
    }}
    .card-text {{
      font-size: 0.88rem;
      color: #D1D5DB;
      margin-bottom: 1rem;
      flex: 1;
      font-family: Georgia, 'Liberation Serif', serif;
    }}
    .card-footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-top: 1px solid var(--border-color);
      padding-top: 0.75rem;
      margin-top: auto;
    }}
    .card-tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.35rem;
    }}
    .tag-pill {{
      font-size: 0.72rem;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      padding: 0.15rem 0.45rem;
      border-radius: 4px;
    }}
    .card-meta {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-size: 0.78rem;
      color: var(--text-dim);
    }}
    .download-btn {{
      color: var(--accent-gold);
      text-decoration: none;
      font-size: 1rem;
      line-height: 1;
    }}
    .download-btn:hover {{
      color: var(--accent-gold-hover);
    }}

    /* Lightbox Modal */
    .lightbox {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.95);
      z-index: 1000;
      flex-direction: column;
    }}
    .lightbox.active {{
      display: flex;
    }}
    .lightbox-header {{
      padding: 1rem 1.5rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(13, 14, 17, 0.8);
      border-bottom: 1px solid var(--border-color);
    }}
    .lightbox-title {{
      font-family: Georgia, 'Liberation Serif', serif;
      font-size: 1.25rem;
      color: var(--accent-gold);
    }}
    .lightbox-actions {{
      display: flex;
      align-items: center;
      gap: 1rem;
    }}
    .lightbox-btn {{
      background: transparent;
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 0.4rem 0.8rem;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.85rem;
    }}
    .lightbox-btn:hover {{
      border-color: var(--accent-gold);
      color: var(--accent-gold);
    }}
    .lightbox-stage {{
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
      padding: 1.5rem;
      user-select: none;
    }}
    .lightbox-img {{
      max-width: 100%;
      max-height: calc(100vh - 140px);
      object-fit: contain;
      box-shadow: 0 20px 50px rgba(0,0,0,0.8);
      border-radius: 4px;
    }}
    .nav-arrow {{
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      background: rgba(22, 25, 34, 0.7);
      border: 1px solid var(--border-color);
      color: #fff;
      font-size: 2rem;
      width: 50px;
      height: 50px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: background 0.2s;
    }}
    .nav-arrow:hover {{
      background: var(--accent-gold);
      color: #000;
    }}
    .nav-prev {{ left: 1.5rem; }}
    .nav-next {{ right: 1.5rem; }}
    .lightbox-footer {{
      padding: 0.75rem 1.5rem;
      background: rgba(13, 14, 17, 0.8);
      border-top: 1px solid var(--border-color);
      text-align: center;
      font-size: 0.82rem;
      color: var(--text-muted);
    }}

    footer {{
      border-top: 1px solid var(--border-color);
      padding: 2rem;
      text-align: center;
      font-size: 0.85rem;
      color: var(--text-dim);
      background: #090A0D;
    }}
    footer a {{
      color: var(--accent-gold);
      text-decoration: none;
    }}
  </style>
</head>
<body>
  <header>
    <div class="header-content">
      <div class="header-top">
        <div>
          <span class="album-badge">Visual Verse TV Album</span>
          <h1>{escaped_title}</h1>
          <p class="description">{escaped_desc}</p>
        </div>
        <button class="slideshow-btn" onclick="startSlideshow()">▶ Play Slideshow</button>
      </div>
      <div class="meta-badges">
        <div class="meta-badge">Slides: <strong>{total_slides}</strong></div>
        <div class="meta-badge">Resolution: <strong>{res_label}</strong></div>
        <div class="meta-badge">Theme: <strong>{theme_name}</strong></div>
        <div class="meta-badge">Format: <strong>{render_cfg.output_format.upper()}</strong></div>
        <div class="meta-badge">Generated: <strong>{datetime.date.today().isoformat()}</strong></div>
      </div>

      <!-- TV Screensaver Setup Guide -->
      <div class="tv-guide-wrapper">
        <div class="tv-guide-header" onclick="toggleTvGuide()">
          <span>📺 How to Sync This Album to Your TV Screensaver</span>
          <span id="guide-arrow">▼</span>
        </div>
        <div class="tv-guide-body" id="tv-guide-content">
          <div class="tv-steps-grid">
            <div class="tv-step-card">
              <h4>1. Google TV &amp; Chromecast</h4>
              <ol>
                <li>Open <strong>Google Photos</strong> on web/mobile.</li>
                <li>Upload all images from this folder.</li>
                <li>Add them to a new album (e.g. <em>"Bible Screensaver"</em>).</li>
                <li>On TV: <strong>Settings → Ambient Mode → Google Photos</strong>.</li>
                <li>Select your scripture album.</li>
              </ol>
            </div>
            <div class="tv-step-card">
              <h4>2. Smart TVs via USB Drive</h4>
              <ol>
                <li>Copy this entire folder onto a USB flash drive.</li>
                <li>Insert into your TV's USB media port.</li>
                <li>Open TV <strong>Photo/Media Gallery</strong> app.</li>
                <li>Select this folder and choose <strong>"Slideshow"</strong>.</li>
                <li>Set transition timer to 15–30 seconds.</li>
              </ol>
            </div>
            <div class="tv-step-card">
              <h4>3. Apple TV / Mac</h4>
              <ol>
                <li>Import this folder into <strong>Apple Photos</strong>.</li>
                <li>Create a Shared or Local Album.</li>
                <li>On Apple TV: <strong>Settings → Screensaver → Photos</strong>.</li>
                <li>Select your curated Scripture album.</li>
              </ol>
            </div>
          </div>
        </div>
      </div>
    </div>
  </header>

  <div class="controls-bar">
    <input type="text" id="search-box" class="search-input" placeholder="Filter slides by citation, text, or tag..." oninput="filterCards()" />
    <div style="font-size: 0.85rem; color: var(--text-dim);" id="filter-count">Showing {total_slides} of {total_slides} slides</div>
  </div>

  <main>
    <div class="gallery-grid" id="gallery-grid">
      {"".join(cards_html)}
    </div>
  </main>

  <!-- Lightbox Modal -->
  <div class="lightbox" id="lightbox">
    <div class="lightbox-header">
      <div class="lightbox-title" id="lightbox-citation">Citation</div>
      <div class="lightbox-actions">
        <button class="lightbox-btn" id="lightbox-play" onclick="toggleSlideshowPlay()">▶ Play (10s)</button>
        <button class="lightbox-btn" onclick="downloadCurrentSlide()">⬇ Download</button>
        <button class="lightbox-btn" onclick="closeLightbox()">✕ Close (Esc)</button>
      </div>
    </div>
    <div class="lightbox-stage">
      <button class="nav-arrow nav-prev" onclick="prevSlide()">‹</button>
      <img src="" alt="" class="lightbox-img" id="lightbox-img" />
      <button class="nav-arrow nav-next" onclick="nextSlide()">›</button>
    </div>
    <div class="lightbox-footer" id="lightbox-footer">Slide 1 of {total_slides}</div>
  </div>

  <footer>
    <p>Rendered with <strong>Bible Engine</strong> — Zero-Dependency Scripture Architecture (ADR-003 & ADR-005).</p>
  </footer>

  <script>
    const SLIDES = {slides_json_array};
    let currentIndex = 0;
    let slideshowInterval = null;

    function toggleTvGuide() {{
      const body = document.getElementById('tv-guide-content');
      const arrow = document.getElementById('guide-arrow');
      body.classList.toggle('active');
      arrow.textContent = body.classList.contains('active') ? '▲' : '▼';
    }}

    function filterCards() {{
      const q = document.getElementById('search-box').value.toLowerCase().trim();
      const cards = document.querySelectorAll('.slide-card');
      let visible = 0;
      cards.forEach(card => {{
        const cit = (card.getAttribute('data-citation') || '').toLowerCase();
        const text = (card.innerText || '').toLowerCase();
        if (!q || cit.includes(q) || text.includes(q)) {{
          card.style.display = '';
          visible++;
        }} else {{
          card.style.display = 'none';
        }}
      }});
      document.getElementById('filter-count').textContent = `Showing ${{visible}} of ${{cards.length}} slides`;
    }}

    function openLightbox(index) {{
      currentIndex = Math.max(0, Math.min(index, SLIDES.length - 1));
      updateLightbox();
      document.getElementById('lightbox').classList.add('active');
      document.body.style.overflow = 'hidden';
    }}

    function closeLightbox() {{
      stopSlideshow();
      document.getElementById('lightbox').classList.remove('active');
      document.body.style.overflow = '';
    }}

    function updateLightbox() {{
      const s = SLIDES[currentIndex];
      if (!s) return;
      document.getElementById('lightbox-img').src = s.filename;
      document.getElementById('lightbox-citation').textContent = `${{s.citation}} (${{s.width}}x${{s.height}} ${{s.format.toUpperCase()}})`;
      document.getElementById('lightbox-footer').textContent = `Slide ${{currentIndex + 1}} of ${{SLIDES.length}} — ${{s.filename}}`;
    }}

    function prevSlide() {{
      currentIndex = (currentIndex - 1 + SLIDES.length) % SLIDES.length;
      updateLightbox();
    }}

    function nextSlide() {{
      currentIndex = (currentIndex + 1) % SLIDES.length;
      updateLightbox();
    }}

    function downloadCurrentSlide() {{
      const s = SLIDES[currentIndex];
      if (s) {{
        const a = document.createElement('a');
        a.href = s.filename;
        a.download = s.filename;
        a.click();
      }}
    }}

    function startSlideshow() {{
      openLightbox(0);
      toggleSlideshowPlay(true);
    }}

    function toggleSlideshowPlay(forceStart = false) {{
      const btn = document.getElementById('lightbox-play');
      if (slideshowInterval && !forceStart) {{
        stopSlideshow();
      }} else {{
        if (slideshowInterval) clearInterval(slideshowInterval);
        slideshowInterval = setInterval(nextSlide, 10000);
        btn.textContent = '⏸ Pause';
        btn.style.borderColor = 'var(--accent-gold)';
      }}
    }}

    function stopSlideshow() {{
      if (slideshowInterval) {{
        clearInterval(slideshowInterval);
        slideshowInterval = null;
      }}
      const btn = document.getElementById('lightbox-play');
      if (btn) {{
        btn.textContent = '▶ Play (10s)';
        btn.style.borderColor = '';
      }}
    }}

    window.addEventListener('keydown', (e) => {{
      const lb = document.getElementById('lightbox');
      if (!lb.classList.contains('active')) return;
      if (e.key === 'Escape') closeLightbox();
      else if (e.key === 'ArrowLeft') prevSlide();
      else if (e.key === 'ArrowRight') nextSlide();
      else if (e.key === ' ') {{
        e.preventDefault();
        toggleSlideshowPlay();
      }}
    }});
  </script>
</body>
</html>
"""
