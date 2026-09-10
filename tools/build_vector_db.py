#!/usr/bin/env python3
"""Batch Vector Ingestion Engine & Whole-Bible Vector Database Compiler CLI.

Zero-dependency CLI utility (Python 3 standard library only per ADR-003 and ADR-083):
- Formulates multi-tiered Semantic Passports for all 1,304+ canonical pericopes (or by --corpus / --book).
- Generates 768-dimensional dense vector embeddings using Google Gemini text-embedding-004
  (with batchEmbedContents or embedContent) or pure stdlib deterministic pseudo-embedding fallback.
- Quantizes normalized float32 vectors to signed int8 byte representations [-127, 127] (ADR-051).
- Ingests into the SQLite `pericope_embeddings` table and tracks progress via a crash-resilient
  `vector_checkpoint_ledger`.
- Supports --resume, --reset-failed, --clear-ledger, --status, --dry-run, and --json telemetry.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import datetime
import json
from pathlib import Path
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.corpora import CanonicalCorpus, get_corpus
from core.db import DEFAULT_DB_PATH, Database
from core.llm import (
    DEFAULT_EMBEDDING_MODEL,
    GeminiClient,
    get_gemini_api_key,
)
from core.passport import SemanticPassportGenerator
from core.projection import project_embeddings
from core.reference import Book, get_book
from core.semantic_compiler import CompilationUnitStatus, RateLimiter
from core.vector import (
    DEFAULT_VECTOR_DIM,
    normalize_vector,
    pseudo_embed_text,
    quantize_float_to_int8,
)


def _utc_now_iso() -> str:
    """Return current UTC ISO-8601 timestamp."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@dataclass(frozen=True)
