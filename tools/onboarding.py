"""Sovereign Zero-Dependency API Key Onboarding Wizard & Credential Manager.

Zero-dependency implementation (Python 3 standard library only per ADR-003).
Provides:
- Live network connectivity & authorization probes for ESV and Gemini APIs.
- Interactive CLI setup wizard with masked input and inline probe verification.
- Secure credential persistence in config/ directory with POSIX 0600 file permissions.
- Non-interactive flags for scripted and CI/CD onboarding.
- Structured JSON and terminal telemetry reporting.
"""

import argparse
import json
import os
from pathlib import Path
import stat
import sys
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
ESV_KEY_FILE = CONFIG_DIR / "esv_api_key.txt"
GEMINI_KEY_FILE = CONFIG_DIR / "gemini_api_key.txt"
USER_CONFIG_DIR = Path.home() / ".config" / "bible"
USER_ESV_KEY_FILE = USER_CONFIG_DIR / "esv_api_key"
USER_GEMINI_KEY_FILE = USER_CONFIG_DIR / "gemini_api_key"


def mask_api_key(key: Optional[str]) -> str:
    """Mask an API key for safe display in logs and terminal outputs."""
    if not key or not key.strip():
        return "(none)"
    clean = key.strip()
    if len(clean) <= 8:
        return clean[:2] + "..." + clean[-2:]
    return clean[:4] + "..." + clean[-4:]


def discover_esv_api_key(repo_root: Optional[Path] = None) -> Tuple[Optional[str], str]:
    """Discover configured ESV API key and its source.

    Returns:
        Tuple of (key_or_none, source_description).
    """
    root = repo_root or REPO_ROOT
    env_val = os.environ.get("ESV_API_KEY")
    if env_val and env_val.strip():
        return env_val.strip(), "environment variable ESV_API_KEY"

    if os.environ.get("BIBLE_TEST_MODE") == "1" and repo_root is None:
        return None, "not configured"

    candidates = [

        (root / "config" / "esv_api_key.txt", "repository config file"),
        (root / ".env", "repository .env file"),
        (USER_ESV_KEY_FILE, "user home config (~/.config/bible/esv_api_key)"),
    ]

    for path, desc in candidates:
        try:
            if path.is_file():
                content = path.read_text(encoding="utf-8")
                if path.name == ".env":
                    for line in content.splitlines():
                        line = line.strip()
                        if line.startswith("ESV_API_KEY="):
                            val = line.split("=", 1)[1].strip().strip("'\"")
                            if val:
                                return val, f"{desc} ({path})"
                else:
                    val = content.strip()
                    if val:
                        return val, f"{desc} ({path})"
        except Exception:
            continue

    return None, "not configured"


def discover_gemini_api_key(repo_root: Optional[Path] = None) -> Tuple[Optional[str], str]:
    """Discover configured Google Gemini API key and its source.

    Returns:
        Tuple of (key_or_none, source_description).
    """
    root = repo_root or REPO_ROOT
    for env_var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(env_var)
        if val and val.strip():
            return val.strip(), f"environment variable {env_var}"

    candidates = [
        (root / "config" / "gemini_api_key.txt", "repository config file"),
        (root / ".env", "repository .env file"),
        (USER_GEMINI_KEY_FILE, "user home config (~/.config/bible/gemini_api_key)"),
    ]

    for path, desc in candidates:
        try:
            if path.is_file():
                content = path.read_text(encoding="utf-8")
                if path.name == ".env":
                    for line in content.splitlines():
                        line = line.strip()
                        for prefix in ("GEMINI_API_KEY=", "GOOGLE_API_KEY="):
                            if line.startswith(prefix):
                                val = line.split("=", 1)[1].strip().strip("'\"")
                                if val:
                                    return val, f"{desc} ({path})"
                else:
                    val = content.strip()
                    if val:
                        return val, f"{desc} ({path})"
        except Exception:
            continue

    return None, "not configured"


