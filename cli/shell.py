"""Interactive Scripture REPL Shell for sovereign, offline Bible study.

Zero external dependencies (Python 3 standard library only per ADR-003).
Provides an interactive command loop powered by cmd.Cmd and readline:
  - Direct passage citation lookup (e.g. 'John 3:16', 'Rom 8:28-30')
  - Full-text search (/search <query>) with color token highlighting
  - Multi-translation comparison (/compare <ref> [versions])
  - Live session settings: /theme, /version, /margin, /flow, /box
  - Built-in diagnostics: /doctor, /summary, /versions
"""

import cmd
import os
from pathlib import Path
import re
import shlex
import sys
from typing import List, Optional, Sequence

from core.db import Database, SearchResult
from core.reference import ALL_BOOKS, Book, BOOKS, parse_reference, Reference
from core.terminal import (
    BOLD,
    BOLD_GOLD,
    CYAN,
    DIM,
    RESET,
    THEMES,
    format_citation_header,
    format_aligned_comparison_styled,
    format_scripture_passage,
    get_terminal_width,
    should_use_color,
    strip_ansi,
)


BANNER = """
╔════════════════════════════════════════════════════════════════════════════════╗
║                   Bible Engine — Sovereign Scripture Shell                    ║
║         Offline-First Sovereign Scripture & Semantic Knowledge Platform        ║
╚════════════════════════════════════════════════════════════════════════════════╝
 Type any scripture passage to read (e.g. 'John 3:16', 'Rom 8:28-30', 'Psalm 23')
 Type '/search <query>' to search or '/compare <ref>' to compare translations
 Type '/help' for command reference, or 'exit' / Ctrl+D to quit.
"""


