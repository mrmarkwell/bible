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
        self.db: Optional[Database] = None
        self._init_db()
        self._update_prompt()

    def _init_db(self) -> None:
        """Initialize or reopen SQLite database connection."""
        if self.db is not None:
            self.db.close()
        self.db = Database(self.db_path, auto_init=True)

    def _update_prompt(self) -> None:
        """Update prompt with current translation and color styling."""
        v_tag = f"[{self.translation_id}]"
        if self.use_color and self.theme != "plain":
            self.prompt = f"\033[1;33mbible\033[0m \033[2m{v_tag}\033[0m> "
        else:
            self.prompt = f"bible {v_tag}> "

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

            handler = getattr(self, f"do_{cmd_name}", None)
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

        else:
            self.stdout.write(f"Unknown tag action '{action}'. Available: add, list, show, for, remove, delete, stats, seed\n")

    def do_tags(self, arg: str) -> None:
        """Alias for /tag."""
        self.do_tag(arg)

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

        fast_mode = arg in ("fast", "--fast", "-f")
        run_all_checks(
            repo_root=repo_root,
            color=self.use_color,
            fast=fast_mode,
            stream=self.stdout,
        )

    def do_summary(self, arg: str) -> None:
        """Generate executive summary and trajectory report."""
        from tools.executive_summary import generate_summary, format_markdown_report
        window = 10
        if arg.strip().isdigit():
            window = int(arg.strip())
        repo_root = Path(__file__).resolve().parent.parent
        report = generate_summary(window=window, repo_root=repo_root, run_doctor=False)
        self.stdout.write("\n" + format_markdown_report(report) + "\n\n")

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

Session Settings:
  /version [ID]           Show or set active translation (e.g. /version KJV)
  /versions               List installed translations and verse statistics
  /theme [name]           Show or set ANSI theme (sacred, amber, cyan, plain)
  /margin [N]             Set left indentation margin (spaces)
  /flow [on|off]          Toggle continuous paragraph reader mode
  /box [on|off]           Toggle decorative header box

System:
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

    def complete_doctor(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete doctor subcommands."""
        options = ["fast", "install-hooks", "uninstall-hooks", "hooks"]
        return [o for o in options if o.startswith(text.lower())]

    def complete_tag(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete tag subcommands and tag names."""
        subcommands = ["add", "list", "show", "for", "remove", "delete", "stats", "seed"]
        parts = line.split()
        if len(parts) <= 1 or (len(parts) == 2 and not line.endswith(" ")):
            return [c for c in subcommands if c.startswith(text.lower())]

        action = parts[1].lower() if len(parts) > 1 else ""
        if action in ("show", "delete", "stats") or (action == "remove" and len(parts) >= 3):
            if self.db is None:
                self._init_db()
            from core.tags import TaggingService
            svc = TaggingService(self.db)
            tags = [t.name for t in svc.list_tags()]
            return [t for t in tags if t.lower().startswith(text.lower())]

        return []

    def complete_tags(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Auto-complete for /tags alias."""
        return self.complete_tag(text, line, begidx, endidx)

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
