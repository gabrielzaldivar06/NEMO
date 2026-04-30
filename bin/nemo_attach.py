#!/usr/bin/env python3
"""
nemo-attach — drop NEMO memory rules into any project so the AI working
there is forced to use NEMO as persistent memory.

Usage:
    python bin/nemo_attach.py                        # interactive menu
    python bin/nemo_attach.py --target /path/to/project
    python bin/nemo_attach.py --clients claude,copilot
    python bin/nemo_attach.py --clients all
    python bin/nemo_attach.py --with-hooks           # also installs Claude Code hooks

Supported clients:
    claude    → CLAUDE.md                            (Claude Code / Claude Desktop)
    copilot   → .github/copilot-instructions.md      (GitHub Copilot — multi-IDE)
    cursor    → .cursor/rules/nemo.mdc               (Cursor)
    windsurf  → .windsurfrules                       (Windsurf)
    aider     → AGENTS.md                            (Aider / Codex)
    gemini    → .gemini/styleguide.md                (Gemini Code Assist)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

VERSION = "2"
MARKER_BEGIN = f"<!-- BEGIN NEMO RULES v{VERSION} -->"
MARKER_END = "<!-- END NEMO RULES -->"
MARKER_PREFIX = "<!-- BEGIN NEMO RULES"  # version-agnostic, for detection
MARKER_RE = re.compile(
    rf"{re.escape(MARKER_PREFIX)}.*?{re.escape(MARKER_END)}",
    re.DOTALL,
)

DEFAULT_NEMO_URL = os.environ.get("NEMO_URL", "http://localhost:8765")


# ── Per-client target descriptors ────────────────────────────────────────────
@dataclass
class Target:
    key: str
    path: str
    formatter: Callable[[str], str]
    label: str


def _plain(body: str) -> str:
    return f"{MARKER_BEGIN}\n{body.rstrip()}\n{MARKER_END}\n"


def _cursor_mdc(body: str) -> str:
    front = (
        "---\n"
        "description: NEMO persistent memory rules — required reading every turn.\n"
        "alwaysApply: true\n"
        "---\n\n"
    )
    return front + _plain(body)


def _gemini(body: str) -> str:
    header = "# NEMO Memory Rules\n\n"
    return header + _plain(body)


TARGETS: list[Target] = [
    Target("claude",   "CLAUDE.md",                        _plain,      "Claude Code / Claude Desktop"),
    Target("copilot",  ".github/copilot-instructions.md",  _plain,      "GitHub Copilot (multi-IDE)"),
    Target("cursor",   ".cursor/rules/nemo.mdc",           _cursor_mdc, "Cursor"),
    Target("windsurf", ".windsurfrules",                   _plain,      "Windsurf"),
    Target("aider",    "AGENTS.md",                        _plain,      "Aider / Codex"),
    Target("gemini",   ".gemini/styleguide.md",            _gemini,     "Gemini Code Assist"),
]

# Menu display order with friendly labels
MENU: list[tuple[str, str, str]] = [
    ("claude",   "Claude Code / Claude Desktop",  "CLAUDE.md"),
    ("copilot",  "GitHub Copilot",                ".github/copilot-instructions.md"),
    ("cursor",   "Cursor",                        ".cursor/rules/nemo.mdc"),
    ("windsurf", "Windsurf",                      ".windsurfrules"),
    ("aider",    "Aider / Codex",                 "AGENTS.md"),
    ("gemini",   "Gemini Code Assist",            ".gemini/styleguide.md"),
]


# ── Template loading ─────────────────────────────────────────────────────────
def find_template() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent / "templates" / "nemo-rules.md",
        Path("/app/templates/nemo-rules.md"),
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        "Could not locate templates/nemo-rules.md. Looked at:\n  "
        + "\n  ".join(str(c) for c in candidates)
    )


# ── Health check ─────────────────────────────────────────────────────────────
def health_check(url: str, timeout: float = 2.0) -> tuple[bool, str]:
    try:
        probe = url.replace("//localhost", "//host.docker.internal", 1) \
            if Path("/.dockerenv").exists() else url
        with urllib.request.urlopen(f"{probe}/health", timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data.get("status") == "ok", data.get("status", "unknown")
    except urllib.error.URLError as exc:
        return False, f"unreachable ({exc.reason})"
    except Exception as exc:
        return False, f"error ({type(exc).__name__}: {exc})"


# ── Per-target write logic ────────────────────────────────────────────────────
def apply_target(target: Target, root: Path, body: str, dry_run: bool) -> str:
    payload = target.formatter(body)
    dest = root / target.path
    dest.parent.mkdir(parents=True, exist_ok=True)

    if not dest.exists():
        if dry_run:
            return "dry-run (would create)"
        dest.write_text(payload, encoding="utf-8")
        return "created"

    existing = dest.read_text(encoding="utf-8")

    if MARKER_PREFIX in existing and MARKER_END in existing:
        m = MARKER_RE.search(payload)
        block_only = m.group(0) if m else payload.strip()
        new = MARKER_RE.sub(block_only, existing, count=1)
        if new == existing:
            return "unchanged"
        if dry_run:
            return "dry-run (would update)"
        dest.write_text(new, encoding="utf-8")
        return "updated"

    appended = existing.rstrip() + "\n\n" + payload
    if dry_run:
        return "dry-run (would append)"
    dest.write_text(appended, encoding="utf-8")
    return "appended"


# ── Claude Code hooks installer ───────────────────────────────────────────────
def install_hooks(nemo_url: str, dry_run: bool) -> str:
    settings_path = Path.home() / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        try:
            current = json.loads(settings_path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return f"skipped (cannot parse existing {settings_path})"
        if not dry_run:
            shutil.copy2(settings_path, settings_path.with_suffix(".json.bak"))
    else:
        current = {}

    hooks = current.setdefault("hooks", {})

    nemo_session_start = {
        "type": "command",
        "command": f"curl -s -X POST {nemo_url}/api/tools/prime_context -H 'Content-Type: application/json' -d '{{\"arguments\": {{}}}}'",
    }
    nemo_stop = {
        "type": "command",
        "command": f"curl -s -X POST {nemo_url}/api/tools/store_conversation -H 'Content-Type: application/json' -d '{{\"arguments\": {{\"content\": \"session ended\", \"role\": \"assistant\"}}}}' >/dev/null",
    }

    def _ensure(event: str, hook: dict) -> None:
        existing = hooks.setdefault(event, [])
        for entry in existing:
            for h in entry.get("hooks", []):
                if h.get("command") == hook["command"]:
                    return
        existing.append({"matcher": "*", "hooks": [hook]})

    _ensure("SessionStart", nemo_session_start)
    _ensure("Stop", nemo_stop)

    if dry_run:
        return f"dry-run (would update {settings_path})"
    settings_path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return f"updated {settings_path} (backup at {settings_path.with_suffix('.json.bak')})"


# ── Interactive client selector ───────────────────────────────────────────────
def prompt_clients() -> list[str]:
    print()
    print("¿Qué clientes AI usas en este proyecto?")
    print()
    for i, (key, label, path) in enumerate(MENU, 1):
        print(f"  {i}. {label:<35} ({path})")
    print(f"  {len(MENU) + 1}. Todos")
    print()

    while True:
        try:
            raw = input(f"Selecciona (ej: 1,3 o {len(MENU) + 1} para todos): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

        if not raw:
            continue

        # "all" shortcut
        if raw == str(len(MENU) + 1) or raw.lower() in {"all", "todos"}:
            return [key for key, _, _ in MENU]

        keys: list[str] = []
        valid = True
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(MENU):
                    keys.append(MENU[idx][0])
                else:
                    print(f"  Opción inválida: {part}")
                    valid = False
                    break
            elif part.lower() in {k for k, _, _ in MENU}:
                keys.append(part.lower())
            else:
                print(f"  Opción no reconocida: {part!r}")
                valid = False
                break

        if valid and keys:
            return list(dict.fromkeys(keys))  # deduplicate preserving order


# ── CLI ───────────────────────────────────────────────────────────────────────
def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nemo-attach",
        description="Drop NEMO memory rules into any project so AI clients use it automatically.",
    )
    parser.add_argument(
        "--target",
        default=None,
        help="Project directory. Defaults to /workdir (Docker) or $PWD.",
    )
    parser.add_argument(
        "--clients",
        default=None,
        help=(
            "Comma-separated clients to configure, or 'all'. "
            f"Available: {', '.join(t.key for t in TARGETS)}. "
            "Omit to get an interactive menu."
        ),
    )
    parser.add_argument(
        "--with-hooks",
        action="store_true",
        help="Install SessionStart + Stop hooks in ~/.claude/settings.json (Claude Code only).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing anything.",
    )
    parser.add_argument(
        "--nemo-url",
        default=DEFAULT_NEMO_URL,
        help=f"NEMO base URL for health check + hook commands. Default: {DEFAULT_NEMO_URL}",
    )
    return parser.parse_args(argv)


def resolve_target_dir(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    workdir = Path("/workdir")
    if workdir.is_dir():
        return workdir
    return Path.cwd().resolve()


def resolve_selected_targets(clients_arg: str | None) -> list[Target]:
    target_map = {t.key: t for t in TARGETS}

    # No --clients flag and stdin is a real terminal → show interactive menu
    if clients_arg is None and sys.stdin.isatty():
        keys = prompt_clients()
        return [target_map[k] for k in keys if k in target_map]

    # Non-interactive fallback (piped input, Docker, CI) → all clients
    if clients_arg is None:
        return list(TARGETS)

    if clients_arg.strip().lower() == "all":
        return list(TARGETS)

    keys = {k.strip() for k in clients_arg.split(",") if k.strip()}
    bad = keys - target_map.keys()
    if bad:
        raise SystemExit(
            f"Unknown client(s): {', '.join(sorted(bad))}. "
            f"Available: {', '.join(target_map)}"
        )
    return [t for t in TARGETS if t.key in keys]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    project = resolve_target_dir(args.target)
    selected = resolve_selected_targets(args.clients)
    template = find_template()
    body = template.read_text(encoding="utf-8")

    print(f"\nnemo-attach v{VERSION}")
    print(f"  project  : {project}")
    print(f"  clients  : {', '.join(t.key for t in selected)}")
    print(f"  dry-run  : {args.dry_run}")
    print()

    ok, status = health_check(args.nemo_url)
    badge = "[OK]  " if ok else "[WARN]"
    print(f"{badge} NEMO @ {args.nemo_url} — {status}")
    if not ok:
        print("       Rules will be written anyway.")
    print()

    counts: dict[str, int] = {}
    for t in selected:
        outcome = apply_target(t, project, body, args.dry_run)
        bucket = outcome.split(" ", 1)[0]
        counts[bucket] = counts.get(bucket, 0) + 1
        print(f"  {outcome:<24}  {t.path:<45}  {t.label}")

    print()
    print(f"Summary → {' · '.join(f'{k}: {v}' for k, v in sorted(counts.items()))}")

    if args.with_hooks:
        print()
        print("Hooks:")
        print(f"  {install_hooks(args.nemo_url, args.dry_run)}")
    else:
        print()
        print("Tip: pass --with-hooks to wire SessionStart + Stop into ~/.claude/settings.json")

    print()
    print("─ Connect your AI client (one-time per client) ─────────────────────────────")
    print(f"  Claude Code     → claude mcp add nemo {args.nemo_url}/mcp/sse --transport sse")
    print(f"  GitHub Copilot  → Settings → MCP → Add → stdio: python ai_memory_mcp_server.py")
    print(f"  Cursor          → Settings → MCP → Add → {args.nemo_url}/mcp/sse")
    print(f"  Windsurf        → Settings → MCP → {args.nemo_url}/mcp/sse")
    print(f"  Gemini          → Settings → Extensions → NEMO MCP")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