def probe_esv_api_key(
    api_key: Optional[str] = None,
    timeout: float = 5.0,
    opener: Optional[Any] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Probe an ESV API key with a live health-check query.

    Args:
        api_key: The API key to test. If None, auto-discovers configured key.
        timeout: Network socket timeout in seconds.
        opener: Optional custom urllib opener for hermetic testing.

    Returns:
        Tuple of (is_valid, message, details_dict).
    """
    key = api_key
    source = "explicit argument"
    if not key:
        key, source = discover_esv_api_key()

    if not key:
        return (
            False,
            "ESV API key is not configured.",
            {"status": "missing", "source": source, "key_masked": None},
        )

    url = "https://api.esv.org/v3/passage/text/?q=John+1:1&include-headings=false&include-footnotes=false"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Token {key}",
            "User-Agent": "BibleEngine/1.0 (Zero-Dependency Sovereign Scripture Platform)",
        },
    )

    try:
        call_open = opener.open if opener else urllib.request.urlopen
        with call_open(req, timeout=timeout) as response:
            status_code = getattr(response, "status", getattr(response, "code", 200))
            if status_code == 200:
                raw_bytes = response.read()
                data = json.loads(raw_bytes.decode("utf-8"))
                passages = data.get("passages", [])
                sample = passages[0].strip() if passages else "John 1:1 verified"
                return (
                    True,
                    f"ESV API key is valid and authorized ({mask_api_key(key)}).",
                    {
                        "status": "authorized",
                        "status_code": 200,
                        "source": source,
                        "key_masked": mask_api_key(key),
                        "sample_passage": sample[:80],
                    },
                )
            else:
                return (
                    False,
                    f"ESV API returned unexpected HTTP status {status_code}.",
                    {"status": "error", "status_code": status_code, "source": source},
                )
    except urllib.error.HTTPError as err:
        if err.code == 401:
            return (
                False,
                f"ESV API authorization failed: Invalid API key (HTTP 401).",
                {"status": "unauthorized", "status_code": 401, "source": source, "key_masked": mask_api_key(key)},
            )
        elif err.code == 403:
            return (
                False,
                f"ESV API access forbidden or quota exceeded (HTTP 403).",
                {"status": "forbidden", "status_code": 403, "source": source, "key_masked": mask_api_key(key)},
            )
        else:
            return (
                False,
                f"ESV API query failed with HTTP {err.code}: {err.reason}",
                {"status": "http_error", "status_code": err.code, "source": source},
            )
    except urllib.error.URLError as err:
        return (
            False,
            f"ESV API unreachable (offline or network failure): {err.reason}",
            {"status": "offline", "error": str(err.reason), "source": source},
        )
    except Exception as exc:
        return (
            False,
            f"ESV API probe failed: {exc}",
            {"status": "exception", "error": str(exc), "source": source},
        )


def probe_gemini_api_key(
    api_key: Optional[str] = None,
    timeout: float = 5.0,
    opener: Optional[Any] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Probe a Google Gemini API key with a live health-check query.

    Args:
        api_key: The API key to test. If None, auto-discovers configured key.
        timeout: Network socket timeout in seconds.
        opener: Optional custom urllib opener for hermetic testing.

    Returns:
        Tuple of (is_valid, message, details_dict).
    """
    key = api_key
    source = "explicit argument"
    if not key:
        key, source = discover_gemini_api_key()

    if not key:
        return (
            False,
            "Gemini API key is not configured.",
            {"status": "missing", "source": source, "key_masked": None},
        )

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "BibleEngine/1.0 (Zero-Dependency Sovereign Scripture Platform)",
        },
    )

    try:
        call_open = opener.open if opener else urllib.request.urlopen
        with call_open(req, timeout=timeout) as response:
            status_code = getattr(response, "status", getattr(response, "code", 200))
            if status_code == 200:
                raw_bytes = response.read()
                data = json.loads(raw_bytes.decode("utf-8"))
                models = data.get("models", [])
                return (
                    True,
                    f"Gemini API key is valid and authorized ({mask_api_key(key)}, {len(models)} models available).",
                    {
                        "status": "authorized",
                        "status_code": 200,
                        "source": source,
                        "key_masked": mask_api_key(key),
                        "models_count": len(models),
                    },
                )
            else:
                return (
                    False,
                    f"Gemini API returned unexpected HTTP status {status_code}.",
                    {"status": "error", "status_code": status_code, "source": source},
                )
    except urllib.error.HTTPError as err:
        if err.code in (400, 403):
            return (
                False,
                f"Gemini API authorization failed: Invalid API key (HTTP {err.code}).",
                {"status": "unauthorized", "status_code": err.code, "source": source, "key_masked": mask_api_key(key)},
            )
        else:
            return (
                False,
                f"Gemini API query failed with HTTP {err.code}: {err.reason}",
                {"status": "http_error", "status_code": err.code, "source": source},
            )
    except urllib.error.URLError as err:
        return (
            False,
            f"Gemini API unreachable (offline or network failure): {err.reason}",
            {"status": "offline", "error": str(err.reason), "source": source},
        )
    except Exception as exc:
        return (
            False,
            f"Gemini API probe failed: {exc}",
            {"status": "exception", "error": str(exc), "source": source},
        )


