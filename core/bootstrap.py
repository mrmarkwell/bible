"""Sovereign Cold-Start Bootstrapping & Database Lifecycle Engine.

Zero-dependency module (Python 3 standard library only per ADR-003).
Provides unified orchestration for:
- Database schema initialization (core/db.py).
- Public Domain scripture ingestion from cached raw JSON (tools/ingest_web.py).
- Curated favorite passages and starred verse tagging (tools/ingest_favorites.py).
- Canonical TGC theological & redemptive-historical tag taxonomies (core/tags.py).
- Canonical Old/New Testament typological cross-reference graph (core/crossref.py).
- SQLite storage optimization (PRAGMA optimize, VACUUM, ANALYZE).
- Automated git hook safeguards installation (tools/doctor.py).
- Comprehensive database inspection and statistics reporting.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from core.crossref import CrossReferenceService
from core.db import DEFAULT_DB_PATH, Database
from core.pericopes import PericopeService
from core.reference import ALL_BOOKS, Book, BOOKS
from core.tags import TaggingService

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RAW_WEB_DIR = REPO_ROOT / "data" / "raw" / "web"
DEFAULT_RAW_KJV_DIR = REPO_ROOT / "data" / "raw" / "kjv"
DEFAULT_FAVORITES_CSV = REPO_ROOT / "favorite_bible_verses.csv"


@dataclass(frozen=True)
class BootstrapReport:
    """Detailed results of a database bootstrapping operation."""

    db_path: Path
    duration_sec: float
    verses_count: int
    translations_count: int
    favorites_count: int
    starred_count: int
    tags_count: int
    cross_references_count: int
    hooks_installed: bool
    pragmas_optimized: bool
    is_clean: bool
    details: str
    pericopes_count: int = 0

    def summary_lines(self) -> List[str]:
        """Generate human-readable summary lines for CLI display."""
        hooks_text = "Installed" if self.hooks_installed else "Skipped/Inactive"
        pragmas_text = "Complete (PRAGMA optimize)" if self.pragmas_optimized else "Skipped"
        return [
            f"Database Path:           {self.db_path}",
            f"Verses Ingested:         {self.verses_count:,} (Bundled Public Domain Translations)",
            f"Translations:            {self.translations_count}",
            f"Curated Favorites:       {self.favorites_count} passages ({self.starred_count} starred)",
            f"Canonical Tags:          {self.tags_count} theological/redemptive taxonomies",
            f"Canonical Pericopes:     {self.pericopes_count} redemptive section headings",
            f"Cross-Reference Edges:   {self.cross_references_count} canonical OT/NT links",
            f"Git Hook Safeguards:     {hooks_text}",
            f"Pragma Optimization:     {pragmas_text}",
            f"Duration:                {self.duration_sec:.2f}s",
            f"Status:                  {self.details}",
        ]


def format_size(bytes_count: int) -> str:
    """Format byte count into human-readable representation."""
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.1f} KB"
    else:
        return f"{bytes_count / (1024 * 1024):.1f} MB"


def get_db_stats(db_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Retrieve comprehensive database statistics, schema health, and pragmas.

    Args:
        db_path: Path to SQLite database (defaults to DEFAULT_DB_PATH).

    Returns:
        Dictionary of database metrics and status.
    """
    target_path = Path(db_path).resolve() if db_path else DEFAULT_DB_PATH
    if not target_path.exists():
        return {
            "exists": False,
            "path": str(target_path),
            "size_bytes": 0,
            "size_human": "0 B",
            "total_verses": 0,
            "translations": [],
            "total_tags": 0,
            "total_tagged_passages": 0,
            "total_cross_references": 0,
            "total_favorites": 0,
            "total_starred": 0,
            "total_pericopes": 0,
            "total_discourse_relations": 0,
            "total_verse_theology": 0,
            "total_typological_arcs": 0,
            "total_semantic_propositions": 0,
            "total_verse_embeddings": 0,
            "total_pericope_embeddings": 0,
            "sqlite_version": "N/A",
            "integrity_check": "missing",
            "fts5_status": "inactive",
            "page_size": 0,
            "page_count": 0,
            "journal_mode": "N/A",
        }

    size_bytes = target_path.stat().st_size
    with Database(target_path, check_same_thread=False) as db:
        # SQLite Pragmas & Version
        sqlite_ver_row = db.execute_sql("SELECT sqlite_version()").fetchone()
        sqlite_version = sqlite_ver_row[0] if sqlite_ver_row else "unknown"

        integrity_row = db.execute_sql("PRAGMA quick_check").fetchone()
        integrity = integrity_row[0] if integrity_row else "unknown"

        page_size_row = db.execute_sql("PRAGMA page_size").fetchone()
        page_size = page_size_row[0] if page_size_row else 4096

        page_count_row = db.execute_sql("PRAGMA page_count").fetchone()
        page_count = page_count_row[0] if page_count_row else 0

        journal_row = db.execute_sql("PRAGMA journal_mode").fetchone()
        journal_mode = journal_row[0] if journal_row else "unknown"

        # Table Row Counts
        total_verses = db.count_verses()

        # Translations
        translations = []
        trans_rows = db.execute_sql(
            "SELECT t.id, t.name, count(v.id) as verse_count "
            "FROM translations t LEFT JOIN verses v ON t.id = v.translation_id "
            "GROUP BY t.id"
        ).fetchall()
        for tr in trans_rows:
            translations.append({
                "id": tr["id"],
                "name": tr["name"],
                "verse_count": tr["verse_count"],
            })

        # Tags
        tag_count_row = db.execute_sql("SELECT count(*) FROM tags").fetchone()
        total_tags = tag_count_row[0] if tag_count_row else 0

        verse_tag_row = db.execute_sql("SELECT count(*) FROM verse_tags").fetchone()
        total_tagged_passages = verse_tag_row[0] if verse_tag_row else 0

        # Favorites
        fav_row = db.execute_sql(
            "SELECT count(*), coalesce(sum(case when starred = 1 then 1 else 0 end), 0) "
            "FROM verse_tags vt JOIN tags t ON vt.tag_id = t.id WHERE t.name = 'favorites'"
        ).fetchone()
        total_favorites = fav_row[0] if fav_row else 0
        total_starred = fav_row[1] if fav_row else 0

        # Cross References
        xr_row = db.execute_sql("SELECT count(*) FROM cross_references").fetchone()
        total_cross_references = xr_row[0] if xr_row else 0

        # Canonical Pericopes
        p_row = db.execute_sql("SELECT count(*) FROM pericopes").fetchone()
        total_pericopes = p_row[0] if p_row else 0

        # Phase 7 Semantic Architecture Tables
        dr_row = db.execute_sql("SELECT count(*) FROM discourse_relations").fetchone()
        total_discourse_relations = dr_row[0] if dr_row else 0

        vt_row = db.execute_sql("SELECT count(*) FROM verse_theology").fetchone()
        total_verse_theology = vt_row[0] if vt_row else 0

        arc_row = db.execute_sql("SELECT count(*) FROM typological_arcs").fetchone()
        total_typological_arcs = arc_row[0] if arc_row else 0

        sp_row = db.execute_sql("SELECT count(*) FROM semantic_propositions").fetchone()
        total_semantic_propositions = sp_row[0] if sp_row else 0

        ve_row = db.execute_sql("SELECT count(*) FROM verse_embeddings").fetchone()
        total_verse_embeddings = ve_row[0] if ve_row else 0

        pe_row = db.execute_sql("SELECT count(*) FROM pericope_embeddings").fetchone()
        total_pericope_embeddings = pe_row[0] if pe_row else 0

        # Canonical Character Profiles
        cp_row = db.execute_sql("SELECT count(*) FROM character_profiles").fetchone()
        total_character_profiles = cp_row[0] if cp_row else 0

        # FTS5 Index status
        fts_row = db.execute_sql(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='verses_fts'"
        ).fetchone()
        fts_active = bool(fts_row and fts_row[0] > 0)

    return {
        "exists": True,
        "path": str(target_path),
        "size_bytes": size_bytes,
        "size_human": format_size(size_bytes),
        "total_verses": total_verses,
        "translations": translations,
        "total_tags": total_tags,
        "total_tagged_passages": total_tagged_passages,
        "total_cross_references": total_cross_references,
        "total_favorites": total_favorites,
        "total_starred": total_starred,
        "total_pericopes": total_pericopes,
        "total_character_profiles": total_character_profiles,
        "total_discourse_relations": total_discourse_relations,
        "total_verse_theology": total_verse_theology,
        "total_typological_arcs": total_typological_arcs,
        "total_semantic_propositions": total_semantic_propositions,
        "total_verse_embeddings": total_verse_embeddings,
        "total_pericope_embeddings": total_pericope_embeddings,
        "sqlite_version": sqlite_version,
        "integrity_check": integrity,
        "fts5_status": "active" if fts_active else "missing",
        "page_size": page_size,
        "page_count": page_count,
        "journal_mode": journal_mode,
    }