class VectorCheckpointRecord:
    """Represents a persisted vector checkpoint ledger row in SQLite."""

    unit_id: str
    pericope_id: int
    book_id: int
    human_ref: str
    start_canonical_id: int
    end_canonical_id: int
    status: CompilationUnitStatus
    attempts: int = 0
    last_error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize record to dictionary."""
        return {
            "unit_id": self.unit_id,
            "pericope_id": self.pericope_id,
            "book_id": self.book_id,
            "human_ref": self.human_ref,
            "start_canonical_id": self.start_canonical_id,
            "end_canonical_id": self.end_canonical_id,
            "status": self.status.value,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class VectorCheckpointLedger:
    """Sovereign SQLite-backed state machine tracking vector ingestion progress."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._init_schema()

    def _init_schema(self) -> None:
        """Ensure vector checkpoint ledger table exists in SQLite database."""
        with self.db.conn:
            self.db.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vector_checkpoint_ledger (
                    unit_id TEXT PRIMARY KEY,
                    pericope_id INTEGER NOT NULL,
                    book_id INTEGER NOT NULL,
                    human_ref TEXT NOT NULL,
                    start_canonical_id INTEGER NOT NULL,
                    end_canonical_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (pericope_id) REFERENCES pericopes(id) ON DELETE CASCADE
                );
                """
            )
            self.db.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_vector_ledger_status
                ON vector_checkpoint_ledger(status);
                """
            )
            self.db.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_vector_ledger_book
                ON vector_checkpoint_ledger(book_id, status);
                """
            )

    def record_pericope(self, pericope_id: int, book_id: int, human_ref: str, s_id: int, e_id: int) -> str:
        """Register or retrieve an existing pericope unit in the ledger."""
        unit_id = f"vec_pericope_{pericope_id}_{s_id}_{e_id}"
        now = _utc_now_iso()
        with self.db.conn:
            self.db.conn.execute(
                """
                INSERT OR IGNORE INTO vector_checkpoint_ledger (
                    unit_id, pericope_id, book_id, human_ref, start_canonical_id, end_canonical_id,
                    status, attempts, last_error, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?)
                """,
                (
                    unit_id,
                    pericope_id,
                    book_id,
                    human_ref,
                    s_id,
                    e_id,
                    CompilationUnitStatus.PENDING.value,
                    now,
                    now,
                ),
            )
        return unit_id

    def get_status(self, unit_id: str) -> Optional[CompilationUnitStatus]:
        """Fetch status of a ledger item."""
        cur = self.db.conn.cursor()
        row = cur.execute(
            "SELECT status FROM vector_checkpoint_ledger WHERE unit_id = ?",
            (unit_id,),
        ).fetchone()
        if not row:
            return None
        val = row[0] if isinstance(row, (tuple, list)) else row["status"]
        return CompilationUnitStatus(val)

    def mark_in_progress(self, unit_id: str) -> None:
        """Mark unit as currently being embedded."""
        now = _utc_now_iso()
        with self.db.conn:
            self.db.conn.execute(
                """
                UPDATE vector_checkpoint_ledger
                SET status = ?, attempts = attempts + 1, updated_at = ?
                WHERE unit_id = ?
                """,
                (CompilationUnitStatus.IN_PROGRESS.value, now, unit_id),
            )

    def mark_completed(self, unit_id: str) -> None:
        """Mark unit as successfully embedded and persisted in SQLite."""
        now = _utc_now_iso()
        with self.db.conn:
            self.db.conn.execute(
                """
                UPDATE vector_checkpoint_ledger
                SET status = ?, last_error = NULL, updated_at = ?
                WHERE unit_id = ?
                """,
                (CompilationUnitStatus.COMPLETED.value, now, unit_id),
            )

    def mark_failed(self, unit_id: str, error_message: str) -> None:
        """Record failure reason for a ledger unit."""
        now = _utc_now_iso()
        with self.db.conn:
            self.db.conn.execute(
                """
                UPDATE vector_checkpoint_ledger
                SET status = ?, last_error = ?, updated_at = ?
                WHERE unit_id = ?
                """,
                (CompilationUnitStatus.FAILED.value, error_message, now, unit_id),
            )

    def reset_failed(self, book_id: Optional[Union[int, Sequence[int]]] = None) -> int:
        """Reset failed units back to PENDING."""
        now = _utc_now_iso()
        query = "UPDATE vector_checkpoint_ledger SET status = ?, updated_at = ? WHERE status = ?"
        params: List[Any] = [CompilationUnitStatus.PENDING.value, now, CompilationUnitStatus.FAILED.value]
        if book_id is not None:
            if isinstance(book_id, int):
                query += " AND book_id = ?"
                params.append(book_id)
            elif isinstance(book_id, (list, tuple, set)):
                b_list = list(book_id)
                if b_list:
                    ph = ",".join("?" for _ in b_list)
                    query += f" AND book_id IN ({ph})"
                    params.extend(b_list)
        with self.db.conn:
            cur = self.db.conn.execute(query, params)
            return cur.rowcount

    def get_summary(self, book_id: Optional[Union[int, Sequence[int]]] = None) -> Dict[str, int]:
        """Aggregate ledger counts by status."""
        query = "SELECT status, count(*) as cnt FROM vector_checkpoint_ledger"
        params: List[Any] = []
        if book_id is not None:
            if isinstance(book_id, int):
                query += " WHERE book_id = ?"
                params.append(book_id)
            elif isinstance(book_id, (list, tuple, set)):
                b_list = list(book_id)
                if b_list:
                    ph = ",".join("?" for _ in b_list)
                    query += f" WHERE book_id IN ({ph})"
                    params.extend(b_list)
        query += " GROUP BY status"

        cur = self.db.conn.cursor()
        rows = cur.execute(query, params).fetchall()

        res = {s.value: 0 for s in CompilationUnitStatus}
        for r in rows:
            st = r[0] if isinstance(r, (tuple, list)) else r["status"]
            cnt = r[1] if isinstance(r, (tuple, list)) else r["cnt"]
            res[st] = cnt
        return res

    def clear_ledger(self, book_id: Optional[Union[int, Sequence[int]]] = None) -> int:
        """Clear checkpoint records from the ledger."""
        with self.db.conn:
            if book_id is not None:
                if isinstance(book_id, int):
                    cur = self.db.conn.execute(
                        "DELETE FROM vector_checkpoint_ledger WHERE book_id = ?",
                        (book_id,),
                    )
                elif isinstance(book_id, (list, tuple, set)):
                    b_list = list(book_id)
                    if b_list:
                        ph = ",".join("?" for _ in b_list)
                        cur = self.db.conn.execute(
                            f"DELETE FROM vector_checkpoint_ledger WHERE book_id IN ({ph})",
                            tuple(b_list),
                        )
                    else:
                        return 0
            else:
                cur = self.db.conn.execute("DELETE FROM vector_checkpoint_ledger")
            return cur.rowcount


@dataclass
class VectorIngestionProgress:
    """Telemetry tracking progress of batch vector compilation."""

    total_units: int = 0
    completed_units: int = 0
    skipped_units: int = 0
    failed_units: int = 0
    total_embeddings: int = 0
    duration_sec: float = 0.0
    start_time: float = field(default_factory=time.time)

    @property
    def percent_complete(self) -> float:
        """Percentage of units processed (completed + skipped)."""
        if self.total_units <= 0:
            return 100.0
        done = self.completed_units + self.skipped_units
        return (done / self.total_units) * 100.0

    @property
    def rate_per_minute(self) -> float:
        """Pericopes completed per minute."""
        elapsed = time.time() - self.start_time
        if elapsed <= 0.1:
            return 0.0
        return (self.completed_units / elapsed) * 60.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert telemetry to dictionary."""
        elapsed = max(0.001, time.time() - self.start_time)
        return {
            "total_units": self.total_units,
            "completed_units": self.completed_units,
            "skipped_units": self.skipped_units,
            "failed_units": self.failed_units,
            "total_embeddings": self.total_embeddings,
            "percent_complete": round(self.percent_complete, 2),
            "duration_sec": round(elapsed, 3),
            "rate_per_minute": round(self.rate_per_minute, 1),
        }