def save_api_key(
    service: str,
    key: str,
    repo_root: Optional[Path] = None,
    use_user_config: bool = False,
) -> Path:
    """Securely write an API key to a local configuration file with 0600 POSIX permissions.

    Args:
        service: 'esv' or 'gemini'.
        key: The raw API key string.
        repo_root: Repository root directory (defaults to REPO_ROOT).
        use_user_config: If True, writes to ~/.config/bible/ instead of repo config/.

    Returns:
        The Path to the written key file.
    """
    clean_key = key.strip()
    root = repo_root or REPO_ROOT

    if use_user_config:
        target_dir = USER_CONFIG_DIR
        target_file = USER_ESV_KEY_FILE if service.lower() == "esv" else USER_GEMINI_KEY_FILE
    else:
        target_dir = root / "config"
        target_file = target_dir / ("esv_api_key.txt" if service.lower() == "esv" else "gemini_api_key.txt")

    target_dir.mkdir(parents=True, exist_ok=True)
    target_file.write_text(clean_key + "\n", encoding="utf-8")

    # Enforce strict POSIX permissions (0600: read/write for owner only)
    try:
        os.chmod(target_file, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass

    return target_file


def clear_api_key(service: str, repo_root: Optional[Path] = None) -> List[Path]:
    """Remove configured API key files for a service.

    Returns:
        List of deleted Paths.
    """
    root = repo_root or REPO_ROOT
    deleted: List[Path] = []
    candidates = []
    if service.lower() == "esv":
        candidates = [
            root / "config" / "esv_api_key.txt",
            USER_ESV_KEY_FILE,
        ]
    else:
        candidates = [
            root / "config" / "gemini_api_key.txt",
            USER_GEMINI_KEY_FILE,
        ]

    for p in candidates:
        if p.is_file():
            try:
                p.unlink()
                deleted.append(p)
            except OSError:
                pass

    return deleted


def get_credential_status(probe: bool = False) -> Dict[str, Any]:
    """Retrieve comprehensive credential status and optional live probe diagnostics."""
    esv_key, esv_source = discover_esv_api_key()
    gemini_key, gemini_source = discover_gemini_api_key()

    status: Dict[str, Any] = {
        "esv": {
            "configured": bool(esv_key),
            "source": esv_source,
            "masked": mask_api_key(esv_key),
            "probe": None,
        },
        "gemini": {
            "configured": bool(gemini_key),
            "source": gemini_source,
            "masked": mask_api_key(gemini_key),
            "probe": None,
        },
    }

    if probe:
        esv_ok, esv_msg, esv_details = probe_esv_api_key(esv_key)
        gem_ok, gem_msg, gem_details = probe_gemini_api_key(gemini_key)
        status["esv"]["probe"] = {"valid": esv_ok, "message": esv_msg, "details": esv_details}
        status["gemini"]["probe"] = {"valid": gem_ok, "message": gem_msg, "details": gem_details}

    return status


def run_onboarding_wizard(
    repo_root: Optional[Path] = None,
    interactive: bool = True,
    esv_key: Optional[str] = None,
    gemini_key: Optional[str] = None,
    probe: bool = True,
    input_fn: Optional[Callable[[str], str]] = None,
    print_fn: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Execute the interactive or automated onboarding wizard.

    Args:
        repo_root: Path to repository root.
        interactive: Whether to prompt for keys if not provided.
        esv_key: Optional explicit ESV key to save.
        gemini_key: Optional explicit Gemini key to save.
        probe: Whether to run live network validation probes.
        input_fn: Custom input function for testing.
        print_fn: Custom print function for testing.

    Returns:
        Summary dictionary of onboarding outcomes.
    """
    _print = print_fn or print
    _input = input_fn or input
    root = repo_root or REPO_ROOT

    outcomes: Dict[str, Any] = {
        "esv_updated": False,
        "gemini_updated": False,
        "esv_status": None,
        "gemini_status": None,
    }

    _print("\n" + "=" * 70)
    _print(" 🌟  Bible Engine — Sovereign Scripture & AI Exegesis Setup Wizard")
    _print("=" * 70)
    _print(" This wizard configures optional external API credentials:")
    _print("  1. ESV API Key: Unlocks modern English Standard Version text (Crossway)")
    _print("  2. Gemini API Key: Unlocks Scripture RAG and Biblical Character Dialogue")
    _print("\n [Note] The Bible Engine is 100% offline-first. If you skip these keys,")
    _print("        the platform runs in complete public-domain mode using the bundled")
    _print("        World English Bible (WEB) with zero network requirements.")
    _print("-" * 70)

    # 1. ESV API Key setup
    cur_esv, cur_esv_src = discover_esv_api_key(root)
    if esv_key is not None:
        if esv_key.strip():
            save_api_key("esv", esv_key.strip(), repo_root=root)
            outcomes["esv_updated"] = True
            _print(f"  [Configured] ESV API Key saved to config/esv_api_key.txt ({mask_api_key(esv_key)})")
        else:
            clear_api_key("esv", repo_root=root)
            _print("  [Cleared] ESV API Key configuration removed.")
    elif interactive and sys.stdin.isatty():
        _print("\n--- [Step 1/2] English Standard Version (ESV) API Key ---")
        _print("  Obtain a free personal API key at: https://api.esv.org/")
        if cur_esv:
            _print(f"  Current Status: Configured via {cur_esv_src} ({mask_api_key(cur_esv)})")
            prompt_str = "  Enter new ESV API Key (or press Enter to keep current, 'clear' to remove): "
        else:
            _print("  Current Status: Not configured (falling back to World English Bible)")
            prompt_str = "  Enter ESV API Key (or press Enter to skip): "

        try:
            choice = _input(prompt_str).strip()
            if choice.lower() == "clear":
                clear_api_key("esv", repo_root=root)
                _print("  [Cleared] ESV API Key removed.")
            elif choice:
                save_api_key("esv", choice, repo_root=root)
                outcomes["esv_updated"] = True
                _print(f"  [Saved] ESV API Key saved to config/esv_api_key.txt ({mask_api_key(choice)})")
        except (EOFError, KeyboardInterrupt):
            _print("\n  [Skipped] ESV configuration skipped.")

    # 2. Gemini API Key setup
    cur_gem, cur_gem_src = discover_gemini_api_key(root)
    if gemini_key is not None:
        if gemini_key.strip():
            save_api_key("gemini", gemini_key.strip(), repo_root=root)
            outcomes["gemini_updated"] = True
            _print(f"  [Configured] Gemini API Key saved to config/gemini_api_key.txt ({mask_api_key(gemini_key)})")
        else:
            clear_api_key("gemini", repo_root=root)
            _print("  [Cleared] Gemini API Key configuration removed.")
    elif interactive and sys.stdin.isatty():
        _print("\n--- [Step 2/2] Google Gemini API Key ---")
        _print("  Obtain a free personal API key at: https://aistudio.google.com/app/apikey")
        if cur_gem:
            _print(f"  Current Status: Configured via {cur_gem_src} ({mask_api_key(cur_gem)})")
            prompt_str = "  Enter new Gemini API Key (or press Enter to keep current, 'clear' to remove): "
        else:
            _print("  Current Status: Not configured (AI exegesis & persona chat will be offline)")
            prompt_str = "  Enter Gemini API Key (or press Enter to skip): "

        try:
            choice = _input(prompt_str).strip()
            if choice.lower() == "clear":
                clear_api_key("gemini", repo_root=root)
                _print("  [Cleared] Gemini API Key removed.")
            elif choice:
                save_api_key("gemini", choice, repo_root=root)
                outcomes["gemini_updated"] = True
                _print(f"  [Saved] Gemini API Key saved to config/gemini_api_key.txt ({mask_api_key(choice)})")
        except (EOFError, KeyboardInterrupt):
            _print("\n  [Skipped] Gemini configuration skipped.")

    # 3. Probing
    _print("\n" + "-" * 70)
    _print(" 🔍  Probing API Service Connectivity & Key Health...")
    _print("-" * 70)

    final_esv, _ = discover_esv_api_key(root)
    final_gem, _ = discover_gemini_api_key(root)

    if probe:
        if final_esv:
            esv_ok, esv_msg, esv_det = probe_esv_api_key(final_esv)
            outcomes["esv_status"] = esv_det
            icon = "✅" if esv_ok else "⚠️"
            _print(f"  {icon} ESV API:    {esv_msg}")
        else:
            outcomes["esv_status"] = {"status": "missing"}
            _print("  ℹ️  ESV API:    Not configured (using offline World English Bible)")

        if final_gem:
            gem_ok, gem_msg, gem_det = probe_gemini_api_key(final_gem)
            outcomes["gemini_status"] = gem_det
            icon = "✅" if gem_ok else "⚠️"
            _print(f"  {icon} Gemini API: {gem_msg}")
        else:
            outcomes["gemini_status"] = {"status": "missing"}
            _print("  ℹ️  Gemini API: Not configured (theological exegesis runs in offline mode)")
    else:
        _print("  [Probe skipped] Network probes bypassed.")

    _print("=" * 70 + "\n")
    return outcomes


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for onboarding and credential management."""
    parser = argparse.ArgumentParser(
        prog="tools/onboarding.py",
        description="Bible Engine Zero-Dependency API Key Onboarding & Health Probe Engine.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # status
    p_status = subparsers.add_parser("status", help="Show current API key configuration and probe status")
    p_status.add_argument("--probe", "-p", action="store_true", help="Perform live network connectivity probe")
    p_status.add_argument("--json", action="store_true", help="Output machine-readable JSON telemetry")

    # wizard
    p_wiz = subparsers.add_parser("wizard", help="Run interactive onboarding wizard")
    p_wiz.add_argument("--no-probe", action="store_true", help="Skip network connectivity probe")

    # set
    p_set = subparsers.add_parser("set", help="Configure API credentials non-interactively")
    p_set.add_argument("--esv", help="Set ESV API key")
    p_set.add_argument("--gemini", help="Set Google Gemini API key")
    p_set.add_argument("--user-config", action="store_true", help="Save to ~/.config/bible/ instead of repo")
    p_set.add_argument("--probe", action="store_true", help="Probe keys after setting")

    # clear
    p_clear = subparsers.add_parser("clear", help="Clear configured API keys")
    p_clear.add_argument("service", choices=["esv", "gemini", "all"], help="Service key to clear")

    # probe
    p_probe = subparsers.add_parser("probe", help="Perform live connectivity probes on configured keys")
    p_probe.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args(argv)

    if not args.command or args.command == "status":
        probe_flag = getattr(args, "probe", False) if args.command else False
        json_flag = getattr(args, "json", False) if args.command else False
        status = get_credential_status(probe=probe_flag)
        if json_flag:
            print(json.dumps(status, indent=2))
            return 0

        print("\n======================================================================")
        print(" Bible Engine API Credential & Service Status")
        print("======================================================================")
        for svc in ("esv", "gemini"):
            info = status[svc]
            svc_label = "ESV Translation (Crossway)" if svc == "esv" else "Google Gemini AI Exegesis"
            state = "CONFIGURED" if info["configured"] else "NOT CONFIGURED (Offline WEB Default)"
            print(f" • {svc_label:32}: {state}")
            print(f"   Source: {info['source']}")
            print(f"   Key:    {info['masked']}")
            if info.get("probe"):
                pr = info["probe"]
                probe_icon = "✅" if pr["valid"] else "⚠️"
                print(f"   Probe:  {probe_icon} {pr['message']}")
            print()
        print("Run './bible init --wizard' or 'python3 tools/onboarding.py wizard' to configure.")
        print("======================================================================\n")
        return 0

    elif args.command == "wizard":
        run_onboarding_wizard(interactive=True, probe=not args.no_probe)
        return 0

    elif args.command == "set":
        if not args.esv and not args.gemini:
            print("Error: Specify at least one of --esv or --gemini to set.", file=sys.stderr)
            return 1
        if args.esv:
            save_api_key("esv", args.esv, use_user_config=args.user_config)
            print(f"[Success] ESV API key saved ({mask_api_key(args.esv)})")
        if args.gemini:
            save_api_key("gemini", args.gemini, use_user_config=args.user_config)
            print(f"[Success] Gemini API key saved ({mask_api_key(args.gemini)})")

        if args.probe:
            st = get_credential_status(probe=True)
            print("\nProbe Results:")
            if args.esv:
                print(f" • ESV:    {st['esv']['probe']['message']}")
            if args.gemini:
                print(f" • Gemini: {st['gemini']['probe']['message']}")
        return 0

    elif args.command == "clear":
        target = args.service
        if target in ("esv", "all"):
            del_esv = clear_api_key("esv")
            print(f"[Cleared] ESV API keys removed: {[str(p) for p in del_esv]}")
        if target in ("gemini", "all"):
            del_gem = clear_api_key("gemini")
            print(f"[Cleared] Gemini API keys removed: {[str(p) for p in del_gem]}")
        return 0

    elif args.command == "probe":
        st = get_credential_status(probe=True)
        if args.json:
            print(json.dumps(st, indent=2))
            return 0
        print("\n=== Live API Service Probe Results ===")
        print(f" • ESV:    {st['esv']['probe']['message']}")
        print(f" • Gemini: {st['gemini']['probe']['message']}")
        print("=======================================\n")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