class BibleShell(cmd.Cmd):
    """Interactive Scripture Study REPL Shell."""

    intro = BANNER
    prompt = "bible> "

    def __init__(
        self,
        db_path: Optional[Path] = None,
        translation_id: str = "WEB",
        theme: str = "sacred",
        margin: int = 2,
        width: Optional[int] = None,
        flow: bool = False,
        box: bool = True,
        color: Optional[bool] = None,
        database: Optional[Database] = None,
        stdin=None,
        stdout=None,
    ) -> None:
        super().__init__(stdin=stdin, stdout=stdout)
        self.db_path = db_path or Path(__file__).resolve().parent.parent / "data" / "bible.db"
        self.translation_id = translation_id.upper()
        self.theme = theme
        self.margin = margin
        self.width = width
        self.flow = flow
        self.box = box
        self.use_color = should_use_color() if color is None else color

        # Database connection
        self.db: Optional[Database] = database
        self._owns_database = database is None
        if self.db is None:
            self._init_db()
        self._update_prompt()

        # Web server daemon reference
        self._server: Optional[Any] = None
        self._server_thread: Optional[Any] = None

    def _init_db(self) -> None:
        """Initialize or reopen SQLite database connection."""
        if self.db is not None and getattr(self, "_owns_database", True):
            self.db.close()
        self.db = Database(self.db_path, auto_init=True, check_same_thread=False)
        self._owns_database = True

    def _update_prompt(self) -> None:
        """Update prompt with current translation and color styling."""
        v_tag = f"[{self.translation_id}]"
        if self.use_color and self.theme != "plain":
            self.prompt = f"\033[1;33mbible\033[0m \033[2m{v_tag}\033[0m> "
        else:
            self.prompt = f"bible {v_tag}> "

    def close(self) -> None:
        """Close the underlying database connection and stop background server."""
        if getattr(self, "_server", None) is not None:
            try:
                self._server.shutdown()
            except Exception:
                pass
            self._server = None
            self._server_thread = None

        if self.db is not None and getattr(self, "_owns_database", True):
            self.db.close()
            self.db = None

    def __enter__(self) -> "BibleShell":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def emptyline(self) -> bool:
        """Do nothing on empty line."""
        return False

    def default(self, line: str) -> None:
        """Handle lines that do not match standard cmd methods."""
        line = line.strip()
        if not line:
            return

        # Check for leading slash commands (e.g. /search, /compare, /get)
        if line.startswith("/"):
            parts = line[1:].split(None, 1)
            cmd_name = parts[0].lower()
            arg_str = parts[1] if len(parts) > 1 else ""

            handler = (
                getattr(self, f"do_{cmd_name}", None)
                or getattr(self, f"do_{cmd_name.replace('-', '_')}", None)
            )
            if handler:
                handler(arg_str)
                return
            else:
                self.stdout.write(f"Unknown slash command: /{cmd_name}. Type '/help' for commands.\n")
                return

        # If line parses as a canonical scripture reference, fetch and display passage
        try:
            ref = parse_reference(line)
        except (ValueError, TypeError):
            ref = None
        if ref is not None:
            self._display_reference(ref)
            return

        # If not a reference and doesn't match a command, suggest search or help
        self.stdout.write(
            f"Unrecognized input: '{line}'.\n"
            f"  - Enter a valid scripture citation (e.g. 'John 3:16', 'Rom 8:28-30')\n"
            f"  - Or search scripture: /search {line}\n"
            f"  - Type '/help' for full command reference.\n"
        )

    # --------------------------------------------------------------------------
    # Scripture Commands
    # --------------------------------------------------------------------------

    def _display_reference(self, ref: Reference) -> None:
        """Fetch and render scripture reference with active styling options."""
        if self.db is None:
            self._init_db()

        try:
            verses, effective_trans, is_fallback = self.db.get_verses_with_fallback(
                ref, translation_id=self.translation_id, fallback_id="WEB"
            )
        except Exception as exc:
            self.stdout.write(f"Database error querying {ref}: {exc}\n")
            return

        if not verses:
            self.stdout.write(f"No verses found for reference '{ref}' in {self.translation_id}.\n")
            return

        if is_fallback:
            self.stdout.write(
                f"[Notice: Translation '{self.translation_id}' not available; showing fallback '{effective_trans}']\n"
            )

        # Show pericope heading if available
        from core.pericopes import PericopeService
        from core.terminal import format_pericope_banner
        p_svc = PericopeService(self.db)
        pericopes = p_svc.get_pericopes_for_passage(ref)
        if pericopes:
            p_banners = "\n".join(format_pericope_banner(p, styling=self.use_color, width=self.width) for p in pericopes)
            self.stdout.write(f"\n{' ' * self.margin}{p_banners}\n")

        passage = format_scripture_passage(
            verses=verses,
            show_verse_numbers=True,
            show_header=True,
            fallback_for=self.translation_id if is_fallback else None,
            margin=self.margin,
            width=self.width,
            flow=self.flow,
            color=self.use_color,
            theme_name=self.theme,
            box_header=self.box,
        )

        self.stdout.write("\n" + passage + "\n\n")

    def do_get(self, arg: str) -> None:
        """Lookup scripture passage: get <reference> (e.g. get John 3:16)."""
        arg = arg.strip()
        if not arg:
            self.stdout.write("Usage: get <reference> (e.g. get John 3:16)\n")
            return
        ref = parse_reference(arg)
        if ref is None:
            self.stdout.write(f"Could not parse '{arg}' as a canonical scripture reference.\n")
            return
        self._display_reference(ref)

    def do_search(self, arg: str) -> None:
        """Search scripture text: search <query> [-e] [-b BOOK] [-n LIMIT]"""
        arg = arg.strip()
        if not arg:
            self.stdout.write("Usage: /search <query> (e.g. /search light of the world)\n")
            return

        exact = False
        book = None
        limit = 10
        raw_tokens = []

        try:
            tokens = shlex.split(arg)
        except ValueError:
            tokens = arg.split()

        idx = 0
        while idx < len(tokens):
            t = tokens[idx]
            if t in ("-e", "--exact"):
                exact = True
                idx += 1
            elif t in ("-b", "--book") and idx + 1 < len(tokens):
                book = tokens[idx + 1]
                idx += 2
            elif t in ("-n", "--limit") and idx + 1 < len(tokens):
                try:
                    limit = int(tokens[idx + 1])
                except ValueError:
                    pass
                idx += 2
            else:
                raw_tokens.append(t)
                idx += 1

        query = " ".join(raw_tokens).strip()
        if not query:
            self.stdout.write("Error: Search query required.\n")
            return

        if self.db is None:
            self._init_db()

        results = self.db.search_text(
            query=query,
            translation_id=self.translation_id,
            book=book,
            limit=limit,
            exact=exact,
        )
        total_matches = self.db.count_search_matches(
            query=query,
            translation_id=self.translation_id,
            book=book,
            exact=exact,
        )

        from cli.main import format_search_results
        output = format_search_results(
            results=results,
            query=query,
            total_count=total_matches,
            translation_label=self.translation_id,
            show_snippets=True,
            color=self.use_color,
            limit=limit,
        )
        self.stdout.write("\n" + output + "\n\n")

    def do_find(self, arg: str) -> None:
        """Alias for /search."""
        self.do_search(arg)

    def do_compare(self, arg: str) -> None:
        """Compare passage across versions: compare <reference> [version1,version2]"""
        arg = arg.strip()
        if not arg:
            self.stdout.write("Usage: /compare <reference> [versions] (e.g. /compare 'John 1:1' WEB,KJV)\n")
            return

        parts = shlex.split(arg) if "'" in arg or '"' in arg else arg.split(None, 1)
        ref_str = parts[0]
        versions_str = parts[1] if len(parts) > 1 else f"{self.translation_id},KJV"

        ref = parse_reference(ref_str)
        if ref is None:
            self.stdout.write(f"Could not parse '{ref_str}' as a scripture reference.\n")
            return

        v_list = [v.strip().upper() for v in versions_str.replace(",", " ").split() if v.strip()]
        if not v_list:
            v_list = [self.translation_id, "KJV"]

        if self.db is None:
            self._init_db()

        comp_dict = self.db.compare_verses(ref, v_list, fallback_id="WEB")
        output = format_aligned_comparison_styled(
            ref_title=ref.format(),
            comparison_data=comp_dict,
            show_header=True,
            margin=self.margin,
            width=self.width,
            box_header=self.box,
            theme_name=self.theme,
            color=self.use_color,
        )
        self.stdout.write("\n" + output + "\n\n")

    def do_tag(self, arg: str) -> None:
        """Semantic tagging: /tag <add|list|show|for|remove|delete|stats|seed> [args...]"""
        if self.db is None:
            self._init_db()

        from core.tags import TaggingService
        from core.terminal import format_tag_table, format_tagged_passages
        svc = TaggingService(self.db)

        try:
            tokens = shlex.split(arg) if arg else []
        except ValueError:
            tokens = arg.split()

        if not tokens:
            summaries = svc.list_tags()
            self.stdout.write("\n" + format_tag_table(summaries, styling=self.use_color) + "\n\n")
            return

        action = tokens[0].lower()
        if action == "list":
            cat = tokens[1] if len(tokens) > 1 else None
            summaries = svc.list_tags(category=cat)
            self.stdout.write("\n" + format_tag_table(summaries, styling=self.use_color) + "\n\n")

        elif action == "show":
            if len(tokens) < 2:
                self.stdout.write("Usage: /tag show <tag_name> [limit]\n")
                return
            tag_name = tokens[1]
            limit = int(tokens[2]) if len(tokens) > 2 and tokens[2].isdigit() else 20
            passages = svc.get_passages_for_tag(tag_name, translation_id=self.translation_id, limit=limit)
            tag_rec = svc.get_tag(tag_name)
            if not tag_rec:
                self.stdout.write(f"Tag '{tag_name}' not found.\n")
                return
            hdr = f"Tag: {tag_rec.name} ({tag_rec.category}) — {len(passages)} passage(s)"
            if tag_rec.description:
                hdr += f"\nDescription: {tag_rec.description}"
            self.stdout.write("\n" + hdr + "\n\n")
            self.stdout.write(format_tagged_passages(passages, styling=self.use_color) + "\n\n")

        elif action == "add":
            if len(tokens) < 3:
                self.stdout.write("Usage: /tag add <reference> <tag1> [tag2...]\n")
                return
            ref_str = tokens[1]
            try:
                ref = parse_reference(ref_str)
            except Exception:
                ref = None
            if not ref:
                self.stdout.write(f"Could not parse '{ref_str}' as a scripture reference.\n")
                return
            tag_names = tokens[2:]
            recs = svc.tag_passage(ref, tag_names, source="user")
            self.stdout.write(f"Successfully tagged {ref.format()} with {len(recs)} tag(s):\n")
            for r in recs:
                self.stdout.write(f"  • {r.tag_name} [{r.human_ref}]\n")
            self.stdout.write("\n")

        elif action == "for":
            if len(tokens) < 2:
                self.stdout.write("Usage: /tag for <reference>\n")
                return
            ref_str = tokens[1]
            try:
                ref = parse_reference(ref_str)
            except Exception:
                ref = None
            if not ref:
                self.stdout.write(f"Could not parse '{ref_str}' as a scripture reference.\n")
                return
            records = svc.get_tags_for_passage(ref)
            if not records:
                self.stdout.write(f"No tags found for {ref.format()}.\n")
            else:
                self.stdout.write(f"Tags for {ref.format()}:\n")
                for r in records:
                    star = " ★" if r.starred else ""
                    self.stdout.write(f"  🏷  {r.tag_name} [{r.human_ref}]{star}\n")
            self.stdout.write("\n")

        elif action == "remove":
            if len(tokens) < 3:
                self.stdout.write("Usage: /tag remove <reference> <tag_name>\n")
                return
            ref_str = tokens[1]
            try:
                ref = parse_reference(ref_str)
            except Exception:
                ref = None
            if not ref:
                self.stdout.write(f"Could not parse '{ref_str}' as a scripture reference.\n")
                return
            tag_name = tokens[2]
            deleted = svc.untag_passage(ref, tag_name)
            if deleted > 0:
                self.stdout.write(f"Removed tag '{tag_name}' from {ref.format()}.\n")
            else:
                self.stdout.write(f"No tag association found for '{tag_name}' on {ref.format()}.\n")

        elif action == "delete":
            if len(tokens) < 2:
                self.stdout.write("Usage: /tag delete <tag_name>\n")
                return
            tag_name = tokens[1]
            ok = svc.delete_tag(tag_name)
            if ok:
                self.stdout.write(f"Deleted tag '{tag_name}' and all its passage associations.\n")
            else:
                self.stdout.write(f"Tag '{tag_name}' not found.\n")

        elif action == "stats":
            tag_name = tokens[1] if len(tokens) > 1 else None
            stats = self.db.get_tag_stats(tag_name=tag_name)
            if not stats:
                self.stdout.write("No tags found.\n")
            else:
                for s in stats:
                    self.stdout.write(f"Tag: {s['name']} ({s['category']})\n")
                    self.stdout.write(f"  Passages: {s['passage_count']}\n")
                    self.stdout.write(f"  Starred:  {s['starred_count']}\n")
                    self.stdout.write(f"  Books:    {s['distinct_books']}\n\n")

        elif action == "seed":
            count = svc.seed_canonical_taxonomies()
            self.stdout.write(f"Successfully seeded {count} canonical theological and redemptive-historical tags.\n")

        elif action == "prompt":
            if len(tokens) < 2:
                self.stdout.write("Usage: /tag prompt <reference>\n")
                return
            ref_str = " ".join(tokens[1:])
            try:
                ref = parse_reference(ref_str)
            except Exception as exc:
                self.stdout.write(f"Could not parse '{ref_str}': {exc}\n")
                return
            from tools.tag_generator import fetch_passage_text
            from core.tag_prompts import generate_tagging_prompt
            try:
                ref_obj, text = fetch_passage_text(self.db, ref, translation_id=self.translation_id)
                prompt = generate_tagging_prompt(ref_obj, text, translation_id=self.translation_id)
                self.stdout.write(f"\n{prompt}\n\n")
            except Exception as exc:
                self.stdout.write(f"Error generating prompt: {exc}\n")

        elif action in ("density", "ribbon"):
            from core.terminal import format_topic_density_table, format_redemptive_ribbon_ascii
            is_ribbon = action == "ribbon" or "--ribbon" in tokens or "-r" in tokens
            filtered_tokens = [t for t in tokens[1:] if t not in ("--ribbon", "-r")]
            tag_name = filtered_tokens[0] if filtered_tokens else None
            densities = svc.get_topic_density_per_book(tag_name=tag_name, min_passages=0 if is_ribbon else 1)
            filter_str = f" for '{tag_name}'" if tag_name else ""
            if is_ribbon:
                self.stdout.write("\n" + format_redemptive_ribbon_ascii(densities, styling=self.use_color, tag_name=tag_name) + "\n\n")
            else:
                self.stdout.write(f"Topic Density Distribution{filter_str}:\n\n")
                self.stdout.write(format_topic_density_table(densities, styling=self.use_color) + "\n\n")

        elif action in ("co-occurrence", "co-occur", "matrix"):
            from core.terminal import format_tag_co_occurrence_table
            tags_filter = tokens[1:] if len(tokens) > 1 else None
            matrix_res = svc.get_tag_co_occurrences(tags=tags_filter, min_co_occurrences=1)
            self.stdout.write("Tag Co-Occurrence Analysis:\n\n")
            self.stdout.write(format_tag_co_occurrence_table(matrix_res.pair_metrics, styling=self.use_color) + "\n\n")

        elif action in ("relevance", "rank"):
            if len(tokens) < 2:
                self.stdout.write("Usage: /tag relevance <tag1> [tag2 ...]\n")
                return
            from core.terminal import format_verse_relevance_table
            tags_list = tokens[1:]
            rankings = svc.score_verse_relevance(tags=tags_list, translation_id=self.translation_id, limit=10)
            self.stdout.write(f"Scripture Passage Relevance Rankings for {tags_list}:\n\n")
            self.stdout.write(format_verse_relevance_table(rankings, styling=self.use_color) + "\n\n")

        else:
            self.stdout.write(f"Unknown tag action '{action}'. Available: add, list, show, for, remove, delete, stats, density, ribbon, co-occurrence, relevance, seed, prompt\n")

    def do_tags(self, arg: str) -> None:
        """Alias for /tag."""
        self.do_tag(arg)

    def do_ribbon(self, arg: str) -> None:
        """Display canonical Redemptive Ribbon ASCII heatmap across 66 books: /ribbon [tag_name]"""
        self.do_tag(f"ribbon {arg}".strip())

    def do_pericopes(self, arg: str) -> None:
        """Inspect canonical pericopes and redemptive summaries: /pericopes [passage|book|keyword]"""
        if self.db is None:
            self._init_db()

        from core.pericopes import PericopeService
        from core.terminal import format_pericope_table
        from core.reference import get_book
        svc = PericopeService(self.db)
        arg = arg.strip()

        if not arg:
            pericopes = self.db.get_pericopes_for_book(None)
            self.stdout.write(f"\nAll Canonical Pericopes ({len(pericopes)} entries):\n\n")
            self.stdout.write(format_pericope_table(pericopes, styling=self.use_color) + "\n\n")
            return

        ref = parse_reference(arg)
        if ref:
            pericopes = svc.get_pericopes_for_passage(ref)
            desc = f"for '{ref.format()}'"
        else:
            book_match = get_book(arg)
            if book_match:
                pericopes = svc.get_pericopes_for_book(book_match.name)
                desc = f"in {book_match.name}"
            else:
                all_p = self.db.get_pericopes_for_book(None)
                q_lower = arg.lower()
                pericopes = [p for p in all_p if q_lower in p.title.lower() or (p.redemptive_summary and q_lower in p.redemptive_summary.lower())]
                desc = f"matching '{arg}'"

        self.stdout.write(f"\nCanonical Pericopes {desc} ({len(pericopes)} entries):\n\n")
        self.stdout.write(format_pericope_table(pericopes, styling=self.use_color) + "\n\n")

    def do_pericope(self, arg: str) -> None:
        """Alias for /pericopes."""
        self.do_pericopes(arg)

    def do_chapters(self, arg: str) -> None:
        """Display chapter-by-chapter topic density drill-down: /chapters <book> [tag_name]"""
        if self.db is None:
            self._init_db()

        tokens = arg.strip().split()
        if not tokens:
            self.stdout.write("Usage: /chapters <book> [tag_name]\nExample: /chapters Genesis Covenant\n")
            return

        from core.tags import TaggingService
        from core.terminal import format_chapter_density_grid
        from core.reference import get_book
        svc = TaggingService(self.db)

        book_match = get_book(tokens[0])
        if not book_match:
            self.stdout.write(f"Unknown book '{tokens[0]}'.\n")
            return

        tag_name = tokens[1] if len(tokens) > 1 else None
        chapters = svc.get_topic_density_per_chapter(book_match.name, tag_name=tag_name)
        self.stdout.write("\n" + format_chapter_density_grid(
            book_name=book_match.name,
            chapters=chapters,
            styling=self.use_color,
            tag_name=tag_name,
        ) + "\n\n")

    def do_chapter(self, arg: str) -> None:
        """Alias for /chapters."""
        self.do_chapters(arg)

    # --------------------------------------------------------------------------
    # Cross-Reference Commands
    # --------------------------------------------------------------------------

    def do_crossref(self, arg: str) -> None:
        """Cross-reference explorer: /crossref [for|link|unlink|list|path|stats|seed] ..."""
        if self.db is None:
            self._init_db()

        from core.crossref import CrossReferenceService, RelationshipType
        from core.terminal import format_cross_references, format_cross_reference_table

        try:
            tokens = shlex.split(arg) if arg else []
        except ValueError:
            tokens = arg.split()

        if not tokens:
            self.stdout.write(
                "Usage: /crossref <action> [args]\n"
                "Actions: for <ref>, link <src> <tgt> [type], unlink <src> <tgt>, list, path <src> <tgt>, stats, seed\n"
            )
            return

        action = tokens[0].lower()
        svc = CrossReferenceService(self.db)

        if action == "for":
            if len(tokens) < 2:
                self.stdout.write("Usage: /crossref for <reference> [relationship_type]\n")
                return
            # Allow multi-word citations if unquoted e.g. /crossref for Genesis 3:15
            # If last token matches a relationship type, treat as type
            if len(tokens) >= 3 and RelationshipType.is_valid(tokens[-1]):
                rel_type = tokens[-1].lower()
                ref_str = " ".join(tokens[1:-1])
            else:
                rel_type = None
                ref_str = " ".join(tokens[1:])
            try:
                ref = parse_reference(ref_str)
            except Exception:
                ref = None
            if not ref:
                self.stdout.write(f"Could not parse '{ref_str}' as a scripture reference.\n")
            hydrated = svc.get_hydrated_cross_references(
                reference=ref,
                translation_id=self.translation_id,
                relationship_type=rel_type,
                bidirectional=True,
            )
            if not hydrated:
                self.stdout.write(f"No cross-references found for {ref.format()}.\n")
            else:
                self.stdout.write(f"Cross-References for {ref.format()} ({len(hydrated)} passages):\n\n")
                self.stdout.write(format_cross_references(hydrated, styling=self.use_color) + "\n\n")

        elif action == "link":
            if len(tokens) < 3:
                self.stdout.write("Usage: /crossref link <source_ref> <target_ref> [type]\n")
                return
            try:
                src_ref = parse_reference(tokens[1])
                tgt_ref = parse_reference(tokens[2])
            except Exception as exc:
                self.stdout.write(f"Error parsing scripture references: {exc}\n")
                return
            rel_type = tokens[3].lower() if len(tokens) > 3 else "thematic"
            try:
                rec = svc.link_passages(src_ref, tgt_ref, relationship_type=rel_type)
                self.stdout.write(f"Linked {rec.source_human_ref} ➜ {rec.target_human_ref} [{rec.relationship_type}] (id: {rec.id})\n")
            except Exception as exc:
                self.stdout.write(f"Link error: {exc}\n")

        elif action == "unlink":
            if len(tokens) < 3:
                self.stdout.write("Usage: /crossref unlink <source_ref> <target_ref>\n")
                return
            try:
                src_ref = parse_reference(tokens[1])
                tgt_ref = parse_reference(tokens[2])
            except Exception as exc:
                self.stdout.write(f"Error parsing scripture references: {exc}\n")
                return
            deleted = svc.unlink_passages(src_ref, tgt_ref)
            if deleted > 0:
                self.stdout.write(f"Removed {deleted} cross-reference edge(s) between {src_ref.format()} and {tgt_ref.format()}.\n")
            else:
                self.stdout.write(f"No cross-reference edges found between {src_ref.format()} and {tgt_ref.format()}.\n")

        elif action == "list":
            rel_type = tokens[1].lower() if len(tokens) > 1 else None
            edges = svc.list_all_cross_references(relationship_type=rel_type, limit=50)
            self.stdout.write(format_cross_reference_table(edges, styling=self.use_color) + "\n")

        elif action == "path":
            if len(tokens) < 3:
                self.stdout.write("Usage: /crossref path <source_ref> <target_ref> [max_depth]\n")
                return
            try:
                src_ref = parse_reference(tokens[1])
                tgt_ref = parse_reference(tokens[2])
            except Exception as exc:
                self.stdout.write(f"Error parsing scripture references: {exc}\n")
                return
            depth = int(tokens[3]) if len(tokens) > 3 and tokens[3].isdigit() else 3
            path = svc.find_path(src_ref, tgt_ref, max_depth=depth)
            if not path:
                self.stdout.write(f"No cross-reference path found connecting {src_ref.format()} and {tgt_ref.format()} within depth {depth}.\n")
            else:
                self.stdout.write(f"Cross-Reference Path ({len(path)} hop{'s' if len(path) != 1 else ''}):\n")
                for idx, step in enumerate(path, 1):
                    icon = RelationshipType.get_icon(step.relationship_type)
                    label = RelationshipType.get_label(step.relationship_type)
                    self.stdout.write(f"  {idx}. {step.source_human_ref} ➜ {step.target_human_ref}  {icon} [{label}]\n")
                self.stdout.write("\n")

        elif action == "stats":
            summary = svc.get_summary_statistics()
            self.stdout.write("Cross-Reference Knowledge Graph Statistics:\n")
            self.stdout.write(f"  Total Edges:       {summary.total_edges}\n")
            self.stdout.write(f"  Distinct Passages: {summary.distinct_sources + summary.distinct_targets}\n")
            for rel, cnt in summary.by_relationship_type.items():
                self.stdout.write(f"  - {rel}: {cnt}\n")
            self.stdout.write("\n")

        elif action == "seed":
            count = svc.seed_canonical_cross_references()
            self.stdout.write(f"Successfully seeded {count} canonical cross-reference edge(s).\n")

        else:
            self.stdout.write(f"Unknown crossref action '{action}'. Available: for, link, unlink, list, path, stats, seed\n")

    def do_xref(self, arg: str) -> None:
        """Alias for /crossref."""
        self.do_crossref(arg)

    def do_refs(self, arg: str) -> None:
        """Alias for /crossref."""
        self.do_crossref(arg)

    def do_arcs(self, arg: str) -> None:
        """Render pure vector SVG Typological Arc Network & explore fulfillments: /arcs [-t TYPE] [-b BOOK] [--svg OUT.svg]"""
        if self.db is None:
            self._init_db()

        from core.arcs import build_arc_network
        from core.crossref import RelationshipType
        from core.reference import ALL_BOOKS, get_book

        rel_type = None
        book = None
        svg_out = None
        theme = "obsidian"

        tokens = shlex.split(arg) if arg.strip() else []
        idx = 0
        while idx < len(tokens):
            tok = tokens[idx]
            if tok in ("-t", "--type") and idx + 1 < len(tokens):
                rel_type = tokens[idx + 1]
                idx += 2
            elif tok in ("-b", "--book") and idx + 1 < len(tokens):
                book = tokens[idx + 1]
                idx += 2
            elif tok in ("-o", "--svg") and idx + 1 < len(tokens):
                svg_out = tokens[idx + 1]
                idx += 2
            elif tok in ("--theme",) and idx + 1 < len(tokens):
                theme = tokens[idx + 1]
                idx += 2
            elif not tok.startswith("-") and rel_type is None:
                if RelationshipType.is_valid(tok):
                    rel_type = tok
                elif get_book(tok):
                    book = tok
                elif tok.lower() in ("prophecy", "prophecies"):
                    rel_type = "prophecy_fulfillment"
                else:
                    rel_type = tok
                idx += 1
            else:
                idx += 1

        net = build_arc_network(
            self.db,
            relationship_type=rel_type,
            book_filter=book,
            theme=theme,
        )

        if svg_out:
            svg_content = net.render_svg(standalone=True, interactive=True)
            out_p = Path(svg_out).resolve()
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(svg_content, encoding="utf-8")
            self.stdout.write(f"Exported vector SVG ({len(svg_content):,} bytes) to '{out_p}'.\n\n")

        self.stdout.write("\n" + net.render_terminal_summary(color=self.use_color) + "\n\n")

    def do_arc(self, arg: str) -> None:
        """Alias for /arcs."""
        self.do_arcs(arg)

    def do_typology(self, arg: str) -> None:
        """Alias for /arcs -t typology."""
        self.do_arcs("-t typology " + arg)

    def complete_arcs(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Autocompletion for /arcs command."""
        from core.reference import ALL_BOOKS
        types = ["typology", "prophecy_fulfillment", "quotation", "thematic", "allusion"]
        books = [b.name for b in ALL_BOOKS]
        opts = types + books + ["--svg", "--type", "--book", "--theme", "--testament"]
        return [o for o in opts if o.lower().startswith(text.lower())]

    def do_slide(self, arg: str) -> None:
        """Generate visual verse slide: /slide <reference> [-o FILE] [-r RES] [-t THEME] [-f FORMAT]"""
        if self.db is None:
            self._init_db()

        tokens = shlex.split(arg) if arg.strip() else []
        if not tokens:
            self.stdout.write("Usage: /slide <reference> [-o FILE] [-r 4k|1080p] [-t THEME] [-f png|svg|jpg]\n"
                              "Example: /slide John 3:16 -o verse.png -t oled_black\n"
                              "Flags: --list-themes, --list-resolutions, --citation-color, --tags, --safe-area\n")
            return

        from core.render import (
            ImageMagickNotFoundError,
            PaginationConfig,
            RenderConfig,
            RenderError,
            SlideContent,
            format_resolution_table,
            format_theme_table,
            get_default_engine,
            get_theme,
            normalize_color,
            paginate_verses,
            parse_resolution,
        )

        if "--list-themes" in tokens:
            self.stdout.write("\n" + format_theme_table(styling=self.use_color) + "\n\n")
            return

        if "--list-resolutions" in tokens:
            self.stdout.write("\n" + format_resolution_table(styling=self.use_color) + "\n\n")
            return

        ref_tokens = []
        out_file = None
        res_preset = "4k"
        theme = "oled_black"
        out_fmt = None
        backend = "auto"
        font_family = None
        font_size = None
        line_spacing = 1.5
        text_align = "center"
        citation_style = "below"
        citation_color = None
        accent_color = None
        show_tags = False
        balance_lines = True
        optical_center = 0.45
        safe_area = 0.15
        open_viewer = False
        paginate_flag = False
        no_paginate_flag = False
        max_verses = None
        max_lines = None
        max_chars = None
        page_format = "{page} / {total}"
        show_indicator = True
        keep_citation = False
        output_dir = None

        idx = 0
        while idx < len(tokens):
            tok = tokens[idx]
            if tok in ("-o", "--output") and idx + 1 < len(tokens):
                out_file = tokens[idx + 1]
                idx += 2
            elif tok in ("-d", "--output-dir") and idx + 1 < len(tokens):
                output_dir = tokens[idx + 1]
                idx += 2
            elif tok in ("-r", "--resolution") and idx + 1 < len(tokens):
                res_preset = tokens[idx + 1]
                idx += 2
            elif tok in ("-t", "--theme") and idx + 1 < len(tokens):
                theme = tokens[idx + 1]
                idx += 2
            elif tok in ("-f", "--format") and idx + 1 < len(tokens):
                out_fmt = tokens[idx + 1]
                idx += 2
            elif tok == "--backend" and idx + 1 < len(tokens):
                backend = tokens[idx + 1]
                idx += 2
            elif tok == "--font" and idx + 1 < len(tokens):
                font_family = tokens[idx + 1]
                idx += 2
            elif tok == "--font-size" and idx + 1 < len(tokens):
                val_str = tokens[idx + 1].strip().lower()
                if val_str not in ("auto", "none", "fit"):
                    if val_str.endswith("pt") or val_str.endswith("px"):
                        val_str = val_str[:-2]
                    try:
                        font_size = float(val_str)
                    except ValueError:
                        pass
                idx += 2
            elif tok == "--line-spacing" and idx + 1 < len(tokens):
                try:
                    line_spacing = float(tokens[idx + 1])
                except ValueError:
                    pass
                idx += 2
            elif tok in ("-c", "--citation-color") and idx + 1 < len(tokens):
                citation_color = tokens[idx + 1]
                idx += 2
            elif tok == "--accent-color" and idx + 1 < len(tokens):
                accent_color = tokens[idx + 1]
                idx += 2
            elif tok == "--safe-area" and idx + 1 < len(tokens):
                sa_str = tokens[idx + 1].strip().rstrip("%")
                try:
                    sa_num = float(sa_str)
                    safe_area = sa_num / 100.0 if sa_num > 1.0 else sa_num
                except ValueError:
                    pass
                idx += 2
            elif tok == "--align" and idx + 1 < len(tokens):
                text_align = tokens[idx + 1].lower()
                idx += 2
            elif tok == "--citation-style" and idx + 1 < len(tokens):
                citation_style = tokens[idx + 1].lower()
                idx += 2
            elif tok == "--optical-center" and idx + 1 < len(tokens):
                try:
                    optical_center = float(tokens[idx + 1])
                except ValueError:
                    pass
                idx += 2
            elif tok == "--paginate":
                paginate_flag = True
                idx += 1
            elif tok == "--no-paginate":
                no_paginate_flag = True
                idx += 1
            elif tok == "--max-verses" and idx + 1 < len(tokens):
                try:
                    max_verses = int(tokens[idx + 1])
                except ValueError:
                    pass
                idx += 2
            elif tok == "--max-lines" and idx + 1 < len(tokens):
                try:
                    max_lines = int(tokens[idx + 1])
                except ValueError:
                    pass
                idx += 2
            elif tok == "--max-chars" and idx + 1 < len(tokens):
                try:
                    max_chars = int(tokens[idx + 1])
                except ValueError:
                    pass
                idx += 2
            elif tok == "--page-format" and idx + 1 < len(tokens):
                page_format = tokens[idx + 1]
                idx += 2
            elif tok == "--no-page-indicator":
                show_indicator = False
                idx += 1
            elif tok == "--keep-citation":
                keep_citation = True
                idx += 1
            elif tok == "--tags":
                show_tags = True
                idx += 1
            elif tok == "--open":
                open_viewer = True
                idx += 1
            elif tok == "--no-balance":
                balance_lines = False
                idx += 1
            else:
                ref_tokens.append(tok)
                idx += 1

        ref_str = " ".join(ref_tokens).strip()
        if not ref_str:
            self.stdout.write("Error: Scripture reference required.\n")
            return

        ref = parse_reference(ref_str)
        if ref is None:
            self.stdout.write(f"Error: Could not parse '{ref_str}' as a canonical scripture reference.\n")
            return

        verses, used_id, is_fallback = self.db.get_verses_with_fallback(ref, translation_id=self.translation_id)
        if not verses:
            self.stdout.write(f"Error: No verses found for '{ref.format()}' in translation '{self.translation_id}'.\n")
            return

        from core.pericopes import PericopeService
        pericope_svc = PericopeService(self.db)
        pericopes = pericope_svc.get_pericopes_for_passage(ref)
        pericope_title = pericopes[0].title if pericopes else None

        slide_tags: List[str] = []
        if show_tags:
            from core.tags import TaggingService
            tag_svc = TaggingService(self.db)
            active_tags = tag_svc.get_tags_for_passage(ref)
            slide_tags = [t.tag_name for t in active_tags if t.tag_name]

        verse_text = " ".join(v.text.strip() for v in verses)
        citation_str = ref.format()

        if out_file:
            dest_path = Path(out_file).resolve()
            ext = dest_path.suffix.lower().lstrip(".")
            if not out_fmt and ext in ("png", "jpg", "jpeg", "svg"):
                out_fmt = ext
        else:
            out_fmt = out_fmt or "png"
            safe_stem = re.sub(r"[^a-zA-Z0-9_]+", "_", citation_str).strip("_").lower()
            dest_path = Path.cwd() / f"slide_{safe_stem}.{out_fmt}"

        out_fmt = out_fmt or "png"
        safe_stem = re.sub(r"[^a-zA-Z0-9_]+", "_", citation_str).strip("_").lower()
        w, h = parse_resolution(res_preset)
        theme_obj = get_theme(theme)

        config = RenderConfig(
            width=w,
            height=h,
            theme=theme_obj,
            safe_area_pct=safe_area,
            font_family=font_family,
            font_size=font_size,
            line_spacing=line_spacing,
            text_align=text_align,
            citation_style=citation_style,
            citation_color=normalize_color(citation_color),
            accent_color=normalize_color(accent_color),
            balance_lines=balance_lines,
            optical_center_pct=optical_center,
            show_tags=show_tags,
            backend=backend,
            output_format=out_fmt,
        )

        if no_paginate_flag:
            pagination = PaginationConfig(enabled=False)
        else:
            pagination = PaginationConfig(
                enabled=True,
                mode="always" if paginate_flag else "auto",
                max_verses_per_slide=max_verses,
                max_lines_per_slide=max_lines,
                max_chars_per_slide=max_chars,
                indicator_format=page_format,
                show_indicator=show_indicator,
                sub_citations=not keep_citation,
                keep_parent_citation=keep_citation,
            )

        slide_contents = paginate_verses(
            verses=verses,
            parent_ref=ref,
            config=config,
            pagination=pagination,
            pericope_title=pericope_title,
            tags=slide_tags,
        )

        if not slide_contents:
            slide_contents = [
                SlideContent(
                    text=verse_text,
                    citation=citation_str,
                    translation=used_id,
                    pericope_title=pericope_title,
                    tags=slide_tags,
                )
            ]

        engine = get_default_engine()
        try:
            if output_dir:
                out_dir_path = Path(output_dir).resolve()
                results = engine.render_sequence_to_dir(
                    slide_contents,
                    destination_dir=out_dir_path,
                    file_prefix=f"slide_{safe_stem}",
                    config=config,
                )
            else:
                assert dest_path is not None
                results = engine.render_sequence_to_files(
                    slide_contents,
                    destination=dest_path,
                    config=config,
                )

            if len(results) == 1:
                result = results[0]
                size_str = f"{len(result.data):,} bytes"
                self.stdout.write(f"\n✓ Generated {result.width}x{result.height} {result.format.upper()} slide ({size_str}) via {result.backend}:\n")
                self.stdout.write(f"  • File:     {result.file_path or dest_path}\n")
                self.stdout.write(f"  • Passage:  {citation_str} ({used_id})\n")
                self.stdout.write(f"  • Theme:    {theme_obj.name}\n")
                if config.citation_color:
                    self.stdout.write(f"  • Citation: {config.citation_color} ({config.citation_style})\n")
                if slide_tags:
                    self.stdout.write(f"  • Tags:     {', '.join(slide_tags)}\n")
                self.stdout.write("\n")
            else:
                res0 = results[0]
                self.stdout.write(f"\n✓ Generated {len(results)}-slide sequence ({res0.width}x{res0.height} {res0.format.upper()}) via {res0.backend}:\n")
                self.stdout.write(f"  • Passage:  {citation_str} ({used_id})\n")
                self.stdout.write(f"  • Theme:    {theme_obj.name}\n")
                self.stdout.write(f"  • Sequence: {len(results)} slides auto-paginated for display readability\n")
                for i, res in enumerate(results):
                    c = slide_contents[i]
                    size_str = f"{len(res.data):,} bytes"
                    ind = f"[{c.page_indicator}]" if c.page_indicator else f"[{i+1}/{len(results)}]"
                    self.stdout.write(f"    {ind:<9} {res.file_path} ({size_str}) — {c.citation}\n")
                self.stdout.write("\n")

            if open_viewer and results:
                target_open = results[0].file_path or dest_path
                if target_open:
                    try:
                        import subprocess
                        opener = "open" if sys.platform == "darwin" else "xdg-open"
                        subprocess.Popen([opener, str(target_open)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass
        except ImageMagickNotFoundError as exc:
            self.stdout.write(f"ImageMagick Error: {exc}\nTip: Run with '--backend svg' or install ImageMagick.\n\n")
        except RenderError as exc:
            self.stdout.write(f"Render Error: {exc}\n\n")

    def do_render(self, arg: str) -> None:
        """Alias for /slide."""
        self.do_slide(arg)

    def complete_slide(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Autocompletion for /slide command."""
        from core.render import STANDARD_THEMES
        from core.reference import ALL_BOOKS
        themes = list(STANDARD_THEMES.keys())
        books = [b.name for b in ALL_BOOKS]
        opts = [
            "-o", "-r", "-t", "-f", "-c", "-d", "--output-dir", "--paginate", "--no-paginate",
            "--max-verses", "--max-lines", "--max-chars", "--page-format", "--no-page-indicator",
            "--keep-citation", "--backend", "--font", "--font-size", "--line-spacing",
            "--align", "--citation-style", "--citation-color", "--accent-color", "--safe-area",
            "--optical-center", "--no-balance", "--tags", "--open", "--list-themes", "--list-resolutions",
            "4k", "1080p", "720p", "square", "png", "svg", "jpg",
            "center", "left", "right", "below", "smallcaps", "none",
        ] + themes + books
        return [o for o in opts if o.lower().startswith(text.lower())]

    def do_slide_batch(self, arg: str) -> None:
        """Batch export visual verse slides: /slide-batch [--favorites|--plan <name>|--tag <name>] [options]"""
        if self.db is None:
            self._init_db()

        tokens = shlex.split(arg) if arg.strip() else []
        from core.plans import format_plans_table, get_plan, list_plans
        from core.render import (
            ImageMagickNotFoundError,
            PaginationConfig,
            RenderConfig,
            RenderError,
            get_theme,
            normalize_color,
            parse_resolution,
        )
        from core.slide_batch import BatchExportConfig, SlideBatchExporter

        if "--list-plans" in tokens or "-l" in tokens:
            self.stdout.write(format_plans_table(styling=self.use_color) + "\n\n")
            return

        favs = "--favorites" in tokens
        starred_only = "--starred-only" in tokens
        plan_name = None
        tag_name = None
        book_name = None
        file_path = None
        out_dir = None
        title = None
        res_str = "4k"
        theme_str = "oled_black"
        fmt_str = "png"
        backend_str = "auto"
        limit = None
        offset = 0
        shuffle = "--shuffle" in tokens
        sequential = "--sequential" in tokens or "-s" in tokens
        no_paginate = "--no-paginate" in tokens
        open_after = "--open" in tokens
        json_out = "--json" in tokens

        i = 0
        refs: List[str] = []
        while i < len(tokens):
            t = tokens[i]
            if t in ("--plan", "--reading-plan") and i + 1 < len(tokens):
                plan_name = tokens[i + 1]
                i += 2
            elif t == "--tag" and i + 1 < len(tokens):
                tag_name = tokens[i + 1]
                i += 2
            elif t == "--book" and i + 1 < len(tokens):
                book_name = tokens[i + 1]
                i += 2
            elif t == "--file" and i + 1 < len(tokens):
                file_path = tokens[i + 1]
                i += 2
            elif t in ("--output-dir", "-d") and i + 1 < len(tokens):
                out_dir = tokens[i + 1]
                i += 2
            elif t == "--title" and i + 1 < len(tokens):
                title = tokens[i + 1]
                i += 2
            elif t in ("--resolution", "-r") and i + 1 < len(tokens):
                res_str = tokens[i + 1]
                i += 2
            elif t in ("--theme", "-t") and i + 1 < len(tokens):
                theme_str = tokens[i + 1]
                i += 2
            elif t in ("--output-format", "-f", "--format") and i + 1 < len(tokens):
                fmt_str = tokens[i + 1]
                i += 2
            elif t in ("--backend", "-b") and i + 1 < len(tokens):
                backend_str = tokens[i + 1]
                i += 2
            elif t in ("--limit", "-n") and i + 1 < len(tokens):
                try:
                    limit = int(tokens[i + 1])
                except ValueError:
                    pass
                i += 2
            elif t == "--offset" and i + 1 < len(tokens):
                try:
                    offset = int(tokens[i + 1])
                except ValueError:
                    pass
                i += 2
            elif t in (
                "--favorites", "--starred-only", "--shuffle", "--sequential", "-s",
                "--no-paginate", "--open", "--json", "--list-plans"
            ):
                i += 1
            else:
                refs.append(t)
                i += 1

        if not (favs or tag_name or book_name or plan_name or file_path or refs):
            self.stdout.write(
                "Usage: /slide-batch [--favorites|--plan <name>|--tag <name>|--book <name>] [options]\n"
                "Examples:\n"
                "  /slide-batch --favorites --starred-only -f svg\n"
                "  /slide-batch --plan sermon_on_the_mount\n"
                "  /slide-batch --plan psalms_of_ascent -r 1080p\n"
                "  /slide-batch --list-plans\n\n"
            )
            return

        w, h = parse_resolution(res_str)
        theme = get_theme(theme_str)
        render_cfg = RenderConfig(
            width=w,
            height=h,
            theme=theme,
            backend=backend_str,
            output_format=fmt_str,
        )

        pagination = PaginationConfig(enabled=not no_paginate)

        folder_slug = "shell_batch"
        if favs:
            folder_slug = "favorites_starred" if starred_only else "favorites"
        elif plan_name:
            folder_slug = f"plan_{re.sub(r'[^a-zA-Z0-9_]+', '_', plan_name).strip('_').lower()}"
        elif tag_name:
            folder_slug = f"tag_{re.sub(r'[^a-zA-Z0-9_]+', '_', tag_name).strip('_').lower()}"
        elif book_name:
            folder_slug = f"book_{re.sub(r'[^a-zA-Z0-9_]+', '_', book_name).strip('_').lower()}"

        dest_dir = Path(out_dir).resolve() if out_dir else Path.cwd() / "exports" / "slides" / folder_slug
        album_title = title or (f"Reading Plan: {plan_name}" if plan_name else "Scripture Screensaver Album")

        export_config = BatchExportConfig(
            destination_dir=dest_dir,
            render_config=render_cfg,
            pagination_config=pagination,
            album_title=album_title,
            sequential=sequential,
            shuffle=shuffle,
            limit=limit,
            offset=offset,
            quiet=True,
        )

        self.stdout.write(f"Generating batch slides ({render_cfg.width}x{render_cfg.height} {render_cfg.output_format.upper()})...\n")

        exporter = SlideBatchExporter(self.db)
        passages = exporter.resolve_passages(
            favorites=favs,
            starred_only=starred_only,
            tag=tag_name,
            book=book_name,
            plan=plan_name,
            file_path=file_path,
            references=refs if refs else None,
            translation_id=self.translation_id,
            limit=limit,
            offset=offset,
            shuffle=shuffle,
        )

        if not passages:
            self.stdout.write("Error: No matching scripture passages found to export.\n\n")
            return

        try:
            result = exporter.export_batch(export_config, passages=passages)
        except ImageMagickNotFoundError as exc:
            self.stdout.write(f"ImageMagick Error: {exc}\nTip: Run with '-f svg' or install ImageMagick.\n\n")
            return
        except RenderError as exc:
            self.stdout.write(f"Render Error: {exc}\n\n")
            return

        if json_out:
            self.stdout.write(json.dumps(result.to_dict(), indent=2) + "\n\n")
            return

        mb_size = result.total_bytes / (1024 * 1024)
        size_str = f"{mb_size:.2f} MB" if mb_size >= 1.0 else f"{result.total_bytes / 1024:.1f} KB"

        self.stdout.write(f"\n✓ Generated {result.total_slides} slides ({size_str}) in {result.duration_seconds:.2f}s:\n")
        self.stdout.write(f"  • Album:     {result.album_title}\n")
        self.stdout.write(f"  • Folder:    {result.destination_dir}\n")
        if result.gallery_path:
            self.stdout.write(f"  • Gallery:   file://{result.gallery_path}\n")
        self.stdout.write(f"  • Manifest:  manifest.json\n\n")

        if open_after and result.gallery_path:
            try:
                import subprocess
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, str(result.gallery_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def do_batch_slide(self, arg: str) -> None:
        """Alias for /slide-batch."""
        self.do_slide_batch(arg)

    def complete_slide_batch(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Autocompletion for /slide-batch command."""
        from core.plans import list_plans
        from core.render import STANDARD_THEMES
        plans = [p.name for p in list_plans()]
        themes = list(STANDARD_THEMES.keys())
        opts = [
            "--favorites", "--starred-only", "--plan", "--tag", "--book", "--list-plans",
            "-d", "--output-dir", "--title", "-r", "--resolution", "-t", "--theme",
            "-f", "--format", "--backend", "-n", "--limit", "--offset", "--shuffle",
            "--sequential", "-s", "--no-paginate", "--open", "--json",
            "4k", "1080p", "720p", "square", "png", "svg", "jpg",
        ] + plans + themes
        return [o for o in opts if o.lower().startswith(text.lower())]


    # --------------------------------------------------------------------------
    # Session Configuration Commands
    # --------------------------------------------------------------------------

    def do_version(self, arg: str) -> None:
        """Set active translation: version <ID> (e.g. version WEB, version KJV)."""
        arg = arg.strip().upper()
        if not arg:
            self.stdout.write(f"Current active translation: {self.translation_id}\n")
            return
        if self.db is None:
            self._init_db()
        available = self.db.get_available_translation_ids()
        if arg not in available:
            self.stdout.write(
                f"Warning: Translation '{arg}' has 0 verses installed (available: {', '.join(available)}).\n"
                f"Lookups will automatically cascade to WEB fallback.\n"
            )
        self.translation_id = arg
        self._update_prompt()
        self.stdout.write(f"Switched session translation to {self.translation_id}.\n")

    def do_versions(self, arg: str) -> None:
        """List installed scripture translations."""
        if self.db is None:
            self._init_db()
        translations = self.db.list_translations()
        if not translations:
            self.stdout.write("No translations registered in database.\n")
            return

        self.stdout.write("\nInstalled Scripture Translations:\n")
        for t in translations:
            count = self.db.count_verses(t.id)
            active_marker = " (active)" if t.id == self.translation_id else ""
            self.stdout.write(f"  • {t.id:6s}: {t.name:<25s} [{count:,} verses]{active_marker}\n")
        self.stdout.write("\n")

    def do_theme(self, arg: str) -> None:
        """Set color theme: theme <sacred|amber|cyan|plain>"""
        arg = arg.strip().lower()
        if not arg:
            self.stdout.write(f"Current theme: {self.theme} (options: {', '.join(THEMES.keys())})\n")
            return
        if arg not in THEMES:
            self.stdout.write(f"Unknown theme '{arg}'. Available themes: {', '.join(THEMES.keys())}\n")
            return
        self.theme = arg
        self._update_prompt()
        self.stdout.write(f"Switched theme to '{self.theme}'.\n")

    def do_margin(self, arg: str) -> None:
        """Set left indentation margin: margin <0-16>"""
        arg = arg.strip()
        if not arg:
            self.stdout.write(f"Current margin: {self.margin} spaces\n")
            return
        try:
            m = int(arg)
            if 0 <= m <= 24:
                self.margin = m
                self.stdout.write(f"Margin set to {self.margin} spaces.\n")
            else:
                self.stdout.write("Margin must be between 0 and 24 spaces.\n")
        except ValueError:
            self.stdout.write("Please provide an integer margin width.\n")

    def do_flow(self, arg: str) -> None:
        """Toggle or set paragraph flow reader mode: flow [on|off]"""
        arg = arg.strip().lower()
        if not arg:
            self.flow = not self.flow
        elif arg in ("on", "true", "1", "yes"):
            self.flow = True
        elif arg in ("off", "false", "0", "no"):
            self.flow = False
        else:
            self.stdout.write("Usage: flow [on|off]\n")
            return
        status = "ON (flowing paragraph reader)" if self.flow else "OFF (verse-by-verse list)"
        self.stdout.write(f"Paragraph flow mode: {status}\n")

    def do_box(self, arg: str) -> None:
        """Toggle or set decorative header box: box [on|off]"""
        arg = arg.strip().lower()
        if not arg:
            self.box = not self.box
        elif arg in ("on", "true", "1", "yes"):
            self.box = True
        elif arg in ("off", "false", "0", "no"):
            self.box = False
        else:
            self.stdout.write("Usage: box [on|off]\n")
            return
        status = "ON (decorative unicode box)" if self.box else "OFF (plain text bar)"
        self.stdout.write(f"Header box: {status}\n")

    def do_clear(self, arg: str) -> None:
        """Clear terminal screen."""
        os.system("clear" if os.name != "nt" else "cls")

    # --------------------------------------------------------------------------
    # Meta / Diagnostic Commands
    # --------------------------------------------------------------------------

    def do_doctor(self, arg: str) -> None:
        """Run repository health diagnostic check: /doctor [fast|install|uninstall|hooks]"""
        from tools.doctor import run_all_checks, install_hooks, uninstall_hooks, check_git_hooks, DoctorStyler
        repo_root = Path(__file__).resolve().parent.parent
        arg = arg.strip().lower()

        if arg in ("install", "install-hooks", "--install-hooks"):
            ok, msg = install_hooks(repo_root)
            self.stdout.write(msg + "\n")
            return

        if arg in ("uninstall", "uninstall-hooks", "--uninstall-hooks"):
            ok, msg = uninstall_hooks(repo_root)
            self.stdout.write(msg + "\n")
            return

        if arg in ("hooks", "check-hooks", "--check-hooks"):
            res = check_git_hooks(repo_root)
            styler = DoctorStyler(enabled=self.use_color)
            badge = styler.green("[PASS]") if res.passed else styler.red("[FAIL]")
            self.stdout.write(f"{badge} {res.name}: {res.details}\n")
            return

        fast_mode = "fast" in arg or "-f" in arg
        fix_mode = "fix" in arg or "--fix" in arg
        json_mode = "json" in arg or "--json" in arg
        bench_mode = "bench" in arg or "benchmark" in arg or "--bench" in arg
        run_all_checks(
            repo_root=repo_root,
            color=self.use_color and not json_mode,
            fast=fast_mode,
            fix=fix_mode,
            bench=bench_mode,
            json_output=json_mode,
            stream=self.stdout,
        )

    def do_test(self, arg: str) -> None:
        """Run hermetic unit test suite in parallel: /test [-p pattern] [-v] [-s] [-x] [--json]"""
        import shlex
        from tools.test_runner import run_tests
        repo_root = Path(__file__).resolve().parent.parent

        tokens = shlex.split(arg) if arg.strip() else []
        pattern = None
        verbose = False
        sequential = False
        failfast = False
        output_json = False
        warn_error = True

        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok in ("-p", "--pattern") and i + 1 < len(tokens):
                pattern = tokens[i + 1]
                i += 2
            elif tok in ("-v", "--verbose"):
                verbose = True
                i += 1
            elif tok in ("-s", "--sequential"):
                sequential = True
                i += 1
            elif tok in ("-x", "--failfast"):
                failfast = True
                i += 1
            elif tok == "--json":
                output_json = True
                i += 1
            elif tok in ("--no-warn", "--no-warn-error"):
                warn_error = False
                i += 1
            elif not tok.startswith("-") and pattern is None:
                pattern = tok
                i += 1
            else:
                i += 1

        run_tests(
            repo_root=repo_root,
            pattern=pattern,
            parallel=not sequential,
            warn_error=warn_error,
            failfast=failfast,
            verbose=verbose,
            color=self.use_color,
            output_json=output_json,
            stream=self.stdout,
        )

    def do_check(self, arg: str) -> None:
        """Alias for /test."""
        self.do_test(arg)

    def complete_test(self, text: str, line: str, start_index: int, end_index: int) -> List[str]:
        """Autocompletion for /test command."""
        options = ["-p", "--pattern", "-v", "--verbose", "-s", "--sequential", "-x", "--failfast", "--json"]
        from tools.test_runner import discover_test_files
        repo_root = Path(__file__).resolve().parent.parent
        test_stems = [p.stem.replace("test_", "") for p in discover_test_files(repo_root)]
        all_candidates = options + test_stems
        return [c for c in all_candidates if c.startswith(text)]

    def do_lint(self, arg: str) -> None:
        """Run sovereign static analysis and code hygiene audit: /lint [-p pattern] [-f/--fix] [-v] [--strict] [--json]"""
        import shlex
        from tools.linter import lint_repository
        repo_root = Path(__file__).resolve().parent.parent

        tokens = shlex.split(arg) if arg.strip() else []
        pattern = None
        fix = False
        verbose = False
        strict = False
        output_json = False

        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok in ("-p", "--pattern") and i + 1 < len(tokens):
                pattern = tokens[i + 1]
                i += 2
            elif tok in ("-f", "--fix"):
                fix = True
                i += 1
            elif tok in ("-v", "--verbose"):
                verbose = True
                i += 1
            elif tok in ("--strict", "-s"):
                strict = True
                i += 1
            elif tok == "--json":
                output_json = True
                i += 1
            elif not tok.startswith("-") and pattern is None:
                pattern = tok
                i += 1
            else:
                i += 1

        lint_repository(
            repo_root=repo_root,
            pattern=pattern,
            fix=fix,
            strict=strict,
            verbose=verbose,
            color=self.use_color,
            output_json=output_json,
            stream=self.stdout,
        )

    def do_check_style(self, arg: str) -> None:
        """Alias for /lint."""
        self.do_lint(arg)

    def complete_lint(self, text: str, line: str, start_index: int, end_index: int) -> List[str]:
        """Autocompletion for /lint command."""
        options = ["-p", "--pattern", "-f", "--fix", "-v", "--verbose", "--strict", "--json"]
        return [c for c in options if c.startswith(text)]

    def do_coverage(self, arg: str) -> None:
        """Audit test coverage across repository modules: /coverage [-p pattern] [-m module] [-u] [--json] [--html path]"""
        import shlex
        from tools.coverage import collect_coverage, format_terminal_table, generate_html_report
        repo_root = Path(__file__).resolve().parent.parent

        tokens = shlex.split(arg) if arg.strip() else []
        pattern = None
        target_module = None
        missed_only = False
        output_json = False
        html_path = None
        sequential = False

        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok in ("-p", "--pattern") and i + 1 < len(tokens):
                pattern = tokens[i + 1]
                i += 2
            elif tok in ("-m", "--module") and i + 1 < len(tokens):
                target_module = tokens[i + 1]
                i += 2
            elif tok in ("--html",) and i + 1 < len(tokens):
                html_path = tokens[i + 1]
                i += 2
            elif tok in ("-u", "--uncovered", "--missed"):
                missed_only = True
                i += 1
            elif tok in ("-s", "--sequential"):
                sequential = True
                i += 1
            elif tok == "--json":
                output_json = True
                i += 1
            elif not tok.startswith("-") and target_module is None:
                target_module = tok
                i += 1
            else:
                i += 1

        report = collect_coverage(
            repo_root=repo_root,
            test_pattern=pattern,
            target_module=target_module,
            parallel=not sequential,
        )
        if html_path:
            generate_html_report(report, Path(html_path).resolve())

        if output_json:
            self.stdout.write(report.to_json(indent=2) + "\n")
        else:
            self.stdout.write(
                "\n"
                + format_terminal_table(
                    report,
                    color=self.use_color,
                    show_missed_only=missed_only,
                )
                + "\n"
            )
            if html_path:
                self.stdout.write(f"[HTML Report] Saved to {Path(html_path).resolve()}\n")

    def do_cov(self, arg: str) -> None:
        """Alias for /coverage."""
        self.do_coverage(arg)

    def complete_coverage(self, text: str, line: str, start_index: int, end_index: int) -> List[str]:
        """Autocompletion for /coverage command."""
        options = ["-p", "--pattern", "-m", "--module", "-u", "--missed", "-s", "--sequential", "--json", "--html", "core", "cli", "tools", "web"]
        return [c for c in options if c.startswith(text)]

    def do_bench(self, arg: str) -> None:
        """Run sovereign performance benchmarks & statistical latency profiler.
        Usage:
          /bench [-q/--quick] [-c <cat>] [-p <pat>] [--compare-baseline] [--json]
        """
        import shlex
        from tools.benchmark import (
            BenchmarkStyler,
            format_benchmark_table,
            generate_html_report,
            load_baseline,
            run_benchmark_suite,
            save_baseline,
            DEFAULT_BASELINE_PATH,
        )

        tokens = shlex.split(arg) if arg.strip() else []
        quick = "--quick" in tokens or "-q" in tokens or "--fast" in tokens
        output_json = "--json" in tokens
        compare_base = "--compare-baseline" in tokens
        save_base = "--save-baseline" in tokens

        cat = None
        pat = None
        for i, t in enumerate(tokens):
            if t in ("-c", "--category") and i + 1 < len(tokens):
                cat = tokens[i + 1]
            elif t in ("-p", "--pattern") and i + 1 < len(tokens):
                pat = tokens[i + 1]

        categories = [c.strip() for c in cat.split(",") if c.strip()] if cat else None
        baseline_data = None
        if compare_base:
            baseline_data = load_baseline(DEFAULT_BASELINE_PATH)

        self.stdout.write("[Benchmarking] Executing statistical latency measurements...\n")
        suite = run_benchmark_suite(
            categories=categories,
            pattern=pat,
            quick=quick,
            baseline=baseline_data,
            baseline_path_str=".benchmark_baseline.json" if compare_base else None,
        )

        if save_base:
            save_baseline(suite, DEFAULT_BASELINE_PATH)
            self.stdout.write(f"[Saved] Baseline saved to {DEFAULT_BASELINE_PATH}\n")

        if output_json:
            self.stdout.write(suite.to_json(indent=2, include_raw=False) + "\n")
        else:
            styler = BenchmarkStyler(enabled=self.use_color)
            self.stdout.write(format_benchmark_table(suite, styler=styler) + "\n")

    def do_benchmark(self, arg: str) -> None:
        """Alias for /bench."""
        self.do_bench(arg)

    def complete_bench(self, text: str, line: str, start_index: int, end_index: int) -> List[str]:
        """Autocompletion for /bench command."""
        options = ["-q", "--quick", "-c", "--category", "-p", "--pattern", "--compare-baseline", "--save-baseline", "--json", "reference", "database", "fts", "crypto", "render", "linter", "cache"]
        return [c for c in options if c.startswith(text)]

    def complete_benchmark(self, text: str, line: str, start_index: int, end_index: int) -> List[str]:
        """Autocompletion for /benchmark command."""
        return self.complete_bench(text, line, start_index, end_index)

    def do_esv(self, arg: str) -> None:
        """Inspect ESV API configuration, ephemeral 500-verse LRU cache, and Crossway legal compliance.
        Usage:
          /esv [status]           Show configuration, quota, and cache metrics
          /esv cache              List verses currently in the ephemeral cache
          /esv clear              Evict all verses from the ephemeral cache
          /esv fetch <ref>        Fetch and cache a passage via the ESV API
        """
        if self.db is None:
            self._init_db()

        from core.esv import (
            ESV_FULL_COPYRIGHT,
            ESV_MAX_CACHE_VERSES,
            ESV_SHORT_ATTRIBUTION,
            ESVError,
            get_esv_api_key,
        )

        parts = arg.strip().split()
        subcmd = parts[0].lower() if parts else "status"

        api_key = get_esv_api_key()
        has_key = bool(api_key and api_key.strip())
        masked_key = f"...{api_key[-4:]}" if has_key and len(api_key) >= 8 else ("Configured" if has_key else "Unset")

        if subcmd == "clear":
            cleared = self.db.clear_esv_cache()
            self.stdout.write(f"Cleared ephemeral ESV cache ({cleared} verses evicted).\n")
            return

        if subcmd == "fetch":
            citation = " ".join(parts[1:]).strip()
            if not citation:
                self.stdout.write("Usage: /esv fetch <reference> (e.g. /esv fetch John 3:16)\n")
                return

            try:
                ref = parse_reference(citation)
            except Exception as exc:
                self.stdout.write(f"Error parsing reference '{citation}': {exc}\n")
                return

            if not has_key:
                self.stdout.write("ESV API key is not configured. Set ESV_API_KEY environment variable.\n")
                return

            client = self.db.get_esv_client()
            try:
                verses = client.fetch_verses(ref)
            except ESVError as exc:
                self.stdout.write(f"ESV API error: {exc}\n")
                return

            saved = self.db.save_esv_cached_verses(verses)
            self.stdout.write(f"=== {ref.format()} (ESV) ===\n\n")
            for v in verses:
                self.stdout.write(f"[{v.verse}] {v.text}\n")
            self.stdout.write(f"\nAttribution: {ESV_SHORT_ATTRIBUTION}\n")
            self.stdout.write(f"(Saved {saved} verses to cache; total {self.db.count_esv_cached_verses()}/{ESV_MAX_CACHE_VERSES})\n")
            return

        if subcmd == "cache":
            cur = self.db.conn.cursor()
            cur.execute(
                """
                SELECT c.canonical_verse_id, b.name as book_name, c.chapter, c.verse, c.text, c.last_accessed_at
                FROM esv_cache c
                JOIN books b ON b.id = c.book_id
                ORDER BY c.canonical_verse_id ASC
                """
            )
            rows = cur.fetchall()
            cur.close()
            if not rows:
                self.stdout.write("Ephemeral ESV cache is currently empty (0 / 500 verses).\n")
                return

            self.stdout.write(f"=== Ephemeral ESV Cache ({len(rows)} / {ESV_MAX_CACHE_VERSES} verses) ===\n")
            self.stdout.write(f"{'Citation':<20} {'Last Accessed':<24} {'Text Snippet'}\n")
            self.stdout.write(f"{'-' * 18} {'-' * 22} {'-' * 35}\n")
            for r in rows[:30]:
                cite = f"{r['book_name']} {r['chapter']}:{r['verse']}"
                snippet = (r["text"][:32] + "...") if len(r["text"]) > 35 else r["text"]
                self.stdout.write(f"{cite:<20} {r['last_accessed_at']:<24} {snippet}\n")
            if len(rows) > 30:
                self.stdout.write(f"... and {len(rows) - 30} more cached verses.\n")
            return

        # Default: status
        stats = self.db.get_esv_cache_stats()
        cached = stats["cached_verses"]
        pct = (cached / ESV_MAX_CACHE_VERSES) * 100
        comp_str = "COMPLIANT (<= 500 verses)" if stats["compliant"] else "NON-COMPLIANT"

        key_status = f"Configured ({masked_key})" if has_key else "Not Configured (Set ESV_API_KEY)"
        self.stdout.write(
            "\n"
            "======================================================================\n"
            " Crossway ESV API & Ephemeral 500-Verse LRU Cache Status (ADR-041)\n"
            "======================================================================\n"
            f" ESV API Key:           {key_status}\n"
            f" API Base Endpoint:     https://api.esv.org/v3/passage/text/\n"
            f" Standard Rate Limits:  60 req/min, 5,000 req/day\n"
            "----------------------------------------------------------------------\n"
            f" Ephemeral Cache Usage: {cached} / {ESV_MAX_CACHE_VERSES} verses ({pct:.1f}%)\n"
            f" Compliance Status:     {comp_str}\n"
            f" Oldest Accessed:       {stats['oldest_accessed_at'] or 'N/A'}\n"
            f" Newest Accessed:       {stats['newest_accessed_at'] or 'N/A'}\n"
            "----------------------------------------------------------------------\n"
            " Crossway Legal Attribution Notice:\n"
            f" {ESV_FULL_COPYRIGHT}\n"
            " Web: https://www.esv.org\n"
            "======================================================================\n\n"
        )

    def complete_esv(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Autocompletion for /esv command."""
        options = ["status", "cache", "clear", "fetch"]
        return [o for o in options if o.startswith(text.lower())]

    def do_gemini(self, arg: str) -> None:
        """Inspect Gemini API configuration, generate completions, or build passage prompt contexts.
        Usage:
          /gemini [status]                 Show API key configuration and model endpoints
          /gemini context <citation>       Build structured passage context (defaults to ESV)
          /gemini prompt <query>           Generate LLM completion from prompt
          /gemini embed <text>             Compute text embedding vector
        """
        from core.llm import (
            DEFAULT_EMBEDDING_MODEL,
            DEFAULT_GEMINI_MODEL,
            FALLBACK_GEMINI_MODEL,
            GEMINI_API_BASE_URL,
            GeminiClient,
            LLMError,
            build_passage_context,
            get_gemini_api_key,
        )

        parts = arg.strip().split(maxsplit=1)
        subcmd = parts[0].lower() if parts else "status"
        rest = parts[1].strip() if len(parts) > 1 else ""

        api_key = get_gemini_api_key()
        has_key = bool(api_key and api_key.strip())
        masked_key = f"...{api_key[-4:]}" if has_key and len(api_key) >= 8 else ("Configured" if has_key else "Unset")

        if subcmd == "context":
            if not rest:
                self.stdout.write("Usage: /gemini context <reference> (e.g. /gemini context John 3:16)\n")
                return
            if self.db is None:
                self._init_db()
            try:
                ctx = build_passage_context(rest, db=self.db, translation="ESV")
                self.stdout.write(f"\n=== Passage Context: {ctx.reference} ({ctx.translation}) ===\n")
                self.stdout.write(f"{ctx.format_prompt_block(include_attribution=True)}\n\n")
            except Exception as exc:
                self.stdout.write(f"Error building passage context: {exc}\n")
            return

        if subcmd == "prompt":
            if not rest:
                self.stdout.write("Usage: /gemini prompt <query> (e.g. /gemini prompt Explain Romans 8:28)\n")
                return
            if not has_key:
                self.stdout.write("Gemini API key is not configured. Set GEMINI_API_KEY environment variable.\n")
                return
            client = GeminiClient(api_key=api_key)
            try:
                self.stdout.write("Querying Google Gemini API...\n")
                resp = client.generate(rest)
                self.stdout.write(f"\n{resp.text}\n")
                if resp.fallback_used:
                    self.stdout.write(f"(Fallback model '{resp.model}' was utilized)\n")
                self.stdout.write(f"\n[Model: {resp.model} | Latency: {resp.latency_seconds:.2f}s | Tokens: {resp.usage.get('total_tokens', 0)}]\n\n")
            except LLMError as exc:
                self.stdout.write(f"Gemini API error: {exc}\n")
            return

        if subcmd == "embed":
            if not rest:
                self.stdout.write("Usage: /gemini embed <text> (e.g. /gemini embed In the beginning)\n")
                return
            if not has_key:
                self.stdout.write("Gemini API key is not configured. Set GEMINI_API_KEY environment variable.\n")
                return
            client = GeminiClient(api_key=api_key)
            try:
                vec = client.embed_content(rest)
                self.stdout.write(f"Generated vector embedding: dimension={len(vec)}, preview={vec[:5]}...\n")
            except LLMError as exc:
                self.stdout.write(f"Embedding error: {exc}\n")
            return

        # Default: status
        key_status = f"Configured ({masked_key})" if has_key else "Not Configured (Set GEMINI_API_KEY)"
        self.stdout.write(
            "\n"
            "======================================================================\n"
            " Google Gemini LLM Client & Context Engine (ADR-006 / ADR-041)\n"
            "======================================================================\n"
            f" Gemini API Key:        {key_status}\n"
            f" Primary Model:         {DEFAULT_GEMINI_MODEL}\n"
            f" Fallback Model:        {FALLBACK_GEMINI_MODEL} (Automatic on 404/429/failures)\n"
            f" Embedding Model:       {DEFAULT_EMBEDDING_MODEL}\n"
            f" Endpoint Base URL:     {GEMINI_API_BASE_URL}\n"
            f" Architecture:          100% Zero-Dependency Python stdlib (urllib.request)\n"
            f" Passage Context:       Defaults to ESV with Crossway legal compliance\n"
            "----------------------------------------------------------------------\n"
            " REPL Commands:\n"
            "   /gemini status              Inspect API key and models\n"
            "   /gemini context <ref>       Build structured passage context\n"
            "   /gemini prompt <text>       Generate completion from prompt\n"
            "   /gemini embed <text>        Generate semantic embedding\n"
            "======================================================================\n\n"
        )

    do_llm = do_gemini

    def complete_gemini(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Autocompletion for /gemini command."""
        options = ["status", "context", "prompt", "embed"]
        return [o for o in options if o.startswith(text.lower())]

    complete_llm = complete_gemini

    def do_ask(self, arg: str) -> None:
        """Query Scripture RAG engine with biblical, thematic, or typological inquiries.
        Usage:
          /ask <query>                      Retrieve grounded Scripture passages and answer via LLM
          /ask --context-only <query>       Inspect retrieved Scripture passages and scores without LLM
          /ask --show-context <query>       Synthesize answer and show underlying Scripture context
        """
        raw_text = arg.strip()
        if not raw_text:
            self.stdout.write("Usage: /ask [--context-only] [--show-context] <query>\n")
            return

        context_only = False
        show_context = False

        tokens = raw_text.split()
        filtered_tokens = []
        for t in tokens:
            if t in ("--context-only", "-c"):
                context_only = True
            elif t in ("--show-context", "-s"):
                show_context = True
            else:
                filtered_tokens.append(t)

        query = " ".join(filtered_tokens).strip()
        if not query:
            self.stdout.write("Usage: /ask [--context-only] [--show-context] <query>\n")
            return

        if self.db is None:
            self._init_db()

        from core.rag import ScriptureRAGEngine
        from core.llm import GeminiClient, LLMError, get_gemini_api_key

        engine = ScriptureRAGEngine(db=self.db, translation=self.translation_id)
        context = engine.retrieve(
            query,
            max_passages=5,
            max_tokens=4000,
            preferred_translation=self.translation_id,
        )

        gold = "\033[1;33m" if self.use_color else ""
        dim = "\033[2m" if self.use_color else ""
        bold = "\033[1m" if self.use_color else ""
        reset = "\033[0m" if self.use_color else ""

        if context_only:
            self.stdout.write(f"\n{gold}{bold}=== Scripture RAG Retrieved Context ==={reset}\n")
            self.stdout.write(f"{bold}Inquiry:{reset} {query}\n")
            self.stdout.write(f"{dim}Passages: {len(context.passages)} | Total Verses: {context.total_verses} | Est. Tokens: {context.estimated_tokens}{reset}\n\n")

            if not context.passages:
                self.stdout.write(f"{dim}(No matching scripture passages found for this inquiry.){reset}\n\n")
                return

            for idx, p in enumerate(context.passages, 1):
                reasons_str = f" [{', '.join(p.retrieval_reasons)}]" if p.retrieval_reasons else ""
                self.stdout.write(f"{gold}[{idx}] {p.human_ref} ({p.translation}){reset} {dim}(Score: {p.score:.2f}{reasons_str}){reset}\n")
                if p.pericope_title:
                    self.stdout.write(f"    {dim}Pericope: {p.pericope_title}{reset}\n")
                if p.theological_loci:
                    self.stdout.write(f"    {dim}Loci: {', '.join(p.theological_loci)}{reset}\n")
                if p.thematic_ribbons:
                    self.stdout.write(f"    {dim}Thematic Ribbons: {', '.join(p.thematic_ribbons)}{reset}\n")
                if p.typological_arcs:
                    arc_summaries = [f"{a.get('type_human_ref', a.get('type_ref'))} ➔ {a.get('antitype_human_ref', a.get('antitype_ref'))}" for a in p.typological_arcs[:2]]
                    self.stdout.write(f"    {dim}Typological Arcs: {'; '.join(arc_summaries)}{reset}\n")
                self.stdout.write(f"    {p.text}\n\n")
            return

        api_key = get_gemini_api_key()
        if not api_key:
            self.stdout.write(
                f"\n{gold}Notice:{reset} GEMINI_API_KEY is not configured. Displaying retrieved Scripture context.\n"
                f"{dim}To enable AI answer synthesis, set the GEMINI_API_KEY environment variable.{reset}\n\n"
            )
            self.stdout.write(f"{gold}{bold}=== Retrieved Scripture Context ==={reset}\n")
            for idx, p in enumerate(context.passages, 1):
                self.stdout.write(f"{gold}[{idx}] {p.human_ref} ({p.translation}){reset} {dim}(Score: {p.score:.2f}){reset}\n")
                self.stdout.write(f"    {p.text}\n\n")
            return

        client = GeminiClient(api_key=api_key)
        prompt_payload = context.format_prompt_payload()
        system_text = prompt_payload["system_instruction"]["parts"][0]["text"]
        user_prompt = prompt_payload["contents"][0]["parts"][0]["text"]

        self.stdout.write(f"\n{dim}Synthesizing grounded answer via Google Gemini ({client.model})...{reset}\n\n")
        self.stdout.write(f"{bold}Inquiry:{reset} {query}\n\n")

        streamed_text = []
        try:
            for chunk in client.generate_stream(user_prompt, system_instruction=system_text):
                if chunk.text:
                    streamed_text.append(chunk.text)
                    self.stdout.write(chunk.text)
                    self.stdout.flush()
            self.stdout.write("\n\n")
        except LLMError as exc:
            self.stdout.write(f"\nError during streaming generation: {exc}\n")
            return

        if show_context:
            self.stdout.write(f"{gold}{bold}--- Retrieved Scripture Context ---{reset}\n")
            for idx, p in enumerate(context.passages, 1):
                self.stdout.write(f"{gold}[{idx}] {p.human_ref} ({p.translation}){reset} {dim}(Score: {p.score:.2f}){reset}\n")
                self.stdout.write(f"    {p.text}\n\n")

    do_rag = do_ask

    def complete_ask(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Autocompletion for /ask command."""
        options = ["--context-only", "--show-context"]
        return [o for o in options if o.startswith(text.lower())]

    complete_rag = complete_ask

    def do_summary(self, arg: str) -> None:
        """Generate executive summary and trajectory report."""
        from tools.executive_summary import generate_summary, format_markdown_report
        window = 10
        if arg.strip().isdigit():
            window = int(arg.strip())
        repo_root = Path(__file__).resolve().parent.parent
        report = generate_summary(window=window, repo_root=repo_root, run_doctor=False)
        self.stdout.write("\n" + format_markdown_report(report) + "\n\n")

    def do_serve(self, arg: str) -> None:
        """Launch, inspect, or stop the built-in HTTP web server and REST API.
        Usage:
          /serve [start|stop|status] [--port 8080] [--open]
        """
        tokens = arg.strip().split()
        cmd = tokens[0].lower() if tokens else "start"

        if cmd in ("stop", "halt", "down"):
            if self._server is not None:
                try:
                    self._server.shutdown()
                except Exception:
                    pass
                self._server = None
                self._server_thread = None
                self.stdout.write("Bible Engine web server stopped.\n")
            else:
                self.stdout.write("Web server is not running.\n")
            return

        if cmd == "status":
            if self._server is not None and self._server.is_running():
                self.stdout.write(f"Web server is active at {self._server.url}\n")
            else:
                self.stdout.write("Web server is stopped. Run '/serve start' to launch.\n")
            return

        # Start server
        if self._server is not None and self._server.is_running():
            self.stdout.write(f"Web server is already active at {self._server.url}\n")
            return

        port = 8080
        open_browser = False
        for i, t in enumerate(tokens):
            if t in ("--port", "-p") and i + 1 < len(tokens):
                try:
                    port = int(tokens[i + 1])
                except ValueError:
                    pass
            elif t.isdigit():
                port = int(t)
            elif t == "--open":
                open_browser = True

        from web.server import create_server
        try:
            self._server = create_server(
                host="127.0.0.1",
                port=port,
                database=self.db,
            )
            import threading
            t = threading.Thread(
                target=self._server.start,
                kwargs={"open_browser": open_browser},
                daemon=True,
            )
            t.start()
            self._server_thread = t
            self.stdout.write(f"✓ Bible Engine web server started at {self._server.url}\n")
            self.stdout.write(f"  • REST API: {self._server.url}/api/health\n")
            self.stdout.write("  Type '/serve stop' to stop.\n")
        except Exception as exc:
            self.stdout.write(f"Error starting web server: {exc}\n")

    def do_server(self, arg: str) -> None:
        """Alias for /serve."""
        self.do_serve(arg)

    def do_db(self, arg: str) -> None:
        """Database inspection and maintenance: /db [stats|status|optimize|vacuum|init]"""
        parts = arg.strip().split()
        sub = parts[0].lower() if parts else "stats"

        if sub in ("stats", "status"):
            from core.bootstrap import get_db_stats
            target_path = self.db_path if self.db_path else DEFAULT_DB_PATH
            stats = get_db_stats(target_path)
            if not stats["exists"]:
                self.stdout.write(f"Database does not exist at {stats['path']}. Use '/init' to create it.\n")
                return

            self.stdout.write("=================================================================\n")
            self.stdout.write(" Bible Engine Database Storage Diagnostics\n")
            self.stdout.write("=================================================================\n")
            self.stdout.write(f" File Location:        {stats['path']}\n")
            self.stdout.write(f" File Size:            {stats['size_human']} ({stats['size_bytes']:,} bytes)\n")
            self.stdout.write(f" SQLite Version:       {stats['sqlite_version']}\n")
            self.stdout.write(f" Integrity Check:      {stats['integrity_check']}\n")
            self.stdout.write(f" Journal Mode:         {stats['journal_mode'].upper()}\n")
            self.stdout.write(f" FTS5 Search Index:    {stats['fts5_status'].upper()}\n")
            self.stdout.write("-----------------------------------------------------------------\n")
            self.stdout.write(f" Total Verses:         {stats['total_verses']:,}\n")
            for tr in stats["translations"]:
                self.stdout.write(f"   - {tr['id']}: {tr['name']} ({tr['verse_count']:,} verses)\n")
            self.stdout.write(f" Total Tags:           {stats['total_tags']} taxonomies\n")
            self.stdout.write(f" Tagged Passages:      {stats['total_tagged_passages']} annotations\n")
            self.stdout.write(f" Curated Favorites:    {stats['total_favorites']} ({stats['total_starred']} starred)\n")
            self.stdout.write(f" Cross-References:     {stats['total_cross_references']} canonical links\n")
            self.stdout.write("=================================================================\n")
        elif sub == "optimize":
            if self.db is None:
                self._init_db()
            self.db.optimize()
            self.stdout.write("✓ Successfully ran PRAGMA optimize on database.\n")
        elif sub == "vacuum":
            if self.db is None:
                self._init_db()
            self.db.vacuum()
            self.stdout.write("✓ Successfully vacuumed SQLite database.\n")
        elif sub in ("init", "setup", "bootstrap"):
            self.do_init(" ".join(parts[1:]))
        else:
            self.stdout.write(f"Unknown db action '{sub}'. Available: stats, status, optimize, vacuum, init\n")

    def do_init(self, arg: str) -> None:
        """Bootstrap or repair scripture database: /init [--force] [--quick]"""
        from core.bootstrap import bootstrap_database
        parts = arg.strip().split()
        force = "--force" in parts or "-f" in parts
        quick = "--quick" in parts

        target_path = self.db_path if self.db_path else DEFAULT_DB_PATH
        self.stdout.write("Bootstrapping scripture database...\n")
        rep = bootstrap_database(
            db_path=target_path,
            force=force,
            quick=quick,
            verbose=False,
        )
        self.stdout.write(f"✓ Bootstrap complete in {rep.duration_sec:.2f}s: {rep.details}\n")
        self.stdout.write(f"  Verses: {rep.verses_count:,} | Tags: {rep.tags_count} | Cross-Refs: {rep.cross_references_count}\n")

    def do_vector(self, arg: str) -> None:
        """Zero-dependency vector similarity engine: /vector [status|search <query>|similar <ref>]"""
        parts = arg.strip().split()
        sub = parts[0].lower() if parts else "status"

        if self.db is None:
            self._init_db()

        if sub in ("status", "stats"):
            verse_count = self.db.count_verse_embeddings()
            pericope_count = self.db.count_pericope_embeddings()
            self.stdout.write("=================================================================\n")
            self.stdout.write(" Zero-Dependency Vector Similarity Engine (ADR-003 / ADR-051)\n")
            self.stdout.write("=================================================================\n")
            self.stdout.write(f" Verse Embeddings:      {verse_count:,} stored\n")
            self.stdout.write(f" Pericope Embeddings:   {pericope_count:,} stored\n")
            self.stdout.write(f" Standard Dimensions:   768 (text-embedding-004)\n")
            self.stdout.write(f" Quantization Scheme:   Int8 signed [-127, 127] (4x compression)\n")
            self.stdout.write(f" Index Architecture:    Two-Tier (768-bit Sign Hash Filter + Exact Int8 Rerank)\n")
            self.stdout.write(f" Whole-Bible Target:    31,102 verses searchable in <15ms without external DBs\n")
            self.stdout.write("=================================================================\n")
        elif sub == "similar":
            if len(parts) < 2:
                self.stdout.write("Usage: /vector similar <reference> (e.g. /vector similar John 3:16)\n")
                return
            ref_str = " ".join(parts[1:])
            from core.reference import parse_reference
            from core.vector import VectorIndex, DEFAULT_VECTOR_DIM
            try:
                ref_obj = parse_reference(ref_str)
            except Exception as e:
                self.stdout.write(f"Invalid reference '{ref_str}': {e}\n")
                return

            source_emb = self.db.get_verse_embedding(ref_obj)
            if not source_emb:
                self.stdout.write(f"No vector embedding stored for '{ref_obj.format()}'.\n")
                return

            idx = VectorIndex(dimensions=DEFAULT_VECTOR_DIM)
            idx.build_from_database(self.db, table="verse_embeddings")
            matches = idx.search(source_emb.embedding, top_k=10)
            self.stdout.write(f"=== Semantically Related Verses for {ref_obj.format()} ===\n")
            for m in matches:
                pct = int(round(m.score * 100))
                bar = "█" * (pct // 10) + "░" * (10 - (pct // 10))
                self.stdout.write(f" {m.rank:2d}. {m.human_ref:<18} [{bar}] {m.score:+.4f}\n")
        elif sub == "search":
            if len(parts) < 2:
                self.stdout.write("Usage: /vector search <query> (e.g. /vector search light and salvation)\n")
                return
            query_str = " ".join(parts[1:])
            from core.llm import GeminiClient, get_gemini_api_key
            from core.vector import VectorIndex, DEFAULT_VECTOR_DIM
            api_key = get_gemini_api_key()
            if not api_key:
                self.stdout.write("GEMINI_API_KEY required to generate embedding for vector search.\n")
                return
            client = GeminiClient(api_key=api_key)
            try:
                vec = client.embed_content(query_str)
            except Exception as exc:
                self.stdout.write(f"Error computing query embedding: {exc}\n")
                return

            if self.db.count_verse_embeddings() == 0:
                self.stdout.write("No verse embeddings stored in database. Populate via Phase 7 compilation.\n")
                return

            idx = VectorIndex(dimensions=DEFAULT_VECTOR_DIM)
            idx.build_from_database(self.db, table="verse_embeddings")
            matches = idx.search(vec, top_k=10)
            self.stdout.write(f"=== Semantic Vector Matches for '{query_str}' ===\n")
            for m in matches:
                pct = int(round(m.score * 100))
                bar = "█" * (pct // 10) + "░" * (10 - (pct // 10))
                self.stdout.write(f" {m.rank:2d}. {m.human_ref:<18} [{bar}] {m.score:+.4f}\n")
        else:
            self.stdout.write(f"Unknown vector action '{sub}'. Available: status, similar, search\n")

    def do_vec(self, arg: str) -> None:
        """Alias for /vector."""
        self.do_vector(arg)

    def complete_vector(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete for /vector actions."""
        options = ["status", "similar", "search"]
        return [o for o in options if o.startswith(text.lower())]

    def complete_vec(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete for /vec alias."""
        return self.complete_vector(text, line, begidx, endidx)

    def do_build_semantic(self, arg: str) -> None:
        """Resumable batch semantic compiler & whole-Bible database builder.

        Usage:
          /build-semantic status              Inspect compilation ledger status
          /build-semantic dry-run [book]      Preview compilation units
          /build-semantic run [book]          Execute compilation
          /build-semantic reset-failed        Reset failed units back to PENDING
        """
        parts = arg.strip().split()
        action = parts[0].lower() if parts else "status"

        from tools.build_semantic_db import run_semantic_build
        db_path = self.db_path

        if action == "status":
            run_semantic_build(db_path=db_path, status_only=True)
        elif action == "dry-run":
            b_filter = parts[1] if len(parts) > 1 else None
            run_semantic_build(db_path=db_path, book_filter=b_filter, dry_run=True)
        elif action == "reset-failed":
            run_semantic_build(db_path=db_path, reset_failed=True)
        elif action in ("run", "start", "compile"):
            b_filter = parts[1] if len(parts) > 1 else None
            run_semantic_build(db_path=db_path, book_filter=b_filter)
        else:
            self.stdout.write(f"Unknown action '{action}'. Available: status, dry-run, run, reset-failed\n")

    def do_compile_semantic(self, arg: str) -> None:
        """Alias for /build-semantic."""
        self.do_build_semantic(arg)

    def complete_build_semantic(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete for /build-semantic."""
        options = ["status", "dry-run", "run", "reset-failed"]
        return [o for o in options if o.startswith(text.lower())]

    def complete_compile_semantic(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete for /compile-semantic."""
        return self.complete_build_semantic(text, line, begidx, endidx)

    def do_audit_semantic(self, arg: str) -> None:
        """Audit semantic database coordinates, schema validation, and whole-Bible coverage.

        Usage:
          /audit-semantic                 Run complete whole-Bible semantic audit
          /audit-semantic [book]          Audit a specific book (e.g. /audit-semantic Romans)
          /audit-semantic --json          Output machine-readable JSON telemetry
          /audit-semantic --verbose       Display detailed finding descriptions
          /audit-semantic --strict        Enforce strict error severity
        """
        import shlex
        from tools.audit_semantic import run_semantic_audit

        tokens = shlex.split(arg) if arg.strip() else []
        book_filter = None
        json_mode = False
        verbose_mode = False
        strict_mode = False
        coverage = True

        for tok in tokens:
            if tok in ("--json", "-j"):
                json_mode = True
            elif tok in ("--verbose", "-v"):
                verbose_mode = True
            elif tok in ("--strict", "-s"):
                strict_mode = True
            elif tok in ("--no-coverage", "-nc"):
                coverage = False
            elif not tok.startswith("-"):
                book_filter = tok

        run_semantic_audit(
            db_path=self.db_path,
            include_coverage=coverage,
            book_filter=book_filter,
            json_output=json_mode,
            verbose=verbose_mode,
            strict=strict_mode,
            stream=self.stdout,
        )

    def do_audit(self, arg: str) -> None:
        """Alias for /audit-semantic."""
        self.do_audit_semantic(arg)

    def complete_audit_semantic(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete for /audit-semantic."""
        options = ["--json", "--verbose", "--strict", "--no-coverage"]
        book_names = [b.name for b in ALL_BOOKS if b.name.lower().startswith(text.lower())]
        return [o for o in options if o.startswith(text.lower())] + book_names

    def complete_audit(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete for /audit alias."""
        return self.complete_audit_semantic(text, line, begidx, endidx)

    # --------------------------------------------------------------------------
    # GitHub Issues & Bug Triage Commands
    # --------------------------------------------------------------------------

    def do_issues(self, arg: str) -> None:
        """Inspect and triage GitHub issues and bug reports.

        Usage:
          /issues [list] [--state=open|closed|all] [--limit=N]
          /issues view <number>
          /issues comment <number> <text>
          /issues close <number> [--reason=completed|not_planned] [--comment="<text>"]
          /issues check
        """
        import shlex
        from tools import github_issues
        parts = shlex.split(arg) if arg.strip() else ["list"]
        github_issues.main(parts)

    def do_bug(self, arg: str) -> None:
        """Alias for /issues."""
        self.do_issues(arg)

    def do_bugs(self, arg: str) -> None:
        """Alias for /issues."""
        self.do_issues(arg)

    def complete_issues(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete for /issues command."""
        commands = ["list", "view", "comment", "close", "check", "--state=open", "--state=closed", "--json"]
        return [c for c in commands if c.startswith(text.lower())]

    # --------------------------------------------------------------------------
    # Exit & Help Commands
    # --------------------------------------------------------------------------

    def do_help(self, arg: str) -> None:
        """Show command reference guide."""
        help_text = f"""
Bible Engine Interactive Scripture Shell — Command Reference
============================================================
Direct Citation:
  <citation>              Directly fetch and render passage (e.g. 'John 3:16', 'Rom 8:28-30')

Study & Search:
  /get <citation>         Lookup passage explicitly
  /search <query>         Full-text scripture search (aliases: /find)
  /compare <ref> [ver]    Compare passage across translations (e.g. /compare 'John 1:1' WEB,KJV)
  /tag <action> [args]    Semantic tagging and passage annotations (aliases: /tags)
  /ribbon [tag]           Display visual Redemptive Ribbon topical heatmap across 66 books
  /crossref <action> ...  Scripture cross-referencing and relationships (aliases: /xref, /refs)
  /arcs [options]         Render pure vector SVG Typological Arc Network & explore fulfillments (alias: /typology)
  /vector [action]        Semantic vector similarity engine & search (alias: /vec)
  /build-semantic [act]   Resumable batch semantic compiler & whole-Bible builder (alias: /compile-semantic)
  /audit-semantic [opts]  Audit semantic database coordinates & 100% whole-Bible coverage (alias: /audit)
  /slide <ref> [options]  Generate 4K/1080p visual verse slide for TV screensavers (alias: /render)
  /slide-batch [options]  Batch export 4K scripture slides for TV screensavers (alias: /batch_slide)
  /ask <query> [options]  Query Scripture RAG engine with biblical inquiries (alias: /rag)
  /issues [command]       Inspect and triage GitHub issues & bug reports (aliases: /bug, /bugs)

Session Settings:
  /version [ID]           Show or set active translation (e.g. /version KJV)
  /versions               List installed translations and verse statistics
  /theme [name]           Show or set ANSI theme (sacred, amber, cyan, plain)
  /margin [N]             Set left indentation margin (spaces)
  /flow [on|off]          Toggle continuous paragraph reader mode
  /box [on|off]           Toggle decorative header box

System & Web:
  /db [stats|optimize]    Inspect database storage statistics or optimize query planner
  /init [--force]         Bootstrap offline database and verify baseline datasets
  /serve [start|stop]     Start or stop built-in HTTP server and Web UI (alias: /server)
  /esv [status|cache|clear] Manage Crossway ESV API & 500-verse LRU cache
  /gemini [status|context] Google Gemini LLM client, model fallback & prompt context (alias: /llm)
  /test [pattern]         Run hermetic unit test suite in parallel (alias: /check)
  /bench [options]        Run performance benchmarks & statistical latency profiler (alias: /benchmark)
  /doctor                 Run comprehensive repository health check
  /summary [window]       Generate executive trajectory report
  /clear                  Clear terminal screen
  exit, quit, Ctrl+D      Exit shell
"""
        self.stdout.write(help_text)

    def do_exit(self, arg: str) -> bool:
        """Exit the scripture shell."""
        self.stdout.write("Grace and peace to you.\n")
        return True

    def do_quit(self, arg: str) -> bool:
        """Exit the scripture shell."""
        return self.do_exit(arg)

    def do_EOF(self, arg: str) -> bool:
        """Handle Ctrl+D (EOF) cleanly."""
        self.stdout.write("\n")
        return self.do_exit(arg)

    # --------------------------------------------------------------------------
    # Auto-Completion
    # --------------------------------------------------------------------------

    def complete_db(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete db actions."""
        options = ["stats", "status", "optimize", "vacuum", "init"]
        return [o for o in options if o.startswith(text.lower())]

    def complete_init(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete init flags."""
        options = ["--force", "--quick"]
        return [o for o in options if o.startswith(text.lower())]

    def complete_doctor(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete doctor subcommands."""
        options = [
            "fast", "fix", "bench", "benchmark", "json", "install-hooks", "uninstall-hooks", "hooks",
            "--fast", "--fix", "--bench", "--benchmark", "--json",
        ]
        return [o for o in options if o.startswith(text.lower())]

    def complete_tag(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete tag subcommands and tag names."""
        subcommands = [
            "add", "list", "show", "for", "remove", "delete", "stats",
            "density", "ribbon", "co-occurrence", "relevance", "seed", "prompt",
        ]
        parts = line.split()
        if len(parts) <= 1 or (len(parts) == 2 and not line.endswith(" ")):
            return [c for c in subcommands if c.startswith(text.lower())]

        action = parts[1].lower() if len(parts) > 1 else ""
        if action in ("show", "delete", "stats", "density", "ribbon", "relevance", "co-occurrence") or (action == "remove" and len(parts) >= 3):
            if self.db is None:
                self._init_db()
            from core.tags import TaggingService
            svc = TaggingService(self.db)
            tags = [t.name for t in svc.list_tags()]
            return [t for t in tags if t.lower().startswith(text.lower())]

        return []

    def complete_ribbon(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete for /ribbon tag names."""
        if self.db is None:
            self._init_db()
        from core.tags import TaggingService
        svc = TaggingService(self.db)
        tags = [t.name for t in svc.list_tags()]
        return [t for t in tags if t.lower().startswith(text.lower())]

    def complete_tags(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete for /tags alias."""
        return self.complete_tag(text, line, begidx, endidx)

    def complete_crossref(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete crossref subcommands and relationship types."""
        subcommands = ["for", "link", "unlink", "list", "path", "stats", "seed"]
        parts = line.split()
        if len(parts) <= 1 or (len(parts) == 2 and not line.endswith(" ")):
            return [c for c in subcommands if c.startswith(text.lower())]

        action = parts[1].lower() if len(parts) > 1 else ""
        if action in ("for", "list") or (action == "link" and len(parts) >= 4):
            from core.crossref import RelationshipType
            return [r for r in RelationshipType.ALL if r.startswith(text.lower())]

        return []

    def complete_xref(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete for /xref alias."""
        return self.complete_crossref(text, line, begidx, endidx)

    def complete_refs(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete for /refs alias."""
        return self.complete_crossref(text, line, begidx, endidx)

    def complete_theme(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete theme names."""
        return [t for t in THEMES.keys() if t.startswith(text.lower())]

    def complete_version(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete translation identifiers."""
        if self.db is None:
            self._init_db()
        return [v for v in self.db.get_available_translation_ids() if v.startswith(text.upper())]

    def completenames(self, text: str, *ignored) -> List[str]:
        """Support auto-completion for slash commands as well as normal commands."""
        dotext = "do_" + text
        names = [a[3:] for a in self.get_names() if a.startswith(dotext)]
        slash_names = ["/" + a[3:] for a in self.get_names() if a.startswith("do_" + text.lstrip("/"))]
        # Also complete Protestant book names!
        book_names = [b.name for b in ALL_BOOKS if b.name.lower().startswith(text.lower())]
        return names + slash_names + book_names


def launch_shell(
    db_path: Optional[Path] = None,
    translation_id: str = "WEB",
    theme: str = "sacred",
    margin: int = 2,
    flow: bool = False,
    box: bool = True,
) -> int:
    """Launch interactive scripture shell session."""
    shell = BibleShell(
        db_path=db_path,
        translation_id=translation_id,
        theme=theme,
        margin=margin,
        flow=flow,
        box=box,
    )
    try:
        shell.cmdloop()
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted. Exiting shell.")
        return 0
    finally:
        shell.close()