def is_database_healthy(db_path: Optional[Union[str, Path]] = None) -> bool:
    """Quickly check if target database exists and contains standard baseline data."""
    target_path = Path(db_path).resolve() if db_path else DEFAULT_DB_PATH
    if not target_path.exists() or target_path.stat().st_size == 0:
        return False

    try:
        with Database(target_path, check_same_thread=False) as db:
            verse_count = db.count_verses()
            tag_count_row = db.execute_sql("SELECT count(*) FROM tags").fetchone()
            tag_count = tag_count_row[0] if tag_count_row else 0
            xr_row = db.execute_sql("SELECT count(*) FROM cross_references").fetchone()
            xr_count = xr_row[0] if xr_row else 0
            p_row = db.execute_sql("SELECT count(*) FROM pericopes").fetchone()
            p_count = p_row[0] if p_row else 0
            return verse_count >= 31100 and tag_count >= 20 and xr_count >= 40 and p_count >= 100
    except Exception:
        return False


def bootstrap_database(
    db_path: Optional[Union[str, Path]] = None,
    raw_web_dir: Optional[Union[str, Path]] = None,
    raw_kjv_dir: Optional[Union[str, Path]] = None,
    favorites_csv: Optional[Union[str, Path]] = None,
    force: bool = False,
    install_git_hooks: bool = True,
    verbose: bool = False,
    quick: bool = False,
    books: Optional[Sequence[Book]] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    onboarding_wizard: bool = False,
    esv_key: Optional[str] = None,
    gemini_key: Optional[str] = None,
    probe_keys: bool = True,
) -> BootstrapReport:
    """Bootstrap and compile complete sovereign scripture and knowledge database.

    Orchestrates the entire offline pipeline:
    1. Validates or initializes SQLite schema with FTS5 search triggers.
    2. Compiles World English Bible (31,103 verses) from cached raw JSON.
    3. Ingests curated favorite verses (829 passages, 50 starred).
    4. Seeds canonical theological and redemptive-historical taxonomies (26 tags).
    5. Seeds curated canonical OT/NT typological cross-reference links (67 edges).
    6. Optimizes SQLite storage via PRAGMA optimize & ANALYZE.
    7. Optionally installs automated git hook safeguards (pre-commit & pre-push).
    8. Optionally executes API key onboarding wizard and connectivity probes.

    Args:
        db_path: Target SQLite database path (defaults to DEFAULT_DB_PATH).
        raw_web_dir: Directory containing cached WEB JSON files.
        favorites_csv: Path to favorite_bible_verses.csv.
        force: If True, re-compiles and re-indexes even if database is healthy.
        install_git_hooks: If True, installs pre-commit/pre-push hooks in .git.
        verbose: If True, outputs step-by-step progress to stdout.
        quick: If True, inits schema and seeds tags/crossrefs with sample books only.
        books: Optional explicit list of canonical books to compile.
        progress_callback: Optional callback receiving (step_description, pct_complete).
        onboarding_wizard: If True, launches interactive API key onboarding wizard.
        esv_key: Optional explicit ESV key to save during bootstrap.
        gemini_key: Optional explicit Gemini key to save during bootstrap.
        probe_keys: Whether to execute live network connectivity probe on configured keys.

    Returns:
        BootstrapReport with verified counts, timings, and status.
    """
    t0 = time.time()
    target_path = Path(db_path).resolve() if db_path else DEFAULT_DB_PATH
    target_raw_dir = Path(raw_web_dir).resolve() if raw_web_dir else DEFAULT_RAW_WEB_DIR
    target_raw_kjv_dir = Path(raw_kjv_dir).resolve() if raw_kjv_dir else DEFAULT_RAW_KJV_DIR
    target_csv = Path(favorites_csv).resolve() if favorites_csv else DEFAULT_FAVORITES_CSV

    def _notify(step: str, pct: float) -> None:
        if progress_callback:
            progress_callback(step, pct)
        if verbose:
            print(f"[{pct * 100:3.0f}%] {step}")

    # Run onboarding wizard if requested or explicit keys provided
    if onboarding_wizard or esv_key is not None or gemini_key is not None:
        try:
            from tools.onboarding import run_onboarding_wizard
            run_onboarding_wizard(
                repo_root=REPO_ROOT,
                interactive=onboarding_wizard,
                esv_key=esv_key,
                gemini_key=gemini_key,
                probe=probe_keys,
            )
        except Exception as exc:
            if verbose:
                print(f"[Notice] Onboarding wizard notice: {exc}")

    # Check for fast idempotent exit if healthy and not forced
    if not force and not quick and books is None and is_database_healthy(target_path):
        stats = get_db_stats(target_path)
        hooks_ok = False
        if install_git_hooks and (REPO_ROOT / ".git").exists():
            from tools.doctor import install_hooks
            hooks_ok, _ = install_hooks(REPO_ROOT)

        dur = time.time() - t0
        return BootstrapReport(
            db_path=target_path,
            duration_sec=dur,
            verses_count=stats["total_verses"],
            translations_count=len(stats["translations"]),
            favorites_count=stats["total_favorites"],
            starred_count=stats["total_starred"],
            tags_count=stats["total_tags"],
            cross_references_count=stats["total_cross_references"],
            hooks_installed=hooks_ok,
            pragmas_optimized=True,
            is_clean=True,
            details="Database already initialized and healthy (idempotent no-op)",
            pericopes_count=stats.get("total_pericopes", 0),
        )

    # Ensure parent directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if force and target_path.exists():
        _notify("Removing existing database for clean rebuild...", 0.05)
        try:
            target_path.unlink()
        except Exception:
            pass

    # 1. Initialize schema
    _notify("Initializing SQLite schema and FTS5 search triggers...", 0.10)
    db = Database(target_path, auto_init=True, check_same_thread=False)

    # 2. Ingest WEB Translation
    target_books = books
    if quick and target_books is None:
        target_books = [BOOKS[1], BOOKS[43], BOOKS[45], BOOKS[66]]

    _notify("Compiling World English Bible scripture texts...", 0.25)
    from tools.ingest_web import ingest_web
    ingested_verses = ingest_web(
        db_path=target_path,
        raw_dir=target_raw_dir,
        force_download=False,
        verbose=False,
        books=target_books,
    )

    if target_raw_kjv_dir.exists():
        _notify("Compiling King James Version scripture texts...", 0.45)
        from tools.ingest_kjv import ingest_kjv
        kjv_verses = ingest_kjv(
            db_path=target_path,
            raw_dir=target_raw_kjv_dir,
            force_download=False,
            verbose=False,
            books=target_books,
        )
        ingested_verses += kjv_verses

    # 3. Ingest Curated Favorites
    favorites_count = 0
    starred_count = 0
    if target_csv.exists():
        _notify("Ingesting curated favorite verses and starred annotations...", 0.60)
        from tools.ingest_favorites import ingest_favorites
        favorites_count, starred_count = ingest_favorites(
            db=db,
            csv_path=target_csv,
            clear_existing=True,
        )

    # 4. Seed Canonical TGC Taxonomies
    _notify("Seeding canonical theological and redemptive taxonomies...", 0.75)
    tag_service = TaggingService(db)
    seeded_tags = tag_service.seed_canonical_taxonomies()

    # 5. Seed Canonical Typological Cross-References
    _notify("Seeding canonical Old/New Testament typological cross-references...", 0.82)
    xr_service = CrossReferenceService(db)
    seeded_xrefs = xr_service.seed_canonical_cross_references()

    # 6. Seed Canonical Pericopes
    _notify("Seeding canonical pericope headings and redemptive summaries...", 0.88)
    pericope_service = PericopeService(db)
    seeded_pericopes = pericope_service.seed_canonical_pericopes()

    # 6b. Seed Canonical Character Profiles
    _notify("Seeding canonical biblical character profiles...", 0.90)
    from core.persona import CANONICAL_PERSONAS
    import json
    for p in CANONICAL_PERSONAS:
        db.insert_character_profile(
            name=p.canonical_name,
            canonical_spans=json.dumps(list(p.key_passages)),
            historical_context=f"{p.canonical_era} | {p.lifespan_description}",
            theological_role=p.theological_role,
        )

    # 7. Compile Permanent Semantic Pack (Phase 7 Whole-Bible Coverage)
    if not quick and books is None:
        _notify("Compiling permanent whole-Bible semantic pack...", 0.92)
        from core.semantic_compiler import SemanticDatabaseCompiler
        compiler = SemanticDatabaseCompiler(db=db)
        compiler.compile_permanent_semantic_pack(resume=True, include_all_chapters=True)

    # 8. Optimize Pragmas and Analyzers
    _notify("Optimizing SQLite query planner statistics (PRAGMA optimize)...", 0.96)
    db.optimize()
    db.close()

    # 8. Install Git Hooks
    hooks_installed = False
    if install_git_hooks and (REPO_ROOT / ".git").exists():
        _notify("Configuring automated git pre-commit & pre-push hooks...", 0.98)
        from tools.doctor import install_hooks
        hooks_installed, _ = install_hooks(REPO_ROOT)

    dur = time.time() - t0
    _notify(f"Bootstrap complete in {dur:.2f}s!", 1.0)

    # Query final verified stats
    final_stats = get_db_stats(target_path)

    return BootstrapReport(
        db_path=target_path,
        duration_sec=dur,
        verses_count=final_stats["total_verses"],
        translations_count=len(final_stats["translations"]),
        favorites_count=final_stats["total_favorites"],
        starred_count=final_stats["total_starred"],
        tags_count=final_stats["total_tags"],
        cross_references_count=final_stats["total_cross_references"],
        hooks_installed=hooks_installed,
        pragmas_optimized=True,
        is_clean=True,
        details=f"Successfully compiled and bootstrapped in {dur:.2f}s",
        pericopes_count=final_stats["total_pericopes"],
    )