class BatchVectorCompiler:
    """Compiles Semantic Passports into quantized int8 vector embeddings in SQLite."""

    def __init__(
        self,
        db: Database,
        api_key: Optional[str] = None,
        model_id: str = DEFAULT_EMBEDDING_MODEL,
        dimensions: int = DEFAULT_VECTOR_DIM,
        rate_limit_rpm: float = 60.0,
        batch_size: int = 25,
        translation_id: str = "WEB",
    ) -> None:
        self.db = db
        self.ledger = VectorCheckpointLedger(db)
        self.passport_gen = SemanticPassportGenerator(db, translation_id=translation_id)
        self.model_id = model_id.strip()
        self.dimensions = dimensions
        self.rate_limiter = RateLimiter(requests_per_minute=rate_limit_rpm)
        self.batch_size = max(1, min(100, batch_size))

        self.api_key = api_key or get_gemini_api_key()
        self.llm_client: Optional[GeminiClient] = None
        if self.api_key:
            self.llm_client = GeminiClient(api_key=self.api_key)

    def load_pericopes_for_scope(
        self,
        book_ids: Optional[Sequence[int]] = None,
    ) -> List[Dict[str, Any]]:
        """Load distinct canonical pericope rows matching the target scope."""
        cur = self.db.conn.cursor()
        query = """
            SELECT id, book_id, start_canonical_id, end_canonical_id, human_ref,
                   title, redemptive_summary, genre, literary_structure, central_proposition
            FROM pericopes
        """
        params: List[Any] = []
        if book_ids:
            ph = ",".join("?" for _ in book_ids)
            query += f" WHERE book_id IN ({ph})"
            params.extend(book_ids)
        query += " ORDER BY start_canonical_id ASC"

        rows = cur.execute(query, params).fetchall()
        result: List[Dict[str, Any]] = []
        for r in rows:
            result.append({
                "id": r["id"] if hasattr(r, "keys") else r[0],
                "book_id": r["book_id"] if hasattr(r, "keys") else r[1],
                "start_canonical_id": r["start_canonical_id"] if hasattr(r, "keys") else r[2],
                "end_canonical_id": r["end_canonical_id"] if hasattr(r, "keys") else r[3],
                "human_ref": r["human_ref"] if hasattr(r, "keys") else r[4],
                "title": r["title"] if hasattr(r, "keys") else r[5],
                "redemptive_summary": r["redemptive_summary"] if hasattr(r, "keys") else r[6],
                "genre": r["genre"] if hasattr(r, "keys") else r[7],
                "literary_structure": r["literary_structure"] if hasattr(r, "keys") else r[8],
                "central_proposition": r["central_proposition"] if hasattr(r, "keys") else r[9],
            })
        return result

    def embed_passport_document(self, document_text: str) -> Tuple[bytes, List[float]]:
        """Embed a single Semantic Passport text document and return packed int8 bytes."""
        clean_text = document_text.strip()
        raw_vec: List[float]
        if self.llm_client and self.llm_client.is_available():
            try:
                raw_vec = self.llm_client.embed_content(clean_text, model=self.model_id)
            except Exception:
                raw_vec = pseudo_embed_text(clean_text, dim=self.dimensions)
        else:
            raw_vec = pseudo_embed_text(clean_text, dim=self.dimensions)

        norm_vec = normalize_vector(raw_vec)
        packed_bytes, _ = quantize_float_to_int8(norm_vec)
        return packed_bytes, norm_vec

    def compile_scope(
        self,
        book_ids: Optional[Sequence[int]] = None,
        resume: bool = True,
        callback: Optional[Callable[[Dict[str, Any], bool, Optional[str], VectorIngestionProgress], None]] = None,
    ) -> VectorIngestionProgress:
        """Execute batch vector compilation across pericopes in the selected scope."""
        pericopes = self.load_pericopes_for_scope(book_ids)
        progress = VectorIngestionProgress(total_units=len(pericopes))

        # Register units in ledger
        unit_map: Dict[int, str] = {}
        for p in pericopes:
            u_id = self.ledger.record_pericope(
                pericope_id=p["id"],
                book_id=p["book_id"],
                human_ref=p["human_ref"],
                s_id=p["start_canonical_id"],
                e_id=p["end_canonical_id"],
            )
            unit_map[p["id"]] = u_id

        # Iterate and process
        for p in pericopes:
            pid = p["id"]
            u_id = unit_map[pid]
            status = self.ledger.get_status(u_id)

            if resume and status == CompilationUnitStatus.COMPLETED:
                # Check if already present in pericope_embeddings table
                existing = self.db.conn.execute(
                    "SELECT 1 FROM pericope_embeddings WHERE pericope_id = ?", (pid,)
                ).fetchone()
                if existing:
                    progress.skipped_units += 1
                    if callback:
                        callback(p, True, "Already completed (skipping)", progress)
                    continue

            self.ledger.mark_in_progress(u_id)
            try:
                # 1. Synthesize Semantic Passport
                passport = self.passport_gen.generate_for_pericope_record(p)
                doc_text = passport.format_document()

                # 2. Rate Limit Pacing
                if self.llm_client and self.llm_client.is_available():
                    self.rate_limiter.wait()

                # 3. Generate Embedding & Quantize
                packed_bytes, norm_vec = self.embed_passport_document(doc_text)

                # 4. Save into SQLite
                self.db.save_pericope_embedding(
                    pericope_id=pid,
                    reference=passport.reference,
                    model_id=self.model_id,
                    dimensions=len(norm_vec),
                    embedding=packed_bytes,
                )

                # 5. Mark Completed
                self.ledger.mark_completed(u_id)
                progress.completed_units += 1
                progress.total_embeddings += 1
                if callback:
                    callback(p, True, None, progress)

            except Exception as exc:
                err_str = str(exc)
                self.ledger.mark_failed(u_id, err_str)
                progress.failed_units += 1
                if callback:
                    callback(p, False, err_str, progress)

        progress.duration_sec = time.time() - progress.start_time
        return progress


