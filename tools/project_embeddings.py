#!/usr/bin/env python3
"""Batch Semantic Embedding Projection Engine & 2D Scatter Map Generator CLI.

Zero-dependency CLI utility (Python 3 standard library only per ADR-003):
- Projects high-dimensional Scripture vector embeddings (e.g. 768-dim) into 2D coordinates (x, y).
- Supports FastMap (O(N) non-linear distance preserving) and Power Iteration PCA methods.
- Writes pre-computed 2D coordinates directly into SQLite (pericope_embeddings.map_x / map_y).
- Exports standalone vector SVGs and JSON map datasets.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.db import Database, DEFAULT_DB_PATH
from core.reference import get_book
from core.projection import (
    DEFAULT_MAP_HEIGHT,
    DEFAULT_MAP_MARGIN,
    DEFAULT_MAP_WIDTH,
    MapPoint,
    project_embeddings,
    render_scatter_map_svg,
)


def run_projection(
    db_path: Path,
    method: str = "fastmap",
    save: bool = True,
    force: bool = False,
    status_only: bool = False,
    export_svg: Optional[Path] = None,
    export_json: Optional[Path] = None,
    width: float = DEFAULT_MAP_WIDTH,
    height: float = DEFAULT_MAP_HEIGHT,
    margin: float = DEFAULT_MAP_MARGIN,
    json_output: bool = False,
    verbose: bool = False,
) -> int:
    """Execute 2D semantic embedding projection and coordinate persistence."""
    if not db_path.exists():
        msg = f"Database file not found: {db_path}"
        if json_output:
            print(json.dumps({"error": msg}))
        else:
            print(f"\033[31m[!] Error: {msg}\033[0m")
        return 1

    db = Database(db_path)

    # 1. Status Check
    if status_only:
        cur = db.conn.cursor()
        total_emb = db.count_pericope_embeddings()
        cur.execute("SELECT count(*) FROM pericope_embeddings WHERE map_x IS NOT NULL AND map_y IS NOT NULL")
        projected_count = cur.fetchone()[0]
        cur.close()

        status_data = {
            "total_pericope_embeddings": total_emb,
            "projected_2d_count": projected_count,
            "coverage_percent": round((projected_count / total_emb * 100.0) if total_emb > 0 else 0.0, 2),
            "status": "complete" if projected_count >= total_emb and total_emb > 0 else "pending",
        }

        if json_output:
            print(json.dumps(status_data, indent=2))
        else:
            print("=" * 70)
            print(" Scripture Semantic 2D Scatter Map Status")
            print("=" * 70)
            print(f" Total Pericope Embeddings: {total_emb:,}")
            print(f" Projected 2D Coordinates:  {projected_count:,} ({status_data['coverage_percent']}%)")
            print(f" Status:                    {status_data['status'].upper()}")
            print("=" * 70)
        return 0

    # 2. Fetch Embeddings
    embeddings = db.get_all_pericope_embeddings()
    if not embeddings:
        msg = "No pericope embeddings found in database. Run semantic compilation first."
        if json_output:
            print(json.dumps({"error": msg}))
        else:
            print(f"\033[33m[!] Notice: {msg}\033[0m")
        return 0

    if not force:
        already_projected = all(e.map_x is not None and e.map_y is not None for e in embeddings)
        if already_projected and not export_svg and not export_json:
            msg = f"All {len(embeddings):,} embeddings already have 2D coordinates. Use --force to reproject."
            if json_output:
                print(json.dumps({"status": "cached", "count": len(embeddings)}))
            else:
                print(f" [✓] {msg}")
            return 0

    if verbose and not json_output:
        print(f"[*] Projecting {len(embeddings):,} embeddings using {method.upper()}...")

    t0 = time.time()
    raw_vectors = [e.embedding for e in embeddings]
    coords = project_embeddings(
        raw_vectors,
        method=method,
        width=width,
        height=height,
        margin=margin,
    )
    elapsed = time.time() - t0

    # 3. Save Coordinates to Database
    updated = 0
    if save:
        update_items = [(embeddings[i].pericope_id, coords[i][0], coords[i][1]) for i in range(len(embeddings))]
        updated = db.update_pericope_embedding_coordinates_batch(update_items)

    # 4. Build MapPoint objects
    map_points = []
    pericopes_by_id = {p.id: p for p in db.get_all_pericopes()}
    for i, e in enumerate(embeddings):
        p_obj = pericopes_by_id.get(e.pericope_id)
        book_id = e.start_canonical_id // 1_000_000
        book_obj = get_book(book_id) if book_id else None
        map_points.append(
            MapPoint(
                entity_id=e.pericope_id,
                human_ref=e.human_ref,
                title=p_obj.title if p_obj else e.human_ref,
                book_id=book_id,
                book_name=book_obj.name if book_obj else "Unknown",
                testament=book_obj.testament if book_obj else "OT",
                genre=p_obj.genre if p_obj and p_obj.genre else "Other",
                x=coords[i][0],
                y=coords[i][1],
                redemptive_summary=p_obj.redemptive_summary if p_obj else "",
            )
        )

    # 5. Optional Exports
    if export_svg:
        svg_content = render_scatter_map_svg(map_points, width=int(width), height=int(height))
        export_svg.parent.mkdir(parents=True, exist_ok=True)
        export_svg.write_text(svg_content, encoding="utf-8")
        if verbose and not json_output:
            print(f"[*] Exported vector SVG to: {export_svg}")

    if export_json:
        export_json.parent.mkdir(parents=True, exist_ok=True)
        export_json.write_text(
            json.dumps({"count": len(map_points), "points": [p.to_dict() for p in map_points]}, indent=2),
            encoding="utf-8",
        )
        if verbose and not json_output:
            print(f"[*] Exported JSON map dataset to: {export_json}")

    result_data = {
        "status": "success",
        "method": method,
        "count": len(embeddings),
        "saved_to_db": updated if save else 0,
        "duration_sec": round(elapsed, 4),
    }

    if json_output:
        print(json.dumps(result_data, indent=2))
    else:
        print(f" [✓] Projected {len(embeddings):,} embeddings in {elapsed:.3f}s via {method.upper()}.")
        if save:
            print(f" [✓] Saved coordinates for {updated:,} pericopes into SQLite database ({db_path.name}).")
        if export_svg:
            print(f" [✓] Wrote SVG map to {export_svg}")
        if export_json:
            print(f" [✓] Wrote JSON map to {export_json}")

    return 0


def main() -> int:
    """Parse CLI arguments and dispatch projection."""
    parser = argparse.ArgumentParser(
        description="Batch Semantic Embedding Projection Engine & 2D Scatter Map Generator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite database")
    parser.add_argument("--method", choices=["fastmap", "pca"], default="fastmap", help="Projection algorithm")
    parser.add_argument("--save", action="store_true", default=True, help="Save coordinates to SQLite database")
    parser.add_argument("--no-save", dest="save", action="store_false", help="Do not write coordinates to SQLite")
    parser.add_argument("--force", action="store_true", help="Force recalculation even if coordinates exist")
    parser.add_argument("--status", action="store_true", help="Show current coordinate coverage status")
    parser.add_argument("--export-svg", type=Path, help="Export standalone SVG scatter map to path")
    parser.add_argument("--export-json", type=Path, help="Export JSON dataset of map points")
    parser.add_argument("--width", type=float, default=DEFAULT_MAP_WIDTH, help="Viewport canvas width")
    parser.add_argument("--height", type=float, default=DEFAULT_MAP_HEIGHT, help="Viewport canvas height")
    parser.add_argument("--margin", type=float, default=DEFAULT_MAP_MARGIN, help="Viewport margin padding")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose telemetry")

    args = parser.parse_args()
    return run_projection(
        db_path=args.db,
        method=args.method,
        save=args.save,
        force=args.force,
        status_only=args.status,
        export_svg=args.export_svg,
        export_json=args.export_json,
        width=args.width,
        height=args.height,
        margin=args.margin,
        json_output=args.json,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