def run_vector_build(
    db_path: Path,
    book_filter: Optional[str] = None,
    corpus_filter: Optional[str] = None,
    compile_all: bool = False,
    resume: bool = True,
    reset_failed: bool = False,
    clear_ledger: bool = False,
    status_only: bool = False,
    dry_run: bool = False,
    translation_id: str = "WEB",
    model_id: str = DEFAULT_EMBEDDING_MODEL,
    rate_limit_rpm: float = 60.0,
    api_key: Optional[str] = None,
    json_output: bool = False,
    verbose: bool = False,
    auto_project: bool = True,
    project_method: str = "fastmap",
) -> int:
    """Execute batch vector compilation or ledger inspection."""
    if not db_path.exists():
        if json_output:
            print(json.dumps({"error": f"Database file not found: {db_path}"}))
        else:
            print(f"\033[31m[!] Error: Database file not found: {db_path}\033[0m")
        return 1

    db = Database(db_path)
    ledger = VectorCheckpointLedger(db)

    # Resolve book filter if provided
    book_obj: Optional[Book] = None
    if book_filter:
        book_obj = get_book(book_filter)
        if not book_obj:
            if json_output:
                print(json.dumps({"error": f"Unknown book: {book_filter}"}))
            else:
                print(f"\033[31m[!] Error: Unknown book '{book_filter}'\033[0m")
            return 1

    # Resolve corpus filter if provided
    corpus_obj: Optional[CanonicalCorpus] = None
    if corpus_filter:
        corpus_obj = get_corpus(corpus_filter)
        if not corpus_obj:
            if json_output:
                print(json.dumps({"error": f"Unknown canonical corpus: {corpus_filter}"}))
            else:
                print(f"\033[31m[!] Error: Unknown canonical corpus '{corpus_filter}'\033[0m")
            return 1

    target_book_ids = list(corpus_obj.book_ids) if corpus_obj else ([book_obj.number] if book_obj else None)

    # Handle ledger maintenance operations
    book_label = book_obj.name if book_obj else "all"
    if clear_ledger:
        cleared = ledger.clear_ledger(book_id=target_book_ids)
        scope_name = f"Corpus {corpus_obj.corpus_id}: {corpus_obj.title}" if corpus_obj else (book_obj.name if book_obj else "all")
        if json_output:
            payload: Dict[str, Any] = {"cleared_units": cleared, "book": book_label, "scope": scope_name}
            if corpus_obj:
                payload["corpus"] = corpus_obj.to_dict()
            print(json.dumps(payload))
        else:
            print(f"Cleared {cleared} vector checkpoint records from ledger for {scope_name}.")
        return 0

    if reset_failed:
        reset_count = ledger.reset_failed(book_id=target_book_ids)
        scope_name = f"Corpus {corpus_obj.corpus_id}: {corpus_obj.title}" if corpus_obj else (book_obj.name if book_obj else "all")
        if json_output:
            payload = {"reset_units": reset_count, "book": book_label, "scope": scope_name}
            if corpus_obj:
                payload["corpus"] = corpus_obj.to_dict()
            print(json.dumps(payload))
        else:
            print(f"Reset {reset_count} failed vector checkpoint records back to PENDING for {scope_name}.")
        return 0

    # Status-only telemetry inspection
    if status_only:
        summary = ledger.get_summary(book_id=target_book_ids)
        scope_name = f"Corpus {corpus_obj.corpus_id}: {corpus_obj.title}" if corpus_obj else (f"Book: {book_obj.name}" if book_obj else "Scope: Whole Bible (1,304 Pericopes)")
        total = sum(summary.values())

        # Also count stored pericope embeddings
        cur = db.conn.cursor()
        if target_book_ids:
            ph = ",".join("?" for _ in target_book_ids)
            stored_cnt = cur.execute(
                f"""
                SELECT COUNT(*) FROM pericope_embeddings pe
                JOIN pericopes p ON pe.pericope_id = p.id
                WHERE p.book_id IN ({ph})
                """,
                target_book_ids,
            ).fetchone()[0]
        else:
            stored_cnt = cur.execute("SELECT COUNT(*) FROM pericope_embeddings").fetchone()[0]

        if json_output:
            payload = {
                "ledger_status": summary,
                "book": book_label,
                "scope": scope_name,
                "stored_embeddings": stored_cnt,
            }
            if corpus_obj:
                payload["corpus"] = corpus_obj.to_dict()
            print(json.dumps(payload, indent=2))
        else:
            print("=" * 72)
            print(f" Bible Engine — Vector Compilation Ledger Status ({scope_name})")
            print("=" * 72)
            print(f" Total Tracked Units:   {total}")
            print(f"  * Completed:          {summary.get('COMPLETED', 0)}")
            print(f"  * Pending:            {summary.get('PENDING', 0)}")
            print(f"  * In Progress:        {summary.get('IN_PROGRESS', 0)}")
            print(f"  * Failed:             {summary.get('FAILED', 0)}")
            print(f" Stored In SQLite:      {stored_cnt:,} pericope embeddings")
            if total > 0:
                pct = (summary.get('COMPLETED', 0) / total) * 100.0
                print(f" Overall Completion:   {pct:.1f}%")
            print("=" * 72)
        return 0

    # Initialize compiler
    compiler = BatchVectorCompiler(
        db=db,
        api_key=api_key,
        model_id=model_id,
        rate_limit_rpm=rate_limit_rpm,
        translation_id=translation_id,
    )

    pericopes = compiler.load_pericopes_for_scope(target_book_ids)
    scope_str = f"Corpus {corpus_obj.corpus_id}: {corpus_obj.title}" if corpus_obj else (book_obj.name if book_obj else "All Canonical Pericopes")

    if dry_run:
        if json_output:
            print(json.dumps({
                "dry_run": True,
                "total_units": len(pericopes),
                "scope": scope_str,
                "sample_units": [p["human_ref"] for p in pericopes[:5]],
            }, indent=2))
        else:
            print(f"[Dry Run] Prepared {len(pericopes)} pericope units for vector compilation across {scope_str}.")
            for p in pericopes[:8]:
                print(f"  - {p['human_ref']:<18} ({p['title'][:35]}): {p['genre']}")
            if len(pericopes) > 8:
                print(f"  ... and {len(pericopes) - 8} more pericopes.")
        return 0

    if not json_output:
        print("=" * 78)
        print(f" Bible Engine — Batch Vector Ingestion Engine ({scope_str})")
        print(f" Target Database: {db_path} | Model: {model_id} | Units: {len(pericopes)}")
        print("=" * 78)

    def telemetry_callback(
        pericope: Dict[str, Any],
        success: bool,
        error_or_msg: Optional[str],
        progress: VectorIngestionProgress,
    ) -> None:
        if json_output:
            return
        status_sym = "\033[32m[✓]\033[0m" if success else "\033[31m[✗]\033[0m"
        ref_str = f"{pericope['human_ref']:<18}"
        pct_str = f"{progress.percent_complete:5.1f}%"
        rpm_str = f"{progress.rate_per_minute:4.1f} u/m"
        title_snippet = pericope.get("title", "")[:35]
        print(f" {status_sym} {ref_str} [{pct_str} | {rpm_str}] {title_snippet}")
        if not success and error_or_msg and verbose:
            print(f"      \033[33mReason: {error_or_msg[:120]}\033[0m")

    progress = compiler.compile_scope(
        book_ids=target_book_ids,
        resume=resume,
        callback=telemetry_callback,
    )

    # Auto-update 2D projection coordinates for newly compiled vector embeddings
    if auto_project and progress.completed_units > 0 and progress.failed_units == 0:
        try:
            embeddings = db.get_all_pericope_embeddings()
            if embeddings:
                raw_vectors = [e.embedding for e in embeddings]
                coords = project_embeddings(raw_vectors, method=project_method)
                update_items = [(embeddings[i].pericope_id, coords[i][0], coords[i][1]) for i in range(len(embeddings))]
                updated_count = db.update_pericope_embedding_coordinates_batch(update_items)
                if not json_output:
                    print(f"  * 2D Coordinates:    {updated_count:,} pericopes projected & persisted ({project_method.upper()})")
        except Exception as proj_exc:
            if verbose and not json_output:
                print(f"  * 2D Projection:     Warning: {proj_exc}")

    if json_output:
        print(json.dumps({
            "status": "COMPLETED" if progress.failed_units == 0 else "COMPLETED_WITH_FAILURES",
            "progress": progress.to_dict(),
        }, indent=2))
    else:
        print("=" * 78)
        print(" Vector Compilation Summary:")
        print(f"  * Units Processed:   {progress.completed_units + progress.skipped_units} / {progress.total_units}")
        print(f"  * Completed:         {progress.completed_units}")
        print(f"  * Skipped (Resume):  {progress.skipped_units}")
        print(f"  * Failed:            {progress.failed_units}")
        print(f"  * Vector Embeddings: {progress.total_embeddings}")
        print(f"  * Duration:          {progress.duration_sec:.2f}s")
        print("=" * 78)

    return 0 if progress.failed_units == 0 else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point for tools/build_vector_db.py."""
    parser = argparse.ArgumentParser(
        description="Resumable Batch Vector Ingestion Engine & Whole-Bible Database Builder (ADR-083)"
    )
    parser.add_argument(
        "--db",
        type=str,
        default=str(DEFAULT_DB_PATH),
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--book",
        type=str,
        default=None,
        help="Filter vector compilation to a specific canonical book (e.g. 'Romans')",
    )
    parser.add_argument(
        "--corpus",
        type=str,
        default=None,
        help="Filter vector compilation to a canonical corpus (1-7, e.g. '1' for Pauline Epistles)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="compile_all",
        help="Compile vectors across all canonical pericopes in the database",
    )
    parser.add_argument(
        "--no-resume",
        action="store_false",
        dest="resume",
        default=True,
        help="Do not skip previously completed units; reprocess all",
    )
    parser.add_argument(
        "--reset-failed",
        action="store_true",
        help="Reset failed units in the vector ledger back to PENDING",
    )
    parser.add_argument(
        "--clear-ledger",
        action="store_true",
        help="Clear vector checkpoint records from the ledger",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Inspect current vector checkpoint ledger status without executing compilation",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview compilation units and passport formulation without generating embeddings",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_EMBEDDING_MODEL,
        help=f"Target embedding model (default: {DEFAULT_EMBEDDING_MODEL})",
    )
    parser.add_argument(
        "--rpm",
        type=float,
        default=60.0,
        help="Rate limit in requests per minute (default: 60.0)",
    )
    parser.add_argument(
        "--version",
        "-v_id",
        dest="version",
        type=str,
        default="WEB",
        help="Scripture translation for passage context (default: WEB)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON telemetry",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed progress and error messages",
    )
    parser.add_argument(
        "--no-project",
        action="store_false",
        dest="auto_project",
        default=True,
        help="Do not automatically calculate and persist 2D projection coordinates upon completion",
    )
    parser.add_argument(
        "--project-method",
        choices=["fastmap", "pca"],
        default="fastmap",
        help="Dimensionality reduction algorithm for auto-projecting (default: fastmap)",
    )

    args = parser.parse_args(argv)
    db_path = Path(args.db).resolve()

    return run_vector_build(
        db_path=db_path,
        book_filter=args.book,
        corpus_filter=args.corpus,
        compile_all=args.compile_all,
        resume=args.resume,
        reset_failed=args.reset_failed,
        clear_ledger=args.clear_ledger,
        status_only=args.status,
        dry_run=args.dry_run,
        translation_id=args.version,
        model_id=args.model,
        rate_limit_rpm=args.rpm,
        json_output=args.json,
        verbose=args.verbose,
        auto_project=args.auto_project,
        project_method=args.project_method,
    )


if __name__ == "__main__":
    sys.exit(main())
